#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
BASE_TABLE_PATH = REPORTS_DIR / "EXP_001_PREPARED_DATA.csv"
AEMO_TZ = ZoneInfo("Australia/Brisbane")

MARKET_STATE_SCHEMA_VERSION = "1.0"
TRANSFER_FEATURE_SET_VERSION = "1.0"
BUILDER_VERSION = "1.0"
DIGITAL_TWIN_VERSION = "digital-twin-v1.0"
RESEARCH_FRAMEWORK_VERSION = "research-framework-v1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reusable transfer-state table for any period")
    parser.add_argument("--quarter", help="Quarter token like 2024Q4")
    parser.add_argument("--start-month", help="Start month YYYY-MM")
    parser.add_argument("--end-month", help="End month YYYY-MM")
    return parser.parse_args()


def quarter_to_months(quarter: str) -> tuple[str, str]:
    token = quarter.strip().upper()
    if len(token) != 6 or token[4] != "Q":
        raise ValueError("quarter must be like 2024Q4")
    year = int(token[:4])
    q = int(token[5])
    if q not in (1, 2, 3, 4):
        raise ValueError("quarter must be Q1..Q4")
    start_month = 1 + (q - 1) * 3
    return f"{year}-{start_month:02d}", f"{year}-{start_month + 2:02d}"


def resolve_period(args: argparse.Namespace) -> tuple[str, str, str]:
    if args.quarter:
        start_month, end_month = quarter_to_months(args.quarter)
        return start_month, end_month, args.quarter.upper()
    if args.start_month and args.end_month:
        token = f"{args.start_month.replace('-', '')}_{args.end_month.replace('-', '')}"
        return args.start_month, args.end_month, token
    raise ValueError("Provide --quarter or both --start-month and --end-month")


def month_range(start_month: str, end_month: str) -> list[pd.Period]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("end-month must be >= start-month")
    out: list[pd.Period] = []
    current = start
    while current <= end:
        out.append(current)
        current += 1
    return out


def utc_bounds_from_months(start_month: str, end_month: str) -> tuple[str, str]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    start_ts = pd.Timestamp(year=start.year, month=start.month, day=1, hour=0, minute=5, tz=AEMO_TZ).tz_convert("UTC")
    end_next = end + 1
    end_ts = pd.Timestamp(year=end_next.year, month=end_next.month, day=1, hour=0, minute=0, tz=AEMO_TZ).tz_convert("UTC")
    return start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), end_ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_aemo_timestamp(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if getattr(parsed.dt, "tz", None) is None:
        parsed = parsed.dt.tz_localize(AEMO_TZ, ambiguous="NaT", nonexistent="NaT")
    return parsed.dt.tz_convert("UTC").dt.floor("5min").dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_git_commit() -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
        return proc.stdout.strip()
    except Exception:
        return "unknown"


def load_base_period(start_utc: str, end_utc: str) -> pd.DataFrame:
    base = pd.read_csv(BASE_TABLE_PATH, low_memory=False)
    base = base.copy()
    base["interval_timestamp_utc"] = base["settlement_timestamp_utc"]
    return base[(base["interval_timestamp_utc"] >= start_utc) & (base["interval_timestamp_utc"] <= end_utc)].copy()


def load_interconnector_period(months: list[pd.Period]) -> pd.DataFrame:
    cache_root = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres" / ".cache"
    paths: list[Path] = []
    for period in months:
        mm = f"{period.month:02d}"
        path = cache_root / f"year={period.year}" / f"month={mm}" / f"PUBLIC_DVD_DISPATCHINTERCONNECTORRES_{period.year}{mm}010000.dispatchinterconnectorres.csv.gz"
        if not path.exists():
            raise FileNotFoundError(f"missing cache file: {path}")
        paths.append(path)

    frame = pd.concat([pd.read_csv(path, low_memory=False) for path in paths], ignore_index=True)
    required = [
        "SETTLEMENTDATE",
        "RUNNO",
        "INTERCONNECTORID",
        "INTERVENTION",
        "METERED_MWFLOW",
        "FLOW_MW",
        "LOSSES_MW",
        "MARGINALVALUE",
        "VIOLATIONDEGREE",
        "EXPORTLIMIT_MW",
        "IMPORTLIMIT_MW",
        "MARGINALLOSS_FACTOR",
        "EXPORTGENCONID",
        "IMPORTGENCONID",
        "LASTCHANGED",
        "SOURCE_FILE",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(f"missing required interconnector columns: {missing}")

    frame = frame.copy()
    frame["interval_timestamp_utc"] = normalize_aemo_timestamp(frame["SETTLEMENTDATE"])
    frame["RUNNO"] = pd.to_numeric(frame["RUNNO"], errors="coerce")
    frame["INTERVENTION"] = pd.to_numeric(frame["INTERVENTION"], errors="coerce")
    for column in [
        "METERED_MWFLOW",
        "FLOW_MW",
        "LOSSES_MW",
        "MARGINALVALUE",
        "VIOLATIONDEGREE",
        "EXPORTLIMIT_MW",
        "IMPORTLIMIT_MW",
        "MARGINALLOSS_FACTOR",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_intervention_audit(interconnector_raw: pd.DataFrame) -> pd.DataFrame:
    compare_fields = [
        "METERED_MWFLOW",
        "FLOW_MW",
        "LOSSES_MW",
        "MARGINALVALUE",
        "VIOLATIONDEGREE",
        "EXPORTLIMIT_MW",
        "IMPORTLIMIT_MW",
        "MARGINALLOSS_FACTOR",
    ]
    grouped = interconnector_raw.groupby(["interval_timestamp_utc", "INTERCONNECTORID"], as_index=False).agg(
        row_count=("INTERVENTION", "size"),
        has_intervention_0=("INTERVENTION", lambda s: bool((s == 0).any())),
        has_intervention_1=("INTERVENTION", lambda s: bool((s == 1).any())),
    )
    grouped["intervention_pair_present"] = grouped["has_intervention_0"] & grouped["has_intervention_1"]
    grouped["intervention_values_identical"] = pd.NA

    pair_keys = grouped[grouped["intervention_pair_present"]][["interval_timestamp_utc", "INTERCONNECTORID"]]
    if not pair_keys.empty:
        paired = interconnector_raw.merge(pair_keys, on=["interval_timestamp_utc", "INTERCONNECTORID"], how="inner")
        wide = paired.pivot_table(index=["interval_timestamp_utc", "INTERCONNECTORID"], columns="INTERVENTION", values=compare_fields, aggfunc="first")
        wide.columns = [f"{c}__{int(i)}" for c, i in wide.columns]
        wide = wide.reset_index()
        identical = pd.Series(True, index=wide.index)
        for field in compare_fields:
            identical &= wide[f"{field}__0"].fillna(-999999999).eq(wide[f"{field}__1"].fillna(-999999999))
        eq = wide[["interval_timestamp_utc", "INTERCONNECTORID"]].copy()
        eq["intervention_values_identical"] = identical.values
        grouped = grouped.merge(eq, on=["interval_timestamp_utc", "INTERCONNECTORID"], how="left", suffixes=("", "_eq"))
        grouped["intervention_values_identical"] = grouped["intervention_values_identical_eq"].combine_first(grouped["intervention_values_identical"])
        grouped = grouped.drop(columns=["intervention_values_identical_eq"])

    grouped["intervention_selected"] = 0
    return grouped


def build_transfer_table(base: pd.DataFrame, interconnector_raw: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    canonical = interconnector_raw[interconnector_raw["INTERVENTION"] == 0].copy()
    canonical = canonical.drop_duplicates(subset=["interval_timestamp_utc", "INTERCONNECTORID"], keep="first")
    canonical = canonical.rename(
        columns={
            "INTERCONNECTORID": "interconnector_id",
            "RUNNO": "runno",
            "INTERVENTION": "intervention",
            "METERED_MWFLOW": "metered_mwflow",
            "FLOW_MW": "mwflow",
            "LOSSES_MW": "mwlosses",
            "MARGINALVALUE": "marginalvalue",
            "VIOLATIONDEGREE": "violationdegree",
            "EXPORTLIMIT_MW": "export_limit_mw",
            "IMPORTLIMIT_MW": "import_limit_mw",
            "MARGINALLOSS_FACTOR": "marginalloss",
            "EXPORTGENCONID": "exportgenconid",
            "IMPORTGENCONID": "importgenconid",
            "LASTCHANGED": "interconnector_lastchanged",
            "SOURCE_FILE": "source_file",
        }
    )
    keep_cols = [
        "interval_timestamp_utc",
        "interconnector_id",
        "runno",
        "intervention",
        "metered_mwflow",
        "mwflow",
        "mwlosses",
        "marginalvalue",
        "violationdegree",
        "export_limit_mw",
        "import_limit_mw",
        "marginalloss",
        "exportgenconid",
        "importgenconid",
        "interconnector_lastchanged",
        "source_file",
    ]
    canonical = canonical[keep_cols]

    audit = audit.rename(columns={"INTERCONNECTORID": "interconnector_id"})
    canonical = canonical.merge(
        audit[["interval_timestamp_utc", "interconnector_id", "intervention_pair_present", "intervention_values_identical", "intervention_selected"]],
        on=["interval_timestamp_utc", "interconnector_id"],
        how="left",
    )

    final = base.merge(
        canonical,
        on=["interval_timestamp_utc", "interconnector_id"],
        how="left",
        suffixes=("_base", ""),
    )

    final["nsw_demand_mw"] = pd.to_numeric(final["total_demand_mw_nsw"], errors="coerce")
    final["qld_demand_mw"] = pd.to_numeric(final["total_demand_mw_qld"], errors="coerce")
    final["nsw_generation_mw"] = pd.to_numeric(final["total_generation_mw_nsw"], errors="coerce")
    final["qld_generation_mw"] = pd.to_numeric(final["total_generation_mw_qld"], errors="coerce")
    final["nsw_net_balance_mw"] = pd.to_numeric(final["net_balance_nsw_mw"], errors="coerce")
    final["qld_net_balance_mw"] = pd.to_numeric(final["net_balance_qld_mw"], errors="coerce")

    final["regional_balance_difference_mw"] = final["nsw_net_balance_mw"] - final["qld_net_balance_mw"]
    export_mask = pd.to_numeric(final["mwflow"], errors="coerce") >= 0
    import_mask = pd.to_numeric(final["mwflow"], errors="coerce") < 0
    final["directional_limit_mw"] = pd.NA
    final.loc[export_mask, "directional_limit_mw"] = final.loc[export_mask, "export_limit_mw"].abs()
    final.loc[import_mask, "directional_limit_mw"] = final.loc[import_mask, "import_limit_mw"].abs()
    final["utilisation_pct"] = (pd.to_numeric(final["mwflow"], errors="coerce").abs() / pd.to_numeric(final["directional_limit_mw"], errors="coerce")) * 100.0
    final["transfer_capability_margin_mw"] = pd.to_numeric(final["directional_limit_mw"], errors="coerce") - pd.to_numeric(final["mwflow"], errors="coerce").abs()

    final["flow_direction"] = "flat"
    final.loc[pd.to_numeric(final["mwflow"], errors="coerce") > 0, "flow_direction"] = "forward"
    final.loc[pd.to_numeric(final["mwflow"], errors="coerce") < 0, "flow_direction"] = "reverse"
    sign = pd.to_numeric(final["mwflow"], errors="coerce").fillna(0).apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    final["flow_reversal_flag"] = sign.ne(sign.shift(1))
    final["flow_ramp_mw"] = pd.to_numeric(final["mwflow"], errors="coerce").diff()
    final["near_export_limit_flag"] = export_mask & (final["utilisation_pct"] >= 95)
    final["near_import_limit_flag"] = import_mask & (final["utilisation_pct"] >= 95)

    final["detailed_constraint_table_available"] = False
    final["export_gencon_id_available"] = final["exportgenconid"].fillna("").astype(str).str.len() > 0
    final["import_gencon_id_available"] = final["importgenconid"].fillna("").astype(str).str.len() > 0
    final["marginal_value_available"] = final["marginalvalue"].notna()
    final["violation_degree_available"] = final["violationdegree"].notna()
    final["detailed_constraint_source_status"] = "detailed_constraint_table_unresolved_public_source"

    final["market_state_schema_version"] = MARKET_STATE_SCHEMA_VERSION
    final["transfer_feature_set_version"] = TRANSFER_FEATURE_SET_VERSION
    final["builder_version"] = BUILDER_VERSION
    final["git_commit"] = get_git_commit()
    final["creation_timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    final["digital_twin_version"] = DIGITAL_TWIN_VERSION
    final["research_framework_version"] = RESEARCH_FRAMEWORK_VERSION

    return final


def validate_table(final: pd.DataFrame, start_utc: str, end_utc: str, audit: pd.DataFrame, interconnector_raw: pd.DataFrame) -> dict[str, object]:
    expected = pd.date_range(start=start_utc, end=end_utc, freq="5min")
    actual = pd.to_datetime(final["interval_timestamp_utc"], utc=True, errors="coerce").dropna().drop_duplicates()
    expected_set = set(expected)
    actual_set = set(actual)

    missing_demand = int(final[["nsw_demand_mw", "qld_demand_mw"]].isna().any(axis=1).sum())
    missing_generation = int(final[["nsw_generation_mw", "qld_generation_mw"]].isna().any(axis=1).sum())
    missing_flow = int(final["mwflow"].isna().sum())
    missing_limits = int(final[["export_limit_mw", "import_limit_mw"]].isna().any(axis=1).sum())
    missing_losses = int(final["mwlosses"].isna().sum())
    missing_marginal = int(final["marginalvalue"].isna().sum())
    missing_pub = int(final["publication_timestamp_interconnector"].isna().sum())

    lineage_cols = ["lineage_regionsum_nsw", "lineage_regionsum_qld", "lineage_interconnector", "source_file", "publication_timestamp_interconnector"]
    missing_lineage = int(final[lineage_cols].isna().any(axis=1).sum())
    lineage_completeness = (1.0 - (missing_lineage / len(final))) * 100.0 if len(final) else 0.0

    summary = {
        "rows_produced": int(len(final)),
        "expected_intervals": int(len(expected_set)),
        "actual_intervals": int(len(actual_set)),
        "interval_coverage_pct": float((len(actual_set) / len(expected_set)) * 100.0 if expected_set else 0.0),
        "duplicate_canonical_keys": int(final.duplicated(subset=["interval_timestamp_utc", "interconnector_id"]).sum()),
        "missing_demand": missing_demand,
        "missing_generation": missing_generation,
        "missing_flow": missing_flow,
        "missing_limits": missing_limits,
        "missing_losses": missing_losses,
        "missing_marginal_value": missing_marginal,
        "missing_publication_timestamps": missing_pub,
        "lineage_completeness_pct": float(lineage_completeness),
        "intervention_rows_excluded": int((interconnector_raw["INTERVENTION"] != 0).sum()),
        "intervention_pairs": int(audit["intervention_pair_present"].sum()),
        "intervention_pairs_identical": int(((audit["intervention_pair_present"]) & (audit["intervention_values_identical"] == True)).sum()),
        "intervention_pairs_differing": int(((audit["intervention_pair_present"]) & (audit["intervention_values_identical"] == False)).sum()),
        "timestamp_range_start": start_utc,
        "timestamp_range_end": end_utc,
        "five_minute_continuity_gaps": int(len(expected_set - actual_set)),
        "available_network_state_fields": [
            "runno",
            "intervention",
            "metered_mwflow",
            "mwflow",
            "mwlosses",
            "marginalvalue",
            "violationdegree",
            "export_limit_mw",
            "import_limit_mw",
            "marginalloss",
            "exportgenconid",
            "importgenconid",
            "interconnector_lastchanged",
            "source_file",
        ],
        "detailed_constraint_data_gap": "Detailed constraint table unresolved; GENCON IDs and interconnector marginal/violation fields are available but not treated as binding evidence.",
    }

    materially_incomplete = (
        (missing_demand / len(final) > 0.001)
        or (missing_generation / len(final) > 0.001)
        or (missing_flow / len(final) > 0.001)
    ) if len(final) else True

    failures: list[str] = []
    if summary["interval_coverage_pct"] < 99.9:
        failures.append("interval coverage below 99.9%")
    if summary["duplicate_canonical_keys"] > 0:
        failures.append("duplicate canonical keys exist")
    if materially_incomplete:
        failures.append("demand/generation/flow materially incomplete")
    if missing_lineage > 0:
        failures.append("source lineage missing")
    summary["validation_failures"] = failures
    return summary


def write_outputs(period_token: str, final: pd.DataFrame, quality: dict[str, object], audit: pd.DataFrame) -> tuple[Path, Path, Path, Path]:
    table_path = REPORTS_DIR / f"{period_token}_TRANSFER_STATE_TABLE.csv"
    quality_path = REPORTS_DIR / f"{period_token}_TRANSFER_STATE_QUALITY.md"
    metadata_path = REPORTS_DIR / f"{period_token}_TRANSFER_STATE_METADATA.json"
    audit_path = REPORTS_DIR / f"{period_token}_TRANSFER_STATE_INTERVENTION_AUDIT.csv"

    final.to_csv(table_path, index=False)
    audit.to_csv(audit_path, index=False)

    quality_md = "\n".join(
        [
            f"# {period_token} Transfer State Quality",
            "",
            f"- Rows produced: {quality['rows_produced']}",
            f"- Expected intervals: {quality['expected_intervals']}",
            f"- Actual intervals: {quality['actual_intervals']}",
            f"- Interval coverage pct: {quality['interval_coverage_pct']:.6f}",
            f"- Duplicate canonical keys: {quality['duplicate_canonical_keys']}",
            f"- Missing demand: {quality['missing_demand']}",
            f"- Missing generation: {quality['missing_generation']}",
            f"- Missing flow: {quality['missing_flow']}",
            f"- Missing limits: {quality['missing_limits']}",
            f"- Missing losses: {quality['missing_losses']}",
            f"- Missing marginal value: {quality['missing_marginal_value']}",
            f"- Missing publication timestamps: {quality['missing_publication_timestamps']}",
            f"- Lineage completeness pct: {quality['lineage_completeness_pct']:.6f}",
            f"- Intervention rows excluded: {quality['intervention_rows_excluded']}",
            f"- Intervention pairs: {quality['intervention_pairs']}",
            f"- Intervention pairs identical: {quality['intervention_pairs_identical']}",
            f"- Intervention pairs differing: {quality['intervention_pairs_differing']}",
            f"- Five-minute continuity gaps: {quality['five_minute_continuity_gaps']}",
            f"- Validation failures: {', '.join(quality['validation_failures']) if quality['validation_failures'] else 'none'}",
        ]
    )
    quality_path.write_text(quality_md, encoding="utf-8")

    metadata = {
        "period": period_token,
        "market_state_schema_version": MARKET_STATE_SCHEMA_VERSION,
        "transfer_feature_set_version": TRANSFER_FEATURE_SET_VERSION,
        "builder_version": BUILDER_VERSION,
        "git_commit": get_git_commit(),
        "creation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "digital_twin_version": DIGITAL_TWIN_VERSION,
        "research_framework_version": RESEARCH_FRAMEWORK_VERSION,
        "quality": quality,
        "columns": list(final.columns),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return table_path, quality_path, metadata_path, audit_path


def main() -> int:
    args = parse_args()
    start_month, end_month, period_token = resolve_period(args)
    start_utc, end_utc = utc_bounds_from_months(start_month, end_month)
    months = month_range(start_month, end_month)

    base = load_base_period(start_utc, end_utc)
    interconnector_raw = load_interconnector_period(months)
    base_min = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce").min()
    base_max = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce").max()
    raw_min = pd.to_datetime(interconnector_raw["interval_timestamp_utc"], utc=True, errors="coerce").min()
    raw_max = pd.to_datetime(interconnector_raw["interval_timestamp_utc"], utc=True, errors="coerce").max()
    effective_start_ts = max(base_min, raw_min)
    effective_end_ts = min(base_max, raw_max)
    if pd.isna(effective_start_ts) or pd.isna(effective_end_ts) or effective_end_ts < effective_start_ts:
        raise SystemExit("Validation failed: no overlapping timestamp window between base and interconnector sources")

    effective_start = effective_start_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    effective_end = effective_end_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    base = base[(base["interval_timestamp_utc"] >= effective_start) & (base["interval_timestamp_utc"] <= effective_end)].copy()
    interconnector_raw = interconnector_raw[
        (interconnector_raw["interval_timestamp_utc"] >= effective_start)
        & (interconnector_raw["interval_timestamp_utc"] <= effective_end)
    ].copy()

    audit = build_intervention_audit(interconnector_raw)
    final = build_transfer_table(base, interconnector_raw, audit)
    quality = validate_table(final, effective_start, effective_end, audit, interconnector_raw)

    if quality["validation_failures"]:
        raise SystemExit("Validation failed: " + "; ".join(quality["validation_failures"]))

    table_path, quality_path, metadata_path, audit_path = write_outputs(period_token, final, quality, audit)
    print(f"wrote {len(final)} rows to {table_path}")
    print(f"quality report: {quality_path}")
    print(f"metadata: {metadata_path}")
    print(f"intervention audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
