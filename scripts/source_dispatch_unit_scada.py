#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatch_unit_scada"
CACHE_DIR = RAW_DIR / ".cache"

URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCH_UNIT_SCADA_{year}{month:02d}010000.zip"
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def month_range(start_month: str, end_month: str) -> list[tuple[int, int]]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("end-month must be >= start-month")
    current = start
    months: list[tuple[int, int]] = []
    while current <= end:
        months.append((current.year, current.month))
        current += 1
    return months


def _download_if_missing(year: int, month: int, destination: Path) -> None:
    if destination.exists():
        return
    url = URL_TEMPLATE.format(year=year, month=month)
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def _parse_archive(archive_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(archive_path, "r") as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            return pd.DataFrame(columns=["SETTLEMENTDATE", "DUID", "SCADA_MW", "REGIONID", "SOURCE_FILE"])
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
        duid = get_value("DUID")
        if not settlement or not duid:
            continue

        scada_value = (
            get_value("SCADAVALUE")
            or get_value("TOTALCLEARED")
            or get_value("INITIALMW")
            or ""
        )
        region = get_value("REGIONID")
        records.append(
            {
                "SETTLEMENTDATE": settlement,
                "DUID": duid,
                "SCADA_MW": pd.to_numeric(scada_value, errors="coerce"),
                "REGIONID": region,
                "SOURCE_FILE": str(archive_path),
            }
        )

    if not records:
        return pd.DataFrame(columns=["SETTLEMENTDATE", "DUID", "SCADA_MW", "REGIONID", "SOURCE_FILE"])

    frame = pd.DataFrame(records)
    frame = frame[frame["SCADA_MW"].notna()].copy()
    return frame.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Source and normalize DISPATCH_UNIT_SCADA archives.")
    parser.add_argument("--start-month", default="2024-01", help="Start month YYYY-MM")
    parser.add_argument("--end-month", default="2024-01", help="End month YYYY-MM")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    months_done = 0
    for year, month in month_range(args.start_month, args.end_month):
        month_token = f"{year}{month:02d}"
        zip_name = f"PUBLIC_DVD_DISPATCH_UNIT_SCADA_{month_token}010000.zip"
        archive_path = RAW_DIR / zip_name

        try:
            _download_if_missing(year, month, archive_path)
        except Exception as exc:
            print(f"skip {month_token}: download failed: {exc}")
            continue

        parsed = _parse_archive(archive_path)
        cache_path = CACHE_DIR / f"PUBLIC_DVD_DISPATCH_UNIT_SCADA_{month_token}010000.dispatch_unit_scada.csv.gz"
        parsed.to_csv(cache_path, index=False, compression="gzip")
        total_rows += len(parsed)
        months_done += 1
        print(f"normalized {month_token}: rows={len(parsed)} -> {cache_path}")

    print(f"done months={months_done} rows={total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())