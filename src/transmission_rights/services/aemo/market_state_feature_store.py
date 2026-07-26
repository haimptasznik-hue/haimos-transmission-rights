from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .market_state_database import MARKET_STATE_SCHEMA


CORE_FEATURE_COLUMNS: tuple[str, ...] = (
    "nsw_rrp",
    "qld_rrp",
    "nsw_qld_spread",
    "mw_flow",
    "available_capability_mw",
    "utilisation_pct",
    "constraint_binding_flag",
    "regional_operational_demand",
)


@dataclass(frozen=True)
class FeatureDefinition:
    feature_name: str
    category: str
    tier: int
    units: str
    data_source: str
    point_in_time_availability: str
    refresh_frequency: str
    confidence: str
    commercial_applications: str


RAW_FEATURE_DEFINITIONS: dict[str, FeatureDefinition] = {
    "interval_timestamp_utc": FeatureDefinition("interval_timestamp_utc", "Calendar", 1, "UTC timestamp", "Market State Database", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "asof_publish_timestamp_utc": FeatureDefinition("asof_publish_timestamp_utc", "Metadata", 1, "UTC timestamp", "Market State Database", "Historical PIT-safe", "Ingestion event", "High", "Auditability|Replay"),
    "decision_cutoff_utc": FeatureDefinition("decision_cutoff_utc", "Metadata", 1, "UTC timestamp", "Market State Database", "Historical PIT-safe", "Decision event", "High", "Replay|Forecast governance"),
    "record_version": FeatureDefinition("record_version", "Metadata", 1, "count", "Market State Database", "Historical PIT-safe", "Correction event", "High", "Auditability"),
    "record_source": FeatureDefinition("record_source", "Metadata", 1, "path", "Market State Database", "Historical PIT-safe", "File event", "High", "Auditability"),
    "corridor": FeatureDefinition("corridor", "Network", 1, "label", "Market State Database", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting|SRA valuation"),
    "direction": FeatureDefinition("direction", "Network", 1, "label", "Market State Database", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting|SRA valuation"),
    "ruleset_id": FeatureDefinition("ruleset_id", "Metadata", 1, "identifier", "Market State Database", "Historical PIT-safe", "Ruleset event", "Medium", "SRA valuation|Replay"),
    "nsw_rrp": FeatureDefinition("nsw_rrp", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting"),
    "qld_rrp": FeatureDefinition("qld_rrp", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting"),
    "vic_rrp": FeatureDefinition("vic_rrp", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting"),
    "sa_rrp": FeatureDefinition("sa_rrp", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting"),
    "tas_rrp": FeatureDefinition("tas_rrp", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting"),
    "nsw_qld_spread": FeatureDefinition("nsw_qld_spread", "Economics", 4, "AUD/MWh", "DISPATCHPRICE", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting"),
    "mw_flow": FeatureDefinition("mw_flow", "Network", 1, "MW", "DISPATCHINTERCONNECTORRES", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting|BESS dispatch"),
    "available_capability_mw": FeatureDefinition("available_capability_mw", "Network", 1, "MW", "DISPATCHINTERCONNECTORRES", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting|Transmission planning"),
    "utilisation_pct": FeatureDefinition("utilisation_pct", "Network", 1, "%", "DISPATCHINTERCONNECTORRES", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting|BESS dispatch"),
    "interconnector_stress_index": FeatureDefinition("interconnector_stress_index", "Derived", 1, "0-1 score", "Market State Database", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting|SRA valuation"),
    "constraint_binding_flag": FeatureDefinition("constraint_binding_flag", "Constraints", 1, "boolean", "DISPATCHCONSTRAINT", "Historical PIT-safe", "5-minute", "Medium", "SRA valuation|Congestion forecasting|Transmission planning"),
    "constraint_marginal_value": FeatureDefinition("constraint_marginal_value", "Constraints", 1, "AUD/MWh or shadow value", "DISPATCHCONSTRAINT", "Historical PIT-safe", "5-minute", "Medium", "SRA valuation|Congestion forecasting"),
    "constraint_time_at_limit_pct": FeatureDefinition("constraint_time_at_limit_pct", "Constraints", 1, "%", "DISPATCHCONSTRAINT", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting"),
    "constraint_duration_intervals": FeatureDefinition("constraint_duration_intervals", "Constraints", 1, "interval count", "DISPATCHCONSTRAINT", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting"),
    "constraint_recurrence_count": FeatureDefinition("constraint_recurrence_count", "Constraints", 1, "count", "DISPATCHCONSTRAINT", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting"),
    "regional_operational_demand": FeatureDefinition("regional_operational_demand", "Demand", 1, "MW", "DISPATCHREGIONSUM", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting|Renewable valuation"),
    "forecast_demand": FeatureDefinition("forecast_demand", "Demand", 1, "MW", "Demand forecast source", "Decision-time available", "5-minute", "Medium", "Forecasting|BESS dispatch"),
    "demand_anomaly": FeatureDefinition("demand_anomaly", "Demand", 1, "MW", "Derived from demand history", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting|Renewable valuation"),
    "demand_short_term_change": FeatureDefinition("demand_short_term_change", "Demand", 1, "MW", "Derived from demand history", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting"),
    "demand_ramp": FeatureDefinition("demand_ramp", "Demand", 1, "MW/hour proxy", "Derived from demand history", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting|BESS dispatch"),
    "renewable_penetration_pct": FeatureDefinition("renewable_penetration_pct", "Generation", 1, "%", "Derived generation mix", "Historical PIT-safe", "5-minute", "Medium", "Congestion forecasting|Renewable valuation"),
    "coal_availability_pct": FeatureDefinition("coal_availability_pct", "Generation", 1, "%", "Derived generation mix", "Historical PIT-safe", "5-minute", "Medium", "SRA valuation|Congestion forecasting"),
    "gas_availability_pct": FeatureDefinition("gas_availability_pct", "Generation", 1, "%", "Derived generation mix", "Historical PIT-safe", "5-minute", "Medium", "SRA valuation|Congestion forecasting"),
    "battery_net_dispatch_mw": FeatureDefinition("battery_net_dispatch_mw", "Batteries", 3, "MW", "Battery dispatch source", "Historical PIT-safe", "5-minute", "Medium", "BESS dispatch|Congestion forecasting"),
    "temperature_c": FeatureDefinition("temperature_c", "Weather", 2, "°C", "Weather source", "Historical PIT-safe", "5-minute to hourly", "Medium", "Demand forecasting|Renewable valuation"),
    "wind_speed_ms": FeatureDefinition("wind_speed_ms", "Weather", 2, "m/s", "Weather source", "Historical PIT-safe", "5-minute to hourly", "Medium", "Renewable valuation|Congestion forecasting"),
    "solar_irradiance_wm2": FeatureDefinition("solar_irradiance_wm2", "Weather", 2, "W/m²", "Weather source", "Historical PIT-safe", "5-minute to hourly", "Medium", "Renewable valuation|Congestion forecasting"),
    "rainfall_mm": FeatureDefinition("rainfall_mm", "Weather", 2, "mm", "Weather source", "Historical PIT-safe", "Hourly/daily", "Low", "Hydro valuation|Context"),
    "network_outage_flag": FeatureDefinition("network_outage_flag", "Outages", 3, "boolean", "Network outage source", "Historical PIT-safe", "Event-driven", "Medium", "Transmission planning|Congestion forecasting"),
    "irsr": FeatureDefinition("irsr", "Economics", 4, "AUD", "IRSR engine", "Closed-settlement historical", "5-minute", "High", "SRA valuation"),
    "sra_payout_per_unit": FeatureDefinition("sra_payout_per_unit", "Economics", 4, "AUD/unit", "SRA settlement source", "Closed-settlement historical", "Quarterly", "High", "SRA valuation"),
    "auction_clearing_price": FeatureDefinition("auction_clearing_price", "Economics", 4, "AUD/unit", "Auction source", "Auction-time historical", "Quarterly", "High", "SRA valuation"),
    "units_sold": FeatureDefinition("units_sold", "Economics", 4, "units", "Auction source", "Auction-time historical", "Quarterly", "High", "SRA valuation"),
}


DERIVED_FEATURE_DEFINITIONS: dict[str, FeatureDefinition] = {
    "interval_year": FeatureDefinition("interval_year", "Calendar", 1, "year", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "interval_month": FeatureDefinition("interval_month", "Calendar", 1, "month number", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "interval_day": FeatureDefinition("interval_day", "Calendar", 1, "day of month", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "interval_hour": FeatureDefinition("interval_hour", "Calendar", 1, "hour", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "interval_minute": FeatureDefinition("interval_minute", "Calendar", 1, "minute", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "interval_quarter_label": FeatureDefinition("interval_quarter_label", "Calendar", 1, "quarter label", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "day_of_week_index": FeatureDefinition("day_of_week_index", "Calendar", 1, "0=Mon..6=Sun", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "day_of_week_name": FeatureDefinition("day_of_week_name", "Calendar", 1, "weekday name", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "is_weekend": FeatureDefinition("is_weekend", "Calendar", 1, "boolean", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "australian_season": FeatureDefinition("australian_season", "Calendar", 1, "season label", "Derived from interval timestamp", "Historical PIT-safe", "5-minute", "High", "All applications"),
    "abs_nsw_qld_spread": FeatureDefinition("abs_nsw_qld_spread", "Derived", 1, "AUD/MWh", "Derived from nsw_qld_spread", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting"),
    "abs_mw_flow": FeatureDefinition("abs_mw_flow", "Derived", 1, "MW", "Derived from mw_flow", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting"),
    "flow_direction_sign": FeatureDefinition("flow_direction_sign", "Derived", 1, "-1/0/1", "Derived from mw_flow", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting|BESS dispatch"),
    "flow_direction_label": FeatureDefinition("flow_direction_label", "Derived", 1, "label", "Derived from mw_flow", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting|BESS dispatch"),
    "available_headroom_mw": FeatureDefinition("available_headroom_mw", "Derived", 1, "MW", "Derived from capability and flow", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting|Transmission planning"),
    "available_headroom_pct": FeatureDefinition("available_headroom_pct", "Derived", 1, "%", "Derived from utilisation_pct", "Historical PIT-safe", "5-minute", "High", "SRA valuation|Congestion forecasting|Transmission planning"),
    "constraint_binding_int": FeatureDefinition("constraint_binding_int", "Derived", 1, "0/1", "Derived from constraint_binding_flag", "Historical PIT-safe", "5-minute", "High", "Congestion forecasting"),
    "network_outage_int": FeatureDefinition("network_outage_int", "Derived", 3, "0/1", "Derived from network_outage_flag", "Historical PIT-safe", "5-minute", "High", "Transmission planning|Congestion forecasting"),
    "market_state_core_non_null_count": FeatureDefinition("market_state_core_non_null_count", "Derived", 1, "count", "Derived from core features", "Historical PIT-safe", "5-minute", "High", "Auditability|Coverage"),
    "market_state_core_coverage_pct": FeatureDefinition("market_state_core_coverage_pct", "Derived", 1, "%", "Derived from core features", "Historical PIT-safe", "5-minute", "High", "Auditability|Coverage"),
}


def _schema_description_map() -> dict[str, str]:
    return {column: description for column, _dtype, description in MARKET_STATE_SCHEMA}


def _australian_season(month: pd.Series) -> pd.Series:
    season_map = {
        12: "Summer",
        1: "Summer",
        2: "Summer",
        3: "Autumn",
        4: "Autumn",
        5: "Autumn",
        6: "Winter",
        7: "Winter",
        8: "Winter",
        9: "Spring",
        10: "Spring",
        11: "Spring",
    }
    return month.map(season_map)


def _to_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin(["true", "1", "t", "yes", "y"])


def derive_market_state_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["interval_timestamp_utc"] = pd.to_datetime(output["interval_timestamp_utc"], utc=True, errors="coerce")

    numeric_columns = [
        "nsw_qld_spread",
        "mw_flow",
        "available_capability_mw",
        "utilisation_pct",
    ]
    for column in numeric_columns:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce")

    timestamps = output["interval_timestamp_utc"]
    output["interval_year"] = timestamps.dt.year
    output["interval_month"] = timestamps.dt.month
    output["interval_day"] = timestamps.dt.day
    output["interval_hour"] = timestamps.dt.hour
    output["interval_minute"] = timestamps.dt.minute
    output["interval_quarter_label"] = timestamps.dt.year.astype("Int64").astype(str) + "Q" + timestamps.dt.quarter.astype("Int64").astype(str)
    output["day_of_week_index"] = timestamps.dt.dayofweek
    output["day_of_week_name"] = timestamps.dt.day_name()
    output["is_weekend"] = timestamps.dt.dayofweek >= 5
    output["australian_season"] = _australian_season(output["interval_month"])

    if "nsw_qld_spread" in output.columns:
        output["abs_nsw_qld_spread"] = output["nsw_qld_spread"].abs()
    if "mw_flow" in output.columns:
        output["abs_mw_flow"] = output["mw_flow"].abs()
        output["flow_direction_sign"] = output["mw_flow"].fillna(0).apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
        output["flow_direction_label"] = output["flow_direction_sign"].map({1: "NSW1->QLD1", -1: "QLD1->NSW1", 0: "NO_FLOW"})
    if {"available_capability_mw", "mw_flow"}.issubset(output.columns):
        output["available_headroom_mw"] = output["available_capability_mw"] - output["mw_flow"].abs()
    if "utilisation_pct" in output.columns:
        output["available_headroom_pct"] = 100.0 - output["utilisation_pct"]
    if "constraint_binding_flag" in output.columns:
        output["constraint_binding_int"] = _to_bool_series(output["constraint_binding_flag"]).astype(int)
    if "network_outage_flag" in output.columns:
        output["network_outage_int"] = _to_bool_series(output["network_outage_flag"]).astype(int)

    available_core = [column for column in CORE_FEATURE_COLUMNS if column in output.columns]
    if available_core:
        output["market_state_core_non_null_count"] = output[available_core].notna().sum(axis=1)
        output["market_state_core_coverage_pct"] = (
            output["market_state_core_non_null_count"] / float(len(available_core)) * 100.0
        )
    else:
        output["market_state_core_non_null_count"] = 0
        output["market_state_core_coverage_pct"] = 0.0

    if pd.api.types.is_datetime64_any_dtype(output["interval_timestamp_utc"]):
        output["interval_timestamp_utc"] = output["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return output


def feature_dictionary_frame(feature_columns: list[str]) -> pd.DataFrame:
    descriptions = _schema_description_map()
    rows: list[dict[str, object]] = []
    for column in feature_columns:
        definition = RAW_FEATURE_DEFINITIONS.get(column) or DERIVED_FEATURE_DEFINITIONS.get(column)
        if definition is None:
            definition = FeatureDefinition(column, "Derived", 4, "unknown", "Unknown", "Unknown", "Unknown", "Low", "TBD")
        rows.append(
            {
                "feature_name": column,
                "category": definition.category,
                "tier": definition.tier,
                "definition": descriptions.get(column, column.replace("_", " ")),
                "units": definition.units,
                "data_source": definition.data_source,
                "point_in_time_availability": definition.point_in_time_availability,
                "refresh_frequency": definition.refresh_frequency,
                "confidence": definition.confidence,
                "commercial_applications": definition.commercial_applications,
            }
        )
    return pd.DataFrame(rows)


def build_market_state_feature_store(
    *,
    input_csv_path: Path,
    output_dir: Path,
    chunksize: int = 50_000,
    sample_rows: int = 1_000,
) -> dict[str, Path | int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_data_path = output_dir / "market_state_feature_store.csv.gz"
    output_metadata_path = output_dir / "market_state_feature_dictionary.csv"
    output_coverage_path = output_dir / "market_state_feature_coverage.csv"
    output_sample_path = output_dir / "market_state_feature_store_sample.csv"
    output_summary_path = output_dir / "market_state_feature_store_summary.json"

    row_count = 0
    feature_columns: list[str] | None = None
    non_null_counts: dict[str, int] = {}
    first_seen: dict[str, pd.Timestamp] = {}
    last_seen: dict[str, pd.Timestamp] = {}
    global_start: pd.Timestamp | None = None
    global_end: pd.Timestamp | None = None
    sample_frame: pd.DataFrame | None = None

    with gzip.open(output_data_path, "wt", encoding="utf-8", newline="") as handle:
        wrote_header = False
        for chunk in pd.read_csv(input_csv_path, chunksize=chunksize, low_memory=False):
            transformed = derive_market_state_features(chunk)
            if feature_columns is None:
                feature_columns = transformed.columns.tolist()
                non_null_counts = {column: 0 for column in feature_columns}

            if sample_frame is None:
                sample_frame = transformed.head(sample_rows).copy()

            transformed.to_csv(handle, index=False, header=not wrote_header)
            wrote_header = True

            row_count += len(transformed)
            timestamps = pd.to_datetime(transformed["interval_timestamp_utc"], utc=True, errors="coerce")
            valid_ts = timestamps.dropna()
            if not valid_ts.empty:
                chunk_start = valid_ts.min()
                chunk_end = valid_ts.max()
                global_start = chunk_start if global_start is None else min(global_start, chunk_start)
                global_end = chunk_end if global_end is None else max(global_end, chunk_end)

            for column in transformed.columns:
                mask = transformed[column].notna()
                non_null_counts[column] = non_null_counts.get(column, 0) + int(mask.sum())
                if mask.any() and not valid_ts.empty:
                    column_ts = timestamps[mask]
                    column_ts = column_ts.dropna()
                    if not column_ts.empty:
                        col_start = column_ts.min()
                        col_end = column_ts.max()
                        first_seen[column] = col_start if column not in first_seen else min(first_seen[column], col_start)
                        last_seen[column] = col_end if column not in last_seen else max(last_seen[column], col_end)

    if feature_columns is None:
        raise ValueError(f"No rows found in input file: {input_csv_path}")

    dictionary = feature_dictionary_frame(feature_columns)
    coverage_rows: list[dict[str, object]] = []
    for column in feature_columns:
        non_null = non_null_counts.get(column, 0)
        coverage_rows.append(
            {
                "feature_name": column,
                "non_null_rows": non_null,
                "coverage_pct": round((non_null / row_count * 100.0), 4) if row_count else 0.0,
                "historical_coverage_start_utc": first_seen.get(column).strftime("%Y-%m-%dT%H:%M:%SZ") if column in first_seen else "",
                "historical_coverage_end_utc": last_seen.get(column).strftime("%Y-%m-%dT%H:%M:%SZ") if column in last_seen else "",
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    dictionary = dictionary.merge(coverage, on="feature_name", how="left")

    dictionary.to_csv(output_metadata_path, index=False)
    coverage.to_csv(output_coverage_path, index=False)
    if sample_frame is not None:
        sample_frame.to_csv(output_sample_path, index=False)

    summary_payload = {
        "input_csv_path": str(input_csv_path),
        "output_data_path": str(output_data_path),
        "row_count": row_count,
        "feature_count": len(feature_columns),
        "historical_coverage_start_utc": global_start.strftime("%Y-%m-%dT%H:%M:%SZ") if global_start is not None else "",
        "historical_coverage_end_utc": global_end.strftime("%Y-%m-%dT%H:%M:%SZ") if global_end is not None else "",
    }
    output_summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    return {
        "data_path": output_data_path,
        "metadata_path": output_metadata_path,
        "coverage_path": output_coverage_path,
        "sample_path": output_sample_path,
        "summary_path": output_summary_path,
        "row_count": row_count,
        "feature_count": len(feature_columns),
        "coverage_start": summary_payload["historical_coverage_start_utc"],
        "coverage_end": summary_payload["historical_coverage_end_utc"],
    }