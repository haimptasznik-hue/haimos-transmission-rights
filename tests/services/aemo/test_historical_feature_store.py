from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.historical_feature_store import (  # noqa: E402
    _list_cache_files,
    _normalize_interconnector_columns,
    _compute_quality_score,
    _read_cached_csv,
)


def test_normalize_interconnector_columns_uses_series_defaults():
    frame = pd.DataFrame(
        {
            "SETTLEMENTDATE": ["2024-10-01 00:05:00", "2024-10-01 00:10:00"],
            "INTERCONNECTORID": ["NSW1-QLD1", "VIC1-NSW1"],
        }
    )

    normalized = _normalize_interconnector_columns(frame)

    assert isinstance(normalized["INTERVENTION"], pd.Series)
    assert len(normalized["INTERVENTION"]) == len(frame)
    assert normalized["INTERVENTION"].tolist() == [0, 0]
    assert normalized["MWFLOW"].isna().all()
    assert normalized["RUNNO"].isna().all()


def test_list_cache_files_filters_date_window(tmp_path: Path):
    cache_file = tmp_path / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres" / ".cache" / "year=2024" / "month=10" / "PUBLIC_DVD_DISPATCHINTERCONNECTORRES_202410010000.dispatchinterconnectorres.csv.gz"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("dummy", encoding="utf-8")

    selected = _list_cache_files(
        tmp_path / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres",
        ".dispatchinterconnectorres.csv.gz",
        start_date="2024-10-01",
        end_date="2024-10-31",
    )

    assert selected == [cache_file]

    excluded = _list_cache_files(
        tmp_path / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres",
        ".dispatchinterconnectorres.csv.gz",
        start_date="2024-11-01",
        end_date="2024-11-30",
    )

    assert excluded == []


def test_read_cached_csv_skips_corrupt_gzip(tmp_path: Path):
    bad_file = tmp_path / "bad.csv.gz"
    bad_file.write_text("not a gzip stream", encoding="utf-8")

    assert _read_cached_csv(bad_file) is None


def test_compute_quality_score_returns_series_for_normal_frame():
    frame = pd.DataFrame(
        {
            "interval_timestamp_utc": ["2024-10-01T00:05:00Z", "2024-10-01T00:10:00Z"],
            "feature_a": [1.0, None],
            "feature_b": [2.0, 3.0],
        }
    )

    quality_score = _compute_quality_score(frame, ["feature_a", "feature_b"])

    assert isinstance(quality_score, pd.Series)
    assert quality_score.tolist() == [100.0, 50.0]
    assert quality_score.name == "quality_score"


def test_compute_quality_score_returns_nan_series_when_no_features():
    frame = pd.DataFrame({"interval_timestamp_utc": ["2024-10-01T00:05:00Z", "2024-10-01T00:10:00Z"]})

    quality_score = _compute_quality_score(frame, [])

    assert isinstance(quality_score, pd.Series)
    assert quality_score.index.equals(frame.index)
    assert quality_score.isna().all()
    assert quality_score.name == "quality_score"
