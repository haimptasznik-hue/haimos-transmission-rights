from __future__ import annotations

import argparse
from pathlib import Path

from transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct quarterly IRSR from Dispatch_IRSR files.")
    parser.add_argument("--start-quarter", required=True, help="Quarter format CYYYYQn, e.g. C2026Q2")
    parser.add_argument("--end-quarter", required=True, help="Quarter format CYYYYQn, e.g. C2026Q3")
    parser.add_argument(
        "--reconcile-quarter",
        default=None,
        help="Optional quarter to reconcile against latest AUCUNITS snapshot, e.g. C2026Q2",
    )
    parser.add_argument(
        "--output-dir",
        default="data/derived/irsr",
        help="Directory for reconstructed output files.",
    )
    args = parser.parse_args()

    fetcher = HistoricalDataFetcher()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dispatch_files = fetcher.fetch_dispatch_irsr_range(args.start_quarter, args.end_quarter)
    if not dispatch_files:
        print("No Dispatch_IRSR files found for requested quarter range.")
        return

    quarterly_df = fetcher.reconstruct_irsr_quarterly(dispatch_files)
    quarter_path = output_dir / f"dispatch_quarterly_{args.start_quarter}_{args.end_quarter}.csv"
    quarterly_df.to_csv(quarter_path, index=False)

    print(f"Dispatch files processed: {len(dispatch_files)}")
    print(f"Quarterly rows: {len(quarterly_df)}")
    print(f"Saved: {quarter_path}")

    if args.reconcile_quarter:
        auc_files = fetcher.list_auction_units_files()
        if auc_files:
            latest_auctions_file = auc_files[-1]
            auction_df = fetcher.load_auction_units_from_file(latest_auctions_file)
        else:
            local_dir = Path("data/raw/aemo/auction_units")
            local_files = sorted(local_dir.glob("AUCUNITS_*.R*")) if local_dir.exists() else []
            if not local_files:
                print("No AUCUNITS files available for reconciliation.")
                return
            latest_local = local_files[-1]
            auction_df = fetcher.parse_auction_units_text(latest_local.read_text())
        recon_df = fetcher.reconcile_dispatch_vs_auction_units(
            quarterly_df,
            auction_df,
            args.reconcile_quarter,
        )
        recon_path = output_dir / f"reconciliation_{args.reconcile_quarter}.csv"
        recon_df.to_csv(recon_path, index=False)
        print(f"Reconciliation rows: {len(recon_df)}")
        print(f"Saved: {recon_path}")


if __name__ == "__main__":
    main()