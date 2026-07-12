#!/usr/bin/env python3
"""
Download RESIDUE_PUBLIC_DATA from MMSDM archive.

Each monthly MMSDM file contains all SRA auction results published that month
(one quarter+tranche per auction event). By downloading all months we get
every tranche for every quarter back to ~2020, giving us:
  - CLEARINGPRICE per category per tranche          (alpha numerator)
  - UNITSSOLD per category per tranche              (position sizing denominator)
  - UNITSOFFERED per category per tranche           (market capacity)

Two filename formats in MMSDM:
  - Legacy  (≤ 2024-07): PUBLIC_DVD_RESIDUE_PUBLIC_DATA_YYYYMMDDHHMM.zip
  - Modern  (≥ 2024-08): PUBLIC_ARCHIVE#RESIDUE_PUBLIC_DATA#FILE01#YYYYMMDDHHMM.zip

Outputs:
  data/raw/aemo/sra_residue_results/residue_results_{YYYY-MM}.csv   (monthly raw)
  data/derived/sra/sra_auction_results.csv                          (all tranches combined)

Usage:
  python scripts/download_sra_residue_results.py                    # download missing months
  python scripts/download_sra_residue_results.py --from 2021-01     # from a specific month
  python scripts/download_sra_residue_results.py --refresh          # re-download all
"""

import argparse
import io
import logging
import os
import zipfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MMSDM_BASE = "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
RAW_DIR = Path("data/raw/aemo/sra_residue_results")
DERIVED_DIR = Path("data/derived/sra")
COMBINED_OUT = DERIVED_DIR / "sra_auction_results.csv"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HaimOS-TR-Bot/1.0)"}


def mmsdm_url(year: int, month: int) -> str:
    ts = f"{year}{month:02d}010000"
    base = f"{MMSDM_BASE}/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader/DATA"
    if (year, month) >= (2024, 8):
        fname = f"PUBLIC_ARCHIVE%23RESIDUE_PUBLIC_DATA%23FILE01%23{ts}.zip"
    else:
        fname = f"PUBLIC_DVD_RESIDUE_PUBLIC_DATA_{ts}.zip"
    return f"{base}/{fname}"


def download_month(year: int, month: int) -> list[dict] | None:
    """Download and parse one month's RESIDUE_PUBLIC_DATA. Returns list of row dicts or None on failure."""
    url = mmsdm_url(year, month)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 404:
            log.debug(f"{year}-{month:02d}: 404 not available")
            return None
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"{year}-{month:02d}: download error — {e}")
        return None

    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        content = zf.read(zf.namelist()[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        log.warning(f"{year}-{month:02d}: bad zip")
        return None

    rows = []
    for line in content.splitlines():
        if not line.startswith("D,IRAUCTION,RESIDUE_PUBLIC_DATA"):
            continue
        # D,IRAUCTION,RESIDUE_PUBLIC_DATA,1,CONTRACTID,VERSIONNO,INTERCONNECTORID,
        #   FROMREGIONID,UNITSOFFERED,UNITSSOLD,CLEARINGPRICE,RESERVEPRICE,LASTCHANGED
        # index: 0=D, 1=IRAUCTION, 2=RESIDUE_PUBLIC_DATA, 3=record_type,
        #        4=contractid, 5=versionno, 6=interconnectorid, 7=fromregionid,
        #        8=unitsoffered, 9=unitssold, 10=clearingprice, 11=reserveprice
        p = line.split(",")
        if len(p) < 12:
            continue
        contract_id = p[4].strip()  # e.g. C2025Q3T09
        if len(contract_id) < 9:
            continue
        quarter = contract_id[:7]  # C2025Q3
        tranche = contract_id[7:]  # T09
        try:
            rows.append({
                "mmsdm_month": f"{year}-{month:02d}",
                "quarter": quarter,
                "tranche": tranche,
                "contract_id": contract_id,
                "version_no": int(p[5]),
                "interconnector_id": p[6].strip(),
                "from_region": p[7].strip(),
                "units_offered": int(p[8]),
                "units_sold": int(p[9]),
                "clearing_price": float(p[10]),
                "reserve_price": float(p[11]) if p[11].strip() else 0.0,
            })
        except (ValueError, IndexError):
            continue

    return rows


def months_range(from_year: int, from_month: int) -> list[tuple[int, int]]:
    today = date.today()
    result = []
    y, m = from_year, from_month
    while (y, m) <= (today.year, today.month):
        result.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


def main():
    parser = argparse.ArgumentParser(description="Download MMSDM RESIDUE_PUBLIC_DATA")
    parser.add_argument("--from", dest="from_month", default="2021-01",
                        help="Earliest month to download (YYYY-MM, default: 2021-01)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-download already-cached months")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    from_year, from_month = map(int, args.from_month.split("-"))

    all_rows: list[dict] = []
    months = months_range(from_year, from_month)
    log.info(f"Processing {len(months)} months from {args.from_month}")

    for year, month in months:
        out_path = RAW_DIR / f"residue_results_{year}-{month:02d}.csv"

        if out_path.exists() and not args.refresh:
            df = pd.read_csv(out_path)
            all_rows.extend(df.to_dict("records"))
            log.info(f"{year}-{month:02d}: loaded from cache ({len(df)} rows)")
            continue

        rows = download_month(year, month)
        if rows is None:
            log.info(f"{year}-{month:02d}: not available, skipping")
            continue

        df = pd.DataFrame(rows)
        df.to_csv(out_path, index=False)
        all_rows.extend(rows)
        log.info(f"{year}-{month:02d}: downloaded {len(rows)} rows → {out_path.name}")

    if not all_rows:
        log.warning("No data downloaded")
        return

    combined = pd.DataFrame(all_rows)

    # Deduplicate: for each (contract_id, interconnector_id, from_region) keep the
    # highest version_no (most recent publication of that auction result).
    combined = (
        combined
        .sort_values("version_no")
        .groupby(["contract_id", "interconnector_id", "from_region"])
        .last()
        .reset_index()
    )

    combined = combined.sort_values(["quarter", "tranche", "interconnector_id", "from_region"])
    combined.to_csv(COMBINED_OUT, index=False)

    quarters = sorted(combined["quarter"].unique())
    log.info(f"Combined: {len(combined)} rows, {len(quarters)} unique quarters")
    log.info(f"Quarter range: {quarters[0]} → {quarters[-1]}")
    log.info(f"Output: {COMBINED_OUT}")


if __name__ == "__main__":
    main()
