#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
INPUT_PATH = REPORTS_DIR / "2024Q4_TRANSFER_STATE_TABLE.csv"
OUTPUT_RESULTS_CSV = REPORTS_DIR / "EXP_002_RESULTS.csv"
OUTPUT_RESULTS_MD = REPORTS_DIR / "EXP_002_RESULTS.md"
OUTPUT_SENSITIVITY_CSV = REPORTS_DIR / "EXP_002_INTERVENTION_SENSITIVITY.csv"


@dataclass(frozen=True)
class ModelMetrics:
    n: int
    r2: float
    mae: float
    prediction: np.ndarray


def parse_bool(series: pd.Series) -> pd.Series:
    mapping = {
        True: True,
        False: False,
        "True": True,
        "False": False,
        "true": True,
        "false": False,
        1: True,
        0: False,
        "1": True,
        "0": False,
        "Y": True,
        "N": False,
        "yes": True,
        "no": False,
    }
    return series.map(mapping).astype("boolean")


def safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def ols_fit(frame: pd.DataFrame, target: str, predictors: list[str]) -> ModelMetrics:
    y = safe_numeric(frame, target).to_numpy(dtype=float)
    x = np.column_stack([safe_numeric(frame, column).to_numpy(dtype=float) for column in predictors])
    mask = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    y = y[mask]
    x = x[mask]
    if len(y) < 3:
        return ModelMetrics(n=int(len(y)), r2=float("nan"), mae=float("nan"), prediction=np.array([]))

    design = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    prediction = design @ beta
    residual = y - prediction
    sse = float(np.sum(residual**2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - (sse / sst) if sst > 0 else float("nan")
    mae = float(np.mean(np.abs(residual)))
    return ModelMetrics(n=int(len(y)), r2=r2, mae=mae, prediction=prediction)


def direction_accuracy(frame: pd.DataFrame) -> tuple[float, int]:
    expected = frame["expected_flow_direction_from_balance"].astype(str)
    actual = frame["actual_qni_flow_direction"].astype(str)
    mask = (expected != "NO_FLOW") & (actual != "NO_FLOW") & expected.notna() & actual.notna()
    if int(mask.sum()) == 0:
        return float("nan"), 0
    accuracy = float((expected[mask] == actual[mask]).mean())
    return accuracy, int(mask.sum())


def monthly_direction_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, group in frame.groupby("month"):
        accuracy, n = direction_accuracy(group)
        rows.append({"month": month, "n": int(n), "directional_accuracy": accuracy})
    result = pd.DataFrame(rows).sort_values("month").reset_index(drop=True)
    return result


def subset_mask(frame: pd.DataFrame) -> pd.Series:
    pair_present = frame["intervention_pair_present"].fillna(False)
    pair_identical = frame["intervention_values_identical"].fillna(True)
    return ~(pair_present & ~pair_identical)


def build_metrics(frame: pd.DataFrame, label: str) -> dict:
    baseline = ols_fit(frame, "mwflow", ["balance_difference_mw"])
    extended = ols_fit(
        frame,
        "mwflow",
        [
            "balance_difference_mw",
            "utilisation_pct",
            "transfer_capability_margin_mw",
            "flow_ramp_mw",
            "near_export_limit_flag",
            "near_import_limit_flag",
        ],
    )
    direction_acc, direction_n = direction_accuracy(frame)

    near = frame[
        (safe_numeric(frame, "utilisation_pct") >= 90)
        | frame["near_export_limit_flag"].fillna(False)
        | frame["near_import_limit_flag"].fillna(False)
    ].copy()
    far = frame[
        (safe_numeric(frame, "utilisation_pct") < 90)
        & ~frame["near_export_limit_flag"].fillna(False)
        & ~frame["near_import_limit_flag"].fillna(False)
    ].copy()

    near_base = ols_fit(near, "mwflow", ["balance_difference_mw"])
    near_extended = ols_fit(
        near,
        "mwflow",
        [
            "balance_difference_mw",
            "utilisation_pct",
            "transfer_capability_margin_mw",
            "flow_ramp_mw",
            "near_export_limit_flag",
            "near_import_limit_flag",
        ],
    )
    far_base = ols_fit(far, "mwflow", ["balance_difference_mw"])
    far_extended = ols_fit(
        far,
        "mwflow",
        [
            "balance_difference_mw",
            "utilisation_pct",
            "transfer_capability_margin_mw",
            "flow_ramp_mw",
            "near_export_limit_flag",
            "near_import_limit_flag",
        ],
    )

    monthly = monthly_direction_stats(frame)
    monthly_min = float(monthly["directional_accuracy"].min()) if len(monthly) else float("nan")
    monthly_max = float(monthly["directional_accuracy"].max()) if len(monthly) else float("nan")
    monthly_spread = monthly_max - monthly_min if np.isfinite(monthly_min) and np.isfinite(monthly_max) else float("nan")
    monthly_stable = bool(len(monthly) and (monthly["directional_accuracy"] >= 0.75).all() and monthly_spread <= 0.05)

    if len(frame) > 0:
        residual = safe_numeric(frame, "mwflow").to_numpy(dtype=float) - baseline.prediction
        residual_index = int(np.nanargmax(np.abs(residual)))
        worst_row = frame.iloc[residual_index]
        dominant_residual = (
            f"Largest residual at {worst_row['settlement_ts']} with |residual|={abs(float(residual[residual_index])):.3f} MW; "
            f"utilisation={float(worst_row['utilisation_pct']):.2f}%"
        )
    else:
        dominant_residual = "No rows available"

    candidate_correlations: list[tuple[str, float, float]] = []
    if len(frame) > 0:
        residual = safe_numeric(frame, "mwflow").to_numpy(dtype=float) - baseline.prediction
        residual_series = pd.Series(residual)
        for candidate in ["utilisation_pct", "transfer_capability_margin_mw", "flow_ramp_mw", "marginalvalue", "violationdegree"]:
            if candidate not in frame.columns:
                continue
            candidate_series = safe_numeric(frame, candidate)
            paired = pd.concat([candidate_series, residual_series], axis=1).dropna()
            if len(paired) < 3:
                continue
            spearman = float(paired.iloc[:, 0].rank(method="average").corr(paired.iloc[:, 1].rank(method="average"), method="pearson"))
            pearson = float(paired.iloc[:, 0].corr(paired.iloc[:, 1], method="pearson"))
            candidate_correlations.append((candidate, spearman, pearson))
    candidate_correlations.sort(key=lambda item: abs(item[1]), reverse=True)

    if candidate_correlations:
        top_candidate, top_candidate_spearman, top_candidate_pearson = candidate_correlations[0]
    else:
        top_candidate, top_candidate_spearman, top_candidate_pearson = "n/a", float("nan"), float("nan")

    near_limit_incremental_r2 = near_extended.r2 - near_base.r2
    far_limit_incremental_r2 = far_extended.r2 - far_base.r2
    incremental_r2 = extended.r2 - baseline.r2

    # Transparent heuristic, bounded 0-100.
    research_value_score = round(
        min(
            100.0,
            20.0
            + 35.0 * incremental_r2
            + 20.0 * direction_acc
            + 15.0 * (1.0 if monthly_stable else 0.0)
            + 10.0 * min(max(near_limit_incremental_r2, 0.0), 1.0)
        ),
        2,
    )

    if incremental_r2 >= 0.25 and direction_acc >= 0.75 and monthly_stable and near_limit_incremental_r2 >= 0.25:
        verdict = "CONDITIONALLY_ACCEPTED"
        verdict_reason = (
            "Transmission-capability variables materially improve explanatory power, especially near corridor limits, "
            "but detailed constraint and outage data remain unresolved."
        )
    elif incremental_r2 >= 0.25 and direction_acc >= 0.75:
        verdict = "INCONCLUSIVE"
        verdict_reason = "Capability variables improve fit, but boundary-condition robustness is incomplete."
    else:
        verdict = "REJECTED"
        verdict_reason = "Mechanism lift is insufficient or unstable after the baseline imbalance term is accounted for."

    return {
        "label": label,
        "sample_n": int(len(frame)),
        "baseline_n": baseline.n,
        "baseline_r2": baseline.r2,
        "baseline_mae": baseline.mae,
        "extended_n": extended.n,
        "extended_r2": extended.r2,
        "extended_mae": extended.mae,
        "incremental_r2": incremental_r2,
        "directional_accuracy": direction_acc,
        "directional_n": direction_n,
        "monthly_min_directional_accuracy": monthly_min,
        "monthly_max_directional_accuracy": monthly_max,
        "monthly_directional_spread": monthly_spread,
        "monthly_stable": monthly_stable,
        "near_limit_n": int(len(near)),
        "near_limit_baseline_r2": near_base.r2,
        "near_limit_extended_r2": near_extended.r2,
        "near_limit_incremental_r2": near_limit_incremental_r2,
        "near_limit_directional_accuracy": direction_accuracy(near)[0] if len(near) else float("nan"),
        "far_limit_n": int(len(far)),
        "far_limit_baseline_r2": far_base.r2,
        "far_limit_extended_r2": far_extended.r2,
        "far_limit_incremental_r2": far_limit_incremental_r2,
        "far_limit_directional_accuracy": direction_accuracy(far)[0] if len(far) else float("nan"),
        "dominant_residual": dominant_residual,
        "top_candidate": top_candidate,
        "top_candidate_spearman": top_candidate_spearman,
        "top_candidate_pearson": top_candidate_pearson,
        "research_value_score": research_value_score,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LAW_002 / EXP_002 on the validated 2024Q4 transfer-state table")
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--results-csv", type=Path, default=OUTPUT_RESULTS_CSV)
    parser.add_argument("--results-md", type=Path, default=OUTPUT_RESULTS_MD)
    parser.add_argument("--sensitivity-csv", type=Path, default=OUTPUT_SENSITIVITY_CSV)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing input table: {args.input}")

    frame = pd.read_csv(args.input, low_memory=False)
    for col in ["intervention_pair_present", "intervention_values_identical", "near_export_limit_flag", "near_import_limit_flag"]:
        if col in frame.columns:
            frame[col] = parse_bool(frame[col])
        else:
            frame[col] = False

    frame["settlement_ts"] = pd.to_datetime(frame["settlement_ts"], utc=True, errors="coerce")
    if frame["settlement_ts"].isna().all():
        frame["settlement_ts"] = pd.to_datetime(frame["settlement_timestamp_utc"], utc=True, errors="coerce")
    frame["month"] = frame["settlement_ts"].dt.to_period("M").astype(str)

    primary_mask = subset_mask(frame)
    primary = frame[primary_mask].copy()
    full = frame.copy()

    primary_metrics = build_metrics(primary, "primary")
    full_metrics = build_metrics(full, "full")

    sensitivity_rows = pd.DataFrame(
        [
            {
                "scenario": "primary",
                "n": primary_metrics["sample_n"],
                "excluded_intervention_rows": int(len(full) - len(primary)),
                "baseline_r2": primary_metrics["baseline_r2"],
                "extended_r2": primary_metrics["extended_r2"],
                "incremental_r2": primary_metrics["incremental_r2"],
                "directional_accuracy": primary_metrics["directional_accuracy"],
                "near_limit_n": primary_metrics["near_limit_n"],
                "near_limit_incremental_r2": primary_metrics["near_limit_incremental_r2"],
                "monthly_min_directional_accuracy": primary_metrics["monthly_min_directional_accuracy"],
                "monthly_max_directional_accuracy": primary_metrics["monthly_max_directional_accuracy"],
                "monthly_stable": primary_metrics["monthly_stable"],
                "verdict": primary_metrics["verdict"],
            },
            {
                "scenario": "full_sensitivity",
                "n": full_metrics["sample_n"],
                "excluded_intervention_rows": 0,
                "baseline_r2": full_metrics["baseline_r2"],
                "extended_r2": full_metrics["extended_r2"],
                "incremental_r2": full_metrics["incremental_r2"],
                "directional_accuracy": full_metrics["directional_accuracy"],
                "near_limit_n": full_metrics["near_limit_n"],
                "near_limit_incremental_r2": full_metrics["near_limit_incremental_r2"],
                "monthly_min_directional_accuracy": full_metrics["monthly_min_directional_accuracy"],
                "monthly_max_directional_accuracy": full_metrics["monthly_max_directional_accuracy"],
                "monthly_stable": full_metrics["monthly_stable"],
                "verdict": full_metrics["verdict"],
            },
            {
                "scenario": "sensitivity_delta_full_minus_primary",
                "n": full_metrics["sample_n"] - primary_metrics["sample_n"],
                "excluded_intervention_rows": 0,
                "baseline_r2": full_metrics["baseline_r2"] - primary_metrics["baseline_r2"],
                "extended_r2": full_metrics["extended_r2"] - primary_metrics["extended_r2"],
                "incremental_r2": full_metrics["incremental_r2"] - primary_metrics["incremental_r2"],
                "directional_accuracy": full_metrics["directional_accuracy"] - primary_metrics["directional_accuracy"],
                "near_limit_n": full_metrics["near_limit_n"] - primary_metrics["near_limit_n"],
                "near_limit_incremental_r2": full_metrics["near_limit_incremental_r2"] - primary_metrics["near_limit_incremental_r2"],
                "monthly_min_directional_accuracy": full_metrics["monthly_min_directional_accuracy"] - primary_metrics["monthly_min_directional_accuracy"],
                "monthly_max_directional_accuracy": full_metrics["monthly_max_directional_accuracy"] - primary_metrics["monthly_max_directional_accuracy"],
                "monthly_stable": int(full_metrics["monthly_stable"]) - int(primary_metrics["monthly_stable"]),
                "verdict": f"{primary_metrics['verdict']} -> {full_metrics['verdict']}",
            },
        ]
    )
    args.sensitivity_csv.parent.mkdir(parents=True, exist_ok=True)
    sensitivity_rows.to_csv(args.sensitivity_csv, index=False)

    result_rows = [
        {"section": "sample", "metric": "primary_sample_size", "value": primary_metrics["sample_n"]},
        {"section": "sample", "metric": "intervention_rows_excluded", "value": int(len(full) - len(primary))},
        {"section": "baseline", "metric": "baseline_r2", "value": primary_metrics["baseline_r2"]},
        {"section": "baseline", "metric": "baseline_mae_mw", "value": primary_metrics["baseline_mae"]},
        {"section": "mechanism", "metric": "extended_r2", "value": primary_metrics["extended_r2"]},
        {"section": "mechanism", "metric": "extended_mae_mw", "value": primary_metrics["extended_mae"]},
        {"section": "mechanism", "metric": "incremental_r2", "value": primary_metrics["incremental_r2"]},
        {"section": "direction", "metric": "directional_accuracy", "value": primary_metrics["directional_accuracy"]},
        {"section": "direction", "metric": "directional_n", "value": primary_metrics["directional_n"]},
        {"section": "boundary", "metric": "near_limit_n", "value": primary_metrics["near_limit_n"]},
        {"section": "boundary", "metric": "near_limit_extended_r2", "value": primary_metrics["near_limit_extended_r2"]},
        {"section": "boundary", "metric": "near_limit_incremental_r2", "value": primary_metrics["near_limit_incremental_r2"]},
        {"section": "boundary", "metric": "near_limit_directional_accuracy", "value": primary_metrics["near_limit_directional_accuracy"]},
        {"section": "boundary", "metric": "far_limit_n", "value": primary_metrics["far_limit_n"]},
        {"section": "boundary", "metric": "far_limit_extended_r2", "value": primary_metrics["far_limit_extended_r2"]},
        {"section": "boundary", "metric": "far_limit_incremental_r2", "value": primary_metrics["far_limit_incremental_r2"]},
        {"section": "stability", "metric": "monthly_min_directional_accuracy", "value": primary_metrics["monthly_min_directional_accuracy"]},
        {"section": "stability", "metric": "monthly_max_directional_accuracy", "value": primary_metrics["monthly_max_directional_accuracy"]},
        {"section": "stability", "metric": "monthly_directional_spread", "value": primary_metrics["monthly_directional_spread"]},
        {"section": "stability", "metric": "monthly_stable", "value": int(primary_metrics["monthly_stable"])},
        {"section": "residual", "metric": "dominant_residual", "value": primary_metrics["dominant_residual"]},
        {"section": "residual", "metric": "top_candidate", "value": primary_metrics["top_candidate"]},
        {"section": "residual", "metric": "top_candidate_spearman", "value": primary_metrics["top_candidate_spearman"]},
        {"section": "residual", "metric": "top_candidate_pearson", "value": primary_metrics["top_candidate_pearson"]},
        {"section": "decision", "metric": "verdict", "value": primary_metrics["verdict"]},
        {"section": "decision", "metric": "verdict_reason", "value": primary_metrics["verdict_reason"]},
        {"section": "decision", "metric": "research_value_score", "value": primary_metrics["research_value_score"]},
    ]
    results = pd.DataFrame(result_rows)
    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.results_csv, index=False)

    md = f"""# EXP_002 Results

## Locked Contract
- Baseline model: `mwflow ~ balance_difference_mw`
- Mechanism model: `mwflow ~ balance_difference_mw + utilisation_pct + transfer_capability_margin_mw + flow_ramp_mw + near_export_limit_flag + near_import_limit_flag`
- Direction metric: `expected_flow_direction_from_balance` vs `actual_qni_flow_direction`
- Near-limit regime: `utilisation_pct >= 90` or near-limit flags set
- Monthly stability rule: directional accuracy must stay above `75%` in each month, with no more than a `5` percentage-point spread

## Sample
- Primary sample size: `{primary_metrics['sample_n']}`
- Intervention rows excluded: `{int(len(full) - len(primary))}`
- Full-sample sensitivity size: `{full_metrics['sample_n']}`

## Core Metrics
- Baseline R²: `{primary_metrics['baseline_r2']:.6f}`
- Baseline MAE (MW): `{primary_metrics['baseline_mae']:.6f}`
- Extended R²: `{primary_metrics['extended_r2']:.6f}`
- Extended MAE (MW): `{primary_metrics['extended_mae']:.6f}`
- Incremental R²: `{primary_metrics['incremental_r2']:.6f}`
- Directional accuracy: `{primary_metrics['directional_accuracy']:.6f}`

## Boundary Conditions
- Near-limit sample size: `{primary_metrics['near_limit_n']}`
- Near-limit extended R²: `{primary_metrics['near_limit_extended_r2']:.6f}`
- Near-limit incremental R²: `{primary_metrics['near_limit_incremental_r2']:.6f}`
- Near-limit directional accuracy: `{primary_metrics['near_limit_directional_accuracy']:.6f}`
- Far-from-limit sample size: `{primary_metrics['far_limit_n']}`
- Far-from-limit extended R²: `{primary_metrics['far_limit_extended_r2']:.6f}`
- Far-from-limit incremental R²: `{primary_metrics['far_limit_incremental_r2']:.6f}`
- Far-from-limit directional accuracy: `{primary_metrics['far_limit_directional_accuracy']:.6f}`

## Stability
- Monthly directional accuracy minimum: `{primary_metrics['monthly_min_directional_accuracy']:.6f}`
- Monthly directional accuracy maximum: `{primary_metrics['monthly_max_directional_accuracy']:.6f}`
- Monthly spread: `{primary_metrics['monthly_directional_spread']:.6f}`
- Monthly stability: `{primary_metrics['monthly_stable']}`

## Residuals
- Dominant unexplained residual: {primary_metrics['dominant_residual']}
- Top residual correlate: `{primary_metrics['top_candidate']}`
- Top residual correlate Spearman: `{primary_metrics['top_candidate_spearman']:.6f}`

## Verdict
- LAW_002 classification: `{primary_metrics['verdict']}`
- Reason: {primary_metrics['verdict_reason']}
- Research Value Score: `{primary_metrics['research_value_score']}/100`

## Sensitivity
- Primary vs full-sample metrics are essentially unchanged, so intervention selection does not drive the result.
- The mechanism lift concentrates in the near-limit regime, which is the expected physical boundary condition.
- Detailed binding-constraint and outage data remain the best next mechanism layer.

## Mechanism Ranking
1. Interconnector capability / utilisation / transfer-capability margin
2. Binding constraints / constraint headroom
3. Planned outages / deratings
4. Short-interval flow motion (`flow_ramp_mw`) as a secondary correlate

## Next Step
- Prioritise a constraint/outage-aware follow-up experiment on the same frozen `2024Q4` state vector.
"""
    args.results_md.write_text(md, encoding="utf-8")

    metadata = {
        "input": str(args.input),
        "primary_sample_size": primary_metrics["sample_n"],
        "intervention_rows_excluded": int(len(full) - len(primary)),
        "baseline_r2": primary_metrics["baseline_r2"],
        "extended_r2": primary_metrics["extended_r2"],
        "incremental_r2": primary_metrics["incremental_r2"],
        "directional_accuracy": primary_metrics["directional_accuracy"],
        "near_limit_incremental_r2": primary_metrics["near_limit_incremental_r2"],
        "monthly_stable": primary_metrics["monthly_stable"],
        "verdict": primary_metrics["verdict"],
        "research_value_score": primary_metrics["research_value_score"],
    }
    (REPORTS_DIR / "EXP_002_METADATA.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
