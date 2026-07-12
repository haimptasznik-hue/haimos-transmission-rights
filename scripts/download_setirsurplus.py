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
from urllib.parse import urljoin

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

def get_month_listing(session, yr, mo):
    listing = BASE_URL + f"{yr}/MMSDM_{yr}_{mo:02d}/MMSDM_Historical_Data_SQLLoader/DATA/"
    r = session.get(listing, timeout=20)
    if r.status_code != 200:
        return None, None
    return listing, r.text


def get_table_url(session, yr, mo, table_name):
    listing, html = get_month_listing(session, yr, mo)
    if not listing:
        return None

    patterns = [
        rf'(PUBLIC_ARCHIVE%23{table_name}%23FILE\d+%23\d+\.zip)',
        rf'(PUBLIC_DVD_{table_name}_\d+\.zip)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return urljoin(listing, match.group(1))

    href_match = re.search(
        rf'href="([^"]*(?:PUBLIC_ARCHIVE%23{table_name}%23FILE\d+%23\d+\.zip|PUBLIC_DVD_{table_name}_\d+\.zip)[^"]*)"',
        html,
        re.IGNORECASE,
    )
    if href_match:
        return urljoin(listing, href_match.group(1))

    return None

def download_and_parse(session, yr, mo):
    setirsurplus_url = get_table_url(session, yr, mo, "SETIRSURPLUS")
    if not setirsurplus_url:
        return None, None

    billingruntrk_url = get_table_url(session, yr, mo, "BILLINGRUNTRK")

    r = session.get(setirsurplus_url, timeout=90)
    if r.status_code != 200 or r.content[:2] != b'PK':
        return None, None

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
    billing_rows = []
    if billingruntrk_url:
        rb = session.get(billingruntrk_url, timeout=60)
        if rb.status_code == 200 and rb.content[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(rb.content)) as zb:
                for fname in zb.namelist():
                    content = zb.read(fname).decode('utf-8', 'ignore').splitlines()
                    for line in content:
                        if not line.startswith('D,BILLING,RUNTRK'):
                            continue
                        try:
                            parts = next(csv.reader([line]))
                            billing_rows.append({
                                'contract_year': int(parts[4]),
                                'week_no': int(parts[5]),
                                'bill_run_no': int(parts[6]),
                                'status': parts[7].strip('"').upper(),
                            })
                        except Exception:
                            continue

    return rows, billing_rows

def rows_to_quarterly(rows, billing_rows):
    """
    Aggregate per-5-minute rows to quarterly totals.
    Uses billing run tracking where possible to select FINAL/PRELIM/REVISE runs.
    PERIODID is 5-minute settlement intervals (1-288).
    """
    if not rows:
        return pd.DataFrame()

    run_by_week = {}
    if billing_rows:
        priority = {'FINAL': 4, 'REVISE': 3, 'PRELIM': 2, 'DAILY': 1}
        best = {}
        for row in billing_rows:
            status = row['status']
            if status not in priority:
                continue
            key = (row['contract_year'], row['week_no'])
            score = (priority[status], row['bill_run_no'])
            if key not in best or score > best[key][0]:
                best[key] = (score, row['bill_run_no'])
        run_by_week = {k: v[1] for k, v in best.items()}

    filtered = []
    if run_by_week:
        for row in rows:
            dt, run_no, period_id, ic, region, surplus = row
            iso = dt.isocalendar()
            target_run = run_by_week.get((iso.year, iso.week))
            if target_run is None:
                continue
            if run_no == target_run:
                filtered.append(row)
    else:
        best_run = defaultdict(int)
        for (dt, run_no, period_id, ic, region, surplus) in rows:
            key = (dt.date(), period_id, ic, region)
            if run_no > best_run[key]:
                best_run[key] = run_no
        for row in rows:
            dt, run_no, period_id, ic, region, surplus = row
            key = (dt.date(), period_id, ic, region)
            if run_no == best_run[key]:
                filtered.append(row)

    # PERIODID in SETIRSURPLUS is 5-minute settlement periods (1-288)
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


def rows_to_final_period_rows(rows):
    """
    Robust selector across vintages:
    pick highest SETTLEMENTRUNNO per (settlement_date, period_id, ic, region).
    """
    best_run = {}
    best_val = {}
    for (dt, run_no, period_id, ic, region, surplus) in rows:
        key = (dt.date(), period_id, ic, region)
        if key not in best_run or run_no > best_run[key]:
            best_run[key] = run_no
            best_val[key] = surplus
    final_rows = []
    for (settle_date, period_id, ic, region), surplus in best_val.items():
        final_rows.append((settle_date, period_id, ic, region, surplus))
    return final_rows


def period_rows_to_quarterly(period_rows):
    quarterly = defaultdict(float)
    for settle_date, period_id, ic, region, surplus in period_rows:
        q = (settle_date.month - 1) // 3 + 1
        quarter = f"C{settle_date.year}Q{q}"
        quarterly[(quarter, ic, region)] += surplus
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
    refresh = False

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
        elif sys.argv[i] == '--refresh':
            refresh = True
            i += 1
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
    all_quarterly = defaultdict(lambda: defaultdict(float))  # backward-compatible accumulator
    all_period_rows = {}  # (date, period_id, ic, region) -> surplus; later months override earlier

    success, skipped, failed = [], [], []

    for yr, mo in months:
        label = f"{yr}-{mo:02d}"
        raw_csv = OUT_RAW / f"setirsurplus_{label}.csv"

        # Load from cache if already downloaded
        if raw_csv.exists() and not refresh:
            df = pd.read_csv(raw_csv)
            print(f"  [{label}] cached ({len(df)} rows)")
            for _, row in df.iterrows():
                all_quarterly[row['quarter']][(row['interconnector_id'], row['from_region'])] += row['surplus_aud']
            skipped.append(label)
            continue

        print(f"  [{label}] downloading...", end='', flush=True)
        rows, billing_rows = download_and_parse(session, yr, mo)

        if rows is None:
            print(f" NOT AVAILABLE")
            failed.append(label)
            time.sleep(0.2)
            continue

        # Use robust per-period selector for storage and combined totals
        period_rows = rows_to_final_period_rows(rows)
        for settle_date, period_id, ic, region, surplus in period_rows:
            all_period_rows[(settle_date, period_id, ic, region)] = surplus

        # Keep monthly CSV output as quarterly rollup for this month's selected rows
        df = period_rows_to_quarterly(period_rows)
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

    # Build combined quarterly CSV.
    # If refresh run collected period rows, aggregate from deduped global period set.
    if all_period_rows:
        combined_df = period_rows_to_quarterly([
            (d, p, ic, r, v) for (d, p, ic, r), v in all_period_rows.items()
        ])
    else:
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
