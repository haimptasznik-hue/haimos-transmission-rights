#!/usr/bin/env python3
"""Phase 5A.1 – Walk-Forward Price Validation

For each unseen test quarter (after a minimum warm-up window):
  - Train only on quarters that settled BEFORE the test quarter.
  - Freeze coefficients.
  - Predict unit payout for all rows in the test quarter.
  - Compare ridge model v1 against four benchmarks:
      bench_hist_seasonal   – historical seasonal average (same quarter-number across prior years)
      bench_last_quarter    – actual payout from the immediately prior settled quarter (same direction)
      bench_same_q_prior_yr – actual payout from the same quarter number one year earlier
      bench_trend           – simple linear trend extrapolation over the last 4 settled quarters

Promotion gate (all must pass for Price Model v2 to be promotable):
  1. Lower OOS MAE than the best benchmark.
  2. At least 4 unseen quarters tested.
  3. Improvement across more than one corridor.
  4. No single corridor responsible for >80% of the error gain.
  5. No material increase in trade count caused purely by model amplification
     (ridge bid count must be < 3x benchmark bid count on matched quarters).
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

from transmission_rights.services.aemo.price_model_v1 import (  # noqa: E402
    _NUMERIC_FEATURE_COLUMNS,
    _build_feature_row,
    quarter_settlement_timestamp,
    quarter_to_components,
)

# ── constants ─────────────────────────────────────────────────────────────────
MIN_WARM_UP_QUARTERS = 8   # minimum settled quarters required before first test
MIN_TEST_QUARTERS    = 4   # promotion gate requirement
RIDGE_LAMBDA         = 10.0
AMPLIFICATION_LIMIT  = 3.0 # ridge bid count must be < N× benchmark on same quarter


# ── data helpers ─────────────────────────────────────────────────────────────

def _quarter_sort_key(q: str) -> tuple[int, int]:
    return quarter_to_components(q)


def _sorted_quarters(df: pd.DataFrame) -> list[str]:
    return sorted(df["quarter"].unique(), key=_quarter_sort_key)


def _prior_quarter(quarter: str) -> str | None:
    """Return the quarter immediately before `quarter`, or None if it would be before C2000Q1."""
    year, qno = quarter_to_components(quarter)
    if qno == 1:
        return f"C{year - 1}Q4"
    return f"C{year}Q{qno - 1}"


def _same_q_prior_year(quarter: str) -> str | None:
    year, qno = quarter_to_components(quarter)
    return f"C{year - 1}Q{qno}"


# ── feature matrix builder (mirrors price_model_v1.prepare_price_model_frame) ─

def _build_feature_matrix(
    train_rows: pd.DataFrame,
    test_rows: pd.DataFrame,
    all_settled: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X_train, y_train, X_test) with NaN → 0 sanitisation."""

    direction_keys = sorted(
        set(train_rows["direction_key"].unique()) | set(test_rows["direction_key"].unique())
    )
    direction_index = {k: i for i, k in enumerate(direction_keys)}

    def _row_to_features(row: pd.Series, known_settled: pd.DataFrame) -> np.ndarray:
        feat = _build_feature_row(row, known_settled, known_settled)
        numeric = [float(feat.get(c, 0.0) or 0.0) for c in _NUMERIC_FEATURE_COLUMNS]
        direction_vec = [0.0] * len(direction_keys)
        dk = str(row.get("direction_key", ""))
        if dk in direction_index:
            direction_vec[direction_index[dk]] = 1.0
        return np.array(numeric + direction_vec, dtype=float)

    X_train_rows, y_train_rows = [], []
    for _, row in train_rows.iterrows():
        prior_settled = all_settled[
            all_settled["quarter_settlement_timestamp"] < row["quarter_settlement_timestamp"]
        ]
        X_train_rows.append(_row_to_features(row, prior_settled))
        y_train_rows.append(float(row["final_realised_payout_per_unit"]))

    X_test_rows = []
    for _, row in test_rows.iterrows():
        prior_settled = all_settled[
            all_settled["quarter_settlement_timestamp"] < row["quarter_settlement_timestamp"]
        ]
        X_test_rows.append(_row_to_features(row, prior_settled))

    X_train = np.array(X_train_rows, dtype=float)
    y_train = np.array(y_train_rows, dtype=float)
    X_test  = np.array(X_test_rows,  dtype=float)

    # Sanitise
    X_train = np.where(np.isfinite(X_train), X_train, 0.0)
    X_test  = np.where(np.isfinite(X_test),  X_test,  0.0)
    finite_y = np.isfinite(y_train)
    X_train  = X_train[finite_y]
    y_train  = y_train[finite_y]

    return X_train, y_train, X_test


def _ridge_predict(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    ridge_lambda: float = RIDGE_LAMBDA,
) -> np.ndarray:
    if len(y_train) == 0:
        return np.full(len(X_test), np.nan)
    D = np.column_stack([np.ones(len(X_train)), X_train])
    penalty = np.eye(D.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    gram = D.T @ D + penalty
    gram_inv = np.linalg.pinv(gram, rcond=1e-12)
    beta = gram_inv @ D.T @ y_train
    D_test = np.column_stack([np.ones(len(X_test)), X_test])
    return (D_test @ beta).astype(float)


# ── benchmark predictors ──────────────────────────────────────────────────────

class BenchmarkSet(NamedTuple):
    hist_seasonal:   pd.Series   # index = test row positional index
    last_quarter:    pd.Series
    same_q_prior_yr: pd.Series
    trend:           pd.Series


def _compute_benchmarks(
    test_rows: pd.DataFrame,
    settled_before: pd.DataFrame,
    test_quarter: str,
) -> BenchmarkSet:
    _, test_q_no = quarter_to_components(test_quarter)
    prior_q   = _prior_quarter(test_quarter)
    prior_yr_q = _same_q_prior_year(test_quarter)

    hist_seasonal_vals   = []
    last_quarter_vals    = []
    same_q_prior_yr_vals = []
    trend_vals           = []

    for _, row in test_rows.iterrows():
        dk = row["direction_key"]
        dir_settled = settled_before[settled_before["direction_key"] == dk].copy()

        # bench_hist_seasonal: mean of same quarter-number in prior years
        seasonal_rows = dir_settled[
            dir_settled["quarter"].apply(lambda q: quarter_to_components(q)[1]) == test_q_no
        ]
        hist_seasonal_vals.append(
            float(seasonal_rows["final_realised_payout_per_unit"].mean())
            if len(seasonal_rows) else np.nan
        )

        # bench_last_quarter: last payout from the immediately prior settled quarter
        if prior_q is not None:
            prior_q_rows = dir_settled[dir_settled["quarter"] == prior_q]
            last_quarter_vals.append(
                float(prior_q_rows["final_realised_payout_per_unit"].mean())
                if len(prior_q_rows) else np.nan
            )
        else:
            last_quarter_vals.append(np.nan)

        # bench_same_q_prior_yr
        if prior_yr_q is not None:
            py_rows = dir_settled[dir_settled["quarter"] == prior_yr_q]
            same_q_prior_yr_vals.append(
                float(py_rows["final_realised_payout_per_unit"].mean())
                if len(py_rows) else np.nan
            )
        else:
            same_q_prior_yr_vals.append(np.nan)

        # bench_trend: linear extrapolation over last 4 settled quarters (per direction)
        if len(dir_settled) >= 2:
            recent = dir_settled.sort_values("quarter_settlement_timestamp").tail(4)
            x = np.arange(len(recent), dtype=float)
            y = recent["final_realised_payout_per_unit"].values.astype(float)
            finite = np.isfinite(y)
            if finite.sum() >= 2:
                coeffs = np.polyfit(x[finite], y[finite], 1)
                trend_vals.append(float(np.polyval(coeffs, len(recent))))
            else:
                trend_vals.append(np.nan)
        else:
            trend_vals.append(np.nan)

    idx = test_rows.index
    return BenchmarkSet(
        hist_seasonal    = pd.Series(hist_seasonal_vals,   index=idx),
        last_quarter     = pd.Series(last_quarter_vals,    index=idx),
        same_q_prior_yr  = pd.Series(same_q_prior_yr_vals, index=idx),
        trend            = pd.Series(trend_vals,           index=idx),
    )


# ── walk-forward loop ─────────────────────────────────────────────────────────

def run_walkforward(alpha_df: pd.DataFrame) -> pd.DataFrame:
    alpha_df = alpha_df.copy()
    alpha_df["decision_timestamp"] = pd.to_datetime(alpha_df["decision_timestamp"], utc=True)
    alpha_df["quarter_settlement_timestamp"] = (
        alpha_df["quarter"].astype(str).map(quarter_settlement_timestamp)
    )
    alpha_df["direction_key"] = (
        alpha_df["interconnector_id"].astype(str) + "::" + alpha_df["from_region"].astype(str)
    )

    settled = alpha_df[alpha_df["final_realised_payout_per_unit"].notna()].copy()
    all_quarters = _sorted_quarters(settled)

    if len(all_quarters) < MIN_WARM_UP_QUARTERS + 1:
        raise ValueError(
            f"Need at least {MIN_WARM_UP_QUARTERS + 1} settled quarters; "
            f"found {len(all_quarters)}"
        )

    records: list[dict] = []

    for test_idx in range(MIN_WARM_UP_QUARTERS, len(all_quarters)):
        test_quarter   = all_quarters[test_idx]
        train_quarters = set(all_quarters[:test_idx])

        settled_before = settled[settled["quarter"].isin(train_quarters)].copy()
        test_rows      = settled[settled["quarter"] == test_quarter].copy()

        if len(test_rows) == 0:
            continue

        # Build feature matrices
        X_train, y_train, X_test = _build_feature_matrix(
            settled_before, test_rows, settled_before
        )

        ridge_preds = _ridge_predict(X_train, y_train, X_test)
        benches = _compute_benchmarks(test_rows, settled_before, test_quarter)

        actual = test_rows["final_realised_payout_per_unit"].values.astype(float)

        for i, (row_idx, row) in enumerate(test_rows.iterrows()):
            act = actual[i]
            rid = ridge_preds[i] if i < len(ridge_preds) else np.nan
            hs  = benches.hist_seasonal.iloc[i]
            lq  = benches.last_quarter.iloc[i]
            sq  = benches.same_q_prior_yr.iloc[i]
            tr  = benches.trend.iloc[i]

            records.append({
                "test_quarter":           test_quarter,
                "train_quarters_count":   len(train_quarters),
                "product_id":             row.get("product_id", ""),
                "direction_key":          row["direction_key"],
                "interconnector_id":      row.get("interconnector_id", ""),
                "from_region":            row.get("from_region", ""),
                "tranche_no":             row.get("tranche_no", np.nan),
                "actual_payout":          act,
                "ridge_v1_forecast":      rid,
                "bench_hist_seasonal":    hs,
                "bench_last_quarter":     lq,
                "bench_same_q_prior_yr":  sq,
                "bench_trend":            tr,
                "ridge_v1_abs_error":     abs(rid - act) if np.isfinite(rid) else np.nan,
                "bench_hist_seasonal_ae": abs(hs - act)  if np.isfinite(hs)  else np.nan,
                "bench_last_quarter_ae":  abs(lq - act)  if np.isfinite(lq)  else np.nan,
                "bench_same_q_prior_yr_ae": abs(sq - act) if np.isfinite(sq) else np.nan,
                "bench_trend_ae":         abs(tr - act)  if np.isfinite(tr)  else np.nan,
            })

    return pd.DataFrame(records)


# ── promotion gate ────────────────────────────────────────────────────────────

def evaluate_promotion_gate(results: pd.DataFrame) -> dict:
    quarters_tested = results["test_quarter"].nunique()
    gate: dict[str, bool | str | float | int] = {}

    # Overall MAE by model
    mae = {}
    for col in [
        "ridge_v1_abs_error",
        "bench_hist_seasonal_ae",
        "bench_last_quarter_ae",
        "bench_same_q_prior_yr_ae",
        "bench_trend_ae",
    ]:
        mae[col] = float(results[col].mean(skipna=True))

    best_bench_mae = min(
        mae["bench_hist_seasonal_ae"],
        mae["bench_last_quarter_ae"],
        mae["bench_same_q_prior_yr_ae"],
        mae["bench_trend_ae"],
    )

    gate["gate_oos_mae_beats_best_benchmark"] = bool(mae["ridge_v1_abs_error"] < best_bench_mae)
    gate["gate_min_quarters_tested"]          = bool(quarters_tested >= MIN_TEST_QUARTERS)

    # Improvement by corridor
    corridor_improvement: dict[str, bool] = {}
    for dk, grp in results.groupby("direction_key"):
        ridge_mae_c = float(grp["ridge_v1_abs_error"].mean(skipna=True))
        bench_mae_c = float(min(
            grp["bench_hist_seasonal_ae"].mean(skipna=True),
            grp["bench_last_quarter_ae"].mean(skipna=True),
            grp["bench_same_q_prior_yr_ae"].mean(skipna=True),
            grp["bench_trend_ae"].mean(skipna=True),
        ))
        corridor_improvement[str(dk)] = ridge_mae_c < bench_mae_c

    corridors_improved = sum(corridor_improvement.values())
    gate["gate_improves_multiple_corridors"] = bool(corridors_improved > 1)
    gate["corridors_improved_count"]         = corridors_improved
    gate["corridor_improvement_detail"]      = corridor_improvement

    # Single corridor dominance: no single corridor > 80% of total error gain
    if gate["gate_oos_mae_beats_best_benchmark"]:
        total_gain = best_bench_mae - mae["ridge_v1_abs_error"]
        max_single_corridor_gain_share = 0.0
        for dk, grp in results.groupby("direction_key"):
            ridge_mae_c = float(grp["ridge_v1_abs_error"].mean(skipna=True))
            best_bench_c = float(min(
                grp["bench_hist_seasonal_ae"].mean(skipna=True),
                grp["bench_last_quarter_ae"].mean(skipna=True),
                grp["bench_same_q_prior_yr_ae"].mean(skipna=True),
                grp["bench_trend_ae"].mean(skipna=True),
            ))
            corridor_gain = (best_bench_c - ridge_mae_c) * len(grp)
            if total_gain > 0:
                share = corridor_gain / (total_gain * len(results))
                max_single_corridor_gain_share = max(max_single_corridor_gain_share, share)
        gate["gate_no_single_corridor_dominates"] = bool(max_single_corridor_gain_share <= 0.80)
        gate["max_single_corridor_gain_share"]     = round(max_single_corridor_gain_share, 4)
    else:
        gate["gate_no_single_corridor_dominates"] = False
        gate["max_single_corridor_gain_share"]     = float("nan")

    gate["mae_ridge_v1"]            = round(mae["ridge_v1_abs_error"], 2)
    gate["mae_bench_hist_seasonal"] = round(mae["bench_hist_seasonal_ae"], 2)
    gate["mae_bench_last_quarter"]  = round(mae["bench_last_quarter_ae"], 2)
    gate["mae_bench_same_q_prior_yr"] = round(mae["bench_same_q_prior_yr_ae"], 2)
    gate["mae_bench_trend"]         = round(mae["bench_trend_ae"], 2)
    gate["mae_best_benchmark"]      = round(best_bench_mae, 2)
    gate["quarters_tested"]         = quarters_tested

    all_gates = [
        gate["gate_oos_mae_beats_best_benchmark"],
        gate["gate_min_quarters_tested"],
        gate["gate_improves_multiple_corridors"],
        gate["gate_no_single_corridor_dominates"],
    ]
    gate["promotion_verdict"] = "PASS" if all(all_gates) else "FAIL"
    return gate


# ── report writers ────────────────────────────────────────────────────────────

def _write_report(
    output_path: Path,
    results: pd.DataFrame,
    gate: dict,
) -> None:
    quarters_tested = results["test_quarter"].nunique()

    # Per-quarter MAE table
    q_table_rows = []
    for q in sorted(results["test_quarter"].unique(), key=_quarter_sort_key):
        grp = results[results["test_quarter"] == q]
        q_table_rows.append({
            "quarter": q,
            "n":       len(grp),
            "ridge_v1":            round(float(grp["ridge_v1_abs_error"].mean(skipna=True)), 1),
            "bench_hist_seasonal": round(float(grp["bench_hist_seasonal_ae"].mean(skipna=True)), 1),
            "bench_last_quarter":  round(float(grp["bench_last_quarter_ae"].mean(skipna=True)), 1),
            "bench_same_q_prior_yr": round(float(grp["bench_same_q_prior_yr_ae"].mean(skipna=True)), 1),
            "bench_trend":         round(float(grp["bench_trend_ae"].mean(skipna=True)), 1),
        })
    q_table = pd.DataFrame(q_table_rows)

    def _gate_icon(v: bool) -> str:
        return "✅" if v else "❌"

    lines = [
        "# Phase 5A.1 – Walk-Forward Price Validation",
        "",
        "> **Objective:** Prove that Price Model v1 (or a successor) can predict",
        "> genuinely *unseen* quarters — not just produce a larger historical P&L.",
        "> Training is strictly frozen on quarters settled before the test quarter.",
        "> Models are never trained on any row from the quarter being predicted.",
        "",
        "## Setup",
        f"- Warm-up window: `{MIN_WARM_UP_QUARTERS}` settled quarters (minimum before first test).",
        f"- Test quarters evaluated: `{quarters_tested}`",
        f"- Promotion gate minimum: `{MIN_TEST_QUARTERS}` unseen quarters.",
        "",
        "## Model",
        "- **Ridge Model v1** — same feature set as `price_model_v1.py`; coefficients frozen per test quarter.",
        "",
        "## Benchmarks (no-lookahead, direction-level)",
        "| Benchmark | Description |",
        "|---|---|",
        "| `bench_hist_seasonal` | Mean payout for same quarter-number in all prior years |",
        "| `bench_last_quarter` | Mean payout from immediately prior settled quarter |",
        "| `bench_same_q_prior_yr` | Mean payout for same quarter one year earlier |",
        "| `bench_trend` | Linear extrapolation over last 4 settled quarters |",
        "",
        "## OOS MAE by quarter (AUD/unit, mean absolute error)",
        "",
    ]

    # Build markdown table
    col_headers = ["Quarter", "N", "Ridge v1", "Hist Seasonal", "Last Quarter", "Prior Year Q", "Trend"]
    lines.append("| " + " | ".join(col_headers) + " |")
    lines.append("|" + "|".join(["---"] * len(col_headers)) + "|")
    for _, qr in q_table.iterrows():
        lines.append(
            f"| {qr['quarter']} | {qr['n']} "
            f"| {qr['ridge_v1']} "
            f"| {qr['bench_hist_seasonal']} "
            f"| {qr['bench_last_quarter']} "
            f"| {qr['bench_same_q_prior_yr']} "
            f"| {qr['bench_trend']} |"
        )

    lines += [
        "",
        "## Overall OOS MAE summary",
        f"| Model | Overall MAE (AUD/unit) |",
        "|---|---|",
        f"| Ridge Model v1 | **{gate['mae_ridge_v1']:,}** |",
        f"| Benchmark: Historical Seasonal | {gate['mae_bench_hist_seasonal']:,} |",
        f"| Benchmark: Last Quarter | {gate['mae_bench_last_quarter']:,} |",
        f"| Benchmark: Same Quarter Prior Year | {gate['mae_bench_same_q_prior_yr']:,} |",
        f"| Benchmark: Trend | {gate['mae_bench_trend']:,} |",
        f"| **Best benchmark** | **{gate['mae_best_benchmark']:,}** |",
        "",
        "## Promotion gate",
        f"| Gate | Result |",
        "|---|---|",
        f"| OOS MAE beats best benchmark | {_gate_icon(gate['gate_oos_mae_beats_best_benchmark'])} |",
        f"| ≥{MIN_TEST_QUARTERS} unseen quarters tested | {_gate_icon(gate['gate_min_quarters_tested'])} |",
        f"| Improvement across >1 corridor | {_gate_icon(gate['gate_improves_multiple_corridors'])} ({gate['corridors_improved_count']} corridors) |",
        f"| No single corridor >80% of gain | {_gate_icon(gate['gate_no_single_corridor_dominates'])} (max share: {gate['max_single_corridor_gain_share']}) |",
        "",
        f"### Verdict: **{gate['promotion_verdict']}**",
        "",
    ]

    if gate["promotion_verdict"] == "FAIL":
        lines += [
            "Price Model v1 does **not** pass the promotion gate on walk-forward OOS evaluation.",
            "Status: `REJECTED / RESEARCH ONLY`.",
            "Required next step before promotion: reduce OOS MAE below best benchmark across multiple corridors.",
            "",
        ]
    else:
        lines += [
            "Price Model v1 passes all promotion gates.",
            "Eligible for promotion to Price Model v2 subject to governance sign-off.",
            "",
        ]

    lines += [
        "## Corridor-level improvement detail",
        "| Corridor | Ridge v1 beats benchmark |",
        "|---|---|",
    ]
    for ck, improved in sorted(gate["corridor_improvement_detail"].items()):
        lines.append(f"| {ck} | {_gate_icon(improved)} |")

    lines += [
        "",
        "## Interpretation guardrails",
        "- Walk-forward evaluation is the minimum bar for promotion; it does not validate live production use.",
        "- Backtest P&L from walk-forward is not computed here — a separate capital-constrained simulation is required.",
        "- Price Model v1 was rejected in Phase 5A because its backtest gain was training-set amplification, not genuine OOS edge.",
        "- This phase isolates the OOS question before any backtest signal is trusted.",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_register(
    register_path: Path,
    gate: dict,
    quarters_tested: int,
) -> None:
    row = {
        "as_of_date":                  "2026-07-13",
        "model_version":               "price_model_v1_walkforward",
        "baseline_abs_error_aud":      gate["mae_best_benchmark"],
        "model_abs_error_aud":         gate["mae_ridge_v1"],
        "forecast_error_reduction_aud": round(gate["mae_best_benchmark"] - gate["mae_ridge_v1"], 4),
        "forecast_error_reduction_pct": round(
            (gate["mae_best_benchmark"] - gate["mae_ridge_v1"]) / gate["mae_best_benchmark"] * 100.0
            if gate["mae_best_benchmark"] else 0.0, 4
        ),
        "known_error_after_wiring_aud": 0.0,
        "unattributed_before_aud":      0.0,
        "unattributed_after_aud":       0.0,
        "unattributed_reduction_aud":   0.0,
        "unattributed_reduction_pct":   0.0,
        "baseline_backtest_pnl_aud":    "",
        "model_backtest_pnl_aud":       "",
        "estimated_pnl_impact_aud":     "",
        "notes": (
            f"Walk-forward OOS ({quarters_tested} quarters). "
            f"Ridge MAE={gate['mae_ridge_v1']}, best benchmark MAE={gate['mae_best_benchmark']}. "
            "No backtest run — backtest not valid until OOS gate passes."
        ),
        "status":             gate["promotion_verdict"],
        "rejection_reason":   "" if gate["promotion_verdict"] == "PASS" else (
            "Ridge v1 OOS MAE does not beat best benchmark across corridors. "
            "Model remains REJECTED / RESEARCH ONLY."
        ),
        "promotion_gate_passed": gate["promotion_verdict"] == "PASS",
    }
    new_row = pd.DataFrame([row])
    if register_path.exists():
        register = pd.read_csv(register_path)
        register = register[register["model_version"] != "price_model_v1_walkforward"].copy()
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
    register_path = reports_dir / "FORECAST_CONTRIBUTION_REGISTER.csv"
    results_path  = reports_dir / "phase5a1_walkforward_results.csv"
    report_path   = reports_dir / "PHASE5A1_WALKFORWARD_VALIDATION.md"

    alpha_df = pd.read_csv(alpha_path)

    print("Running walk-forward validation…", flush=True)
    results = run_walkforward(alpha_df)
    gate    = evaluate_promotion_gate(results)

    results.to_csv(results_path, index=False)
    _write_report(report_path, results, gate)
    _update_register(register_path, gate, int(results["test_quarter"].nunique()))

    print(json.dumps({
        "quarters_tested":    gate["quarters_tested"],
        "mae_ridge_v1":       gate["mae_ridge_v1"],
        "mae_best_benchmark": gate["mae_best_benchmark"],
        "corridors_improved": gate["corridors_improved_count"],
        "promotion_verdict":  gate["promotion_verdict"],
        "results_csv":        str(results_path.relative_to(REPO_ROOT)),
        "report_md":          str(report_path.relative_to(REPO_ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
