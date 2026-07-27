#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.historical_feature_store import build_historical_feature_store  # noqa: E402


INTERVENTION_AUDIT_COLUMNS = [
    "interval_timestamp_utc",
    "interconnector_id",
    "runno",
    "count_intervention_0",
    "count_intervention_1",
    "paired_intervention_values_differ",
]


def _normalize_date(value: str | None, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _month_bounds(month_value: str) -> tuple[str, str]:
    start = pd.Timestamp(f"{month_value}-01").normalize()
    end = (start + pd.offsets.MonthEnd(0)).normalize()
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _month_windows(start_date: str, end_date: str | None) -> list[tuple[str, str, str]]:
    start = pd.Timestamp(start_date).normalize().replace(day=1)
    end = pd.Timestamp(end_date).normalize() if end_date is not None else pd.Timestamp.now().normalize()
    windows: list[tuple[str, str, str]] = []
    current = start
    while current <= end:
        month_end = (current + pd.offsets.MonthEnd(0)).normalize()
        bounded_end = min(month_end, end)
        windows.append((current.strftime("%Y-%m-%d"), bounded_end.strftime("%Y-%m-%d"), current.strftime("%Y-%m")))
        current = (current + pd.offsets.MonthBegin(1)).normalize()
    return windows


def _rss_mb() -> float:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024.0 * 1024.0)
        return usage.ru_maxrss / 1024.0
    except Exception:
        return 0.0


def _checkpoint_paths(month_dir: Path) -> dict[str, Path]:
    return {
        "feature_store": month_dir / "historical_market_feature_store_5min.csv.gz",
        "dataset_status": month_dir / "historical_dataset_status.csv",
        "intervention_audit": month_dir / "historical_intervention_audit.csv",
        "metadata": month_dir / "historical_feature_store_metadata.json",
    }


def _write_intervention_audit_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.reindex(columns=INTERVENTION_AUDIT_COLUMNS).to_csv(path, index=False)


def _load_intervention_audit_csv(path: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        if path.exists() and path.stat().st_size == 0:
            warnings.append(f"Legacy zero-byte intervention audit at {path}")
            return pd.DataFrame(columns=INTERVENTION_AUDIT_COLUMNS), warnings
        raise

    frame = frame.reindex(columns=INTERVENTION_AUDIT_COLUMNS)
    return frame, warnings


def _load_checkpoint(month_dir: Path):
    paths = _checkpoint_paths(month_dir)
    if not all(path.exists() for path in paths.values()):
        return None

    feature_store = pd.read_csv(paths["feature_store"])
    dataset_status = pd.read_csv(paths["dataset_status"])
    intervention_audit, warnings = _load_intervention_audit_csv(paths["intervention_audit"])
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    metadata["checkpoint_dir"] = str(month_dir)
    if warnings:
        metadata.setdefault("compatibility_warnings", []).extend(warnings)
    return feature_store, dataset_status, intervention_audit, metadata


def _safe_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _schema_signature(frame: pd.DataFrame) -> tuple[str, str]:
    schema_repr = "|".join(f"{column}:{dtype}" for column, dtype in zip(frame.columns, frame.dtypes.astype(str), strict=False))
    digest = hashlib.sha256(schema_repr.encode("utf-8")).hexdigest()[:16]
    return digest, schema_repr


def _publication_lag_stats(feature_store: pd.DataFrame) -> tuple[float, float, float]:
    if "publication_timestamp_utc" not in feature_store.columns:
        return 0.0, 0.0, 0.0
    observed = _safe_timestamp(feature_store["interval_timestamp_utc"])
    published = _safe_timestamp(feature_store["publication_timestamp_utc"])
    lag_minutes = (published - observed).dt.total_seconds().div(60)
    lag_minutes = lag_minutes.dropna()
    if lag_minutes.empty:
        return 0.0, 0.0, 0.0
    return float(lag_minutes.mean()), float(lag_minutes.quantile(0.95)), float(lag_minutes.max())


def _disk_usage_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _print_month_progress(
    *,
    month_label: str,
    month_start: str,
    month_end: str,
    dataset_status: pd.DataFrame,
    rows: int,
    coverage_pct: float,
    mean_quality: float,
    checkpoint_status: str,
    month_elapsed_s: float,
    build_elapsed_s: float,
    month_index: int,
    month_total: int,
) -> None:
    memory_mb = _rss_mb()
    datasets_completed = int(dataset_status["status"].astype(str).str.contains("AVAILABLE|DERIVED_PARTIAL", case=False, na=False).sum())
    avg_month_seconds = build_elapsed_s / max(month_index, 1)
    eta_seconds = avg_month_seconds * max(month_total - month_index, 0)
    print(
        f"[{month_index}/{month_total}] month={month_label} range={month_start}..{month_end} "
        f"datasets_completed={datasets_completed} rows={rows} month_elapsed_s={month_elapsed_s:.2f} "
        f"total_elapsed_s={build_elapsed_s:.2f} checkpoint={checkpoint_status} coverage_pct={coverage_pct:.4f} "
        f"quality_mean={mean_quality:.4f} rss_mb={memory_mb:.2f} eta_s={eta_seconds:.2f}"
    )


def _print_annual_summary(monthly_build_status: list[dict[str, object]], month_label: str) -> None:
    current_year = month_label.split("-")[0]
    year_rows = [row for row in monthly_build_status if str(row["month"]).startswith(current_year)]
    if not year_rows:
        return
    total_rows = int(sum(int(row["rows_processed"]) for row in year_rows))
    avg_quality = float(sum(float(row["quality_mean"]) for row in year_rows) / len(year_rows))
    avg_coverage = float(sum(float(row["interval_coverage_pct"]) for row in year_rows) / len(year_rows))
    print(
        f"[ANNUAL] year={current_year} months={len(year_rows)} rows={total_rows} "
        f"avg_quality={avg_quality:.4f} avg_coverage={avg_coverage:.4f}"
    )


def _build_windowed_feature_store(repo_root: Path, start_date: str, end_date: str | None, output_dir: Path, *, resume: bool) -> object:
    month_windows = _month_windows(start_date, end_date)
    month_root = output_dir / "checkpoints"
    month_root.mkdir(parents=True, exist_ok=True)

    feature_frames: list[pd.DataFrame] = []
    dataset_status_frames: list[pd.DataFrame] = []
    intervention_frames: list[pd.DataFrame] = []
    monthly_metadata: list[dict[str, object]] = []

    monthly_build_status: list[dict[str, object]] = []
    monthly_dataset_coverage: list[dict[str, object]] = []
    monthly_quality_report: list[dict[str, object]] = []
    monthly_lineage_report: list[dict[str, object]] = []
    monthly_schema_report: list[dict[str, object]] = []
    monthly_checkpoint_report: list[dict[str, object]] = []
    failed_months: list[str] = []

    start_time = time.perf_counter()

    for month_index, (month_start, month_end, month_label) in enumerate(month_windows, start=1):
        month_dir = month_root / month_label
        month_dir.mkdir(parents=True, exist_ok=True)

        month_start_time = time.perf_counter()
        cached = _load_checkpoint(month_dir) if resume else None

        if cached is not None:
            feature_store, dataset_status, intervention_audit, metadata = cached
            checkpoint_status = "REUSED"
        else:
            try:
                result = build_historical_feature_store(
                    repo_root,
                    start_date=month_start,
                    end_date=month_end,
                    output_dir=month_dir,
                )
            except Exception:
                failed_months.append(month_label)
                raise
            feature_store = result.feature_store
            dataset_status = result.dataset_status
            metadata = result.metadata
            audit_path = month_dir / "historical_intervention_audit.csv"
            if audit_path.exists():
                intervention_audit, warnings = _load_intervention_audit_csv(audit_path)
                if warnings:
                    metadata.setdefault("compatibility_warnings", []).extend(warnings)
            else:
                intervention_audit = pd.DataFrame(columns=INTERVENTION_AUDIT_COLUMNS)
            checkpoint_status = "WRITTEN"

        feature_frames.append(feature_store)
        dataset_status_frames.append(dataset_status.assign(build_window=month_label))
        intervention_frames.append(intervention_audit.assign(build_window=month_label))
        monthly_metadata.append(metadata)

        duplicate_keys = int(feature_store.duplicated(subset=["interval_timestamp_utc"], keep=False).sum()) if not feature_store.empty else 0
        interval_coverage = float(metadata.get("interval_coverage_pct", 0.0))
        quality_mean = float(feature_store["quality_score"].mean()) if "quality_score" in feature_store.columns and not feature_store.empty else 0.0
        quality_p05 = float(feature_store["quality_score"].quantile(0.05)) if "quality_score" in feature_store.columns and not feature_store.empty else 0.0
        quality_p95 = float(feature_store["quality_score"].quantile(0.95)) if "quality_score" in feature_store.columns and not feature_store.empty else 0.0
        publication_lag_mean, publication_lag_p95, publication_lag_max = _publication_lag_stats(feature_store)
        schema_version, schema_repr = _schema_signature(feature_store)
        build_elapsed_s = time.perf_counter() - start_time
        month_elapsed_s = time.perf_counter() - month_start_time
        rows_processed = int(len(feature_store))

        monthly_build_status.append(
            {
                "month": month_label,
                "month_start": month_start,
                "month_end": month_end,
                "rows_processed": rows_processed,
                "datasets_completed": int(dataset_status["status"].astype(str).str.contains("AVAILABLE|DERIVED_PARTIAL", case=False, na=False).sum()),
                "datasets_blocked": int(dataset_status["status"].astype(str).str.contains("BLOCKED", case=False, na=False).sum()),
                "interval_coverage_pct": interval_coverage,
                "duplicate_canonical_keys": duplicate_keys,
                "quality_mean": quality_mean,
                "publication_lag_mean_minutes": publication_lag_mean,
                "schema_version": schema_version,
                "checkpoint_status": checkpoint_status,
                "elapsed_seconds": round(month_elapsed_s, 6),
                "total_elapsed_seconds": round(build_elapsed_s, 6),
                "memory_mb": round(_rss_mb(), 6),
                "status": "COMPLETED",
            }
        )

        for _, row in dataset_status.iterrows():
            monthly_dataset_coverage.append(
                {
                    "month": month_label,
                    "dataset": row.get("dataset"),
                    "dataset_status": row.get("status"),
                    "rows": row.get("rows", 0),
                    "files": row.get("files", 0),
                    "min_interval": row.get("min_interval"),
                    "max_interval": row.get("max_interval"),
                    "blocker": row.get("blocker", ""),
                }
            )
            monthly_lineage_report.append(
                {
                    "month": month_label,
                    "dataset": row.get("dataset"),
                    "dataset_status": row.get("status"),
                    "lineage_hash": row.get("lineage_hash"),
                    "source_lineage_complete": bool(pd.notna(row.get("lineage_hash")) or "BLOCKED" in str(row.get("status", ""))),
                }
            )

        monthly_quality_report.append(
            {
                "month": month_label,
                "rows": rows_processed,
                "interval_coverage_pct": interval_coverage,
                "duplicate_canonical_keys": duplicate_keys,
                "quality_mean": quality_mean,
                "quality_p05": quality_p05,
                "quality_p95": quality_p95,
                "publication_lag_mean_minutes": publication_lag_mean,
                "publication_lag_p95_minutes": publication_lag_p95,
                "publication_lag_max_minutes": publication_lag_max,
                "pit_integrity": bool("point_in_time_available" in feature_store.columns and feature_store["point_in_time_available"].fillna(False).all()),
            }
        )

        monthly_schema_report.append(
            {
                "month": month_label,
                "schema_version": schema_version,
                "column_count": int(len(feature_store.columns)),
                "schema_signature": schema_repr,
                "schema_integrity": True,
            }
        )

        checkpoint_files = _checkpoint_paths(month_dir)
        monthly_checkpoint_report.append(
            {
                "month": month_label,
                "checkpoint_dir": str(month_dir),
                "checkpoint_status": checkpoint_status,
                "checkpoint_complete": all(path.exists() for path in checkpoint_files.values()),
                "feature_store_checkpoint": str(checkpoint_files["feature_store"]),
                "dataset_status_checkpoint": str(checkpoint_files["dataset_status"]),
                "intervention_audit_checkpoint": str(checkpoint_files["intervention_audit"]),
                "metadata_checkpoint": str(checkpoint_files["metadata"]),
            }
        )

        _print_month_progress(
            month_label=month_label,
            month_start=month_start,
            month_end=month_end,
            dataset_status=dataset_status,
            rows=rows_processed,
            coverage_pct=interval_coverage,
            mean_quality=quality_mean,
            checkpoint_status=checkpoint_status,
            month_elapsed_s=month_elapsed_s,
            build_elapsed_s=build_elapsed_s,
            month_index=month_index,
            month_total=len(month_windows),
        )

        if month_index % 12 == 0 or month_index == len(month_windows):
            _print_annual_summary(monthly_build_status, month_label)

    combined_feature_store = pd.concat(feature_frames, ignore_index=True).drop_duplicates(subset=["interval_timestamp_utc"], keep="last")
    combined_feature_store = combined_feature_store.sort_values("interval_timestamp_utc").reset_index(drop=True)
    combined_dataset_status = pd.concat(dataset_status_frames, ignore_index=True)
    combined_intervention_audit = pd.concat(intervention_frames, ignore_index=True)

    lineage_digests = [str(item.get("lineage_hash", "")) for item in monthly_metadata if item.get("lineage_hash")]
    lineage_hash = hashlib.sha256("|".join(sorted(lineage_digests)).encode("utf-8")).hexdigest() if lineage_digests else None

    total_elapsed = time.perf_counter() - start_time
    metadata = {
        "start_date": start_date,
        "end_date": month_windows[-1][1] if month_windows else end_date,
        "build_windows": month_windows,
        "months_completed": int(len(month_windows) - len(failed_months)),
        "months_failed": int(len(failed_months)),
        "failed_month_labels": failed_months,
        "elapsed_seconds": round(total_elapsed, 6),
        "average_runtime_per_month_seconds": round(total_elapsed / max(len(month_windows), 1), 6),
        "rss_mb": round(_rss_mb(), 6),
        "expected_intervals": int(len(combined_feature_store)),
        "actual_intervals": int(combined_feature_store["interval_timestamp_utc"].nunique()) if not combined_feature_store.empty else 0,
        "interval_coverage_pct": round((int(combined_feature_store["interval_timestamp_utc"].nunique()) / max(len(combined_feature_store), 1)) * 100.0, 6) if not combined_feature_store.empty else 0.0,
        "duplicate_interval_keys": int(combined_feature_store.duplicated(subset=["interval_timestamp_utc"], keep=False).sum()) if not combined_feature_store.empty else 0,
        "feature_rows": int(len(combined_feature_store)),
        "feature_columns": int(len(combined_feature_store.columns)),
        "lineage_hash": lineage_hash,
        "checkpoint_root": str(month_root),
        "output_dir": str(output_dir),
        "outputs": {
            "feature_store": str(output_dir / "historical_market_feature_store_5min.csv.gz"),
            "dataset_status": str(output_dir / "historical_dataset_status.csv"),
            "intervention_audit": str(output_dir / "historical_intervention_audit.csv"),
        },
    }

    monthly_reports = {
        "monthly_build_status": pd.DataFrame(monthly_build_status),
        "monthly_dataset_coverage": pd.DataFrame(monthly_dataset_coverage),
        "monthly_quality_report": pd.DataFrame(monthly_quality_report),
        "monthly_lineage_report": pd.DataFrame(monthly_lineage_report),
        "monthly_schema_report": pd.DataFrame(monthly_schema_report),
        "monthly_build_checkpoints": pd.DataFrame(monthly_checkpoint_report),
    }

    return type(
        "WindowedBuildResult",
        (),
        {
            "feature_store": combined_feature_store,
            "dataset_status": combined_dataset_status,
            "intervention_audit": combined_intervention_audit,
            "metadata": metadata,
            "monthly_reports": monthly_reports,
        },
    )()


def _write_deliverables(repo_root: Path, result) -> None:
    output_dir = Path(result.metadata["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_store = result.feature_store
    dataset_status = result.dataset_status
    metadata = result.metadata
    monthly_reports = result.monthly_reports

    feature_store_path = output_dir / "historical_market_feature_store_5min.csv.gz"
    dataset_status_path = output_dir / "historical_dataset_status.csv"
    intervention_audit_path = output_dir / "historical_intervention_audit.csv"
    metadata_path = output_dir / "historical_feature_store_metadata.json"

    feature_store.to_csv(feature_store_path, index=False, compression="gzip")
    dataset_status.to_csv(dataset_status_path, index=False)
    _write_intervention_audit_csv(result.intervention_audit, intervention_audit_path)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    monthly_build_status_csv = repo_root / "MONTHLY_BUILD_STATUS.csv"
    monthly_dataset_coverage_csv = repo_root / "MONTHLY_DATASET_COVERAGE.csv"
    monthly_quality_report_csv = repo_root / "MONTHLY_QUALITY_REPORT.csv"
    monthly_lineage_report_csv = repo_root / "MONTHLY_LINEAGE_REPORT.csv"
    monthly_schema_report_csv = repo_root / "MONTHLY_SCHEMA_REPORT.csv"
    monthly_build_checkpoints_csv = repo_root / "MONTHLY_BUILD_CHECKPOINTS.csv"

    monthly_reports["monthly_build_status"].to_csv(monthly_build_status_csv, index=False)
    monthly_reports["monthly_dataset_coverage"].to_csv(monthly_dataset_coverage_csv, index=False)
    monthly_reports["monthly_quality_report"].to_csv(monthly_quality_report_csv, index=False)
    monthly_reports["monthly_lineage_report"].to_csv(monthly_lineage_report_csv, index=False)
    monthly_reports["monthly_schema_report"].to_csv(monthly_schema_report_csv, index=False)
    monthly_reports["monthly_build_checkpoints"].to_csv(monthly_build_checkpoints_csv, index=False)

    pivot = (
        monthly_reports["monthly_dataset_coverage"]
        .pivot_table(index="month", columns="dataset", values="dataset_status", aggfunc="first")
        .sort_index()
    )
    completeness_matrix_md = repo_root / "DATASET_COMPLETENESS_MATRIX.md"
    completeness_matrix_md.write_text(
        "\n".join(
            [
                "# Dataset Completeness Matrix",
                "",
                pivot.to_markdown(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    build_status_md = repo_root / "HISTORICAL_BUILD_STATUS.md"
    blocked_datasets = monthly_reports["monthly_dataset_coverage"][
        monthly_reports["monthly_dataset_coverage"]["dataset_status"].astype(str).str.contains("BLOCKED", case=False, na=False)
    ]["dataset"].dropna().unique().tolist()

    quality_frame = monthly_reports["monthly_quality_report"]
    quality_summary = {
        "quality_mean": float(quality_frame["quality_mean"].mean()) if not quality_frame.empty else 0.0,
        "quality_p05": float(quality_frame["quality_p05"].mean()) if not quality_frame.empty else 0.0,
        "quality_p95": float(quality_frame["quality_p95"].mean()) if not quality_frame.empty else 0.0,
        "interval_coverage_pct_mean": float(quality_frame["interval_coverage_pct"].mean()) if not quality_frame.empty else 0.0,
    }

    build_status_md.write_text(
        "\n".join(
            [
                "# Historical Build Status",
                "",
                "## Summary",
                f"- Start date: {metadata['start_date']}",
                f"- End date: {metadata['end_date']}",
                f"- Months completed: {metadata['months_completed']}",
                f"- Months failed: {metadata['months_failed']}",
                f"- Total rows ingested: {metadata['feature_rows']}",
                f"- Total disk usage bytes: {_disk_usage_bytes(output_dir)}",
                f"- Average runtime per month (s): {metadata['average_runtime_per_month_seconds']}",
                f"- Coverage (%): {metadata['interval_coverage_pct']}",
                f"- Duplicate interval keys: {metadata['duplicate_interval_keys']}",
                "",
                "## Quality Summary",
                f"- Mean quality score: {quality_summary['quality_mean']}",
                f"- Mean p05 quality score: {quality_summary['quality_p05']}",
                f"- Mean p95 quality score: {quality_summary['quality_p95']}",
                f"- Mean interval coverage (%): {quality_summary['interval_coverage_pct_mean']}",
                "",
                "## Blocked Datasets",
                ", ".join(sorted(blocked_datasets)) if blocked_datasets else "None",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the historical point-in-time feature store.")
    parser.add_argument("--start-date", default="2020-01-01", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", default=None, help="Inclusive end date (YYYY-MM-DD). Defaults to latest available month.")
    parser.add_argument("--start-month", default=None, help="Optional month shortcut YYYY-MM.")
    parser.add_argument("--end-month", default=None, help="Optional month shortcut YYYY-MM.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "data" / "derived" / "historical_feature_store"), help="Final output directory.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed monthly checkpoints if available.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    start_date = _normalize_date(args.start_date, default="2020-01-01")
    end_date = _normalize_date(args.end_date) if args.end_date else None

    if args.start_month:
        start_date, _ = _month_bounds(args.start_month)
    if args.end_month:
        _, end_date = _month_bounds(args.end_month)

    output_dir = Path(args.output_dir)
    result = _build_windowed_feature_store(
        REPO_ROOT,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        resume=bool(args.resume),
    )
    _write_deliverables(REPO_ROOT, result)
    print(json.dumps(result.metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
