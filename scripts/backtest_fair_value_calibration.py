from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

backtest_module = importlib.import_module("transmission_rights.services.fair_value_backtest")
backtest_with_calibration = backtest_module.backtest_with_calibration
backtest_with_quarter_calibration = backtest_module.backtest_with_quarter_calibration
summarize_by_quarter = backtest_module.summarize_by_quarter
load_backtest_rows = backtest_module.load_backtest_rows
calibration_grid_scores = backtest_module.calibration_grid_scores


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back-test and calibrate fair-value discounts against historical AEMO data."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("data/raw/aemo/sra_results"),
        help="Directory containing historical SRA_Results CSV files.",
    )
    parser.add_argument(
        "--dispatch-quarterly-csv",
        type=Path,
        default=Path("data/derived/irsr/dispatch_quarterly_C2025Q3_C2026Q2.csv"),
        help="Quarterly Dispatch_IRSR reconstruction CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/derived/fair_value"),
        help="Directory to write backtest outputs.",
    )
    parser.add_argument(
        "--risk-grid",
        type=str,
        default="0.00,0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.10",
        help="Comma-separated risk discount grid.",
    )
    parser.add_argument(
        "--liquidity-grid",
        type=str,
        default="0.00,0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.10",
        help="Comma-separated liquidity discount grid.",
    )
    parser.add_argument(
        "--payout-weight",
        type=float,
        default=0.7,
        help="Weight for payout-per-unit MAPE in calibration objective.",
    )
    parser.add_argument(
        "--price-weight",
        type=float,
        default=0.3,
        help="Weight for clearing-price MAPE in calibration objective.",
    )
    parser.add_argument(
        "--calibration-scope",
        type=str,
        choices=["global", "quarter"],
        default="global",
        help="Calibrate one global parameter set or a separate set per quarter.",
    )
    parser.add_argument(
        "--ape-cap",
        type=float,
        default=300.0,
        help="Optional cap for absolute percentage errors (APE). Set negative to disable cap.",
    )
    parser.add_argument(
        "--quarter-balanced-weighting",
        action="store_true",
        help="Balance calibration objective so each quarter contributes equally in global mode.",
    )
    parser.add_argument(
        "--min-total-discount",
        type=float,
        default=0.0,
        help="Minimum model+risk discount floor for calibration objective.",
    )
    parser.add_argument(
        "--discount-penalty-strength",
        type=float,
        default=100.0,
        help="Penalty strength per unit of discount shortfall below minimum total discount.",
    )
    args = parser.parse_args()

    risk_grid = [float(value) for value in args.risk_grid.split(",") if value.strip()]
    liquidity_grid = [float(value) for value in args.liquidity_grid.split(",") if value.strip()]
    ape_cap = args.ape_cap if args.ape_cap >= 0 else None

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "fair_value_backtest_rows.csv"
    summary_path = args.output_dir / "fair_value_calibration_summary.json"
    quarter_path = args.output_dir / "fair_value_backtest_by_quarter.csv"
    quarter_calibration_path = args.output_dir / "fair_value_calibration_by_quarter.csv"
    diagnostics_path = args.output_dir / "fair_value_calibration_diagnostics.csv"
    diagnostics_written = False

    if args.calibration_scope == "quarter":
        result_df, calibration_df = backtest_with_quarter_calibration(
            results_dir=args.results_dir,
            dispatch_quarterly_csv=args.dispatch_quarterly_csv,
            model_risk_discounts=risk_grid,
            liquidity_discounts=liquidity_grid,
            payout_error_weight=args.payout_weight,
            clearing_price_error_weight=args.price_weight,
            ape_cap=ape_cap,
            quarter_balanced_weighting=args.quarter_balanced_weighting,
            min_total_discount=args.min_total_discount,
            discount_penalty_strength=args.discount_penalty_strength,
        )
        calibration_df.to_csv(quarter_calibration_path, index=False)

        total_rows = int(calibration_df["rows"].sum()) if not calibration_df.empty else 0
        if total_rows > 0:
            mape_actual = float(
                (calibration_df["mape_actual_per_unit"] * calibration_df["rows"]).sum()
                / total_rows
            )
            mape_price = float(
                (calibration_df["mape_clearing_price"] * calibration_df["rows"]).sum()
                / total_rows
            )
            weighted_score = float(
                (calibration_df["weighted_score"] * calibration_df["rows"]).sum()
                / total_rows
            )
        else:
            mape_actual = 0.0
            mape_price = 0.0
            weighted_score = 0.0

        calibration_summary = {
            "calibration_scope": "quarter",
            "rows_backtested": int(len(result_df)),
            "quarters": int(len(calibration_df)),
            "payout_error_weight": float(args.payout_weight),
            "clearing_price_error_weight": float(args.price_weight),
            "ape_cap": ape_cap,
            "quarter_balanced_weighting": bool(args.quarter_balanced_weighting),
            "min_total_discount": float(args.min_total_discount),
            "discount_penalty_strength": float(args.discount_penalty_strength),
            "mape_actual_per_unit_mean": mape_actual,
            "mape_clearing_price_mean": mape_price,
            "weighted_score_mean": weighted_score,
        }

        backtest_df = load_backtest_rows(args.results_dir, args.dispatch_quarterly_csv)
        diagnostics_frames: list[pd.DataFrame] = []
        for quarter, quarter_df in backtest_df.groupby("quarter", as_index=False):
            grid_df = calibration_grid_scores(
                backtest_df=quarter_df,
                model_risk_discounts=risk_grid,
                liquidity_discounts=liquidity_grid,
                payout_error_weight=args.payout_weight,
                clearing_price_error_weight=args.price_weight,
                ape_cap=ape_cap,
                quarter_balanced_weighting=args.quarter_balanced_weighting,
                min_total_discount=args.min_total_discount,
                discount_penalty_strength=args.discount_penalty_strength,
            )
            if not grid_df.empty:
                grid_df.insert(0, "quarter", str(quarter))
                diagnostics_frames.append(grid_df)
        if diagnostics_frames:
            pd.concat(diagnostics_frames, ignore_index=True).to_csv(diagnostics_path, index=False)
            diagnostics_written = True
    else:
        result_df, calibration = backtest_with_calibration(
            results_dir=args.results_dir,
            dispatch_quarterly_csv=args.dispatch_quarterly_csv,
            model_risk_discounts=risk_grid,
            liquidity_discounts=liquidity_grid,
            payout_error_weight=args.payout_weight,
            clearing_price_error_weight=args.price_weight,
            ape_cap=ape_cap,
            quarter_balanced_weighting=args.quarter_balanced_weighting,
            min_total_discount=args.min_total_discount,
            discount_penalty_strength=args.discount_penalty_strength,
        )
        calibration_summary = calibration.to_dict()
        calibration_summary["calibration_scope"] = "global"
        calibration_summary["min_total_discount"] = float(args.min_total_discount)
        calibration_summary["discount_penalty_strength"] = float(args.discount_penalty_strength)

        backtest_df = load_backtest_rows(args.results_dir, args.dispatch_quarterly_csv)
        diagnostics_df = calibration_grid_scores(
            backtest_df=backtest_df,
            model_risk_discounts=risk_grid,
            liquidity_discounts=liquidity_grid,
            payout_error_weight=args.payout_weight,
            clearing_price_error_weight=args.price_weight,
            ape_cap=ape_cap,
            quarter_balanced_weighting=args.quarter_balanced_weighting,
            min_total_discount=args.min_total_discount,
            discount_penalty_strength=args.discount_penalty_strength,
        )
        if not diagnostics_df.empty:
            diagnostics_df.to_csv(diagnostics_path, index=False)
            diagnostics_written = True

    result_df.to_csv(result_path, index=False)
    summarize_by_quarter(result_df).to_csv(quarter_path, index=False)
    summary_path.write_text(json.dumps(calibration_summary, indent=2), encoding="utf-8")

    print(f"Rows backtested: {len(result_df)}")
    print(f"Calibration scope: {args.calibration_scope}")
    print(f"APE cap: {'none' if ape_cap is None else f'{ape_cap:.2f}%'}")
    print(f"Quarter-balanced weighting: {args.quarter_balanced_weighting}")
    print(f"Minimum total discount: {args.min_total_discount:.2%}")
    print(f"Discount penalty strength: {args.discount_penalty_strength:.2f}")
    if args.calibration_scope == "quarter":
        print(f"Objective weights: payout={args.payout_weight:.1%}, price={args.price_weight:.1%}")
        print(f"Mean MAPE actual per unit: {calibration_summary['mape_actual_per_unit_mean']:.2f}%")
        print(f"Mean MAPE clearing price: {calibration_summary['mape_clearing_price_mean']:.2f}%")
        print(f"Mean weighted score: {calibration_summary['weighted_score_mean']:.2f}%")
        print(f"Quarter calibrations: {calibration_summary['quarters']}")
        print(f"Saved: {quarter_calibration_path}")
    else:
        print(f"Best model risk discount: {calibration.model_risk_discount:.2%}")
        print(f"Best liquidity discount: {calibration.liquidity_discount:.2%}")
        print(
            "Objective weights: "
            f"payout={calibration.payout_error_weight:.1%}, "
            f"price={calibration.clearing_price_error_weight:.1%}"
        )
        print(f"MAPE actual per unit: {calibration.mape_actual_per_unit:.2f}%")
        print(f"MAPE clearing price: {calibration.mape_clearing_price:.2f}%")
        print(f"Weighted score: {calibration.weighted_score:.2f}%")
    print(f"Saved: {result_path}")
    print(f"Saved: {quarter_path}")
    print(f"Saved: {summary_path}")
    if diagnostics_written:
        print(f"Saved: {diagnostics_path}")


if __name__ == "__main__":
    main()
