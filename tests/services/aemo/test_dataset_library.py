from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.dataset_library import (  # noqa: E402
    DatasetSpec,
    build_correlation_ready_table,
    load_normalized_dataset,
    normalize_aemo_timestamp_series,
)


def test_normalize_aemo_timestamp_series_localizes_aemo_time_to_utc():
    series = pd.Series(["2024/01/01 00:05:00", "2024/01/01 00:09:59"])

    result = normalize_aemo_timestamp_series(series)

    assert result.dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist() == [
        "2023-12-31T14:05:00Z",
        "2023-12-31T14:05:00Z",
    ]


def test_load_normalized_dataset_keeps_join_key_and_selected_values(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "SETTLEMENTDATE": ["2024/01/01 00:05:00", "2024/01/01 00:10:00"],
            "RRP": [100.0, 101.0],
            "MWFLOW": [450.0, 455.0],
        }
    ).to_csv(csv_path, index=False)

    spec = DatasetSpec(
        dataset_id="sample",
        display_name="Sample",
        category="Test",
        source_type="CSV",
        data_path=str(csv_path),
        timestamp_column="SETTLEMENTDATE",
        timestamp_timezone="Australia/Brisbane",
        point_in_time_safe=True,
        refresh_frequency="5-minute",
        description="sample",
        commercial_applications="test",
        value_columns=("RRP",),
    )

    result = load_normalized_dataset(spec, repo_root=tmp_path)

    assert list(result.columns) == ["interval_timestamp_utc", "RRP"]
    assert result["interval_timestamp_utc"].tolist()[0] == "2023-12-31T14:05:00Z"


def test_build_correlation_ready_table_outer_joins_datasets(tmp_path: Path):
    repo_root = tmp_path
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "interval_timestamp_utc": ["2024-01-01T00:05:00Z", "2024-01-01T00:10:00Z"],
            "nsw_qld_spread": [10.0, 6.0],
            "mw_flow": [445.0, 489.0],
            "available_capability_mw": [500.0, 500.0],
            "utilisation_pct": [89.0, 97.8],
            "constraint_binding_flag": [False, True],
            "regional_operational_demand": [8000.0, 8100.0],
            "irsr": [1000.0, 1200.0],
        }
    ).to_csv(reports_dir / "phase5c_market_state.csv", index=False)

    pd.DataFrame(
        {
            "interval_timestamp": ["2024-01-01T00:05:00Z"],
            "demand_nsw_mw": [7900.0],
            "demand_qld_mw": [6500.0],
            "generation_nsw_mw": [8200.0],
            "generation_qld_mw": [6200.0],
            "net_balance_nsw_mw": [300.0],
            "net_balance_qld_mw": [-300.0],
            "balance_difference_mw": [-600.0],
            "qni_flow_mw": [445.0],
            "qni_utilisation_pct": [89.0],
        }
    ).to_csv(reports_dir / "EXP_001_PREPARED_DATA.csv", index=False)

    constraint_dir = repo_root / "data" / "raw" / "aemo" / "mmsdm_dispatchconstraint" / ".cache"
    constraint_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "SETTLEMENTDATE": [
                "2024/01/01 10:05:00",
                "2024/01/01 10:05:00",
                "2024/01/01 10:10:00",
            ],
            "CONSTRAINTID": ["C1", "C2", "C3"],
            "MARGINALVALUE": [0.0, 25.0, 0.0],
            "VIOLATIONDEGREE": [0.0, 0.0, 1.5],
        }
    ).to_csv(
        constraint_dir / "PUBLIC_DVD_DISPATCHCONSTRAINT_202401010000.dispatchconstraint.csv.gz",
        index=False,
        compression="gzip",
    )

    scada_dir = repo_root / "data" / "raw" / "aemo" / "mmsdm_dispatch_unit_scada" / ".cache"
    scada_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "SETTLEMENTDATE": [
                "2024/01/01 10:05:00",
                "2024/01/01 10:05:00",
                "2024/01/01 10:10:00",
            ],
            "DUID": ["BAT1", "GEN1", "GEN1"],
            "SCADA_MW": [-10.0, 120.0, 118.0],
            "REGIONID": ["NSW1", "NSW1", "NSW1"],
        }
    ).to_csv(
        scada_dir / "PUBLIC_DVD_DISPATCH_UNIT_SCADA_202401010000.dispatch_unit_scada.csv.gz",
        index=False,
        compression="gzip",
    )

    result = build_correlation_ready_table(repo_root=repo_root)

    assert "market_state__mw_flow" in result.columns
    assert "exp_001_prepared__balance_difference_mw" in result.columns
    assert "dispatchconstraint__dispatchconstraint_binding_count" in result.columns
    assert "dispatchconstraint__dispatchconstraint_binding_flag" in result.columns
    assert "dispatch_unit_scada__dispatch_unit_scada_total_mw" in result.columns
    assert "dispatch_unit_scada__dispatch_unit_scada_duid_count" in result.columns
    assert len(result) == 2