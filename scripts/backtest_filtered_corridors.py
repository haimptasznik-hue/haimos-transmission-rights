#!/usr/bin/env python3
"""Backtest with corridor/quarter filtering to isolate edge sources.

Answers:
1. What happens if we exclude the losing VIC1-NSW1 corridor?
2. What happens if we exclude Q4 quarters (systematically 0% hit rate)?
3. How much profit comes from each source independently?
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]


def quarter_settlement_date(quarter: str) -> datetime:
    """When does a quarter settle? 3 months after quarter end."""
    year = int(quarter[1:5])
    q = int(quarter[6])
    settle_month = q * 3 + 3
    settle_year = year
    if settle_month > 12:
        settle_month -= 12
        settle_year += 1
    if settle_month == 12:
        settle_dt = datetime(settle_year, 12, 31, 23, 59, 59, tzinfo=UTC)
    else:
        next_month = settle_month + 1
        settle_dt = datetime(settle_year, next_month, 1, 0, 0, 0, tzinfo=UTC) - timedelta(seconds=1)
    return settle_dt


def is_quarter_settled(quarter: str, as_of_date: datetime) -> bool:
    """Is quarter data available (settled)?"""
    return as_of_date >= quarter_settlement_date(quarter)


def run_filtered_backtest(
    alpha_db_path: Path,
    initial_capital: float = 1000000.0,
    acq_fee_pct: float = 0.001,
    funding_rate: float = 0.08,
    exclude_corridors: list[str] | None = None,
    exclude_quarters: list[str] | None = None,
) -> dict:
    """
    Run backtest with optional corridor/quarter filters.
    
    Args:
        alpha_db_path: Path to alpha database CSV
        initial_capital: Starting capital
        acq_fee_pct: Acquisition fee as % of notional
        funding_rate: Annual funding rate
        exclude_corridors: List of corridor names to exclude (e.g., ["VIC1-NSW1"])
        exclude_quarters: List of quarter codes to exclude (e.g., ["C2024Q4"])
    
    Returns:
        dict with keys: profit, trades, hit_rate, capital_progression, trades_detail
    """
    df = pd.read_csv(alpha_db_path)
    df["decision_timestamp"] = pd.to_datetime(df["decision_timestamp"], utc=True)
    df["quarter"] = df["quarter"].astype(str)

    # Extract corridor from product_id (format: CYYYYQX:CORRIDOR:...)
    df["corridor"] = df["product_id"].str.split(":").str[1]
    df["quarter_code"] = df["quarter"]

    # Apply filters
    if exclude_corridors:
        print(f"Excluding corridors: {exclude_corridors}")
        df = df[~df["corridor"].isin(exclude_corridors)].copy()
        print(f"  → {len(df)} trades remain")

    if exclude_quarters:
        print(f"Excluding quarters: {exclude_quarters}")
        df = df[~df["quarter_code"].isin(exclude_quarters)].copy()
        print(f"  → {len(df)} trades remain")

    today = datetime(2026, 7, 15, tzinfo=UTC)
    df["is_settled"] = df["quarter"].apply(lambda q: is_quarter_settled(q, today))

    results = []
    trades_detail = []
    
    available_capital = initial_capital
    cumulative_pnl = 0.0
    locked_positions = []

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 31, tzinfo=UTC)
    current = start
    total_trades = 0
    total_wins = 0

    while current <= end:
        cutoff_dt = datetime(current.year, current.month, 1, 0, 0, 0, tzinfo=UTC)

        # Free up capital from settled positions
        now_settled = [lp for lp in locked_positions if cutoff_dt >= lp["settlement_dt"]]
        for lp in now_settled:
            available_capital += lp["pnl"]
            cumulative_pnl += lp["pnl"]
            locked_positions.remove(lp)

        frozen_df = df[
            (df["decision_timestamp"] <= cutoff_dt) & (df["is_settled"])
        ].copy()

        if len(frozen_df) == 0:
            current = datetime(current.year if current.month < 12 else current.year + 1,
                               1 if current.month == 12 else current.month + 1, 1, tzinfo=UTC)
            continue

        month_pnl = 0.0
        month_trades = 0

        # Collect opportunities from settled quarters
        opportunities = []
        for quarter in sorted(frozen_df["quarter"].unique()):
            q_data = frozen_df[frozen_df["quarter"] == quarter].copy()
            q_settled = q_data[q_data["final_realised_payout_per_unit"].notna()].copy()
            if len(q_settled) == 0:
                continue

            q_settled["confidence"] = q_settled["fair_value_forecast"] / (q_settled["auction_clearing_price"] + 0.01)
            q_settled["score"] = np.abs(q_settled["confidence"] - 1.0)
            q_settled["should_bid"] = q_settled["fair_value_forecast"] > q_settled["auction_clearing_price"]

            for _, row in q_settled[q_settled["should_bid"]].iterrows():
                cost_per_unit = row["auction_clearing_price"]
                units = int(row["units_sold"])  # Use actual units sold
                notional_cost = cost_per_unit * units
                score = row["score"]

                opportunities.append({
                    "row": row,
                    "quarter": quarter,
                    "units": units,
                    "cost_per_unit": cost_per_unit,
                    "notional_cost": notional_cost,
                    "score": score,
                    "settlement_dt": quarter_settlement_date(quarter),
                })

        # Sort by score (confidence) descending and allocate greedily
        opportunities.sort(key=lambda x: x["score"], reverse=True)

        for opp in opportunities:
            if available_capital <= 0:
                break

            # Position sizing: max 10% of available capital
            max_for_position = available_capital * 0.10
            can_afford_units = int(max_for_position / opp["cost_per_unit"])
            
            if can_afford_units <= 0:
                continue

            # Execute: take min of what we can afford and what's available
            actual_units = min(can_afford_units, opp["units"])
            actual_cost = actual_units * opp["cost_per_unit"]

            # Costs: acquisition fee + funding cost
            acq_fee = actual_cost * acq_fee_pct
            funding_cost = actual_cost * funding_rate * 0.25  # 1 quarter @ 8% p.a.
            total_cost = actual_cost + acq_fee + funding_cost

            if total_cost > available_capital:
                continue

            # Calculate payout and alpha
            row = opp["row"]
            payout = actual_units * row["final_realised_payout_per_unit"]
            alpha = payout - total_cost
            is_win = alpha > 0

            # Execute trade
            available_capital -= total_cost
            cumulative_pnl += alpha
            month_pnl += alpha
            month_trades += 1
            total_trades += 1
            if is_win:
                total_wins += 1

            locked_positions.append({
                "pnl": alpha,
                "settlement_dt": opp["settlement_dt"],
            })

            trades_detail.append({
                "decision_date": cutoff_dt.date(),
                "quarter": opp["quarter"],
                "product_id": row["product_id"],
                "corridor": row["corridor"],
                "units": actual_units,
                "clearing_price": opp["cost_per_unit"],
                "fair_value": row["fair_value_forecast"],
                "notional": actual_cost,
                "acq_fee": acq_fee,
                "funding_cost": funding_cost,
                "total_cost": total_cost,
                "realized_payout": payout,
                "alpha": alpha,
                "is_win": is_win,
            })

        results.append({
            "month": cutoff_dt,
            "available_capital": available_capital,
            "cumulative_pnl": cumulative_pnl,
            "month_pnl": month_pnl,
            "month_trades": month_trades,
        })

        current = datetime(current.year if current.month < 12 else current.year + 1,
                           1 if current.month == 12 else current.month + 1, 1, tzinfo=UTC)

    hit_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    final_capital = initial_capital + cumulative_pnl

    return {
        "profit": cumulative_pnl,
        "final_capital": final_capital,
        "roi": (cumulative_pnl / initial_capital) * 100,
        "trades": total_trades,
        "wins": total_wins,
        "hit_rate": hit_rate,
        "results": results,
        "trades_detail": trades_detail,
    }


def main():
    parser = argparse.ArgumentParser(description="Run filtered backtest")
    parser.add_argument("--capital", type=float, default=1000000, help="Initial capital")
    parser.add_argument("--exclude-corridors", type=str, default="", help="Comma-separated list of corridors to exclude")
    parser.add_argument("--exclude-quarters", type=str, default="", help="Comma-separated list of quarters to exclude")
    parser.add_argument("--output-csv", type=str, default="", help="Output CSV file for trade details")
    args = parser.parse_args()

    alpha_db = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    if not alpha_db.exists():
        print(f"Error: {alpha_db} not found")
        sys.exit(1)

    exclude_corridors = [c.strip() for c in args.exclude_corridors.split(",") if c.strip()]
    exclude_quarters = [q.strip() for q in args.exclude_quarters.split(",") if q.strip()]

    print("=" * 80)
    print("FILTERED BACKTEST")
    print("=" * 80)
    print(f"Initial capital: ${args.capital:,.0f}")
    if exclude_corridors:
        print(f"Excluding corridors: {exclude_corridors}")
    if exclude_quarters:
        print(f"Excluding quarters: {exclude_quarters}")
    print()

    result = run_filtered_backtest(
        alpha_db,
        initial_capital=args.capital,
        exclude_corridors=exclude_corridors,
        exclude_quarters=exclude_quarters,
    )

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total Profit:        ${result['profit']:>15,.0f}")
    print(f"Final Capital:       ${result['final_capital']:>15,.0f}")
    print(f"ROI:                 {result['roi']:>15,.1f}%")
    print(f"Total Trades:        {result['trades']:>15,}")
    print(f"Winning Trades:      {result['wins']:>15,}")
    print(f"Hit Rate:            {result['hit_rate']:>15,.1f}%")
    print()

    if args.output_csv:
        trades_df = pd.DataFrame(result["trades_detail"])
        trades_df.to_csv(args.output_csv, index=False)
        print(f"✅ Trade details saved to: {args.output_csv}")

    return result


if __name__ == "__main__":
    main()
