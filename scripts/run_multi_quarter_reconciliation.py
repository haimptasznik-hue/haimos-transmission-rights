#!/usr/bin/env python3
"""
Multi-quarter reconciliation orchestrator.

Automatically runs reconciliation for all detected quarters and produces
a comprehensive multi-quarter report with aggregate statistics.

Usage:
  python scripts/run_multi_quarter_reconciliation.py
  python scripts/run_multi_quarter_reconciliation.py --output report.json
  python scripts/run_multi_quarter_reconciliation.py --quarters C2025Q3 C2025Q4 --output report.json

Output:
  - per-quarter reconciliation summary
  - aggregate certification statistics
  - JSON report with detailed metrics
"""

import sys, json, re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transmission_rights.replication.payout_recon_engine import PayoutReconEngine
from transmission_rights.replication.aucunits_loader import AucUnitsLoader
from transmission_rights.replication.quarter_closure import closed_quarters, open_quarters

AUCUNITS_DIR = ROOT / "data/raw/aemo/auction_units"
IRSR_DERIVED_DIR = ROOT / "data/derived/irsr"

TOTAL_THRESHOLD_PCT = 0.01
CATEGORY_THRESHOLD_PCT = 0.051

@dataclass
class QuarterResult:
    """Result for a single quarter reconciliation."""
    quarter: str
    total_aucunits_aud: float
    total_reconstructed_residue_aud: float
    total_gap_aud: float
    total_gap_pct: float
    max_category_gap_pct: float
    num_categories: int
    certification_status: str
    errors: list

def detect_available_quarters():
    """Scan AUCUNITS data to find all quarters."""
    loader = AucUnitsLoader()
    loader.load_directory(AUCUNITS_DIR)
    quarters = sorted(set(r.relevant_quarter for r in loader.all_rows() if r.relevant_quarter))
    return quarters

def reconcile_quarter(engine: PayoutReconEngine, quarter: str) -> QuarterResult:
    """Run reconciliation for a single quarter."""
    result = QuarterResult(
        quarter=quarter,
        total_aucunits_aud=0.0,
        total_reconstructed_residue_aud=0.0,
        total_gap_aud=0.0,
        total_gap_pct=0.0,
        max_category_gap_pct=0.0,
        num_categories=0,
        certification_status="UNKNOWN",
        errors=[]
    )
    
    try:
        report = engine.reconcile(quarter)
        
        if not report.rows:
            result.errors.append(f"No reconciliation data for {quarter}")
            result.certification_status = "NO_DATA"
            return result
        
        comparable_rows = [r for r in report.rows 
                          if "no_aucunits" not in r.warnings and "no_dispatch_irsr" not in r.warnings]
        
        if not comparable_rows:
            result.errors.append(f"No comparable categories in {quarter}")
            result.certification_status = "NO_COMPARABLES"
            return result
        
        result.total_aucunits_aud = float(report.total_aemo_reference_aud)
        result.total_reconstructed_residue_aud = float(report.total_reconstructed_residue_aud)
        result.total_gap_aud = result.total_reconstructed_residue_aud - result.total_aucunits_aud
        result.total_gap_pct = (abs(result.total_gap_aud) / abs(result.total_aucunits_aud)) if result.total_aucunits_aud else 0.0
        result.max_category_gap_pct = max(float(r.percentage_variance) for r in comparable_rows)
        result.num_categories = len(comparable_rows)
        
        # Certification
        pass_total = result.total_gap_pct <= TOTAL_THRESHOLD_PCT
        pass_category = result.max_category_gap_pct <= CATEGORY_THRESHOLD_PCT
        result.certification_status = "PASS" if (pass_total and pass_category) else "NOT_YET"
        
    except Exception as e:
        result.errors.append(f"Reconciliation error: {str(e)}")
        result.certification_status = "ERROR"
    
    return result

def parse_args():
    """Parse command-line arguments."""
    quarters = None
    output_file = None
    include_open = False
    as_of = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--quarters":
            quarters = []
            i += 1
            while i < len(sys.argv) and not sys.argv[i].startswith("--"):
                quarters.append(sys.argv[i])
                i += 1
        elif sys.argv[i] == "--output":
            i += 1
            if i < len(sys.argv):
                output_file = sys.argv[i]
            i += 1
        elif sys.argv[i] == "--include-open":
            include_open = True
            i += 1
        elif sys.argv[i] == "--as-of" and i + 1 < len(sys.argv):
            as_of = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    return quarters, output_file, include_open, as_of

def main():
    # Parse arguments
    quarters, output_file, include_open, as_of = parse_args()
    
    # Detect quarters if not specified
    if not quarters:
        quarters = detect_available_quarters()

    if not include_open:
        quarters = closed_quarters(quarters)
    else:
        # Keep open quarters available only when explicitly requested.
        quarters = sorted(set(quarters))
    
    if not quarters:
        print("ERROR: No quarters detected")
        return 1
    
    print(f"\nMulti-Quarter Reconciliation Orchestrator")
    print(f"Quarters to process: {quarters}\n")
    
    # Initialize engine once
    engine = PayoutReconEngine()
    n = engine.load_aucunits_directory(AUCUNITS_DIR)
    print(f"Loaded {n} AUCUNITS rows")
    
    # Load all dispatch quarterly CSVs available
    irsr_files = sorted(IRSR_DERIVED_DIR.glob("dispatch_quarterly_*.csv"))
    for f in irsr_files:
        try:
            engine.load_dispatch_quarterly(f)
        except Exception:
            pass  # Skip if load fails
    print(f"Loaded {len(irsr_files)} dispatch IRSR files\n")
    
    # Run reconciliation for each quarter
    results = []
    for quarter in quarters:
        print(f"[{quarter}]")
        result = reconcile_quarter(engine, quarter)
        results.append(result)
        
        # Print summary
        if result.certification_status == "PASS":
            status_marker = "✓"
        elif result.certification_status in ("NOT_YET", "NO_DATA", "NO_COMPARABLES"):
            status_marker = "~"
        else:
            status_marker = "✗"
        
        if result.errors:
            print(f"  {status_marker} Status: {result.certification_status}")
            print(f"    Errors: {'; '.join(result.errors)}")
        else:
            print(f"  {status_marker} Status: {result.certification_status}")
            print(f"    Total gap: {result.total_gap_pct:.2%} ({TOTAL_THRESHOLD_PCT:.0%} threshold)")
            print(f"    Max category gap: {result.max_category_gap_pct:.2%} ({CATEGORY_THRESHOLD_PCT:.0%} threshold)")
            print(f"    Categories: {result.num_categories}")
        print()
    
    # Aggregate stats
    passed = [r for r in results if r.certification_status == "PASS"]
    not_yet = [r for r in results if r.certification_status == "NOT_YET"]
    errors = [r for r in results if r.certification_status in ("ERROR", "NO_DATA", "NO_COMPARABLES")]
    
    print(f"╭─ SUMMARY ──────────────────────────")
    print(f"├─ PASS:       {len(passed)}/{len(results)}")
    print(f"├─ NOT_YET:    {len(not_yet)}/{len(results)}")
    print(f"├─ ERRORS:     {len(errors)}/{len(results)}")
    print(f"╰─ Total Quarters: {len(results)}\n")
    
    if passed:
        avg_gap_pct = sum(r.total_gap_pct for r in passed) / len(passed)
        max_category_avg = sum(r.max_category_gap_pct for r in passed) / len(passed)
        print(f"Passed quarters: {[r.quarter for r in passed]}")
        print(f"  Average total gap: {avg_gap_pct:.2%}")
        print(f"  Average max category gap: {max_category_avg:.2%}\n")
    
    # Write JSON report
    if output_file:
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "thresholds": {
                "total_pct": TOTAL_THRESHOLD_PCT,
                "category_pct": CATEGORY_THRESHOLD_PCT,
            },
            "quarters": [asdict(r) for r in results],
            "summary": {
                "total_quarters": len(results),
                "passed": len(passed),
                "not_yet": len(not_yet),
                "errors": len(errors),
            }
        }
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report written to {output_file}\n")
    
    return 0 if len(passed) > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
