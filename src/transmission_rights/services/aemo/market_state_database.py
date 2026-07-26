from __future__ import annotations

import csv
import hashlib
import io
import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

import pandas as pd

from transmission_rights.domain.interconnectors import Interconnector


MARKET_STATE_SCHEMA: tuple[tuple[str, str, str], ...] = (
    ("interval_timestamp_utc", "datetime", "5-minute interval timestamp in UTC"),
    ("asof_publish_timestamp_utc", "datetime", "Timestamp when source record was published/ingested"),
    ("decision_cutoff_utc", "datetime", "Decision-time cutoff for PIT replay queries"),
    ("record_version", "int", "Monotonic version for re-ingested corrections"),
    ("record_source", "str", "Source table/file name"),
    ("corridor", "str", "Interconnector corridor label (e.g., NSW1-QLD1)"),
    ("direction", "str", "Direction key for corridor (e.g., NSW1->QLD1)"),
    ("ruleset_id", "str", "Commercial ruleset identifier"),
    ("nsw_rrp", "float", "NSW regional reference price"),
    ("qld_rrp", "float", "QLD regional reference price"),
    ("vic_rrp", "float", "VIC regional reference price"),
    ("sa_rrp", "float", "SA regional reference price"),
    ("tas_rrp", "float", "TAS regional reference price"),
    ("nsw_qld_spread", "float", "NSW minus QLD price spread"),
    ("mw_flow", "float", "Directional interconnector flow (MW)"),
    ("available_capability_mw", "float", "Available interconnector capability (MW)"),
    ("utilisation_pct", "float", "Absolute flow / capability percentage"),
    ("interconnector_stress_index", "float", "0-1 stress score from spread and corridor loading"),
    ("constraint_binding_flag", "bool", "Any binding constraint affecting corridor at interval"),
    ("constraint_marginal_value", "float", "Constraint marginal value (if binding)"),
    ("constraint_time_at_limit_pct", "float", "Trailing share of intervals at or near constraint limit"),
    ("constraint_duration_intervals", "int", "Current consecutive binding duration in 5-minute intervals"),
    ("constraint_recurrence_count", "int", "Trailing count of binding episodes for corridor"),
    ("regional_operational_demand", "float", "Regional operational demand"),
    ("forecast_demand", "float", "Forecast demand at decision time"),
    ("demand_anomaly", "float", "Demand deviation vs seasonal normal"),
    ("demand_short_term_change", "float", "Short-term demand change vs prior interval"),
    ("demand_ramp", "float", "Demand ramp vs prior hour"),
    ("renewable_penetration_pct", "float", "Renewable share of generation"),
    ("coal_availability_pct", "float", "Coal fleet available capacity percentage"),
    ("gas_availability_pct", "float", "Gas fleet available capacity percentage"),
    ("battery_net_dispatch_mw", "float", "Battery net charging/discharging"),
    ("temperature_c", "float", "Temperature"),
    ("wind_speed_ms", "float", "Wind speed"),
    ("solar_irradiance_wm2", "float", "Solar irradiance"),
    ("rainfall_mm", "float", "Rainfall"),
    ("network_outage_flag", "bool", "Whether major outage active"),
    ("irsr", "float", "Interval residue settlement amount"),
    ("sra_payout_per_unit", "float", "SRA payout per unit (closed-settlement only)"),
    ("auction_clearing_price", "float", "Auction clearing price reference"),
    ("units_sold", "float", "Auction units sold"),
)


PRICE_REGION_MAP = {
    "NSW1": "nsw_rrp",
    "QLD1": "qld_rrp",
    "VIC1": "vic_rrp",
    "SA1": "sa_rrp",
    "TAS1": "tas_rrp",
}

_DISPATCHPRICE_ARCHIVE_URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCHPRICE_{year}{month:02d}010000.zip"
)

_DISPATCHINTERCONNECTORRES_ARCHIVE_URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCHINTERCONNECTORRES_{year}{month:02d}010000.zip"
)

_DISPATCHREGIONSUM_ARCHIVE_URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCHREGIONSUM_{year}{month:02d}010000.zip"
)

_DISPATCHCONSTRAINT_ARCHIVE_URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCHCONSTRAINT_{year}{month:02d}010000.zip"
)

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_DISPATCHPRICE_MANIFEST_COLUMNS: tuple[str, ...] = (
    "source_file_path",
    "file_size_bytes",
    "modified_timestamp_utc",
    "sha256_hash",
    "rows_ingested",
    "ingestion_timestamp_utc",
    "output_partition_path",
    "cache_schema_version",
    "status",
    "error",
)

_DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION = 2
_DISPATCHREGIONSUM_REQUIRED_NORMALIZED_COLUMNS: tuple[str, ...] = (
    "interval_timestamp_utc",
    "region_id",
    "regional_operational_demand",
)


@dataclass(frozen=True)
class DispatchPriceIngestionResult:
    rows_read: int
    rows_normalized: int
    rows_valid: int
    files_processed: int
    download_attempts: int = 0
    download_successes: int = 0


@dataclass(frozen=True)
class InterconnectorFlowIngestionResult:
    rows_read: int
    rows_normalized: int
    rows_valid: int
    files_processed: int
    download_attempts: int = 0
    download_successes: int = 0


@dataclass(frozen=True)
class RegionalDemandIngestionResult:
    rows_read: int
    rows_normalized: int
    rows_valid: int
    files_processed: int
    download_attempts: int = 0
    download_successes: int = 0


@dataclass(frozen=True)
class ConstraintIngestionResult:
    rows_read: int
    rows_normalized: int
    rows_valid: int
    files_processed: int
    download_attempts: int = 0
    download_successes: int = 0


class BulkCacheLoader:
    @staticmethod
    def load(
        *,
        cache_root: Path,
        key_columns: list[str],
        month_token_resolver,
        month_range_resolver,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> tuple[pd.DataFrame, dict[str, object], int, int, int]:
        if not cache_root.exists():
            empty_profile = {
                "loader_type": "bulk_single_pass",
                "input_row_count": 0,
                "cache_files_loaded": 0,
                "cache_files_skipped": 0,
                "concat_operations": 0,
                "dedup_operations": 0,
                "sort_operations": 0,
                "upsert_operations": 0,
                "duplicates_before_dedup": 0,
                "duplicates_after_dedup": 0,
                "timings_seconds": {
                    "file_reads": 0.0,
                    "concatenation": 0.0,
                    "deduplication": 0.0,
                    "final_assignment": 0.0,
                    "total_runtime": 0.0,
                },
            }
            return pd.DataFrame(), empty_profile, 0, 0, 0

        parquet_files = sorted(cache_root.rglob("*.parquet"))
        csv_files = sorted(cache_root.rglob("*.csv.gz"))
        cache_files = parquet_files if parquet_files else csv_files

        if start_month and end_month:
            allowed_months = {
                f"{year:04d}-{month:02d}"
                for year, month in month_range_resolver(start_month, end_month)
            }
            cache_files = [
                file_path
                for file_path in cache_files
                if month_token_resolver(file_path) in allowed_months
            ]

        rows_read = 0
        rows_norm = 0
        files_processed = 0

        read_start = time.perf_counter()
        frames: list[pd.DataFrame] = []
        for file_path in cache_files:
            try:
                if file_path.suffix == ".parquet":
                    frame = pd.read_parquet(file_path)
                else:
                    frame = pd.read_csv(file_path)
            except Exception:
                continue

            if frame.empty:
                continue
            files_processed += 1
            rows_read += len(frame)
            rows_norm += len(frame)
            frames.append(frame)
        read_seconds = time.perf_counter() - read_start

        if not frames:
            profile = {
                "loader_type": "bulk_single_pass",
                "input_row_count": 0,
                "cache_files_loaded": files_processed,
                "cache_files_skipped": int(max(len(cache_files) - files_processed, 0)),
                "concat_operations": 0,
                "dedup_operations": 0,
                "sort_operations": 0,
                "upsert_operations": 0,
                "duplicates_before_dedup": 0,
                "duplicates_after_dedup": 0,
                "timings_seconds": {
                    "file_reads": round(read_seconds, 6),
                    "concatenation": 0.0,
                    "deduplication": 0.0,
                    "final_assignment": 0.0,
                    "total_runtime": round(read_seconds, 6),
                },
            }
            return pd.DataFrame(), profile, rows_read, rows_norm, files_processed

        concat_start = time.perf_counter()
        combined = pd.concat(frames, ignore_index=True)
        concat_seconds = time.perf_counter() - concat_start

        if "region_id" not in combined.columns:
            direction_series = combined.get("direction", pd.Series(dtype=str)).astype(str)
            combined["region_id"] = direction_series.str.split("->").str[0].str.strip().str.upper()
        else:
            combined["region_id"] = combined["region_id"].astype(str).str.upper().str.strip()

        if "interval_timestamp_utc" in combined.columns:
            combined["interval_timestamp_utc"] = pd.to_datetime(
                combined["interval_timestamp_utc"], utc=True, errors="coerce"
            ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        dedup_start = time.perf_counter()
        duplicates_before = int(combined.duplicated(subset=key_columns, keep="last").sum())
        record_version_series = combined.get("record_version", pd.Series([pd.NA] * len(combined)))
        asof_series = combined.get("asof_publish_timestamp_utc", pd.Series([pd.NA] * len(combined)))
        combined["__record_version_num"] = pd.to_numeric(record_version_series, errors="coerce").fillna(0)
        combined["__asof_ts"] = pd.to_datetime(asof_series, utc=True, errors="coerce")
        combined = combined.sort_values(key_columns + ["__record_version_num", "__asof_ts"])
        deduplicated = combined.drop_duplicates(subset=key_columns, keep="last").copy()
        deduplicated = deduplicated.drop(columns=["__record_version_num", "__asof_ts"], errors="ignore")
        duplicates_after = int(deduplicated.duplicated(subset=key_columns, keep=False).sum())
        dedup_seconds = time.perf_counter() - dedup_start

        total_seconds = read_seconds + concat_seconds + dedup_seconds
        profile = {
            "loader_type": "bulk_single_pass",
            "input_row_count": int(len(combined)),
            "cache_files_loaded": files_processed,
            "cache_files_skipped": int(max(len(cache_files) - files_processed, 0)),
            "concat_operations": 1,
            "dedup_operations": 1,
            "sort_operations": 1,
            "upsert_operations": 0,
            "duplicates_before_dedup": duplicates_before,
            "duplicates_after_dedup": duplicates_after,
            "timings_seconds": {
                "file_reads": round(read_seconds, 6),
                "concatenation": round(concat_seconds, 6),
                "deduplication": round(dedup_seconds, 6),
                "final_assignment": 0.0,
                "total_runtime": round(total_seconds, 6),
            },
        }
        return deduplicated, profile, rows_read, rows_norm, files_processed


class IngestionStalledError(RuntimeError):
    def __init__(self, report: dict[str, object]) -> None:
        super().__init__(str(report))
        self.report = report


class MarketStateDatabase:
    _PRIMARY_CORRIDOR = "NSW1-QLD1"
    _STALL_TIMEOUT_SECONDS = 600
    _PROGRESS_LOG_INTERVAL_ROWS = 100_000

    def __init__(self) -> None:
        self._state = pd.DataFrame(columns=[name for name, _, _ in MARKET_STATE_SCHEMA])

    @property
    def state(self) -> pd.DataFrame:
        return self._state.copy()

    @staticmethod
    def schema_dictionary() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"column": name, "dtype": dtype, "description": desc}
                for name, dtype, desc in MARKET_STATE_SCHEMA
            ]
        )

    @staticmethod
    def _empty_market_state_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=[name for name, _, _ in MARKET_STATE_SCHEMA])

    @staticmethod
    def _align_to_market_state_schema(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for column_name, _, _ in MARKET_STATE_SCHEMA:
            if column_name not in out.columns:
                out[column_name] = pd.NA
        return out[[name for name, _, _ in MARKET_STATE_SCHEMA]].copy()

    @staticmethod
    def _month_range(start_month: str, end_month: str) -> list[tuple[int, int]]:
        start_period = pd.Period(start_month, freq="M")
        end_period = pd.Period(end_month, freq="M")
        if end_period < start_period:
            return []
        periods = pd.period_range(start=start_period, end=end_period, freq="M")
        return [(int(period.year), int(period.month)) for period in periods]

    @staticmethod
    def _download_archive(url: str) -> bytes:
        request = Request(url, headers=_REQUEST_HEADERS)
        with urlopen(request, timeout=120) as response:
            return response.read()

    @staticmethod
    def _memory_usage_mb() -> float | None:
        try:
            import resource

            raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            if raw <= 0:
                return None
            # macOS reports bytes; Linux reports KB.
            if raw > 10_000_000:
                return round(raw / (1024 * 1024), 2)
            return round(raw / 1024, 2)
        except Exception:
            return None

    @classmethod
    def _cache_file_path(cls, raw_archive_dir: Path, archive_name: str, suffix: str) -> Path:
        cache_dir = raw_archive_dir / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe_name = archive_name.replace(".zip", "")
        return cache_dir / f"{safe_name}.{suffix}.csv.gz"

    @staticmethod
    def _dispatchprice_cache_root(raw_archive_dir: Path) -> Path:
        return raw_archive_dir / "dispatchprice_normalized_cache"

    @staticmethod
    def _dispatchinterconnectorres_cache_root(raw_archive_dir: Path) -> Path:
        return raw_archive_dir / "dispatchinterconnectorres_normalized_cache"

    @staticmethod
    def _dispatchregionsum_cache_root(raw_archive_dir: Path) -> Path:
        return raw_archive_dir / "dispatchregionsum_normalized_cache"

    @staticmethod
    def _dispatchprice_manifest_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchprice_ingestion_manifest.csv"

    @staticmethod
    def _dispatchprice_cache_report_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchprice_cache_report.md"

    @staticmethod
    def _dispatchinterconnectorres_manifest_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchinterconnectorres_ingestion_manifest.csv"

    @staticmethod
    def _dispatchregionsum_manifest_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchregionsum_ingestion_manifest.csv"

    @staticmethod
    def _dispatchinterconnectorres_cache_report_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchinterconnectorres_cache_report.md"

    @staticmethod
    def _dispatchregionsum_cache_report_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchregionsum_cache_report.md"

    @staticmethod
    def _dispatchprice_failed_files_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchprice_failed_files.csv"

    @staticmethod
    def _dispatchinterconnectorres_failed_files_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchinterconnectorres_failed_files.csv"

    @staticmethod
    def _dispatchregionsum_failed_files_path(reports_dir: Path) -> Path:
        return reports_dir / "phase5c_dispatchregionsum_failed_files.csv"

    @staticmethod
    def _file_sha256(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _to_utc_iso(ts: float) -> str:
        return pd.to_datetime(ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _supports_parquet() -> bool:
        for module_name in ("pyarrow", "fastparquet"):
            try:
                importlib.import_module(module_name)
                return True
            except Exception:
                continue
        return False

    @classmethod
    def _load_dispatchprice_manifest(cls, manifest_path: Path) -> pd.DataFrame:
        if not manifest_path.exists():
            return pd.DataFrame(columns=list(_DISPATCHPRICE_MANIFEST_COLUMNS))
        try:
            frame = pd.read_csv(manifest_path)
        except Exception:
            return pd.DataFrame(columns=list(_DISPATCHPRICE_MANIFEST_COLUMNS))
        for column in _DISPATCHPRICE_MANIFEST_COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA
        return frame[list(_DISPATCHPRICE_MANIFEST_COLUMNS)].copy()

    @classmethod
    def _save_dispatchprice_manifest(cls, manifest_path: Path, manifest: pd.DataFrame) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest[list(_DISPATCHPRICE_MANIFEST_COLUMNS)].to_csv(manifest_path, index=False)

    @classmethod
    def _upsert_manifest_row(cls, manifest: pd.DataFrame, row: dict[str, object]) -> pd.DataFrame:
        if manifest.empty:
            return pd.DataFrame([row], columns=list(_DISPATCHPRICE_MANIFEST_COLUMNS))
        key = str(row.get("sha256_hash", ""))
        out = manifest[manifest["sha256_hash"].astype(str) != key].copy()
        out = pd.concat([out, pd.DataFrame([row])], ignore_index=True)
        return out[list(_DISPATCHPRICE_MANIFEST_COLUMNS)].copy()

    @staticmethod
    def _cache_output_has_columns(output_path: Path, required_columns: tuple[str, ...]) -> bool:
        if not output_path.exists():
            return False
        try:
            if output_path.suffix == ".parquet":
                sample = pd.read_parquet(output_path)
            else:
                sample = pd.read_csv(output_path, nrows=5)
        except Exception:
            return False
        return set(required_columns).issubset(sample.columns)

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        rem = int(seconds % 60)
        return f"{minutes}m {rem}s"

    @classmethod
    def _log_file_progress(
        cls,
        *,
        function_name: str,
        files_completed: int,
        files_total: int,
        rows_processed: int,
        elapsed_seconds: float,
    ) -> None:
        avg_per_file = (elapsed_seconds / files_completed) if files_completed > 0 else 0.0
        remaining_files = max(files_total - files_completed, 0)
        eta_seconds = avg_per_file * remaining_files
        payload = {
            "event": "ingestion_file_progress",
            "function": function_name,
            "files_completed": files_completed,
            "files_total": files_total,
            "rows_processed": rows_processed,
            "elapsed": cls._format_seconds(elapsed_seconds),
            "eta": cls._format_seconds(eta_seconds),
            "memory_mb": cls._memory_usage_mb(),
        }
        print(json.dumps(payload), flush=True)

    def ingest_dispatchprice_cache(self, raw_archive_dir: Path) -> DispatchPriceIngestionResult:
        return self.load_dispatchprice_cache_bulk(raw_archive_dir=raw_archive_dir)

    @staticmethod
    def _cache_file_month_token(file_path: Path) -> str | None:
        match = re.search(r"year=(\d{4})/month=(\d{2})", file_path.as_posix())
        if match is None:
            return None
        return f"{match.group(1)}-{match.group(2)}"

    def load_dispatchprice_cache_bulk(
        self,
        raw_archive_dir: Path,
        start_month: str | None = None,
        end_month: str | None = None,
        reports_dir: Path | None = None,
    ) -> DispatchPriceIngestionResult:
        assign_start = time.perf_counter()
        deduplicated, profile_payload, rows_read, rows_norm, files_processed = BulkCacheLoader.load(
            cache_root=self._dispatchprice_cache_root(raw_archive_dir),
            key_columns=["interval_timestamp_utc", "region_id"],
            month_token_resolver=self._cache_file_month_token,
            month_range_resolver=self._month_range,
            start_month=start_month,
            end_month=end_month,
        )
        existing_table_row_count = int(len(self._state))
        if not deduplicated.empty:
            aligned = self._align_to_market_state_schema(deduplicated)
            self._state = self._recompute_derived_fields(aligned).reset_index(drop=True)
        assign_seconds = time.perf_counter() - assign_start

        profile_payload["function"] = "load_dispatchprice_cache_bulk"
        profile_payload["existing_table_row_count"] = existing_table_row_count
        profile_payload["key_columns"] = ["interval_timestamp_utc", "region_id"]
        profile_payload["timings_seconds"]["final_assignment"] = round(assign_seconds, 6)
        profile_payload["timings_seconds"]["total_runtime"] = round(
            float(profile_payload["timings_seconds"]["total_runtime"]) + assign_seconds,
            6,
        )
        self._last_dispatchprice_bulk_profile = profile_payload

        if reports_dir is not None:
            reports_dir.mkdir(parents=True, exist_ok=True)
            profile_path = reports_dir / "phase5c5_dispatchprice_bulkload_profile.csv"
            profile_rows = [
                {
                    "stage": stage_name,
                    "seconds": profile_payload["timings_seconds"][stage_name],
                    "input_row_count": profile_payload["input_row_count"],
                    "existing_table_row_count": profile_payload["existing_table_row_count"],
                    "duplicates_before_dedup": profile_payload["duplicates_before_dedup"],
                    "duplicates_after_dedup": profile_payload["duplicates_after_dedup"],
                }
                for stage_name in ["file_reads", "concatenation", "deduplication", "final_assignment", "total_runtime"]
            ]
            pd.DataFrame(profile_rows).to_csv(profile_path, index=False)

        rows_valid = int(self._state["nsw_qld_spread"].notna().sum()) if not self._state.empty else 0
        return DispatchPriceIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_dispatchinterconnectorres_cache(self, raw_archive_dir: Path) -> InterconnectorFlowIngestionResult:
        return self.load_dispatchinterconnectorres_cache_bulk(raw_archive_dir=raw_archive_dir)

    def load_dispatchinterconnectorres_cache_bulk(
        self,
        raw_archive_dir: Path,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> InterconnectorFlowIngestionResult:
        assign_start = time.perf_counter()
        deduplicated, profile_payload, rows_read, rows_norm, files_processed = BulkCacheLoader.load(
            cache_root=self._dispatchinterconnectorres_cache_root(raw_archive_dir),
            key_columns=["interval_timestamp_utc", "region_id"],
            month_token_resolver=self._cache_file_month_token,
            month_range_resolver=self._month_range,
            start_month=start_month,
            end_month=end_month,
        )
        existing_table_row_count = int(len(self._state))
        if not deduplicated.empty:
            aligned = self._align_to_market_state_schema(deduplicated)
            self._state = self._recompute_derived_fields(aligned).reset_index(drop=True)
        assign_seconds = time.perf_counter() - assign_start

        profile_payload["function"] = "load_dispatchinterconnectorres_cache_bulk"
        profile_payload["existing_table_row_count"] = existing_table_row_count
        profile_payload["key_columns"] = ["interval_timestamp_utc", "region_id"]
        profile_payload["timings_seconds"]["final_assignment"] = round(assign_seconds, 6)
        profile_payload["timings_seconds"]["total_runtime"] = round(
            float(profile_payload["timings_seconds"]["total_runtime"]) + assign_seconds,
            6,
        )
        self._last_dispatchinterconnectorres_bulk_profile = profile_payload

        rows_valid = int(self._state["mw_flow"].notna().sum()) if not self._state.empty else 0
        return InterconnectorFlowIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_dispatchregionsum_cache(self, raw_archive_dir: Path) -> RegionalDemandIngestionResult:
        return self.load_dispatchregionsum_cache_bulk(raw_archive_dir=raw_archive_dir)

    def load_dispatchregionsum_cache_bulk(
        self,
        raw_archive_dir: Path,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> RegionalDemandIngestionResult:
        assign_start = time.perf_counter()
        deduplicated, profile_payload, rows_read, rows_norm, files_processed = BulkCacheLoader.load(
            cache_root=self._dispatchregionsum_cache_root(raw_archive_dir),
            key_columns=["interval_timestamp_utc", "region_id"],
            month_token_resolver=self._cache_file_month_token,
            month_range_resolver=self._month_range,
            start_month=start_month,
            end_month=end_month,
        )
        existing_table_row_count = int(len(self._state))
        if not deduplicated.empty:
            aligned = self._align_to_market_state_schema(deduplicated)
            self._state = self._recompute_derived_fields(aligned).reset_index(drop=True)
        assign_seconds = time.perf_counter() - assign_start

        profile_payload["function"] = "load_dispatchregionsum_cache_bulk"
        profile_payload["existing_table_row_count"] = existing_table_row_count
        profile_payload["key_columns"] = ["interval_timestamp_utc", "region_id"]
        profile_payload["timings_seconds"]["final_assignment"] = round(assign_seconds, 6)
        profile_payload["timings_seconds"]["total_runtime"] = round(
            float(profile_payload["timings_seconds"]["total_runtime"]) + assign_seconds,
            6,
        )
        self._last_dispatchregionsum_bulk_profile = profile_payload

        rows_valid = int(self._state["regional_operational_demand"].notna().sum()) if not self._state.empty else 0
        return RegionalDemandIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def load_dispatchregionsum_component_cache(self, raw_archive_dir: Path) -> pd.DataFrame:
        cache_root = self._dispatchregionsum_cache_root(raw_archive_dir)
        if not cache_root.exists():
            return pd.DataFrame(
                columns=[
                    "interval_timestamp_utc",
                    "region_id",
                    "regional_operational_demand",
                    "forecast_demand",
                    "source_file",
                    "publish_timestamp_utc",
                ]
            )

        parquet_files = sorted(cache_root.rglob("*.parquet"))
        csv_files = sorted(cache_root.rglob("*.csv.gz"))
        cache_files = parquet_files if parquet_files else csv_files

        frames: list[pd.DataFrame] = []
        for file_path in cache_files:
            try:
                if file_path.suffix == ".parquet":
                    frame = pd.read_parquet(file_path)
                else:
                    frame = pd.read_csv(file_path)
            except Exception:
                continue

            if frame.empty:
                continue
            if {"interval_timestamp_utc", "region_id", "regional_operational_demand"}.issubset(frame.columns):
                frames.append(frame)

        if not frames:
            return pd.DataFrame(
                columns=[
                    "interval_timestamp_utc",
                    "region_id",
                    "regional_operational_demand",
                    "forecast_demand",
                    "source_file",
                    "publish_timestamp_utc",
                ]
            )

        out = pd.concat(frames, ignore_index=True)
        out["interval_timestamp_utc"] = pd.to_datetime(out["interval_timestamp_utc"], utc=True, errors="coerce")
        out["region_id"] = out["region_id"].astype(str).str.upper().str.strip()
        out = out[out["interval_timestamp_utc"].notna()].copy()
        return out

    @classmethod
    def _log_progress(
        cls,
        *,
        function_name: str,
        files_processed: int,
        rows_processed: int,
        current_file: str,
        row_in_current_file: int | None = None,
    ) -> float:
        payload = {
            "event": "ingestion_progress",
            "function": function_name,
            "files_processed": files_processed,
            "rows_processed": rows_processed,
            "current_file": current_file,
            "row_in_current_file": row_in_current_file,
            "memory_mb": cls._memory_usage_mb(),
            "timestamp": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        print(json.dumps(payload), flush=True)
        return time.time()

    @classmethod
    def _check_stall(
        cls,
        *,
        function_name: str,
        files_processed: int,
        rows_processed: int,
        current_file: str,
        row_in_current_file: int | None,
        last_output_at: float,
    ) -> None:
        if (time.time() - last_output_at) <= cls._STALL_TIMEOUT_SECONDS:
            return
        report = {
            "event": "ingestion_stalled",
            "where_execution_stopped": function_name,
            "function_consuming_time": function_name,
            "files_processed": files_processed,
            "rows_processed": rows_processed,
            "current_file_being_parsed": current_file,
            "row_in_current_file": row_in_current_file,
            "memory_mb": cls._memory_usage_mb(),
            "policy": "Stopped after >10 minutes without new output.",
        }
        raise IngestionStalledError(report)

    @staticmethod
    def _format_timestamp(value: object) -> str | None:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _combine_record_sources(series: pd.Series) -> str | None:
        values = []
        for value in series.dropna().astype(str):
            if value and value not in values:
                values.append(value)
        if not values:
            return None
        return "|".join(values)

    @staticmethod
    def _choose_capability(row: pd.Series) -> float | None:
        candidates = []
        for key in ["import_limit_mw", "export_limit_mw"]:
            value = pd.to_numeric(row.get(key), errors="coerce")
            if pd.notna(value):
                candidates.append(abs(float(value)))
        if not candidates:
            return None
        return max(candidates)

    @staticmethod
    def _compute_stress_index(row: pd.Series) -> float | None:
        utilisation = pd.to_numeric(row.get("utilisation_pct"), errors="coerce")
        spread = pd.to_numeric(row.get("nsw_qld_spread"), errors="coerce")
        stress_parts: list[float] = []

        if pd.notna(utilisation):
            util_component = min(max(abs(float(utilisation)) / 100.0, 0.0), 1.0)
            stress_parts.append(0.65 * util_component)
            if util_component >= 0.98:
                stress_parts.append(0.10)

        if pd.notna(spread):
            spread_component = min(abs(float(spread)) / 300.0, 1.0)
            stress_parts.append(0.25 * spread_component)

        if not stress_parts:
            return None
        return round(min(sum(stress_parts), 1.0), 6)

    @staticmethod
    def _rolling_episode_counts(series: pd.Series, window: int) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
        starts = (values > 0) & (values.shift(1, fill_value=0.0) <= 0)
        return starts.rolling(window=window, min_periods=1).sum().astype(float)

    @staticmethod
    def _current_run_length(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
        run_lengths: list[int] = []
        current = 0
        for value in values:
            if value > 0:
                current += 1
            else:
                current = 0
            run_lengths.append(current)
        return pd.Series(run_lengths, index=series.index, dtype=float)

    @classmethod
    def _recompute_derived_fields(cls, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame

        out = frame.copy()
        for price_col in ["nsw_rrp", "qld_rrp", "mw_flow", "available_capability_mw"]:
            if price_col in out.columns:
                out[price_col] = pd.to_numeric(out[price_col], errors="coerce")

        out["nsw_qld_spread"] = pd.to_numeric(out.get("nsw_rrp"), errors="coerce") - pd.to_numeric(
            out.get("qld_rrp"), errors="coerce"
        )
        out["utilisation_pct"] = (
            pd.to_numeric(out.get("mw_flow"), errors="coerce").abs()
            / pd.to_numeric(out.get("available_capability_mw"), errors="coerce")
            * 100.0
        )
        out.loc[
            pd.to_numeric(out.get("available_capability_mw"), errors="coerce") <= 0,
            "utilisation_pct",
        ] = pd.NA

        out["interconnector_stress_index"] = out.apply(cls._compute_stress_index, axis=1)
        out["demand_short_term_change"] = pd.NA
        out["demand_ramp"] = pd.NA
        out["constraint_time_at_limit_pct"] = pd.NA
        out["constraint_duration_intervals"] = pd.NA
        out["constraint_recurrence_count"] = pd.NA

        out["interval_timestamp_utc"] = pd.to_datetime(out["interval_timestamp_utc"], utc=True, errors="coerce")
        out = out.sort_values(["corridor", "interval_timestamp_utc", "record_version"], kind="stable")

        for _, corridor_frame in out.groupby("corridor", dropna=False, sort=False):
            idx = corridor_frame.index

            demand = pd.to_numeric(corridor_frame.get("regional_operational_demand"), errors="coerce")
            if demand.notna().any():
                out.loc[idx, "demand_short_term_change"] = demand.diff().values
                out.loc[idx, "demand_ramp"] = (demand - demand.shift(12)).values
                seasonal_norm = demand.shift(2016)
                out.loc[idx, "demand_anomaly"] = (demand - seasonal_norm).values

            binding = pd.to_numeric(corridor_frame.get("constraint_binding_flag"), errors="coerce").fillna(0.0)
            if binding.notna().any():
                out.loc[idx, "constraint_time_at_limit_pct"] = (
                    binding.rolling(window=96, min_periods=1).mean().values * 100.0
                )
                out.loc[idx, "constraint_duration_intervals"] = cls._current_run_length(binding).values
                out.loc[idx, "constraint_recurrence_count"] = cls._rolling_episode_counts(binding, window=2016).values

        out["interval_timestamp_utc"] = out["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return out[[name for name, _, _ in MARKET_STATE_SCHEMA]].copy()

    @classmethod
    def parse_dispatchprice_archive_bytes(
        cls,
        content: bytes,
        progress_meta: dict[str, object] | None = None,
    ) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        meta = progress_meta or {}
        next_log_at = cls._PROGRESS_LOG_INTERVAL_ROWS
        local_rows = 0
        last_output_at = float(meta.get("last_output_at", time.time()))

        def _parse_zip(zip_bytes: bytes) -> None:
            nonlocal next_log_at, local_rows, last_output_at
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for member_name in archive.namelist():
                    with archive.open(member_name) as handle:
                        payload = handle.read()
                    lower_name = member_name.lower()
                    if lower_name.endswith(".zip") and payload.startswith(b"PK"):
                        _parse_zip(payload)
                        continue
                    if not lower_name.endswith(".csv"):
                        continue
                    for raw_line in payload.decode("utf-8", errors="ignore").splitlines():
                        line = raw_line.strip()
                        if not line.startswith("D,DISPATCH,PRICE,"):
                            continue
                        row = next(csv.reader([line]))
                        if len(row) < 9:
                            continue
                        settlement_date = row[4].strip().strip('"')
                        region_id = row[6].strip().strip('"').upper()
                        rrp = row[8].strip().strip('"')
                        if not settlement_date or not region_id:
                            continue
                        records.append(
                            {
                                "SETTLEMENTDATE": settlement_date,
                                "REGIONID": region_id,
                                "RRP": rrp,
                            }
                        )
                        local_rows += 1
                        if local_rows >= next_log_at:
                            last_output_at = cls._log_progress(
                                function_name=str(meta.get("function_name", "parse_dispatchprice_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                            )
                            next_log_at += cls._PROGRESS_LOG_INTERVAL_ROWS
                        if local_rows % 10_000 == 0:
                            cls._check_stall(
                                function_name=str(meta.get("function_name", "parse_dispatchprice_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                                last_output_at=last_output_at,
                            )

        _parse_zip(content)
        meta["last_output_at"] = last_output_at
        if not records:
            return pd.DataFrame(columns=["SETTLEMENTDATE", "REGIONID", "RRP"])
        return pd.DataFrame(records)

    @classmethod
    def parse_dispatchinterconnectorres_archive_bytes(
        cls,
        content: bytes,
        progress_meta: dict[str, object] | None = None,
    ) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        meta = progress_meta or {}
        next_log_at = cls._PROGRESS_LOG_INTERVAL_ROWS
        local_rows = 0
        last_output_at = float(meta.get("last_output_at", time.time()))

        def _parse_zip(zip_bytes: bytes) -> None:
            nonlocal next_log_at, local_rows, last_output_at
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for member_name in archive.namelist():
                    with archive.open(member_name) as handle:
                        payload = handle.read()
                    lower_name = member_name.lower()
                    if lower_name.endswith(".zip") and payload.startswith(b"PK"):
                        _parse_zip(payload)
                        continue
                    if not lower_name.endswith(".csv"):
                        continue

                    header_index: dict[str, int] | None = None
                    for raw_line in payload.decode("utf-8", errors="ignore").splitlines():
                        line = raw_line.strip()
                        if line.startswith("I,DISPATCH,INTERCONNECTORRES,"):
                            header_row = next(csv.reader([line]))
                            header_index = {
                                str(column).upper(): idx for idx, column in enumerate(header_row)
                            }
                            continue
                        if not line.startswith("D,DISPATCH,INTERCONNECTORRES,") or header_index is None:
                            continue

                        row = next(csv.reader([line]))
                        settlement_idx = header_index.get("SETTLEMENTDATE")
                        interconnector_idx = header_index.get("INTERCONNECTORID")
                        metered_flow_idx = header_index.get("METEREDMWFLOW")
                        mw_flow_idx = header_index.get("MWFLOW")
                        export_limit_idx = header_index.get("EXPORTLIMIT")
                        import_limit_idx = header_index.get("IMPORTLIMIT")

                        if settlement_idx is None or interconnector_idx is None:
                            continue
                        if max(settlement_idx, interconnector_idx) >= len(row):
                            continue

                        settlement_date = row[settlement_idx].strip().strip('"')
                        interconnector_id = row[interconnector_idx].strip().strip('"').upper()
                        metered_flow = (
                            row[metered_flow_idx].strip().strip('"')
                            if metered_flow_idx is not None and metered_flow_idx < len(row)
                            else ""
                        )
                        mw_flow = (
                            row[mw_flow_idx].strip().strip('"')
                            if mw_flow_idx is not None and mw_flow_idx < len(row)
                            else ""
                        )
                        export_limit = (
                            row[export_limit_idx].strip().strip('"')
                            if export_limit_idx is not None and export_limit_idx < len(row)
                            else ""
                        )
                        import_limit = (
                            row[import_limit_idx].strip().strip('"')
                            if import_limit_idx is not None and import_limit_idx < len(row)
                            else ""
                        )

                        if not settlement_date or not interconnector_id:
                            continue

                        records.append(
                            {
                                "SETTLEMENTDATE": settlement_date,
                                "INTERCONNECTORID": interconnector_id,
                                "METEREDMWFLOW": metered_flow,
                                "MWFLOW": mw_flow,
                                "EXPORTLIMIT": export_limit,
                                "IMPORTLIMIT": import_limit,
                            }
                        )
                        local_rows += 1
                        if local_rows >= next_log_at:
                            last_output_at = cls._log_progress(
                                function_name=str(meta.get("function_name", "parse_dispatchinterconnectorres_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                            )
                            next_log_at += cls._PROGRESS_LOG_INTERVAL_ROWS
                        if local_rows % 10_000 == 0:
                            cls._check_stall(
                                function_name=str(meta.get("function_name", "parse_dispatchinterconnectorres_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                                last_output_at=last_output_at,
                            )

        _parse_zip(content)
        meta["last_output_at"] = last_output_at
        if not records:
            return pd.DataFrame(
                columns=[
                    "SETTLEMENTDATE",
                    "INTERCONNECTORID",
                    "METEREDMWFLOW",
                    "MWFLOW",
                    "EXPORTLIMIT",
                    "IMPORTLIMIT",
                ]
            )
        return pd.DataFrame(records)

    @classmethod
    def parse_dispatchregionsum_archive_bytes(
        cls,
        content: bytes,
        progress_meta: dict[str, object] | None = None,
    ) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        meta = progress_meta or {}
        next_log_at = cls._PROGRESS_LOG_INTERVAL_ROWS
        local_rows = 0
        last_output_at = float(meta.get("last_output_at", time.time()))

        def _parse_zip(zip_bytes: bytes) -> None:
            nonlocal next_log_at, local_rows, last_output_at
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for member_name in archive.namelist():
                    with archive.open(member_name) as handle:
                        payload = handle.read()
                    lower_name = member_name.lower()
                    if lower_name.endswith(".zip") and payload.startswith(b"PK"):
                        _parse_zip(payload)
                        continue
                    if not lower_name.endswith(".csv"):
                        continue

                    header_index: dict[str, int] | None = None
                    for raw_line in payload.decode("utf-8", errors="ignore").splitlines():
                        line = raw_line.strip()
                        if line.startswith("I,DISPATCH,REGIONSUM,"):
                            header_row = next(csv.reader([line]))
                            header_index = {str(column).upper(): idx for idx, column in enumerate(header_row)}
                            continue
                        if not line.startswith("D,DISPATCH,REGIONSUM,") or header_index is None:
                            continue

                        row = next(csv.reader([line]))
                        settlement_idx = header_index.get("SETTLEMENTDATE")
                        region_idx = header_index.get("REGIONID")
                        total_demand_idx = header_index.get("TOTALDEMAND")
                        forecast_idx = (
                            header_index.get("DEMANDFORECAST")
                            or header_index.get("TOTALDEMANDFORECAST")
                            or header_index.get("PREDISPATCHDEMAND")
                        )

                        if settlement_idx is None or region_idx is None or total_demand_idx is None:
                            continue
                        if max(settlement_idx, region_idx, total_demand_idx) >= len(row):
                            continue

                        record: dict[str, object] = {
                            "SETTLEMENTDATE": row[settlement_idx].strip().strip('"'),
                            "REGIONID": row[region_idx].strip().strip('"').upper(),
                            "TOTALDEMAND": row[total_demand_idx].strip().strip('"'),
                        }
                        if forecast_idx is not None and forecast_idx < len(row):
                            record["DEMANDFORECAST"] = row[forecast_idx].strip().strip('"')
                        records.append(record)
                        local_rows += 1
                        if local_rows >= next_log_at:
                            last_output_at = cls._log_progress(
                                function_name=str(meta.get("function_name", "parse_dispatchregionsum_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                            )
                            next_log_at += cls._PROGRESS_LOG_INTERVAL_ROWS
                        if local_rows % 10_000 == 0:
                            cls._check_stall(
                                function_name=str(meta.get("function_name", "parse_dispatchregionsum_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                                last_output_at=last_output_at,
                            )

        _parse_zip(content)
        meta["last_output_at"] = last_output_at
        if not records:
            return pd.DataFrame(columns=["SETTLEMENTDATE", "REGIONID", "TOTALDEMAND", "DEMANDFORECAST"])
        return pd.DataFrame(records)

    @classmethod
    def parse_dispatchconstraint_archive_bytes(
        cls,
        content: bytes,
        progress_meta: dict[str, object] | None = None,
    ) -> pd.DataFrame:
        aggregates: dict[str, dict[str, object]] = {}
        meta = progress_meta or {}
        next_log_at = cls._PROGRESS_LOG_INTERVAL_ROWS
        local_rows = 0
        last_output_at = float(meta.get("last_output_at", time.time()))
        ref = Interconnector.get(cls._PRIMARY_CORRIDOR)
        primary_region = ref.direction_from_region if ref is not None else "NSW1"

        def _parse_zip(zip_bytes: bytes) -> None:
            nonlocal next_log_at, local_rows, last_output_at
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for member_name in archive.namelist():
                    with archive.open(member_name) as handle:
                        payload = handle.read()
                    lower_name = member_name.lower()
                    if lower_name.endswith(".zip") and payload.startswith(b"PK"):
                        _parse_zip(payload)
                        continue
                    if not lower_name.endswith(".csv"):
                        continue

                    header_index: dict[str, int] | None = None
                    for raw_line in payload.decode("utf-8", errors="ignore").splitlines():
                        line = raw_line.strip()
                        if line.startswith("I,DISPATCH,CONSTRAINT,"):
                            header_row = next(csv.reader([line]))
                            header_index = {str(column).upper(): idx for idx, column in enumerate(header_row)}
                            continue
                        if not line.startswith("D,DISPATCH,CONSTRAINT,") or header_index is None:
                            continue

                        row = next(csv.reader([line]))
                        settlement_idx = header_index.get("SETTLEMENTDATE")
                        constraint_idx = header_index.get("CONSTRAINTID")
                        marginal_idx = header_index.get("MARGINALVALUE")
                        violation_idx = header_index.get("VIOLATIONDEGREE")
                        interconnector_idx = header_index.get("INTERCONNECTORID")
                        region_idx = header_index.get("REGIONID")

                        if settlement_idx is None or constraint_idx is None:
                            continue
                        if max(settlement_idx, constraint_idx) >= len(row):
                            continue
                        settlement_date = row[settlement_idx].strip().strip('"')
                        if not settlement_date:
                            continue

                        interconnector_id = ""
                        region_id = ""
                        if interconnector_idx is not None and interconnector_idx < len(row):
                            interconnector_id = row[interconnector_idx].strip().strip('"').upper()
                        if region_idx is not None and region_idx < len(row):
                            region_id = row[region_idx].strip().strip('"').upper()

                        row_relevant = True
                        if interconnector_idx is not None or region_idx is not None:
                            row_relevant = (
                                interconnector_id == cls._PRIMARY_CORRIDOR
                                or region_id == primary_region
                            )
                        if not row_relevant:
                            continue

                        marginal_value = pd.NA
                        if marginal_idx is not None and marginal_idx < len(row):
                            marginal_value = pd.to_numeric(row[marginal_idx].strip().strip('"'), errors="coerce")

                        violation_value = pd.NA
                        if violation_idx is not None and violation_idx < len(row):
                            violation_value = pd.to_numeric(row[violation_idx].strip().strip('"'), errors="coerce")

                        bucket = aggregates.setdefault(
                            settlement_date,
                            {
                                "max_abs_marginal": pd.NA,
                                "has_binding": False,
                                "violation_observed": False,
                            },
                        )

                        if pd.notna(marginal_value):
                            current_max = pd.to_numeric(bucket["max_abs_marginal"], errors="coerce")
                            candidate = abs(float(marginal_value))
                            if pd.isna(current_max) or candidate > float(current_max):
                                bucket["max_abs_marginal"] = candidate

                        if pd.notna(violation_value):
                            bucket["violation_observed"] = True
                            if abs(float(violation_value)) > 0:
                                bucket["has_binding"] = True

                        local_rows += 1
                        if local_rows >= next_log_at:
                            last_output_at = cls._log_progress(
                                function_name=str(meta.get("function_name", "parse_dispatchconstraint_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                            )
                            next_log_at += cls._PROGRESS_LOG_INTERVAL_ROWS
                        if local_rows % 10_000 == 0:
                            cls._check_stall(
                                function_name=str(meta.get("function_name", "parse_dispatchconstraint_archive_bytes")),
                                files_processed=int(meta.get("files_processed", 0)),
                                rows_processed=int(meta.get("rows_processed_base", 0)) + local_rows,
                                current_file=str(meta.get("current_file", "archive_bytes")),
                                row_in_current_file=local_rows,
                                last_output_at=last_output_at,
                            )

        _parse_zip(content)
        meta["last_output_at"] = last_output_at
        if not aggregates:
            return pd.DataFrame(
                columns=[
                    "SETTLEMENTDATE",
                    "CONSTRAINTID",
                    "MARGINALVALUE",
                    "VIOLATIONDEGREE",
                    "INTERCONNECTORID",
                    "REGIONID",
                ]
            )

        records: list[dict[str, object]] = []
        for settlement_date, bucket in sorted(aggregates.items()):
            violation = pd.NA
            if bool(bucket.get("violation_observed", False)):
                violation = 1.0 if bool(bucket.get("has_binding", False)) else 0.0
            records.append(
                {
                    "SETTLEMENTDATE": settlement_date,
                    "CONSTRAINTID": f"{cls._PRIMARY_CORRIDOR}_AGG",
                    "MARGINALVALUE": bucket.get("max_abs_marginal", pd.NA),
                    "VIOLATIONDEGREE": violation,
                    "INTERCONNECTORID": cls._PRIMARY_CORRIDOR,
                    "REGIONID": primary_region,
                }
            )

        return pd.DataFrame(records)

    @staticmethod
    def normalize_dispatchprice_frame(
        frame: pd.DataFrame,
        source_file: str,
        publish_timestamp_utc: str,
        record_version: int = 1,
    ) -> pd.DataFrame:
        if frame.empty:
            return MarketStateDatabase._empty_market_state_frame()

        cols_upper = {col.upper(): col for col in frame.columns.astype(str)}
        if "SETTLEMENTDATE" not in cols_upper or "REGIONID" not in cols_upper or "RRP" not in cols_upper:
            return MarketStateDatabase._empty_market_state_frame()

        settlement_col = cols_upper["SETTLEMENTDATE"]
        region_col = cols_upper["REGIONID"]
        rrp_col = cols_upper["RRP"]

        base = frame[[settlement_col, region_col, rrp_col]].copy()
        base.columns = ["interval_timestamp_utc", "regionid", "rrp"]
        base["interval_timestamp_utc"] = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce")
        base["rrp"] = pd.to_numeric(base["rrp"], errors="coerce")
        base["regionid"] = base["regionid"].astype(str).str.upper().str.strip()
        base = base[base["interval_timestamp_utc"].notna()].copy()

        if base.empty:
            return MarketStateDatabase._empty_market_state_frame()

        # Pivot by region into one row per interval
        pivot = (
            base.pivot_table(index="interval_timestamp_utc", columns="regionid", values="rrp", aggfunc="mean")
            .reset_index()
        )

        out = pd.DataFrame(columns=[name for name, _, _ in MARKET_STATE_SCHEMA])
        out["interval_timestamp_utc"] = pivot["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["asof_publish_timestamp_utc"] = publish_timestamp_utc
        out["decision_cutoff_utc"] = pd.NA
        out["record_version"] = int(record_version)
        out["record_source"] = source_file
        out["corridor"] = MarketStateDatabase._PRIMARY_CORRIDOR
        out["direction"] = "NSW1->QLD1"
        out["ruleset_id"] = pd.NA

        for region, col_name in PRICE_REGION_MAP.items():
            out[col_name] = pivot.get(region)

        out["nsw_qld_spread"] = pd.to_numeric(out["nsw_rrp"], errors="coerce") - pd.to_numeric(out["qld_rrp"], errors="coerce")

        # Keep non-price fields null until later ingestors are added
        for column, _, _ in MARKET_STATE_SCHEMA:
            if column not in out.columns:
                out[column] = pd.NA

        return MarketStateDatabase._recompute_derived_fields(
            out[[name for name, _, _ in MARKET_STATE_SCHEMA]].copy()
        )

    @staticmethod
    def normalize_dispatchinterconnectorres_frame(
        frame: pd.DataFrame,
        source_file: str,
        publish_timestamp_utc: str,
        record_version: int = 1,
    ) -> pd.DataFrame:
        if frame.empty:
            return MarketStateDatabase._empty_market_state_frame()

        cols_upper = {col.upper(): col for col in frame.columns.astype(str)}
        required = {"SETTLEMENTDATE", "INTERCONNECTORID"}
        if not required.issubset(cols_upper):
            return MarketStateDatabase._empty_market_state_frame()

        settlement_col = cols_upper["SETTLEMENTDATE"]
        interconnector_col = cols_upper["INTERCONNECTORID"]
        metered_flow_col = cols_upper.get("METEREDMWFLOW")
        mw_flow_col = cols_upper.get("MWFLOW")
        export_limit_col = cols_upper.get("EXPORTLIMIT")
        import_limit_col = cols_upper.get("IMPORTLIMIT")

        use_flow_col = metered_flow_col or mw_flow_col
        if use_flow_col is None:
            return MarketStateDatabase._empty_market_state_frame()

        selected_columns = [settlement_col, interconnector_col, use_flow_col]
        if export_limit_col is not None:
            selected_columns.append(export_limit_col)
        if import_limit_col is not None:
            selected_columns.append(import_limit_col)

        base = frame[selected_columns].copy()
        rename_map = {
            settlement_col: "interval_timestamp_utc",
            interconnector_col: "interconnector_id",
            use_flow_col: "mw_flow",
        }
        if export_limit_col is not None:
            rename_map[export_limit_col] = "export_limit_mw"
        if import_limit_col is not None:
            rename_map[import_limit_col] = "import_limit_mw"
        base = base.rename(columns=rename_map)

        base["interval_timestamp_utc"] = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce")
        base["interconnector_id"] = base["interconnector_id"].astype(str).str.upper().str.strip()
        base["mw_flow"] = pd.to_numeric(base["mw_flow"], errors="coerce")
        if "export_limit_mw" in base.columns:
            base["export_limit_mw"] = pd.to_numeric(base["export_limit_mw"], errors="coerce")
        if "import_limit_mw" in base.columns:
            base["import_limit_mw"] = pd.to_numeric(base["import_limit_mw"], errors="coerce")

        base = base[
            base["interval_timestamp_utc"].notna()
            & base["interconnector_id"].eq(MarketStateDatabase._PRIMARY_CORRIDOR)
        ].copy()
        if base.empty:
            return MarketStateDatabase._empty_market_state_frame()

        ref = Interconnector.get(MarketStateDatabase._PRIMARY_CORRIDOR)
        direction = (
            f"{ref.direction_from_region}->{ref.direction_to_region}"
            if ref is not None
            else "NSW1->QLD1"
        )

        out = MarketStateDatabase._empty_market_state_frame()
        out["interval_timestamp_utc"] = base["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["asof_publish_timestamp_utc"] = publish_timestamp_utc
        out["decision_cutoff_utc"] = pd.NA
        out["record_version"] = int(record_version)
        out["record_source"] = source_file
        out["corridor"] = MarketStateDatabase._PRIMARY_CORRIDOR
        out["direction"] = direction
        out["mw_flow"] = base["mw_flow"].values
        out["available_capability_mw"] = base.apply(MarketStateDatabase._choose_capability, axis=1).values

        return MarketStateDatabase._recompute_derived_fields(out)

    @staticmethod
    def normalize_dispatchregionsum_frame(
        frame: pd.DataFrame,
        source_file: str,
        publish_timestamp_utc: str,
        record_version: int = 1,
    ) -> pd.DataFrame:
        if frame.empty:
            return MarketStateDatabase._empty_market_state_frame()

        cols_upper = {col.upper(): col for col in frame.columns.astype(str)}
        required = {"SETTLEMENTDATE", "REGIONID", "TOTALDEMAND"}
        if not required.issubset(cols_upper):
            return MarketStateDatabase._empty_market_state_frame()

        settlement_col = cols_upper["SETTLEMENTDATE"]
        region_col = cols_upper["REGIONID"]
        demand_col = cols_upper["TOTALDEMAND"]
        forecast_col = cols_upper.get("DEMANDFORECAST")

        selected_columns = [settlement_col, region_col, demand_col]
        if forecast_col is not None:
            selected_columns.append(forecast_col)

        base = frame[selected_columns].copy()
        rename_map = {
            settlement_col: "interval_timestamp_utc",
            region_col: "region_id",
            demand_col: "regional_operational_demand",
        }
        if forecast_col is not None:
            rename_map[forecast_col] = "forecast_demand"
        base = base.rename(columns=rename_map)

        base["interval_timestamp_utc"] = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce")
        base["region_id"] = base["region_id"].astype(str).str.upper().str.strip()
        base["regional_operational_demand"] = pd.to_numeric(base["regional_operational_demand"], errors="coerce")
        if "forecast_demand" in base.columns:
            base["forecast_demand"] = pd.to_numeric(base["forecast_demand"], errors="coerce")

        ref = Interconnector.get(MarketStateDatabase._PRIMARY_CORRIDOR)
        primary_region = ref.direction_from_region if ref is not None else "NSW1"
        direction = f"{primary_region}->{ref.direction_to_region if ref is not None else 'QLD1'}"
        base = base[
            base["interval_timestamp_utc"].notna() & base["region_id"].eq(primary_region)
        ].copy()
        if base.empty:
            return MarketStateDatabase._empty_market_state_frame()

        out = MarketStateDatabase._empty_market_state_frame()
        out["interval_timestamp_utc"] = base["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["asof_publish_timestamp_utc"] = publish_timestamp_utc
        out["decision_cutoff_utc"] = pd.NA
        out["record_version"] = int(record_version)
        out["record_source"] = source_file
        out["corridor"] = MarketStateDatabase._PRIMARY_CORRIDOR
        out["direction"] = direction
        out["regional_operational_demand"] = base["regional_operational_demand"].values
        if "forecast_demand" in base.columns:
            out["forecast_demand"] = base["forecast_demand"].values

        return MarketStateDatabase._recompute_derived_fields(out)

    @staticmethod
    def normalize_dispatchconstraint_frame(
        frame: pd.DataFrame,
        source_file: str,
        publish_timestamp_utc: str,
        record_version: int = 1,
    ) -> pd.DataFrame:
        if frame.empty:
            return MarketStateDatabase._empty_market_state_frame()

        cols_upper = {col.upper(): col for col in frame.columns.astype(str)}
        if "SETTLEMENTDATE" not in cols_upper or "CONSTRAINTID" not in cols_upper:
            return MarketStateDatabase._empty_market_state_frame()

        settlement_col = cols_upper["SETTLEMENTDATE"]
        constraint_col = cols_upper["CONSTRAINTID"]
        marginal_col = cols_upper.get("MARGINALVALUE")
        violation_col = cols_upper.get("VIOLATIONDEGREE")
        interconnector_col = cols_upper.get("INTERCONNECTORID")
        region_col = cols_upper.get("REGIONID")

        selected_columns = [settlement_col, constraint_col]
        if marginal_col is not None:
            selected_columns.append(marginal_col)
        if violation_col is not None:
            selected_columns.append(violation_col)
        if interconnector_col is not None:
            selected_columns.append(interconnector_col)
        if region_col is not None:
            selected_columns.append(region_col)

        base = frame[selected_columns].copy()
        rename_map = {
            settlement_col: "interval_timestamp_utc",
            constraint_col: "constraint_id",
        }
        if marginal_col is not None:
            rename_map[marginal_col] = "constraint_marginal_value"
        if violation_col is not None:
            rename_map[violation_col] = "violation_degree"
        if interconnector_col is not None:
            rename_map[interconnector_col] = "interconnector_id"
        if region_col is not None:
            rename_map[region_col] = "region_id"
        base = base.rename(columns=rename_map)

        base["interval_timestamp_utc"] = pd.to_datetime(base["interval_timestamp_utc"], utc=True, errors="coerce")
        if "constraint_marginal_value" in base.columns:
            base["constraint_marginal_value"] = pd.to_numeric(base["constraint_marginal_value"], errors="coerce")
        if "violation_degree" in base.columns:
            base["violation_degree"] = pd.to_numeric(base["violation_degree"], errors="coerce")
        if "interconnector_id" in base.columns:
            base["interconnector_id"] = base["interconnector_id"].astype(str).str.upper().str.strip()
        if "region_id" in base.columns:
            base["region_id"] = base["region_id"].astype(str).str.upper().str.strip()

        base = base[base["interval_timestamp_utc"].notna()].copy()
        if base.empty:
            return MarketStateDatabase._empty_market_state_frame()

        ref = Interconnector.get(MarketStateDatabase._PRIMARY_CORRIDOR)
        primary_region = ref.direction_from_region if ref is not None else "NSW1"
        direction = f"{primary_region}->{ref.direction_to_region if ref is not None else 'QLD1'}"

        if "interconnector_id" in base.columns or "region_id" in base.columns:
            corridor_mask = pd.Series(False, index=base.index)
            if "interconnector_id" in base.columns:
                corridor_mask |= base["interconnector_id"].eq(MarketStateDatabase._PRIMARY_CORRIDOR)
            if "region_id" in base.columns:
                corridor_mask |= base["region_id"].eq(primary_region)
            base = base[corridor_mask].copy() if corridor_mask.any() else base.copy()

        if base.empty:
            return MarketStateDatabase._empty_market_state_frame()

        out = MarketStateDatabase._empty_market_state_frame()
        out["interval_timestamp_utc"] = base["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["asof_publish_timestamp_utc"] = publish_timestamp_utc
        out["decision_cutoff_utc"] = pd.NA
        out["record_version"] = int(record_version)
        out["record_source"] = source_file
        out["corridor"] = MarketStateDatabase._PRIMARY_CORRIDOR
        out["direction"] = direction
        out["constraint_binding_flag"] = True
        if "violation_degree" in base.columns:
            out["constraint_binding_flag"] = base["violation_degree"].fillna(0.0).abs() > 0
        if "constraint_marginal_value" in base.columns:
            out["constraint_marginal_value"] = base["constraint_marginal_value"].abs().values

        return MarketStateDatabase._recompute_derived_fields(out)

    def upsert(self, normalized_rows: pd.DataFrame) -> None:
        if normalized_rows.empty:
            return
        combined = pd.concat([self._state, normalized_rows], ignore_index=True)
        combined = combined.sort_values(["interval_timestamp_utc", "corridor", "record_version"])

        merged_rows: list[dict[str, object]] = []
        for _, group in combined.groupby(["interval_timestamp_utc", "corridor"], dropna=False, sort=False):
            merged_row: dict[str, object] = {}
            for column, _, _ in MARKET_STATE_SCHEMA:
                if column == "record_source":
                    merged_row[column] = self._combine_record_sources(group[column])
                    continue
                if column == "record_version":
                    merged_row[column] = int(pd.to_numeric(group[column], errors="coerce").fillna(0).max())
                    continue
                if column == "asof_publish_timestamp_utc":
                    timestamps = pd.to_datetime(group[column], utc=True, errors="coerce").dropna()
                    merged_row[column] = (
                        timestamps.max().strftime("%Y-%m-%dT%H:%M:%SZ") if not timestamps.empty else pd.NA
                    )
                    continue

                non_null = group[column][group[column].notna()]
                merged_row[column] = non_null.iloc[-1] if not non_null.empty else pd.NA
            merged_rows.append(merged_row)

        merged_frame = pd.DataFrame(merged_rows)
        self._state = self._recompute_derived_fields(merged_frame).reset_index(drop=True)

    def ingest_historical_dispatchprice_archive(
        self,
        raw_archive_dir: Path,
        publish_timestamp_utc: str,
        start_month: str,
        end_month: str | None = None,
        reports_dir: Path | None = None,
        diagnostic_one_file: bool = False,
    ) -> DispatchPriceIngestionResult:
        raw_archive_dir.mkdir(parents=True, exist_ok=True)
        resolved_reports_dir = reports_dir or (raw_archive_dir.parent.parent.parent / "reports")
        resolved_reports_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = self._dispatchprice_manifest_path(resolved_reports_dir)
        failed_path = self._dispatchprice_failed_files_path(resolved_reports_dir)
        cache_report_path = self._dispatchprice_cache_report_path(resolved_reports_dir)

        manifest = self._load_dispatchprice_manifest(manifest_path)
        parquet_supported = self._supports_parquet()
        cache_format = "parquet" if parquet_supported else "csv.gz"

        last_available_month = (pd.Timestamp.now("UTC") - pd.DateOffset(months=1)).strftime("%Y-%m")
        resolved_end_month = end_month or last_available_month

        rows_read = 0
        rows_norm = 0
        files_processed = 0
        download_attempts = 0
        download_successes = 0
        skipped_hashes = 0
        failed_files = 0
        function_name = "ingest_historical_dispatchprice_archive"
        started_at = time.perf_counter()

        candidate_archives: list[Path] = []
        for year, month in self._month_range(start_month, resolved_end_month):
            archive_name = f"PUBLIC_DVD_DISPATCHPRICE_{year}{month:02d}010000.zip"
            archive_path = raw_archive_dir / archive_name
            if not archive_path.exists():
                download_attempts += 1
                url = _DISPATCHPRICE_ARCHIVE_URL_TEMPLATE.format(year=year, month=month)
                try:
                    archive_path.write_bytes(self._download_archive(url))
                    download_successes += 1
                except (HTTPError, URLError, TimeoutError, ValueError, OSError):
                    continue
            if archive_path.exists():
                candidate_archives.append(archive_path)

        candidate_archives = sorted(candidate_archives)
        if diagnostic_one_file and candidate_archives:
            candidate_archives = candidate_archives[:1]
        files_total = len(candidate_archives)

        last_output_at = self._log_progress(
            function_name=function_name,
            files_processed=files_processed,
            rows_processed=rows_read,
            current_file="init",
            row_in_current_file=0,
        )

        for archive_path in candidate_archives:
            archive_stat = archive_path.stat()
            archive_hash = self._file_sha256(archive_path)
            modified_utc = self._to_utc_iso(archive_stat.st_mtime)

            existing = manifest[manifest["sha256_hash"].astype(str) == archive_hash]
            if not existing.empty:
                existing_row = existing.iloc[-1]
                output_path = Path(str(existing_row.get("output_partition_path", "")))
                existing_status_ok = str(existing_row.get("status", "")).upper() == "SUCCESS"
                existing_schema = pd.to_numeric(existing_row.get("cache_schema_version"), errors="coerce")
                schema_ok = pd.notna(existing_schema) and int(existing_schema) == _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION
                output_ok = self._cache_output_has_columns(
                    output_path,
                    _DISPATCHREGIONSUM_REQUIRED_NORMALIZED_COLUMNS,
                )
                if existing_status_ok and schema_ok and output_ok:
                    skipped_hashes += 1
                    self._log_file_progress(
                        function_name=function_name,
                        files_completed=files_processed + skipped_hashes + failed_files,
                        files_total=files_total,
                        rows_processed=rows_read,
                        elapsed_seconds=time.perf_counter() - started_at,
                    )
                    continue

            in_progress_row = {
                "source_file_path": str(archive_path),
                "file_size_bytes": int(archive_stat.st_size),
                "modified_timestamp_utc": modified_utc,
                "sha256_hash": archive_hash,
                "rows_ingested": pd.NA,
                "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "output_partition_path": pd.NA,
                "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                "status": "IN_PROGRESS",
                "error": pd.NA,
            }
            manifest = self._upsert_manifest_row(manifest, in_progress_row)
            self._save_dispatchprice_manifest(manifest_path, manifest)

            try:
                progress_meta = {
                    "function_name": function_name,
                    "files_processed": files_processed,
                    "rows_processed_base": rows_read,
                    "current_file": str(archive_path),
                    "last_output_at": last_output_at,
                }
                raw = self.parse_dispatchprice_archive_bytes(archive_path.read_bytes(), progress_meta=progress_meta)
                last_output_at = float(progress_meta.get("last_output_at", last_output_at))

                norm = self.normalize_dispatchprice_frame(
                    raw,
                    source_file=str(archive_path),
                    publish_timestamp_utc=publish_timestamp_utc,
                    record_version=1,
                )
                period_token = archive_path.stem.split("_")[-1][:6]
                partition_year = period_token[:4] if len(period_token) >= 4 else "unknown"
                partition_month = period_token[4:6] if len(period_token) >= 6 else "00"
                partition_dir = self._dispatchprice_cache_root(raw_archive_dir) / f"year={partition_year}" / f"month={partition_month}"
                partition_dir.mkdir(parents=True, exist_ok=True)
                output_name = f"dispatchprice_{archive_hash}.{cache_format}"
                output_path = partition_dir / output_name

                if parquet_supported:
                    norm.to_parquet(output_path, index=False)
                else:
                    norm.to_csv(output_path, index=False, compression="gzip")

                files_processed += 1
                rows_read += len(raw)
                rows_norm += len(norm)
                self.upsert(norm)

                success_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": int(len(norm)),
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": str(output_path),
                    "status": "SUCCESS",
                    "error": pd.NA,
                }
                manifest = self._upsert_manifest_row(manifest, success_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)

                self._log_progress(
                    function_name=function_name,
                    files_processed=files_processed,
                    rows_processed=rows_read,
                    current_file=str(archive_path),
                    row_in_current_file=len(raw),
                )
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
            except IngestionStalledError as exc:
                print(json.dumps(exc.report), flush=True)
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "status": "FAILED",
                    "error": str(exc.report),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                break
            except Exception as exc:
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "status": "FAILED",
                    "error": str(exc),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
                continue

        self._save_dispatchprice_manifest(manifest_path, manifest)

        failed_manifest = manifest[manifest["status"].astype(str).str.upper() == "FAILED"].copy()
        failed_manifest.to_csv(failed_path, index=False)

        cache_report_lines = [
            "# Phase5C DISPATCHPRICE Cache Report",
            "",
            f"- Cache format: `{cache_format}`",
            f"- Parquet supported: `{'Yes' if parquet_supported else 'No'}`",
            f"- Files total considered: `{files_total}`",
            f"- Files processed this run: `{files_processed}`",
            f"- Files skipped by hash: `{skipped_hashes}`",
            f"- Failed files: `{len(failed_manifest)}`",
            f"- Rows read this run: `{rows_read}`",
            f"- Rows normalized this run: `{rows_norm}`",
            f"- Manifest: `{manifest_path}`",
            f"- Failed file report: `{failed_path}`",
        ]
        if not parquet_supported:
            cache_report_lines.append("- Limitation: `pyarrow`/`fastparquet` unavailable, using compressed CSV cache.")
        cache_report_path.write_text("\n".join(cache_report_lines) + "\n", encoding="utf-8")

        rows_valid = int(self._state["nsw_qld_spread"].notna().sum()) if not self._state.empty else 0
        return DispatchPriceIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
            download_attempts=download_attempts,
            download_successes=download_successes,
        )

    def ingest_dispatchinterconnectorres_files(
        self,
        file_paths: list[Path],
        publish_timestamp_utc: str,
    ) -> InterconnectorFlowIngestionResult:
        rows_read = 0
        rows_norm = 0
        files_processed = 0

        for file_path in file_paths:
            raw = pd.DataFrame()
            try:
                raw = pd.read_csv(file_path)
            except Exception:
                try:
                    raw = self.parse_dispatchinterconnectorres_archive_bytes(file_path.read_bytes())
                except Exception:
                    raw = pd.DataFrame()
            if raw.empty:
                continue

            files_processed += 1
            rows_read += len(raw)
            norm = self.normalize_dispatchinterconnectorres_frame(
                raw,
                source_file=str(file_path),
                publish_timestamp_utc=publish_timestamp_utc,
                record_version=1,
            )
            rows_norm += len(norm)
            self.upsert(norm)

        rows_valid = int(self._state["mw_flow"].notna().sum()) if not self._state.empty else 0
        return InterconnectorFlowIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_historical_dispatchinterconnectorres_archive(
        self,
        raw_archive_dir: Path,
        publish_timestamp_utc: str,
        start_month: str,
        end_month: str | None = None,
        reports_dir: Path | None = None,
        diagnostic_one_file: bool = False,
    ) -> InterconnectorFlowIngestionResult:
        raw_archive_dir.mkdir(parents=True, exist_ok=True)
        resolved_reports_dir = reports_dir or (raw_archive_dir.parent.parent.parent / "reports")
        resolved_reports_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = self._dispatchinterconnectorres_manifest_path(resolved_reports_dir)
        failed_path = self._dispatchinterconnectorres_failed_files_path(resolved_reports_dir)
        cache_report_path = self._dispatchinterconnectorres_cache_report_path(resolved_reports_dir)

        manifest = self._load_dispatchprice_manifest(manifest_path)
        parquet_supported = self._supports_parquet()
        cache_format = "parquet" if parquet_supported else "csv.gz"

        last_available_month = (pd.Timestamp.now("UTC") - pd.DateOffset(months=1)).strftime("%Y-%m")
        resolved_end_month = end_month or last_available_month

        rows_read = 0
        rows_norm = 0
        files_processed = 0
        download_attempts = 0
        download_successes = 0
        skipped_hashes = 0
        failed_files = 0
        function_name = "ingest_historical_dispatchinterconnectorres_archive"
        started_at = time.perf_counter()

        candidate_archives: list[Path] = []
        for year, month in self._month_range(start_month, resolved_end_month):
            archive_name = f"PUBLIC_DVD_DISPATCHINTERCONNECTORRES_{year}{month:02d}010000.zip"
            archive_path = raw_archive_dir / archive_name
            if not archive_path.exists():
                download_attempts += 1
                url = _DISPATCHINTERCONNECTORRES_ARCHIVE_URL_TEMPLATE.format(year=year, month=month)
                try:
                    archive_path.write_bytes(self._download_archive(url))
                    download_successes += 1
                except (HTTPError, URLError, TimeoutError, ValueError, OSError):
                    continue
            if archive_path.exists():
                candidate_archives.append(archive_path)

        candidate_archives = sorted(candidate_archives)
        if diagnostic_one_file and candidate_archives:
            candidate_archives = candidate_archives[:1]
        files_total = len(candidate_archives)

        last_output_at = self._log_progress(
            function_name=function_name,
            files_processed=files_processed,
            rows_processed=rows_read,
            current_file="init",
            row_in_current_file=0,
        )

        for archive_path in candidate_archives:
            archive_stat = archive_path.stat()
            archive_hash = self._file_sha256(archive_path)
            modified_utc = self._to_utc_iso(archive_stat.st_mtime)

            existing = manifest[manifest["sha256_hash"].astype(str) == archive_hash]
            if not existing.empty:
                existing_row = existing.iloc[-1]
                output_path = Path(str(existing_row.get("output_partition_path", "")))
                existing_status_ok = str(existing_row.get("status", "")).upper() == "SUCCESS"
                output_exists = output_path.exists()
                existing_schema = pd.to_numeric(existing_row.get("cache_schema_version"), errors="coerce")
                schema_ok = pd.notna(existing_schema) and int(existing_schema) == _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION
                required_columns_ok = self._cache_output_has_columns(
                    output_path,
                    _DISPATCHREGIONSUM_REQUIRED_NORMALIZED_COLUMNS,
                )
                if existing_status_ok and output_exists and schema_ok and required_columns_ok:
                    skipped_hashes += 1
                    self._log_file_progress(
                        function_name=function_name,
                        files_completed=files_processed + skipped_hashes + failed_files,
                        files_total=files_total,
                        rows_processed=rows_read,
                        elapsed_seconds=time.perf_counter() - started_at,
                    )
                    continue

            in_progress_row = {
                "source_file_path": str(archive_path),
                "file_size_bytes": int(archive_stat.st_size),
                "modified_timestamp_utc": modified_utc,
                "sha256_hash": archive_hash,
                "rows_ingested": pd.NA,
                "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "output_partition_path": pd.NA,
                "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                "status": "IN_PROGRESS",
                "error": pd.NA,
            }
            manifest = self._upsert_manifest_row(manifest, in_progress_row)
            self._save_dispatchprice_manifest(manifest_path, manifest)

            try:
                progress_meta = {
                    "function_name": function_name,
                    "files_processed": files_processed,
                    "rows_processed_base": rows_read,
                    "current_file": str(archive_path),
                    "last_output_at": last_output_at,
                }
                raw = self.parse_dispatchinterconnectorres_archive_bytes(archive_path.read_bytes(), progress_meta=progress_meta)
                last_output_at = float(progress_meta.get("last_output_at", last_output_at))

                norm = self.normalize_dispatchinterconnectorres_frame(
                    raw,
                    source_file=str(archive_path),
                    publish_timestamp_utc=publish_timestamp_utc,
                    record_version=1,
                )
                period_token = archive_path.stem.split("_")[-1][:6]
                partition_year = period_token[:4] if len(period_token) >= 4 else "unknown"
                partition_month = period_token[4:6] if len(period_token) >= 6 else "00"
                partition_dir = self._dispatchinterconnectorres_cache_root(raw_archive_dir) / f"year={partition_year}" / f"month={partition_month}"
                partition_dir.mkdir(parents=True, exist_ok=True)
                output_name = f"dispatchinterconnectorres_{archive_hash}.{cache_format}"
                output_path = partition_dir / output_name

                if parquet_supported:
                    norm.to_parquet(output_path, index=False)
                else:
                    norm.to_csv(output_path, index=False, compression="gzip")

                files_processed += 1
                rows_read += len(raw)
                rows_norm += len(norm)
                self.upsert(norm)

                success_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": int(len(norm)),
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": str(output_path),
                    "status": "SUCCESS",
                    "error": pd.NA,
                }
                manifest = self._upsert_manifest_row(manifest, success_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)

                self._log_progress(
                    function_name=function_name,
                    files_processed=files_processed,
                    rows_processed=rows_read,
                    current_file=str(archive_path),
                    row_in_current_file=len(raw),
                )
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
            except IngestionStalledError as exc:
                print(json.dumps(exc.report), flush=True)
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "status": "FAILED",
                    "error": str(exc.report),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                break
            except Exception as exc:
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "status": "FAILED",
                    "error": str(exc),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
                continue

        self._save_dispatchprice_manifest(manifest_path, manifest)

        failed_manifest = manifest[manifest["status"].astype(str).str.upper() == "FAILED"].copy()
        failed_manifest.to_csv(failed_path, index=False)

        cache_report_lines = [
            "# Phase5C DISPATCHINTERCONNECTORRES Cache Report",
            "",
            f"- Cache format: `{cache_format}`",
            f"- Parquet supported: `{'Yes' if parquet_supported else 'No'}`",
            f"- Files total considered: `{files_total}`",
            f"- Files processed this run: `{files_processed}`",
            f"- Files skipped by hash: `{skipped_hashes}`",
            f"- Failed files: `{len(failed_manifest)}`",
            f"- Rows read this run: `{rows_read}`",
            f"- Rows normalized this run: `{rows_norm}`",
            f"- Manifest: `{manifest_path}`",
            f"- Failed file report: `{failed_path}`",
        ]
        if not parquet_supported:
            cache_report_lines.append("- Limitation: `pyarrow`/`fastparquet` unavailable, using compressed CSV cache.")
        cache_report_path.write_text("\n".join(cache_report_lines) + "\n", encoding="utf-8")

        rows_valid = int(self._state["mw_flow"].notna().sum()) if not self._state.empty else 0
        return InterconnectorFlowIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
            download_attempts=download_attempts,
            download_successes=download_successes,
        )

    def ingest_dispatchprice_files(self, file_paths: list[Path], publish_timestamp_utc: str) -> DispatchPriceIngestionResult:
        rows_read = 0
        rows_norm = 0
        files_processed = 0
        for file_path in file_paths:
            try:
                raw = pd.read_csv(file_path)
            except Exception:
                continue
            files_processed += 1
            rows_read += len(raw)
            norm = self.normalize_dispatchprice_frame(
                raw,
                source_file=str(file_path),
                publish_timestamp_utc=publish_timestamp_utc,
                record_version=1,
            )
            rows_norm += len(norm)
            self.upsert(norm)

        rows_valid = int(self._state["nsw_qld_spread"].notna().sum()) if not self._state.empty else 0
        return DispatchPriceIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_dispatchregionsum_files(
        self,
        file_paths: list[Path],
        publish_timestamp_utc: str,
    ) -> RegionalDemandIngestionResult:
        rows_read = 0
        rows_norm = 0
        files_processed = 0

        for file_path in file_paths:
            raw = pd.DataFrame()
            try:
                raw = pd.read_csv(file_path)
            except Exception:
                try:
                    raw = self.parse_dispatchregionsum_archive_bytes(file_path.read_bytes())
                except Exception:
                    raw = pd.DataFrame()
            if raw.empty:
                continue

            files_processed += 1
            rows_read += len(raw)
            norm = self.normalize_dispatchregionsum_frame(
                raw,
                source_file=str(file_path),
                publish_timestamp_utc=publish_timestamp_utc,
                record_version=1,
            )
            rows_norm += len(norm)
            self.upsert(norm)

        rows_valid = int(self._state["regional_operational_demand"].notna().sum()) if not self._state.empty else 0
        return RegionalDemandIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_historical_dispatchregionsum_archive(
        self,
        raw_archive_dir: Path,
        publish_timestamp_utc: str,
        start_month: str,
        end_month: str | None = None,
        reports_dir: Path | None = None,
        diagnostic_one_file: bool = False,
    ) -> RegionalDemandIngestionResult:
        raw_archive_dir.mkdir(parents=True, exist_ok=True)
        resolved_reports_dir = reports_dir or (raw_archive_dir.parent.parent.parent / "reports")
        resolved_reports_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = self._dispatchregionsum_manifest_path(resolved_reports_dir)
        failed_path = self._dispatchregionsum_failed_files_path(resolved_reports_dir)
        cache_report_path = self._dispatchregionsum_cache_report_path(resolved_reports_dir)

        manifest = self._load_dispatchprice_manifest(manifest_path)
        parquet_supported = self._supports_parquet()
        cache_format = "parquet" if parquet_supported else "csv.gz"

        last_available_month = (pd.Timestamp.now("UTC") - pd.DateOffset(months=1)).strftime("%Y-%m")
        resolved_end_month = end_month or last_available_month

        rows_read = 0
        rows_norm = 0
        files_processed = 0
        download_attempts = 0
        download_successes = 0
        skipped_hashes = 0
        failed_files = 0
        function_name = "ingest_historical_dispatchregionsum_archive"
        started_at = time.perf_counter()

        candidate_archives: list[Path] = []
        for year, month in self._month_range(start_month, resolved_end_month):
            archive_name = f"PUBLIC_DVD_DISPATCHREGIONSUM_{year}{month:02d}010000.zip"
            archive_path = raw_archive_dir / archive_name
            if not archive_path.exists():
                download_attempts += 1
                url = _DISPATCHREGIONSUM_ARCHIVE_URL_TEMPLATE.format(year=year, month=month)
                try:
                    archive_path.write_bytes(self._download_archive(url))
                    download_successes += 1
                except (HTTPError, URLError, TimeoutError, ValueError, OSError):
                    continue
            if archive_path.exists():
                candidate_archives.append(archive_path)

        candidate_archives = sorted(candidate_archives)
        if diagnostic_one_file and candidate_archives:
            candidate_archives = candidate_archives[:1]
        files_total = len(candidate_archives)

        last_output_at = self._log_progress(
            function_name=function_name,
            files_processed=files_processed,
            rows_processed=rows_read,
            current_file="init",
            row_in_current_file=0,
        )

        for archive_path in candidate_archives:
            archive_stat = archive_path.stat()
            archive_hash = self._file_sha256(archive_path)
            modified_utc = self._to_utc_iso(archive_stat.st_mtime)

            existing = manifest[manifest["sha256_hash"].astype(str) == archive_hash]
            if not existing.empty:
                existing_row = existing.iloc[-1]
                existing_status_ok = str(existing_row.get("status", "")).upper() == "SUCCESS"
                output_path = Path(str(existing_row.get("output_partition_path", "")))
                output_exists = output_path.exists()
                existing_schema = pd.to_numeric(existing_row.get("cache_schema_version"), errors="coerce")
                schema_ok = pd.notna(existing_schema) and int(existing_schema) == _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION
                required_columns_ok = self._cache_output_has_columns(
                    output_path,
                    _DISPATCHREGIONSUM_REQUIRED_NORMALIZED_COLUMNS,
                )
                if existing_status_ok and output_exists and schema_ok and required_columns_ok:
                    skipped_hashes += 1
                    self._log_file_progress(
                        function_name=function_name,
                        files_completed=files_processed + skipped_hashes + failed_files,
                        files_total=files_total,
                        rows_processed=rows_read,
                        elapsed_seconds=time.perf_counter() - started_at,
                    )
                    continue

            in_progress_row = {
                "source_file_path": str(archive_path),
                "file_size_bytes": int(archive_stat.st_size),
                "modified_timestamp_utc": modified_utc,
                "sha256_hash": archive_hash,
                "rows_ingested": pd.NA,
                "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "output_partition_path": pd.NA,
                "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                "status": "IN_PROGRESS",
                "error": pd.NA,
            }
            manifest = self._upsert_manifest_row(manifest, in_progress_row)
            self._save_dispatchprice_manifest(manifest_path, manifest)

            try:
                progress_meta = {
                    "function_name": function_name,
                    "files_processed": files_processed,
                    "rows_processed_base": rows_read,
                    "current_file": str(archive_path),
                    "last_output_at": last_output_at,
                }
                raw = self.parse_dispatchregionsum_archive_bytes(archive_path.read_bytes(), progress_meta=progress_meta)
                last_output_at = float(progress_meta.get("last_output_at", last_output_at))

                cols_upper = {str(col).upper(): col for col in raw.columns}
                settlement_col = cols_upper.get("SETTLEMENTDATE")
                region_col = cols_upper.get("REGIONID")
                demand_col = cols_upper.get("TOTALDEMAND")
                forecast_col = cols_upper.get("DEMANDFORECAST")
                component = pd.DataFrame()
                if settlement_col and region_col and demand_col:
                    component = pd.DataFrame(
                        {
                            "interval_timestamp_utc": pd.to_datetime(raw[settlement_col], utc=True, errors="coerce"),
                            "region_id": raw[region_col].astype(str).str.upper().str.strip(),
                            "regional_operational_demand": pd.to_numeric(raw[demand_col], errors="coerce"),
                            "forecast_demand": pd.to_numeric(raw[forecast_col], errors="coerce") if forecast_col else pd.NA,
                            "source_file": str(archive_path),
                            "publish_timestamp_utc": publish_timestamp_utc,
                        }
                    )
                    component = component[
                        component["interval_timestamp_utc"].notna()
                        & component["region_id"].isin(["NSW1", "QLD1"])
                    ].copy()

                norm = self.normalize_dispatchregionsum_frame(
                    raw,
                    source_file=str(archive_path),
                    publish_timestamp_utc=publish_timestamp_utc,
                    record_version=1,
                )
                period_token = archive_path.stem.split("_")[-1][:6]
                partition_year = period_token[:4] if len(period_token) >= 4 else "unknown"
                partition_month = period_token[4:6] if len(period_token) >= 6 else "00"
                partition_dir = self._dispatchregionsum_cache_root(raw_archive_dir) / f"year={partition_year}" / f"month={partition_month}"
                partition_dir.mkdir(parents=True, exist_ok=True)
                output_name = f"dispatchregionsum_{archive_hash}.{cache_format}"
                output_path = partition_dir / output_name

                if parquet_supported:
                    component.to_parquet(output_path, index=False)
                else:
                    component.to_csv(output_path, index=False, compression="gzip")

                files_processed += 1
                rows_read += len(raw)
                rows_norm += len(norm)
                self.upsert(norm)

                success_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": int(len(component)),
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": str(output_path),
                    "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                    "status": "SUCCESS",
                    "error": pd.NA,
                }
                manifest = self._upsert_manifest_row(manifest, success_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)

                self._log_progress(
                    function_name=function_name,
                    files_processed=files_processed,
                    rows_processed=rows_read,
                    current_file=str(archive_path),
                    row_in_current_file=len(raw),
                )
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
            except IngestionStalledError as exc:
                print(json.dumps(exc.report), flush=True)
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                    "status": "FAILED",
                    "error": str(exc.report),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                break
            except Exception as exc:
                fail_row = {
                    "source_file_path": str(archive_path),
                    "file_size_bytes": int(archive_stat.st_size),
                    "modified_timestamp_utc": modified_utc,
                    "sha256_hash": archive_hash,
                    "rows_ingested": pd.NA,
                    "ingestion_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "output_partition_path": pd.NA,
                    "cache_schema_version": _DISPATCHREGIONSUM_CACHE_SCHEMA_VERSION,
                    "status": "FAILED",
                    "error": str(exc),
                }
                manifest = self._upsert_manifest_row(manifest, fail_row)
                self._save_dispatchprice_manifest(manifest_path, manifest)
                failed_files += 1
                self._log_file_progress(
                    function_name=function_name,
                    files_completed=files_processed + skipped_hashes + failed_files,
                    files_total=files_total,
                    rows_processed=rows_read,
                    elapsed_seconds=time.perf_counter() - started_at,
                )
                continue

        self._save_dispatchprice_manifest(manifest_path, manifest)

        failed_manifest = manifest[manifest["status"].astype(str).str.upper() == "FAILED"].copy()
        failed_manifest.to_csv(failed_path, index=False)

        cache_report_lines = [
            "# Phase5C DISPATCHREGIONSUM Cache Report",
            "",
            f"- Cache format: `{cache_format}`",
            f"- Parquet supported: `{'Yes' if parquet_supported else 'No'}`",
            f"- Files total considered: `{files_total}`",
            f"- Files processed this run: `{files_processed}`",
            f"- Files skipped by hash: `{skipped_hashes}`",
            f"- Failed files: `{len(failed_manifest)}`",
            f"- Rows read this run: `{rows_read}`",
            f"- Rows normalized this run: `{rows_norm}`",
            f"- Manifest: `{manifest_path}`",
            f"- Failed file report: `{failed_path}`",
        ]
        if not parquet_supported:
            cache_report_lines.append("- Limitation: `pyarrow`/`fastparquet` unavailable, using compressed CSV cache.")
        cache_report_path.write_text("\n".join(cache_report_lines) + "\n", encoding="utf-8")

        rows_valid = int(self._state["regional_operational_demand"].notna().sum()) if not self._state.empty else 0
        return RegionalDemandIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
            download_attempts=download_attempts,
            download_successes=download_successes,
        )

    def ingest_dispatchconstraint_files(
        self,
        file_paths: list[Path],
        publish_timestamp_utc: str,
    ) -> ConstraintIngestionResult:
        rows_read = 0
        rows_norm = 0
        files_processed = 0

        for file_path in file_paths:
            raw = pd.DataFrame()
            try:
                raw = pd.read_csv(file_path)
            except Exception:
                try:
                    raw = self.parse_dispatchconstraint_archive_bytes(file_path.read_bytes())
                except Exception:
                    raw = pd.DataFrame()
            if raw.empty:
                continue

            files_processed += 1
            rows_read += len(raw)
            norm = self.normalize_dispatchconstraint_frame(
                raw,
                source_file=str(file_path),
                publish_timestamp_utc=publish_timestamp_utc,
                record_version=1,
            )
            rows_norm += len(norm)
            self.upsert(norm)

        rows_valid = int(self._state["constraint_binding_flag"].notna().sum()) if not self._state.empty else 0
        return ConstraintIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
        )

    def ingest_historical_dispatchconstraint_archive(
        self,
        raw_archive_dir: Path,
        publish_timestamp_utc: str,
        start_month: str,
        end_month: str | None = None,
    ) -> ConstraintIngestionResult:
        raw_archive_dir.mkdir(parents=True, exist_ok=True)
        last_available_month = (pd.Timestamp.now("UTC") - pd.DateOffset(months=1)).strftime("%Y-%m")
        resolved_end_month = end_month or last_available_month

        rows_read = 0
        rows_norm = 0
        files_processed = 0
        download_attempts = 0
        download_successes = 0
        last_output_at = self._log_progress(
            function_name="ingest_historical_dispatchconstraint_archive",
            files_processed=files_processed,
            rows_processed=rows_read,
            current_file="init",
            row_in_current_file=0,
        )

        for year, month in self._month_range(start_month, resolved_end_month):
            archive_name = f"PUBLIC_DVD_DISPATCHCONSTRAINT_{year}{month:02d}010000.zip"
            archive_path = raw_archive_dir / archive_name
            if not archive_path.exists():
                download_attempts += 1
                url = _DISPATCHCONSTRAINT_ARCHIVE_URL_TEMPLATE.format(year=year, month=month)
                try:
                    archive_path.write_bytes(self._download_archive(url))
                    download_successes += 1
                except (HTTPError, URLError, TimeoutError, ValueError, OSError):
                    continue

            try:
                cache_path = self._cache_file_path(raw_archive_dir, archive_name, "dispatchconstraint_corridor")
                if cache_path.exists():
                    raw = pd.read_csv(cache_path)
                else:
                    progress_meta = {
                        "function_name": "ingest_historical_dispatchconstraint_archive",
                        "files_processed": files_processed,
                        "rows_processed_base": rows_read,
                        "current_file": str(archive_path),
                        "last_output_at": last_output_at,
                    }
                    raw = self.parse_dispatchconstraint_archive_bytes(archive_path.read_bytes(), progress_meta=progress_meta)
                    last_output_at = float(progress_meta.get("last_output_at", last_output_at))
                    raw.to_csv(cache_path, index=False, compression="gzip")
            except IngestionStalledError as exc:
                print(json.dumps(exc.report), flush=True)
                break
            except Exception:
                continue

            files_processed += 1
            rows_read += len(raw)
            norm = self.normalize_dispatchconstraint_frame(
                raw,
                source_file=str(archive_path),
                publish_timestamp_utc=publish_timestamp_utc,
                record_version=1,
            )
            rows_norm += len(norm)
            self.upsert(norm)
            last_output_at = self._log_progress(
                function_name="ingest_historical_dispatchconstraint_archive",
                files_processed=files_processed,
                rows_processed=rows_read,
                current_file=str(archive_path),
                row_in_current_file=len(raw),
            )

        rows_valid = int(self._state["constraint_binding_flag"].notna().sum()) if not self._state.empty else 0
        return ConstraintIngestionResult(
            rows_read=rows_read,
            rows_normalized=rows_norm,
            rows_valid=rows_valid,
            files_processed=files_processed,
            download_attempts=download_attempts,
            download_successes=download_successes,
        )

    def query_market_state_at(self, timestamp_utc: str) -> pd.DataFrame:
        if self._state.empty:
            return self._state.copy()
        ts = pd.to_datetime(timestamp_utc, utc=True, errors="coerce")
        if pd.isna(ts):
            return pd.DataFrame(columns=self._state.columns)
        frame = self._state.copy()
        frame["interval_timestamp_utc"] = pd.to_datetime(frame["interval_timestamp_utc"], utc=True, errors="coerce")
        return frame[frame["interval_timestamp_utc"] == ts].copy()
