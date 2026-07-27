from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "build_historical_feature_store.py"
MODULE_SPEC = importlib.util.spec_from_file_location("build_historical_feature_store", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError("Unable to load build_historical_feature_store module")
build_script = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(build_script)


def _write_minimum_checkpoint(month_dir: Path, row_count: int = 1) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)

    feature_store = pd.DataFrame(
        {
            "interval_timestamp_utc": [f"2020-01-01T00:{5 * (index + 1):02d}:00Z" for index in range(row_count)],
            "quality_score": [100.0] * row_count,
        }
    )
    feature_store.to_csv(month_dir / "historical_market_feature_store_5min.csv.gz", index=False, compression="gzip")

    dataset_status = pd.DataFrame(
        [{"dataset": "DISPATCHINTERCONNECTORRES", "status": "AVAILABLE", "rows": row_count, "files": 1}]
    )
    dataset_status.to_csv(month_dir / "historical_dataset_status.csv", index=False)

    metadata = {"start_date": "2020-01-01", "end_date": "2020-01-31", "months_completed": 1, "feature_rows": row_count}
    (month_dir / "historical_feature_store_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def test_non_empty_intervention_audit_round_trip(tmp_path: Path):
    path = tmp_path / "historical_intervention_audit.csv"
    frame = pd.DataFrame(
        [
            {
                "interval_timestamp_utc": "2020-01-01T00:05:00Z",
                "interconnector_id": "NSW1-QLD1",
                "runno": 1,
                "count_intervention_0": 1,
                "count_intervention_1": 0,
                "paired_intervention_values_differ": False,
            }
        ]
    )

    build_script._write_intervention_audit_csv(frame, path)
    loaded, warnings = build_script._load_intervention_audit_csv(path)

    assert warnings == []
    assert list(loaded.columns) == build_script.INTERVENTION_AUDIT_COLUMNS
    assert len(loaded) == 1


def test_header_only_empty_audit_is_readable(tmp_path: Path):
    path = tmp_path / "historical_intervention_audit.csv"

    build_script._write_intervention_audit_csv(pd.DataFrame(columns=build_script.INTERVENTION_AUDIT_COLUMNS), path)
    loaded, warnings = build_script._load_intervention_audit_csv(path)

    assert warnings == []
    assert list(loaded.columns) == build_script.INTERVENTION_AUDIT_COLUMNS
    assert loaded.empty


def test_legacy_zero_byte_audit_is_compatible(tmp_path: Path):
    path = tmp_path / "historical_intervention_audit.csv"
    path.write_bytes(b"")

    loaded, warnings = build_script._load_intervention_audit_csv(path)

    assert list(loaded.columns) == build_script.INTERVENTION_AUDIT_COLUMNS
    assert loaded.empty
    assert any("Legacy zero-byte intervention audit" in warning for warning in warnings)


def test_malformed_non_empty_audit_raises(tmp_path: Path):
    path = tmp_path / "historical_intervention_audit.csv"
    path.write_text('interval_timestamp_utc,interconnector_id\n"unterminated', encoding="utf-8")

    with pytest.raises(pd.errors.ParserError):
        build_script._load_intervention_audit_csv(path)


def test_checkpoint_reuse_with_header_only_empty_audit(tmp_path: Path):
    month_dir = tmp_path / "checkpoints" / "2020-01"
    _write_minimum_checkpoint(month_dir, row_count=2)
    build_script._write_intervention_audit_csv(pd.DataFrame(columns=build_script.INTERVENTION_AUDIT_COLUMNS), month_dir / "historical_intervention_audit.csv")

    loaded = build_script._load_checkpoint(month_dir)

    assert loaded is not None
    feature_store, dataset_status, intervention_audit, metadata = loaded
    assert len(feature_store) == 2
    assert len(dataset_status) == 1
    assert intervention_audit.empty
    assert list(intervention_audit.columns) == build_script.INTERVENTION_AUDIT_COLUMNS
    assert metadata["months_completed"] == 1


def test_checkpoint_reuse_preserves_rows_and_metadata(tmp_path: Path):
    month_dir = tmp_path / "checkpoints" / "2020-01"
    _write_minimum_checkpoint(month_dir, row_count=3)
    build_script._write_intervention_audit_csv(pd.DataFrame(columns=build_script.INTERVENTION_AUDIT_COLUMNS), month_dir / "historical_intervention_audit.csv")

    loaded = build_script._load_checkpoint(month_dir)
    assert loaded is not None
    feature_store, _, _, metadata = loaded

    assert len(feature_store) == 3
    assert metadata["feature_rows"] == 3
    assert metadata["start_date"] == "2020-01-01"
    assert metadata["end_date"] == "2020-01-31"
