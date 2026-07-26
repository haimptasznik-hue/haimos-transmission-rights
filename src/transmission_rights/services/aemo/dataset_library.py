from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


AEMO_MARKET_TZ = ZoneInfo("Australia/Brisbane")


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    display_name: str
    category: str
    source_type: str
    data_path: str
    timestamp_column: str
    timestamp_timezone: str
    point_in_time_safe: bool
    refresh_frequency: str
    description: str
    commercial_applications: str
    default_join_keys: tuple[str, ...] = ("interval_timestamp_utc",)
    value_columns: tuple[str, ...] = ()
    timestamp_aliases: tuple[str, ...] = ()
    data_glob: str | None = None


def normalize_aemo_timestamp_series(
    series: pd.Series,
    *,
    source_timezone: str = "Australia/Brisbane",
    floor_minutes: int = 5,
) -> pd.Series:
    parsed = pd.to_datetime(series, utc=False, errors="coerce")

    if getattr(parsed.dt, "tz", None) is None:
        parsed = parsed.dt.tz_localize(ZoneInfo(source_timezone), ambiguous="NaT", nonexistent="NaT")

    parsed = parsed.dt.tz_convert("UTC")
    return parsed.dt.floor(f"{floor_minutes}min")


def load_normalized_dataset(
    spec: DatasetSpec,
    *,
    repo_root: Path,
    selected_columns: list[str] | None = None,
) -> pd.DataFrame:
    def _resolve_paths() -> list[Path]:
        if spec.data_glob:
            return sorted(repo_root.glob(spec.data_glob))
        file_path = Path(spec.data_path)
        if not file_path.is_absolute():
            file_path = repo_root / file_path
        return [file_path]

    paths = _resolve_paths()
    if not paths:
        raise FileNotFoundError(
            f"No files found for dataset {spec.dataset_id}. data_path={spec.data_path!r} data_glob={spec.data_glob!r}"
        )
    frame = pd.concat([pd.read_csv(path, low_memory=False) for path in paths], ignore_index=True)
    timestamp_candidates = [spec.timestamp_column, *spec.timestamp_aliases]
    source_timestamp_column = next((column for column in timestamp_candidates if column in frame.columns), None)
    if source_timestamp_column is None:
        raise KeyError(
            f"Dataset {spec.dataset_id} missing timestamp column. Tried {timestamp_candidates!r}"
        )

    frame = frame.copy()
    frame["interval_timestamp_utc"] = normalize_aemo_timestamp_series(
        frame[source_timestamp_column],
        source_timezone=spec.timestamp_timezone,
    )
    frame = frame[frame["interval_timestamp_utc"].notna()].copy()
    frame["interval_timestamp_utc"] = frame["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    keep_columns = ["interval_timestamp_utc"]
    candidate_columns = selected_columns if selected_columns is not None else list(spec.value_columns)
    for column in candidate_columns:
        if column in frame.columns and column not in keep_columns:
            keep_columns.append(column)

    if selected_columns is None and not spec.value_columns:
        keep_columns.extend([column for column in frame.columns if column not in keep_columns])

    return frame[keep_columns].drop_duplicates().reset_index(drop=True)


def build_dataset_catalog(repo_root: Path) -> list[DatasetSpec]:
    return [
        DatasetSpec(
            dataset_id="market_state",
            display_name="Market State Table",
            category="Market State",
            source_type="AEMO-derived",
            data_path="reports/phase5c_market_state.csv",
            timestamp_column="interval_timestamp_utc",
            timestamp_timezone="UTC",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Unified market-state table built from AEMO dispatch sources.",
            commercial_applications="SRA valuation|Congestion forecasting|BESS dispatch",
            value_columns=(
                "nsw_qld_spread",
                "mw_flow",
                "available_capability_mw",
                "utilisation_pct",
                "constraint_binding_flag",
                "regional_operational_demand",
                "irsr",
            ),
            timestamp_aliases=("interval_timestamp", "SETTLEMENTDATE"),
        ),
        DatasetSpec(
            dataset_id="exp_001_prepared",
            display_name="EXP_001 Prepared Dataset",
            category="Research Experiment",
            source_type="AEMO-derived",
            data_path="reports/EXP_001_PREPARED_DATA.csv",
            timestamp_column="interval_timestamp_utc",
            timestamp_timezone="UTC",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Prepared interval dataset for the first market-physics law experiment.",
            commercial_applications="Research only|Congestion mechanism analysis",
            value_columns=(
                "demand_nsw_mw",
                "demand_qld_mw",
                "generation_nsw_mw",
                "generation_qld_mw",
                "net_balance_nsw_mw",
                "net_balance_qld_mw",
                "balance_difference_mw",
                "qni_flow_mw",
                "qni_utilisation_pct",
            ),
            timestamp_aliases=(
                "interval_timestamp",
                "SETTLEMENTDATE",
                "settlement_timestamp_utc",
                "settlement_ts",
                "settlementdate",
            ),
        ),
        DatasetSpec(
            dataset_id="dispatchconstraint",
            display_name="DISPATCHCONSTRAINT (cached)",
            category="Constraints",
            source_type="AEMO raw cache",
            data_path="data/raw/aemo/mmsdm_dispatchconstraint/.cache/PUBLIC_DVD_DISPATCHCONSTRAINT_202401010000.dispatchconstraint.csv.gz",
            timestamp_column="SETTLEMENTDATE",
            timestamp_timezone="Australia/Brisbane",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Constraint-level dispatch records used to derive interval-level binding and severity signals.",
            commercial_applications="SRA valuation|Congestion forecasting|Transmission planning",
            value_columns=("CONSTRAINTID", "MARGINALVALUE", "VIOLATIONDEGREE"),
            timestamp_aliases=("interval_timestamp", "interval_timestamp_utc"),
            data_glob="data/raw/aemo/mmsdm_dispatchconstraint/.cache/**/*.dispatchconstraint.csv.gz",
        ),
        DatasetSpec(
            dataset_id="dispatch_unit_scada",
            display_name="DISPATCH_UNIT_SCADA (cached)",
            category="Generation / DUID",
            source_type="AEMO raw cache",
            data_path="data/raw/aemo/mmsdm_dispatch_unit_scada/.cache/PUBLIC_DVD_DISPATCH_UNIT_SCADA_202401010000.dispatch_unit_scada.csv.gz",
            timestamp_column="SETTLEMENTDATE",
            timestamp_timezone="Australia/Brisbane",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Unit-level SCADA dispatch telemetry normalized from AEMO DISPATCH_UNIT_SCADA archives.",
            commercial_applications="Congestion forecasting|BESS dispatch|Renewable valuation|SRA valuation",
            value_columns=("DUID", "SCADA_MW", "REGIONID"),
            timestamp_aliases=("interval_timestamp", "interval_timestamp_utc", "settlementdate"),
            data_glob="data/raw/aemo/mmsdm_dispatch_unit_scada/.cache/*.dispatch_unit_scada.csv.gz",
        ),
        DatasetSpec(
            dataset_id="dispatchregionsum",
            display_name="DISPATCHREGIONSUM (cached)",
            category="Regional Aggregates",
            source_type="AEMO raw cache",
            data_path="data/raw/aemo/mmsdm_dispatchregionsum/.cache/PUBLIC_DVD_DISPATCHREGIONSUM_202401010000.dispatchregionsum.csv.gz",
            timestamp_column="SETTLEMENTDATE",
            timestamp_timezone="Australia/Brisbane",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Regional demand, net interchange, and price target aggregates from AEMO dispatch.",
            commercial_applications="Demand forecasting|Interconnector flow prediction|Regional price targeting|SRA valuation",
            value_columns=("REGIONID", "TOTAL_DEMAND_MW", "NET_INTERCHANGE_MW", "PRICE_TARGET"),
            timestamp_aliases=("interval_timestamp", "interval_timestamp_utc", "settlementdate"),
            data_glob="data/raw/aemo/mmsdm_dispatchregionsum/.cache/**/*.dispatchregionsum.csv.gz",
        ),
        DatasetSpec(
            dataset_id="dispatchinterconnectorres",
            display_name="DISPATCHINTERCONNECTORRES (cached)",
            category="Interconnector Results",
            source_type="AEMO raw cache",
            data_path="data/raw/aemo/mmsdm_dispatchinterconnectorres/.cache/PUBLIC_DVD_DISPATCHINTERCONNECTORRES_202401010000.dispatchinterconnectorres.csv.gz",
            timestamp_column="SETTLEMENTDATE",
            timestamp_timezone="Australia/Brisbane",
            point_in_time_safe=True,
            refresh_frequency="5-minute historical",
            description="Interconnector flow results and losses normalized from AEMO dispatch archives.",
            commercial_applications="Flow forecasting|Congestion localization|Transmission routing|SRA valuation",
            value_columns=("INTERCONNECTORID", "FLOW_MW", "LOSSES_MW"),
            timestamp_aliases=("interval_timestamp", "interval_timestamp_utc", "settlementdate"),
            data_glob="data/raw/aemo/mmsdm_dispatchinterconnectorres/.cache/**/*.dispatchinterconnectorres.csv.gz",
        ),
    ]


def dataset_catalog_frame(repo_root: Path) -> pd.DataFrame:
    return pd.DataFrame([asdict(spec) for spec in build_dataset_catalog(repo_root)])


def build_correlation_ready_table(
    *,
    repo_root: Path,
    dataset_ids: list[str] | None = None,
) -> pd.DataFrame:
    catalog = {spec.dataset_id: spec for spec in build_dataset_catalog(repo_root)}
    selected_ids = dataset_ids or list(catalog.keys())
    combined: pd.DataFrame | None = None

    def _resolve_spec_paths(spec: DatasetSpec) -> list[Path]:
        if spec.data_glob:
            return sorted(repo_root.glob(spec.data_glob))
        file_path = Path(spec.data_path)
        if not file_path.is_absolute():
            file_path = repo_root / file_path
        return [file_path]

    for dataset_id in selected_ids:
        spec = catalog[dataset_id]
        try:
            if dataset_id == "dispatch_unit_scada":
                paths = _resolve_spec_paths(spec)
                if not paths:
                    continue
                grouped_parts: list[pd.DataFrame] = []
                for path in paths:
                    raw = pd.read_csv(path, low_memory=False)
                    timestamp_candidates = [spec.timestamp_column, *spec.timestamp_aliases]
                    source_ts = next((column for column in timestamp_candidates if column in raw.columns), None)
                    if source_ts is None:
                        continue
                    working = raw.copy()
                    working["interval_timestamp_utc"] = normalize_aemo_timestamp_series(
                        working[source_ts],
                        source_timezone=spec.timestamp_timezone,
                    )
                    working = working[working["interval_timestamp_utc"].notna()].copy()
                    working["interval_timestamp_utc"] = working["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    working["SCADA_MW"] = pd.to_numeric(working.get("SCADA_MW"), errors="coerce").fillna(0.0)
                    grouped_parts.append(
                        working.groupby("interval_timestamp_utc", as_index=False).agg(
                            dispatch_unit_scada_duid_count=("DUID", "nunique"),
                            dispatch_unit_scada_total_mw=("SCADA_MW", "sum"),
                            dispatch_unit_scada_abs_total_mw=("SCADA_MW", lambda s: float(s.abs().sum())),
                            dispatch_unit_scada_mean_mw=("SCADA_MW", "mean"),
                            dispatch_unit_scada_positive_mw=("SCADA_MW", lambda s: float(s[s > 0].sum())),
                            dispatch_unit_scada_negative_mw=("SCADA_MW", lambda s: float(s[s < 0].sum())),
                        )
                    )
                if not grouped_parts:
                    continue
                frame = pd.concat(grouped_parts, ignore_index=True)
                frame = frame.groupby("interval_timestamp_utc", as_index=False).agg(
                    dispatch_unit_scada_duid_count=("dispatch_unit_scada_duid_count", "max"),
                    dispatch_unit_scada_total_mw=("dispatch_unit_scada_total_mw", "sum"),
                    dispatch_unit_scada_abs_total_mw=("dispatch_unit_scada_abs_total_mw", "sum"),
                    dispatch_unit_scada_mean_mw=("dispatch_unit_scada_mean_mw", "mean"),
                    dispatch_unit_scada_positive_mw=("dispatch_unit_scada_positive_mw", "sum"),
                    dispatch_unit_scada_negative_mw=("dispatch_unit_scada_negative_mw", "sum"),
                )
                frame["dispatch_unit_scada_active_units"] = frame["dispatch_unit_scada_duid_count"] > 0
            else:
                frame = load_normalized_dataset(spec, repo_root=repo_root)
        except FileNotFoundError:
            continue

        if dataset_id == "dispatchconstraint":
            working = frame.copy()
            working["MARGINALVALUE"] = pd.to_numeric(working.get("MARGINALVALUE"), errors="coerce").fillna(0.0)
            working["VIOLATIONDEGREE"] = pd.to_numeric(working.get("VIOLATIONDEGREE"), errors="coerce").fillna(0.0)
            grouped = (
                working.groupby("interval_timestamp_utc", as_index=False)
                .agg(
                    dispatchconstraint_constraint_count=("CONSTRAINTID", "nunique"),
                    dispatchconstraint_binding_count=("MARGINALVALUE", lambda s: int((s > 0).sum())),
                    dispatchconstraint_violation_count=("VIOLATIONDEGREE", lambda s: int((s > 0).sum())),
                    dispatchconstraint_max_marginal_value=("MARGINALVALUE", "max"),
                    dispatchconstraint_mean_marginal_value=("MARGINALVALUE", "mean"),
                    dispatchconstraint_max_violation_degree=("VIOLATIONDEGREE", "max"),
                )
            )
            grouped["dispatchconstraint_binding_flag"] = grouped[
                "dispatchconstraint_binding_count"
            ] > 0
            frame = grouped

        if dataset_id == "dispatchregionsum":
            working = frame.copy()
            working["TOTAL_DEMAND_MW"] = pd.to_numeric(working.get("TOTAL_DEMAND_MW"), errors="coerce").fillna(0.0)
            working["NET_INTERCHANGE_MW"] = pd.to_numeric(working.get("NET_INTERCHANGE_MW"), errors="coerce").fillna(0.0)
            working["PRICE_TARGET"] = pd.to_numeric(working.get("PRICE_TARGET"), errors="coerce").fillna(0.0)
            grouped = (
                working.groupby("interval_timestamp_utc", as_index=False)
                .agg(
                    dispatchregionsum_region_count=("REGIONID", "nunique"),
                    dispatchregionsum_total_demand_mw=("TOTAL_DEMAND_MW", "sum"),
                    dispatchregionsum_mean_demand_mw=("TOTAL_DEMAND_MW", "mean"),
                    dispatchregionsum_net_interchange_mw=("NET_INTERCHANGE_MW", "sum"),
                    dispatchregionsum_mean_price_target=("PRICE_TARGET", "mean"),
                    dispatchregionsum_max_price_target=("PRICE_TARGET", "max"),
                )
            )
            frame = grouped

        if dataset_id == "dispatchinterconnectorres":
            working = frame.copy()
            working["FLOW_MW"] = pd.to_numeric(working.get("FLOW_MW"), errors="coerce").fillna(0.0)
            working["LOSSES_MW"] = pd.to_numeric(working.get("LOSSES_MW"), errors="coerce").fillna(0.0)
            grouped = (
                working.groupby("interval_timestamp_utc", as_index=False)
                .agg(
                    dispatchinterconnectorres_interconnector_count=("INTERCONNECTORID", "nunique"),
                    dispatchinterconnectorres_net_flow_mw=("FLOW_MW", "sum"),
                    dispatchinterconnectorres_total_abs_flow_mw=("FLOW_MW", lambda s: float(s.abs().sum())),
                    dispatchinterconnectorres_mean_flow_mw=("FLOW_MW", "mean"),
                    dispatchinterconnectorres_total_losses_mw=("LOSSES_MW", "sum"),
                )
            )
            frame = grouped

        rename_map = {
            column: f"{dataset_id}__{column}"
            for column in frame.columns
            if column != "interval_timestamp_utc"
        }
        frame = frame.rename(columns=rename_map)
        if combined is None:
            combined = frame
        else:
            combined = combined.merge(frame, on="interval_timestamp_utc", how="outer")

    if combined is None:
        return pd.DataFrame(columns=["interval_timestamp_utc"])

    return combined.sort_values("interval_timestamp_utc").reset_index(drop=True)