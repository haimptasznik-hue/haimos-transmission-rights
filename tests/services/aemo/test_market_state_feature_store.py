from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.market_state_feature_store import (  # noqa: E402
    CORE_FEATURE_COLUMNS,
    derive_market_state_features,
    feature_dictionary_frame,
)


def test_derive_market_state_features_adds_expected_columns():
    frame = pd.DataFrame(
        {
            "interval_timestamp_utc": ["2024-01-01T00:05:00Z", "2024-07-06T13:10:00Z"],
            "nsw_qld_spread": [10.0, -7.5],
            "mw_flow": [445.0, -50.0],
            "available_capability_mw": [500.0, 200.0],
            "utilisation_pct": [89.0, 25.0],
            "constraint_binding_flag": [True, False],
            "network_outage_flag": [False, True],
            "nsw_rrp": [100.0, 80.0],
            "qld_rrp": [90.0, 87.5],
            "regional_operational_demand": [8000.0, 7200.0],
        }
    )

    result = derive_market_state_features(frame)

    assert "interval_quarter_label" in result.columns
    assert "australian_season" in result.columns
    assert "abs_nsw_qld_spread" in result.columns
    assert "available_headroom_mw" in result.columns
    assert "market_state_core_coverage_pct" in result.columns
    assert result.loc[0, "flow_direction_label"] == "NSW1->QLD1"
    assert result.loc[1, "flow_direction_label"] == "QLD1->NSW1"
    assert result.loc[0, "available_headroom_mw"] == 55.0
    assert result.loc[1, "available_headroom_pct"] == 75.0
    assert result.loc[0, "market_state_core_non_null_count"] <= len(CORE_FEATURE_COLUMNS)


def test_feature_dictionary_frame_contains_metadata_for_raw_and_derived_features():
    dictionary = feature_dictionary_frame(["mw_flow", "interval_quarter_label", "available_headroom_mw"])

    assert set(dictionary["feature_name"].tolist()) == {"mw_flow", "interval_quarter_label", "available_headroom_mw"}
    assert dictionary.loc[dictionary["feature_name"] == "mw_flow", "category"].iloc[0] == "Network"
    assert dictionary.loc[dictionary["feature_name"] == "interval_quarter_label", "category"].iloc[0] == "Calendar"
    assert dictionary.loc[dictionary["feature_name"] == "available_headroom_mw", "tier"].iloc[0] == 1