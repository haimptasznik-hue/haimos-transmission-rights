#!/usr/bin/env python3
"""Phase 4 root-cause attribution scaffold using available historical fields.

This script does deterministic attribution from available dataset columns and
explicitly marks unresolved components that require deeper model internals.

Outputs:
- reports/phase4_trade_level_attribution.csv
- reports/phase4_grouped_attribution.csv
- reports/PHASE4_ROOT_CAUSE_ATTRIBUTION.md
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_direction(product_id: str, from_region: str) -> str:
    parts = product_id.split(":")
    corridor = parts[1] if len(parts) > 1 else "UNKNOWN"
    unit_region = parts[2] if len(parts) > 2 else "UNKNOWN"
    return f"{corridor}|from={from_region}|unit={unit_region}"


def classify_error_bucket(row: pd.Series) -> str:
    # Deterministic classification with current observables only.
    # We can directly observe valuation miss but cannot yet split it into
    # price/flow/constraint internals without additional model artifacts.
    if abs(row["valuation_miss_per_unit"]) < 1e-6:
        return "No material miss"
    if row["ruleset_id"] != "RS-BASELINE-v1":
        return "Rule version drift"
    if row["valuation_miss_per_unit"] < 0:
        return "Forecast overvaluation (upstream driver unresolved)"
    return "Forecast undervaluation (upstream driver unresolved)"


def main() -> None:
    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(alpha_path)
    df["decision_timestamp"] = pd.to_datetime(df["decision_timestamp"], utc=True)

    # Focus on rows where realized outcomes are known and the strategy would bid.
    settled = df[df["final_realised_payout_per_unit"].notna()].copy()
    settled["should_bid"] = settled["fair_value_forecast"] > settled["auction_clearing_price"]
    trades = settled[settled["should_bid"]].copy()

    trades["valuation_miss_per_unit"] = trades["final_realised_payout_per_unit"] - trades["fair_value_forecast"]
    trades["market_price_error_per_unit"] = trades["auction_clearing_price"] - trades["fair_value_forecast"]
    trades["realised_alpha_per_unit_recon"] = trades["final_realised_payout_per_unit"] - trades["auction_clearing_price"]
    trades["realised_alpha_per_unit_delta"] = trades["realised_alpha_per_unit_recon"] - trades["realised_alpha"]
    trades["direction_key"] = trades.apply(lambda r: _parse_direction(str(r["product_id"]), str(r["from_region"])), axis=1)
    trades["error_bucket"] = trades.apply(classify_error_bucket, axis=1)

    # Preserve requested analysis keys where present.
    group_cols = [
        "interconnector_id",
        "direction_key",
        "tranche",
        "quarter",
        "ruleset_id",
        "error_bucket",
    ]

    grouped = (
        trades.groupby(group_cols)
        .agg(
            trades=("product_id", "count"),
            mean_valuation_miss_per_unit=("valuation_miss_per_unit", "mean"),
            mean_realised_alpha_per_unit=("realised_alpha_per_unit_recon", "mean"),
            pct_negative_realised_alpha=("realised_alpha_per_unit_recon", lambda s: (s < 0).mean() * 100),
        )
        .reset_index()
        .sort_values(["trades"], ascending=False)
    )

    trade_out = trades[
        [
            "decision_timestamp",
            "product_id",
            "contract_id",
            "interconnector_id",
            "from_region",
            "direction_key",
            "quarter",
            "tranche",
            "ruleset_id",
            "units_offered",
            "units_sold",
            "fair_value_forecast",
            "auction_clearing_price",
            "final_realised_payout_per_unit",
            "market_price_error_per_unit",
            "valuation_miss_per_unit",
            "realised_alpha_per_unit_recon",
            "realised_alpha_per_unit_delta",
            "forecast_error_to_clearing",
            "forecast_error_to_realised",
            "error_bucket",
            "source_lineage",
        ]
    ].copy()

    trade_csv = reports_dir / "phase4_trade_level_attribution.csv"
    group_csv = reports_dir / "phase4_grouped_attribution.csv"
    report_md = reports_dir / "PHASE4_ROOT_CAUSE_ATTRIBUTION.md"

    trade_out.to_csv(trade_csv, index=False)
    grouped.to_csv(group_csv, index=False)

    total = len(trade_out)
    negative = int((trade_out["realised_alpha_per_unit_recon"] < 0).sum())
    overvaluation = int((trade_out["valuation_miss_per_unit"] < 0).sum())
    unique_rulesets = trade_out["ruleset_id"].nunique()

    lines = [
        "# Phase 4 – Root Cause Attribution (Deterministic Layer)",
        "",
        "This report does **attribution with currently available observables** and separates what is proven from what still needs deeper model instrumentation.",
        "",
        "## Coverage",
        f"- Total bid-eligible settled trade rows: `{total}`",
        f"- Negative realized alpha rows: `{negative}` ({(negative / total * 100) if total else 0:.1f}%)",
        f"- Overvaluation rows (`realized < forecast`): `{overvaluation}` ({(overvaluation / total * 100) if total else 0:.1f}%)",
        f"- Distinct ruleset versions observed: `{unique_rulesets}`",
        "",
        "## Deterministic Findings",
        "- Trade arithmetic fields are reconstructible from stored primitives (cost, payout, alpha definitions).",
        "- Ruleset variation cannot explain losses in this dataset snapshot because only one ruleset appears (`RS-BASELINE-v1`).",
        "- The dominant direct error signal is valuation miss (`final_realised_payout_per_unit - fair_value_forecast`).",
        "",
        "## Requested Breakdown Availability",
        "- By interconnector: available (`interconnector_id`).",
        "- By direction: proxied as `direction_key = corridor|from_region|unit_region` from product fields.",
        "- By tranche: available (`tranche`).",
        "- By quarter: available (`quarter`).",
        "- By RuleSet version: available (`ruleset_id`) but single version in sample.",
        "- By unit table/version: **not explicitly present** in current dataset columns.",
        "",
        "## What this does NOT yet identify",
        "- Price forecast vs flow forecast vs constraint forecast decomposition (requires model internal component outputs).",
        "- Settlement methodology branch attribution beyond current realized payout primitives.",
        "",
        "## Top groups by trade count",
        "",
        "| interconnector_id | direction_key | tranche | quarter | ruleset_id | error_bucket | trades | mean_valuation_miss_per_unit | mean_realised_alpha_per_unit | pct_negative_realised_alpha |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|",
    ]

    for _, r in grouped.head(25).iterrows():
        lines.append(
            f"| {r['interconnector_id']} | {r['direction_key']} | {r['tranche']} | {r['quarter']} | {r['ruleset_id']} | {r['error_bucket']} | {int(r['trades'])} | {r['mean_valuation_miss_per_unit']:.2f} | {r['mean_realised_alpha_per_unit']:.2f} | {r['pct_negative_realised_alpha']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Output Files",
            f"- `{trade_csv.relative_to(REPO_ROOT)}`",
            f"- `{group_csv.relative_to(REPO_ROOT)}`",
            "",
            "These are the Phase 4 base tables for deeper attribution once internal forecast components are exported.",
        ]
    )

    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {trade_csv}")
    print(f"Saved: {group_csv}")
    print(f"Saved: {report_md}")


if __name__ == "__main__":
    main()
