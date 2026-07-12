from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from transmission_rights.services.aemo.alpha_validation import (
    BacktestConfig,
    assign_split,
    audit_required_columns,
    latest_decision_report,
    leakage_audit,
    run_investable_backtest,
    split_summary,
)


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "decision_timestamp": datetime(2023, 1, 1, tzinfo=UTC).isoformat(),
            "information_cutoff": datetime(2023, 1, 1, tzinfo=UTC).isoformat(),
            "source_timestamp_max": datetime(2023, 1, 1, tzinfo=UTC).isoformat(),
            "ruleset_id": "RS-BASELINE-v1",
            "product_id": "Q1-2023:VIC1-NSW1:VIC:T1",
            "auction_clearing_price": 10.0,
            "fair_value_forecast": 15.0,
            "final_realised_payout_per_unit": 20.0,
            "forecast_error_to_realised": -5.0,
            "realised_alpha": 10.0,
            "source_lineage": "{}",
            "quarter": "Q1-2023",
            "interconnector_id": "VIC1-NSW1",
            "from_region": "VIC",
            "tranche_no": 1,
            "units_offered": 1000,
            "units_sold": 900,
            "fill_probability": 0.9,
            "expected_alpha": 5.0,
            "confidence_band": "medium",
        },
        {
            "decision_timestamp": datetime(2023, 4, 1, tzinfo=UTC).isoformat(),
            "information_cutoff": datetime(2023, 4, 1, tzinfo=UTC).isoformat(),
            "source_timestamp_max": datetime(2023, 4, 1, tzinfo=UTC).isoformat(),
            "ruleset_id": "RS-BASELINE-v1",
            "product_id": "Q2-2023:VIC1-NSW1:VIC:T2",
            "auction_clearing_price": 12.0,
            "fair_value_forecast": 18.0,
            "final_realised_payout_per_unit": 19.0,
            "forecast_error_to_realised": -1.0,
            "realised_alpha": 7.0,
            "source_lineage": "{}",
            "quarter": "Q2-2023",
            "interconnector_id": "VIC1-NSW1",
            "from_region": "VIC",
            "tranche_no": 2,
            "units_offered": 1000,
            "units_sold": 850,
            "fill_probability": 0.8,
            "expected_alpha": 6.0,
            "confidence_band": "high",
        },
        {
            "decision_timestamp": datetime(2023, 7, 1, tzinfo=UTC).isoformat(),
            "information_cutoff": datetime(2023, 7, 1, tzinfo=UTC).isoformat(),
            "source_timestamp_max": datetime(2023, 7, 1, tzinfo=UTC).isoformat(),
            "ruleset_id": "RS-BASELINE-v1",
            "product_id": "Q3-2023:VIC1-NSW1:VIC:T3",
            "auction_clearing_price": 11.0,
            "fair_value_forecast": 14.0,
            "final_realised_payout_per_unit": 16.0,
            "forecast_error_to_realised": -2.0,
            "realised_alpha": 5.0,
            "source_lineage": "{}",
            "quarter": "Q3-2023",
            "interconnector_id": "VIC1-NSW1",
            "from_region": "VIC",
            "tranche_no": 3,
            "units_offered": 1000,
            "units_sold": 800,
            "fill_probability": 0.7,
            "expected_alpha": 3.0,
            "confidence_band": "low",
        },
    ]


def test_required_columns_and_leakage_pass() -> None:
    frame = pd.DataFrame(_sample_rows())
    schema = audit_required_columns(frame)
    leakage = leakage_audit(frame)

    assert schema["status"] == "pass"
    assert leakage["status"] == "pass"
    assert leakage["checked_rows"] == 3


def test_leakage_detects_cutoff_after_decision() -> None:
    rows = _sample_rows()
    rows[0]["information_cutoff"] = datetime(2023, 1, 2, tzinfo=UTC).isoformat()
    frame = pd.DataFrame(rows)

    leakage = leakage_audit(frame)

    assert leakage["status"] == "fail"
    assert any(item["reason"] == "information_cutoff_after_decision" for item in leakage["failures"])


def test_split_backtest_and_decision_report_outputs() -> None:
    frame = pd.DataFrame(_sample_rows())
    split_frame = assign_split(frame)

    trades_df, quarter_df, summary = run_investable_backtest(split_frame, BacktestConfig())
    split_metrics = split_summary(split_frame, BacktestConfig())
    decision_report = latest_decision_report(trades_df)

    assert summary["status"] in {"ok", "no_trades"}
    assert set(split_metrics.keys()) == {"in_sample", "validation", "out_of_sample"}
    assert len(quarter_df) >= 1
    assert decision_report["status"] in {"ok", "no_trades"}
