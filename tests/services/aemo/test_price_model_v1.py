from __future__ import annotations

import pandas as pd

from transmission_rights.services.aemo.price_model_v1 import (
    PriceModelV1Config,
    generate_price_model_v1_predictions,
    quarter_settlement_timestamp,
)


def test_quarter_settlement_timestamp_rolls_forward_one_quarter() -> None:
    assert quarter_settlement_timestamp("C2025Q4") == pd.Timestamp("2026-03-31T23:59:59Z")


def test_price_model_v1_uses_fallback_then_regression() -> None:
    frame = pd.DataFrame(
        [
            {
                "decision_timestamp": "2021-01-01T00:00:00Z",
                "product_id": "C2020Q1:NSW1-QLD1:NSW1:T01",
                "quarter": "C2020Q1",
                "tranche": "T01",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "units_offered": 100,
                "units_sold": 100,
                "fill_probability": 1.0,
                "fair_value_forecast": 40.0,
                "auction_clearing_price": 40.0,
                "final_realised_payout_per_unit": 100.0,
            },
            {
                "decision_timestamp": "2021-10-01T00:00:00Z",
                "product_id": "C2020Q2:NSW1-QLD1:NSW1:T01",
                "quarter": "C2020Q2",
                "tranche": "T01",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "units_offered": 100,
                "units_sold": 100,
                "fill_probability": 1.0,
                "fair_value_forecast": 50.0,
                "auction_clearing_price": 50.0,
                "final_realised_payout_per_unit": 120.0,
            },
            {
                "decision_timestamp": "2022-10-01T00:00:00Z",
                "product_id": "C2021Q2:NSW1-QLD1:NSW1:T01",
                "quarter": "C2021Q2",
                "tranche": "T01",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "units_offered": 100,
                "units_sold": 100,
                "fill_probability": 1.0,
                "fair_value_forecast": 60.0,
                "auction_clearing_price": 60.0,
                "final_realised_payout_per_unit": 130.0,
            },
        ]
    )

    artifacts = generate_price_model_v1_predictions(
        frame,
        PriceModelV1Config(min_training_rows=2, ridge_lambda=0.1),
    )
    predictions = artifacts.predictions

    assert predictions.loc[0, "forecast_method"].startswith("fallback_")
    assert predictions.loc[0, "price_model_v1_forecast"] == 40.0

    assert predictions.loc[2, "forecast_method"] == "ridge_regression"
    assert predictions.loc[2, "training_rows"] == 2
    assert predictions.loc[2, "price_model_v1_ci_high"] > predictions.loc[2, "price_model_v1_ci_low"]
