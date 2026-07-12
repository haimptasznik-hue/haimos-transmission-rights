from __future__ import annotations

from datetime import datetime

from transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher
from transmission_rights.services.aemo.sra_market_calendar import SRAMarketCalendar
from transmission_rights.services.aemo.sra_product_registry import SRAProductRegistry


def main() -> None:
    fetcher = HistoricalDataFetcher()
    registry = SRAProductRegistry()
    calendar = SRAMarketCalendar()

    files = fetcher.list_sra_results_files()
    if not files:
        print("No SRA_Results files found.")
        return

    latest_file, quarter, tranche = files[-1]
    csv_text = fetcher.fetch_sra_results_file(latest_file)
    snapshots = fetcher.parse_sra_results(csv_text)

    effective_date = fetcher._effective_date_from_filename(latest_file)
    loaded_products = fetcher.load_products_from_sra_results(registry, snapshots, effective_date)
    loaded_events = fetcher.load_calendar_from_sra_results(
        calendar,
        snapshots,
        auction_timestamp=datetime.combine(effective_date, datetime.min.time()),
    )

    print(f"Loaded file: {latest_file}")
    print(f"Quarter/Tranche: {quarter} / T{tranche:02d}")
    print(f"Snapshots parsed: {len(snapshots)}")
    print(f"Products loaded: {loaded_products}")
    print(f"Auction events loaded: {loaded_events}")
    print(f"Unique interconnectors: {len({s.directional_interconnector for s in snapshots})}")


if __name__ == "__main__":
    main()