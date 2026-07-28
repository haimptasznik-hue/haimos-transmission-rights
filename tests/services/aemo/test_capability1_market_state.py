"""Capability 1 – focused tests covering:

1. Raw source preservation (EXPORTLIMIT_MW, IMPORTLIMIT_MW, source lineage)
2. Directional capability derivation
3. Utilisation (abs(MWFLOW) / directional_limit × 100)
4. Edge cases: positive flow, negative flow, zero flow, asymmetric limits,
   null limit, zero limit, flow exceeding limit.
5. Integration: build_capability1_market_state and write_capability1_artifacts.
"""

from __future__ import annotations
from pathlib import Path
import math
import pandas as pd
import pytest

from transmission_rights.services.aemo.dataset_library import (
    _derive_interconnector_row_fields,
    build_correlation_ready_table,
)
from transmission_rights.services.aemo.capability1_market_state import (
    build_capability1_market_state,
    write_capability1_artifacts,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _gzip(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, compression="gzip")


def _row(**kwargs) -> pd.DataFrame:
    defaults = dict(
        INTERCONNECTORID=["NSW1-QLD1"],
        MWFLOW=[0.0],
        EXPORTLIMIT=[500.0],
        IMPORTLIMIT=[500.0],
        MWLOSSES=[0.0],
    )
    defaults.update({k: [v] for k, v in kwargs.items()})
    return pd.DataFrame(defaults)


def _write_fixtures(repo_root: Path) -> None:
    _gzip(
        repo_root / "data/raw/aemo/mmsdm_dispatchconstraint/.cache/PUBLIC_DVD_DISPATCHCONSTRAINT_202401010000.dispatchconstraint.csv.gz",
        pd.DataFrame({
            "SETTLEMENTDATE": ["2024/01/01 10:05:00", "2024/01/01 10:10:00"],
            "CONSTRAINTID": ["C1", "C2"],
            "MARGINALVALUE": [0.0, 15.5],
            "VIOLATIONDEGREE": [0.0, 1.2],
            "INTERCONNECTORID": ["NSW1-QLD1", "NSW1-QLD1"],
            "REGIONID": ["NSW1", "NSW1"],
        }),
    )
    _gzip(
        repo_root / "data/raw/aemo/mmsdm_dispatch_unit_scada/.cache/PUBLIC_DVD_DISPATCH_UNIT_SCADA_202401010000.dispatch_unit_scada.csv.gz",
        pd.DataFrame({
            "SETTLEMENTDATE": ["2024/01/01 10:05:00", "2024/01/01 10:05:00", "2024/01/01 10:10:00"],
            "DUID": ["BAT1", "WIND1", "WIND1"],
            "SCADA_MW": [-12.0, 120.0, 118.0],
            "REGIONID": ["NSW1", "NSW1", "NSW1"],
        }),
    )
    _gzip(
        repo_root / "data/raw/aemo/mmsdm_dispatchinterconnectorres/.cache/PUBLIC_DVD_DISPATCHINTERCONNECTORRES_202401010000.dispatchinterconnectorres.csv.gz",
        pd.DataFrame({
            "SETTLEMENTDATE": ["2024/01/01 10:05:00", "2024/01/01 10:10:00"],
            "INTERCONNECTORID": ["NSW1-QLD1", "NSW1-QLD1"],
            "MWFLOW": [445.0, 489.0],
            "EXPORTLIMIT": [500.0, 500.0],
            "IMPORTLIMIT": [500.0, 500.0],
            "MWLOSSES": [1.2, 1.4],
        }),
    )


# ─── 1. Raw source preservation ───────────────────────────────────────────────

class TestRawPreservation:
    def test_exportlimit_preserved_exactly(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=100.0, EXPORTLIMIT=480.0, IMPORTLIMIT=520.0))
        assert r.loc[0, "EXPORTLIMIT_MW"] == 480.0

    def test_importlimit_preserved_exactly(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=-100.0, EXPORTLIMIT=480.0, IMPORTLIMIT=520.0))
        assert r.loc[0, "IMPORTLIMIT_MW"] == 520.0

    def test_original_source_columns_not_mutated(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=200.0, EXPORTLIMIT=400.0, IMPORTLIMIT=300.0))
        assert r.loc[0, "EXPORTLIMIT"] == 400.0
        assert r.loc[0, "IMPORTLIMIT"] == 300.0

    def test_interconnectorid_column_survives(self):
        r = _derive_interconnector_row_fields(_row())
        assert "INTERCONNECTORID" in r.columns


# ─── 2. Directional capability ────────────────────────────────────────────────

class TestDirectionalCapability:
    def test_positive_flow_uses_export_limit(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=300.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert r.loc[0, "directional_limit_mw"] == 500.0

    def test_negative_flow_uses_abs_import_limit(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=-300.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert r.loc[0, "directional_limit_mw"] == 400.0

    def test_zero_flow_uses_max_of_both(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=0.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert r.loc[0, "directional_limit_mw"] == 500.0

    def test_zero_flow_asymmetric_uses_larger(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=0.0, EXPORTLIMIT=200.0, IMPORTLIMIT=600.0))
        assert r.loc[0, "directional_limit_mw"] == 600.0

    def test_null_export_limit_positive_flow_is_invalid(self):
        frame = pd.DataFrame({
            "INTERCONNECTORID": ["NSW1-QLD1"],
            "MWFLOW": [100.0],
            "EXPORTLIMIT": [float("nan")],
            "IMPORTLIMIT": [500.0],
            "MWLOSSES": [0.0],
        })
        r = _derive_interconnector_row_fields(frame)
        assert r.loc[0, "limit_quality_flag"] == "INVALID"
        assert pd.isna(r.loc[0, "utilisation_pct"])

    def test_zero_export_limit_positive_flow_is_invalid(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=100.0, EXPORTLIMIT=0.0, IMPORTLIMIT=500.0))
        assert r.loc[0, "limit_quality_flag"] == "INVALID"
        assert pd.isna(r.loc[0, "utilisation_pct"])

    def test_null_mwflow_produces_nan_directional_limit(self):
        frame = pd.DataFrame({
            "INTERCONNECTORID": ["NSW1-QLD1"],
            "MWFLOW": [float("nan")],
            "EXPORTLIMIT": [500.0],
            "IMPORTLIMIT": [500.0],
            "MWLOSSES": [0.0],
        })
        r = _derive_interconnector_row_fields(frame)
        assert pd.isna(r.loc[0, "directional_limit_mw"])

    def test_valid_limit_produces_ok_flag(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=100.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert r.loc[0, "limit_quality_flag"] == "OK"


# ─── 3. Utilisation ───────────────────────────────────────────────────────────

class TestUtilisation:
    def test_positive_flow_utilisation(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=250.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert abs(r.loc[0, "utilisation_pct"] - 50.0) < 1e-9

    def test_negative_flow_utilisation_uses_import_limit(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=-300.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert abs(r.loc[0, "utilisation_pct"] - 75.0) < 1e-9

    def test_no_negative_utilisation(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=-300.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert r.loc[0, "utilisation_pct"] >= 0.0

    def test_zero_flow_utilisation_is_zero(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=0.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert r.loc[0, "utilisation_pct"] == 0.0

    def test_over_limit_not_clipped(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=600.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert r.loc[0, "utilisation_pct"] == pytest.approx(120.0, abs=1e-9)

    def test_over_limit_flag_set(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=600.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert bool(r.loc[0, "over_limit_flag"]) is True

    def test_under_limit_flag_not_set(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=250.0, EXPORTLIMIT=500.0, IMPORTLIMIT=500.0))
        assert bool(r.loc[0, "over_limit_flag"]) is False

    def test_null_limit_gives_nan_not_inf(self):
        frame = pd.DataFrame({
            "INTERCONNECTORID": ["NSW1-QLD1"],
            "MWFLOW": [100.0],
            "EXPORTLIMIT": [float("nan")],
            "IMPORTLIMIT": [500.0],
            "MWLOSSES": [0.0],
        })
        r = _derive_interconnector_row_fields(frame)
        val = r.loc[0, "utilisation_pct"]
        assert pd.isna(val)

    def test_zero_limit_gives_nan_not_inf(self):
        r = _derive_interconnector_row_fields(_row(MWFLOW=100.0, EXPORTLIMIT=0.0, IMPORTLIMIT=0.0))
        val = r.loc[0, "utilisation_pct"]
        assert pd.isna(val)

    def test_asymmetric_limits_negative_flow(self):
        # 300 MW import on a 400 MW import limit = 75%
        r = _derive_interconnector_row_fields(_row(MWFLOW=-300.0, EXPORTLIMIT=500.0, IMPORTLIMIT=400.0))
        assert abs(r.loc[0, "utilisation_pct"] - 75.0) < 1e-9


# ─── 4. Aggregation column surface ────────────────────────────────────────────

class TestAggregationColumns:
    def test_export_import_limits_in_aggregate(self, tmp_path):
        _write_fixtures(tmp_path)
        t = build_correlation_ready_table(repo_root=tmp_path, dataset_ids=["dispatchinterconnectorres"])
        assert "dispatchinterconnectorres__dispatchinterconnectorres_export_limit_mw" in t.columns
        assert "dispatchinterconnectorres__dispatchinterconnectorres_import_limit_mw" in t.columns

    def test_directional_limit_in_aggregate(self, tmp_path):
        _write_fixtures(tmp_path)
        t = build_correlation_ready_table(repo_root=tmp_path, dataset_ids=["dispatchinterconnectorres"])
        assert "dispatchinterconnectorres__dispatchinterconnectorres_directional_limit_mw" in t.columns
        assert t.iloc[0]["dispatchinterconnectorres__dispatchinterconnectorres_directional_limit_mw"] == 500.0

    def test_utilisation_in_aggregate(self, tmp_path):
        _write_fixtures(tmp_path)
        t = build_correlation_ready_table(repo_root=tmp_path, dataset_ids=["dispatchinterconnectorres"])
        assert "dispatchinterconnectorres__dispatchinterconnectorres_utilisation_pct" in t.columns
        # 445/500 * 100 = 89.0
        assert abs(t.iloc[0]["dispatchinterconnectorres__dispatchinterconnectorres_utilisation_pct"] - 89.0) < 1e-6

    def test_over_limit_count_in_aggregate(self, tmp_path):
        _gzip(
            tmp_path / "data/raw/aemo/mmsdm_dispatchinterconnectorres/.cache/over.dispatchinterconnectorres.csv.gz",
            pd.DataFrame({
                "SETTLEMENTDATE": ["2024/01/01 10:05:00"],
                "INTERCONNECTORID": ["NSW1-QLD1"],
                "MWFLOW": [550.0],
                "EXPORTLIMIT": [500.0],
                "IMPORTLIMIT": [500.0],
                "MWLOSSES": [2.0],
            }),
        )
        t = build_correlation_ready_table(repo_root=tmp_path, dataset_ids=["dispatchinterconnectorres"])
        assert t.iloc[0]["dispatchinterconnectorres__dispatchinterconnectorres_over_limit_count"] >= 1

    def test_limit_invalid_count_for_null_limit(self, tmp_path):
        _gzip(
            tmp_path / "data/raw/aemo/mmsdm_dispatchinterconnectorres/.cache/null_lim.dispatchinterconnectorres.csv.gz",
            pd.DataFrame({
                "SETTLEMENTDATE": ["2024/01/01 10:05:00"],
                "INTERCONNECTORID": ["NSW1-QLD1"],
                "MWFLOW": [100.0],
                "EXPORTLIMIT": [float("nan")],
                "IMPORTLIMIT": [500.0],
                "MWLOSSES": [0.0],
            }),
        )
        t = build_correlation_ready_table(repo_root=tmp_path, dataset_ids=["dispatchinterconnectorres"])
        assert t.iloc[0]["dispatchinterconnectorres__dispatchinterconnectorres_limit_invalid_count"] >= 1


# ─── 5. Capability-1 builder ──────────────────────────────────────────────────

class TestCapability1Builder:
    def test_transmission_capability_mw_present(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert "transmission_capability_mw" in r.combined_market_state.columns

    def test_network_utilisation_pct_present(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert "network_utilisation_pct" in r.combined_market_state.columns

    def test_export_import_limit_aliases_present(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert "export_limit_mw" in r.combined_market_state.columns
        assert "import_limit_mw" in r.combined_market_state.columns

    def test_quality_flag_columns_present(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert "over_limit_count" in r.combined_market_state.columns
        assert "limit_invalid_count" in r.combined_market_state.columns

    def test_constraint_and_scada_aliases_present(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert "constraint_binding_flag" in r.combined_market_state.columns
        assert "scada_generation_mw" in r.combined_market_state.columns

    def test_eight_datasets_in_inventory(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert r.summary["datasets_total"] == 8

    def test_external_gaps_flagged_correctly(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        inv = r.inventory.set_index("dataset_name")
        assert inv.loc["weather", "status"] == "EXTERNAL_GAP"
        assert inv.loc["generator_outages", "status"] == "EXTERNAL_GAP"

    def test_completion_above_zero(self, tmp_path):
        _write_fixtures(tmp_path)
        r = build_capability1_market_state(tmp_path)
        assert r.summary["completion_pct"] > 0


class TestWriteArtifacts:
    def test_creates_four_output_files(self, tmp_path):
        _write_fixtures(tmp_path)
        out = tmp_path / "reports" / "capability1"
        write_capability1_artifacts(tmp_path, out)
        assert (out / "capability1_market_state_inventory.csv").exists()
        assert (out / "capability1_source_availability.csv").exists()
        assert (out / "capability1_combined_market_state.csv").exists()
        assert (out / "capability1_market_state_summary.json").exists()
