from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .dataset_library import build_correlation_ready_table, build_dataset_catalog, load_normalized_dataset
from .driver_catalogue import build_catalogue_df
from .phase5c_pipeline import assess_source_availability


CAPABILITY1_PRIORITY = 1


@dataclass(frozen=True)
class Capability1Result:
    combined_market_state: pd.DataFrame
    inventory: pd.DataFrame
    source_availability: pd.DataFrame
    summary: dict[str, object]


@dataclass(frozen=True)
class Capability1DatasetSpec:
    dataset_name: str
    priority: int
    status: str
    source_kind: str
    dataset_id: str | None
    driver_variables: tuple[str, ...]
    required_columns: tuple[str, ...]
    commercial_capability: str
    dependency_note: str


CAPABILITY1_DATASETS: tuple[Capability1DatasetSpec, ...] = (
    Capability1DatasetSpec(
        dataset_name="constraint_state",
        priority=1,
        status="AVAILABLE",
        source_kind="direct",
        dataset_id="dispatchconstraint",
        driver_variables=("constraint_frequency", "constraint_marginal_value"),
        required_columns=("interval_timestamp_utc", "CONSTRAINTID", "MARGINALVALUE", "VIOLATIONDEGREE"),
        commercial_capability="Constraint-aware congestion detection",
        dependency_note="Directly supported by DISPATCHCONSTRAINT archives.",
    ),
    Capability1DatasetSpec(
        dataset_name="generator_outages",
        priority=2,
        status="EXTERNAL_GAP",
        source_kind="external",
        dataset_id=None,
        driver_variables=("network_outage_days",),
        required_columns=(),
        commercial_capability="Outage-aware capacity screening",
        dependency_note="External outage register / MT PASA source not present in repository snapshot.",
    ),
    Capability1DatasetSpec(
        dataset_name="unit_commitment",
        priority=3,
        status="DERIVED",
        source_kind="derived",
        dataset_id="dispatch_unit_scada",
        driver_variables=("duid_generation",),
        required_columns=("interval_timestamp_utc", "DUID", "SCADA_MW", "REGIONID"),
        commercial_capability="Unit-level on/off and dispatch participation proxy",
        dependency_note="Derived from DISPATCH_UNIT_SCADA by interval and DUID activity.",
    ),
    Capability1DatasetSpec(
        dataset_name="scada_generation",
        priority=4,
        status="AVAILABLE",
        source_kind="direct",
        dataset_id="dispatch_unit_scada",
        driver_variables=("duid_generation",),
        required_columns=("interval_timestamp_utc", "DUID", "SCADA_MW", "REGIONID"),
        commercial_capability="Unit-level dispatch telemetry",
        dependency_note="Directly supported by DISPATCH_UNIT_SCADA archives.",
    ),
    Capability1DatasetSpec(
        dataset_name="renewable_availability",
        priority=5,
        status="PARTIAL",
        source_kind="derived",
        dataset_id="dispatch_unit_scada",
        driver_variables=("wind_generation_quarterly", "solar_generation_quarterly", "hydro_generation_quarterly"),
        required_columns=("interval_timestamp_utc", "DUID", "SCADA_MW", "REGIONID"),
        commercial_capability="Renewable participation / output availability proxy",
        dependency_note="SCADA exists, but a unit technology map is still required for fully labelled renewable availability.",
    ),
    Capability1DatasetSpec(
        dataset_name="weather",
        priority=6,
        status="EXTERNAL_GAP",
        source_kind="external",
        dataset_id=None,
        driver_variables=("temperature_anomaly_quarterly", "wind_resource_index", "rainfall_and_hydrology"),
        required_columns=(),
        commercial_capability="Weather-driven demand / renewable context",
        dependency_note="External BOM / hydrology inputs are not present in the repository snapshot.",
    ),
    Capability1DatasetSpec(
        dataset_name="transmission_capability",
        priority=7,
        status="AVAILABLE",
        source_kind="derived",
        dataset_id="dispatchinterconnectorres",
        driver_variables=("interconnector_flow", "available_capability_mw"),
        required_columns=("interval_timestamp_utc", "INTERCONNECTORID", "MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT"),
        commercial_capability="Interconnector capacity and headroom",
        dependency_note="Derived from DISPATCHINTERCONNECTORRES import / export limits.",
    ),
    Capability1DatasetSpec(
        dataset_name="network_utilisation",
        priority=8,
        status="DERIVED",
        source_kind="derived",
        dataset_id="dispatchinterconnectorres",
        driver_variables=("interconnector_flow", "available_capability_mw"),
        required_columns=("interval_timestamp_utc", "INTERCONNECTORID", "MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT"),
        commercial_capability="Capacity usage and congestion intensity",
        dependency_note="Derived as absolute flow divided by available capability.",
    ),
)


def _normalise_timestamp_frame(frame: pd.DataFrame, *, timestamp_column: str = "interval_timestamp_utc") -> pd.DataFrame:
    if frame.empty or timestamp_column not in frame.columns:
        return frame.copy()
    output = frame.copy()
    output[timestamp_column] = pd.to_datetime(output[timestamp_column], utc=True, errors="coerce")
    return output


def _combined_hash(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    resolved_paths = [path.resolve() for path in paths if path.exists()]
    for path in sorted(resolved_paths):
        digest.update(str(path).encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("utf-8"))
        digest.update(str(int(path.stat().st_mtime_ns)).encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except Exception:
            continue
    return digest.hexdigest()


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100.0, 2)


def _quality_score(*, schema_valid: bool, pit_valid_pct: float, completeness_pct: float, source_count: int) -> float:
    base = 0.0
    base += 30.0 if schema_valid else 0.0
    base += min(max(completeness_pct, 0.0), 100.0) * 0.45
    base += min(max(pit_valid_pct, 0.0), 100.0) * 0.20
    base += min(source_count, 3) * 5.0
    return round(min(base, 100.0), 2)


def _dataset_source_paths(repo_root: Path, dataset_id: str | None) -> list[Path]:
    if dataset_id is None:
        return []
    catalog = {spec.dataset_id: spec for spec in build_dataset_catalog(repo_root) if spec.dataset_id is not None}
    spec = catalog.get(dataset_id)
    if spec is None:
        return []
    if spec.data_glob:
        return sorted(repo_root.glob(spec.data_glob))
    file_path = Path(spec.data_path)
    if not file_path.is_absolute():
        file_path = repo_root / file_path
    return [file_path] if file_path.exists() else []


def _load_direct_dataset(repo_root: Path, dataset_id: str) -> pd.DataFrame:
    catalog = {spec.dataset_id: spec for spec in build_dataset_catalog(repo_root) if spec.dataset_id is not None}
    spec = catalog.get(dataset_id)
    if spec is None:
        return pd.DataFrame()
    try:
        return load_normalized_dataset(spec, repo_root=repo_root)
    except Exception:
        return pd.DataFrame()


def _build_inventory_row(repo_root: Path, spec: Capability1DatasetSpec) -> dict[str, object]:
    source_paths = _dataset_source_paths(repo_root, spec.dataset_id)
    source_count = len(source_paths)
    direct_frame = _load_direct_dataset(repo_root, spec.dataset_id) if spec.dataset_id else pd.DataFrame()

    if spec.source_kind == "external":
        driver_catalogue = build_catalogue_df()
        driver_rows = driver_catalogue[driver_catalogue["variable"].isin(spec.driver_variables)] if not driver_catalogue.empty else pd.DataFrame()
        return {
            "dataset_name": spec.dataset_name,
            "priority": spec.priority,
            "status": spec.status,
            "source_kind": spec.source_kind,
            "dataset_id": spec.dataset_id or "",
            "rows": 0,
            "distinct_intervals": 0,
            "schema_valid": False,
            "pit_valid_pct": 0.0,
            "completeness_pct": 0.0,
            "quality_score": 0.0,
            "lineage_hash": _combined_hash([]) if not driver_rows.empty else hashlib.sha256(spec.dataset_name.encode("utf-8")).hexdigest(),
            "source_paths": "",
            "commercial_capability": spec.commercial_capability,
            "dependency_note": spec.dependency_note,
            "driver_variables": "|".join(spec.driver_variables),
            "driver_catalogue_matches": int(len(driver_rows)),
        }

    if direct_frame.empty:
        return {
            "dataset_name": spec.dataset_name,
            "priority": spec.priority,
            "status": "MISSING",
            "source_kind": spec.source_kind,
            "dataset_id": spec.dataset_id or "",
            "rows": 0,
            "distinct_intervals": 0,
            "schema_valid": False,
            "pit_valid_pct": 0.0,
            "completeness_pct": 0.0,
            "quality_score": 0.0,
            "lineage_hash": _combined_hash(source_paths),
            "source_paths": "|".join(str(path) for path in source_paths),
            "commercial_capability": spec.commercial_capability,
            "dependency_note": spec.dependency_note,
            "driver_variables": "|".join(spec.driver_variables),
            "driver_catalogue_matches": 0,
        }

    normalised = _normalise_timestamp_frame(direct_frame)
    row_count = int(len(normalised))
    distinct_intervals = int(normalised["interval_timestamp_utc"].dropna().nunique()) if "interval_timestamp_utc" in normalised.columns else 0
    schema_valid = all(column in normalised.columns for column in spec.required_columns)
    pit_valid_pct = 100.0
    if "interval_timestamp_utc" in normalised.columns:
        pit_valid_pct = _safe_ratio(normalised["interval_timestamp_utc"].notna().sum(), row_count)
    required_present = sum(1 for column in spec.required_columns if column in normalised.columns)
    completeness_pct = _safe_ratio(required_present, len(spec.required_columns)) if spec.required_columns else 100.0
    if spec.status == "DERIVED":
        status = "DERIVED"
    elif spec.status == "PARTIAL":
        status = "PARTIAL"
    else:
        status = "AVAILABLE"
    quality_score = _quality_score(
        schema_valid=schema_valid,
        pit_valid_pct=pit_valid_pct,
        completeness_pct=completeness_pct,
        source_count=source_count,
    )
    return {
        "dataset_name": spec.dataset_name,
        "priority": spec.priority,
        "status": status,
        "source_kind": spec.source_kind,
        "dataset_id": spec.dataset_id or "",
        "rows": row_count,
        "distinct_intervals": distinct_intervals,
        "schema_valid": schema_valid,
        "pit_valid_pct": pit_valid_pct,
        "completeness_pct": completeness_pct,
        "quality_score": quality_score,
        "lineage_hash": _combined_hash(source_paths),
        "source_paths": "|".join(str(path) for path in source_paths),
        "commercial_capability": spec.commercial_capability,
        "dependency_note": spec.dependency_note,
        "driver_variables": "|".join(spec.driver_variables),
        "driver_catalogue_matches": 0,
    }


def _augment_combined_market_state(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if output.empty:
        return output

    alias_map = {
        "dispatchconstraint__dispatchconstraint_binding_flag": "constraint_binding_flag",
        "dispatchconstraint__dispatchconstraint_binding_count": "constraint_binding_count",
        "dispatchconstraint__dispatchconstraint_violation_count": "constraint_violation_count",
        "dispatchconstraint__dispatchconstraint_max_marginal_value": "constraint_marginal_value",
        "dispatchconstraint__dispatchconstraint_mean_marginal_value": "constraint_mean_marginal_value",
        "dispatchconstraint__dispatchconstraint_max_violation_degree": "constraint_max_violation_degree",
        "dispatch_unit_scada__dispatch_unit_scada_duid_count": "unit_commitment_active_units",
        "dispatch_unit_scada__dispatch_unit_scada_total_mw": "scada_generation_mw",
        "dispatch_unit_scada__dispatch_unit_scada_abs_total_mw": "scada_abs_generation_mw",
        "dispatch_unit_scada__dispatch_unit_scada_mean_mw": "scada_mean_generation_mw",
        "dispatch_unit_scada__dispatch_unit_scada_active_units": "unit_commitment_proxy_flag",
        # Raw flow
        "dispatchinterconnectorres__dispatchinterconnectorres_net_flow_mw": "transmission_flow_mw",
        "dispatchinterconnectorres__dispatchinterconnectorres_total_abs_flow_mw": "transmission_abs_flow_mw",
        "dispatchinterconnectorres__dispatchinterconnectorres_total_losses_mw": "transmission_losses_mw",
        # Preserved raw limits
        "dispatchinterconnectorres__dispatchinterconnectorres_export_limit_mw": "export_limit_mw",
        "dispatchinterconnectorres__dispatchinterconnectorres_import_limit_mw": "import_limit_mw",
        # Directional capability and utilisation (already correct, just surface them)
        "dispatchinterconnectorres__dispatchinterconnectorres_directional_limit_mw": "transmission_capability_mw",
        "dispatchinterconnectorres__dispatchinterconnectorres_utilisation_pct": "network_utilisation_pct",
        # Quality flags
        "dispatchinterconnectorres__dispatchinterconnectorres_limit_invalid_count": "limit_invalid_count",
        "dispatchinterconnectorres__dispatchinterconnectorres_over_limit_count": "over_limit_count",
    }
    for source_column, alias in alias_map.items():
        if source_column in output.columns and alias not in output.columns:
            output[alias] = output[source_column]

    if "dispatch_unit_scada__dispatch_unit_scada_duid_count" in output.columns and "unit_commitment_rate_pct" not in output.columns:
        active_units = pd.to_numeric(output["dispatch_unit_scada__dispatch_unit_scada_duid_count"], errors="coerce")
        output["unit_commitment_rate_pct"] = active_units.where(active_units.notna(), pd.NA)
    return output


def build_capability1_market_state(repo_root: Path) -> Capability1Result:
    source_availability = assess_source_availability(repo_root)
    combined = build_correlation_ready_table(repo_root=repo_root)
    combined = _augment_combined_market_state(combined)

    inventory_rows = [_build_inventory_row(repo_root, spec) for spec in CAPABILITY1_DATASETS]
    inventory = pd.DataFrame(inventory_rows).sort_values(["priority", "dataset_name"]).reset_index(drop=True)

    available_count = int((inventory["status"] != "EXTERNAL_GAP").sum()) if not inventory.empty else 0
    total_count = int(len(inventory))
    completion_pct = round((available_count / total_count * 100.0), 2) if total_count else 0.0

    direct_rows = int(len(combined)) if not combined.empty else 0
    pit_columns = [column for column in combined.columns if column.endswith("utc") or column.endswith("_flag") or column.endswith("_pct")]
    pit_valid_rows = 0
    if not combined.empty:
        if "interval_timestamp_utc" in combined.columns:
            pit_valid_rows = int(pd.to_datetime(combined["interval_timestamp_utc"], utc=True, errors="coerce").notna().sum())
        else:
            pit_valid_rows = direct_rows
    summary = {
        "repo_root": str(repo_root),
        "capability": "Capability 1 — Market State Completion",
        "datasets_total": total_count,
        "datasets_available_or_derived": available_count,
        "datasets_external_gap": int((inventory["status"] == "EXTERNAL_GAP").sum()) if not inventory.empty else 0,
        "completion_pct": completion_pct,
        "combined_rows": direct_rows,
        "combined_pit_valid_rows": pit_valid_rows,
        "combined_pit_valid_pct": round((pit_valid_rows / direct_rows * 100.0), 2) if direct_rows else 0.0,
        "combined_columns": int(len(combined.columns)) if not combined.empty else 0,
        "pit_markers_observed": ",".join(sorted(set(pit_columns))) if pit_columns else "",
    }

    return Capability1Result(
        combined_market_state=combined,
        inventory=inventory,
        source_availability=source_availability,
        summary=summary,
    )


def write_capability1_artifacts(repo_root: Path, output_dir: Path) -> Capability1Result:
    result = build_capability1_market_state(repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = output_dir / "capability1_market_state_inventory.csv"
    source_path = output_dir / "capability1_source_availability.csv"
    combined_path = output_dir / "capability1_combined_market_state.csv"
    summary_path = output_dir / "capability1_market_state_summary.json"

    result.inventory.to_csv(inventory_path, index=False)
    result.source_availability.to_csv(source_path, index=False)
    result.combined_market_state.to_csv(combined_path, index=False)
    summary_path.write_text(json.dumps(result.summary, indent=2) + "\n", encoding="utf-8")

    return result
