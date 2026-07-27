from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset_library import _derive_interconnector_row_fields, normalize_aemo_timestamp_series


INTERVENTION_AUDIT_COLUMNS = [
    "interval_timestamp_utc",
    "interconnector_id",
    "runno",
    "count_intervention_0",
    "count_intervention_1",
    "paired_intervention_values_differ",
]


@dataclass(frozen=True)
class HistoricalFeatureStoreResult:
    feature_store: pd.DataFrame
    dataset_status: pd.DataFrame
    metadata: dict[str, object]


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if not path.exists():
            continue
        digest.update(str(path).encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("utf-8"))
        digest.update(str(path.stat().st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()


def _cache_file_timestamp(file_path: Path) -> pd.Timestamp | None:
    match = re.search(r"_(\d{12})\.", file_path.name)
    if not match:
        return None
    return pd.to_datetime(match.group(1), format="%Y%m%d%H%M", utc=True)


def _list_cache_files(base: Path, suffix: str, *, start_date: str | None = None, end_date: str | None = None) -> list[Path]:
    cache = base / ".cache"
    if not cache.exists():
        return []
    files = sorted(cache.rglob(f"*{suffix}"))
    if start_date is None and end_date is None:
        return files

    start_ts = pd.to_datetime(start_date, utc=True) if start_date is not None else None
    end_ts = pd.to_datetime(end_date, utc=True) if end_date is not None else None
    selected: list[Path] = []
    for file_path in files:
        file_ts = _cache_file_timestamp(file_path)
        if file_ts is None:
            continue
        if start_ts is not None and file_ts < start_ts:
            continue
        if end_ts is not None and file_ts > end_ts:
            continue
        selected.append(file_path)
    return selected


def _to_interval_utc(frame: pd.DataFrame, source_col: str = "SETTLEMENTDATE") -> pd.Series:
    return normalize_aemo_timestamp_series(frame[source_col], source_timezone="Australia/Brisbane").dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _aligned_series(frame: pd.DataFrame, column: str, default: object = pd.NA, dtype: str | None = None) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index, dtype=dtype)


def _numeric_column(frame: pd.DataFrame, candidates: tuple[str, ...], default: float = float("nan")) -> pd.Series:
    for column in candidates:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _read_cached_csv(file_path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(file_path, low_memory=False)
    except (EOFError, OSError, pd.errors.ParserError, ValueError):
        return None


def _aggregate_dispatchprice(
    repo_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    files = _list_cache_files(
        repo_root / "data/raw/aemo/mmsdm_dispatchprice",
        ".dispatchprice.csv.gz",
        start_date=start_date,
        end_date=end_date,
    )
    if not files:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "MISSING", "rows": 0}

    frames: list[pd.DataFrame] = []
    for file_path in files:
        data = _read_cached_csv(file_path)
        if data is None:
            continue
        if not {"SETTLEMENTDATE", "REGIONID", "RRP"}.issubset(data.columns):
            continue
        data = data[["SETTLEMENTDATE", "REGIONID", "RRP"]].copy()
        data["interval_timestamp_utc"] = _to_interval_utc(data)
        data["RRP"] = pd.to_numeric(data["RRP"], errors="coerce")
        frames.append(data)

    if not frames:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "INVALID", "rows": 0}

    frame = pd.concat(frames, ignore_index=True)
    agg = (
        frame.groupby(["interval_timestamp_utc", "REGIONID"], as_index=False)["RRP"]
        .mean()
        .pivot(index="interval_timestamp_utc", columns="REGIONID", values="RRP")
        .reset_index()
    )
    region_name_map = {
        "NSW1": "dispatchprice_nsw_rrp",
        "QLD1": "dispatchprice_qld_rrp",
        "VIC1": "dispatchprice_vic_rrp",
        "SA1": "dispatchprice_sa_rrp",
        "TAS1": "dispatchprice_tas_rrp",
    }
    agg.columns = ["interval_timestamp_utc", *[region_name_map.get(str(column), f"dispatchprice_{str(column).lower()}_rrp") for column in agg.columns[1:]]]
    region_cols = [c for c in agg.columns if c.startswith("dispatchprice_") and c.endswith("_rrp")]
    if region_cols:
        agg["dispatchprice_price_spread_max_min"] = agg[region_cols].max(axis=1) - agg[region_cols].min(axis=1)

    meta = {
        "status": "AVAILABLE",
        "rows": int(len(agg)),
        "files": int(len(files)),
        "lineage_hash": _hash_files(files),
        "min_interval": agg["interval_timestamp_utc"].min() if not agg.empty else None,
        "max_interval": agg["interval_timestamp_utc"].max() if not agg.empty else None,
    }
    return agg, meta


def _aggregate_dispatchregionsum(
    repo_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    files = _list_cache_files(
        repo_root / "data/raw/aemo/mmsdm_dispatchregionsum",
        ".dispatchregionsum.csv.gz",
        start_date=start_date,
        end_date=end_date,
    )
    if not files:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "MISSING", "rows": 0}

    frames: list[pd.DataFrame] = []
    for file_path in files:
        data = _read_cached_csv(file_path)
        if data is None:
            continue
        if "SETTLEMENTDATE" not in data.columns or "REGIONID" not in data.columns:
            continue
        demand_col = "TOTALDEMAND" if "TOTALDEMAND" in data.columns else "TOTAL_DEMAND_MW" if "TOTAL_DEMAND_MW" in data.columns else None
        forecast_col = "DEMANDFORECAST" if "DEMANDFORECAST" in data.columns else None
        if demand_col is None:
            continue
        cols = ["SETTLEMENTDATE", "REGIONID", demand_col] + ([forecast_col] if forecast_col else [])
        data = data[cols].copy()
        data["interval_timestamp_utc"] = _to_interval_utc(data)
        data["demand"] = pd.to_numeric(data[demand_col], errors="coerce")
        if forecast_col:
            data["forecast"] = pd.to_numeric(data[forecast_col], errors="coerce")
        frames.append(data)

    if not frames:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "INVALID", "rows": 0}

    frame = pd.concat(frames, ignore_index=True)
    demand_total = frame.groupby("interval_timestamp_utc", as_index=False)["demand"].sum().rename(
        columns={"demand": "dispatchregionsum_total_demand_mw"}
    )
    demand_region = (
        frame.groupby(["interval_timestamp_utc", "REGIONID"], as_index=False)["demand"]
        .sum()
        .pivot(index="interval_timestamp_utc", columns="REGIONID", values="demand")
        .reset_index()
    )
    demand_region.columns = [
        "interval_timestamp_utc",
        *[
            "dispatchregionsum_nsw_demand_mw" if c == "NSW1" else
            "dispatchregionsum_qld_demand_mw" if c == "QLD1" else
            "dispatchregionsum_vic_demand_mw" if c == "VIC1" else
            "dispatchregionsum_sa_demand_mw" if c == "SA1" else
            "dispatchregionsum_tas_demand_mw" if c == "TAS1" else
            f"dispatchregionsum_{str(c).lower()}_demand_mw"
            for c in demand_region.columns[1:]
        ],
    ]
    agg = demand_total.merge(demand_region, on="interval_timestamp_utc", how="left")

    if "forecast" in frame.columns:
        forecast = frame.groupby("interval_timestamp_utc", as_index=False)["forecast"].sum().rename(
            columns={"forecast": "dispatchregionsum_total_forecast_demand_mw"}
        )
        agg = agg.merge(forecast, on="interval_timestamp_utc", how="left")

    meta = {
        "status": "AVAILABLE",
        "rows": int(len(agg)),
        "files": int(len(files)),
        "lineage_hash": _hash_files(files),
        "min_interval": agg["interval_timestamp_utc"].min() if not agg.empty else None,
        "max_interval": agg["interval_timestamp_utc"].max() if not agg.empty else None,
    }
    return agg, meta


def _normalize_interconnector_columns(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["MWFLOW"] = _numeric_column(frame, ("MWFLOW", "FLOW_MW"))
    frame["METEREDMWFLOW"] = _numeric_column(frame, ("METEREDMWFLOW", "METERED_MWFLOW"))
    frame["EXPORTLIMIT"] = _numeric_column(frame, ("EXPORTLIMIT", "EXPORTLIMIT_MW"))
    frame["IMPORTLIMIT"] = _numeric_column(frame, ("IMPORTLIMIT", "IMPORTLIMIT_MW"))
    intervention_source = _aligned_series(frame, "INTERVENTION", default=0, dtype="int64")
    frame["INTERVENTION"] = pd.to_numeric(intervention_source, errors="coerce").fillna(0).astype(int)
    frame["RUNNO"] = pd.to_numeric(_aligned_series(frame, "RUNNO"), errors="coerce")
    frame["LASTCHANGED"] = _aligned_series(frame, "LASTCHANGED", default=pd.NA, dtype="object")
    frame["SOURCE_FILE"] = _aligned_series(frame, "SOURCE_FILE", default=pd.NA, dtype="object")
    return frame


def _aggregate_dispatchinterconnectorres(
    repo_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    files = _list_cache_files(
        repo_root / "data/raw/aemo/mmsdm_dispatchinterconnectorres",
        ".dispatchinterconnectorres.csv.gz",
        start_date=start_date,
        end_date=end_date,
    )
    if not files:
        empty = pd.DataFrame(columns=["interval_timestamp_utc"])
        return empty, pd.DataFrame(), {"status": "MISSING", "rows": 0}

    frames: list[pd.DataFrame] = []
    for file_path in files:
        data = _read_cached_csv(file_path)
        if data is None:
            continue
        if "SETTLEMENTDATE" not in data.columns or "INTERCONNECTORID" not in data.columns:
            continue
        data = _normalize_interconnector_columns(data)
        data["interval_timestamp_utc"] = _to_interval_utc(data)
        data["__source_file"] = str(file_path)
        frames.append(data)

    if not frames:
        empty = pd.DataFrame(columns=["interval_timestamp_utc"])
        return empty, pd.DataFrame(), {"status": "INVALID", "rows": 0}

    frame = pd.concat(frames, ignore_index=True)

    # intervention audit at run granularity
    audit_rows: list[dict[str, object]] = []
    for key, grp in frame.groupby(["interval_timestamp_utc", "INTERCONNECTORID", "RUNNO"], dropna=False):
        g0 = grp[grp["INTERVENTION"] == 0]
        g1 = grp[grp["INTERVENTION"] == 1]
        differs = False
        if not g0.empty and not g1.empty:
            r0 = g0.iloc[0]
            r1 = g1.iloc[0]
            for col in ["MWFLOW", "METEREDMWFLOW", "EXPORTLIMIT", "IMPORTLIMIT"]:
                v0, v1 = r0.get(col), r1.get(col)
                if (pd.isna(v0) and pd.isna(v1)):
                    continue
                if pd.isna(v0) != pd.isna(v1) or float(v0) != float(v1):
                    differs = True
                    break
        audit_rows.append(
            {
                "interval_timestamp_utc": key[0],
                "interconnector_id": key[1],
                "runno": key[2],
                "count_intervention_0": int(len(g0)),
                "count_intervention_1": int(len(g1)),
                "paired_intervention_values_differ": differs,
            }
        )
    audit = pd.DataFrame(audit_rows, columns=INTERVENTION_AUDIT_COLUMNS)

    canonical = frame[frame["INTERVENTION"] == 0].copy()
    canonical = _derive_interconnector_row_fields(canonical)

    canonical["publication_timestamp_utc"] = pd.to_datetime(canonical["LASTCHANGED"], errors="coerce", utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    agg = (
        canonical.groupby("interval_timestamp_utc", as_index=False)
        .agg(
            dispatchinterconnectorres_interconnector_count=("INTERCONNECTORID", "nunique"),
            dispatchinterconnectorres_net_flow_mw=("MWFLOW", "sum"),
            dispatchinterconnectorres_metered_flow_mw=("METEREDMWFLOW", "sum"),
            dispatchinterconnectorres_total_abs_flow_mw=("MWFLOW", lambda s: float(s.abs().sum())),
            dispatchinterconnectorres_export_limit_mw=("EXPORTLIMIT_MW", "mean"),
            dispatchinterconnectorres_import_limit_mw=("IMPORTLIMIT_MW", "mean"),
            dispatchinterconnectorres_directional_limit_mw=("directional_limit_mw", "mean"),
            dispatchinterconnectorres_utilisation_pct=("utilisation_pct", "mean"),
            dispatchinterconnectorres_over_limit_count=("over_limit_flag", lambda s: int(s.fillna(False).sum())),
            dispatchinterconnectorres_limit_invalid_count=("limit_quality_flag", lambda s: int((s == "INVALID").sum())),
            dispatchinterconnectorres_latest_publication_timestamp=("publication_timestamp_utc", "max"),
        )
        .reset_index(drop=True)
    )

    # primary interconnector signal for queryability (QNI-like proxy)
    qni = canonical[canonical["INTERCONNECTORID"].astype(str).str.contains("NSW1-QLD1", na=False)].copy()
    if not qni.empty:
        qni_agg = (
            qni.groupby("interval_timestamp_utc", as_index=False)
            .agg(
                qni_flow_mw=("MWFLOW", "sum"),
                qni_utilisation_pct=("utilisation_pct", "mean"),
                qni_directional_limit_mw=("directional_limit_mw", "mean"),
                qni_over_limit_count=("over_limit_flag", lambda s: int(s.fillna(False).sum())),
            )
        )
        agg = agg.merge(qni_agg, on="interval_timestamp_utc", how="left")

    interv_counts = frame.groupby("interval_timestamp_utc", as_index=False).agg(
        dispatchinterconnectorres_intervention1_excluded=("INTERVENTION", lambda s: int((s == 1).sum())),
    )
    agg = agg.merge(interv_counts, on="interval_timestamp_utc", how="left")

    pair_diff = audit.groupby("interval_timestamp_utc", as_index=False)["paired_intervention_values_differ"].sum().rename(
        columns={"paired_intervention_values_differ": "dispatchinterconnectorres_intervention_pair_diff_count"}
    )
    agg = agg.merge(pair_diff, on="interval_timestamp_utc", how="left")

    meta = {
        "status": "AVAILABLE",
        "rows": int(len(agg)),
        "files": int(len(files)),
        "lineage_hash": _hash_files(files),
        "min_interval": agg["interval_timestamp_utc"].min() if not agg.empty else None,
        "max_interval": agg["interval_timestamp_utc"].max() if not agg.empty else None,
        "intervention1_rows_excluded": int((frame["INTERVENTION"] == 1).sum()),
        "intervention_pairs_differ": int(audit["paired_intervention_values_differ"].sum()) if not audit.empty else 0,
    }
    return agg, audit, meta


def _aggregate_dispatchconstraint(
    repo_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    files = _list_cache_files(
        repo_root / "data/raw/aemo/mmsdm_dispatchconstraint",
        ".dispatchconstraint.csv.gz",
        start_date=start_date,
        end_date=end_date,
    )
    if not files:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "MISSING", "rows": 0}

    frames: list[pd.DataFrame] = []
    for file_path in files:
        data = _read_cached_csv(file_path)
        if data is None:
            continue
        if "SETTLEMENTDATE" not in data.columns:
            continue
        cons_col = "CONSTRAINTID" if "CONSTRAINTID" in data.columns else None
        if cons_col is None:
            continue
        marg_col = "MARGINALVALUE" if "MARGINALVALUE" in data.columns else None
        viol_col = "VIOLATIONDEGREE" if "VIOLATIONDEGREE" in data.columns else "VIOLATION_DEGREE" if "VIOLATION_DEGREE" in data.columns else None
        cols = ["SETTLEMENTDATE", cons_col] + ([marg_col] if marg_col else []) + ([viol_col] if viol_col else [])
        data = data[cols].copy()
        data["interval_timestamp_utc"] = _to_interval_utc(data)
        data["MARGINALVALUE"] = pd.to_numeric(data[marg_col], errors="coerce") if marg_col else np.nan
        data["VIOLATIONDEGREE"] = pd.to_numeric(data[viol_col], errors="coerce") if viol_col else np.nan
        frames.append(data)

    if not frames:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "INVALID", "rows": 0}

    frame = pd.concat(frames, ignore_index=True)
    agg = frame.groupby("interval_timestamp_utc", as_index=False).agg(
        dispatchconstraint_constraint_count=(cons_col, "nunique"),
        dispatchconstraint_max_marginal_value=("MARGINALVALUE", "max"),
        dispatchconstraint_mean_marginal_value=("MARGINALVALUE", "mean"),
        dispatchconstraint_violation_count=("VIOLATIONDEGREE", lambda s: int((s.fillna(0).abs() > 0).sum())),
        dispatchconstraint_max_violation_degree=("VIOLATIONDEGREE", "max"),
    )
    agg["dispatchconstraint_binding_flag"] = agg["dispatchconstraint_violation_count"] > 0

    meta = {
        "status": "AVAILABLE",
        "rows": int(len(agg)),
        "files": int(len(files)),
        "lineage_hash": _hash_files(files),
        "min_interval": agg["interval_timestamp_utc"].min() if not agg.empty else None,
        "max_interval": agg["interval_timestamp_utc"].max() if not agg.empty else None,
    }
    return agg, meta


def _aggregate_dispatch_unit_scada(
    repo_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    files = _list_cache_files(
        repo_root / "data/raw/aemo/mmsdm_dispatch_unit_scada",
        ".dispatch_unit_scada.csv.gz",
        start_date=start_date,
        end_date=end_date,
    )
    if not files:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "MISSING", "rows": 0}

    frames: list[pd.DataFrame] = []
    for file_path in files:
        data = _read_cached_csv(file_path)
        if data is None:
            continue
        if not {"SETTLEMENTDATE", "DUID", "SCADA_MW"}.issubset(data.columns):
            continue
        data = data[["SETTLEMENTDATE", "DUID", "SCADA_MW", *(["REGIONID"] if "REGIONID" in data.columns else [])]].copy()
        data["interval_timestamp_utc"] = _to_interval_utc(data)
        data["SCADA_MW"] = pd.to_numeric(data["SCADA_MW"], errors="coerce")
        frames.append(data)

    if not frames:
        return pd.DataFrame(columns=["interval_timestamp_utc"]), {"status": "INVALID", "rows": 0}

    frame = pd.concat(frames, ignore_index=True)
    agg = frame.groupby("interval_timestamp_utc", as_index=False).agg(
        dispatch_unit_scada_duid_count=("DUID", "nunique"),
        dispatch_unit_scada_total_mw=("SCADA_MW", "sum"),
        dispatch_unit_scada_abs_total_mw=("SCADA_MW", lambda s: float(s.abs().sum())),
        dispatch_unit_scada_mean_mw=("SCADA_MW", "mean"),
        dispatch_unit_scada_positive_mw=("SCADA_MW", lambda s: float(s[s > 0].sum())),
        dispatch_unit_scada_negative_mw=("SCADA_MW", lambda s: float(s[s < 0].sum())),
    )
    agg["dispatch_unit_scada_active_units"] = agg["dispatch_unit_scada_duid_count"] > 0

    meta = {
        "status": "AVAILABLE",
        "rows": int(len(agg)),
        "files": int(len(files)),
        "lineage_hash": _hash_files(files),
        "min_interval": agg["interval_timestamp_utc"].min() if not agg.empty else None,
        "max_interval": agg["interval_timestamp_utc"].max() if not agg.empty else None,
    }
    return agg, meta


def _compute_quality_score(feature_store: pd.DataFrame, feature_columns: list[str]) -> pd.Series:
    if not feature_columns:
        return pd.Series(np.nan, index=feature_store.index, dtype=float, name="quality_score")

    non_null_count = feature_store[feature_columns].notna().sum(axis=1)
    quality_score = non_null_count.div(len(feature_columns)).mul(100.0).round(4)
    quality_score.name = "quality_score"
    return quality_score


def build_historical_feature_store(
    repo_root: Path,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    output_dir: Path | None = None,
) -> HistoricalFeatureStoreResult:
    if output_dir is None:
        output_dir = repo_root / "data" / "derived" / "historical_feature_store"
    output_dir.mkdir(parents=True, exist_ok=True)

    dprice, dprice_meta = _aggregate_dispatchprice(repo_root, start_date=start_date, end_date=end_date)
    dregion, dregion_meta = _aggregate_dispatchregionsum(repo_root, start_date=start_date, end_date=end_date)
    dinter, intervention_audit, dinter_meta = _aggregate_dispatchinterconnectorres(repo_root, start_date=start_date, end_date=end_date)
    dcons, dcons_meta = _aggregate_dispatchconstraint(repo_root, start_date=start_date, end_date=end_date)
    dscada, dscada_meta = _aggregate_dispatch_unit_scada(repo_root, start_date=start_date, end_date=end_date)

    frames = [dprice, dregion, dinter, dcons, dscada]
    valid_frames = [f for f in frames if not f.empty]

    if valid_frames:
        max_interval = max(pd.to_datetime(f["interval_timestamp_utc"], utc=True, errors="coerce").max() for f in valid_frames)
    else:
        max_interval = pd.Timestamp.now("UTC").floor("5min")

    start_ts = pd.Timestamp(start_date, tz="Australia/Brisbane").tz_convert("UTC")
    timeline = pd.date_range(start=start_ts, end=max_interval, freq="5min", tz="UTC")
    feature_store = pd.DataFrame({"interval_timestamp_utc": timeline.strftime("%Y-%m-%dT%H:%M:%SZ")})

    for frame in valid_frames:
        feature_store = feature_store.merge(frame, on="interval_timestamp_utc", how="left")

    feature_columns = [c for c in feature_store.columns if c != "interval_timestamp_utc"]
    feature_store["observation_timestamp_utc"] = feature_store["interval_timestamp_utc"]
    feature_store["effective_timestamp_utc"] = feature_store["interval_timestamp_utc"]
    feature_store["publication_timestamp_utc"] = feature_store.get(
        "dispatchinterconnectorres_latest_publication_timestamp",
        feature_store["interval_timestamp_utc"],
    )
    feature_store["source"] = "AEMO_PUBLIC_MMSDM"
    feature_store["point_in_time_available"] = True
    feature_store["quality_score"] = _compute_quality_score(feature_store, feature_columns)

    lineage_hash = _hash_files(
        _list_cache_files(repo_root / "data/raw/aemo/mmsdm_dispatchprice", ".dispatchprice.csv.gz", start_date=start_date, end_date=end_date)
        + _list_cache_files(repo_root / "data/raw/aemo/mmsdm_dispatchregionsum", ".dispatchregionsum.csv.gz", start_date=start_date, end_date=end_date)
        + _list_cache_files(repo_root / "data/raw/aemo/mmsdm_dispatchinterconnectorres", ".dispatchinterconnectorres.csv.gz", start_date=start_date, end_date=end_date)
        + _list_cache_files(repo_root / "data/raw/aemo/mmsdm_dispatchconstraint", ".dispatchconstraint.csv.gz", start_date=start_date, end_date=end_date)
        + _list_cache_files(repo_root / "data/raw/aemo/mmsdm_dispatch_unit_scada", ".dispatch_unit_scada.csv.gz", start_date=start_date, end_date=end_date)
    )
    feature_store["lineage_hash"] = lineage_hash

    duplicate_keys = int(feature_store.duplicated(subset=["interval_timestamp_utc"], keep=False).sum())
    expected_intervals = int(len(feature_store))
    actual_intervals = int(feature_store["interval_timestamp_utc"].nunique())
    interval_coverage_pct = round((actual_intervals / expected_intervals * 100.0), 6) if expected_intervals else 0.0

    dataset_status = pd.DataFrame(
        [
            {"dataset": "DISPATCHPRICE", **dprice_meta},
            {"dataset": "DISPATCHREGIONSUM", **dregion_meta},
            {"dataset": "DISPATCHINTERCONNECTORRES", **dinter_meta},
            {"dataset": "DISPATCHCONSTRAINT", **dcons_meta},
            {"dataset": "DISPATCH_UNIT_SCADA", **dscada_meta},
            {
                "dataset": "GENERATOR_OUTAGES",
                "status": "BLOCKED_EXTERNAL",
                "rows": 0,
                "files": 0,
                "lineage_hash": None,
                "min_interval": None,
                "max_interval": None,
                "blocker": "External outage source not ingested yet",
            },
            {
                "dataset": "UNIT_COMMITMENT",
                "status": "DERIVED_PARTIAL",
                "rows": int(dscada_meta.get("rows", 0)),
                "files": int(dscada_meta.get("files", 0)),
                "lineage_hash": dscada_meta.get("lineage_hash"),
                "min_interval": dscada_meta.get("min_interval"),
                "max_interval": dscada_meta.get("max_interval"),
                "blocker": "Derived proxy from SCADA only (no unit technology register)",
            },
            {
                "dataset": "RENEWABLE_GENERATION",
                "status": "DERIVED_PARTIAL",
                "rows": int(dscada_meta.get("rows", 0)),
                "files": int(dscada_meta.get("files", 0)),
                "lineage_hash": dscada_meta.get("lineage_hash"),
                "min_interval": dscada_meta.get("min_interval"),
                "max_interval": dscada_meta.get("max_interval"),
                "blocker": "No DUID technology map in repo snapshot",
            },
            {
                "dataset": "WEATHER",
                "status": "BLOCKED_EXTERNAL",
                "rows": 0,
                "files": 0,
                "lineage_hash": None,
                "min_interval": None,
                "max_interval": None,
                "blocker": "No BOM weather ingest configured",
            },
            {
                "dataset": "FCAS",
                "status": "BLOCKED_EXTERNAL",
                "rows": 0,
                "files": 0,
                "lineage_hash": None,
                "min_interval": None,
                "max_interval": None,
                "blocker": "No FCAS dataset ingest in current snapshot",
            },
        ]
    )

    # Persist core artifacts
    feature_store_path = output_dir / "historical_market_feature_store_5min.csv.gz"
    feature_store.to_csv(feature_store_path, index=False, compression="gzip")

    dataset_status_path = output_dir / "historical_dataset_status.csv"
    dataset_status.to_csv(dataset_status_path, index=False)

    intervention_audit_path = output_dir / "historical_intervention_audit.csv"
    intervention_audit.reindex(columns=INTERVENTION_AUDIT_COLUMNS).to_csv(intervention_audit_path, index=False)

    metadata = {
        "start_date": start_date,
        "end_date": str(max_interval),
        "expected_intervals": expected_intervals,
        "actual_intervals": actual_intervals,
        "interval_coverage_pct": interval_coverage_pct,
        "duplicate_interval_keys": duplicate_keys,
        "feature_columns": len(feature_columns),
        "lineage_hash": lineage_hash,
        "outputs": {
            "feature_store": str(feature_store_path),
            "dataset_status": str(dataset_status_path),
            "intervention_audit": str(intervention_audit_path),
        },
    }

    metadata_path = output_dir / "historical_feature_store_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return HistoricalFeatureStoreResult(
        feature_store=feature_store,
        dataset_status=dataset_status,
        metadata=metadata,
    )
