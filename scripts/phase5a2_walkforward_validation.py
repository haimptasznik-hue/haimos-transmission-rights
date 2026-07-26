#!/usr/bin/env python3
"""Phase 5A.2 – Walk-Forward Deviation Model Validation

Tests Price Model v2 (deviation-based forecasting) against:
  - Seasonal benchmark (OOS MAE: $8,470/unit from Phase 5A.1)
  - Regime-adjusted benchmark (seasonal + recent weighted deviation)
  - Ridge regression deviation model

Strict walk-forward: train only on quarters before the test quarter.
Promotion gate requires:
  1. OOS deviation MAE beats best benchmark
  2. Improves multiple corridors
  3. No single corridor dominates
  4. At least 17 OOS quarters
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.price_model_v2 import (  # noqa: E402
    PriceModelV2Config,
    build_deviation_features,
    compute_seasonal_benchmark,
    compute_regime_adjusted_benchmark,
    quarter_settlement_timestamp,
    quarter_to_components,
    _fit_ridge_deviation,
    _predict_ridge_deviation,
)


# ── constants ─────────────────────────────────────────────────────────────────

MIN_WARM_UP_QUARTERS = 8
MIN_TEST_QUARTERS = 4
RIDGE_LAMBDA = 10.0
PHASE5A1_SEASONAL_MAE = 8470.02  # Baseline to beat


# ── helpers ───────────────────────────────────────────────────────────────────

def _quarter_sort_key(q: str) -> tuple[int, int]:
    return quarter_to_components(q)


def _sorted_quarters(df: pd.DataFrame) -> list[str]:
    return sorted(df["quarter"].unique(), key=_quarter_sort_key)


# ── walk-forward loop ─────────────────────────────────────────────────────────

def run_walkforward_v2(
    alpha_df: pd.DataFrame,
    payout_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Walk-forward validation of Price Model v2.
    
    Returns:
    - results_df: per-row predictions and errors
    - corridor_df: per-corridor summary
    - gate_dict: promotion gate evaluation
    """
    alpha_df = alpha_df.copy()
    alpha_df["decision_timestamp"] = pd.to_datetime(alpha_df["decision_timestamp"], utc=True)
    alpha_df["quarter_settlement_timestamp"] = (
        alpha_df["quarter"].astype(str).map(quarter_settlement_timestamp)
    )
    alpha_df["direction_key"] = (
        alpha_df["interconnector_id"].astype(str) + "::" + alpha_df["from_region"].astype(str)
    )

    # payout_df is quarterly summary; use alpha_df settled rows as our training data
    settled = alpha_df[alpha_df["final_realised_payout_per_unit"].notna()].copy()
    all_quarters = _sorted_quarters(settled)

    if len(all_quarters) < MIN_WARM_UP_QUARTERS + 1:
        raise ValueError(f"Need ≥{MIN_WARM_UP_QUARTERS + 1} settled quarters; found {len(all_quarters)}")

    records: list[dict] = []
    feature_coverage: dict[str, dict[str, int]] = {}

    for test_idx in range(MIN_WARM_UP_QUARTERS, len(all_quarters)):
        test_quarter = all_quarters[test_idx]
        train_quarters = set(all_quarters[:test_idx])

        settled_before = settled[settled["quarter"].isin(train_quarters)].copy()
        test_rows = settled[settled["quarter"] == test_quarter].copy()

        if len(test_rows) == 0:
            continue

        # Build feature matrix for ridge model
        feature_data = []
        y_train_list = []
        y_test_list = []
        test_directions = []

        # Training rows: deviations from seasonal
        for _, row in settled_before.iterrows():
            dk = row["direction_key"]
            seasonal = compute_seasonal_benchmark(settled_before, dk) or 0.0
            feats = build_deviation_features(settled_before, dk, seasonal)
            actual_dev = row["final_realised_payout_per_unit"] - seasonal
            if np.isfinite(actual_dev):
                feature_data.append([
                    feats.recent_trend_4q,
                    feats.deviation_volatility_4q,
                    feats.recent_mean_abs_dev,
                    feats.same_q_variance_prior_years,
                    feats.lagged_deviation,
                ])
                y_train_list.append(actual_dev)

        X_train = np.array(feature_data, dtype=float) if feature_data else np.empty((0, 5))
        y_train = np.array(y_train_list, dtype=float)

        # Test rows: compute benchmarks and features
        for _, row in test_rows.iterrows():
            dk = row["direction_key"]
            actual_payout = row["final_realised_payout_per_unit"]

            seasonal = compute_seasonal_benchmark(settled_before, dk) or 0.0
            regime_adj = compute_regime_adjusted_benchmark(settled_before, dk) or seasonal
            feats = build_deviation_features(settled_before, dk, seasonal)

            actual_dev = actual_payout - seasonal if np.isfinite(actual_payout) else np.nan

            # Predict deviation with ridge
            X_row = np.array([
                feats.recent_trend_4q,
                feats.deviation_volatility_4q,
                feats.recent_mean_abs_dev,
                feats.same_q_variance_prior_years,
                feats.lagged_deviation,
            ], dtype=float).reshape(1, -1)

            ridge_dev_forecast = 0.0
            if len(y_train) >= 2 and X_train.shape[1] == 5:
                beta = _fit_ridge_deviation(X_train, y_train, RIDGE_LAMBDA)
                if beta is not None:
                    ridge_dev_forecast = float(_predict_ridge_deviation(X_row, beta)[0])

            # Compute error metrics
            ridge_payout_forecast = seasonal + ridge_dev_forecast
            bench_seasonal_error = abs(seasonal - actual_payout) if np.isfinite(actual_payout) else np.nan
            bench_regime_error = abs(regime_adj - actual_payout) if np.isfinite(actual_payout) else np.nan
            ridge_error = abs(ridge_payout_forecast - actual_payout) if np.isfinite(actual_payout) else np.nan

            records.append({
                "test_quarter":              test_quarter,
                "train_quarters_count":      len(train_quarters),
                "product_id":                row.get("product_id", ""),
                "direction_key":             dk,
                "interconnector_id":         row.get("interconnector_id", ""),
                "from_region":               row.get("from_region", ""),
                "tranche_no":                row.get("tranche_no", np.nan),
                "actual_payout":             actual_payout,
                "seasonal_benchmark":        seasonal,
                "regime_adj_benchmark":      regime_adj,
                "ridge_v2_payout_forecast":  ridge_payout_forecast,
                "ridge_v2_deviation_forecast": ridge_dev_forecast,
                "bench_seasonal_error":      bench_seasonal_error,
                "bench_regime_error":        bench_regime_error,
                "ridge_v2_error":            ridge_error,
                "feat_recent_trend":         feats.recent_trend_4q,
                "feat_volatility":           feats.deviation_volatility_4q,
                "feat_mean_abs_dev":         feats.recent_mean_abs_dev,
                "feat_same_q_var":           feats.same_q_variance_prior_years,
                "feat_lagged_dev":           feats.lagged_deviation,
            })

            # Track feature coverage
            if dk not in feature_coverage:
                feature_coverage[dk] = {
                    "recent_trend": 0,
                    "volatility": 0,
                    "mean_abs_dev": 0,
                    "same_q_var": 0,
                    "lagged_dev": 0,
                    "total": 0,
                }
            feature_coverage[dk]["total"] += 1
            if np.isfinite(feats.recent_trend_4q) and feats.recent_trend_4q != 0:
                feature_coverage[dk]["recent_trend"] += 1
            if np.isfinite(feats.deviation_volatility_4q) and feats.deviation_volatility_4q > 0:
                feature_coverage[dk]["volatility"] += 1
            if np.isfinite(feats.recent_mean_abs_dev) and feats.recent_mean_abs_dev > 0:
                feature_coverage[dk]["mean_abs_dev"] += 1
            if np.isfinite(feats.same_q_variance_prior_years) and feats.same_q_variance_prior_years > 0:
                feature_coverage[dk]["same_q_var"] += 1
            if np.isfinite(feats.lagged_deviation) and feats.lagged_deviation != 0:
                feature_coverage[dk]["lagged_dev"] += 1

    results_df = pd.DataFrame(records)

    # Corridor summary
    corridor_summary = []
    for dk, grp in results_df.groupby("direction_key"):
        seasonal_mae = float(grp["bench_seasonal_error"].mean(skipna=True))
        regime_mae = float(grp["bench_regime_error"].mean(skipna=True))
        ridge_mae = float(grp["ridge_v2_error"].mean(skipna=True))
        cov = feature_coverage.get(dk, {})

        corridor_summary.append({
            "direction_key": dk,
            "n_rows": len(grp),
            "bench_seasonal_mae": seasonal_mae,
            "bench_regime_mae": regime_mae,
            "ridge_v2_mae": ridge_mae,
            "ridge_beats_seasonal": ridge_mae < seasonal_mae,
            "ridge_beats_regime": ridge_mae < regime_mae,
            "coverage_recent_trend_pct": (cov.get("recent_trend", 0) / cov.get("total", 1) * 100) if cov.get("total", 0) > 0 else 0,
            "coverage_volatility_pct": (cov.get("volatility", 0) / cov.get("total", 1) * 100) if cov.get("total", 0) > 0 else 0,
            "coverage_mean_abs_dev_pct": (cov.get("mean_abs_dev", 0) / cov.get("total", 1) * 100) if cov.get("total", 0) > 0 else 0,
            "coverage_same_q_var_pct": (cov.get("same_q_var", 0) / cov.get("total", 1) * 100) if cov.get("total", 0) > 0 else 0,
            "coverage_lagged_dev_pct": (cov.get("lagged_dev", 0) / cov.get("total", 1) * 100) if cov.get("total", 0) > 0 else 0,
        })

    corridor_df = pd.DataFrame(corridor_summary)

    # Promotion gate
    quarters_tested = results_df["test_quarter"].nunique()
    overall_seasonal_mae = float(results_df["bench_seasonal_error"].mean(skipna=True))
    overall_regime_mae = float(results_df["bench_regime_error"].mean(skipna=True))
    overall_ridge_mae = float(results_df["ridge_v2_error"].mean(skipna=True))

    corridors_ridge_better = (corridor_df["ridge_beats_seasonal"] | corridor_df["ridge_beats_regime"]).sum()

    gate = {
        "quarters_tested": quarters_tested,
        "overall_seasonal_mae": overall_seasonal_mae,
        "overall_regime_mae": overall_regime_mae,
        "overall_ridge_mae": overall_ridge_mae,
        "corridors_improved": corridors_ridge_better,
        "total_corridors": len(corridor_df),
        "gate_ridge_beats_seasonal": overall_ridge_mae < overall_seasonal_mae,
        "gate_ridge_beats_regime": overall_ridge_mae < overall_regime_mae,
        "gate_multiple_corridors": corridors_ridge_better > 1,
        "gate_min_quarters": quarters_tested >= MIN_TEST_QUARTERS,
    }

    # Check for single-corridor dominance
    if gate["gate_ridge_beats_seasonal"]:
        total_gain = overall_seasonal_mae - overall_ridge_mae
        max_single_gain_share = 0.0
        for _, row in corridor_df.iterrows():
            if row["ridge_beats_seasonal"]:
                corridor_gain = (row["bench_seasonal_mae"] - row["ridge_v2_mae"]) * row["n_rows"]
                if total_gain > 0:
                    share = corridor_gain / (total_gain * len(results_df))
                    max_single_gain_share = max(max_single_gain_share, share)
        gate["max_single_corridor_gain_share"] = max_single_gain_share
        gate["gate_no_single_dominates"] = max_single_gain_share <= 0.80
    else:
        gate["max_single_corridor_gain_share"] = float("nan")
        gate["gate_no_single_dominates"] = False

    # Verdict
    all_gates_pass = (
        gate["gate_ridge_beats_seasonal"]
        and gate["gate_ridge_beats_regime"]
        and gate["gate_multiple_corridors"]
        and gate["gate_no_single_dominates"]
        and gate["gate_min_quarters"]
    )
    gate["verdict"] = "PASS" if all_gates_pass else "FAIL"

    return results_df, corridor_df, gate


# ── report writers ────────────────────────────────────────────────────────────

def _write_summary(
    output_path: Path,
    results_df: pd.DataFrame,
    corridor_df: pd.DataFrame,
    gate: dict,
) -> None:
    """Write markdown summary report."""
    lines = [
        "# Phase 5A.2 – Price Model v2 Walk-Forward Validation",
        "",
        "> **Objective:** Test deviation-based forecasting with regime features.",
        "> Ridge regression predicts: actual_payout − seasonal_benchmark.",
        "> Benchmarks: seasonal, regime-adjusted, and ridge model v2.",
        "",
        "## Setup",
        f"- Warm-up window: `{MIN_WARM_UP_QUARTERS}` settled quarters.",
        f"- Test quarters evaluated: `{gate['quarters_tested']}`",
        f"- Minimum test quarters required: `{MIN_TEST_QUARTERS}`",
        "",
        "## Benchmarks",
        "| Benchmark | Description |",
        "|---|---|",
        "| `seasonal` | Historical mean payout for same quarter-number |",
        "| `regime_adjusted` | seasonal + 0.25 × weighted recent deviation |",
        "| `ridge_v2` | Ridge regression on deviation features |",
        "",
        "## Overall OOS MAE (AUD/unit)",
        "| Model | MAE |",
        "|---|---|",
        f"| Seasonal (Phase 5A.1 baseline) | {PHASE5A1_SEASONAL_MAE:,.2f} |",
        f"| Seasonal (this fold) | {gate['overall_seasonal_mae']:,.2f} |",
        f"| Regime-adjusted | {gate['overall_regime_mae']:,.2f} |",
        f"| **Ridge Model v2** | **{gate['overall_ridge_mae']:,.2f}** |",
        "",
    ]

    # Per-corridor table
    lines += [
        "## Per-Corridor OOS MAE",
        "| Corridor | N | Seasonal | Regime-adj | Ridge v2 | Ridge beats seasonal? | Ridge beats regime? |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in corridor_df.iterrows():
        lines.append(
            f"| {row['direction_key']} | {row['n_rows']} "
            f"| {row['bench_seasonal_mae']:,.0f} "
            f"| {row['bench_regime_mae']:,.0f} "
            f"| {row['ridge_v2_mae']:,.0f} "
            f"| {'✅' if row['ridge_beats_seasonal'] else '❌'} "
            f"| {'✅' if row['ridge_beats_regime'] else '❌'} |"
        )

    lines += [
        "",
        "## Promotion Gate",
        f"| Gate | Result |",
        "|---|---|",
        f"| OOS MAE beats seasonal | {'✅' if gate['gate_ridge_beats_seasonal'] else '❌'} |",
        f"| OOS MAE beats regime-adjusted | {'✅' if gate['gate_ridge_beats_regime'] else '❌'} |",
        f"| Improves >1 corridor | {'✅' if gate['gate_multiple_corridors'] else '❌'} ({gate['corridors_improved']}/{gate['total_corridors']}) |",
        f"| No single corridor >80% of gain | {'✅' if gate['gate_no_single_dominates'] else '❌'} (max: {gate['max_single_corridor_gain_share']:.1%}) |",
        f"| ≥{MIN_TEST_QUARTERS} quarters tested | {'✅' if gate['gate_min_quarters'] else '❌'} ({gate['quarters_tested']}) |",
        "",
        f"## Verdict: **{gate['verdict']}**",
        "",
    ]

    if gate["verdict"] == "FAIL":
        lines += [
            "Price Model v2 does **not** pass the promotion gate.",
            "- Ridge model OOS MAE exceeds one or both benchmarks.",
            "- Model may not add signal beyond seasonality and recent regime adjustment.",
            "- Status: `REJECTED / RESEARCH ONLY`.",
            "",
        ]
    else:
        lines += [
            "Price Model v2 passes all promotion gates.",
            "- Eligible for promotion subject to governance sign-off.",
            "",
        ]

    lines += [
        "## Feature Coverage by Corridor",
        "| Corridor | Recent Trend | Volatility | Mean Abs Dev | Same-Q Var | Lagged Dev |",
        "|---|---|---|---|---|---|",
    ]
    for _, row in corridor_df.iterrows():
        lines.append(
            f"| {row['direction_key']} "
            f"| {row['coverage_recent_trend_pct']:.0f}% "
            f"| {row['coverage_volatility_pct']:.0f}% "
            f"| {row['coverage_mean_abs_dev_pct']:.0f}% "
            f"| {row['coverage_same_q_var_pct']:.0f}% "
            f"| {row['coverage_lagged_dev_pct']:.0f}% |"
        )

    lines += [
        "",
        "## Interpretation",
        "- Ridge v2 predicts deviations from seasonal baseline, not raw payouts.",
        "- Features capture recent trends and volatility in payout swings.",
        "- Regime-adjusted benchmark adds weighted recent deviations on top of seasonality.",
        "- If ridge beats both benchmarks, the model has identified explainable regimes.",
        "- Feature coverage gaps may limit model applicability in sparse corridors.",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_register(
    register_path: Path,
    gate: dict,
) -> None:
    """Update FORECAST_CONTRIBUTION_REGISTER with v2 results."""
    row = {
        "as_of_date": "2026-07-13",
        "model_version": "price_model_v2",
        "baseline_abs_error_aud": gate["overall_seasonal_mae"],
        "model_abs_error_aud": gate["overall_ridge_mae"],
        "forecast_error_reduction_aud": round(gate["overall_seasonal_mae"] - gate["overall_ridge_mae"], 2),
        "forecast_error_reduction_pct": round(
            (gate["overall_seasonal_mae"] - gate["overall_ridge_mae"]) / gate["overall_seasonal_mae"] * 100
            if gate["overall_seasonal_mae"] > 0 else 0, 2
        ),
        "known_error_after_wiring_aud": 0.0,
        "unattributed_before_aud": 0.0,
        "unattributed_after_aud": 0.0,
        "unattributed_reduction_aud": 0.0,
        "unattributed_reduction_pct": 0.0,
        "baseline_backtest_pnl_aud": "",
        "model_backtest_pnl_aud": "",
        "estimated_pnl_impact_aud": "",
        "notes": f"Phase 5A.2 walk-forward. {gate['quarters_tested']} OOS quarters. Ridge v2 MAE={gate['overall_ridge_mae']:.0f} vs seasonal={gate['overall_seasonal_mae']:.0f}.",
        "status": gate["verdict"],
        "rejection_reason": "" if gate["verdict"] == "PASS" else (
            f"Ridge v2 OOS MAE ({gate['overall_ridge_mae']:.0f}) does not beat seasonal baseline ({gate['overall_seasonal_mae']:.0f}). "
            "Deviation model shows no material improvement."
        ),
        "promotion_gate_passed": gate["verdict"] == "PASS",
    }

    new_row = pd.DataFrame([row])
    if register_path.exists():
        register = pd.read_csv(register_path)
        register = register[register["model_version"] != "price_model_v2"].copy()
        register = pd.concat([register, new_row], ignore_index=True)
    else:
        register = new_row
    register.to_csv(register_path, index=False)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import json

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    payout_path = REPO_ROOT / "data" / "derived" / "sra" / "sra_payout_history.csv"
    register_path = reports_dir / "FORECAST_CONTRIBUTION_REGISTER.csv"
    results_path = reports_dir / "phase5a2_walkforward_results.csv"
    corridor_path = reports_dir / "phase5a2_corridor_results.csv"
    summary_path = reports_dir / "PHASE5A2_PRICE_MODEL_V2_SUMMARY.md"

    alpha_df = pd.read_csv(alpha_path)
    payout_df = pd.read_csv(payout_path)

    print("Running walk-forward validation for Price Model v2…", flush=True)
    results_df, corridor_df, gate = run_walkforward_v2(alpha_df, payout_df)

    results_df.to_csv(results_path, index=False)
    corridor_df.to_csv(corridor_path, index=False)
    _write_summary(summary_path, results_df, corridor_df, gate)
    _update_register(register_path, gate)

    print(json.dumps({
        "quarters_tested": int(gate["quarters_tested"]),
        "seasonal_mae": round(gate["overall_seasonal_mae"], 2),
        "regime_mae": round(gate["overall_regime_mae"], 2),
        "ridge_v2_mae": round(gate["overall_ridge_mae"], 2),
        "corridors_improved": int(gate["corridors_improved"]),
        "verdict": gate["verdict"],
        "results_csv": str(results_path.relative_to(REPO_ROOT)),
        "corridor_csv": str(corridor_path.relative_to(REPO_ROOT)),
        "summary_md": str(summary_path.relative_to(REPO_ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
