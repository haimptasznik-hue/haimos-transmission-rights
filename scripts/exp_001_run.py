#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"


def _linear_regression_metrics(frame: pd.DataFrame) -> tuple[np.ndarray, float, float]:
    y = frame["mwflow"].to_numpy(dtype=float)
    x = frame[["net_balance_nsw_mw", "net_balance_qld_mw"]].to_numpy(dtype=float)
    x = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    pred = x @ beta
    residual = y - pred

    sse = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - (sse / sst) if sst > 0 else float("nan")
    mae = float(np.mean(np.abs(residual)))
    return pred, r2, mae


def _spearman(series_a: pd.Series, series_b: pd.Series) -> float:
    ranked_a = series_a.rank(method="average")
    ranked_b = series_b.rank(method="average")
    return float(ranked_a.corr(ranked_b, method="pearson"))


def _segment_metric(frame: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    rows = []
    for key, group in frame.groupby(segment_col):
        if len(group) < 10:
            continue
        pearson = group["balance_difference_mw"].corr(group["mwflow"], method="pearson")
        spearman = _spearman(group["balance_difference_mw"], group["mwflow"])
        pred, r2, _ = _linear_regression_metrics(group)
        rows.append(
            {
                "segment_type": segment_col,
                "segment": str(key),
                "n": int(len(group)),
                "pearson": float(pearson),
                "spearman": float(spearman),
                "r2": float(r2),
                "mean_abs_residual": float(np.mean(np.abs(group["mwflow"].to_numpy() - pred))),
            }
        )
    return pd.DataFrame(rows)


def _verdict(
    *,
    r2: float,
    sign_accuracy: float,
    overall_spearman: float,
    monthly_spearman: pd.Series,
    peak_offpeak_spearman: pd.Series,
    weekday_weekend_spearman: pd.Series,
) -> tuple[str, str]:
    acceptance_r2 = r2 > 0.5
    acceptance_sign = sign_accuracy > 0.90

    stable_monthly = bool((monthly_spearman > 0).all()) if len(monthly_spearman) else False
    stable_peak = bool((peak_offpeak_spearman > 0).all()) if len(peak_offpeak_spearman) else False
    stable_week = bool((weekday_weekend_spearman > 0).all()) if len(weekday_weekend_spearman) else False

    if not acceptance_r2 or not acceptance_sign:
        return "REJECTED", "Core acceptance threshold failure (R² or directional accuracy)."

    if overall_spearman <= 0 or not (stable_monthly and stable_peak and stable_week):
        return "INCONCLUSIVE", "Core fit passes but robustness/spearman stability is insufficient."

    return (
        "CONDITIONALLY_ACCEPTED",
        "Core criteria passed; controls and multi-window historical reproducibility still pending pre-registered follow-up.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EXP_001 pre-registered test")
    parser.add_argument(
        "--input",
        type=Path,
        default=REPORTS_DIR / "EXP_001_PREPARED_DATA.csv",
        help="Prepared dataset CSV path",
    )
    parser.add_argument(
        "--results-csv",
        type=Path,
        default=REPORTS_DIR / "EXP_001_RESULTS.csv",
        help="Output results CSV",
    )
    parser.add_argument(
        "--results-md",
        type=Path,
        default=REPORTS_DIR / "EXP_001_RESULTS.md",
        help="Output results markdown",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Prepared dataset not found: {args.input}")

    frame = pd.read_csv(args.input)
    frame["settlement_ts"] = pd.to_datetime(frame["settlement_timestamp_utc"], utc=True, errors="coerce")

    required = [
        "balance_difference_mw",
        "mwflow",
        "net_balance_nsw_mw",
        "net_balance_qld_mw",
        "expected_flow_direction_from_balance",
        "actual_qni_flow_direction",
        "utilisation_pct",
    ]
    frame = frame.dropna(subset=required).copy()

    frame["month"] = frame["settlement_ts"].dt.to_period("M").astype(str)
    frame["hour"] = frame["settlement_ts"].dt.hour
    frame["peak_bucket"] = np.where(frame["hour"].between(7, 21), "PEAK", "OFFPEAK")
    frame["week_bucket"] = np.where(frame["settlement_ts"].dt.dayofweek < 5, "WEEKDAY", "WEEKEND")

    pearson = float(frame["balance_difference_mw"].corr(frame["mwflow"], method="pearson"))
    spearman = _spearman(frame["balance_difference_mw"], frame["mwflow"])

    pred, r2, mae = _linear_regression_metrics(frame)
    frame["prediction_mw"] = pred
    frame["residual_mw"] = frame["mwflow"] - frame["prediction_mw"]

    non_neutral = frame[
        (frame["expected_flow_direction_from_balance"] != "NO_FLOW")
        & (frame["actual_qni_flow_direction"] != "NO_FLOW")
    ]
    directional_sign_accuracy = float(
        (non_neutral["expected_flow_direction_from_balance"] == non_neutral["actual_qni_flow_direction"]).mean()
    )

    imbalance_threshold = float(frame["balance_difference_mw"].abs().quantile(0.75))
    high_imbalance = frame[frame["balance_difference_mw"].abs() >= imbalance_threshold]
    high_imbalance_congestion_rate = float((high_imbalance["utilisation_pct"] >= 80.0).mean())

    segment_month = _segment_metric(frame, "month")
    segment_peak = _segment_metric(frame, "peak_bucket")
    segment_week = _segment_metric(frame, "week_bucket")

    stability_monthly = bool((segment_month["spearman"] > 0).all()) if not segment_month.empty else False
    stability_peak_offpeak = bool((segment_peak["spearman"] > 0).all()) if not segment_peak.empty else False
    stability_weekday_weekend = bool((segment_week["spearman"] > 0).all()) if not segment_week.empty else False
    stability_result = (
        "STABLE"
        if (stability_monthly and stability_peak_offpeak and stability_weekday_weekend)
        else "UNSTABLE_OR_PARTIAL"
    )

    worst = frame.iloc[frame["residual_mw"].abs().idxmax()]
    dominant_residual = (
        f"Largest residual at {worst['settlement_timestamp_utc']} with |residual|={abs(float(worst['residual_mw'])):.3f} MW; "
        f"utilisation={float(worst['utilisation_pct']):.2f}%"
    )

    verdict, verdict_reason = _verdict(
        r2=r2,
        sign_accuracy=directional_sign_accuracy,
        overall_spearman=spearman,
        monthly_spearman=segment_month["spearman"] if not segment_month.empty else pd.Series(dtype=float),
        peak_offpeak_spearman=segment_peak["spearman"] if not segment_peak.empty else pd.Series(dtype=float),
        weekday_weekend_spearman=segment_week["spearman"] if not segment_week.empty else pd.Series(dtype=float),
    )

    metrics = pd.DataFrame(
        [
            {"metric": "pearson_correlation", "value": pearson},
            {"metric": "spearman_correlation", "value": spearman},
            {"metric": "r2", "value": r2},
            {"metric": "mae_mw", "value": mae},
            {"metric": "directional_sign_accuracy", "value": directional_sign_accuracy},
            {"metric": "high_imbalance_congestion_rate", "value": high_imbalance_congestion_rate},
            {"metric": "stability_monthly", "value": float(stability_monthly)},
            {"metric": "stability_peak_offpeak", "value": float(stability_peak_offpeak)},
            {"metric": "stability_weekday_weekend", "value": float(stability_weekday_weekend)},
            {"metric": "verdict", "value": verdict},
        ]
    )

    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.results_csv, index=False)

    lines = [
        "# EXP_001 Results",
        "",
        "## Locked Contract",
        "- R² acceptance threshold: `> 0.5`",
        "- Directional accuracy acceptance threshold: `> 0.90`",
        "- QNI sign convention: positive `MWFLOW = NSW1->QLD1`, negative `MWFLOW = QLD1->NSW1`",
        "",
        "## Core Metrics",
        f"- Pearson correlation: `{pearson:.6f}`",
        f"- Spearman correlation: `{spearman:.6f}`",
        f"- R²: `{r2:.6f}`",
        f"- MAE (MW): `{mae:.6f}`",
        f"- Directional sign accuracy: `{directional_sign_accuracy:.6f}`",
        f"- High-imbalance congestion rate: `{high_imbalance_congestion_rate:.6f}`",
        "",
        "## Stability",
        f"- Monthly stability (Spearman > 0 in each month): `{stability_monthly}`",
        f"- Peak vs off-peak stability: `{stability_peak_offpeak}`",
        f"- Weekday vs weekend stability: `{stability_weekday_weekend}`",
        f"- Stability result: `{stability_result}`",
        "",
        "## Residual Analysis",
        f"- Dominant unexplained residual: {dominant_residual}",
        "",
        "## Verdict",
        f"- LAW_001 classification: `{verdict}`",
        f"- Reason: {verdict_reason}",
        "",
        "## Recommended Next Experiment",
        "- `EXP_002`: Replicate LAW_001 across additional historical windows (e.g., 2020Q1 + 2025 windows) and constrained/unconstrained partitions with unchanged thresholds.",
        "",
    ]
    args.results_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Pearson: {pearson:.6f}")
    print(f"Spearman: {spearman:.6f}")
    print(f"R2: {r2:.6f}")
    print(f"Directional accuracy: {directional_sign_accuracy:.6f}")
    print(f"Verdict: {verdict}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
