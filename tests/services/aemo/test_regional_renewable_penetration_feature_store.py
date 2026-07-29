from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.regional_renewable_penetration_feature_store import (  # noqa: E402
    canonical_hash_contract_metadata,
    compute_feature_rows_canonical_hash_sha256,
    _load_checkpoint,
    build_regional_renewable_penetration_feature_store,
)


def _gzip(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, compression="gzip")


def _write_generator_master(repo_root: Path) -> None:
    master_dir = repo_root / "data" / "derived" / "generator_master_v1"
    master_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "DUID": "WIND1",
                "station_name": "Wind One",
                "participant": "Tester",
                "region": "NSW1",
                "registered_capacity_mw": 100.0,
                "fuel_type": "WIND",
                "technology_type": "WIND_TURBINE",
                "dispatch_classification": "GENERATING",
                "renewable_flag": True,
                "snapshot_date": "2026-07-29",
                "snapshot_version": "2026-07-29",
                "authoritative_source": "TEST",
                "classification_confidence": "HIGH",
                "first_seen_utc": "2024-01-01T00:05:00Z",
                "last_seen_utc": "2024-01-01T00:05:00Z",
                "observed_max_mw": 80.0,
                "observed_min_mw": 80.0,
                "observed_mean_mw": 80.0,
                "interval_count": 1,
                "positive_interval_count": 1,
                "zero_interval_count": 0,
                "negative_interval_count": 0,
                "positive_energy_mwh_proxy": 6.6667,
                "negative_energy_mwh_proxy": 0.0,
                "quality_status": "AUTHORITATIVE",
                "schema_version": "1.0",
                "generator_master_version": "1.0",
                "pit_scope": "CURRENT_STATE_ONLY",
                "effective_from": "2026-07-29",
                "effective_to": "2026-07-29",
            },
            {
                "DUID": "COAL1",
                "station_name": "Coal One",
                "participant": "Tester",
                "region": "NSW1",
                "registered_capacity_mw": 200.0,
                "fuel_type": "BLACK_COAL",
                "technology_type": "STEAM_TURBINE",
                "dispatch_classification": "GENERATING",
                "renewable_flag": False,
                "snapshot_date": "2026-07-29",
                "snapshot_version": "2026-07-29",
                "authoritative_source": "TEST",
                "classification_confidence": "HIGH",
                "first_seen_utc": "2024-01-01T00:05:00Z",
                "last_seen_utc": "2024-01-01T00:05:00Z",
                "observed_max_mw": 50.0,
                "observed_min_mw": 50.0,
                "observed_mean_mw": 50.0,
                "interval_count": 1,
                "positive_interval_count": 1,
                "zero_interval_count": 0,
                "negative_interval_count": 0,
                "positive_energy_mwh_proxy": 4.1667,
                "negative_energy_mwh_proxy": 0.0,
                "quality_status": "AUTHORITATIVE",
                "schema_version": "1.0",
                "generator_master_version": "1.0",
                "pit_scope": "CURRENT_STATE_ONLY",
                "effective_from": "2026-07-29",
                "effective_to": "2026-07-29",
            },
        ]
    ).to_csv(master_dir / "generator_master_v1.csv", index=False)


def test_build_regional_renewable_penetration_feature_store(tmp_path: Path):
    repo_root = tmp_path
    _write_generator_master(repo_root)

    scada_dir = repo_root / "data" / "raw" / "aemo" / "mmsdm_dispatch_unit_scada" / ".cache"
    _gzip(
        scada_dir / "PUBLIC_DVD_DISPATCH_UNIT_SCADA_202401010000.dispatch_unit_scada.csv.gz",
        pd.DataFrame(
            {
                "SETTLEMENTDATE": ["2024/01/01 00:05:00", "2024/01/01 00:05:00", "2024/01/01 00:05:00"],
                "DUID": ["WIND1", "COAL1", "UNMATCHED1"],
                "SCADA_MW": [80.0, 50.0, 20.0],
                "REGIONID": ["NSW1", "NSW1", "NSW1"],
            }
        ),
    )

    result = build_regional_renewable_penetration_feature_store(
        repo_root=repo_root,
        output_dir=repo_root / "data" / "derived" / "regional_renewable_penetration_feature_store",
    )

    assert len(result.feature_store) == 1
    row = result.feature_store.iloc[0]
    assert row["region"] == "NSW1"
    assert row["total_positive_generation_mw"] == 150.0
    assert row["renewable_positive_generation_mw"] == 80.0
    assert row["matched_positive_generation_mw"] == 130.0
    assert row["unmatched_positive_generation_mw"] == 20.0
    assert row["renewable_penetration_pct"] == 53.333333
    assert row["renewable_penetration_known_pct"] == 61.538462
    assert row["matched_generation_share_pct"] == 86.666667
    assert row["renewable_unit_share_pct"] == 33.333333
    assert len(result.unmatched_observations) == 1
    assert result.unmatched_observations.iloc[0]["DUID"] == "UNMATCHED1"
    assert result.metadata["rows"] == 1


def test_checkpoint_round_trip(tmp_path: Path):
    month_dir = tmp_path / "data" / "derived" / "regional_renewable_penetration_feature_store" / "checkpoints" / "2024-01"
    month_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "interval_timestamp_utc": ["2024-01-01T00:05:00Z"],
            "region": ["NSW1"],
            "total_positive_generation_mw": [150.0],
            "renewable_positive_generation_mw": [80.0],
            "matched_positive_generation_mw": [130.0],
            "unmatched_positive_generation_mw": [20.0],
            "active_unit_count": [3],
            "renewable_active_unit_count": [1],
            "matched_active_unit_count": [2],
            "unmatched_active_unit_count": [1],
            "renewable_penetration_pct": [53.333333],
            "renewable_penetration_known_pct": [61.538462],
            "matched_generation_share_pct": [86.666667],
            "renewable_unit_share_pct": [50.0],
            "quality_score": [100.0],
            "point_in_time_available": [True],
            "source_month": ["2024-01"],
            "source_file": ["dummy"],
        }
    ).to_csv(month_dir / "regional_renewable_penetration_5min.csv.gz", index=False, compression="gzip")
    pd.DataFrame({"interval_timestamp_utc": ["2024-01-01T00:05:00Z"], "DUID": ["UNMATCHED1"]}).to_csv(
        month_dir / "unmatched_duid_observations.csv.gz",
        index=False,
        compression="gzip",
    )
    (month_dir / "monthly_metadata.json").write_text("{}", encoding="utf-8")
    (month_dir / ".complete.json").write_text("{}", encoding="utf-8")

    loaded = _load_checkpoint(month_dir)
    assert loaded is not None
    feature_store, unmatched, metadata = loaded
    assert len(feature_store) == 1
    assert len(unmatched) == 1
    assert metadata["checkpoint_dir"] == str(month_dir)


def test_canonical_hash_contract_metadata_shape():
    contract = canonical_hash_contract_metadata()
    assert contract["algorithm"] == "SHA-256"
    assert contract["contract_version"] == 1
    assert contract["scope"] == "renewable_penetration_features"
    assert contract["normalization"]["source_file"] == "basename_only"


def test_canonical_hash_invariant_to_machine_paths_for_published_v1():
    repo_root = Path(__file__).resolve().parents[3]
    features_csv = repo_root / "data" / "derived" / "renewable_penetration_v1" / "renewable_penetration_features_v1.csv"
    if not features_csv.exists():
        pytest.skip("Published renewable penetration v1 features CSV is not present.")

    expected_hash = "2d0943d8e0267d026c7d57a51cddf406a25ef89e913401c7dd75f90a1d08d5e1"
    base = pd.read_csv(features_csv, low_memory=False)
    observed = compute_feature_rows_canonical_hash_sha256(base)
    assert observed == expected_hash

    path_prefixes = [
        "/Users/hamish/project",
        "/home/runner/build",
        r"D:\agent\workspace",
    ]

    for prefix in path_prefixes:
        variant = base.copy()
        basename_only = variant["source_file"].astype(str).map(lambda value: Path(value.replace("\\", "/")).name)
        if prefix.startswith("D:\\"):
            variant["source_file"] = basename_only.map(lambda value: f"{prefix}\\{value}")
        else:
            variant["source_file"] = basename_only.map(lambda value: f"{prefix}/{value}")
        assert compute_feature_rows_canonical_hash_sha256(variant) == expected_hash


def test_canonical_hash_csv_parquet_and_source_output_match_contract_v1():
    repo_root = Path(__file__).resolve().parents[3]
    expected_hash = "2d0943d8e0267d026c7d57a51cddf406a25ef89e913401c7dd75f90a1d08d5e1"

    published_csv = repo_root / "data" / "derived" / "renewable_penetration_v1" / "renewable_penetration_features_v1.csv"
    published_parquet = repo_root / "data" / "derived" / "renewable_penetration_v1" / "renewable_penetration_features_v1.parquet"
    source_output = Path("/tmp/rrp_full/regional_renewable_penetration_5min.csv.gz")

    assert published_csv.exists()
    assert published_parquet.exists()
    assert source_output.exists()

    csv_df = pd.read_csv(published_csv, low_memory=False)
    parquet_df = pd.read_parquet(published_parquet)
    source_df = pd.read_csv(source_output, low_memory=False, compression="gzip")

    assert compute_feature_rows_canonical_hash_sha256(csv_df) == expected_hash
    assert compute_feature_rows_canonical_hash_sha256(parquet_df) == expected_hash
    assert compute_feature_rows_canonical_hash_sha256(source_df) == expected_hash
