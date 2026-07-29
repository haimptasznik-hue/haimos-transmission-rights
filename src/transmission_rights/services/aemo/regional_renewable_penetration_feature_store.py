from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .dataset_library import normalize_aemo_timestamp_series


OUTPUT_COLUMNS = [
    "interval_timestamp_utc",
    "region",
    "total_positive_generation_mw",
    "renewable_positive_generation_mw",
    "matched_positive_generation_mw",
    "unmatched_positive_generation_mw",
    "active_unit_count",
    "renewable_active_unit_count",
    "matched_active_unit_count",
    "unmatched_active_unit_count",
    "renewable_penetration_pct",
    "renewable_penetration_known_pct",
    "matched_generation_share_pct",
    "renewable_unit_share_pct",
    "quality_score",
    "point_in_time_available",
    "source_month",
    "source_file",
]

CANONICAL_HASH_ALGORITHM = "SHA-256"
CANONICAL_HASH_CONTRACT_VERSION = 1
CANONICAL_HASH_SCOPE = "renewable_penetration_features"
CANONICAL_HASH_SORT_COLUMNS = ["interval_timestamp_utc", "region"]


def canonical_hash_contract_metadata() -> dict[str, object]:
    return {
        "algorithm": CANONICAL_HASH_ALGORITHM,
        "contract_version": CANONICAL_HASH_CONTRACT_VERSION,
        "scope": CANONICAL_HASH_SCOPE,
        "sort_columns": list(CANONICAL_HASH_SORT_COLUMNS),
        "column_order": list(OUTPUT_COLUMNS),
        "normalization": {
            "timestamp": "utc_iso8601_z",
            "null_representation": "pandas_default_csv",
            "source_file": "basename_only",
            "encoding": "utf-8",
            "line_terminator": "lf",
            "include_index": False,
            "float_format": "pandas_default_csv",
        },
    }


def _normalize_source_file_basename(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = text.replace("\\", "/")
    return normalized.split("/")[-1]


def canonicalize_feature_rows_for_hash(frame: pd.DataFrame) -> pd.DataFrame:
    canonical = frame.copy()
    for column in OUTPUT_COLUMNS:
        if column not in canonical.columns:
            canonical[column] = pd.NA
    canonical = canonical[OUTPUT_COLUMNS]

    canonical["interval_timestamp_utc"] = pd.to_datetime(
        canonical["interval_timestamp_utc"], errors="coerce", utc=True
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical["source_file"] = canonical["source_file"].map(_normalize_source_file_basename)
    canonical = canonical.sort_values(CANONICAL_HASH_SORT_COLUMNS, kind="mergesort").reset_index(drop=True)
    return canonical


def compute_feature_rows_canonical_hash_sha256(frame: pd.DataFrame) -> str:
    canonical = canonicalize_feature_rows_for_hash(frame)
    canonical_csv = canonical.to_csv(index=False, lineterminator="\n")
    digest = hashlib.sha256()
    digest.update(canonical_csv.encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True)
class RegionalRenewablePenetrationResult:
    feature_store: pd.DataFrame
    unmatched_observations: pd.DataFrame
    monthly_status: pd.DataFrame
    metadata: dict[str, object]


def _bool_series(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin(["true", "1", "t", "yes", "y"])


def _month_token_from_path(path: Path) -> str:
    match = re.search(r"_(\d{6})010000\.dispatch_unit_scada\.csv\.gz$", path.name)
    if not match:
        raise ValueError(f"Unable to extract month token from {path.name}")
    return match.group(1)


def _month_label_from_path(path: Path) -> str:
    token = _month_token_from_path(path)
    return f"{token[:4]}-{token[4:6]}"


def _cache_paths(repo_root: Path, start_month: str | None = None, end_month: str | None = None) -> list[Path]:
    cache_dir = repo_root / "data" / "raw" / "aemo" / "mmsdm_dispatch_unit_scada" / ".cache"
    if not cache_dir.exists():
        return []

    files = sorted(cache_dir.glob("PUBLIC_DVD_DISPATCH_UNIT_SCADA_*.dispatch_unit_scada.csv.gz"))
    if start_month is None and end_month is None:
        return files

    start_token = start_month.replace("-", "") if start_month else None
    end_token = end_month.replace("-", "") if end_month else None
    selected: list[Path] = []
    for file_path in files:
        token = _month_token_from_path(file_path)
        if start_token is not None and token < start_token:
            continue
        if end_token is not None and token > end_token:
            continue
        selected.append(file_path)
    return selected


def _hash_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if not path.exists():
            continue
        digest.update(str(path).encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("utf-8"))
        digest.update(str(path.stat().st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()


def _load_generator_master(repo_root: Path) -> pd.DataFrame:
    master_path = repo_root / "data" / "derived" / "generator_master_v1" / "generator_master_v1.csv"
    if not master_path.exists():
        raise FileNotFoundError(f"Generator master not found: {master_path}")

    frame = pd.read_csv(
        master_path,
        low_memory=False,
        dtype={
            "DUID": "string",
            "snapshot_date": "string",
            "snapshot_version": "string",
            "authoritative_source": "string",
            "classification_confidence": "string",
            "quality_status": "string",
            "schema_version": "string",
            "generator_master_version": "string",
            "pit_scope": "string",
            "effective_from": "string",
            "effective_to": "string",
            "fuel_type": "string",
            "technology_type": "string",
            "dispatch_classification": "string",
            "region": "string",
        },
    )
    frame["DUID"] = frame["DUID"].astype(str).str.strip()
    frame["region"] = frame["region"].astype(str).str.upper().str.strip()
    frame["renewable_flag"] = _bool_series(frame["renewable_flag"]) if "renewable_flag" in frame.columns else False
    frame["registered_capacity_mw"] = pd.to_numeric(frame.get("registered_capacity_mw"), errors="coerce")
    return frame


def _load_scada_month(file_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(file_path, low_memory=False, dtype={"DUID": "string", "REGIONID": "string"})
    required = {"SETTLEMENTDATE", "DUID", "SCADA_MW"}
    if not required.issubset(frame.columns):
        return pd.DataFrame(columns=["SETTLEMENTDATE", "DUID", "SCADA_MW", "REGIONID", "SOURCE_FILE"])

    output = frame[["SETTLEMENTDATE", "DUID", "SCADA_MW", *( ["REGIONID"] if "REGIONID" in frame.columns else [] )]].copy()
    output["DUID"] = output["DUID"].astype(str).str.strip()
    output["SCADA_MW"] = pd.to_numeric(output["SCADA_MW"], errors="coerce")
    output = output[output["SCADA_MW"].notna()].copy()
    if "REGIONID" not in output.columns:
        output["REGIONID"] = pd.NA
    output["SOURCE_FILE"] = str(file_path)
    output["interval_timestamp_utc"] = normalize_aemo_timestamp_series(
        output["SETTLEMENTDATE"],
        source_timezone="Australia/Brisbane",
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    output = output[output["interval_timestamp_utc"].notna()].copy()
    return output.reset_index(drop=True)


def _checkpoint_paths(month_dir: Path) -> dict[str, Path]:
    return {
        "feature_store": month_dir / "regional_renewable_penetration_5min.csv.gz",
        "unmatched": month_dir / "unmatched_duid_observations.csv.gz",
        "metadata": month_dir / "monthly_metadata.json",
        "marker": month_dir / ".complete.json",
    }


def _load_checkpoint(month_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]] | None:
    paths = _checkpoint_paths(month_dir)
    if not paths["feature_store"].exists() or not paths["metadata"].exists() or not paths["marker"].exists():
        return None

    feature_store = pd.read_csv(paths["feature_store"], low_memory=False)
    unmatched = pd.read_csv(paths["unmatched"], low_memory=False) if paths["unmatched"].exists() else pd.DataFrame()
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    metadata["checkpoint_dir"] = str(month_dir)
    return feature_store, unmatched, metadata


def _quality_score(frame: pd.DataFrame, feature_columns: list[str]) -> pd.Series:
    if not feature_columns:
        return pd.Series(0.0, index=frame.index, dtype=float, name="quality_score")
    coverage = frame[feature_columns].notna().sum(axis=1)
    return (coverage / float(len(feature_columns)) * 100.0).round(4).rename("quality_score")


def _aggregate_month(
    *,
    month_label: str,
    scada: pd.DataFrame,
    generator_master: pd.DataFrame,
    source_file: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    if scada.empty:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        return empty, pd.DataFrame(), {
            "month": month_label,
            "rows": 0,
            "intervals": 0,
            "regions": 0,
            "duids": 0,
            "renewable_penetration_mean_pct": 0.0,
            "generator_master_match_rate_pct": 0.0,
            "source_file": str(source_file),
            "unmatched_duid_count": 0,
        }

    master = generator_master[["DUID", "region", "renewable_flag", "fuel_type", "technology_type", "registered_capacity_mw"]].copy()
    master = master.rename(columns={"region": "master_region"})

    merged = scada.merge(master, on="DUID", how="left", indicator="generator_master_match")
    merged["generator_master_match"] = merged["generator_master_match"].eq("both")
    merged["region"] = merged["REGIONID"].where(
        merged["REGIONID"].notna() & (merged["REGIONID"].astype(str).str.strip() != ""),
        merged["master_region"],
    )
    merged["region"] = merged["region"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
    merged["renewable_flag"] = merged["renewable_flag"].fillna(False).astype(bool)
    merged["positive_scada_mw"] = merged["SCADA_MW"].clip(lower=0.0)
    merged["positive_renewable_mw"] = merged["positive_scada_mw"].where(merged["renewable_flag"], 0.0)
    merged["positive_matched_mw"] = merged["positive_scada_mw"].where(merged["generator_master_match"], 0.0)
    merged["positive_unmatched_mw"] = merged["positive_scada_mw"].where(~merged["generator_master_match"], 0.0)
    merged["active_unit_flag"] = merged["SCADA_MW"].fillna(0.0) > 0.0
    merged["renewable_active_unit_flag"] = merged["active_unit_flag"] & merged["renewable_flag"]
    merged["matched_active_unit_flag"] = merged["active_unit_flag"] & merged["generator_master_match"]
    merged["unmatched_active_unit_flag"] = merged["active_unit_flag"] & ~merged["generator_master_match"]

    unmatched = merged.loc[~merged["generator_master_match"], ["interval_timestamp_utc", "DUID", "SCADA_MW", "region", "SOURCE_FILE"]].copy()
    if not unmatched.empty:
        unmatched["source_month"] = month_label
        unmatched["renewable_flag"] = False
        unmatched["generator_master_match"] = False
        unmatched = unmatched.sort_values(["interval_timestamp_utc", "DUID"]).reset_index(drop=True)
    else:
        unmatched = pd.DataFrame(columns=["interval_timestamp_utc", "DUID", "SCADA_MW", "region", "SOURCE_FILE", "source_month", "renewable_flag", "generator_master_match"])

    agg = (
        merged.groupby(["interval_timestamp_utc", "region"], as_index=False)
        .agg(
            total_positive_generation_mw=("positive_scada_mw", "sum"),
            renewable_positive_generation_mw=("positive_renewable_mw", "sum"),
            matched_positive_generation_mw=("positive_matched_mw", "sum"),
            unmatched_positive_generation_mw=("positive_unmatched_mw", "sum"),
            active_unit_count=("active_unit_flag", "sum"),
            renewable_active_unit_count=("renewable_active_unit_flag", "sum"),
            matched_active_unit_count=("matched_active_unit_flag", "sum"),
            unmatched_active_unit_count=("unmatched_active_unit_flag", "sum"),
            source_duid_count=("DUID", "nunique"),
        )
        .reset_index(drop=True)
    )

    agg["renewable_penetration_pct"] = agg.apply(
        lambda row: round(row["renewable_positive_generation_mw"] / row["total_positive_generation_mw"] * 100.0, 6)
        if row["total_positive_generation_mw"] > 0 else pd.NA,
        axis=1,
    )
    agg["renewable_penetration_known_pct"] = agg.apply(
        lambda row: round(row["renewable_positive_generation_mw"] / row["matched_positive_generation_mw"] * 100.0, 6)
        if row["matched_positive_generation_mw"] > 0 else pd.NA,
        axis=1,
    )
    agg["matched_generation_share_pct"] = agg.apply(
        lambda row: round(row["matched_positive_generation_mw"] / row["total_positive_generation_mw"] * 100.0, 6)
        if row["total_positive_generation_mw"] > 0 else pd.NA,
        axis=1,
    )
    agg["renewable_unit_share_pct"] = agg.apply(
        lambda row: round(row["renewable_active_unit_count"] / row["active_unit_count"] * 100.0, 6)
        if row["active_unit_count"] > 0 else pd.NA,
        axis=1,
    )

    agg["quality_score"] = _quality_score(
        agg,
        [
            "total_positive_generation_mw",
            "renewable_positive_generation_mw",
            "matched_positive_generation_mw",
            "unmatched_positive_generation_mw",
            "active_unit_count",
            "renewable_active_unit_count",
            "matched_active_unit_count",
            "unmatched_active_unit_count",
            "renewable_penetration_pct",
            "renewable_penetration_known_pct",
            "matched_generation_share_pct",
            "renewable_unit_share_pct",
        ],
    )
    agg["point_in_time_available"] = True
    agg["source_month"] = month_label
    agg["source_file"] = str(source_file)
    agg = agg[OUTPUT_COLUMNS]

    metadata = {
        "month": month_label,
        "rows": int(len(agg)),
        "intervals": int(agg["interval_timestamp_utc"].nunique()) if not agg.empty else 0,
        "regions": int(agg["region"].nunique()) if not agg.empty else 0,
        "duids": int(merged["DUID"].nunique()) if not merged.empty else 0,
        "renewable_penetration_mean_pct": float(pd.to_numeric(agg["renewable_penetration_pct"], errors="coerce").mean()) if not agg.empty else 0.0,
        "generator_master_match_rate_pct": round(float(merged["generator_master_match"].mean()) * 100.0, 6) if not merged.empty else 0.0,
        "source_file": str(source_file),
        "source_rows": int(len(merged)),
        "unmatched_duid_count": int((~merged["generator_master_match"]).sum()),
    }
    return agg, unmatched, metadata


def build_regional_renewable_penetration_feature_store(
    repo_root: Path,
    output_dir: Path,
    *,
    start_month: str | None = None,
    end_month: str | None = None,
    resume: bool = True,
) -> RegionalRenewablePenetrationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_root = output_dir / "checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)

    generator_master = _load_generator_master(repo_root)
    scada_files = _cache_paths(repo_root, start_month=start_month, end_month=end_month)
    if not scada_files:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        metadata = {
            "start_month": start_month,
            "end_month": end_month,
            "months": 0,
            "rows": 0,
            "regions": 0,
            "duids": 0,
            "checkpoint_root": str(checkpoint_root),
            "generator_master_path": str(repo_root / "data" / "derived" / "generator_master_v1" / "generator_master_v1.csv"),
            "source_hash": _hash_paths([]),
        }
        return RegionalRenewablePenetrationResult(empty, pd.DataFrame(), pd.DataFrame(), metadata)

    monthly_rows: list[pd.DataFrame] = []
    monthly_unmatched: list[pd.DataFrame] = []
    monthly_status_rows: list[dict[str, object]] = []
    all_source_paths: list[Path] = [repo_root / "data" / "derived" / "generator_master_v1" / "generator_master_v1.csv"]

    for source_file in scada_files:
        month_label = _month_label_from_path(source_file)
        month_dir = checkpoint_root / month_label
        month_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = _load_checkpoint(month_dir) if resume else None

        if checkpoint is not None:
            month_frame, unmatched_frame, month_metadata = checkpoint
            checkpoint_status = "REUSED"
        else:
            scada = _load_scada_month(source_file)
            month_frame, unmatched_frame, month_metadata = _aggregate_month(
                month_label=month_label,
                scada=scada,
                generator_master=generator_master,
                source_file=source_file,
            )
            month_frame.to_csv(month_dir / "regional_renewable_penetration_5min.csv.gz", index=False, compression="gzip")
            unmatched_frame.to_csv(month_dir / "unmatched_duid_observations.csv.gz", index=False, compression="gzip")
            (month_dir / "monthly_metadata.json").write_text(
                json.dumps(month_metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (month_dir / ".complete.json").write_text(
                json.dumps({"month": month_label, "status": "COMPLETE"}, indent=2) + "\n",
                encoding="utf-8",
            )
            checkpoint_status = "WRITTEN"

        monthly_rows.append(month_frame)
        monthly_unmatched.append(unmatched_frame)
        all_source_paths.append(source_file)
        monthly_status_rows.append(
            {
                "month": month_label,
                "rows": int(len(month_frame)),
                "intervals": int(month_frame["interval_timestamp_utc"].nunique()) if not month_frame.empty else 0,
                "regions": int(month_frame["region"].nunique()) if not month_frame.empty else 0,
                "checkpoint_status": checkpoint_status,
                "generator_master_match_rate_pct": month_metadata.get("generator_master_match_rate_pct", 0.0),
                "renewable_penetration_mean_pct": month_metadata.get("renewable_penetration_mean_pct", 0.0),
                "unmatched_duid_count": month_metadata.get("unmatched_duid_count", 0),
                "source_file": str(source_file),
            }
        )

    feature_store = pd.concat(monthly_rows, ignore_index=True) if monthly_rows else pd.DataFrame(columns=OUTPUT_COLUMNS)
    unmatched_observations = pd.concat(monthly_unmatched, ignore_index=True) if monthly_unmatched else pd.DataFrame()
    monthly_status = pd.DataFrame(monthly_status_rows)

    if not feature_store.empty:
        feature_store = feature_store.drop_duplicates(subset=["interval_timestamp_utc", "region"], keep="last").sort_values(
            ["interval_timestamp_utc", "region"]
        ).reset_index(drop=True)

    feature_store_path = output_dir / "regional_renewable_penetration_5min.csv.gz"
    unmatched_path = output_dir / "unmatched_duid_observations.csv.gz"
    status_path = output_dir / "monthly_build_status.csv"
    metadata_path = output_dir / "regional_renewable_penetration_metadata.json"

    feature_store.to_csv(feature_store_path, index=False, compression="gzip")
    unmatched_observations.to_csv(unmatched_path, index=False, compression="gzip")
    monthly_status.to_csv(status_path, index=False)

    metadata = {
        "start_month": start_month or _month_label_from_path(scada_files[0]),
        "end_month": end_month or _month_label_from_path(scada_files[-1]),
        "months": int(len(scada_files)),
        "rows": int(len(feature_store)),
        "regions": int(feature_store["region"].nunique()) if not feature_store.empty else 0,
        "intervals": int(feature_store["interval_timestamp_utc"].nunique()) if not feature_store.empty else 0,
        "unmatched_observations": int(len(unmatched_observations)),
        "checkpoint_root": str(checkpoint_root),
        "generator_master_path": str(repo_root / "data" / "derived" / "generator_master_v1" / "generator_master_v1.csv"),
        "source_hash": _hash_paths(all_source_paths),
        "output_files": {
            "feature_store": str(feature_store_path),
            "unmatched_observations": str(unmatched_path),
            "monthly_status": str(status_path),
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return RegionalRenewablePenetrationResult(feature_store, unmatched_observations, monthly_status, metadata)
