#!/usr/bin/env python3
"""
Run AEMO payout reconciliation for all available quarters.

Usage:
  python scripts/run_reconciliation.py [quarter]
  e.g.  python scripts/run_reconciliation.py C2025Q2

If no quarter specified, runs all quarters where both AUCUNITS and dispatch IRSR data exist.
"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transmission_rights.replication.payout_recon_engine import PayoutReconEngine, print_report

AUCUNITS_DIR  = ROOT / "data/raw/aemo/auction_units"
IRSR_DIR      = ROOT / "data/derived/irsr"

TOTAL_THRESHOLD_PCT = 0.01
CATEGORY_THRESHOLD_PCT = 0.051


def _print_certification(report) -> None:
    comparable_rows = [r for r in report.rows if "no_aucunits" not in r.warnings and "no_dispatch_irsr" not in r.warnings]
    if not comparable_rows:
        print("  Digital Twin Certification: INDETERMINATE (no comparable categories)")
        return

    total_baseline = float(report.total_aemo_reference_aud)
    total_gap = abs(float(report.total_reconstructed_residue_aud) - total_baseline)
    total_gap_pct = (total_gap / abs(total_baseline)) if total_baseline else 0.0

    max_cat_pct = max(float(r.percentage_variance) for r in comparable_rows)
    pass_total = total_gap_pct <= TOTAL_THRESHOLD_PCT
    pass_category = max_cat_pct <= CATEGORY_THRESHOLD_PCT
    certified = pass_total and pass_category

    status = "PASS" if certified else "NOT YET"
    print(
        f"  Digital Twin Certification: {status}  "
        f"(total_gap={total_gap_pct:.2%}, max_category_gap={max_cat_pct:.2%}, "
        f"thresholds total<={TOTAL_THRESHOLD_PCT:.0%}, category<={CATEGORY_THRESHOLD_PCT:.0%})"
    )


def main():
    engine = PayoutReconEngine()

    # Load all AUCUNITS
    n = engine.load_aucunits_directory(AUCUNITS_DIR)
    print(f"Loaded {n} AUCUNITS rows from {len(list(AUCUNITS_DIR.glob('AUCUNITS_*.R*')))} files")

    # Load all dispatch quarterly CSVs
    irsr_files = sorted(IRSR_DIR.glob("dispatch_quarterly_*.csv"))
    for f in irsr_files:
        engine.load_dispatch_quarterly(f)
        print(f"Loaded dispatch IRSR: {f.name}")

    quarters = [sys.argv[1]] if len(sys.argv) > 1 else engine._loader.list_quarters()
    print(f"\nRunning reconciliation for {len(quarters)} quarter(s): {quarters}\n")

    for quarter in quarters:
        report = engine.reconcile(quarter)
        if not report.rows:
            print(f"  {quarter}: no data")
            continue
        print_report(report)
        _print_certification(report)


if __name__ == "__main__":
    main()
