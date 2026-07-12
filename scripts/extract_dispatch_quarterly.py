#!/usr/bin/env python3
"""
Fast, targeted dispatch IRSR quarterly extraction.

Reads archive zips efficiently, filters by quarter, aggregates to quarterly totals
using 30-minute interval averaging. Produces clean dispatch_quarterly_*.csv files.

Usage:
  python scripts/extract_dispatch_quarterly.py C2025Q3
  python scripts/extract_dispatch_quarterly.py --all
"""

import sys, glob, io, zipfile, csv
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IRSR_ARCHIVE_DIR = ROOT / "data/raw/aemo/dispatch_irsr/archive"
IRSR_DERIVED_DIR = ROOT / "data/derived/irsr"

def parse_quarter(quarter_str):
    """Parse C2025Q3 -> (2025, 3)"""
    import re
    m = re.match(r'C(\d{4})Q([1-4])', quarter_str)
    if not m:
        raise ValueError(f"Invalid quarter: {quarter_str}")
    year, q = int(m.group(1)), int(m.group(2))
    month_start = (q - 1) * 3 + 1
    month_end = month_start + 2
    return year, month_start, month_end

def extract_quarter_from_archives(quarter_str):
    """
    Fast extraction: read each archive once, filter rows in-memory,
    aggregate by 30-minute interval.
    """
    print(f"  Extracting {quarter_str}...")
    year, month_start, month_end = parse_quarter(quarter_str)
    
    interval_sum = {}  # (ic, region, interval) -> [residues]
    row_count = 0
    
    archive_files = sorted(glob.glob(str(IRSR_ARCHIVE_DIR / "*.zip")))
    
    for archive_idx, archive_path in enumerate(archive_files):
        try:
            with zipfile.ZipFile(archive_path, 'r') as outer:
                for inner_name in outer.namelist():
                    try:
                        inner_bytes = outer.read(inner_name)
                        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                            for csv_name in inner.namelist():
                                content = inner.read(csv_name).decode('utf-8', 'ignore')
                                for line in content.splitlines():
                                    if not line.startswith('D,DISPATCH,IRSR,2,'):
                                        continue
                                    
                                    try:
                                        # Parse: D,DISPATCH,IRSR,2,"2025/07/01 00:00:00",INTERCONNECTOR,FROM_REGION,RESIDUE
                                        reader = csv.reader([line])
                                        parts = next(reader)
                                        
                                        dt_str = parts[4].strip('"')
                                        dt = datetime.strptime(dt_str, '%Y/%m/%d %H:%M:%S')
                                        
                                        # Filter by quarter
                                        if dt.year != year or dt.month < month_start or dt.month > month_end:
                                            continue
                                        
                                        ic = parts[5].strip('"')
                                        region = parts[6].strip('"')
                                        residue = float(parts[7].strip('"'))
                                        
                                        # Normalize to 30-minute interval
                                        interval_key = dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
                                        key = (ic, region, interval_key.isoformat())
                                        
                                        if key not in interval_sum:
                                            interval_sum[key] = []
                                        interval_sum[key].append(residue)
                                        row_count += 1
                                        
                                    except Exception:
                                        continue
                    except (zipfile.BadZipFile, KeyError):
                        continue
        except Exception:
            continue
        
        if (archive_idx + 1) % 5 == 0:
            print(f"    [{archive_idx+1} archives processed, {row_count} rows]")
    
    print(f"    Total rows: {row_count}")
    
    if row_count == 0:
        return None
    
    # Aggregate: average per 30-min interval, then sum to quarterly
    quarterly = {}
    for (ic, region, interval_iso), residues in interval_sum.items():
        avg_residue = sum(residues) / len(residues)
        key = (ic, region)
        if key not in quarterly:
            quarterly[key] = 0.0
        quarterly[key] += avg_residue
    
    # Convert to DataFrame
    rows = []
    for (ic, region), total in sorted(quarterly.items()):
        rows.append({
            'quarter': quarter_str,
            'interconnector_id': ic,
            'from_region': region,
            'residue_aud': total,
        })
    
    return pd.DataFrame(rows)

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_dispatch_quarterly.py [quarter|--all]")
        print("  e.g. python extract_dispatch_quarterly.py C2025Q3")
        print("       python extract_dispatch_quarterly.py --all")
        return 1
    
    IRSR_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    
    if sys.argv[1] == "--all":
        # Auto-detect from AUCUNITS
        sys.path.insert(0, str(ROOT / "src"))
        from transmission_rights.replication.aucunits_loader import AucUnitsLoader
        loader = AucUnitsLoader()
        loader.load_directory(ROOT / "data/raw/aemo/auction_units")
        quarters = sorted(set(r.relevant_quarter for r in loader.all_rows() if r.relevant_quarter))
    else:
        quarters = sys.argv[1:]
    
    print(f"\nExtracting dispatch IRSR for {len(quarters)} quarter(s)\n")
    
    success = []
    failed = []
    
    for quarter in quarters:
        csv_file = IRSR_DERIVED_DIR / f"dispatch_quarterly_{quarter}.csv"
        
        if csv_file.exists():
            print(f"[{quarter}] Already exists")
            success.append(quarter)
            continue
        
        print(f"[{quarter}]")
        try:
            df = extract_quarter_from_archives(quarter)
            if df is None or df.empty:
                print(f"    WARNING: No data extracted\n")
                failed.append(quarter)
                continue
            
            df.to_csv(csv_file, index=False)
            print(f"    ✓ Saved {csv_file.name} ({len(df)} categories)\n")
            success.append(quarter)
        except Exception as e:
            print(f"    ERROR: {e}\n")
            failed.append(quarter)
    
    print(f"─" * 60)
    print(f"Complete: {len(success)}")
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print(f"\nCSVs ready in {IRSR_DERIVED_DIR}/")
    
    return 0 if len(success) > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
