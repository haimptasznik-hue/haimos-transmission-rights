from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

backtest_module = importlib.import_module("transmission_rights.services.fair_value_backtest")
grid_search_calibration = backtest_module.grid_search_calibration
load_backtest_rows = backtest_module.load_backtest_rows
backtest_with_quarter_calibration = backtest_module.backtest_with_quarter_calibration
calibration_grid_scores = backtest_module.calibration_grid_scores


def test_grid_search_calibration_prefers_zero_discount_on_perfect_data() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2026Q2",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
            {
                "filename": "B.csv",
                "quarter": "C2026Q2",
                "tranche_no": 2,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "QLD1",
                "to_region": "NSW1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
        ]
    )

    result = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0, 0.05],
        liquidity_discounts=[0.0, 0.05],
    )

    assert result.model_risk_discount == 0.0
    assert result.liquidity_discount == 0.0
    assert result.n_rows == 2
    assert result.mape_actual_per_unit == 0.0
    assert result.mape_clearing_price == 0.0
    assert result.payout_error_weight == 0.7
    assert result.clearing_price_error_weight == 0.3


def test_grid_search_calibration_responds_to_price_weight() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2026Q2",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 20.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            }
        ]
    )

    payout_focused = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0],
        liquidity_discounts=[0.0, 0.4],
        payout_error_weight=1.0,
        clearing_price_error_weight=0.0,
    )
    price_focused = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0],
        liquidity_discounts=[0.0, 0.4],
        payout_error_weight=0.0,
        clearing_price_error_weight=1.0,
    )

    assert payout_focused.liquidity_discount == 0.0
    assert price_focused.liquidity_discount == 0.4


def test_grid_search_calibration_honors_ape_cap() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2026Q2",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 1.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            }
        ]
    )

    capped = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0],
        liquidity_discounts=[0.0],
        ape_cap=10.0,
    )

    assert capped.mape_actual_per_unit == 0.0
    assert capped.mape_clearing_price == 10.0
    assert capped.ape_cap == 10.0


def test_grid_search_calibration_quarter_balanced_weighting_changes_score() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A1.csv",
                "quarter": "C2025Q3",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
            {
                "filename": "A2.csv",
                "quarter": "C2025Q3",
                "tranche_no": 2,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
            {
                "filename": "B1.csv",
                "quarter": "C2025Q4",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 20.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
        ]
    )

    unbalanced = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0],
        liquidity_discounts=[0.0],
        payout_error_weight=0.0,
        clearing_price_error_weight=1.0,
        quarter_balanced_weighting=False,
    )
    balanced = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0],
        liquidity_discounts=[0.0],
        payout_error_weight=0.0,
        clearing_price_error_weight=1.0,
        quarter_balanced_weighting=True,
    )

    assert balanced.quarter_balanced_weighting is True
    assert unbalanced.weighted_score != balanced.weighted_score


def test_grid_search_calibration_penalizes_low_total_discount() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2026Q2",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            }
        ]
    )

    no_penalty = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0, 0.1],
        liquidity_discounts=[0.0],
        min_total_discount=0.0,
        discount_penalty_strength=100.0,
    )
    with_penalty = grid_search_calibration(
        frame,
        model_risk_discounts=[0.0, 0.1],
        liquidity_discounts=[0.0],
        min_total_discount=0.1,
        discount_penalty_strength=200.0,
    )

    assert no_penalty.model_risk_discount == 0.0
    assert with_penalty.model_risk_discount == 0.1


def test_calibration_grid_scores_returns_ranked_rows() -> None:
    frame = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2026Q2",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            }
        ]
    )

    grid_df = calibration_grid_scores(
        backtest_df=frame,
        model_risk_discounts=[0.0, 0.1],
        liquidity_discounts=[0.0, 0.1],
        min_total_discount=0.05,
        discount_penalty_strength=50.0,
    )

    assert len(grid_df) == 4
    assert list(grid_df.columns) == [
        "model_risk_discount",
        "liquidity_discount",
        "total_discount",
        "discount_shortfall",
        "mape_actual_per_unit",
        "mape_clearing_price",
        "weighted_score",
    ]
    assert grid_df.iloc[0]["weighted_score"] <= grid_df.iloc[-1]["weighted_score"]


def test_load_backtest_rows_handles_missing_files(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    dispatch_csv = tmp_path / "dispatch.csv"
    pd.DataFrame(columns=["quarter", "interconnector_id", "from_region", "residue_aud"]).to_csv(dispatch_csv, index=False)

    frame = load_backtest_rows(results_dir, dispatch_csv)
    assert frame.empty


def test_backtest_with_quarter_calibration_returns_per_quarter_outputs(monkeypatch, tmp_path: Path) -> None:
    synthetic = pd.DataFrame(
        [
            {
                "filename": "A.csv",
                "quarter": "C2025Q3",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 100.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
            {
                "filename": "B.csv",
                "quarter": "C2025Q4",
                "tranche_no": 1,
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "to_region": "QLD1",
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 80.0,
                "actual_residue_total": 10000.0,
                "actual_per_unit": 100.0,
                "actual_total_payout": 10000.0,
                "total_units_sold": 100,
            },
        ]
    )

    monkeypatch.setattr(backtest_module, "load_backtest_rows", lambda *_: synthetic)

    result_df, calibration_df = backtest_with_quarter_calibration(
        results_dir=tmp_path,
        dispatch_quarterly_csv=tmp_path / "dispatch.csv",
        model_risk_discounts=[0.0, 0.1],
        liquidity_discounts=[0.0, 0.2],
        payout_error_weight=0.6,
        clearing_price_error_weight=0.4,
    )

    assert len(result_df) == 2
    assert set(result_df["quarter"]) == {"C2025Q3", "C2025Q4"}
    assert "calibrated_model_risk_discount" in result_df.columns
    assert "calibrated_liquidity_discount" in result_df.columns

    assert len(calibration_df) == 2
    assert set(calibration_df["quarter"]) == {"C2025Q3", "C2025Q4"}
    assert "weighted_score" in calibration_df.columns
