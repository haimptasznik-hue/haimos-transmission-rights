#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.regional_renewable_penetration_feature_store import (  # noqa: E402
    build_regional_renewable_penetration_feature_store,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the regional five-minute renewable penetration feature store.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data" / "derived" / "regional_renewable_penetration_feature_store"),
        help="Output directory for the feature store artifacts.",
    )
    parser.add_argument("--start-month", default=None, help="Optional start month YYYY-MM.")
    parser.add_argument("--end-month", default=None, help="Optional end month YYYY-MM.")
    parser.add_argument("--no-resume", action="store_true", help="Disable checkpoint reuse.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_regional_renewable_penetration_feature_store(
        repo_root=REPO_ROOT,
        output_dir=Path(args.output_dir),
        start_month=args.start_month,
        end_month=args.end_month,
        resume=not args.no_resume,
    )

    print("Regional renewable penetration feature store built")
    print(f"- Rows: {len(result.feature_store)}")
    print(f"- Unmatched observations: {len(result.unmatched_observations)}")
    print(f"- Months: {result.metadata['months']}")
    print(f"- Output: {result.metadata['output_files']['feature_store']}")
    print(f"- Metadata: {result.metadata['output_files']['monthly_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
