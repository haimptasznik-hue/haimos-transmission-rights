#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.capability1_market_state import write_capability1_artifacts  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Capability 1 market-state inventory and combined dataset.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root path.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "reports" / "capability1"),
        help="Directory for generated inventory and summary artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = write_capability1_artifacts(Path(args.repo_root), Path(args.output_dir))

    print("Capability 1 market-state artifacts built successfully")
    print(f"- Completion: {result.summary['completion_pct']}%")
    print(f"- Combined rows: {result.summary['combined_rows']}")
    print(f"- Inventory: {Path(args.output_dir) / 'capability1_market_state_inventory.csv'}")
    print(f"- Source availability: {Path(args.output_dir) / 'capability1_source_availability.csv'}")
    print(f"- Combined market state: {Path(args.output_dir) / 'capability1_combined_market_state.csv'}")
    print(f"- Summary: {Path(args.output_dir) / 'capability1_market_state_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
