#!/usr/bin/env python3
"""
Download SETIRSURPLUS from MMSDM (2021-01 to present).

For each monthly MMSDM package:
  1. Fetch the DATA directory listing
  2. Download the SETIRSURPLUS zip
  3. Extract and parse rows
  4. Aggregate to quarterly totals (30-min interval averaging)
  5. Save per-month CSV to data/raw/aemo/setirsurplus/
  6. Also saves a combined quarterly CSV to data/derived/irsr/

SETIRSURPLUS columns used:
  SETTLEMENTDATE, SETTLEMENTRUNNO, PERIODID,
  INTERCONNECTORID, REGIONID, SURPLUSVALUE

Usage:
  python scripts/download_setirsurplus.py
  python scripts/download_setirsurplus.py --from 2023-01
  python scripts/download_setirsurplus.py --month 2024-10
"""
import sys, re, io, zipfile, csv, time
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BASE_URL = "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
OUT_RAW = ROOT / "data/raw/aemo/setirsurplus"
OUT_DERIVED = ROOT / "data/derived/irsr"

OUT_RAW.mkdir(parents=True, exist_ok=True)
OUT_DERIVED.mkdir(parents=True, exist_ok=True)

def get_setirsurplus_url(session, yr, mo):
    listing = BASE_URL + f"{yr}/MMSDM_{yr}_{mo:02d}/MMSDM_Historical_Data_SQLLoader/DATA/"
    r = session.get(listing, timeout=15)
    if r.status_code != 200:
        return None
    m = re.search(r'(PUBLIC_ARCHIVE%23SETIRSURPLUS[^"<>\s]+)', r.text)
    if not m:
        return None
    return listing + m.group(1)

def download_and_parse(session, yr, mo):
    url = get_setirsurplus_url(session, yr, mo)
    if not url:
        return None

    r = session.get(url, timeout=60)
    if r.status_code != 200 or r.content[:2] != b'PK':
        return None

    rows = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for fname in z.namelist():
            content = z.read(fname).decode('utf-8', 'ignore').splitlines()
            for line in content:
                if not line.startswith('D,SETTLEMENTS,IRSURPLUS'):
                    continue
                try:
                    parts = next(csv.reader([line]))
                    # [4]=SETTLEMENTDATE [5]=RUNNO [6]=PERIODID
                    # [7]=INTERCONNECTORID [8]=REGIONID [11]=SURPLUSVALUE
                    settle_dt = datetime.strptime(parts[4].strip('"'), '%Y/%m/%d %H:%M:%S')
                    run_no    = int(parts[5])
                    period_id = int(parts[6])
                    ic        = parts[7].strip('"')
                    region    = parts[8].strip('"')
                    surplus   = float(parts[11])
                    rows.append((settle_dt, run_no, period_id, ic, region, surplus))
                except Exception:
                    continue
    return rows

def rows_to_quarterly(rows, yr, mo):
    """
    Aggregate per-5-minute rows to quarterly totals.
    Uses 30-minute interval averaging (consistent with Dispatch_IRSR treatment).
    Takes the highest run_no per settlement date (final settlement run).
    """
    if not rows:
        return pd.DataFrame()

    # Keep only final settlement run per date
    best_run = defaultdict(int)
    for (dt, run_no, period_id, ic, region, surplus) in rows:
        key = dt.date()
        if run_no > best_run[key]:
            best_run[key] = run_no

    # Filter to best run per date
    filtered = [r for r in rows if r[1] == best_run[r[0].date()]]

    # Convert PERIODID (1-288 or 1-48 in half-hours) to 30-min bucket
    # PERIODID in SETTLEMENTS is trading period (half-hour): 1-48
    # So each row is already a 30-min settlement period
    interval_data = defaultdict(list)
    for (dt, run_no, period_id, ic, region, surplus) in filtered:
        # quarter
        q = (dt.month - 1) // 3 + 1
        quarter = f"C{dt.year}Q{q}"
        key = (quarter, ic, region, dt.date(), period_id)
        interval_data[key].append(surplus)

    # Average duplicates within same period, then sum to quarterly
    quarterly = defaultdict(float)
    for (quarter, ic, region, dt, period_id), values in interval_data.items():
        quarterly[(quarter, ic, region)] += sum(values) / len(values)

    result_rows = []
    for (quarter, ic, region), total in sorted(quarterly.items()):
        result_rows.append({
            'quarter': quarter,
            'interconnector_id': ic,
            'from_region': region,
            'surplus_aud': total,
        })
    return pd.DataFrame(result_rows)


def main():
    # Parse args
    from_ym = (2021, 1)
    single_month = None

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--from' and i+1 < len(sys.argv):
            yr, mo = sys.argv[i+1].split('-')
            from_ym = (int(yr), int(mo))
            i += 2
        elif sys.argv[i] == '--month' and i+1 < len(sys.argv):
            yr, mo = sys.argv[i+1].split('-')
            single_month = (int(yr), int(mo))
            i += 2
        else:
            i += 1

    # Build month list
    today = date.today()
    if single_month:
        months = [single_month]
    else:
        months = []
        yr, mo = from_ym
        while (yr, mo) <= (today.year, today.month):
            months.append((yr, mo))
            mo += 1
            if mo > 12:
                mo = 1
                yr += 1

    session = requests.Session()
    session.headers['User-Agent'] = UA

    print(f"\nDownloading SETIRSURPLUS: {len(months)} months ({months[0][0]}-{months[0][1]:02d} to {months[-1][0]}-{months[-1][1]:02d})\n")

    # Accumulate all rows for combined quarterly output
    all_quarterly = defaultdict(lambda: defaultdict(float))  # quarter -> (ic, region) -> total

    success, skipped, failed = [], [], []

    for yr, mo in months:
        label = f"{yr}-{mo:02d}"
        raw_csv = OUT_RAW / f"setirsurplus_{label}.csv"

        # Load from cache if already downloaded
        if raw_csv.exists():
            df = pd.read_csv(raw_csv)
            print(f"  [{label}] cached ({len(df)} rows)")
            for _, row in df.iterrows():
                all_quarterly[row['quarter']][(row['interconnector_id'], row['from_region'])] += row['surplus_aud']
            skipped.append(label)
            continue

        print(f"  [{label}] downloading...", end='', flush=True)
        rows = download_and_parse(session, yr, mo)

        if rows is None:
            print(f" NOT AVAILABLE")
            failed.append(label)
            time.sleep(0.2)
            continue

        df = rows_to_quarterly(rows, yr, mo)
        if df.empty:
            print(f" EMPTY")
            failed.append(label)
            time.sleep(0.2)
            continue

        df.to_csv(raw_csv, index=False)
        print(f" ✓ {len(rows):,} rows -> {len(df)} quarter/category totals")

        for _, row in df.iterrows():
            all_quarterly[row['quarter']][(row['interconnector_id'], row['from_region'])] += row['surplus_aud']

        success.append(label)
        time.sleep(0.3)  # polite delay

    # Write combined quarterly CSV
    combined_rows = []
    for quarter in sorted(all_quarterly):
        for (ic, region), total in sorted(all_quarterly[quarter].items()):
            combined_rows.append({
                'quarter': quarter,
                'interconnector_id': ic,
                'from_region': region,
                'surplus_aud': total,
            })
    combined_df = pd.DataFrame(combined_rows)
    combined_path = OUT_DERIVED / "setirsurplus_quarterly_all.csv"
    combined_df.to_csv(combined_path, index=False)

    print(f"\n{'─'*60}")
    print(f"Downloaded:  {len(success)}")
    print(f"Cached:      {len(skipped)}")
    print(f"Not found:   {len(failed)}")
    print(f"\nQuarters covered: {sorted(all_quarterly.keys())}")
    print(f"Combined quarterly file: {combined_path}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
