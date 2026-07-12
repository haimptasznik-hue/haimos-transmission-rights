from __future__ import annotations

from pathlib import Path

import requests

from transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> None:
    base_dir = Path("data/raw/aemo")
    fetcher = HistoricalDataFetcher()

    sra_results = fetcher.list_sra_results_files()
    aucunits = fetcher.list_auction_units_files()
    offers = fetcher.list_sra_offer_files()
    bids = fetcher.list_sra_bid_files()

    print(f"Found {len(sra_results)} SRA_Results files")
    print(f"Found {len(aucunits)} AUCUNITS files")
    print(f"Found {len(offers)} SRA_Offers files")
    print(f"Found {len(bids)} SRA_Bids files")

    downloaded = 0
    skipped = 0

    for filename, _, _ in sra_results:
        try:
            fetcher.fetch_sra_results_file(filename)
            _write_file(base_dir / "sra_results" / filename, fetcher.cached_files[filename])
            downloaded += 1
        except requests.RequestException:
            skipped += 1

    for filename in aucunits:
        try:
            fetcher.fetch_auction_units_file(filename)
            _write_file(base_dir / "auction_units" / filename, fetcher.cached_files[filename])
            downloaded += 1
        except requests.RequestException:
            skipped += 1

    for filename in offers:
        try:
            fetcher.fetch_sra_offer_file(filename)
            _write_file(base_dir / "sra_offers" / filename, fetcher.cached_files[filename])
            downloaded += 1
        except requests.RequestException:
            skipped += 1

    for filename in bids:
        try:
            fetcher.fetch_sra_bid_file(filename)
            _write_file(base_dir / "sra_bids" / filename, fetcher.cached_files[filename])
            downloaded += 1
        except requests.RequestException:
            skipped += 1

    print("Download complete.")
    print(f"Stored under: {base_dir}")
    print(f"Downloaded files: {downloaded}")
    print(f"Skipped files: {skipped}")


if __name__ == "__main__":
    main()