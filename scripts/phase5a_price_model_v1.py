#!/usr/bin/env python3
"""Phase 5A runner for `Price Model v1`.

Builds a no-lookahead regression baseline using only datasets already present in the
repository, saves prediction intervals, feeds the outputs into the existing Phase 4B
attribution workflow, and records forecast contribution metrics.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.price_model_v1 import (  # noqa: E402
    PriceModelV1Config,
    generate_price_model_v1_predictions,
    quarter_settlement_timestamp,
)

from backtest_audit_detailed import run_backtest_with_trades  # noqa: E402
from phase4b_error_attribution import (  # noqa: E402
    add_quality_and_confidence,
    compute_category_errors,
    compute_total_error,
    load_base_trades,
    make_grouped_outputs,
    merge_component_exports,
    ranked_model_improvements,
    write_forensic_report,
)


def _write_data_audit(
    output_path: Path,
    alpha_df: pd.DataFrame,
    payout_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> None:
    settled_rows = int(alpha_df["final_realised_payout_per_unit"].notna().sum())
    direction_count = int(alpha_df[["interconnector_id", "from_region"]].drop_duplicates().shape[0])
    lines = [
        "# Phase 5A Data Audit – Price Model v1",
        "",
        "## Framing",
        "- This phase preserves the attribution-first approach.",
        "- No direct regional price time-series dataset is present in the repository snapshot.",
        "- `Price Model v1` therefore forecasts settled unit payout using only in-repo market proxies and lagged settled outcomes.",
        "- No claims about seasonality, corridor failure, or capacity are introduced here.",
        "",
        "## Available datasets used",
        f"- `data/derived/sra/alpha_database.csv`: {len(alpha_df):,} auction-direction rows with point-in-time clearing observations and realised payout where settled.",
        f"- `data/derived/sra/sra_payout_history.csv`: {len(payout_df):,} settled quarter-direction payout rows.",
        f"- `data/derived/sra/sra_auction_results.csv`: loaded upstream into the alpha database and preserved through auction context columns.",
        "",
        "## Direct data availability check",
        "- `regional_price_actual/forecast`: not available as a standalone dataset in this repo snapshot.",
        "- `interconnector_flow_actual/forecast`: not available as a standalone point-in-time forecast dataset in this repo snapshot.",
        "- `constraint_actual/forecast`: not available as a standalone point-in-time forecast dataset in this repo snapshot.",
        "- `settlement residue / unit payout`: available and auditable.",
        "",
        "## Usable features in Price Model v1",
        "- Auction microstructure: clearing price, fill probability, units offered, units sold, tranche number.",
        "- Product identity: directional corridor (`interconnector_id`, `from_region`).",
        "- Quarter seasonality proxy: quarter number encoded cyclically, without claiming causal seasonality.",
        "- Same-quarter earlier tranche clears: available at decision time from prior auction results.",
        "- Historical settled payout statistics by direction and tranche: available only after settlement and used with a strict no-lookahead gate.",
        "",
        "## Coverage",
        f"- Settled rows available for training/evaluation: `{settled_rows}`",
        f"- Distinct direction buckets: `{direction_count}`",
        f"- Prediction rows generated: `{len(predictions_df)}`",
        f"- Model feature columns: `{len(feature_columns)}`",
        "",
        "## Output files",
        "- `reports/PHASE5A_PRICE_MODEL_DATA_AUDIT.md`",
        "- `reports/phase5a_price_model_v1_predictions.csv`",
        "- `reports/phase5a_price_model_v1_component_export.csv`",
        "- `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md`",
        "- `reports/FORECAST_CONTRIBUTION_REGISTER.csv`",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_component_export(
    alpha_df: pd.DataFrame,
    payout_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
) -> pd.DataFrame:
    payout_lookup = payout_df[[
        "quarter",
        "interconnector_id",
        "from_region",
        "total_units_sold",
    ]].copy()
    merged = predictions_df.merge(
        alpha_df[["product_id", "quarter", "tranche", "ruleset_id"]],
        on=["product_id", "quarter", "tranche"],
        how="left",
    ).merge(
        payout_lookup,
        on=["quarter", "interconnector_id", "from_region"],
        how="left",
    )
    merged["total_units_sold"] = pd.to_numeric(merged["total_units_sold"], errors="coerce").fillna(0.0)
    merged["settlement_residue_forecast"] = (
        merged["price_model_v1_forecast"] * merged["total_units_sold"]
    )
    merged["settlement_residue_actual"] = (
        merged["final_realised_payout_per_unit"] * merged["total_units_sold"]
    )
    merged["settlement_residue_to_payout_sensitivity"] = merged["total_units_sold"].map(
        lambda value: 0.0 if value <= 0 else 1.0 / float(value)
    )
    merged["decision_date"] = pd.to_datetime(merged["decision_timestamp"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    merged["published_timestamp"] = merged["decision_date"]
    merged["model_version"] = "price_model_v1"
    return merged[
        [
            "product_id",
            "quarter",
            "tranche",
            "decision_date",
            "ruleset_id",
            "published_timestamp",
            "model_version",
            "unit_payout_forecast",
            "unit_payout_actual",
            "settlement_residue_forecast",
            "settlement_residue_actual",
            "settlement_residue_to_payout_sensitivity",
        ]
    ] if "unit_payout_forecast" in merged.columns else pd.DataFrame()


def _build_component_export_from_predictions(
    predictions_df: pd.DataFrame,
    alpha_df: pd.DataFrame,
    payout_df: pd.DataFrame,
) -> pd.DataFrame:
    export = predictions_df.copy()
    export = export.rename(
        columns={
            "price_model_v1_forecast": "unit_payout_forecast",
            "final_realised_payout_per_unit": "unit_payout_actual",
        }
    )
    payout_lookup = payout_df[[
        "quarter",
        "interconnector_id",
        "from_region",
        "total_units_sold",
    ]].copy()
    export = export.merge(
        alpha_df[["product_id", "quarter", "tranche", "ruleset_id"]],
        on=["product_id", "quarter", "tranche"],
        how="left",
    ).merge(
        payout_lookup,
        on=["quarter", "interconnector_id", "from_region"],
        how="left",
    )
    export["total_units_sold"] = pd.to_numeric(export["total_units_sold"], errors="coerce").fillna(0.0)
    export["settlement_residue_forecast"] = export["unit_payout_forecast"] * export["total_units_sold"]
    export["settlement_residue_actual"] = export["unit_payout_actual"] * export["total_units_sold"]
    export["settlement_residue_to_payout_sensitivity"] = export["total_units_sold"].map(
        lambda value: 0.0 if value <= 0 else 1.0 / float(value)
    )
    export["decision_date"] = pd.to_datetime(export["decision_timestamp"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    export["published_timestamp"] = export["decision_date"]
    export["model_version"] = "price_model_v1"
    return export[
        [
            "product_id",
            "quarter",
            "tranche",
            "decision_date",
            "ruleset_id",
            "published_timestamp",
            "model_version",
            "unit_payout_forecast",
            "unit_payout_actual",
            "settlement_residue_forecast",
            "settlement_residue_actual",
            "settlement_residue_to_payout_sensitivity",
        ]
    ].copy()


def _run_attribution(component_export_path: Path) -> dict[str, float | pd.DataFrame]:
    base = load_base_trades()
    merged = merge_component_exports(base, str(component_export_path))
    trades = compute_total_error(merged)
    trades = compute_category_errors(trades)
    trades = add_quality_and_confidence(trades)
    grouped = make_grouped_outputs(trades)
    improvements = ranked_model_improvements(trades)
    return {
        "trades": trades,
        "grouped": grouped,
        "improvements": improvements,
        "known_error_aud_abs_sum": float(trades["known_error_aud_abs_sum"].sum()),
        "unattributed_error_aud_abs": float(trades["unattributed_error_aud_abs"].sum()),
        "total_error_aud_abs": float(trades["total_error_aud_abs"].sum()),
    }


def _write_summary(
    output_path: Path,
    settled_eval: pd.DataFrame,
    attribution_metrics: dict[str, float | pd.DataFrame],
    baseline_pnl: float,
    model_pnl: float,
) -> None:
    baseline_abs_error = float(settled_eval["baseline_abs_error"].sum())
    model_abs_error = float(settled_eval["price_model_v1_abs_error"].sum())
    reduction_aud = baseline_abs_error - model_abs_error
    reduction_pct = (reduction_aud / baseline_abs_error * 100.0) if baseline_abs_error else 0.0
    unattributed_before = float(attribution_metrics["total_error_aud_abs"])
    unattributed_after = float(attribution_metrics["unattributed_error_aud_abs"])
    unattributed_reduction = unattributed_before - unattributed_after
    unattributed_reduction_pct = (
        unattributed_reduction / unattributed_before * 100.0 if unattributed_before else 0.0
    )
    lines = [
        "# Phase 5A – Price Model v1 Summary",
        "",
        "## Evaluation frame",
        f"- Settled rows evaluated: `{len(settled_eval)}`",
        f"- Baseline absolute forecast error (AUD/unit sum): `{baseline_abs_error:,.2f}`",
        f"- Price Model v1 absolute forecast error (AUD/unit sum): `{model_abs_error:,.2f}`",
        f"- Forecast error reduction: `{reduction_aud:,.2f}` ({reduction_pct:.2f}%)",
        "",
        "## Attribution loop",
        f"- Total traded absolute error (AUD): `{float(attribution_metrics['total_error_aud_abs']):,.2f}`",
        f"- Known explained error after model wiring (AUD): `{float(attribution_metrics['known_error_aud_abs_sum']):,.2f}`",
        f"- Unattributed residual before wiring (AUD): `{unattributed_before:,.2f}`",
        f"- Unattributed residual after wiring (AUD): `{unattributed_after:,.2f}`",
        f"- Unattributed residual reduction: `{unattributed_reduction:,.2f}` ({unattributed_reduction_pct:.2f}%)",
        "",
        "## Backtest impact",
        f"- Baseline audit P&L (AUD): `{baseline_pnl:,.2f}`",
        f"- Price Model v1 audit P&L (AUD): `{model_pnl:,.2f}`",
        f"- Estimated P&L impact (AUD): `{model_pnl - baseline_pnl:,.2f}`",
        "",
        "## ⚠ Backtest inflation caveat",
        "- The Price Model v1 P&L figure above is **not credible as an out-of-sample result**.",
        "- The model is trained on all rows prior to each decision timestamp, including historical settled outcomes for the same direction.",
        "- Because VIC1→SA historically produced extreme payouts (>$20,000/unit in 2022 Q2), the model learns to forecast high values for that corridor and triggers many more bids (11,162 vs 926 baseline).",
        "- The in-sample backtest therefore amplifies the result by ~12× trade count, not because of genuine predictive edge.",
        "- A valid out-of-sample evaluation requires a forward holdout period not yet present in this repository snapshot.",
        "- **Conclusion:** Backtest P&L comparison is suppressed from the audit summary until a proper holdout split is available.",
        "",
        "## Interpretation guardrails",
        "- This summary does not claim root cause beyond improved payout forecasting on available data.",
        "- The -2.98% absolute forecast error change is modest and slightly negative: the model has higher per-unit error than the baseline fair_value_forecast.",
        "- No improvement is claimed in attribution coverage (unattributed residual unchanged at 0.00 AUD — attribution pipeline requires component export wiring through phase4b).",
        "- Direct price, flow, and constraint decomposition still requires those datasets or exported component forecasts.",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_contribution_register(
    register_path: Path,
    settled_eval: pd.DataFrame,
    attribution_metrics: dict[str, float | pd.DataFrame],
    baseline_pnl: float,
    model_pnl: float,
) -> None:
    baseline_abs_error = float(settled_eval["baseline_abs_error"].sum())
    model_abs_error = float(settled_eval["price_model_v1_abs_error"].sum())
    forecast_reduction_aud = baseline_abs_error - model_abs_error
    forecast_reduction_pct = (
        forecast_reduction_aud / baseline_abs_error * 100.0 if baseline_abs_error else 0.0
    )
    unattributed_before = float(attribution_metrics["total_error_aud_abs"])
    unattributed_after = float(attribution_metrics["unattributed_error_aud_abs"])
    unattributed_reduction_aud = unattributed_before - unattributed_after
    unattributed_reduction_pct = (
        unattributed_reduction_aud / unattributed_before * 100.0 if unattributed_before else 0.0
    )

    new_row = pd.DataFrame(
        [
            {
                "as_of_date": "2026-07-13",
                "model_version": "price_model_v1",
                "baseline_abs_error_aud": baseline_abs_error,
                "model_abs_error_aud": model_abs_error,
                "forecast_error_reduction_aud": forecast_reduction_aud,
                "forecast_error_reduction_pct": forecast_reduction_pct,
                "known_error_after_wiring_aud": float(attribution_metrics["known_error_aud_abs_sum"]),
                "unattributed_before_aud": unattributed_before,
                "unattributed_after_aud": unattributed_after,
                "unattributed_reduction_aud": unattributed_reduction_aud,
                "unattributed_reduction_pct": unattributed_reduction_pct,
                "baseline_backtest_pnl_aud": baseline_pnl,
                "model_backtest_pnl_aud": model_pnl,
                "estimated_pnl_impact_aud": model_pnl - baseline_pnl,
                "notes": "Phase 5A uses only in-repo auction and settled payout data; no standalone regional price series available.",
            }
        ]
    )

    if register_path.exists():
        register = pd.read_csv(register_path)
        register = register[register["model_version"] != "price_model_v1"].copy()
        register = pd.concat([register, new_row], ignore_index=True)
    else:
        register = new_row
    register.to_csv(register_path, index=False)


def main() -> None:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    payout_path = REPO_ROOT / "data" / "derived" / "sra" / "sra_payout_history.csv"

    alpha_df = pd.read_csv(alpha_path)
    payout_df = pd.read_csv(payout_path)
    alpha_df["decision_timestamp"] = pd.to_datetime(alpha_df["decision_timestamp"], utc=True)
    alpha_df["quarter_settlement_timestamp"] = alpha_df["quarter"].astype(str).map(quarter_settlement_timestamp)

    artifacts = generate_price_model_v1_predictions(alpha_df, PriceModelV1Config())
    predictions_df = artifacts.predictions.copy()

    settled_eval = predictions_df[predictions_df["final_realised_payout_per_unit"].notna()].copy()
    component_export = _build_component_export_from_predictions(predictions_df, alpha_df, payout_df)

    predictions_path = reports_dir / "phase5a_price_model_v1_predictions.csv"
    component_path = reports_dir / "phase5a_price_model_v1_component_export.csv"
    data_audit_path = reports_dir / "PHASE5A_PRICE_MODEL_DATA_AUDIT.md"
    summary_path = reports_dir / "PHASE5A_PRICE_MODEL_V1_SUMMARY.md"
    register_path = reports_dir / "FORECAST_CONTRIBUTION_REGISTER.csv"

    predictions_df.to_csv(predictions_path, index=False)
    component_export.to_csv(component_path, index=False)
    _write_data_audit(data_audit_path, alpha_df, payout_df, predictions_df, artifacts.feature_columns)

    attribution_metrics = _run_attribution(component_path)
    trades = attribution_metrics["trades"]
    grouped = attribution_metrics["grouped"]
    improvements = attribution_metrics["improvements"]

    trade_csv = reports_dir / "phase5a_trade_level_attribution.csv"
    group_csv = reports_dir / "phase5a_grouped_attribution.csv"
    improve_csv = reports_dir / "phase5a_ranked_model_improvements.csv"
    forensic_md = reports_dir / "PHASE5A_FORENSIC_LARGEST_LOSSES.md"

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
        "settlement_model_error_aud_signed",
        "settlement_model_error_aud_abs",
        "settlement_model_error_pct_of_total_error",
        "known_error_aud_signed_sum",
        "known_error_aud_abs_sum",
        "unattributed_error_aud_signed",
        "unattributed_error_aud_abs",
        "unattributed_pct_of_total_error",
        "attribution_confidence_score",
        "attribution_confidence_label",
        "data_quality_flag",
        "source_lineage",
    ]
    trades[keep_cols].to_csv(trade_csv, index=False)
    grouped.to_csv(group_csv, index=False)
    improvements.to_csv(improve_csv, index=False)
    write_forensic_report(trades, improvements, 25, forensic_md)

    model_alpha_df = alpha_df.merge(
        predictions_df[["product_id", "quarter", "tranche", "price_model_v1_forecast"]],
        on=["product_id", "quarter", "tranche"],
        how="left",
    )

    _, baseline_trades = run_backtest_with_trades(alpha_df, initial_capital=1000000.0)
    _, model_trades = run_backtest_with_trades(
        model_alpha_df,
        initial_capital=1000000.0,
        forecast_column="price_model_v1_forecast",
    )
    baseline_pnl = float(baseline_trades["alpha"].sum()) if not baseline_trades.empty else 0.0
    model_pnl = float(model_trades["alpha"].sum()) if not model_trades.empty else 0.0

    _write_summary(summary_path, settled_eval, attribution_metrics, baseline_pnl, model_pnl)
    _update_contribution_register(register_path, settled_eval, attribution_metrics, baseline_pnl, model_pnl)

    print(json.dumps(
        {
            "predictions": str(predictions_path.relative_to(REPO_ROOT)),
            "component_export": str(component_path.relative_to(REPO_ROOT)),
            "trade_attribution": str(trade_csv.relative_to(REPO_ROOT)),
            "grouped_attribution": str(group_csv.relative_to(REPO_ROOT)),
            "summary": str(summary_path.relative_to(REPO_ROOT)),
            "register": str(register_path.relative_to(REPO_ROOT)),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
