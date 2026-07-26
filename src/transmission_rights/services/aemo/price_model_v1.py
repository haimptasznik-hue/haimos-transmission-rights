from __future__ import annotations

from dataclasses import dataclass
import math
import re

import numpy as np
import pandas as pd


_QUARTER_RE = re.compile(r"C(\d{4})Q([1-4])")
_DEFAULT_INTERVAL_Z = 1.2815515655446004


@dataclass(frozen=True)
class PriceModelV1Config:
    min_training_rows: int = 24
    ridge_lambda: float = 10.0
    interval_z: float = _DEFAULT_INTERVAL_Z


@dataclass(frozen=True)
class PriceModelV1Artifacts:
    predictions: pd.DataFrame
    direct_regional_price_data_available: bool
    feature_columns: tuple[str, ...]


_NUMERIC_FEATURE_COLUMNS = (
    "auction_clearing_price",
    "fill_probability",
    "units_offered",
    "units_sold",
    "tranche_no",
    "quarter_number",
    "year_number",
    "quarter_sin",
    "quarter_cos",
    "same_quarter_prior_tranche_clear_median",
    "same_quarter_prior_tranche_clear_last",
    "category_known_clear_median",
    "category_known_clear_mean",
    "category_settled_payout_mean",
    "category_settled_payout_median",
    "category_settled_payout_std",
    "category_settled_last_payout",
    "category_settled_alpha_mean",
    "category_settled_alpha_std",
    "tranche_settled_payout_mean",
    "tranche_settled_payout_std",
    "tranche_settled_last_payout",
    "settled_observation_count",
    "category_settled_observation_count",
    "tranche_settled_observation_count",
)


def quarter_to_components(quarter: str) -> tuple[int, int]:
    match = _QUARTER_RE.fullmatch(str(quarter))
    if match is None:
        raise ValueError(f"Invalid quarter format: {quarter}")
    return int(match.group(1)), int(match.group(2))


def quarter_settlement_timestamp(quarter: str) -> pd.Timestamp:
    year, quarter_no = quarter_to_components(quarter)
    settle_month = quarter_no * 3 + 3
    settle_year = year
    if settle_month > 12:
        settle_month -= 12
        settle_year += 1
    if settle_month == 12:
        return pd.Timestamp(settle_year, 12, 31, 23, 59, 59, tz="UTC")
    return pd.Timestamp(settle_year, settle_month + 1, 1, tz="UTC") - pd.Timedelta(seconds=1)


def _quarter_angle(quarter_number: int) -> float:
    return (2.0 * math.pi * float(quarter_number)) / 4.0


def _safe_std(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return 0.0
    return float(clean.std(ddof=1))


def _ridge_fit(
    x_train: np.ndarray,
    y_train: np.ndarray,
    ridge_lambda: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    design = np.column_stack([np.ones(len(x_train)), x_train])
    # Replace non-finite values with 0 to avoid SVD failure on NaN/inf features.
    design = np.where(np.isfinite(design), design, 0.0)
    # Drop rows where the label is non-finite.
    finite_mask = np.isfinite(y_train)
    design = design[finite_mask]
    y_train = y_train[finite_mask]
    if len(y_train) == 0:
        n_features = design.shape[1]
        beta = np.zeros(n_features)
        gram_inv = np.eye(n_features)
        return beta, gram_inv, design
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    gram = design.T @ design + penalty
    gram_inv = np.linalg.pinv(gram, rcond=1e-12)
    beta = gram_inv @ design.T @ y_train
    return beta, gram_inv, design


def _predict_with_beta(x_row: np.ndarray, beta: np.ndarray) -> float:
    x_clean = np.where(np.isfinite(x_row), x_row, 0.0)
    design_row = np.concatenate([[1.0], x_clean])
    return float(design_row @ beta)


def _fallback_forecast(row: pd.Series) -> tuple[float, str]:
    same_quarter_clear = float(row["same_quarter_prior_tranche_clear_median"])
    category_payout = float(row["category_settled_payout_median"])
    category_clear = float(row["category_known_clear_median"])
    current_clear = float(row["auction_clearing_price"])

    if same_quarter_clear > 0:
        return same_quarter_clear, "fallback_same_quarter_clear"
    if category_payout > 0:
        return category_payout, "fallback_category_payout"
    if category_clear > 0:
        return category_clear, "fallback_category_clear"
    return current_clear, "fallback_current_clear"


def _build_feature_row(
    row: pd.Series,
    known_rows: pd.DataFrame,
    settled_rows: pd.DataFrame,
) -> dict[str, float | str]:
    direction_key = f"{row['interconnector_id']}|{row['from_region']}"
    same_direction_known = known_rows[
        (known_rows["interconnector_id"] == row["interconnector_id"])
        & (known_rows["from_region"] == row["from_region"])
    ]
    same_direction_settled = settled_rows[
        (settled_rows["interconnector_id"] == row["interconnector_id"])
        & (settled_rows["from_region"] == row["from_region"])
    ]
    same_tranche_settled = same_direction_settled[
        same_direction_settled["tranche_no"] == row["tranche_no"]
    ]
    same_quarter_prior = same_direction_known[
        (same_direction_known["quarter"] == row["quarter"])
        & (same_direction_known["tranche_no"] < row["tranche_no"])
    ]

    quarter_year, quarter_number = quarter_to_components(str(row["quarter"]))
    angle = _quarter_angle(quarter_number)

    category_settled_alpha = (
        same_direction_settled["final_realised_payout_per_unit"]
        - same_direction_settled["auction_clearing_price"]
    ) if not same_direction_settled.empty else pd.Series(dtype=float)

    feature_row: dict[str, float | str] = {
        "direction_key": direction_key,
        "auction_clearing_price": float(row["auction_clearing_price"]),
        "fill_probability": float(row["fill_probability"]),
        "units_offered": float(row["units_offered"]),
        "units_sold": float(row["units_sold"]),
        "tranche_no": float(row["tranche_no"]),
        "quarter_number": float(quarter_number),
        "year_number": float(quarter_year),
        "quarter_sin": math.sin(angle),
        "quarter_cos": math.cos(angle),
        "same_quarter_prior_tranche_clear_median": float(
            same_quarter_prior["auction_clearing_price"].median()
        ) if not same_quarter_prior.empty else 0.0,
        "same_quarter_prior_tranche_clear_last": float(
            same_quarter_prior["auction_clearing_price"].iloc[-1]
        ) if not same_quarter_prior.empty else 0.0,
        "category_known_clear_median": float(
            same_direction_known["auction_clearing_price"].median()
        ) if not same_direction_known.empty else 0.0,
        "category_known_clear_mean": float(
            same_direction_known["auction_clearing_price"].mean()
        ) if not same_direction_known.empty else 0.0,
        "category_settled_payout_mean": float(
            same_direction_settled["final_realised_payout_per_unit"].mean()
        ) if not same_direction_settled.empty else 0.0,
        "category_settled_payout_median": float(
            same_direction_settled["final_realised_payout_per_unit"].median()
        ) if not same_direction_settled.empty else 0.0,
        "category_settled_payout_std": _safe_std(
            same_direction_settled["final_realised_payout_per_unit"]
        ) if not same_direction_settled.empty else 0.0,
        "category_settled_last_payout": float(
            same_direction_settled["final_realised_payout_per_unit"].iloc[-1]
        ) if not same_direction_settled.empty else 0.0,
        "category_settled_alpha_mean": float(category_settled_alpha.mean()) if len(category_settled_alpha) else 0.0,
        "category_settled_alpha_std": _safe_std(category_settled_alpha) if len(category_settled_alpha) else 0.0,
        "tranche_settled_payout_mean": float(
            same_tranche_settled["final_realised_payout_per_unit"].mean()
        ) if not same_tranche_settled.empty else 0.0,
        "tranche_settled_payout_std": _safe_std(
            same_tranche_settled["final_realised_payout_per_unit"]
        ) if not same_tranche_settled.empty else 0.0,
        "tranche_settled_last_payout": float(
            same_tranche_settled["final_realised_payout_per_unit"].iloc[-1]
        ) if not same_tranche_settled.empty else 0.0,
        "settled_observation_count": float(len(settled_rows)),
        "category_settled_observation_count": float(len(same_direction_settled)),
        "tranche_settled_observation_count": float(len(same_tranche_settled)),
    }
    return feature_row


def prepare_price_model_frame(alpha_df: pd.DataFrame) -> pd.DataFrame:
    frame = alpha_df.copy()
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True)
    frame["quarter"] = frame["quarter"].astype(str)
    frame["tranche_no"] = pd.to_numeric(frame["tranche_no"], errors="coerce").fillna(0).astype(int)
    frame["fill_probability"] = pd.to_numeric(frame["fill_probability"], errors="coerce").fillna(0.0)
    frame["quarter_settlement_timestamp"] = frame["quarter"].map(quarter_settlement_timestamp)
    frame = frame.sort_values(
        ["decision_timestamp", "quarter", "tranche_no", "interconnector_id", "from_region"]
    ).reset_index(drop=True)

    feature_rows: list[dict[str, float | str]] = []
    for idx, row in frame.iterrows():
        known_rows = frame.iloc[:idx].copy()
        settled_rows = known_rows[
            known_rows["quarter_settlement_timestamp"] <= row["decision_timestamp"]
        ].copy()
        feature_rows.append(_build_feature_row(row, known_rows, settled_rows))

    features = pd.DataFrame(feature_rows)
    combined = pd.concat([frame, features], axis=1)
    # Drop duplicate columns (frame columns take precedence over recomputed feature columns)
    combined = combined.loc[:, ~combined.columns.duplicated(keep="first")]
    return combined


def _design_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.loc[:, _NUMERIC_FEATURE_COLUMNS].astype(float)
    encoded_direction = pd.get_dummies(frame["direction_key"], prefix="direction", dtype=float)
    return pd.concat([numeric, encoded_direction], axis=1)


def generate_price_model_v1_predictions(
    alpha_df: pd.DataFrame,
    config: PriceModelV1Config | None = None,
) -> PriceModelV1Artifacts:
    model_config = config or PriceModelV1Config()
    prepared = prepare_price_model_frame(alpha_df)
    matrix = _design_matrix(prepared)
    model_feature_columns = tuple(matrix.columns.tolist())

    predictions: list[dict[str, object]] = []
    global_settled = prepared[prepared["final_realised_payout_per_unit"].notna()].copy()
    global_target_std = _safe_std(global_settled["final_realised_payout_per_unit"]) or 0.0

    for idx, row in prepared.iterrows():
        decision_timestamp = row["decision_timestamp"]
        train_mask = (
            prepared.index < idx
        ) & (
            prepared["quarter_settlement_timestamp"] <= decision_timestamp
        ) & (
            prepared["final_realised_payout_per_unit"].notna()
        )
        train_rows = prepared.loc[train_mask].copy()
        x_row = matrix.iloc[idx].to_numpy(dtype=float)
        actual = row.get("final_realised_payout_per_unit")
        baseline = float(row["fair_value_forecast"])

        if len(train_rows) < model_config.min_training_rows:
            forecast, method = _fallback_forecast(row)
            local_std = float(row["category_settled_payout_std"]) or global_target_std or abs(forecast) * 0.25
            interval_half_width = model_config.interval_z * max(local_std, 1.0)
            ci_low = forecast - interval_half_width
            ci_high = forecast + interval_half_width
            training_residual_std = local_std
        else:
            x_train = matrix.loc[train_mask].to_numpy(dtype=float)
            y_train = pd.to_numeric(
                train_rows["final_realised_payout_per_unit"], errors="coerce"
            ).to_numpy(dtype=float)
            beta, gram_inv, train_design = _ridge_fit(
                x_train=x_train,
                y_train=y_train,
                ridge_lambda=model_config.ridge_lambda,
            )
            forecast = _predict_with_beta(x_row, beta)
            train_predictions = train_design @ beta
            residuals = y_train - train_predictions
            residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
            training_residual_std = residual_std or float(row["category_settled_payout_std"]) or global_target_std
            design_row = np.concatenate([[1.0], x_row])
            leverage = float(design_row @ gram_inv @ design_row)
            prediction_std = max(training_residual_std, 1.0) * math.sqrt(max(1.0, leverage))
            interval_half_width = model_config.interval_z * prediction_std
            ci_low = forecast - interval_half_width
            ci_high = forecast + interval_half_width
            method = "ridge_regression"

        predictions.append(
            {
                "decision_timestamp": decision_timestamp,
                "product_id": row["product_id"],
                "quarter": row["quarter"],
                "tranche": row["tranche"],
                "tranche_no": int(row["tranche_no"]),
                "interconnector_id": row["interconnector_id"],
                "from_region": row["from_region"],
                "auction_clearing_price": float(row["auction_clearing_price"]),
                "baseline_fair_value_forecast": baseline,
                "price_model_v1_forecast": float(forecast),
                "price_model_v1_ci_low": float(ci_low),
                "price_model_v1_ci_high": float(ci_high),
                "price_model_v1_interval_width": float(ci_high - ci_low),
                "final_realised_payout_per_unit": (
                    float(actual) if pd.notna(actual) else np.nan
                ),
                "baseline_abs_error": (
                    abs(float(actual) - baseline) if pd.notna(actual) else np.nan
                ),
                "price_model_v1_abs_error": (
                    abs(float(actual) - float(forecast)) if pd.notna(actual) else np.nan
                ),
                "training_rows": int(len(train_rows)),
                "training_residual_std": float(training_residual_std or 0.0),
                "forecast_method": method,
                "settled_observation_count": int(row["settled_observation_count"]),
                "category_settled_observation_count": int(row["category_settled_observation_count"]),
                "tranche_settled_observation_count": int(row["tranche_settled_observation_count"]),
                "same_quarter_prior_tranche_clear_median": float(row["same_quarter_prior_tranche_clear_median"]),
                "category_settled_payout_median": float(row["category_settled_payout_median"]),
                "model_version": "price_model_v1",
            }
        )

    prediction_frame = pd.DataFrame(predictions)
    return PriceModelV1Artifacts(
        predictions=prediction_frame,
        direct_regional_price_data_available=False,
        feature_columns=model_feature_columns,
    )
