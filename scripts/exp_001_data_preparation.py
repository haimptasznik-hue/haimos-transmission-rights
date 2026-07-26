#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
RAW_DEMAND_DIR = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"
RAW_FLOW_DIR = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"

MONTHS = ["202410", "202411", "202412"]
PRIMARY_INTERCONNECTOR_ID = "NSW1-QLD1"
FROM_REGION = "NSW1"
TO_REGION = "QLD1"
RULESET_ID = "EXP_001_RULESET_V1"


@dataclass(frozen=True)
class QualityGate:
    min_coverage_pct: float = 99.9
    max_duplicates: int = 0
    max_timestamp_mismatches: int = 0


def _find_month_zip(directory: Path, dataset_stub: str, month: str) -> Path:
    candidates = [
        directory / f"PUBLIC_DVD_{dataset_stub}_{month}010000.zip",
        directory / f"PUBLIC_ARCHIVE#{dataset_stub}#FILE01#{month}010000.zip",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No archive found for {dataset_stub} {month} in {directory}")


def _read_regionsum_month(month: str) -> pd.DataFrame:
    archive_path = _find_month_zip(RAW_DEMAND_DIR, "DISPATCHREGIONSUM", month)
    with zipfile.ZipFile(archive_path) as zf:
        member = [name for name in zf.namelist() if name.upper().endswith(".CSV")][0]
        with zf.open(member) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
            header = None
            idx: dict[str, int] | None = None
            rows: list[dict[str, object]] = []
            for row in reader:
                if not row:
                    continue
                if row[0] == "I" and row[1] == "DISPATCH" and row[2] == "REGIONSUM":
                    header = row[4:]
                    idx = {column: i for i, column in enumerate(header)}
                    continue
                if row[0] != "D" or row[1] != "DISPATCH" or row[2] != "REGIONSUM" or idx is None:
                    continue
                data = row[4:]
                if data[idx["INTERVENTION"]] != "0":
                    continue
                settlementdate = data[idx["SETTLEMENTDATE"]]
                if not settlementdate.startswith(f"2024/{month[4:]}"):
                    continue
                region = data[idx["REGIONID"]]
                if region not in (FROM_REGION, TO_REGION):
                    continue
                rows.append(
                    {
                        "settlementdate": settlementdate,
                        "region_id": region,
                        "total_demand_mw": pd.to_numeric(data[idx["TOTALDEMAND"]], errors="coerce"),
                        "dispatchable_generation_mw": pd.to_numeric(
                            data[idx["DISPATCHABLEGENERATION"]], errors="coerce"
                        ),
                        "total_intermittent_generation_mw": pd.to_numeric(
                            data[idx["TOTALINTERMITTENTGENERATION"]], errors="coerce"
                        ),
                        "available_generation_mw": pd.to_numeric(
                            data[idx["AVAILABLEGENERATION"]], errors="coerce"
                        ),
                        "demand_and_nonschedgen_mw": pd.to_numeric(
                            data[idx["DEMAND_AND_NONSCHEDGEN"]], errors="coerce"
                        ),
                        "regionsum_lastchanged": data[idx["LASTCHANGED"]],
                        "regionsum_source_file": str(archive_path),
                    }
                )
    return pd.DataFrame(rows)


def _read_interconnector_month(month: str) -> pd.DataFrame:
    archive_path = _find_month_zip(RAW_FLOW_DIR, "DISPATCHINTERCONNECTORRES", month)
    with zipfile.ZipFile(archive_path) as zf:
        member = [name for name in zf.namelist() if name.upper().endswith(".CSV")][0]
        with zf.open(member) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
            idx: dict[str, int] | None = None
            rows: list[dict[str, object]] = []
            for row in reader:
                if not row:
                    continue
                if row[0] == "I" and row[1] == "DISPATCH" and row[2] == "INTERCONNECTORRES":
                    idx = {column: i for i, column in enumerate(row[4:])}
                    continue
                if row[0] != "D" or row[1] != "DISPATCH" or row[2] != "INTERCONNECTORRES" or idx is None:
                    continue
                data = row[4:]
                if data[idx["INTERVENTION"]] != "0":
                    continue
                settlementdate = data[idx["SETTLEMENTDATE"]]
                if not settlementdate.startswith(f"2024/{month[4:]}"):
                    continue
                if data[idx["INTERCONNECTORID"]] != PRIMARY_INTERCONNECTOR_ID:
                    continue
                rows.append(
                    {
                        "settlementdate": settlementdate,
                        "interconnector_id": data[idx["INTERCONNECTORID"]],
                        "mwflow": pd.to_numeric(data[idx["MWFLOW"]], errors="coerce"),
                        "metered_mwflow": pd.to_numeric(data[idx["METEREDMWFLOW"]], errors="coerce"),
                        "export_limit_mw": pd.to_numeric(data[idx["EXPORTLIMIT"]], errors="coerce"),
                        "import_limit_mw": pd.to_numeric(data[idx["IMPORTLIMIT"]], errors="coerce"),
                        "interconnector_lastchanged": data[idx["LASTCHANGED"]],
                        "interconnector_source_file": str(archive_path),
                    }
                )
    return pd.DataFrame(rows)


def _prepare_dataset() -> pd.DataFrame:
    demand_frames = [_read_regionsum_month(month) for month in MONTHS]
    flow_frames = [_read_interconnector_month(month) for month in MONTHS]

    demand = pd.concat(demand_frames, ignore_index=True)
    flows = pd.concat(flow_frames, ignore_index=True)

    demand["settlement_ts"] = pd.to_datetime(demand["settlementdate"], format="%Y/%m/%d %H:%M:%S", errors="coerce")
    flows["settlement_ts"] = pd.to_datetime(flows["settlementdate"], format="%Y/%m/%d %H:%M:%S", errors="coerce")

    for region in (FROM_REGION, TO_REGION):
        region_mask = demand["region_id"] == region
        demand.loc[region_mask, "total_generation_mw"] = (
            demand.loc[region_mask, "dispatchable_generation_mw"]
            + demand.loc[region_mask, "total_intermittent_generation_mw"]
        )

    demand_nsw = demand[demand["region_id"] == FROM_REGION].copy()
    demand_qld = demand[demand["region_id"] == TO_REGION].copy()

    merged = demand_nsw.merge(
        demand_qld,
        on="settlement_ts",
        how="inner",
        suffixes=("_nsw", "_qld"),
    ).merge(flows, on="settlement_ts", how="inner")

    merged = merged.sort_values("settlement_ts").reset_index(drop=True)
    merged["ruleset_id"] = RULESET_ID

    merged["net_balance_nsw_mw"] = merged["total_generation_mw_nsw"] - merged["total_demand_mw_nsw"]
    merged["net_balance_qld_mw"] = merged["total_generation_mw_qld"] - merged["total_demand_mw_qld"]
    merged["balance_difference_mw"] = merged["net_balance_qld_mw"] - merged["net_balance_nsw_mw"]

    merged["expected_flow_direction_from_balance"] = np.where(
        merged["balance_difference_mw"] > 0,
        "QLD1->NSW1",
        np.where(merged["balance_difference_mw"] < 0, "NSW1->QLD1", "NO_FLOW"),
    )

    merged["actual_qni_flow_direction"] = np.where(
        merged["mwflow"] > 0,
        "NSW1->QLD1",
        np.where(merged["mwflow"] < 0, "QLD1->NSW1", "NO_FLOW"),
    )

    merged["flow_magnitude_mw"] = merged["mwflow"].abs()
    merged["directional_limit_mw"] = np.where(
        merged["mwflow"] >= 0,
        merged["export_limit_mw"].abs(),
        merged["import_limit_mw"].abs(),
    )
    merged["utilisation_pct"] = np.where(
        merged["directional_limit_mw"] > 0,
        (merged["flow_magnitude_mw"] / merged["directional_limit_mw"]) * 100.0,
        np.nan,
    )

    merged["lineage_regionsum_nsw"] = merged["regionsum_source_file_nsw"]
    merged["lineage_regionsum_qld"] = merged["regionsum_source_file_qld"]
    merged["lineage_interconnector"] = merged["interconnector_source_file"]

    merged["publication_timestamp_regionsum_nsw"] = merged["regionsum_lastchanged_nsw"]
    merged["publication_timestamp_regionsum_qld"] = merged["regionsum_lastchanged_qld"]
    merged["publication_timestamp_interconnector"] = merged["interconnector_lastchanged"]

    merged["dq_missing_demand_flag"] = merged[["total_demand_mw_nsw", "total_demand_mw_qld"]].isna().any(axis=1)
    merged["dq_missing_generation_flag"] = merged[
        ["total_generation_mw_nsw", "total_generation_mw_qld"]
    ].isna().any(axis=1)
    merged["dq_missing_flow_flag"] = merged["mwflow"].isna()
    merged["dq_missing_utilisation_flag"] = merged["utilisation_pct"].isna()

    merged["settlement_timestamp_utc"] = merged["settlement_ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return merged


def _build_data_quality_report(dataset: pd.DataFrame, gate: QualityGate) -> tuple[dict[str, object], bool]:
    expected_intervals = 26496
    joined_intervals = int(len(dataset))

    duplicates = int(dataset.duplicated(subset=["settlement_timestamp_utc"]).sum())
    timestamp_mismatches = int(dataset["settlement_ts"].isna().sum())

    missing_demand = int(dataset["dq_missing_demand_flag"].sum())
    missing_generation = int(dataset["dq_missing_generation_flag"].sum())
    missing_flow = int(dataset["dq_missing_flow_flag"].sum())

    coverage_pct = (joined_intervals / expected_intervals) * 100 if expected_intervals else 0.0

    net_balance_summary = {
        "net_balance_nsw_mean": float(dataset["net_balance_nsw_mw"].mean()),
        "net_balance_nsw_std": float(dataset["net_balance_nsw_mw"].std(ddof=0)),
        "net_balance_qld_mean": float(dataset["net_balance_qld_mw"].mean()),
        "net_balance_qld_std": float(dataset["net_balance_qld_mw"].std(ddof=0)),
        "balance_difference_mean": float(dataset["balance_difference_mw"].mean()),
        "balance_difference_std": float(dataset["balance_difference_mw"].std(ddof=0)),
    }

    flow_direction_summary = (
        dataset["actual_qni_flow_direction"].value_counts(dropna=False).rename_axis("direction").reset_index(name="count")
    )

    gate_pass = (
        coverage_pct >= gate.min_coverage_pct
        and duplicates <= gate.max_duplicates
        and timestamp_mismatches <= gate.max_timestamp_mismatches
        and missing_demand == 0
        and missing_generation == 0
        and missing_flow == 0
    )

    payload = {
        "expected_intervals": expected_intervals,
        "joined_intervals": joined_intervals,
        "missing_demand": missing_demand,
        "missing_generation": missing_generation,
        "missing_flow": missing_flow,
        "duplicates": duplicates,
        "timestamp_mismatches": timestamp_mismatches,
        "coverage_pct": coverage_pct,
        "data_quality_gate": "PASS" if gate_pass else "FAIL",
        "net_balance_summary": net_balance_summary,
        "flow_direction_summary": flow_direction_summary.to_dict(orient="records"),
    }
    return payload, gate_pass


def _write_quality_markdown(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# EXP_001 Data Quality",
        "",
        f"- Data quality gate: **{summary['data_quality_gate']}**",
        f"- Expected intervals: `{summary['expected_intervals']}`",
        f"- Joined intervals: `{summary['joined_intervals']}`",
        f"- Missing demand: `{summary['missing_demand']}`",
        f"- Missing generation: `{summary['missing_generation']}`",
        f"- Missing flow: `{summary['missing_flow']}`",
        f"- Duplicates: `{summary['duplicates']}`",
        f"- Timestamp mismatches: `{summary['timestamp_mismatches']}`",
        f"- Coverage: `{summary['coverage_pct']:.6f}%`",
        "",
        "## Net-Balance Summary",
    ]
    for key, value in summary["net_balance_summary"].items():
        lines.append(f"- {key}: `{value:.6f}`")

    lines.append("")
    lines.append("## Flow Direction Summary")
    for item in summary["flow_direction_summary"]:
        lines.append(f"- {item['direction']}: `{item['count']}`")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare EXP_001 C2024Q4 dataset")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORTS_DIR / "EXP_001_PREPARED_DATA.csv",
        help="Output CSV path for prepared dataset",
    )
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=REPORTS_DIR / "EXP_001_DATA_QUALITY.md",
        help="Output markdown data quality report path",
    )
    args = parser.parse_args()

    dataset = _prepare_dataset()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.quality_report.parent.mkdir(parents=True, exist_ok=True)

    dataset.to_csv(args.output, index=False)
    summary, gate_pass = _build_data_quality_report(dataset, gate=QualityGate())
    _write_quality_markdown(args.quality_report, summary)

    print(f"Prepared dataset rows: {len(dataset)}")
    print(f"Coverage: {summary['coverage_pct']:.6f}%")
    print(f"Data-quality gate: {summary['data_quality_gate']}")

    if not gate_pass:
        print("Pre-registered data-quality gate failed. Stopping before EXP_001 run.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
