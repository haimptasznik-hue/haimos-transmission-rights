from __future__ import annotations

import io
from pathlib import Path
import sys
import zipfile

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.market_state_database import MarketStateDatabase


def _build_dispatchprice_archive_bytes() -> bytes:
    csv_lines = [
        'D,DISPATCH,PRICE,1,"2024/01/01 00:05:00",X,NSW1,Y,100.0',
        'D,DISPATCH,PRICE,1,"2024/01/01 00:05:00",X,QLD1,Y,90.0',
        'D,DISPATCH,PRICE,1,"2024/01/01 00:10:00",X,NSW1,Y,101.5',
        'D,DISPATCH,PRICE,1,"2024/01/01 00:10:00",X,QLD1,Y,95.5',
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("PUBLIC_DVD_DISPATCHPRICE_202401010000.CSV", "\n".join(csv_lines))
    return buffer.getvalue()


def _build_dispatchinterconnectorres_archive_bytes() -> bytes:
    csv_lines = [
        'I,DISPATCH,INTERCONNECTORRES,1,SETTLEMENTDATE,RUNNO,INTERCONNECTORID,DISPATCHINTERVAL,INTERVENTION,METEREDMWFLOW,MWFLOW,MWLOSSES,EXPORTLIMIT,IMPORTLIMIT',
        'D,DISPATCH,INTERCONNECTORRES,1,"2024/01/01 00:05:00",1,NSW1-QLD1,1,0,450.0,445.0,0.0,500.0,500.0',
        'D,DISPATCH,INTERCONNECTORRES,1,"2024/01/01 00:10:00",1,NSW1-QLD1,1,0,490.0,489.0,0.0,500.0,500.0',
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("PUBLIC_ARCHIVE#DISPATCHINTERCONNECTORRES#FILE01#202401010000.CSV", "\n".join(csv_lines))
    return buffer.getvalue()


def test_parse_dispatchprice_archive_bytes_extracts_expected_rows():
    frame = MarketStateDatabase.parse_dispatchprice_archive_bytes(_build_dispatchprice_archive_bytes())

    assert list(frame.columns) == ["SETTLEMENTDATE", "REGIONID", "RRP"]
    assert len(frame) == 4
    assert sorted(frame["REGIONID"].unique().tolist()) == ["NSW1", "QLD1"]


def test_ingest_historical_dispatchprice_archive_normalizes_spread(tmp_path: Path):
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "PUBLIC_DVD_DISPATCHPRICE_202401010000.zip"
    archive_path.write_bytes(_build_dispatchprice_archive_bytes())

    market_db = MarketStateDatabase()
    result = market_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-13T00:00:00Z",
        start_month="2024-01",
        end_month="2024-01",
    )

    state = market_db.state.sort_values("interval_timestamp_utc").reset_index(drop=True)

    assert result.files_processed == 1
    assert result.rows_read == 4
    assert result.rows_normalized == 2
    assert result.rows_valid == 2
    assert result.download_attempts == 0
    assert result.download_successes == 0
    assert state["nsw_rrp"].tolist() == [100.0, 101.5]
    assert state["qld_rrp"].tolist() == [90.0, 95.5]
    assert state["nsw_qld_spread"].tolist() == [10.0, 6.0]
    assert pd.notna(state.loc[0, "record_source"])


def test_parse_dispatchinterconnectorres_archive_bytes_extracts_expected_rows():
    frame = MarketStateDatabase.parse_dispatchinterconnectorres_archive_bytes(
        _build_dispatchinterconnectorres_archive_bytes()
    )

    assert list(frame.columns) == [
        "SETTLEMENTDATE",
        "INTERCONNECTORID",
        "METEREDMWFLOW",
        "MWFLOW",
        "EXPORTLIMIT",
        "IMPORTLIMIT",
    ]
    assert len(frame) == 2
    assert frame["INTERCONNECTORID"].tolist() == ["NSW1-QLD1", "NSW1-QLD1"]


def test_ingest_historical_dispatchinterconnectorres_archive_adds_flow_and_stress(tmp_path: Path):
    archive_dir = tmp_path / "flow_archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "PUBLIC_ARCHIVE#DISPATCHINTERCONNECTORRES#FILE01#202401010000.zip"
    archive_path.write_bytes(_build_dispatchinterconnectorres_archive_bytes())

    market_db = MarketStateDatabase()
    result = market_db.ingest_historical_dispatchinterconnectorres_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-13T00:00:00Z",
        start_month="2024-01",
        end_month="2024-01",
    )

    state = market_db.state.sort_values("interval_timestamp_utc").reset_index(drop=True)

    assert result.files_processed == 1
    assert result.rows_read == 2
    assert result.rows_normalized == 2
    assert result.rows_valid == 2
    assert state["mw_flow"].tolist() == [450.0, 490.0]
    assert state["available_capability_mw"].tolist() == [500.0, 500.0]
    assert state["utilisation_pct"].tolist() == [90.0, 98.0]
    assert all(value is not None for value in state["interconnector_stress_index"].tolist())


def test_dispatchprice_incremental_cache_skips_unchanged_hash(tmp_path: Path):
    archive_dir = tmp_path / "archives"
    reports_dir = tmp_path / "reports"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "PUBLIC_DVD_DISPATCHPRICE_202401010000.zip"
    archive_path.write_bytes(_build_dispatchprice_archive_bytes())

    first_db = MarketStateDatabase()
    first = first_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-14T00:00:00Z",
        start_month="2024-01",
        end_month="2024-01",
        reports_dir=reports_dir,
    )
    assert first.files_processed == 1
    assert first.rows_read == 4
    assert first.rows_normalized == 2

    second_db = MarketStateDatabase()
    second = second_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-14T00:10:00Z",
        start_month="2024-01",
        end_month="2024-01",
        reports_dir=reports_dir,
    )

    manifest_path = reports_dir / "phase5c_dispatchprice_ingestion_manifest.csv"
    cache_report_path = reports_dir / "phase5c_dispatchprice_cache_report.md"
    failed_path = reports_dir / "phase5c_dispatchprice_failed_files.csv"

    manifest = pd.read_csv(manifest_path)
    success_rows = manifest[manifest["status"] == "SUCCESS"]

    assert second.files_processed == 0
    assert second.rows_read == 0
    assert second.rows_normalized == 0
    assert len(success_rows) == 1
    assert cache_report_path.exists()
    assert failed_path.exists()


def test_dispatchprice_resume_after_interruption_reprocesses_failed_hash(tmp_path: Path):
    archive_dir = tmp_path / "archives"
    reports_dir = tmp_path / "reports"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "PUBLIC_DVD_DISPATCHPRICE_202401010000.zip"
    archive_path.write_bytes(_build_dispatchprice_archive_bytes())

    failing_db = MarketStateDatabase()
    original_parser = failing_db.parse_dispatchprice_archive_bytes
    call_count = {"value": 0}

    def flaky_parser(content: bytes, progress_meta=None):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise RuntimeError("simulated interruption")
        return original_parser(content, progress_meta=progress_meta)

    failing_db.parse_dispatchprice_archive_bytes = flaky_parser  # type: ignore[method-assign]
    first = failing_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-14T00:00:00Z",
        start_month="2024-01",
        end_month="2024-01",
        reports_dir=reports_dir,
    )
    assert first.files_processed == 0

    resume_db = MarketStateDatabase()
    second = resume_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc="2026-07-14T00:10:00Z",
        start_month="2024-01",
        end_month="2024-01",
        reports_dir=reports_dir,
    )

    manifest_path = reports_dir / "phase5c_dispatchprice_ingestion_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    assert second.files_processed == 1
    assert second.rows_normalized == 2
    assert "SUCCESS" in manifest["status"].tolist()