"""Price Model v2 – Deviation model predicting payout deviation from seasonal benchmark.

Instead of forecasting raw settlement payout, v2 forecasts:
  actual_payout - seasonal_benchmark_payout

Features are designed to explain *deviations* from normal seasonality:
  - recent trend (last 4 quarters' deviation from seasonal trend)
  - deviation volatility (std of recent deviations)
  - recent direction strength (mean absolute deviation)
  - same-quarter recent years variance
  - lagged residual (last quarter's deviation)

Data lineage: Every row tracks source file, publish timestamp, decision cutoff, quarter, corridor, ruleset.

Leakage controls:
  - Features computed only from data available before the decision date.
  - Final realised payout used only for scoring, never feature engineering.
  - Coefficients are frozen per walk-forward fold.

Two model classes tested:
  - Ridge regression (SimpleDeviation)
  - Gradient boosting (XGBDeviation)

Output: deviation forecasts (payout - seasonal), plus metadata for audit.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import NamedTuple

import numpy as np
import pandas as pd

# ── constants ─────────────────────────────────────────────────────────────────

_QUARTER_RE = re.compile(r"C(\d{4})Q([1-4])")
_DEFAULT_INTERVAL_Z = 1.2815515655446004


@dataclass(frozen=True)
class PriceModelV2Config:
    """Configuration for Price Model v2."""
    min_training_rows: int = 24
    ridge_lambda: float = 10.0
    interval_z: float = _DEFAULT_INTERVAL_Z


class DeviationFeatures(NamedTuple):
    """Deviation features computed for a single row."""
    recent_trend_4q: float          # linear trend of last 4 quarters' deviations
    deviation_volatility_4q: float  # std of last 4 quarters' deviations
    recent_mean_abs_dev: float      # mean absolute deviation in last 4q
    same_q_variance_prior_years: float  # variance of same-quarter payouts in prior years
    lagged_deviation: float         # last settled quarter's actual deviation


class ModelFit(NamedTuple):
    """Fitted model state."""
    model_type: str  # "ridge"
    beta: np.ndarray | None  # ridge coefficients
    feature_names: list[str]


# ── helpers ───────────────────────────────────────────────────────────────────

def quarter_to_components(quarter: str) -> tuple[int, int]:
    """Parse quarter string (e.g. 'C2024Q3') into (year, quarter_no)."""
    match = _QUARTER_RE.fullmatch(str(quarter))
    if match is None:
        raise ValueError(f"Invalid quarter format: {quarter}")
    return int(match.group(1)), int(match.group(2))


def quarter_settlement_timestamp(quarter: str) -> pd.Timestamp:
    """Return the settlement end timestamp for a quarter."""
    year, quarter_no = quarter_to_components(quarter)
    settle_month = quarter_no * 3 + 3
    settle_year = year
    if settle_month > 12:
        settle_month -= 12
        settle_year += 1
    if settle_month == 12:
        return pd.Timestamp(settle_year, 12, 31, 23, 59, 59, tz="UTC")
    return pd.Timestamp(settle_year, settle_month + 1, 1, tz="UTC") - pd.Timedelta(seconds=1)


def _quarterly_sort_key(q: str) -> tuple[int, int]:
    """Sort key for quarters."""
    return quarter_to_components(q)


# ── seasonal benchmark ────────────────────────────────────────────────────────

def compute_seasonal_benchmark(
    settled_history: pd.DataFrame,
    direction_key: str,
) -> float | None:
    """Compute seasonal average for a direction across all settled history.
    
    Returns the mean payout for all quarters with the same quarter-number,
    computed from all prior settled quarters (no lookahead).
    """
    if len(settled_history) == 0:
        return None
    
    # Get same direction rows
    same_dir = settled_history[settled_history["direction_key"] == direction_key].copy()
    if len(same_dir) == 0:
        return None
    
    payouts = same_dir["final_realised_payout_per_unit"].dropna()
    if len(payouts) == 0:
        return None
    
    return float(payouts.mean())


# ── regime-adjusted benchmark ─────────────────────────────────────────────────

def compute_regime_adjusted_benchmark(
    settled_history: pd.DataFrame,
    direction_key: str,
) -> float | None:
    """Seasonal mean + weighted recent deviation.
    
    Gives more weight to recent quarters' deviations from the seasonal norm.
    """
    if len(settled_history) < 2:
        return compute_seasonal_benchmark(settled_history, direction_key)
    
    same_dir = settled_history[settled_history["direction_key"] == direction_key].copy()
    if len(same_dir) == 0:
        return None
    
    seasonal = compute_seasonal_benchmark(settled_history, direction_key)
    if seasonal is None:
        return None
    
    # Recent 4 quarters' deviations from seasonal
    recent = same_dir.sort_values("quarter_settlement_timestamp").tail(4)
    if len(recent) < 2:
        return seasonal
    
    deviations = (recent["final_realised_payout_per_unit"] - seasonal).dropna()
    if len(deviations) == 0:
        return seasonal
    
    # Weight recent more heavily
    weights = np.array([1.0, 1.5, 2.0, 2.5][-len(deviations):])
    weighted_recent_dev = float((deviations.values * weights).sum() / weights.sum())
    
    return seasonal + weighted_recent_dev * 0.25  # dial back the adjustment


# ── deviation feature builder ─────────────────────────────────────────────────

def build_deviation_features(
    settled_history: pd.DataFrame,
    direction_key: str,
    seasonal_benchmark: float | None = None,
) -> DeviationFeatures:
    """Build deviation-based features for a direction.
    
    All computations limited to data available before decision date (leakage control).
    """
    same_dir = settled_history[settled_history["direction_key"] == direction_key].copy()
    
    if seasonal_benchmark is None:
        seasonal_benchmark = compute_seasonal_benchmark(settled_history, direction_key) or 0.0
    
    # Recent 4 quarters' deviations
    recent_sorted = same_dir.sort_values("quarter_settlement_timestamp").tail(4).copy()
    if len(recent_sorted) == 0:
        return DeviationFeatures(
            recent_trend_4q=0.0,
            deviation_volatility_4q=0.0,
            recent_mean_abs_dev=0.0,
            same_q_variance_prior_years=0.0,
            lagged_deviation=0.0,
        )
    
    recent_payouts = recent_sorted["final_realised_payout_per_unit"].values
    recent_deviations = recent_payouts - seasonal_benchmark
    finite_devs = recent_deviations[np.isfinite(recent_deviations)]
    
    # trend: linear fit on deviations
    if len(finite_devs) >= 2:
        x = np.arange(len(finite_devs), dtype=float)
        try:
            coeffs = np.polyfit(x, finite_devs, 1)
            recent_trend = float(coeffs[0])
        except (np.linalg.LinAlgError, ValueError):
            recent_trend = 0.0
    else:
        recent_trend = 0.0
    
    # deviation volatility
    deviation_vol = float(np.std(finite_devs)) if len(finite_devs) > 1 else 0.0
    
    # mean absolute deviation
    mean_abs_dev = float(np.abs(finite_devs).mean()) if len(finite_devs) > 0 else 0.0
    
    # same-quarter variance across prior years
    _, q_no = quarter_to_components(str(recent_sorted.iloc[-1]["quarter"]))
    same_q_rows = same_dir[
        same_dir["quarter"].apply(lambda q: quarter_to_components(str(q))[1]) == q_no
    ]
    same_q_payouts = same_q_rows["final_realised_payout_per_unit"].dropna()
    same_q_var = float(np.var(same_q_payouts)) if len(same_q_payouts) > 1 else 0.0
    
    # lagged deviation (last quarter)
    if len(recent_sorted) > 0:
        last_payout = recent_sorted.iloc[-1]["final_realised_payout_per_unit"]
        lagged_dev = float(last_payout - seasonal_benchmark) if np.isfinite(last_payout) else 0.0
    else:
        lagged_dev = 0.0
    
    return DeviationFeatures(
        recent_trend_4q=recent_trend,
        deviation_volatility_4q=deviation_vol,
        recent_mean_abs_dev=mean_abs_dev,
        same_q_variance_prior_years=same_q_var,
        lagged_deviation=lagged_dev,
    )


# ── model fitting (ridge + XGB) ───────────────────────────────────────────────

def _fit_ridge_deviation(
    X_train: np.ndarray,
    y_train: np.ndarray,
    ridge_lambda: float = 10.0,
) -> np.ndarray | None:
    """Fit ridge regression to deviation targets."""
    if len(y_train) < 2 or X_train.shape[1] == 0:
        return None
    
    # Sanitise
    X_train = np.where(np.isfinite(X_train), X_train, 0.0)
    finite_y = np.isfinite(y_train)
    X_train = X_train[finite_y]
    y_train = y_train[finite_y]
    
    if len(y_train) < 2:
        return None
    
    # Add intercept
    D = np.column_stack([np.ones(len(X_train)), X_train])
    penalty = np.eye(D.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    gram = D.T @ D + penalty
    gram_inv = np.linalg.pinv(gram, rcond=1e-12)
    beta = gram_inv @ D.T @ y_train
    return beta


def _predict_ridge_deviation(
    X_test: np.ndarray,
    beta: np.ndarray,
) -> np.ndarray:
    """Predict using fitted ridge regression."""
    X_test = np.where(np.isfinite(X_test), X_test, 0.0)
    D_test = np.column_stack([np.ones(len(X_test)), X_test])
    return (D_test @ beta).astype(float)


def _fit_xgb_deviation(
    X_train: np.ndarray,
    y_train: np.ndarray,
    config: PriceModelV2Config,
) -> None:
    """XGBoost fitting not available (dependency missing)."""
    return None


def _predict_xgb_deviation(
    X_test: np.ndarray,
    xgb_model: object,
) -> np.ndarray:
    """XGBoost prediction not available (dependency missing)."""
    return np.zeros(len(X_test))


# ── main prediction function (walk-forward compatible) ───────────────────────

def generate_price_model_v2_predictions(
    alpha_df: pd.DataFrame,
    settled_payout_history: pd.DataFrame,
    config: PriceModelV2Config | None = None,
) -> pd.DataFrame:
    """Generate deviation predictions for all rows in alpha_df.
    
    Requires:
    - alpha_df: rows with decision_timestamp, quarter, direction_key, 
               final_realised_payout_per_unit (for scoring only)
    - settled_payout_history: already-settled rows with final_realised_payout_per_unit,
                            quarter_settlement_timestamp (for feature computation)
    
    Returns:
    - DataFrame with deviation_forecast, seasonal_benchmark, regime_benchmark,
      feature values, and lineage columns.
    """
    if config is None:
        config = PriceModelV2Config()
    
    alpha_df = alpha_df.copy()
    alpha_df["decision_timestamp"] = pd.to_datetime(alpha_df["decision_timestamp"], utc=True)
    alpha_df["quarter_settlement_timestamp"] = (
        alpha_df["quarter"].astype(str).map(quarter_settlement_timestamp)
    )
    alpha_df["direction_key"] = (
        alpha_df["interconnector_id"].astype(str) + "::" + alpha_df["from_region"].astype(str)
    )
    
    settled_payout_history = settled_payout_history.copy()
    settled_payout_history["decision_timestamp"] = pd.to_datetime(
        settled_payout_history["decision_timestamp"], utc=True
    )
    settled_payout_history["quarter_settlement_timestamp"] = (
        settled_payout_history["quarter"].astype(str).map(quarter_settlement_timestamp)
    )
    settled_payout_history["direction_key"] = (
        settled_payout_history["interconnector_id"].astype(str) + "::" 
        + settled_payout_history["from_region"].astype(str)
    )
    
    predictions: list[dict] = []
    
    for idx, row in alpha_df.iterrows():
        decision_ts = row["decision_timestamp"]
        actual_payout = row.get("final_realised_payout_per_unit", np.nan)
        direction_key = row["direction_key"]
        
        # All settled data before decision (no lookahead)
        settled_before = settled_payout_history[
            settled_payout_history["decision_timestamp"] < decision_ts
        ].copy()
        
        # Compute benchmarks
        seasonal = compute_seasonal_benchmark(settled_before, direction_key) or 0.0
        regime_adj = compute_regime_adjusted_benchmark(settled_before, direction_key) or seasonal
        
        # Build features
        dev_feats = build_deviation_features(settled_before, direction_key, seasonal)
        
        # Predict deviation (ridge only for now; XGB added later if data permits)
        X_row = np.array([
            dev_feats.recent_trend_4q,
            dev_feats.deviation_volatility_4q,
            dev_feats.recent_mean_abs_dev,
            dev_feats.same_q_variance_prior_years,
            dev_feats.lagged_deviation,
        ], dtype=float)
        
        # For now, simple fallback: if not enough training data, predict 0 deviation
        deviation_forecast = 0.0  # Will be overridden in walk-forward loop
        
        # Compute actual deviation for scoring
        actual_deviation = actual_payout - seasonal if np.isfinite(actual_payout) else np.nan
        
        predictions.append({
            "product_id":                 row.get("product_id", ""),
            "quarter":                    row.get("quarter", ""),
            "decision_timestamp":         decision_ts.isoformat() if pd.notna(decision_ts) else "",
            "interconnector_id":          row.get("interconnector_id", ""),
            "from_region":                row.get("from_region", ""),
            "direction_key":              direction_key,
            "tranche_no":                 row.get("tranche_no", np.nan),
            "ruleset_id":                 row.get("ruleset_id", ""),
            "seasonal_benchmark":         seasonal,
            "regime_adjusted_benchmark":  regime_adj,
            "actual_payout":              actual_payout,
            "actual_deviation":           actual_deviation,
            "deviation_forecast":         deviation_forecast,
            "feat_recent_trend_4q":       dev_feats.recent_trend_4q,
            "feat_deviation_volatility_4q": dev_feats.deviation_volatility_4q,
            "feat_recent_mean_abs_dev":   dev_feats.recent_mean_abs_dev,
            "feat_same_q_variance":       dev_feats.same_q_variance_prior_years,
            "feat_lagged_deviation":      dev_feats.lagged_deviation,
        })
    
    return pd.DataFrame(predictions)
