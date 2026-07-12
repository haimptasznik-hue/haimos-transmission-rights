from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

HistoricalDataFetcher = importlib.import_module(
    "transmission_rights.adapters.aemo.historical_data_fetcher"
).HistoricalDataFetcher
SRAAuctionParser = importlib.import_module(
    "transmission_rights.services.aemo.sra_auction_parser"
).SRAAuctionParser
SRAMarketCalendar = importlib.import_module(
    "transmission_rights.services.aemo.sra_market_calendar"
).SRAMarketCalendar
SRAProductRegistry = importlib.import_module(
    "transmission_rights.services.aemo.sra_product_registry"
).SRAProductRegistry


def ingest_directory(input_dir: Path) -> pd.DataFrame:
    fetcher = HistoricalDataFetcher()
    parser = SRAAuctionParser()
    registry = SRAProductRegistry()
    calendar = SRAMarketCalendar()

    rows: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("*.csv")):
        csv_text = path.read_text(encoding="utf-8")
        snapshots = fetcher.parse_sra_results(csv_text)
        if not snapshots:
            continue

        effective_date = fetcher._effective_date_from_filename(path.name)
        products_loaded = fetcher.load_products_from_sra_results(
            registry=registry,
            snapshots=snapshots,
            effective_date=effective_date,
        )
        events_loaded = fetcher.load_calendar_from_sra_results(
            calendar=calendar,
            snapshots=snapshots,
            auction_timestamp=datetime.combine(effective_date, datetime.min.time()),
        )
        ingested_rows = parser.ingest_sra_results_csv_text(csv_text)
        report_datetime = parser._parse_report_datetime(csv_text)

        rows.append(
            {
                "filename": path.name,
                "quarter": snapshots[0].quarter,
                "tranche_no": snapshots[0].tranche_no,
                "report_datetime": report_datetime.isoformat(),
                "snapshot_rows": len(snapshots),
                "ingested_rows": ingested_rows,
                "products_loaded": products_loaded,
                "events_loaded": events_loaded,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest historical SRA_Results files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/aemo/sra_results"),
        help="Directory containing downloaded SRA_Results CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/derived/aemo"),
        help="Directory for summary outputs.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    summary_df = ingest_directory(args.input_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "historical_auction_results_summary.csv"
    summary_df.to_csv(output_path, index=False)

    print(f"Files processed: {len(summary_df)}")
    print(f"Rows ingested: {int(summary_df['ingested_rows'].sum()) if not summary_df.empty else 0}")
    print(f"Products loaded: {int(summary_df['products_loaded'].sum()) if not summary_df.empty else 0}")
    print(f"Calendar events loaded: {int(summary_df['events_loaded'].sum()) if not summary_df.empty else 0}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
