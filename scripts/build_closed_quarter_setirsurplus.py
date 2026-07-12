#!/usr/bin/env python3
"""Build a closed-quarter-only SETIRSURPLUS dataset.

This script filters `data/derived/irsr/setirsurplus_quarterly_all.csv` down to
quarters that are fully closed as of a given date, then writes:

  `data/derived/irsr/setirsurplus_quarterly_closed.csv`

Usage:
  python scripts/build_closed_quarter_setirsurplus.py
  python scripts/build_closed_quarter_setirsurplus.py --as-of 2026-07-12
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transmission_rights.replication.quarter_closure import closed_quarters


def parse_as_of(argv: list[str]) -> date:
    if "--as-of" in argv:
        idx = argv.index("--as-of")
        if idx + 1 >= len(argv):
            raise SystemExit("--as-of requires YYYY-MM-DD")
        return datetime.strptime(argv[idx + 1], "%Y-%m-%d").date()
    return date.today()


def main() -> int:
    as_of = parse_as_of(sys.argv[1:])
    source = ROOT / "data/derived/irsr/setirsurplus_quarterly_all.csv"
    target = ROOT / "data/derived/irsr/setirsurplus_quarterly_closed.csv"

    if not source.exists():
        raise SystemExit(f"Missing source dataset: {source}")

    df = pd.read_csv(source)
    quarters = sorted(set(df["quarter"].dropna().astype(str)))
    keep = set(closed_quarters(quarters, as_of=as_of))
    filtered = df[df["quarter"].astype(str).isin(keep)].copy()
    filtered.to_csv(target, index=False)

    print(f"as_of={as_of.isoformat()}")
    print(f"quarters_kept={len(keep)}")
    print(f"rows_written={len(filtered)}")
    print(f"output={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())