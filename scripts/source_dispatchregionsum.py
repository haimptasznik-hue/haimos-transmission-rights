#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import time
import zipfile

import pandas as pd

from mmsdm_source_utils import (
    fetch_archive_with_retry,
    month_range,
    partitioned_cache_path,
    progress_line,
    write_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"
CACHE_DIR = RAW_DIR / ".cache"
DATASET_TOKEN = "DISPATCHREGIONSUM"
SCHEMA_VERSION = "1.1"


def _parse_archive(archive_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(archive_path, "r") as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            return pd.DataFrame(
                columns=[
                    "SETTLEMENTDATE",
                    "RUNNO",
                    "REGIONID",
                    "INTERVENTION",
                    "TOTAL_DEMAND_MW",
                    "DISPATCHABLE_GENERATION_MW",
                    "TOTAL_INTERMITTENT_GENERATION_MW",
                    "AVAILABLE_GENERATION_MW",
                    "INITIAL_SUPPLY_MW",
                    "DEMAND_AND_NONSCHEDGEN_MW",
                    "NET_INTERCHANGE_MW",
                    "LASTCHANGED",
                    "SOURCE_FILE",
                ]
            )
        content = archive.read(csv_members[0]).decode("utf-8", errors="ignore")

    reader = csv.reader(io.StringIO(content))
    header_idx: dict[str, int] | None = None
    records: list[dict[str, object]] = []

    for row in reader:
        if not row:
            continue
        record_type = row[0].strip().upper()
        if record_type == "I" and "SETTLEMENTDATE" in [value.strip().upper() for value in row]:
            header_idx = {value.strip().upper(): idx for idx, value in enumerate(row)}
            continue
        if record_type != "D" or header_idx is None:
            continue

        def get_value(name: str) -> str:
            idx = header_idx.get(name)
            if idx is None or idx >= len(row):
                return ""
            return row[idx]

        settlement = get_value("SETTLEMENTDATE")
        runno = get_value("RUNNO")
        region = get_value("REGIONID")
        intervention = get_value("INTERVENTION")
        if not settlement or not region:
            continue

        demand = get_value("TOTALDEMAND") or ""
        dispatchable_generation = get_value("DISPATCHABLEGENERATION") or ""
        intermittent_generation = get_value("TOTALINTERMITTENTGENERATION") or ""
        available_generation = get_value("AVAILABLEGENERATION") or ""
        initial_supply = get_value("INITIALSUPPLY") or ""
        demand_and_nonschedgen = get_value("DEMAND_AND_NONSCHEDGEN") or ""
        interchange = get_value("NETINTERCHANGE") or ""
        lastchanged = get_value("LASTCHANGED") or ""
        records.append(
            {
                "SETTLEMENTDATE": settlement,
                "RUNNO": pd.to_numeric(runno, errors="coerce"),
                "REGIONID": region,
                "INTERVENTION": pd.to_numeric(intervention, errors="coerce"),
                "TOTAL_DEMAND_MW": pd.to_numeric(demand, errors="coerce"),
                "DISPATCHABLE_GENERATION_MW": pd.to_numeric(dispatchable_generation, errors="coerce"),
                "TOTAL_INTERMITTENT_GENERATION_MW": pd.to_numeric(intermittent_generation, errors="coerce"),
                "AVAILABLE_GENERATION_MW": pd.to_numeric(available_generation, errors="coerce"),
                "INITIAL_SUPPLY_MW": pd.to_numeric(initial_supply, errors="coerce"),
                "DEMAND_AND_NONSCHEDGEN_MW": pd.to_numeric(demand_and_nonschedgen, errors="coerce"),
                "NET_INTERCHANGE_MW": pd.to_numeric(interchange, errors="coerce"),
                "LASTCHANGED": lastchanged,
                "SOURCE_FILE": str(archive_path),
            }
        )

    if not records:
        return pd.DataFrame(
            columns=[
                "SETTLEMENTDATE",
                "RUNNO",
                "REGIONID",
                "INTERVENTION",
                "TOTAL_DEMAND_MW",
                "DISPATCHABLE_GENERATION_MW",
                "TOTAL_INTERMITTENT_GENERATION_MW",
                "AVAILABLE_GENERATION_MW",
                "INITIAL_SUPPLY_MW",
                "DEMAND_AND_NONSCHEDGEN_MW",
                "NET_INTERCHANGE_MW",
                "LASTCHANGED",
                "SOURCE_FILE",
            ]
        )

    frame = pd.DataFrame(records)
    return frame.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Source and normalize DISPATCHREGIONSUM archives.")
    parser.add_argument("--start-month", default="2024-01", help="Start month YYYY-MM")
    parser.add_argument("--end-month", default="2024-01", help="End month YYYY-MM")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    total_rows = 0
    months_done = 0
    for year, month in month_range(args.start_month, args.end_month):
        month_token = f"{year}{month:02d}"
        try:
            fetch_result = fetch_archive_with_retry(
                dataset_token=DATASET_TOKEN,
                year=year,
                month=month,
                raw_dir=RAW_DIR,
            )
        except Exception as exc:
            print(f"skip {month_token}: download failed: {exc}")
            continue

        parsed = _parse_archive(fetch_result.archive_path)
        cache_path = partitioned_cache_path(
            CACHE_DIR,
            year,
            month,
            f"PUBLIC_DVD_DISPATCHREGIONSUM_{month_token}010000.dispatchregionsum.csv.gz",
        )
        parsed.to_csv(cache_path, index=False, compression="gzip")
        write_manifest(
            cache_path.with_suffix(".manifest.json"),
            {
                "dataset": DATASET_TOKEN,
                "schema_version": SCHEMA_VERSION,
                "month": month_token,
                "source_url": fetch_result.source_url,
                "source_archive": str(fetch_result.archive_path),
                "source_sha256": fetch_result.sha256,
                "zip_valid": fetch_result.zip_valid,
                "cache_skipped_download": fetch_result.cache_skipped,
                "rows_normalized": int(len(parsed)),
                "normalized_columns": list(parsed.columns),
                "generated_at_unix": time.time(),
            },
        )
        total_rows += len(parsed)
        months_done += 1
        print(
            progress_line(
                dataset_token=DATASET_TOKEN,
                month_token=month_token,
                rows_normalized=len(parsed),
                cache_path=cache_path,
                cache_skipped=fetch_result.cache_skipped,
            )
        )

    elapsed = time.perf_counter() - started
    print(f"done dataset={DATASET_TOKEN} months={months_done} rows={total_rows} runtime_sec={elapsed:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
