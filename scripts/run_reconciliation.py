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


if __name__ == "__main__":
    main()
