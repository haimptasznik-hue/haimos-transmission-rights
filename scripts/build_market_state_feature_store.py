#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.market_state_feature_store import (  # noqa: E402
    build_market_state_feature_store,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Market State Feature Store from the existing PIT-safe market state table.")
    parser.add_argument(
        "--input-csv",
        default=str(REPO_ROOT / "reports" / "phase5c_market_state.csv"),
        help="Input market state CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data" / "derived" / "market_state_feature_store"),
        help="Output directory for the feature store artifacts.",
    )
    parser.add_argument("--chunksize", type=int, default=50000, help="CSV chunksize for streaming build.")
    parser.add_argument("--sample-rows", type=int, default=1000, help="Number of sample rows to export.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = build_market_state_feature_store(
        input_csv_path=Path(args.input_csv),
        output_dir=Path(args.output_dir),
        chunksize=args.chunksize,
        sample_rows=args.sample_rows,
    )

    print("Market State Feature Store built successfully")
    print(f"- Rows: {results['row_count']}")
    print(f"- Features: {results['feature_count']}")
    print(f"- Coverage: {results['coverage_start']} -> {results['coverage_end']}")
    print(f"- Data: {results['data_path']}")
    print(f"- Dictionary: {results['metadata_path']}")
    print(f"- Coverage report: {results['coverage_path']}")
    print(f"- Sample: {results['sample_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())