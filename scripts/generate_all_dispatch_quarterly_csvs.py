#!/usr/bin/env python3
"""
Generate dispatch_quarterly CSVs for all missing quarters.

Scans available quarters from AUCUNITS data and ensures matching
dispatch_quarterly_*.csv files exist in data/derived/irsr/.
"""

import sys, glob, io, zipfile, csv
from pathlib import Path
from datetime import datetime
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transmission_rights.replication.aucunits_loader import AucUnitsLoader

AUCUNITS_DIR = ROOT / "data/raw/aemo/auction_units"
IRSR_ARCHIVE_DIR = ROOT / "data/raw/aemo/dispatch_irsr/archive"
IRSR_DERIVED_DIR = ROOT / "data/derived/irsr"

def detect_available_quarters():
    """Detect quarters from AUCUNITS data."""
    loader = AucUnitsLoader()
    loader.load_directory(AUCUNITS_DIR)
    quarters = sorted(set(r.relevant_quarter for r in loader.all_rows() if r.relevant_quarter))
    return quarters

def reconstruct_irsr_quarterly_local(quarter: str):
    """
    Reconstruct quarterly dispatch IRSR from local archive files.
    Uses 30-minute interval averaging (historical trading window normalization).
    """
    print(f"  Scanning archive for {quarter} data...")
    
    # Parse quarter
    import re
    match = re.match(r'C(\d{4})Q(\d)', quarter)
    if not match:
        print(f"    ERROR: Invalid quarter format {quarter}")
        return None
    
    year, q = int(match.group(1)), int(match.group(2))
    month_start = (q - 1) * 3 + 1
    month_end = month_start + 2
    
    rows = []
    archive_files = sorted(glob.glob(str(IRSR_ARCHIVE_DIR / "*.zip")))
    
    for archive_path in archive_files:
        try:
            with zipfile.ZipFile(archive_path, 'r') as outer:
                for inner_name in outer.namelist():
                    try:
                        with zipfile.ZipFile(io.BytesIO(outer.read(inner_name))) as inner:
                            for csv_name in inner.namelist():
                                content = inner.read(csv_name).decode('utf-8', 'ignore')
                                for line in content.splitlines():
                                    if not line.startswith('D,DISPATCH,IRSR,2,'): 
                                        continue
                                    
                                    parts = next(csv.reader([line]))
                                    # Format: D,DISPATCH,IRSR,2,TIMESTAMP,INTERCONNECTOR,FROM_REGION,RESIDUE
                                    try:
                                        ts_str = parts[4].strip('"')
                                        dt = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
                                        
                                        # Filter to quarter
                                        if dt.year != year or dt.month < month_start or dt.month > month_end:
                                            continue
                                        
                                        interconnector_id = parts[5].strip('"')
                                        from_region = parts[6].strip('"')
                                        residue = Decimal(parts[7].strip('"'))
                                        
                                        # Normalize to 30-minute interval
                                        interval_dt = dt.replace(
                                            minute=(dt.minute // 30) * 30,
                                            second=0,
                                            microsecond=0
                                        )
                                        
                                        rows.append({
                                            'quarter': quarter,
                                            'trading_interval': interval_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                            'interconnector_id': interconnector_id,
                                            'from_region': from_region,
                                            'residue_aud': float(residue),
                                        })
                                    except Exception:
                                        continue
                    except zipfile.BadZipFile:
                        continue
        except Exception:
            continue
    
    if not rows:
        print(f"    No data found in archive for {quarter}")
        return None
    
    # Aggregate by 30-minute interval
    interval_data = {}
    for row in rows:
        key = (row['quarter'], row['trading_interval'], row['interconnector_id'], row['from_region'])
        if key not in interval_data:
            interval_data[key] = []
        interval_data[key].append(row['residue_aud'])
    
    # Average per interval and sum to quarterly
    quarterly_data = {}
    for (q, interval, ic, region), values in interval_data.items():
        avg_val = sum(values) / len(values)
        key = (ic, region)
        if key not in quarterly_data:
            quarterly_data[key] = 0.0
        quarterly_data[key] += avg_val
    
    # Convert to CSV rows
    csv_rows = []
    for (ic, region), total_residue in sorted(quarterly_data.items()):
        csv_rows.append({
            'quarter': quarter,
            'interconnector_id': ic,
            'from_region': region,
            'residue_aud': total_residue,
        })
    
    return csv_rows

def main():
    quarters = detect_available_quarters()
    print(f"Detected quarters: {quarters}\n")
    
    IRSR_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    
    generated = []
    skipped = []
    
    for quarter in quarters:
        csv_file = IRSR_DERIVED_DIR / f"dispatch_quarterly_{quarter}.csv"
        
        if csv_file.exists():
            print(f"[{quarter}] Already exists: {csv_file.name}")
            skipped.append(quarter)
            continue
        
        print(f"[{quarter}]")
        rows = reconstruct_irsr_quarterly_local(quarter)
        
        if not rows:
            print(f"    SKIPPED: Could not reconstruct\n")
            skipped.append(quarter)
            continue
        
        # Write CSV
        import pandas as pd
        df = pd.DataFrame(rows)
        df.to_csv(csv_file, index=False)
        print(f"    ✓ Created {csv_file.name} with {len(rows)} rows\n")
        generated.append(quarter)
    
    print(f"─" * 50)
    print(f"Summary:")
    print(f"  Generated: {len(generated)} ({', '.join(generated) if generated else 'none'})")
    print(f"  Skipped:   {len(skipped)} ({', '.join(skipped) if skipped else 'none'})")
    print(f"\nAll CSVs ready in {IRSR_DERIVED_DIR}/")
    
    return 0 if len(generated) > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
