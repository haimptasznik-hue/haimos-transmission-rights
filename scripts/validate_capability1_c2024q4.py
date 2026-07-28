#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
import sys

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.dataset_library import (  # noqa: E402
    _derive_interconnector_row_fields,
    normalize_aemo_timestamp_series,
)


QUARTER_START_LOCAL = pd.Timestamp("2024-10-01 00:00:00")
QUARTER_END_LOCAL_EXCL = pd.Timestamp("2025-01-01 00:00:00")


def _read_q4_source() -> pd.DataFrame:
    cache_root = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres" / ".cache"
    month_paths = [
        cache_root / "year=2024" / "month=10",
        cache_root / "year=2024" / "month=11",
        cache_root / "year=2024" / "month=12",
    ]

    frames: list[pd.DataFrame] = []
    for month_path in month_paths:
        if not month_path.exists():
            continue
        for file_path in sorted(month_path.glob("*.dispatchinterconnectorres.csv.gz")):
            frame = pd.read_csv(file_path, low_memory=False)
            frame["__file_path"] = str(file_path)
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True)

    # Local quarter filter on raw timestamp (as published in source timezone)
    local_ts = pd.to_datetime(data.get("SETTLEMENTDATE"), errors="coerce")
    mask = (local_ts >= QUARTER_START_LOCAL) & (local_ts < QUARTER_END_LOCAL_EXCL)
    data = data.loc[mask].copy()

    return data.reset_index(drop=True)


def _normalize_required_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()

    # Required raw-preserved fields (canonical aliases)
    out["interconnector_id"] = out.get("INTERCONNECTORID")

    if "MWFLOW" in out.columns:
        out["MWFLOW"] = pd.to_numeric(out["MWFLOW"], errors="coerce")
    else:
        out["MWFLOW"] = pd.to_numeric(out.get("FLOW_MW"), errors="coerce")

    if "METERED_MWFLOW" in out.columns:
        out["METERED_MWFLOW"] = pd.to_numeric(out["METERED_MWFLOW"], errors="coerce")
    else:
        out["METERED_MWFLOW"] = pd.to_numeric(out.get("METEREDMWFLOW"), errors="coerce")

    if "EXPORTLIMIT_MW" in out.columns:
        out["EXPORTLIMIT_MW"] = pd.to_numeric(out["EXPORTLIMIT_MW"], errors="coerce")
    else:
        out["EXPORTLIMIT_MW"] = pd.to_numeric(out.get("EXPORTLIMIT"), errors="coerce")

    if "IMPORTLIMIT_MW" in out.columns:
        out["IMPORTLIMIT_MW"] = pd.to_numeric(out["IMPORTLIMIT_MW"], errors="coerce")
    else:
        out["IMPORTLIMIT_MW"] = pd.to_numeric(out.get("IMPORTLIMIT"), errors="coerce")

    out["INTERVENTION"] = pd.to_numeric(out.get("INTERVENTION"), errors="coerce").fillna(0).astype(int)
    out["RUNNO"] = pd.to_numeric(out.get("RUNNO"), errors="coerce")

    out["source_file"] = out.get("SOURCE_FILE").fillna(out.get("__file_path")) if "SOURCE_FILE" in out.columns else out.get("__file_path")
    out["LASTCHANGED"] = out.get("LASTCHANGED")

    last_changed_ts = pd.to_datetime(out["LASTCHANGED"], errors="coerce", utc=True)
    out["publication_timestamp"] = np.where(
        last_changed_ts.notna(),
        last_changed_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        pd.NA,
    )

    out["interval_timestamp_utc"] = normalize_aemo_timestamp_series(
        out.get("SETTLEMENTDATE"),
        source_timezone="Australia/Brisbane",
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return out


def _build_intervention_audit(full_frame: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["interval_timestamp_utc", "interconnector_id", "RUNNO"]
    compare_cols = ["MWFLOW", "METERED_MWFLOW", "EXPORTLIMIT_MW", "IMPORTLIMIT_MW"]

    records: list[dict[str, object]] = []
    grouped = full_frame.groupby(key_cols, dropna=False)
    for key, grp in grouped:
        g0 = grp[grp["INTERVENTION"] == 0]
        g1 = grp[grp["INTERVENTION"] == 1]

        values_differ = False
        if not g0.empty and not g1.empty:
            row0 = g0.iloc[0]
            row1 = g1.iloc[0]
            for col in compare_cols:
                v0 = row0.get(col)
                v1 = row1.get(col)
                if (pd.isna(v0) and pd.isna(v1)):
                    continue
                if pd.isna(v0) != pd.isna(v1):
                    values_differ = True
                    break
                if float(v0) != float(v1):
                    values_differ = True
                    break

        records.append(
            {
                "interval_timestamp_utc": key[0],
                "interconnector_id": key[1],
                "RUNNO": key[2],
                "count_intervention_0": int(len(g0)),
                "count_intervention_1": int(len(g1)),
                "excluded_intervention_1_rows": int(len(g1)),
                "paired_intervention_values_differ": values_differ,
            }
        )

    return pd.DataFrame(records)


def _expected_interval_index_utc() -> pd.DatetimeIndex:
    start_local = pd.Timestamp("2024-10-01 00:05:00", tz="Australia/Brisbane")
    end_local = pd.Timestamp("2025-01-01 00:00:00", tz="Australia/Brisbane")
    local_index = pd.date_range(start=start_local, end=end_local, freq="5min")
    return local_index.tz_convert("UTC")


def _direction_label(flow: pd.Series) -> pd.Series:
    return np.where(flow > 0, "positive", np.where(flow < 0, "negative", "zero"))


def _compute_verdict(metrics: dict[str, object]) -> tuple[str, str | None]:
    gates: list[tuple[bool, str]] = [
        (float(metrics["interval_coverage_pct"]) > 99.9, "coverage <= 99.9%"),
        (int(metrics["duplicate_canonical_keys"]) == 0, "duplicate canonical keys > 0"),
        (int(metrics["missing_mwflow"]) == 0, "missing MWFLOW > 0"),
        (int(metrics["infinite_utilisation_count"]) == 0, "infinite utilisation present"),
        (int(metrics["negative_utilisation_count"]) == 0, "negative utilisation present"),
        (bool(metrics["raw_limits_preserved_exactly"]) is True, "raw limits not preserved exactly"),
        (bool(metrics["over_limit_retained_and_flagged"]) is True, "over-limit rows not fully retained+flagged"),
        (float(metrics["lineage_completeness_pct"]) == 100.0, "lineage completeness < 100%"),
    ]
    for ok, reason in gates:
        if not ok:
            return "CAPABILITY1_CONDITIONAL", reason
    return "CAPABILITY1_VALIDATED", None


def run_validation() -> dict[str, object]:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    source = _read_q4_source()
    if source.empty:
        raise RuntimeError("No C2024Q4 source rows found in DISPATCHINTERCONNECTORRES cache")

    normalized = _normalize_required_columns(source)

    # Apply existing validated capability logic (no logic changes)
    derivation_input = normalized.copy()
    derivation_input["EXPORTLIMIT"] = derivation_input["EXPORTLIMIT_MW"]
    derivation_input["IMPORTLIMIT"] = derivation_input["IMPORTLIMIT_MW"]
    derived = _derive_interconnector_row_fields(derivation_input)

    normalized["directional_limit_mw"] = pd.to_numeric(derived.get("directional_limit_mw"), errors="coerce")
    normalized["utilisation_pct"] = pd.to_numeric(derived.get("utilisation_pct"), errors="coerce")
    normalized["over_limit_flag"] = derived.get("over_limit_flag").fillna(False).astype(bool)
    normalized["capability_data_quality_flag"] = derived.get("limit_quality_flag")

    intervention_audit = _build_intervention_audit(normalized)

    # Canonical primary frame: INTERVENTION=0 only
    primary = normalized[normalized["INTERVENTION"] == 0].copy()

    # Required output columns
    required_fields = [
        "interval_timestamp_utc",
        "interconnector_id",
        "MWFLOW",
        "METERED_MWFLOW",
        "EXPORTLIMIT_MW",
        "IMPORTLIMIT_MW",
        "directional_limit_mw",
        "utilisation_pct",
        "over_limit_flag",
        "capability_data_quality_flag",
        "INTERVENTION",
        "RUNNO",
        "source_file",
        "publication_timestamp",
        "LASTCHANGED",
    ]

    for col in required_fields:
        if col not in primary.columns:
            primary[col] = pd.NA

    primary = primary[required_fields].copy()

    # Coverage and quality metrics
    expected_idx = _expected_interval_index_utc()
    expected_iso = pd.Series(expected_idx.strftime("%Y-%m-%dT%H:%M:%SZ"))

    actual_intervals = pd.Series(primary["interval_timestamp_utc"].dropna().unique())
    expected_count = int(len(expected_iso))
    actual_count = int(actual_intervals.nunique())
    coverage_pct = round((actual_count / expected_count * 100.0), 6) if expected_count else 0.0

    canonical_key_cols = ["interval_timestamp_utc", "interconnector_id", "RUNNO"]
    duplicate_keys = int(primary.duplicated(subset=canonical_key_cols, keep=False).sum())

    missing_mwflow = int(primary["MWFLOW"].isna().sum())
    missing_export = int(primary["EXPORTLIMIT_MW"].isna().sum())
    missing_import = int(primary["IMPORTLIMIT_MW"].isna().sum())
    missing_directional = int(primary["directional_limit_mw"].isna().sum())
    missing_util = int(primary["utilisation_pct"].isna().sum())

    zero_limit = int((pd.to_numeric(primary["directional_limit_mw"], errors="coerce") == 0).sum())
    null_limit = int(primary["directional_limit_mw"].isna().sum())

    over_limit = int(primary["over_limit_flag"].fillna(False).sum())
    max_util = float(pd.to_numeric(primary["utilisation_pct"], errors="coerce").max()) if not primary.empty else float("nan")

    util_series = pd.to_numeric(primary["utilisation_pct"], errors="coerce")
    infinite_util = int(np.isinf(util_series).sum())
    negative_util = int((util_series < 0).sum())

    # Continuity: missing expected intervals
    missing_intervals = int(expected_count - actual_count)
    continuity_ok = missing_intervals == 0

    # Lineage completeness (all required lineage cols present and non-null)
    lineage_cols = ["source_file", "publication_timestamp", "LASTCHANGED"]
    lineage_non_null = primary[lineage_cols].notna().all(axis=1)
    lineage_completeness_pct = round((lineage_non_null.sum() / len(primary) * 100.0), 6) if len(primary) else 0.0

    # Raw limit preservation check
    raw_limits_preserved = bool((primary["EXPORTLIMIT_MW"].equals(primary["EXPORTLIMIT_MW"])) and (primary["IMPORTLIMIT_MW"].equals(primary["IMPORTLIMIT_MW"])))

    # Directional sanity checks
    flow = pd.to_numeric(primary["MWFLOW"], errors="coerce")
    export = pd.to_numeric(primary["EXPORTLIMIT_MW"], errors="coerce")
    imp = pd.to_numeric(primary["IMPORTLIMIT_MW"], errors="coerce")
    directional = pd.to_numeric(primary["directional_limit_mw"], errors="coerce")

    positive_mask = flow > 0
    negative_mask = flow < 0
    zero_mask = flow == 0

    positive_correct = int((directional[positive_mask] == export[positive_mask]).sum())
    negative_correct = int((directional[negative_mask] == imp[negative_mask].abs()).sum())
    zero_expected = pd.concat([export[zero_mask], imp[zero_mask].abs()], axis=1).max(axis=1)
    zero_correct = int((directional[zero_mask] == zero_expected).sum())

    direction = pd.Series(_direction_label(flow), index=primary.index)
    primary["flow_direction"] = direction

    by_direction = (
        primary.groupby("flow_direction", dropna=False)
        .agg(
            intervals=("flow_direction", "size"),
            mean_utilisation_pct=("utilisation_pct", "mean"),
            max_utilisation_pct=("utilisation_pct", "max"),
            over_limit_count=("over_limit_flag", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
    )

    capability_margin = directional - flow.abs()
    margin_desc = capability_margin.describe(percentiles=[0.01, 0.05, 0.5, 0.95, 0.99]).to_dict()

    physically_inconsistent = int(
        ((flow > 0) & (directional != export)).sum()
        + ((flow < 0) & (directional != imp.abs())).sum()
        + ((flow == 0) & (directional != pd.concat([export, imp.abs()], axis=1).max(axis=1))).sum()
        + (util_series < 0).sum()
        + np.isinf(util_series).sum()
    )

    # Intervention handling summary
    excluded_intervention1_rows = int((normalized["INTERVENTION"] == 1).sum())
    paired_differences = int(intervention_audit["paired_intervention_values_differ"].fillna(False).sum()) if not intervention_audit.empty else 0

    over_limit_retained_and_flagged = True
    over_limit_condition = util_series > 100.0
    if int(over_limit_condition.sum()) > 0:
        over_limit_retained_and_flagged = bool((primary.loc[over_limit_condition, "over_limit_flag"] == True).all())  # noqa: E712

    metrics = {
        "rows_produced": int(len(primary)),
        "expected_intervals": expected_count,
        "actual_intervals": actual_count,
        "interval_coverage_pct": coverage_pct,
        "duplicate_canonical_keys": duplicate_keys,
        "missing_mwflow": missing_mwflow,
        "missing_export_limits": missing_export,
        "missing_import_limits": missing_import,
        "missing_directional_capability": missing_directional,
        "missing_utilisation": missing_util,
        "zero_limit_intervals": zero_limit,
        "null_limit_intervals": null_limit,
        "over_limit_intervals": over_limit,
        "maximum_utilisation": max_util,
        "timestamp_continuity_ok": continuity_ok,
        "missing_expected_intervals": missing_intervals,
        "lineage_completeness_pct": lineage_completeness_pct,
        "excluded_intervention1_rows": excluded_intervention1_rows,
        "paired_intervention_values_differ_count": paired_differences,
        "positive_flow_intervals": int(positive_mask.sum()),
        "negative_flow_intervals": int(negative_mask.sum()),
        "zero_flow_intervals": int(zero_mask.sum()),
        "positive_flow_directional_limit_correct": positive_correct,
        "negative_flow_directional_limit_correct": negative_correct,
        "zero_flow_directional_limit_correct": zero_correct,
        "capability_margin_distribution": margin_desc,
        "physically_inconsistent_records": physically_inconsistent,
        "infinite_utilisation_count": infinite_util,
        "negative_utilisation_count": negative_util,
        "raw_limits_preserved_exactly": raw_limits_preserved,
        "over_limit_retained_and_flagged": over_limit_retained_and_flagged,
    }

    verdict, blocker = _compute_verdict(metrics)
    metrics["verdict"] = verdict
    metrics["blocker"] = blocker

    # Outputs
    validation_csv = reports_dir / "C2024Q4_CAPABILITY1_VALIDATION.csv"
    quality_md = reports_dir / "C2024Q4_CAPABILITY1_QUALITY.md"
    intervention_csv = reports_dir / "C2024Q4_CAPABILITY1_INTERVENTION_AUDIT.csv"
    metadata_json = reports_dir / "C2024Q4_CAPABILITY1_METADATA.json"

    primary.to_csv(validation_csv, index=False)
    intervention_audit.to_csv(intervention_csv, index=False)

    direction_text = by_direction.to_string(index=False) if not by_direction.empty else "No direction rows."

    quality_lines = [
        "# C2024Q4 Capability 1 Quality",
        "",
        f"- Rows produced: {metrics['rows_produced']}",
        f"- Expected intervals: {metrics['expected_intervals']}",
        f"- Actual intervals: {metrics['actual_intervals']}",
        f"- Interval coverage (%): {metrics['interval_coverage_pct']}",
        f"- Duplicate canonical keys: {metrics['duplicate_canonical_keys']}",
        f"- Missing MWFLOW: {metrics['missing_mwflow']}",
        f"- Missing export limits: {metrics['missing_export_limits']}",
        f"- Missing import limits: {metrics['missing_import_limits']}",
        f"- Missing directional capability: {metrics['missing_directional_capability']}",
        f"- Missing utilisation: {metrics['missing_utilisation']}",
        f"- Zero-limit intervals: {metrics['zero_limit_intervals']}",
        f"- Null-limit intervals: {metrics['null_limit_intervals']}",
        f"- Over-limit intervals: {metrics['over_limit_intervals']}",
        f"- Maximum utilisation: {metrics['maximum_utilisation']}",
        f"- Timestamp continuity OK: {metrics['timestamp_continuity_ok']}",
        f"- Lineage completeness (%): {metrics['lineage_completeness_pct']}",
        f"- Excluded INTERVENTION=1 rows: {metrics['excluded_intervention1_rows']}",
        f"- Paired intervention differences: {metrics['paired_intervention_values_differ_count']}",
        "",
        "## Directional checks",
        f"- Positive flow intervals: {metrics['positive_flow_intervals']} (correct directional limit rows: {metrics['positive_flow_directional_limit_correct']})",
        f"- Negative flow intervals: {metrics['negative_flow_intervals']} (correct directional limit rows: {metrics['negative_flow_directional_limit_correct']})",
        f"- Zero flow intervals: {metrics['zero_flow_intervals']} (correct directional limit rows: {metrics['zero_flow_directional_limit_correct']})",
        "",
        "## Verdict",
        f"- {metrics['verdict']}",
        f"- Blocker: {metrics['blocker'] if metrics['blocker'] else 'None'}",
        "",
        "## By direction",
        "",
        direction_text,
    ]
    quality_md.write_text("\n".join(quality_lines) + "\n", encoding="utf-8")

    metadata_payload = {
        "quarter": "C2024Q4",
        "inputs": {
            "source_root": str(REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres" / ".cache"),
            "month_paths": [
                "year=2024/month=10",
                "year=2024/month=11",
                "year=2024/month=12",
            ],
            "canonical_intervention": 0,
        },
        "outputs": {
            "validation_csv": str(validation_csv),
            "quality_md": str(quality_md),
            "intervention_audit_csv": str(intervention_csv),
            "metadata_json": str(metadata_json),
        },
        "metrics": metrics,
    }
    metadata_json.write_text(json.dumps(metadata_payload, indent=2) + "\n", encoding="utf-8")

    return {"metrics": metrics, "by_direction": by_direction.to_dict(orient="records")}


if __name__ == "__main__":
    result = run_validation()
    print(json.dumps(result["metrics"], indent=2))
