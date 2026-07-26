from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .price_model_v2 import quarter_to_components


@dataclass(frozen=True)
class DataSourceRequirement:
    source_name: str
    priority: int
    required: bool
    glob_patterns: tuple[str, ...]
    required_columns: tuple[str, ...]
    description: str


REQUIRED_SOURCES: tuple[DataSourceRequirement, ...] = (
    DataSourceRequirement(
        source_name="DISPATCHPRICE",
        priority=1,
        required=True,
        glob_patterns=(
            "data/raw/aemo/**/DISPATCHPRICE*.csv",
            "data/derived/aemo/**/dispatchprice*.csv",
            "data/**/dispatch_price*.csv",
        ),
        required_columns=("SETTLEMENTDATE", "REGIONID", "RRP"),
        description="Regional reference prices by interval; needed for spread forecast.",
    ),
    DataSourceRequirement(
        source_name="DISPATCHINTERCONNECTORRES",
        priority=2,
        required=True,
        glob_patterns=(
            "data/raw/aemo/**/DISPATCHINTERCONNECTORRES*.csv",
            "data/derived/aemo/**/dispatchinterconnectorres*.csv",
            "data/**/interconnector_flow*.csv",
        ),
        required_columns=("SETTLEMENTDATE", "INTERCONNECTORID", "MWFLOW"),
        description="Interconnector directional flow and utilisation inputs.",
    ),
    DataSourceRequirement(
        source_name="DISPATCHCONSTRAINT",
        priority=4,
        required=False,
        glob_patterns=(
            "data/raw/aemo/**/DISPATCHCONSTRAINT*.csv",
            "data/derived/aemo/**/dispatchconstraint*.csv",
            "data/**/constraint_binding*.csv",
        ),
        required_columns=("SETTLEMENTDATE", "CONSTRAINTID", "MARGINALVALUE"),
        description="Constraint frequency and marginal values.",
    ),
    DataSourceRequirement(
        source_name="REGIONAL_DEMAND",
        priority=3,
        required=True,
        glob_patterns=(
            "data/raw/aemo/**/DISPATCHREGIONSUM*.csv",
            "data/derived/aemo/**/regional_demand*.csv",
            "data/**/regional_demand*.csv",
        ),
        required_columns=("SETTLEMENTDATE", "REGIONID", "TOTALDEMAND"),
        description="Regional demand/load signals.",
    ),
    DataSourceRequirement(
        source_name="DUID_GENERATION",
        priority=5,
        required=False,
        glob_patterns=(
            "data/raw/aemo/**/DISPATCHLOAD*.csv",
            "data/derived/aemo/**/duid_generation*.csv",
            "data/**/dispatchload*.csv",
        ),
        required_columns=("SETTLEMENTDATE", "DUID", "TOTALCLEARED"),
        description="Unit output and fuel aggregation features.",
    ),
)


def discover_files(repo_root: Path, patterns: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(repo_root.glob(pattern))
    deduped = sorted({path.resolve() for path in found if path.is_file()})
    return deduped


def validate_source_columns(file_path: Path, required_columns: tuple[str, ...]) -> tuple[bool, str, list[str]]:
    try:
        frame = pd.read_csv(file_path, nrows=5)
    except Exception as exc:
        return False, f"read_error: {exc}", []
    cols = frame.columns.astype(str).tolist()
    upper_cols = {column.upper() for column in cols}
    missing = [column for column in required_columns if column.upper() not in upper_cols]
    if missing:
        return False, f"missing_columns: {missing}", cols
    return True, "ok", cols


def assess_source_availability(repo_root: Path) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for requirement in REQUIRED_SOURCES:
        files = discover_files(repo_root, requirement.glob_patterns)
        if not files:
            records.append(
                {
                    "source_name": requirement.source_name,
                    "priority": requirement.priority,
                    "required": requirement.required,
                    "status": "MISSING",
                    "file_path": "",
                    "column_check": "no_files_found",
                    "description": requirement.description,
                }
            )
            continue
        any_valid = False
        for file_path in files:
            ok, message, columns = validate_source_columns(file_path, requirement.required_columns)
            if ok:
                any_valid = True
                records.append(
                    {
                        "source_name": requirement.source_name,
                        "priority": requirement.priority,
                        "required": requirement.required,
                        "status": "AVAILABLE",
                        "file_path": str(file_path),
                        "column_check": "ok",
                        "description": requirement.description,
                        "columns": ",".join(columns),
                    }
                )
            else:
                records.append(
                    {
                        "source_name": requirement.source_name,
                        "priority": requirement.priority,
                        "required": requirement.required,
                        "status": "INVALID_SCHEMA",
                        "file_path": str(file_path),
                        "column_check": message,
                        "description": requirement.description,
                    }
                )
        if not any_valid:
            records.append(
                {
                    "source_name": requirement.source_name,
                    "priority": requirement.priority,
                    "required": requirement.required,
                    "status": "MISSING_VALID_SCHEMA",
                    "file_path": "",
                    "column_check": "no_schema_match",
                    "description": requirement.description,
                }
            )

    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    return frame.sort_values(["priority", "source_name", "status", "file_path"]).reset_index(drop=True)


def _quarter_sort_key(quarter: str) -> tuple[int, int]:
    year, quarter_no = quarter_to_components(str(quarter))
    return year, quarter_no


def build_nsw1_qld1_stub_feature_store(alpha_database: pd.DataFrame) -> pd.DataFrame:
    frame = alpha_database.copy()
    mask = (
        frame["interconnector_id"].astype(str).eq("NSW1-QLD1")
        & frame["from_region"].astype(str).isin(["NSW1", "QLD1"])
    )
    corridor = frame.loc[mask].copy()
    if corridor.empty:
        return pd.DataFrame(
            columns=[
                "decision_cutoff",
                "quarter",
                "corridor",
                "direction",
                "ruleset_id",
                "source_file",
                "publish_timestamp",
                "pit_valid",
                "regional_spread_forecast",
                "directional_flow_forecast",
                "utilisation_forecast",
                "digital_twin_payout_forecast",
                "actual_payout",
                "notes",
            ]
        )

    corridor["decision_timestamp"] = pd.to_datetime(corridor["decision_timestamp"], utc=True, errors="coerce")
    corridor = corridor.sort_values(["quarter", "tranche_no", "from_region", "decision_timestamp"])

    output = pd.DataFrame(
        {
            "decision_cutoff": corridor["decision_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quarter": corridor["quarter"].astype(str),
            "corridor": "NSW1-QLD1",
            "direction": corridor["from_region"].astype(str),
            "ruleset_id": corridor.get("ruleset_id", "").astype(str),
            "source_file": "data/derived/sra/alpha_database.csv",
            "publish_timestamp": corridor["decision_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pit_valid": False,
            "regional_spread_forecast": pd.NA,
            "directional_flow_forecast": pd.NA,
            "utilisation_forecast": pd.NA,
            "digital_twin_payout_forecast": pd.NA,
            "actual_payout": corridor["final_realised_payout_per_unit"],
            "notes": "Stub row only; requires DISPATCHPRICE + DISPATCHINTERCONNECTORRES ingestion before physical forecasts.",
        }
    )
    return output.sort_values("quarter", key=lambda s: s.map(_quarter_sort_key)).reset_index(drop=True)


def build_pit_coverage_report(source_status: pd.DataFrame, feature_store: pd.DataFrame) -> pd.DataFrame:
    required_sources = source_status[source_status["required"] == True] if not source_status.empty else pd.DataFrame()
    available_required = required_sources[required_sources["status"] == "AVAILABLE"]["source_name"].nunique() if not required_sources.empty else 0
    required_count = required_sources["source_name"].nunique() if not required_sources.empty else 0

    pit_rows = int(len(feature_store))
    pit_valid_rows = int(feature_store["pit_valid"].fillna(False).sum()) if pit_rows else 0

    return pd.DataFrame(
        [
            {
                "metric": "required_sources_available",
                "value": available_required,
            },
            {
                "metric": "required_sources_total",
                "value": required_count,
            },
            {
                "metric": "required_source_coverage_pct",
                "value": round((available_required / required_count * 100.0), 2) if required_count else 0.0,
            },
            {
                "metric": "feature_rows_total",
                "value": pit_rows,
            },
            {
                "metric": "feature_rows_pit_valid",
                "value": pit_valid_rows,
            },
            {
                "metric": "feature_rows_pit_valid_pct",
                "value": round((pit_valid_rows / pit_rows * 100.0), 2) if pit_rows else 0.0,
            },
        ]
    )


def compute_phase5c_verdict(source_status: pd.DataFrame) -> str:
    if source_status.empty:
        return "INSUFFICIENT_DATA"
    required = source_status[source_status["required"] == True]
    required_names = set(required["source_name"].tolist())
    available_required = set(required[required["status"] == "AVAILABLE"]["source_name"].tolist())
    if required_names.issubset(available_required):
        return "READY_FOR_MODELLING"
    return "INSUFFICIENT_DATA"
