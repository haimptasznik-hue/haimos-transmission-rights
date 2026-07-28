#!/usr/bin/env python3
"""Stage 2C Phase 1A full 79-month regional calendar integration."""

from __future__ import annotations

import csv
import gzip
import json
import os
import resource
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from build_calendar_features_v2 import (
    CALENDAR_FEATURE_DEFINITION_VERSION,
    add_calendar_features_regional,
    get_all_regional_holidays,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "data" / "derived" / "historical_feature_store" / "checkpoints"
OUTPUT_ROOT = REPO_ROOT / "data" / "derived" / "historical_feature_store_calendar_v2_regional"
OUTPUT_CHECKPOINT_DIR = OUTPUT_ROOT / "checkpoints"
REPORTS_DIR = REPO_ROOT / "reports"

CANONICAL_KEYS = ["observation_timestamp_utc", "interval_timestamp_utc"]
TIMESTAMP_CANDIDATES = {
    "observation_timestamp_utc",
    "interval_timestamp_utc",
    "effective_timestamp_utc",
    "publication_timestamp_utc",
}

REGION_TIMEZONES = {
    "nsw": "Australia/Sydney",
    "qld": "Australia/Brisbane",
    "vic": "Australia/Melbourne",
    "sa": "Australia/Adelaide",
    "tas": "Australia/Hobart",
}

REGION_TO_MARKET = {
    "nsw": "NSW1",
    "qld": "QLD1",
    "vic": "VIC1",
    "sa": "SA1",
    "tas": "TAS1",
}

REGIONAL_FIELD_SUFFIXES = [
    "local_timestamp",
    "local_date",
    "local_hour",
    "local_day_of_week",
    "weekend_flag",
    "business_day_flag",
    "public_holiday_flag",
    "public_holiday_name",
    "pre_holiday_flag",
    "post_holiday_flag",
    "bridge_day_flag",
    "daylight_saving_flag",
    "daylight_saving_transition_flag",
    "Easter_period_flag",
    "Christmas_New_Year_period_flag",
    "working_day_count_in_month",
]


@dataclass
class ProgressState:
    total_months: int
    start_time: float
    last_update_time: float
    months_completed: int = 0
    latest_completed_month: str = ""
    current_month: str = ""
    rows_processed: int = 0
    latest_checkpoint: str = ""
    blockers: str = "None"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _semantic_timestamp_equal(base: pd.Series, enriched: pd.Series) -> bool:
    b = _to_utc(base)
    e = _to_utc(enriched)
    sentinel = pd.Timestamp("1970-01-01", tz="UTC")
    return b.fillna(sentinel).equals(e.fillna(sentinel))


def _rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = float(usage.ru_maxrss)
    if rss > 10_000_000:
        return round(rss / (1024.0 * 1024.0), 2)
    return round(rss / 1024.0, 2)


def _cpu_hint() -> str:
    try:
        load1, _load5, _load15 = os.getloadavg()
        return f"load1={load1:.2f}"
    except OSError:
        return "load1=n/a"


def _elapsed(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def _json_dump_text(payload: object) -> str:
    def _default(value: object) -> object:
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return str(value)

    return json.dumps(payload, indent=2, allow_nan=False, default=_default)


def _build_calendar_columns() -> List[str]:
    return [f"{region}_{suffix}" for region in REGION_TIMEZONES for suffix in REGIONAL_FIELD_SUFFIXES]


def _source_months() -> List[str]:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source checkpoints directory not found: {SOURCE_DIR}")
    months = []
    for path in sorted(SOURCE_DIR.iterdir()):
        if not path.is_dir():
            continue
        if (path / "historical_market_feature_store_5min.csv.gz").exists():
            months.append(path.name)
    if not months:
        raise RuntimeError("No monthly checkpoints found in source store")
    return months


def _month_paths(month: str) -> Tuple[Path, Path, Path, Path]:
    month_dir = OUTPUT_CHECKPOINT_DIR / month
    checkpoint_path = month_dir / "historical_market_feature_store_5min.csv.gz"
    marker_path = month_dir / ".phase1a_complete.json"
    month_lineage_path = month_dir / "calendar_lineage.json"
    month_quality_path = month_dir / "calendar_quality.json"
    return checkpoint_path, marker_path, month_lineage_path, month_quality_path


def _load_source_month(month: str) -> pd.DataFrame:
    source_path = SOURCE_DIR / month / "historical_market_feature_store_5min.csv.gz"
    with gzip.open(source_path, "rt") as f:
        return pd.read_csv(f)


def _write_month_checkpoint(month: str, df: pd.DataFrame) -> Path:
    month_dir = OUTPUT_CHECKPOINT_DIR / month
    month_dir.mkdir(parents=True, exist_ok=True)
    out_path = month_dir / "historical_market_feature_store_5min.csv.gz"
    with gzip.open(out_path, "wt") as f:
        df.to_csv(f, index=False)
    return out_path


def _dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            fp = Path(root) / name
            if fp.exists():
                total += fp.stat().st_size
    return total


def _validate_month(
    base_df: pd.DataFrame,
    enriched_df: pd.DataFrame,
    holiday_maps: Dict[str, Dict[str, str]],
) -> Dict[str, object]:
    gates: Dict[str, object] = {}

    gates["row_count_preserved"] = len(base_df) == len(enriched_df)

    if not all(key in enriched_df.columns for key in CANONICAL_KEYS):
        raise RuntimeError(f"Canonical keys missing in enriched month: {CANONICAL_KEYS}")

    duplicate_keys = int(enriched_df.duplicated(CANONICAL_KEYS).sum())
    gates["duplicate_canonical_keys"] = duplicate_keys
    gates["duplicate_keys_zero"] = duplicate_keys == 0

    canonical_semantic = True
    for key in CANONICAL_KEYS:
        canonical_semantic = canonical_semantic and _semantic_timestamp_equal(base_df[key], enriched_df[key])
    gates["canonical_utc_semantically_unchanged"] = canonical_semantic

    base_columns = list(base_df.columns)
    gates["base_columns_preserved_exactly"] = base_columns == list(enriched_df.columns[: len(base_columns)])

    non_ts_ok = True
    ts_ok = True
    non_ts_mutations = 0
    ts_mutations = 0
    for col in base_columns:
        if col in TIMESTAMP_CANDIDATES:
            eq = _semantic_timestamp_equal(base_df[col], enriched_df[col])
            ts_ok = ts_ok and eq
            if not eq:
                ts_mutations += 1
        else:
            eq = base_df[col].equals(enriched_df[col])
            non_ts_ok = non_ts_ok and eq
            if not eq:
                non_ts_mutations += 1
    gates["non_timestamp_base_columns_strictly_unchanged"] = non_ts_ok
    gates["timestamp_base_columns_semantically_unchanged"] = ts_ok
    gates["non_timestamp_base_mutation_columns"] = non_ts_mutations
    gates["timestamp_base_mutation_columns"] = ts_mutations

    calendar_cols = _build_calendar_columns()
    missing_calendar_cols = [c for c in calendar_cols if c not in enriched_df.columns]
    gates["calendar_columns_present"] = len(missing_calendar_cols) == 0
    gates["missing_calendar_columns"] = missing_calendar_cols

    obs_utc = _to_utc(enriched_df["observation_timestamp_utc"])

    local_ts_valid = True
    local_date_valid = True
    holiday_valid = True
    dst_valid = True
    contamination_count = 0

    holiday_coverage_by_region: Dict[str, int] = {}
    business_day_count_by_region: Dict[str, int] = {}
    dst_transition_count_by_region: Dict[str, int] = {}

    for region, tz_name in REGION_TIMEZONES.items():
        local_ts_col = f"{region}_local_timestamp"
        local_date_col = f"{region}_local_date"
        local_hour_col = f"{region}_local_hour"
        holiday_flag_col = f"{region}_public_holiday_flag"
        holiday_name_col = f"{region}_public_holiday_name"
        dst_flag_col = f"{region}_daylight_saving_flag"
        dst_transition_col = f"{region}_daylight_saving_transition_flag"
        business_col = f"{region}_business_day_flag"

        expected_local = obs_utc.dt.tz_convert(tz_name)
        actual_local = pd.to_datetime(enriched_df[local_ts_col], errors="coerce")

        expected_utc = expected_local.dt.tz_convert("UTC")
        actual_utc = pd.to_datetime(actual_local, utc=True, errors="coerce")
        sentinel = pd.Timestamp("1970-01-01", tz="UTC")
        region_local_ts_ok = expected_utc.fillna(sentinel).equals(actual_utc.fillna(sentinel))
        local_ts_valid = local_ts_valid and region_local_ts_ok

        expected_local_date = expected_local.dt.strftime("%Y-%m-%d")
        expected_local_hour = expected_local.dt.hour
        region_local_date_ok = expected_local_date.equals(enriched_df[local_date_col].astype(str))
        region_local_hour_ok = expected_local_hour.equals(pd.to_numeric(enriched_df[local_hour_col], errors="coerce"))
        local_date_valid = local_date_valid and region_local_date_ok and region_local_hour_ok

        region_map = holiday_maps[REGION_TO_MARKET[region]]
        expected_holiday_name = enriched_df[local_date_col].astype(str).map(region_map).fillna("")
        expected_holiday_flag = expected_holiday_name.ne("").astype(int)

        actual_holiday_flag = pd.to_numeric(enriched_df[holiday_flag_col], errors="coerce").fillna(0).astype(int)
        actual_holiday_name = enriched_df[holiday_name_col].fillna("").astype(str)

        region_holiday_mismatch = (
            (actual_holiday_flag != expected_holiday_flag)
            | ((expected_holiday_flag == 1) & (actual_holiday_name != expected_holiday_name))
        )
        mismatch_count = int(region_holiday_mismatch.sum())
        contamination_count += mismatch_count
        holiday_valid = holiday_valid and mismatch_count == 0

        dst_flag_series = pd.to_numeric(enriched_df[dst_flag_col], errors="coerce").fillna(0).astype(int)
        dst_transition_series = pd.to_numeric(enriched_df[dst_transition_col], errors="coerce").fillna(0).astype(int)

        if region == "qld":
            region_dst_ok = bool((dst_flag_series == 0).all() and (dst_transition_series == 0).all())
        else:
            offset_seconds = actual_local.apply(
                lambda value: value.utcoffset().total_seconds() if pd.notna(value) else None
            )
            expected_transition = offset_seconds.ne(offset_seconds.shift(1)).fillna(False).astype(int)
            if len(expected_transition) > 0:
                expected_transition.iloc[0] = 0
            region_dst_ok = bool(
                dst_flag_series.isin([0, 1]).all()
                and dst_transition_series.isin([0, 1]).all()
                and dst_transition_series.equals(expected_transition)
            )

        dst_valid = dst_valid and region_dst_ok

        holiday_coverage_by_region[region] = int(actual_holiday_flag.sum())
        business_day_count_by_region[region] = int(
            enriched_df.loc[pd.to_numeric(enriched_df[business_col], errors="coerce").fillna(0).astype(int) == 1, local_date_col]
            .astype(str)
            .nunique()
        )
        dst_transition_count_by_region[region] = int(dst_transition_series.sum())

    gates["regional_local_timestamps_valid"] = local_ts_valid
    gates["regional_local_date_hour_valid"] = local_date_valid
    gates["public_holiday_jurisdiction_valid"] = holiday_valid
    gates["dst_handling_valid"] = dst_valid
    gates["cross_state_contamination_count"] = contamination_count
    gates["no_cross_state_contamination"] = contamination_count == 0

    version_ok = (
        "calendar_feature_definition_version" in enriched_df.columns
        and enriched_df["calendar_feature_definition_version"].astype(str).eq(CALENDAR_FEATURE_DEFINITION_VERSION).all()
    )
    lineage_ok = (
        "holiday_source_lineage" in enriched_df.columns
        and "holiday_jurisdiction_lineage" in enriched_df.columns
        and enriched_df["holiday_source_lineage"].astype(str).str.len().gt(0).all()
        and enriched_df["holiday_jurisdiction_lineage"].astype(str).str.len().gt(0).all()
    )
    gates["lineage_populated"] = lineage_ok
    gates["feature_definition_version_correct"] = version_ok

    pass_all = (
        gates["row_count_preserved"]
        and gates["duplicate_keys_zero"]
        and gates["canonical_utc_semantically_unchanged"]
        and gates["base_columns_preserved_exactly"]
        and gates["non_timestamp_base_columns_strictly_unchanged"]
        and gates["timestamp_base_columns_semantically_unchanged"]
        and gates["calendar_columns_present"]
        and gates["regional_local_timestamps_valid"]
        and gates["regional_local_date_hour_valid"]
        and gates["public_holiday_jurisdiction_valid"]
        and gates["dst_handling_valid"]
        and gates["no_cross_state_contamination"]
        and gates["lineage_populated"]
        and gates["feature_definition_version_correct"]
    )

    gates["state_holiday_validation"] = holiday_valid
    gates["holiday_coverage_by_region"] = holiday_coverage_by_region
    gates["business_day_count_by_region"] = business_day_count_by_region
    gates["dst_transition_count_by_region"] = dst_transition_count_by_region
    gates["pass_all"] = pass_all

    return gates


def _write_month_metadata(month: str, quality: Dict[str, object], source_rows: int, enriched_path: Path) -> None:
    checkpoint_path, marker_path, month_lineage_path, month_quality_path = _month_paths(month)

    month_lineage_payload = {
        "month": month,
        "feature_set_version": "historical_feature_store_calendar_v2_regional",
        "calendar_feature_definition_version": CALENDAR_FEATURE_DEFINITION_VERSION,
        "source_feature_store_version": "historical-feature-store-v1.0",
        "source_checkpoint": str(SOURCE_DIR / month / "historical_market_feature_store_5min.csv.gz"),
        "enriched_checkpoint": str(enriched_path),
        "lineage_generated_at_utc": _utc_now_iso(),
        "holiday_source_lineage": "National + state public holiday calendar curated in build_calendar_features_v2.py",
        "holiday_jurisdiction_lineage": "NSW1:NSW,QLD1:QLD,VIC1:VIC,SA1:SA,TAS1:TAS",
    }
    month_lineage_path.write_text(_json_dump_text(month_lineage_payload), encoding="utf-8")

    month_quality_payload = {
        "month": month,
        "rows_source": int(source_rows),
        "rows_enriched": int(source_rows),
        "quality_generated_at_utc": _utc_now_iso(),
        "gates": quality,
    }
    month_quality_path.write_text(_json_dump_text(month_quality_payload), encoding="utf-8")

    marker_payload = {
        "month": month,
        "status": "COMPLETE",
        "completed_at_utc": _utc_now_iso(),
        "enriched_checkpoint": str(checkpoint_path),
        "calendar_lineage_metadata": str(month_lineage_path),
        "calendar_quality_metadata": str(month_quality_path),
        "rows": int(source_rows),
        "validation_pass_all": bool(quality["pass_all"]),
        "feature_definition_version": CALENDAR_FEATURE_DEFINITION_VERSION,
    }
    marker_path.write_text(_json_dump_text(marker_payload), encoding="utf-8")


def _progress_update(state: ProgressState, event: str, confidence: str = "High") -> None:
    now = time.time()
    elapsed = now - state.start_time
    completed = state.months_completed
    remaining = max(state.total_months - completed, 0)
    avg_per_month = elapsed / completed if completed > 0 else 0.0
    eta_seconds = avg_per_month * remaining if completed > 0 else 0.0
    percent_complete = (completed / state.total_months * 100.0) if state.total_months else 0.0

    print("\nProject Status")
    print(f"Current Objective: Stage 2C Phase 1A full 79-month regional calendar integration ({event})")
    print(f"Current Month: {state.current_month}")
    print(f"Latest Completed Month: {state.latest_completed_month}")
    print(f"Months Completed: {completed}")
    print(f"Months Remaining: {remaining}")
    print(f"Percent Complete: {percent_complete:.2f}%")
    print(f"Elapsed Runtime: {_elapsed(elapsed)}")
    print(f"Average Runtime / Month: {avg_per_month:.2f}s")
    print(f"Estimated Time Remaining: {_elapsed(eta_seconds)}")
    print(f"Latest Checkpoint: {state.latest_checkpoint}")
    print(f"CPU: {_cpu_hint()}")
    print(f"Memory: {_rss_mb():.2f} MB")
    print(f"Rows Processed: {state.rows_processed}")
    print(f"Known Blockers: {state.blockers}")
    print(f"Confidence: {confidence}")
    print("-")

    state.last_update_time = now


def _write_full_history_reports(
    months: List[str],
    monthly_rows: List[Dict[str, object]],
    summary: Dict[str, object],
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    status_md = REPORTS_DIR / "PHASE1A_CALENDAR_FULL_HISTORY_STATUS.md"
    quality_csv = REPORTS_DIR / "PHASE1A_CALENDAR_FULL_HISTORY_QUALITY.csv"
    coverage_csv = REPORTS_DIR / "PHASE1A_CALENDAR_FULL_HISTORY_COVERAGE.csv"
    lineage_md = REPORTS_DIR / "PHASE1A_CALENDAR_FULL_HISTORY_LINEAGE.md"
    metadata_json = REPORTS_DIR / "PHASE1A_CALENDAR_FULL_HISTORY_METADATA.json"
    dictionary_md = REPORTS_DIR / "PHASE1A_CALENDAR_FEATURE_DATA_DICTIONARY.md"

    quality_fields = [
        "month",
        "rows",
        "reused_checkpoint",
        "runtime_sec",
        "row_count_preserved",
        "duplicate_canonical_keys",
        "canonical_utc_semantically_unchanged",
        "non_timestamp_base_columns_strictly_unchanged",
        "timestamp_base_columns_semantically_unchanged",
        "calendar_columns_present",
        "regional_local_timestamps_valid",
        "public_holiday_jurisdiction_valid",
        "dst_handling_valid",
        "cross_state_contamination_count",
        "lineage_populated",
        "feature_definition_version_correct",
        "pass_all",
    ]
    with quality_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=quality_fields)
        writer.writeheader()
        for row in monthly_rows:
            out = {key: row.get(key, "") for key in quality_fields}
            writer.writerow(out)

    coverage_fields = [
        "month",
        "start_observation_utc",
        "end_observation_utc",
        "rows",
        "holiday_intervals_nsw",
        "holiday_intervals_qld",
        "holiday_intervals_vic",
        "holiday_intervals_sa",
        "holiday_intervals_tas",
        "business_days_nsw",
        "business_days_qld",
        "business_days_vic",
        "business_days_sa",
        "business_days_tas",
        "dst_transitions_nsw",
        "dst_transitions_qld",
        "dst_transitions_vic",
        "dst_transitions_sa",
        "dst_transitions_tas",
    ]
    with coverage_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=coverage_fields)
        writer.writeheader()
        for row in monthly_rows:
            writer.writerow({key: row.get(key, "") for key in coverage_fields})

    status_lines = [
        "# Phase 1A Calendar Full History Status",
        "",
        f"- months_enriched: {summary['months_enriched']}",
        f"- rows_enriched: {summary['rows_enriched']}",
        f"- historical_start: {summary['historical_start']}",
        f"- historical_end: {summary['historical_end']}",
        f"- duplicate_canonical_keys_total: {summary['duplicate_canonical_keys_total']}",
        f"- row_count_preservation_all_months: {summary['row_count_preservation_all_months']}",
        f"- base_column_preservation_all_months: {summary['base_column_preservation_all_months']}",
        f"- cross_state_contamination_count_total: {summary['cross_state_contamination_count_total']}",
        f"- lineage_completeness_pct: {summary['lineage_completeness_pct']}",
        f"- checkpoint_reuse_months: {summary['checkpoint_reuse_months']}",
        f"- runtime_seconds_total: {summary['runtime_seconds_total']:.2f}",
        f"- runtime_seconds_avg_per_month: {summary['runtime_seconds_avg_per_month']:.2f}",
        f"- disk_usage_bytes_output_store: {summary['disk_usage_bytes_output_store']}",
        "",
        "## Acceptance Criteria",
        f"- 79/79 months enriched: {summary['months_enriched'] == 79}",
        f"- 691,106 rows preserved: {summary['rows_enriched'] == 691106}",
        f"- 0 duplicate canonical keys: {summary['duplicate_canonical_keys_total'] == 0}",
        f"- 0 base-value mutations: {summary['base_value_mutations_total'] == 0}",
        f"- 0 cross-state contamination defects: {summary['cross_state_contamination_count_total'] == 0}",
        f"- 100% regional calendar coverage: {summary['regional_calendar_coverage_pct'] == 100.0}",
        f"- 100% calendar lineage completeness: {summary['lineage_completeness_pct'] == 100.0}",
        f"- all monthly completion markers present: {summary['all_completion_markers_present']}",
    ]
    status_md.write_text("\n".join(status_lines), encoding="utf-8")

    lineage_lines = [
        "# Phase 1A Calendar Full History Lineage",
        "",
        "- source_feature_store_version: historical-feature-store-v1.0",
        "- enriched_feature_store_version: historical_feature_store_calendar_v2_regional",
        f"- calendar_feature_definition_version: {CALENDAR_FEATURE_DEFINITION_VERSION}",
        "- holiday_source_lineage: National + state public holiday calendar curated in build_calendar_features_v2.py",
        "- holiday_jurisdiction_lineage: NSW1:NSW,QLD1:QLD,VIC1:VIC,SA1:SA,TAS1:TAS",
        "",
        "## Monthly Completion Markers",
    ]
    for month in months:
        _checkpoint, marker_path, _lineage_path, _quality_path = _month_paths(month)
        lineage_lines.append(f"- {month}: {marker_path}")
    lineage_md.write_text("\n".join(lineage_lines), encoding="utf-8")

    metadata_json.write_text(_json_dump_text(summary), encoding="utf-8")

    dict_lines = [
        "# Phase 1A Calendar Feature Data Dictionary",
        "",
        f"- feature_definition_version: {CALENDAR_FEATURE_DEFINITION_VERSION}",
        "",
        "## Regional Calendar Columns (per region: nsw, qld, vic, sa, tas)",
        "",
        "| Suffix | Description |",
        "|---|---|",
        "| local_timestamp | Region-local timezone timestamp derived from observation UTC |",
        "| local_date | Region-local calendar date (YYYY-MM-DD) |",
        "| local_hour | Region-local hour (0-23) |",
        "| local_day_of_week | Region-local weekday number (Monday=0..Sunday=6) |",
        "| weekend_flag | 1 if local day is Saturday/Sunday else 0 |",
        "| business_day_flag | 1 if weekday and not public holiday else 0 |",
        "| public_holiday_flag | 1 if region holiday applies on local date else 0 |",
        "| public_holiday_name | Official holiday name for region/local date else empty |",
        "| pre_holiday_flag | 1 if next local day is a region holiday else 0 |",
        "| post_holiday_flag | 1 if prior local day is a region holiday else 0 |",
        "| bridge_day_flag | 1 for working-day bridge between holidays else 0 |",
        "| daylight_saving_flag | 1 if DST active in region at local timestamp else 0 |",
        "| daylight_saving_transition_flag | 1 at DST offset transition intervals else 0 |",
        "| Easter_period_flag | 1 if local date in Easter event window else 0 |",
        "| Christmas_New_Year_period_flag | 1 if local date in Christmas/New Year window else 0 |",
        "| working_day_count_in_month | Count of business days in region-local month |",
        "",
        "## Metadata Columns",
        "",
        "| Column | Description |",
        "|---|---|",
        "| calendar_feature_definition_version | Calendar feature schema version identifier |",
        "| holiday_source_lineage | Holiday source lineage description |",
        "| holiday_jurisdiction_lineage | Region-to-jurisdiction lineage mapping |",
    ]
    dictionary_md.write_text("\n".join(dict_lines), encoding="utf-8")


def integrate_full_history() -> Dict[str, object]:
    OUTPUT_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    months = _source_months()
    total_months = len(months)

    state = ProgressState(
        total_months=total_months,
        start_time=time.time(),
        last_update_time=time.time(),
    )

    holiday_maps = get_all_regional_holidays()

    monthly_rows: List[Dict[str, object]] = []
    completion_markers_present = True
    latest_year = ""

    _progress_update(state, event="integration started", confidence="High")

    for idx, month in enumerate(months, start=1):
        month_start = time.time()
        state.current_month = month

        year = month.split("-")[0]
        if year != latest_year:
            latest_year = year
            _progress_update(state, event=f"new year begins processing: {year}", confidence="High")

        checkpoint_path, marker_path, month_lineage_path, month_quality_path = _month_paths(month)

        reused = False
        if checkpoint_path.exists() and marker_path.exists() and month_lineage_path.exists() and month_quality_path.exists():
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("status") == "COMPLETE":
                reused = True
                rows = int(marker.get("rows", 0))
                quality_payload = json.loads(month_quality_path.read_text(encoding="utf-8"))
                gates = quality_payload.get("gates", {})

                monthly_rows.append(
                    {
                        "month": month,
                        "rows": rows,
                        "reused_checkpoint": True,
                        "runtime_sec": round(time.time() - month_start, 4),
                        **gates,
                        "start_observation_utc": quality_payload.get("start_observation_utc", ""),
                        "end_observation_utc": quality_payload.get("end_observation_utc", ""),
                        "holiday_intervals_nsw": gates.get("holiday_coverage_by_region", {}).get("nsw", 0),
                        "holiday_intervals_qld": gates.get("holiday_coverage_by_region", {}).get("qld", 0),
                        "holiday_intervals_vic": gates.get("holiday_coverage_by_region", {}).get("vic", 0),
                        "holiday_intervals_sa": gates.get("holiday_coverage_by_region", {}).get("sa", 0),
                        "holiday_intervals_tas": gates.get("holiday_coverage_by_region", {}).get("tas", 0),
                        "business_days_nsw": gates.get("business_day_count_by_region", {}).get("nsw", 0),
                        "business_days_qld": gates.get("business_day_count_by_region", {}).get("qld", 0),
                        "business_days_vic": gates.get("business_day_count_by_region", {}).get("vic", 0),
                        "business_days_sa": gates.get("business_day_count_by_region", {}).get("sa", 0),
                        "business_days_tas": gates.get("business_day_count_by_region", {}).get("tas", 0),
                        "dst_transitions_nsw": gates.get("dst_transition_count_by_region", {}).get("nsw", 0),
                        "dst_transitions_qld": gates.get("dst_transition_count_by_region", {}).get("qld", 0),
                        "dst_transitions_vic": gates.get("dst_transition_count_by_region", {}).get("vic", 0),
                        "dst_transitions_sa": gates.get("dst_transition_count_by_region", {}).get("sa", 0),
                        "dst_transitions_tas": gates.get("dst_transition_count_by_region", {}).get("tas", 0),
                    }
                )

                state.months_completed += 1
                state.latest_completed_month = month
                state.rows_processed += rows
                state.latest_checkpoint = str(checkpoint_path)

                if state.months_completed % 10 == 0:
                    _progress_update(state, event="10-month milestone (reused checkpoints)", confidence="High")

                if time.time() - state.last_update_time >= 600:
                    _progress_update(state, event="10-minute heartbeat", confidence="High")

        if reused:
            continue

        base_df = _load_source_month(month)
        enriched_df = add_calendar_features_regional(base_df.copy())

        gates = _validate_month(base_df, enriched_df, holiday_maps)

        if not gates["pass_all"]:
            state.blockers = f"Month {month} failed validation gates"
            _progress_update(state, event="warning/exception", confidence="Low")

            failing_gates = {
                key: value
                for key, value in gates.items()
                if isinstance(value, bool) and value is False
            }
            raise RuntimeError(
                "Monthly validation failed. "
                f"month={month}, failing_gates={failing_gates}, duplicate_keys={gates.get('duplicate_canonical_keys')}"
            )

        out_path = _write_month_checkpoint(month, enriched_df)

        month_quality_payload = {
            "month": month,
            "rows_source": int(len(base_df)),
            "rows_enriched": int(len(enriched_df)),
            "quality_generated_at_utc": _utc_now_iso(),
            "start_observation_utc": str(_to_utc(enriched_df["observation_timestamp_utc"]).min()),
            "end_observation_utc": str(_to_utc(enriched_df["observation_timestamp_utc"]).max()),
            "gates": gates,
        }
        month_quality_path.parent.mkdir(parents=True, exist_ok=True)
        month_quality_path.write_text(_json_dump_text(month_quality_payload), encoding="utf-8")

        _write_month_metadata(month, gates, len(base_df), out_path)

        monthly_rows.append(
            {
                "month": month,
                "rows": int(len(base_df)),
                "reused_checkpoint": False,
                "runtime_sec": round(time.time() - month_start, 4),
                **gates,
                "start_observation_utc": str(_to_utc(enriched_df["observation_timestamp_utc"]).min()),
                "end_observation_utc": str(_to_utc(enriched_df["observation_timestamp_utc"]).max()),
                "holiday_intervals_nsw": gates["holiday_coverage_by_region"]["nsw"],
                "holiday_intervals_qld": gates["holiday_coverage_by_region"]["qld"],
                "holiday_intervals_vic": gates["holiday_coverage_by_region"]["vic"],
                "holiday_intervals_sa": gates["holiday_coverage_by_region"]["sa"],
                "holiday_intervals_tas": gates["holiday_coverage_by_region"]["tas"],
                "business_days_nsw": gates["business_day_count_by_region"]["nsw"],
                "business_days_qld": gates["business_day_count_by_region"]["qld"],
                "business_days_vic": gates["business_day_count_by_region"]["vic"],
                "business_days_sa": gates["business_day_count_by_region"]["sa"],
                "business_days_tas": gates["business_day_count_by_region"]["tas"],
                "dst_transitions_nsw": gates["dst_transition_count_by_region"]["nsw"],
                "dst_transitions_qld": gates["dst_transition_count_by_region"]["qld"],
                "dst_transitions_vic": gates["dst_transition_count_by_region"]["vic"],
                "dst_transitions_sa": gates["dst_transition_count_by_region"]["sa"],
                "dst_transitions_tas": gates["dst_transition_count_by_region"]["tas"],
            }
        )

        state.months_completed += 1
        state.latest_completed_month = month
        state.rows_processed += int(len(base_df))
        state.latest_checkpoint = str(out_path)

        _progress_update(state, event="checkpoint written", confidence="High")

        if state.months_completed % 10 == 0:
            _progress_update(state, event="10-month milestone", confidence="High")

        if time.time() - state.last_update_time >= 600:
            _progress_update(state, event="10-minute heartbeat", confidence="High")

    elapsed_total = time.time() - state.start_time

    monthly_df = pd.DataFrame(monthly_rows).sort_values("month").reset_index(drop=True)

    duplicates_total = int(monthly_df["duplicate_canonical_keys"].sum()) if not monthly_df.empty else 0
    row_count_preserved_all = bool(monthly_df["row_count_preserved"].all()) if not monthly_df.empty else False
    base_preserved_all = bool(monthly_df["base_columns_preserved_exactly"].all()) if not monthly_df.empty else False
    no_non_ts_mutation = bool(monthly_df["non_timestamp_base_columns_strictly_unchanged"].all()) if not monthly_df.empty else False
    no_ts_mutation = bool(monthly_df["timestamp_base_columns_semantically_unchanged"].all()) if not monthly_df.empty else False
    base_value_mutations_total = int(monthly_df["non_timestamp_base_mutation_columns"].sum() + monthly_df["timestamp_base_mutation_columns"].sum()) if not monthly_df.empty else 0

    cross_state_contamination_count_total = int(monthly_df["cross_state_contamination_count"].sum()) if not monthly_df.empty else 0

    lineage_completeness_pct = 100.0 if (not monthly_df.empty and bool(monthly_df["lineage_populated"].all())) else 0.0
    regional_calendar_coverage_pct = 100.0 if (not monthly_df.empty and bool(monthly_df["calendar_columns_present"].all())) else 0.0

    for month in months:
        _checkpoint, marker_path, _lineage, _quality = _month_paths(month)
        if not marker_path.exists():
            completion_markers_present = False
            break

    rows_enriched = int(monthly_df["rows"].sum()) if not monthly_df.empty else 0
    checkpoint_reuse_months = int(monthly_df["reused_checkpoint"].sum()) if not monthly_df.empty else 0

    summary = {
        "months_enriched": int(len(monthly_df)),
        "rows_enriched": rows_enriched,
        "historical_start": months[0],
        "historical_end": months[-1],
        "duplicate_canonical_keys_total": duplicates_total,
        "row_count_preservation_all_months": row_count_preserved_all,
        "base_column_preservation_all_months": bool(base_preserved_all and no_non_ts_mutation and no_ts_mutation),
        "base_value_mutations_total": base_value_mutations_total,
        "state_holiday_validation_all_months": bool(monthly_df["state_holiday_validation"].all()) if not monthly_df.empty else False,
        "dst_validation_all_months": bool(monthly_df["dst_handling_valid"].all()) if not monthly_df.empty else False,
        "cross_state_contamination_count_total": cross_state_contamination_count_total,
        "lineage_completeness_pct": float(lineage_completeness_pct),
        "regional_calendar_coverage_pct": float(regional_calendar_coverage_pct),
        "quality_validation_pass_all_months": bool(monthly_df["pass_all"].all()) if not monthly_df.empty else False,
        "checkpoint_reuse_months": checkpoint_reuse_months,
        "checkpoint_reuse_result": {
            "reused_months": checkpoint_reuse_months,
            "newly_processed_months": int(len(monthly_df) - checkpoint_reuse_months),
            "resume_supported": True,
        },
        "disk_usage_bytes_output_store": _dir_size_bytes(OUTPUT_ROOT),
        "runtime_seconds_total": float(elapsed_total),
        "runtime_seconds_avg_per_month": float(elapsed_total / len(monthly_df)) if len(monthly_df) > 0 else 0.0,
        "all_completion_markers_present": completion_markers_present,
        "tests_passed_failed": {
            "passed_months": int(monthly_df["pass_all"].sum()) if not monthly_df.empty else 0,
            "failed_months": int((~monthly_df["pass_all"]).sum()) if not monthly_df.empty else 0,
        },
        "generated_at_utc": _utc_now_iso(),
        "output_root": str(OUTPUT_ROOT),
    }

    _write_full_history_reports(months, monthly_rows, summary)

    state.blockers = "None"
    _progress_update(state, event="integration completed", confidence="High")

    return summary


def main() -> None:
    summary = integrate_full_history()
    print(_json_dump_text(summary))


if __name__ == "__main__":
    main()
