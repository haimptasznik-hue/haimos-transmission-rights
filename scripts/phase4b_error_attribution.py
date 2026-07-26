#!/usr/bin/env python3
"""Phase 4B - Forecast Error Attribution Engine.

Requirements implemented:
- Accept component-level forecasts + realized outcomes for:
  regional prices, interconnector flows, constraints,
  settlement residue, unit payout
- Compare forecast components vs realized outcomes
- Attribute trade forecast error into:
  price, flow, constraint, settlement-model,
  unit-table/rules, optimiser/execution, UNATTRIBUTED
- Produce absolute AUD and percentage contribution
- Group outputs by corridor, direction, quarter, tranche, ruleset,
  winning vs losing trades
- Add confidence/data-quality flags
- Keep unexplained residual visible in UNATTRIBUTED
- Generate trade-level CSV, grouped CSV, forensic markdown,
  ranked model-improvement list

Usage:
  python scripts/phase4b_error_attribution.py
  python scripts/phase4b_error_attribution.py --component-exports data/derived/sra/component_exports.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

CATEGORIES = [
    "price_error",
    "flow_error",
    "constraint_error",
    "settlement_model_error",
    "unit_table_rules_error",
    "optimiser_execution_error",
]

CATEGORY_TO_EXPORT_COL = {
    "price_error": "price_error_aud",
    "flow_error": "flow_error_aud",
    "constraint_error": "constraint_error_aud",
    "settlement_model_error": "settlement_model_error_aud",
    "unit_table_rules_error": "unit_table_rules_error_aud",
    "optimiser_execution_error": "optimiser_execution_error_aud",
}

COMPONENT_SPECS = {
    "price_error": {
        "forecast_cols": ["regional_price_forecast", "price_forecast"],
        "actual_cols": ["regional_price_actual", "price_actual"],
        "sens_cols": ["regional_price_to_payout_sensitivity", "price_to_payout_sensitivity"],
    },
    "flow_error": {
        "forecast_cols": ["interconnector_flow_forecast", "flow_forecast"],
        "actual_cols": ["interconnector_flow_actual", "flow_actual"],
        "sens_cols": ["flow_to_payout_sensitivity"],
    },
    "constraint_error": {
        "forecast_cols": ["constraint_forecast"],
        "actual_cols": ["constraint_actual"],
        "sens_cols": ["constraint_to_payout_sensitivity"],
    },
    "settlement_model_error": {
        "forecast_cols": ["settlement_residue_forecast"],
        "actual_cols": ["settlement_residue_actual"],
        "sens_cols": ["settlement_residue_to_payout_sensitivity"],
    },
    "optimiser_execution_error": {
        "forecast_cols": ["execution_price_forecast", "optimizer_execution_forecast"],
        "actual_cols": ["execution_price_actual", "optimizer_execution_actual"],
        "sens_cols": ["execution_to_payout_sensitivity"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 4B Forecast Error Attribution")
    parser.add_argument(
        "--component-exports",
        type=str,
        default="",
        help="Optional CSV with component-level forecasts/actuals and optional *_error_aud fields",
    )
    parser.add_argument(
        "--top-losses",
        type=int,
        default=25,
        help="Number of largest losses in forensic report",
    )
    return parser.parse_args()


def _find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns and df[col].notna().any():
            return col
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _parse_direction(product_id: str, from_region: str) -> str:
    parts = str(product_id).split(":")
    corridor = parts[1] if len(parts) > 1 else "UNKNOWN"
    unit_region = parts[2] if len(parts) > 2 else "UNKNOWN"
    return f"{corridor}|from={from_region}|unit={unit_region}"


def load_base_trades() -> pd.DataFrame:
    trades = pd.read_csv(REPO_ROOT / "reports" / "backtest_detailed_trades.csv")
    alpha = pd.read_csv(REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv")

    trades["decision_date"] = pd.to_datetime(trades["decision_date"], utc=True)
    alpha["decision_timestamp"] = pd.to_datetime(alpha["decision_timestamp"], utc=True)

    # Attach ruleset/interconnector/from_region by matching product and taking latest record <= decision_date.
    alpha = alpha.sort_values("decision_timestamp")
    meta_cols = [
        "product_id",
        "quarter",
        "tranche",
        "decision_timestamp",
        "interconnector_id",
        "from_region",
        "ruleset_id",
        "forecast_error_to_clearing",
        "forecast_error_to_realised",
        "source_lineage",
    ]
    alpha_meta = alpha[meta_cols].copy()

    out_rows = []
    grouped = alpha_meta.groupby(["product_id", "quarter", "tranche"], dropna=False)

    for _, t in trades.iterrows():
        key = (t["product_id"], t["quarter"], t["tranche"])
        if key in grouped.groups:
            sub = grouped.get_group(key)
            sub = sub[sub["decision_timestamp"] <= t["decision_date"]]
            if len(sub) == 0:
                sub = grouped.get_group(key)
            meta = sub.iloc[-1]
        else:
            meta = pd.Series({
                "interconnector_id": "UNKNOWN",
                "from_region": "UNKNOWN",
                "ruleset_id": "UNKNOWN",
                "forecast_error_to_clearing": np.nan,
                "forecast_error_to_realised": np.nan,
                "source_lineage": "UNKNOWN",
            })

        row = dict(t)
        row["interconnector_id"] = meta.get("interconnector_id", "UNKNOWN")
        row["from_region"] = meta.get("from_region", "UNKNOWN")
        row["ruleset_id"] = meta.get("ruleset_id", "UNKNOWN")
        row["forecast_error_to_clearing"] = meta.get("forecast_error_to_clearing", np.nan)
        row["forecast_error_to_realised"] = meta.get("forecast_error_to_realised", np.nan)
        row["source_lineage"] = meta.get("source_lineage", "UNKNOWN")
        out_rows.append(row)

    base = pd.DataFrame(out_rows)
    base["direction"] = base.apply(lambda r: _parse_direction(r["product_id"], r["from_region"]), axis=1)
    base["trade_outcome"] = np.where(base["alpha"] > 0, "winning", "losing")
    return base


def merge_component_exports(base: pd.DataFrame, path: str) -> pd.DataFrame:
    if not path:
        return base

    comp = pd.read_csv(path)

    # Normalize dates if provided
    if "decision_date" in comp.columns:
        comp["decision_date"] = pd.to_datetime(comp["decision_date"], utc=True)

    # Try best key from most to least specific.
    key_options = [
        ["product_id", "quarter", "tranche", "decision_date"],
        ["product_id", "quarter", "tranche"],
        ["product_id", "decision_date"],
        ["product_id"],
    ]

    for keys in key_options:
        if all(k in base.columns for k in keys) and all(k in comp.columns for k in keys):
            merged = base.merge(comp, on=keys, how="left", suffixes=("", "_comp"))
            return merged

    raise ValueError(
        "Could not merge component exports: no compatible key set found. "
        "Supported keys include product_id/quarter/tranche/decision_date."
    )


def compute_total_error(trades: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()

    # Unit payout forecast/actual may come from component exports; fallback to base fields.
    payout_fc_col = _find_first_existing(trades, ["unit_payout_forecast", "fair_value_forecast"])
    payout_ac_col = _find_first_existing(trades, ["unit_payout_actual", "payout_per_unit"])

    if payout_fc_col is None or payout_ac_col is None:
        raise ValueError("Missing required payout forecast/actual fields for total error calculation")

    trades["unit_payout_forecast_used"] = trades[payout_fc_col]
    trades["unit_payout_actual_used"] = trades[payout_ac_col]
    trades["total_error_per_unit"] = trades["unit_payout_actual_used"] - trades["unit_payout_forecast_used"]
    trades["total_error_aud_signed"] = trades["total_error_per_unit"] * trades["units"]
    trades["total_error_aud_abs"] = trades["total_error_aud_signed"].abs()
    return trades


def compute_category_errors(trades: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()

    for cat in CATEGORIES:
        signed_col = f"{cat}_aud_signed"
        abs_col = f"{cat}_aud_abs"
        available_col = f"dq_has_{cat}"

        trades[signed_col] = np.nan

        # Priority 1: explicit AUD export field
        explicit_col = CATEGORY_TO_EXPORT_COL[cat]
        if explicit_col in trades.columns:
            trades[signed_col] = trades[explicit_col]

        # Priority 2: derive from component forecast/actual/sensitivity where possible
        if cat in COMPONENT_SPECS:
            spec = COMPONENT_SPECS[cat]
            fc_col = _find_first_existing(trades, spec["forecast_cols"])
            ac_col = _find_first_existing(trades, spec["actual_cols"])
            se_col = _find_first_existing(trades, spec["sens_cols"])

            if fc_col and ac_col and se_col:
                derived = (trades[ac_col] - trades[fc_col]) * trades[se_col] * trades["units"]
                trades[signed_col] = trades[signed_col].where(trades[signed_col].notna(), derived)

        # Priority 3: explicit unit-table/rules mismatch AUD if provided
        if cat == "unit_table_rules_error":
            if "unit_table_rules_error_aud" in trades.columns:
                trades[signed_col] = trades[signed_col].where(
                    trades[signed_col].notna(), trades["unit_table_rules_error_aud"]
                )

        trades[abs_col] = trades[signed_col].abs()
        trades[available_col] = trades[signed_col].notna()

    # Known sum and residual / unattributed bucket
    signed_cols = [f"{c}_aud_signed" for c in CATEGORIES]
    abs_cols = [f"{c}_aud_abs" for c in CATEGORIES]

    trades["known_error_aud_signed_sum"] = trades[signed_cols].fillna(0.0).sum(axis=1)
    trades["known_error_aud_abs_sum"] = trades[abs_cols].fillna(0.0).sum(axis=1)

    trades["unattributed_error_aud_signed"] = trades["total_error_aud_signed"] - trades["known_error_aud_signed_sum"]
    trades["unattributed_error_aud_abs"] = trades["unattributed_error_aud_signed"].abs()

    # Percent contributions (absolute, relative to total abs error)
    denom = trades["total_error_aud_abs"].replace(0, np.nan)
    for cat in CATEGORIES:
        trades[f"{cat}_pct_of_total_error"] = (trades[f"{cat}_aud_abs"] / denom * 100).fillna(0.0)
    trades["unattributed_pct_of_total_error"] = (trades["unattributed_error_aud_abs"] / denom * 100).fillna(0.0)

    return trades


def add_quality_and_confidence(trades: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()
    availability_cols = [f"dq_has_{c}" for c in CATEGORIES]

    trades["dq_missing_component_count"] = len(CATEGORIES) - trades[availability_cols].sum(axis=1)
    trades["dq_available_component_count"] = trades[availability_cols].sum(axis=1)

    availability_ratio = trades["dq_available_component_count"] / len(CATEGORIES)
    coverage_ratio = (trades["known_error_aud_abs_sum"] / trades["total_error_aud_abs"].replace(0, np.nan)).clip(0, 1).fillna(1.0)

    trades["attribution_confidence_score"] = (0.6 * availability_ratio + 0.4 * coverage_ratio).clip(0, 1)
    trades["attribution_confidence_label"] = np.select(
        [
            trades["attribution_confidence_score"] >= 0.80,
            trades["attribution_confidence_score"] >= 0.50,
        ],
        ["high", "medium"],
        default="low",
    )

    # Data quality flag
    unresolved_ratio = (trades["unattributed_error_aud_abs"] / trades["total_error_aud_abs"].replace(0, np.nan)).fillna(0.0)
    trades["data_quality_flag"] = np.select(
        [
            trades["total_error_aud_abs"] == 0,
            trades["attribution_confidence_score"] < 0.50,
            unresolved_ratio > 0.30,
        ],
        [
            "no_forecast_error",
            "low_attribution_confidence",
            "high_unattributed_residual",
        ],
        default="usable",
    )

    return trades


def make_grouped_outputs(trades: pd.DataFrame) -> pd.DataFrame:
    group_dimensions = [
        "corridor",
        "direction",
        "quarter",
        "tranche",
        "ruleset_id",
        "trade_outcome",
    ]

    frames = []
    for dim in group_dimensions:
        g = trades.groupby(dim, dropna=False)

        agg = g.agg(
            trades=("product_id", "count"),
            total_error_aud_signed=("total_error_aud_signed", "sum"),
            total_error_aud_abs=("total_error_aud_abs", "sum"),
            known_error_aud_abs_sum=("known_error_aud_abs_sum", "sum"),
            unattributed_error_aud_signed=("unattributed_error_aud_signed", "sum"),
            unattributed_error_aud_abs=("unattributed_error_aud_abs", "sum"),
            mean_confidence=("attribution_confidence_score", "mean"),
            pct_low_confidence=("attribution_confidence_label", lambda s: (s == "low").mean() * 100),
        ).reset_index()

        for cat in CATEGORIES:
            cat_signed = g[f"{cat}_aud_signed"].sum().reset_index(name=f"{cat}_aud_signed")
            cat_abs = g[f"{cat}_aud_abs"].sum().reset_index(name=f"{cat}_aud_abs")
            agg = agg.merge(cat_signed, on=dim, how="left")
            agg = agg.merge(cat_abs, on=dim, how="left")

        # percentage contribution within group
        denom = agg["total_error_aud_abs"].replace(0, np.nan)
        for cat in CATEGORIES:
            agg[f"{cat}_pct_of_group_error"] = (agg[f"{cat}_aud_abs"] / denom * 100).fillna(0.0)
        agg["unattributed_pct_of_group_error"] = (agg["unattributed_error_aud_abs"] / denom * 100).fillna(0.0)

        agg.insert(0, "group_type", dim)
        agg = agg.rename(columns={dim: "group_value"})
        frames.append(agg)

    return pd.concat(frames, ignore_index=True)


def ranked_model_improvements(trades: pd.DataFrame) -> pd.DataFrame:
    # Costing logic: for each category, sum negative signed errors on losing trades.
    # Negative signed error means realized < forecast component contribution.
    losing = trades[trades["trade_outcome"] == "losing"].copy()

    rows = []
    for cat in CATEGORIES + ["unattributed_error"]:
        if cat == "unattributed_error":
            s = losing["unattributed_error_aud_signed"].fillna(0.0)
            label = "unattributed_investigation"
        else:
            s = losing[f"{cat}_aud_signed"].fillna(0.0)
            label = cat

        cost = -s[s < 0].sum()  # AUD currently lost to this error source
        rows.append(
            {
                "improvement_area": label,
                "estimated_cost_of_error_aud": cost,
                "estimated_gain_if_25pct_reduced_aud": cost * 0.25,
                "estimated_gain_if_50pct_reduced_aud": cost * 0.50,
                "estimated_gain_if_100pct_reduced_aud": cost,
            }
        )

    out = pd.DataFrame(rows).sort_values("estimated_cost_of_error_aud", ascending=False)
    return out


def write_forensic_report(trades: pd.DataFrame, improvements: pd.DataFrame, top_n: int, out_md: Path) -> None:
    largest_losses = trades.sort_values("alpha", ascending=True).head(top_n).copy()

    # Identify dominant component per losing trade by absolute error
    def dominant_component(row: pd.Series) -> str:
        comps: Dict[str, float] = {c: float(row.get(f"{c}_aud_abs", np.nan)) for c in CATEGORIES}
        comps["unattributed_error"] = float(row.get("unattributed_error_aud_abs", np.nan))
        clean = {k: (0.0 if np.isnan(v) else v) for k, v in comps.items()}
        return max(clean, key=clean.get)

    largest_losses["dominant_component"] = largest_losses.apply(dominant_component, axis=1)

    top_impr = improvements.head(10)

    total_abs_error = trades["total_error_aud_abs"].sum()
    known_abs_error = trades["known_error_aud_abs_sum"].sum()
    unattributed_abs_error = trades["unattributed_error_aud_abs"].sum()

    lines = [
        "# Phase 4B Forensic Report – Largest Losses & Improvement Ranking",
        "",
        "## Summary",
        f"- Trades analyzed: `{len(trades):,}`",
        f"- Total absolute forecast error (AUD): `${total_abs_error:,.2f}`",
        f"- Known attributed absolute error (AUD): `${known_abs_error:,.2f}`",
        f"- Unattributed absolute error (AUD): `${unattributed_abs_error:,.2f}`",
        f"- Unattributed share: `{(unattributed_abs_error / total_abs_error * 100) if total_abs_error else 0:.1f}%`",
        "",
        "## Largest Losses (Forensic)",
        "",
        "| decision_date | product_id | corridor | quarter | tranche | alpha_aud | total_error_aud | dominant_component | confidence | data_quality_flag |",
        "|---|---|---|---|---|---:|---:|---|---|---|",
    ]

    for _, r in largest_losses.iterrows():
        lines.append(
            f"| {r['decision_date']} | {r['product_id']} | {r['corridor']} | {r['quarter']} | {r['tranche']} | {r['alpha']:.2f} | {r['total_error_aud_signed']:.2f} | {r['dominant_component']} | {r['attribution_confidence_label']} ({r['attribution_confidence_score']:.2f}) | {r['data_quality_flag']} |"
        )

    lines.extend(
        [
            "",
            "## Ranked Model Improvements by Estimated P&L Benefit",
            "",
            "| rank | improvement_area | estimated_cost_of_error_aud | gain_if_25pct | gain_if_50pct | gain_if_100pct |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )

    for i, (_, r) in enumerate(top_impr.iterrows(), start=1):
        lines.append(
            f"| {i} | {r['improvement_area']} | {r['estimated_cost_of_error_aud']:.2f} | {r['estimated_gain_if_25pct_reduced_aud']:.2f} | {r['estimated_gain_if_50pct_reduced_aud']:.2f} | {r['estimated_gain_if_100pct_reduced_aud']:.2f} |"
        )

    if len(top_impr) > 0:
        best = top_impr.iloc[0]
        lines.extend(
            [
                "",
                "## Main Question Answer",
                "",
                f"The largest current loss source is **`{best['improvement_area']}`** with estimated cost `${best['estimated_cost_of_error_aud']:,.2f}`.",
                "",
                "This identifies the highest-value next improvement target. Strategy optimization should wait until this dominant error source is reduced or better explained.",
            ]
        )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    base = load_base_trades()
    merged = merge_component_exports(base, args.component_exports)

    trades = compute_total_error(merged)
    trades = compute_category_errors(trades)
    trades = add_quality_and_confidence(trades)

    grouped = make_grouped_outputs(trades)
    improvements = ranked_model_improvements(trades)

    trade_csv = reports_dir / "phase4b_trade_level_attribution.csv"
    group_csv = reports_dir / "phase4b_grouped_attribution.csv"
    improve_csv = reports_dir / "phase4b_ranked_model_improvements.csv"
    forensic_md = reports_dir / "PHASE4B_FORENSIC_LARGEST_LOSSES.md"

    # Selected columns for trade-level output
    keep_cols = [
        "decision_date",
        "product_id",
        "quarter",
        "tranche",
        "corridor",
        "direction",
        "interconnector_id",
        "ruleset_id",
        "trade_outcome",
        "units",
        "alpha",
        "unit_payout_forecast_used",
        "unit_payout_actual_used",
        "total_error_per_unit",
        "total_error_aud_signed",
        "total_error_aud_abs",
    ]
    for c in CATEGORIES:
        keep_cols.extend([
            f"{c}_aud_signed",
            f"{c}_aud_abs",
            f"{c}_pct_of_total_error",
            f"dq_has_{c}",
        ])
    keep_cols.extend(
        [
            "known_error_aud_signed_sum",
            "known_error_aud_abs_sum",
            "unattributed_error_aud_signed",
            "unattributed_error_aud_abs",
            "unattributed_pct_of_total_error",
            "dq_available_component_count",
            "dq_missing_component_count",
            "attribution_confidence_score",
            "attribution_confidence_label",
            "data_quality_flag",
            "source_lineage",
        ]
    )

    trades[keep_cols].to_csv(trade_csv, index=False)
    grouped.to_csv(group_csv, index=False)
    improvements.to_csv(improve_csv, index=False)
    write_forensic_report(trades, improvements, args.top_losses, forensic_md)

    # Executive print
    top = improvements.iloc[0] if len(improvements) > 0 else None
    print("=" * 88)
    print("PHASE 4B ERROR ATTRIBUTION COMPLETE")
    print("=" * 88)
    print(f"Trades analyzed: {len(trades):,}")
    print(f"Trade-level output: {trade_csv}")
    print(f"Grouped output: {group_csv}")
    print(f"Forensic report: {forensic_md}")
    print(f"Improvement ranking: {improve_csv}")
    if top is not None:
        print()
        print("Main Answer:")
        print(
            f"  Dominant cost driver = {top['improvement_area']} "
            f"(estimated cost ${top['estimated_cost_of_error_aud']:,.2f})"
        )


if __name__ == "__main__":
    main()
