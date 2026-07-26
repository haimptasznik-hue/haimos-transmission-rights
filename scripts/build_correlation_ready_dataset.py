#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.dataset_library import (  # noqa: E402
    build_correlation_ready_table,
    dataset_catalog_frame,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a normalized AEMO-aligned correlation-ready dataset.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data" / "derived" / "correlation_library"),
        help="Output directory.",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Optional dataset IDs to include.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    joined = build_correlation_ready_table(repo_root=REPO_ROOT, dataset_ids=args.datasets)
    catalog = dataset_catalog_frame(REPO_ROOT)

    joined_path = output_dir / "normalized_correlation_table.csv.gz"
    catalog_path = output_dir / "dataset_catalog.csv"
    summary_path = output_dir / "normalized_correlation_summary.json"

    joined.to_csv(joined_path, index=False, compression="gzip")
    catalog.to_csv(catalog_path, index=False)

    summary = {
        "dataset_count": int(len(catalog if args.datasets is None else catalog[catalog["dataset_id"].isin(args.datasets)])),
        "row_count": int(len(joined)),
        "column_count": int(len(joined.columns)),
        "join_key": "interval_timestamp_utc",
        "output_path": str(joined_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Normalized correlation dataset built")
    print(f"- Rows: {summary['row_count']}")
    print(f"- Columns: {summary['column_count']}")
    print(f"- Output: {joined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())