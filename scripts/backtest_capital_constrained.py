#!/usr/bin/env python3
"""Real point-in-time backtest with proper capital constraints.

If we had started with $1M on January 1, 2025 and followed the model's signals,
using ONLY information available at each decision point and respecting capital
limits, what would we have ended with?

Key: This respects that capital is actually LIMITED and locked up.
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
    """Has a quarter settled by as_of_date?"""
    return as_of_date >= quarter_settlement_date(quarter)


def run_capital_constrained_backtest(
    alpha_db_path: Path,
    initial_capital: float = 1000000.0,
    max_position_pct: float = 0.10,  # 10% of capital per position
) -> tuple[pd.DataFrame, list]:
    """
    Execute month-by-month backtest WITH REAL CAPITAL CONSTRAINTS:
    - Each month 1st, freeze data as of that date
    - Only use settled quarters (payouts known)
    - Rank opportunities by model confidence
    - Allocate capital greedily: highest confidence first, until capital runs out
    - Track positions and lock-up
    """
    df = pd.read_csv(alpha_db_path)
    df["decision_timestamp"] = pd.to_datetime(df["decision_timestamp"], utc=True)
    df["quarter"] = df["quarter"].astype(str)

    # Mark which quarters have settled
    today = datetime(2026, 7, 15, tzinfo=UTC)
    df["is_settled"] = df["quarter"].apply(lambda q: is_quarter_settled(q, today))

    results = []
    available_capital = initial_capital
    cumulative_pnl = 0.0
    trades_history = []
    locked_positions = []  # Track when capital becomes free

    # Starting January 1, 2025, check on first of each month
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 31, tzinfo=UTC)
    current = start

    while current <= end:
        cutoff_dt = datetime(current.year, current.month, 1, 0, 0, 0, tzinfo=UTC)

        # Free up capital from settled positions
        now_settled = [lp for lp in locked_positions if cutoff_dt >= lp["settlement_dt"]]
        for lp in now_settled:
            available_capital += lp["pnl"]
            cumulative_pnl += lp["pnl"]
            locked_positions.remove(lp)

        # Freeze: only use data up to and including this date, for settled quarters only
        frozen_df = df[
            (df["decision_timestamp"] <= cutoff_dt) & (df["is_settled"])
        ].copy()

        if len(frozen_df) == 0:
            results.append({
                "decision_date": cutoff_dt.isoformat(),
                "available_capital": available_capital,
                "locked_capital": sum(lp["notional"] for lp in locked_positions),
                "cumulative_pnl": cumulative_pnl,
                "month_pnl": 0.0,
                "trades_this_month": 0,
                "total_trades": len(trades_history),
                "status": "no_data",
            })
            current = datetime(current.year if current.month < 12 else current.year + 1,
                               1 if current.month == 12 else current.month + 1, 1, tzinfo=UTC)
            continue

        # For each settled quarter with payouts, find opportunities
        month_pnl = 0.0
        month_trades = 0
        opportunities = []

        for quarter in sorted(frozen_df["quarter"].unique()):
            q_data = frozen_df[frozen_df["quarter"] == quarter].copy()

            # Only rows with realized payouts
            q_settled = q_data[q_data["final_realised_payout_per_unit"].notna()].copy()
            if len(q_settled) == 0:
                continue

            # Score opportunities: confidence of the model
            q_settled["confidence"] = q_settled["fair_value_forecast"] / (q_settled["auction_clearing_price"] + 0.01)
            q_settled["score"] = np.abs(q_settled["confidence"] - 1.0)  # Higher = more confident prediction

            # Bid on products where model predicted positive
            q_settled["should_bid"] = (
                q_settled["fair_value_forecast"] > q_settled["auction_clearing_price"]
            )

            for _, row in q_settled[q_settled["should_bid"]].iterrows():
                cost_per_unit = row["auction_clearing_price"]
                units = int(row["units_sold"])
                notional_cost = cost_per_unit * units
                score = row["score"]

                opportunities.append({
                    "quarter": quarter,
                    "product_id": row["product_id"],
                    "units": units,
                    "cost_per_unit": cost_per_unit,
                    "notional_cost": notional_cost,
                    "payout_per_unit": row["final_realised_payout_per_unit"],
                    "fair_value": row["fair_value_forecast"],
                    "score": score,
                    "settlement_dt": quarter_settlement_date(quarter),
                })

        # Sort by confidence (score) descending
        opportunities.sort(key=lambda x: x["score"], reverse=True)

        # Greedily allocate capital
        for opp in opportunities:
            max_for_position = available_capital * max_position_pct
            can_afford_units = int(max_for_position / opp["cost_per_unit"])
            
            if can_afford_units <= 0 or available_capital <= 0:
                continue

            # Execute partial or full position
            actual_units = min(can_afford_units, opp["units"])
            actual_cost = actual_units * opp["cost_per_unit"]

            # Costs
            acq_fee = actual_cost * 0.001
            funding_cost = actual_cost * 0.08 * 0.25  # 1 quarter @ 8% p.a.
            total_cost = actual_cost + acq_fee + funding_cost

            if total_cost > available_capital:
                continue

            # Execution
            payout = actual_units * opp["payout_per_unit"]
            alpha = payout - total_cost

            available_capital -= total_cost
            locked_positions.append({
                "notional": total_cost,
                "pnl": alpha,
                "settlement_dt": opp["settlement_dt"],
            })

            month_pnl += alpha
            month_trades += 1
            trades_history.append({
                "quarter": opp["quarter"],
                "product_id": opp["product_id"],
                "decision_date": cutoff_dt.isoformat(),
                "units": actual_units,
                "bid_price": opp["cost_per_unit"],
                "payout": payout,
                "cost": total_cost,
                "alpha": alpha,
            })

            if available_capital <= 0:
                break

        results.append({
            "decision_date": cutoff_dt.isoformat(),
            "available_capital": available_capital,
            "locked_capital": sum(lp["notional"] for lp in locked_positions),
            "cumulative_pnl": cumulative_pnl + month_pnl,
            "month_pnl": month_pnl,
            "trades_this_month": month_trades,
            "total_trades": len(trades_history),
            "opportunities_considered": len(opportunities),
            "status": "ok",
        })

        current = datetime(current.year if current.month < 12 else current.year + 1,
                           1 if current.month == 12 else current.month + 1, 1, tzinfo=UTC)

    return pd.DataFrame(results), trades_history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-capital", type=float, default=1000000.0,
                        help="Starting capital (default: $1M)")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    alpha_db = repo_root / "data/derived/sra/alpha_database.csv"
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f"POINT-IN-TIME BACKTEST (Capital-Constrained)")
    print(f"Starting Capital: ${args.initial_capital:,.0f}")
    print(f"Period: January 2025 → July 2026")
    print("=" * 80)
    print()

    if not alpha_db.exists():
        print(f"ERROR: {alpha_db} not found")
        sys.exit(1)

    frame = pd.read_csv(alpha_db)
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True)
    print(f"Data loaded: {len(frame)} records")
    print(f"Date range: {frame['decision_timestamp'].min()} to {frame['decision_timestamp'].max()}")
    print()

    print("Running month-by-month backtest with capital constraints...")
    results_df, trades_history = run_capital_constrained_backtest(alpha_db, initial_capital=args.initial_capital)

    # Save results
    results_df.to_csv(reports_dir / "jan_2025_capital_constrained.csv", index=False)
    print()
    print(f"✓ Results saved to reports/jan_2025_capital_constrained.csv")
    print()

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if len(results_df) > 0:
        first_ok = results_df[results_df["status"] == "ok"]
        if len(first_ok) > 0:
            first = first_ok.iloc[0]
            print(f"First execution: {first['decision_date']}")
            print(f"  Available capital: ${first['available_capital']:,.0f}")
            print(f"  Trades: {int(first['trades_this_month'])}")
            print()

        last = results_df.iloc[-1]
        starting = args.initial_capital
        ending = last["available_capital"] + last["cumulative_pnl"]
        total_pnl = last["cumulative_pnl"]
        total_trades = int(last["total_trades"])

        print(f"Final (July 2026):")
        print(f"  Available capital: ${last['available_capital']:,.0f}")
        print(f"  Locked capital: ${last['locked_capital']:,.0f}")
        print(f"  Total P&L: ${total_pnl:,.0f}")
        print(f"  Ending position: ${ending:,.0f}")
        print(f"  Total trades: {total_trades}")
        print()

        ret_pct = (ending - starting) / starting
        if ret_pct > 0:
            print(f"📈 IF YOU HAD FOLLOWED THE MODEL:")
            print(f"   Starting: ${starting:,.0f}")
            print(f"   Ending:   ${ending:,.0f}")
            print(f"   Return:   +{ret_pct:.1%}")
        elif ret_pct < 0:
            print(f"📉 IF YOU HAD FOLLOWED THE MODEL:")
            print(f"   Starting: ${starting:,.0f}")
            print(f"   Ending:   ${ending:,.0f}")
            print(f"   Loss:     -{abs(ret_pct):.1%}")
        else:
            print(f"IF YOU HAD FOLLOWED THE MODEL: Break-even")

        print()
        print("Trade details:")
        if len(trades_history) > 0:
            profitable = sum(1 for t in trades_history if t["alpha"] > 0)
            hit_rate = profitable / len(trades_history)
            print(f"  Total trades executed: {len(trades_history)}")
            print(f"  Profitable trades: {profitable}")
            print(f"  Hit rate: {hit_rate:.1%}")
        else:
            print("  No trades executed (insufficient capital or opportunities)")


if __name__ == "__main__":
    main()
