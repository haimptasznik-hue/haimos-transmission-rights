#!/usr/bin/env python3
"""Iteration scenario runner built on trusted audit backtest logic.

Scenarios covered:
1) Baseline (no filters)
2) Exclude corridor(s)
3) Exclude quarter(s)
4) Corridor stop-loss kill switch

Outputs:
- reports/iteration2_scenarios.csv
- reports/iteration2_scenarios.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scenario:
    name: str
    exclude_corridors: tuple[str, ...] = ()
    exclude_quarters: tuple[str, ...] = ()
    corridor_stop_loss: float | None = None


def quarter_settlement_date(quarter: str) -> datetime:
    year = int(quarter[1:5])
    q = int(quarter[6])
    settle_month = q * 3 + 3
    settle_year = year
    if settle_month > 12:
        settle_month -= 12
        settle_year += 1
    if settle_month == 12:
        return datetime(settle_year, 12, 31, 23, 59, 59, tzinfo=UTC)
    next_month = settle_month + 1
    return datetime(settle_year, next_month, 1, 0, 0, 0, tzinfo=UTC) - timedelta(seconds=1)


def is_quarter_settled(quarter: str, as_of_date: datetime) -> bool:
    return as_of_date >= quarter_settlement_date(quarter)


def _corridor_from_product(product_id: str) -> str:
    parts = product_id.split(":")
    return parts[1] if len(parts) > 1 else "UNKNOWN"


def run_scenario(
    alpha_db_path: Path,
    scenario: Scenario,
    initial_capital: float = 1_000_000.0,
    acq_fee_pct: float = 0.001,
    funding_rate: float = 0.08,
    max_position_pct: float = 0.10,
) -> dict:
    df = pd.read_csv(alpha_db_path)
    df["decision_timestamp"] = pd.to_datetime(df["decision_timestamp"], utc=True)
    df["quarter"] = df["quarter"].astype(str)
    df["corridor"] = df["product_id"].apply(_corridor_from_product)

    today = datetime(2026, 7, 15, tzinfo=UTC)
    df["is_settled"] = df["quarter"].apply(lambda q: is_quarter_settled(q, today))

    if scenario.exclude_corridors:
        df = df[~df["corridor"].isin(scenario.exclude_corridors)].copy()
    if scenario.exclude_quarters:
        df = df[~df["quarter"].isin(scenario.exclude_quarters)].copy()

    available_capital = initial_capital
    locked_positions: list[dict] = []
    trades_ledger: list[dict] = []
    corridor_realized_alpha: dict[str, float] = {}

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 31, tzinfo=UTC)
    current = start

    while current <= end:
        cutoff_dt = datetime(current.year, current.month, 1, 0, 0, 0, tzinfo=UTC)

        now_settled = [lp for lp in locked_positions if cutoff_dt >= lp["settlement_dt"]]
        for lp in now_settled:
            available_capital += lp["alpha"]
            corridor = lp["corridor"]
            corridor_realized_alpha[corridor] = corridor_realized_alpha.get(corridor, 0.0) + lp["alpha"]
            locked_positions.remove(lp)

        frozen_df = df[(df["decision_timestamp"] <= cutoff_dt) & (df["is_settled"])].copy()
        if len(frozen_df) == 0:
            current = datetime(
                current.year if current.month < 12 else current.year + 1,
                1 if current.month == 12 else current.month + 1,
                1,
                tzinfo=UTC,
            )
            continue

        opportunities: list[dict] = []
        for quarter in sorted(frozen_df["quarter"].unique()):
            q_data = frozen_df[frozen_df["quarter"] == quarter].copy()
            q_settled = q_data[q_data["final_realised_payout_per_unit"].notna()].copy()
            if len(q_settled) == 0:
                continue

            q_settled["confidence"] = q_settled["fair_value_forecast"] / (q_settled["auction_clearing_price"] + 0.01)
            q_settled["score"] = np.abs(q_settled["confidence"] - 1.0)
            q_settled["should_bid"] = q_settled["fair_value_forecast"] > q_settled["auction_clearing_price"]

            for _, row in q_settled[q_settled["should_bid"]].iterrows():
                corridor = row["corridor"]
                if scenario.corridor_stop_loss is not None and corridor_realized_alpha.get(corridor, 0.0) <= scenario.corridor_stop_loss:
                    continue

                opportunities.append(
                    {
                        "quarter": quarter,
                        "product_id": row["product_id"],
                        "corridor": corridor,
                        "units": int(row["units_sold"]),
                        "cost_per_unit": float(row["auction_clearing_price"]),
                        "payout_per_unit": float(row["final_realised_payout_per_unit"]),
                        "score": float(row["score"]),
                        "settlement_dt": quarter_settlement_date(quarter),
                    }
                )

        opportunities.sort(key=lambda x: x["score"], reverse=True)

        for opp in opportunities:
            if available_capital <= 0:
                break

            max_for_position = available_capital * max_position_pct
            can_afford_units = int(max_for_position / opp["cost_per_unit"])
            if can_afford_units <= 0:
                continue

            units = min(can_afford_units, opp["units"])
            if units <= 0:
                continue

            notional = units * opp["cost_per_unit"]
            acq_fee = notional * acq_fee_pct
            funding_cost = notional * funding_rate * 0.25
            total_cost = notional + acq_fee + funding_cost
            if total_cost > available_capital:
                continue

            payout = units * opp["payout_per_unit"]
            alpha = payout - total_cost

            available_capital -= total_cost
            locked_positions.append(
                {
                    "alpha": alpha,
                    "settlement_dt": opp["settlement_dt"],
                    "corridor": opp["corridor"],
                }
            )

            trades_ledger.append(
                {
                    "decision_date": cutoff_dt.isoformat(),
                    "quarter": opp["quarter"],
                    "product_id": opp["product_id"],
                    "corridor": opp["corridor"],
                    "units": units,
                    "total_cost": total_cost,
                    "payout": payout,
                    "alpha": alpha,
                }
            )

        current = datetime(
            current.year if current.month < 12 else current.year + 1,
            1 if current.month == 12 else current.month + 1,
            1,
            tzinfo=UTC,
        )

    trades_df = pd.DataFrame(trades_ledger)
    total_alpha = float(trades_df["alpha"].sum()) if len(trades_df) > 0 else 0.0
    hit_rate = float((trades_df["alpha"] > 0).mean() * 100) if len(trades_df) > 0 else 0.0

    return {
        "scenario": scenario.name,
        "profit": total_alpha,
        "final_capital": initial_capital + total_alpha,
        "roi_pct": (total_alpha / initial_capital) * 100,
        "trades": int(len(trades_df)),
        "hit_rate_pct": hit_rate,
    }


def main() -> None:
    alpha_db_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        Scenario(name="baseline"),
        Scenario(name="exclude_vic1_nsw1", exclude_corridors=("VIC1-NSW1",)),
        Scenario(
            name="exclude_q4_problem_set",
            exclude_quarters=("C2020Q2", "C2021Q4", "C2022Q4", "C2023Q4", "C2024Q4", "C2025Q2"),
        ),
        Scenario(
            name="exclude_vic1_nsw1_and_q4_problem_set",
            exclude_corridors=("VIC1-NSW1",),
            exclude_quarters=("C2020Q2", "C2021Q4", "C2022Q4", "C2023Q4", "C2024Q4", "C2025Q2"),
        ),
        Scenario(name="corridor_stop_loss_-25m", corridor_stop_loss=-25_000_000.0),
        Scenario(name="corridor_stop_loss_-10m", corridor_stop_loss=-10_000_000.0),
    ]

    rows = [run_scenario(alpha_db_path, scenario) for scenario in scenarios]
    result_df = pd.DataFrame(rows).sort_values("profit", ascending=False)

    csv_path = reports_dir / "iteration2_scenarios.csv"
    md_path = reports_dir / "iteration2_scenarios.md"
    result_df.to_csv(csv_path, index=False)

    lines = [
        "# Iteration 2 Scenario Results",
        "",
        "All scenarios use the same capital-constrained allocation logic as the audit backtest.",
        "",
        "| Scenario | Profit | Final Capital | ROI | Trades | Hit Rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in result_df.iterrows():
        lines.append(
            f"| {row['scenario']} | ${row['profit']:,.0f} | ${row['final_capital']:,.0f} | {row['roi_pct']:.1f}% | {int(row['trades'])} | {row['hit_rate_pct']:.1f}% |"
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 80)
    print("ITERATION 2 SCENARIOS")
    print("=" * 80)
    print(result_df.to_string(index=False))
    print()
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
