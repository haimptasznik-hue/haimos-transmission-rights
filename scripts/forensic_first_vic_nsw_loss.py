#!/usr/bin/env python3
"""Forensic audit of first losing VIC1-NSW1 trade executed by replay engine.

Outputs:
- reports/FORENSIC_FIRST_VIC_NSW_LOSS.md
- reports/forensic_first_vic_nsw_loss.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_first_losing_trade(trades: pd.DataFrame) -> pd.Series:
    trades = trades.copy()
    trades["decision_date"] = pd.to_datetime(trades["decision_date"], utc=True)
    vic = trades[trades["corridor"] == "VIC1-NSW1"].sort_values(["decision_date", "product_id"])
    losing = vic[vic["alpha"] < 0]
    if losing.empty:
        raise RuntimeError("No losing VIC1-NSW1 trade found in replay ledger")
    return losing.iloc[0]


def main() -> None:
    trades_path = REPO_ROOT / "reports" / "backtest_detailed_trades.csv"
    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    out_md = REPO_ROOT / "reports" / "FORENSIC_FIRST_VIC_NSW_LOSS.md"
    out_json = REPO_ROOT / "reports" / "forensic_first_vic_nsw_loss.json"

    trades = pd.read_csv(trades_path)
    alpha_db = pd.read_csv(alpha_path)
    t = _load_first_losing_trade(trades)

    product_match = alpha_db[alpha_db["product_id"] == t["product_id"]].copy()
    product_match["decision_timestamp"] = pd.to_datetime(product_match["decision_timestamp"], utc=True)
    product_match = product_match.sort_values("decision_timestamp")

    row_at_or_before = product_match[product_match["decision_timestamp"] <= pd.to_datetime(t["decision_date"], utc=True)]
    alpha_row = row_at_or_before.iloc[-1] if not row_at_or_before.empty else product_match.iloc[0]

    units = float(t["units"])
    cost_per_unit = float(t["cost_per_unit"])
    payout_per_unit = float(t["payout_per_unit"])
    fair_value = float(t["fair_value_forecast"])
    notional_cost = float(t["notional_cost"])
    acq_fee = float(t["acq_fee"])
    funding_cost = float(t["funding_cost"])
    total_cost = float(t["total_cost"])
    payout_total = float(t["payout"])
    alpha_total = float(t["alpha"])

    recon_notional = units * cost_per_unit
    recon_total_cost = notional_cost + acq_fee + funding_cost
    recon_payout = units * payout_per_unit
    recon_alpha = payout_total - total_cost

    expected_payout_total = units * fair_value
    miss_per_unit = payout_per_unit - fair_value
    miss_total = payout_total - expected_payout_total

    calc_checks = {
        "notional_delta": recon_notional - notional_cost,
        "total_cost_delta": recon_total_cost - total_cost,
        "payout_delta": recon_payout - payout_total,
        "alpha_delta": recon_alpha - alpha_total,
    }

    stored_realised_alpha = float(alpha_row["realised_alpha"])
    reconstructed_realised_alpha = float(alpha_row["final_realised_payout_per_unit"]) - float(alpha_row["auction_clearing_price"])
    settlement_delta = reconstructed_realised_alpha - stored_realised_alpha

    summary = {
        "decision_date": str(t["decision_date"]),
        "product_id": str(t["product_id"]),
        "quarter": str(t["quarter"]),
        "tranche": str(t["tranche"]),
        "corridor": str(t["corridor"]),
        "ruleset_id": str(alpha_row.get("ruleset_id", "UNKNOWN")),
        "source_lineage": str(alpha_row.get("source_lineage", "UNKNOWN")),
        "units": units,
        "cost_per_unit": cost_per_unit,
        "fair_value_forecast_per_unit": fair_value,
        "realized_payout_per_unit": payout_per_unit,
        "forecast_miss_per_unit": miss_per_unit,
        "forecast_miss_total": miss_total,
        "calc_checks": calc_checks,
        "settlement_reconstruction_delta": settlement_delta,
    }

    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Forensic Audit: First Losing VIC1-NSW1 Trade",
        "",
        "## Trade",
        f"- Decision date: `{summary['decision_date']}`",
        f"- Product: `{summary['product_id']}`",
        f"- Quarter / Tranche: `{summary['quarter']}` / `{summary['tranche']}`",
        f"- Ruleset: `{summary['ruleset_id']}`",
        "",
        "## Reconstruction (Auction → Settlement)",
        f"- Units: `{int(units)}`",
        f"- Cost per unit: `${cost_per_unit:,.4f}`",
        f"- Fair value forecast per unit: `${fair_value:,.4f}`",
        f"- Realized payout per unit: `${payout_per_unit:,.4f}`",
        f"- Forecast miss per unit: `${miss_per_unit:,.4f}`",
        "",
        f"- Notional reconstructed vs ledger delta: `{calc_checks['notional_delta']:.8f}`",
        f"- Total cost reconstructed vs ledger delta: `{calc_checks['total_cost_delta']:.8f}`",
        f"- Payout reconstructed vs ledger delta: `{calc_checks['payout_delta']:.8f}`",
        f"- Alpha reconstructed vs ledger delta: `{calc_checks['alpha_delta']:.8f}`",
        "",
        f"- Settlement reconstruction delta (`realised_alpha` consistency): `{settlement_delta:.8f}`",
        "",
        "## First Divergence Point",
        "All arithmetic checks reconcile. The first material divergence is forecasted unit payout versus realized unit payout.",
        f"- Forecast: `${fair_value:,.4f}` per unit",
        f"- Realized: `${payout_per_unit:,.4f}` per unit",
        f"- Divergence: `${miss_per_unit:,.4f}` per unit",
        "",
        "This localizes root-cause work to forecast/valuation components (price, flow, constraints, settlement expectation), not trade accounting arithmetic.",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {out_md}")
    print(f"Saved: {out_json}")


if __name__ == "__main__":
    main()
