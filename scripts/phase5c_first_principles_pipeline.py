#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.phase5c_pipeline import (  # noqa: E402
    REQUIRED_SOURCES,
    assess_source_availability,
    build_nsw1_qld1_stub_feature_store,
    build_pit_coverage_report,
    compute_phase5c_verdict,
    discover_files,
)
from transmission_rights.services.aemo.market_state_database import (  # noqa: E402
    IngestionStalledError,
    MarketStateDatabase,
)
from transmission_rights.domain.interconnectors import Interconnector  # noqa: E402


PROFILE_STAGE_TIMEOUT_SECONDS = 30


class StageTimeoutError(RuntimeError):
    def __init__(self, stage: str, function_name: str, elapsed_seconds: float) -> None:
        self.stage = stage
        self.function_name = function_name
        self.elapsed_seconds = elapsed_seconds
        super().__init__(f"Stage '{stage}' ({function_name}) exceeded {PROFILE_STAGE_TIMEOUT_SECONDS}s")


def _memory_usage_mb() -> float | None:
    try:
        import resource

        raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if raw <= 0:
            return None
        if raw > 10_000_000:
            return round(raw / (1024 * 1024), 2)
        return round(raw / 1024, 2)
    except Exception:
        return None


def _format_elapsed(seconds: float) -> str:
    return f"{seconds:.3f}s"


def _stage_timeout_handler(signum, frame):
    raise TimeoutError("Stage execution exceeded timeout")


def _profile_stage(
    *,
    stage: str,
    function_name: str,
    run,
    profile_rows: list[dict[str, object]],
    rows_extractor=None,
    files_extractor=None,
):
    print(f"Stage: {stage} | Function: {function_name} | Status: STARTED", flush=True)
    previous_handler = signal.getsignal(signal.SIGALRM)
    start = time.perf_counter()
    signal.signal(signal.SIGALRM, _stage_timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, PROFILE_STAGE_TIMEOUT_SECONDS)

    try:
        result = run()
        elapsed = time.perf_counter() - start
        rows = rows_extractor(result) if rows_extractor else None
        files = files_extractor(result) if files_extractor else None
        profile_rows.append(
            {
                "Stage": stage,
                "Function": function_name,
                "Elapsed": _format_elapsed(elapsed),
                "Rows": rows,
                "Files": files,
                "Memory": _memory_usage_mb(),
                "Status": "OK",
            }
        )
        print(f"Stage: {stage} | Elapsed: {_format_elapsed(elapsed)} | Status: OK", flush=True)
        return result
    except TimeoutError:
        elapsed = time.perf_counter() - start
        profile_rows.append(
            {
                "Stage": stage,
                "Function": function_name,
                "Elapsed": _format_elapsed(elapsed),
                "Rows": None,
                "Files": None,
                "Memory": _memory_usage_mb(),
                "Status": "TIMEOUT_STOPPED",
            }
        )
        raise StageTimeoutError(stage=stage, function_name=function_name, elapsed_seconds=elapsed)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_stage_profile(reports_dir: Path, profile_rows: list[dict[str, object]]) -> pd.DataFrame:
    profile_df = pd.DataFrame(profile_rows, columns=["Stage", "Function", "Elapsed", "Rows", "Files", "Memory", "Status"])
    output_path = reports_dir / "phase5c_stage_profile.csv"
    profile_df.to_csv(output_path, index=False)
    print(profile_df.to_string(index=False))
    return profile_df


def _write_timeout_bottleneck_report(
    reports_dir: Path,
    timeout_error: StageTimeoutError,
    profile_rows: list[dict[str, object]],
) -> None:
    payload = {
        "status": "TIMEOUT_STOPPED",
        "policy": "Stop execution if a major function exceeds 30 seconds.",
        "bottleneck": {
            "stage": timeout_error.stage,
            "function_name": timeout_error.function_name,
            "elapsed_seconds": round(timeout_error.elapsed_seconds, 3),
        },
        "memory_mb": _memory_usage_mb(),
        "timestamp": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile_rows_recorded": len(profile_rows),
    }
    report_path = reports_dir / "phase5c_profile_bottleneck.json"
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


def _build_walkforward_stub(feature_store: pd.DataFrame, benchmark_mae: float = 8065.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "corridor": "NSW1-QLD1",
                "quarters_tested": int(feature_store["quarter"].nunique()) if not feature_store.empty else 0,
                "model_mae": pd.NA,
                "benchmark_regime_adjusted_mae": benchmark_mae,
                "beats_benchmark": False,
                "improved_quarters_count": 0,
                "no_leakage": False,
                "status": "NOT_RUN",
                "notes": "Walk-forward not run: required market data sources are missing.",
            }
        ]
    )


def _build_driver_attribution_stub(source_status: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in source_status.iterrows():
        rows.append(
            {
                "driver": row["source_name"],
                "priority": row["priority"],
                "required": row["required"],
                "status": row["status"],
                "source_path": row.get("file_path", ""),
                "attribution_ready": bool(row["status"] == "AVAILABLE"),
                "notes": row.get("description", ""),
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "driver"]).reset_index(drop=True)


def _build_ingestion_validation_report(
    source_status: pd.DataFrame,
    dispatchprice_rows_read: int,
    dispatchprice_rows_normalized: int,
    dispatchprice_rows_valid: int,
    dispatchprice_files_processed: int,
    dispatchprice_download_attempts: int,
    dispatchprice_download_successes: int,
    interconnector_rows_read: int,
    interconnector_rows_normalized: int,
    interconnector_rows_valid: int,
    interconnector_files_processed: int,
    interconnector_download_attempts: int,
    interconnector_download_successes: int,
    demand_rows_read: int,
    demand_rows_normalized: int,
    demand_rows_valid: int,
    demand_files_processed: int,
    demand_download_attempts: int,
    demand_download_successes: int,
    constraint_rows_read: int,
    constraint_rows_normalized: int,
    constraint_rows_valid: int,
    constraint_files_processed: int,
    constraint_download_attempts: int,
    constraint_download_successes: int,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": "dispatchprice_download_attempts",
                "value": dispatchprice_download_attempts,
            },
            {
                "metric": "dispatchprice_download_successes",
                "value": dispatchprice_download_successes,
            },
            {
                "metric": "dispatchprice_files_processed",
                "value": dispatchprice_files_processed,
            },
            {
                "metric": "dispatchprice_rows_read",
                "value": dispatchprice_rows_read,
            },
            {
                "metric": "dispatchprice_rows_normalized",
                "value": dispatchprice_rows_normalized,
            },
            {
                "metric": "dispatchprice_rows_valid_with_spread",
                "value": dispatchprice_rows_valid,
            },
            {
                "metric": "dispatchinterconnectorres_download_attempts",
                "value": interconnector_download_attempts,
            },
            {
                "metric": "dispatchinterconnectorres_download_successes",
                "value": interconnector_download_successes,
            },
            {
                "metric": "dispatchinterconnectorres_files_processed",
                "value": interconnector_files_processed,
            },
            {
                "metric": "dispatchinterconnectorres_rows_read",
                "value": interconnector_rows_read,
            },
            {
                "metric": "dispatchinterconnectorres_rows_normalized",
                "value": interconnector_rows_normalized,
            },
            {
                "metric": "dispatchinterconnectorres_rows_valid_with_flow",
                "value": interconnector_rows_valid,
            },
            {
                "metric": "dispatchregionsum_download_attempts",
                "value": demand_download_attempts,
            },
            {
                "metric": "dispatchregionsum_download_successes",
                "value": demand_download_successes,
            },
            {
                "metric": "dispatchregionsum_files_processed",
                "value": demand_files_processed,
            },
            {
                "metric": "dispatchregionsum_rows_read",
                "value": demand_rows_read,
            },
            {
                "metric": "dispatchregionsum_rows_normalized",
                "value": demand_rows_normalized,
            },
            {
                "metric": "dispatchregionsum_rows_valid_with_demand",
                "value": demand_rows_valid,
            },
            {
                "metric": "dispatchconstraint_download_attempts",
                "value": constraint_download_attempts,
            },
            {
                "metric": "dispatchconstraint_download_successes",
                "value": constraint_download_successes,
            },
            {
                "metric": "dispatchconstraint_files_processed",
                "value": constraint_files_processed,
            },
            {
                "metric": "dispatchconstraint_rows_read",
                "value": constraint_rows_read,
            },
            {
                "metric": "dispatchconstraint_rows_normalized",
                "value": constraint_rows_normalized,
            },
            {
                "metric": "dispatchconstraint_rows_valid_with_binding",
                "value": constraint_rows_valid,
            },
            {
                "metric": "required_sources_total",
                "value": source_status[source_status["required"] == True]["source_name"].nunique() if not source_status.empty else 0,
            },
            {
                "metric": "required_sources_available",
                "value": source_status[(source_status["required"] == True) & (source_status["status"] == "AVAILABLE")]["source_name"].nunique() if not source_status.empty else 0,
            },
        ]
    )


def _write_summary(
    output_path: Path,
    source_status: pd.DataFrame,
    pit_report: pd.DataFrame,
    schema_rows: int,
    market_state_rows: int,
    dispatchprice_rows_valid: int,
    interconnector_rows_valid: int,
    demand_rows_valid: int,
    constraint_rows_valid: int,
    verdict: str,
) -> None:
    required = source_status[source_status["required"] == True] if not source_status.empty else pd.DataFrame()
    missing_required = required[required["status"] != "AVAILABLE"] if not required.empty else pd.DataFrame()

    required_cov = pit_report[pit_report["metric"] == "required_source_coverage_pct"]
    coverage_pct = float(required_cov["value"].iloc[0]) if not required_cov.empty else 0.0

    lines = [
        "# Phase 5C – Commercial Market State Database (Foundation)",
        "",
        "## Objective",
        "- Build a point-in-time clean Commercial Market State Database.",
        "- Scope corridor: `NSW1-QLD1`.",
        "- Store schema + PIT timestamps + versioning + normalization + validation APIs.",
        "- Phase 1 critical data: `DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, `REGIONAL_DEMAND`.",
        "- Use physical market-state inputs before any new payout model.",
        "- Do not build a new payout model until required external datasets are available.",
        "",
        "## Market State Database Build",
        f"- Schema fields defined: `{schema_rows}`",
        f"- Stored market-state rows: `{market_state_rows}`",
        f"- Rows with usable NSW-QLD spread: `{dispatchprice_rows_valid}`",
        f"- Rows with corridor flow/capability: `{interconnector_rows_valid}`",
        f"- Rows with regional demand: `{demand_rows_valid}`",
        f"- Rows with binding-constraint signal: `{constraint_rows_valid}`",
        "- `Interconnector Stress Index` is now scaffolded from spread + utilisation.",
        "",
        "## Source Availability",
        "| Source | Priority | Required | Status |",
        "|---|---|---|---|",
    ]

    for _, row in source_status.sort_values(["priority", "source_name"]).iterrows():
        lines.append(
            f"| {row['source_name']} | {int(row['priority'])} | {'Yes' if bool(row['required']) else 'No'} | {row['status']} |"
        )

    lines += [
        "",
        "## PIT Coverage",
        f"- Required source coverage: `{coverage_pct:.2f}%`",
        "- Feature store rows are currently PIT-invalid placeholders pending external ingestion.",
        "",
        "## Required Missing Sources",
    ]

    if missing_required.empty:
        lines.append("- None. Required sources are available.")
    else:
        for _, row in missing_required.iterrows():
            lines.append(f"- `{row['source_name']}`: {row['status']} ({row['column_check']})")

    lines += [
        "",
        "## Success Gate Status",
        "- Benchmark to beat (future model): `$8,065/unit` regime-adjusted OOS MAE.",
        "- Current stage: ingestion only, modelling deferred until required data is available.",
        f"- Verdict: `{verdict}`",
        "",
        "## Next Action",
        "- Perform one-quarter corridor-level stress vs realised residue correlation check.",
        "- Keep improving PIT lineage integrity before modelling.",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_register(register_path: Path, verdict: str) -> None:
    row = pd.DataFrame(
        [
            {
                "as_of_date": "2026-07-13",
                "model_version": "phase5c_first_principles_pipeline",
                "baseline_abs_error_aud": 8065.0,
                "model_abs_error_aud": pd.NA,
                "forecast_error_reduction_aud": pd.NA,
                "forecast_error_reduction_pct": pd.NA,
                "known_error_after_wiring_aud": 0.0,
                "unattributed_before_aud": 0.0,
                "unattributed_after_aud": 0.0,
                "unattributed_reduction_aud": 0.0,
                "unattributed_reduction_pct": 0.0,
                "baseline_backtest_pnl_aud": pd.NA,
                "model_backtest_pnl_aud": pd.NA,
                "estimated_pnl_impact_aud": pd.NA,
                "notes": "Phase 5C ingestion gate: modelling deferred pending DISPATCHPRICE + DISPATCHINTERCONNECTORRES availability.",
                "status": verdict,
                "rejection_reason": "" if verdict == "PASS" else "Required first-principles datasets missing; cannot run leakage-safe walk-forward.",
                "promotion_gate_passed": verdict == "PASS",
            }
        ]
    )

    if register_path.exists():
        register = pd.read_csv(register_path)
        register = register[register["model_version"] != "phase5c_first_principles_pipeline"].copy()
        register = pd.concat([register, row], ignore_index=True)
    else:
        register = row
    register.to_csv(register_path, index=False)


def _write_bottleneck_report(report_path: Path, stage: str, error: IngestionStalledError) -> None:
    payload = {
        "stage": stage,
        "status": "STOPPED_NO_PROGRESS",
        "timestamp": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "details": error.report,
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


def _run_with_stall_guard(report_path: Path, stage: str, func):
    try:
        return func()
    except IngestionStalledError as error:
        _write_bottleneck_report(report_path, stage, error)
        raise


def _quarter_bounds(quarter: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    period = pd.Period(quarter, freq="Q")
    start = period.start_time.tz_localize("UTC")
    end = (period + 1).start_time.tz_localize("UTC")
    return start, end


def _build_nsw1_qld1_joined_table(market_state_df: pd.DataFrame, demand_component: pd.DataFrame) -> pd.DataFrame:
    frame = market_state_df.copy()
    frame["interval_timestamp_utc"] = pd.to_datetime(frame["interval_timestamp_utc"], utc=True, errors="coerce")
    frame = frame[frame["interval_timestamp_utc"].notna()].copy()
    frame = frame.sort_values("interval_timestamp_utc").drop_duplicates(subset=["interval_timestamp_utc"], keep="last")

    joined = pd.DataFrame()
    joined["interval_timestamp_utc"] = frame["interval_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    joined["nsw_rrp"] = pd.to_numeric(frame.get("nsw_rrp"), errors="coerce")
    joined["qld_rrp"] = pd.to_numeric(frame.get("qld_rrp"), errors="coerce")
    joined["directional_price_spread"] = pd.to_numeric(frame.get("nsw_qld_spread"), errors="coerce")
    joined["interconnector_flow_mw"] = pd.to_numeric(frame.get("mw_flow"), errors="coerce")
    joined["flow_direction"] = np.where(
        joined["interconnector_flow_mw"] >= 0,
        "NSW1->QLD1",
        "QLD1->NSW1",
    )
    joined["import_capability_mw"] = pd.to_numeric(frame.get("available_capability_mw"), errors="coerce")
    joined["export_capability_mw"] = pd.to_numeric(frame.get("available_capability_mw"), errors="coerce")
    joined["utilisation_pct"] = pd.to_numeric(frame.get("utilisation_pct"), errors="coerce")
    joined["interconnector_stress_index"] = pd.to_numeric(frame.get("interconnector_stress_index"), errors="coerce")
    joined["nsw_demand"] = pd.to_numeric(frame.get("regional_operational_demand"), errors="coerce")
    joined["qld_demand"] = pd.NA
    joined["demand_anomaly"] = pd.to_numeric(frame.get("demand_anomaly"), errors="coerce")
    joined["realised_irsr"] = pd.to_numeric(frame.get("irsr"), errors="coerce")
    joined["source_lineage"] = frame.get("record_source")
    joined["publication_timestamp_utc"] = frame.get("asof_publish_timestamp_utc")
    joined["dq_missing_price_flag"] = joined[["nsw_rrp", "qld_rrp"]].isna().any(axis=1)
    joined["dq_missing_flow_flag"] = joined["interconnector_flow_mw"].isna()
    joined["dq_missing_demand_flag"] = joined["nsw_demand"].isna()
    joined["dq_missing_irsr_flag"] = joined["realised_irsr"].isna()

    if not demand_component.empty:
        dc = demand_component.copy()
        dc = dc[dc["region_id"].isin(["NSW1", "QLD1"])].copy()
        dc = dc.dropna(subset=["interval_timestamp_utc"]).copy()
        pivot = (
            dc.pivot_table(
                index="interval_timestamp_utc",
                columns="region_id",
                values="regional_operational_demand",
                aggfunc="last",
            )
            .rename_axis(None, axis=1)
            .reset_index()
        )
        pivot["interval_timestamp_utc"] = pd.to_datetime(pivot["interval_timestamp_utc"], utc=True, errors="coerce")
        joined_ts = pd.to_datetime(joined["interval_timestamp_utc"], utc=True, errors="coerce")
        merged = pd.DataFrame({"interval_timestamp_utc": joined_ts}).merge(
            pivot,
            on="interval_timestamp_utc",
            how="left",
        )
        if "NSW1" in merged.columns:
            joined["nsw_demand"] = pd.to_numeric(merged["NSW1"], errors="coerce")
        if "QLD1" in merged.columns:
            joined["qld_demand"] = pd.to_numeric(merged["QLD1"], errors="coerce")
        joined["dq_missing_demand_flag"] = joined[["nsw_demand", "qld_demand"]].isna().any(axis=1)

    return joined


def _load_dispatch_irsr_interval_frame(repo_root: Path, quarter: str) -> pd.DataFrame:
    start, end = _quarter_bounds(quarter)
    irsr_dir = repo_root / "data" / "raw" / "aemo" / "dispatch_irsr"
    files = sorted(irsr_dir.rglob("*.zip"))
    if not files:
        return pd.DataFrame(columns=["interval_timestamp_utc", "interconnector_id", "from_region", "residue_aud"])

    frames: list[pd.DataFrame] = []
    for file_path in files:
        try:
            import zipfile

            with zipfile.ZipFile(file_path, "r") as zf:
                for member in zf.namelist():
                    payload = zf.read(member).decode("utf-8", errors="ignore").splitlines()
                    header = None
                    for line in payload:
                        if line.startswith("I,DISPATCH,IRSR,"):
                            header = next(__import__("csv").reader([line]))
                            continue
                        if not line.startswith("D,DISPATCH,IRSR,") or header is None:
                            continue
                        row = next(__import__("csv").reader([line]))
                        index = {str(col).upper(): i for i, col in enumerate(header)}
                        ti = row[index.get("TRADING_INTERVAL", -1)] if index.get("TRADING_INTERVAL") is not None else ""
                        ic = row[index.get("INTERCONNECTORID", -1)] if index.get("INTERCONNECTORID") is not None else ""
                        fr = row[index.get("FROMREGIONID", -1)] if index.get("FROMREGIONID") is not None else ""
                        rs = row[index.get("RESIDUE", -1)] if index.get("RESIDUE") is not None else ""
                        ts = pd.to_datetime(ti, utc=True, errors="coerce")
                        if pd.isna(ts) or ts < start or ts >= end:
                            continue
                        frames.append(
                            pd.DataFrame(
                                [
                                    {
                                        "interval_timestamp_utc": ts,
                                        "interconnector_id": str(ic).strip().upper(),
                                        "from_region": str(fr).strip().upper(),
                                        "residue_aud": pd.to_numeric(rs, errors="coerce"),
                                    }
                                ]
                            )
                        )
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(columns=["interval_timestamp_utc", "interconnector_id", "from_region", "residue_aud"])
    return pd.concat(frames, ignore_index=True)


def _attach_interval_irsr(joined: pd.DataFrame, quarter: str, repo_root: Path) -> tuple[pd.DataFrame, int, str]:
    irsr = _load_dispatch_irsr_interval_frame(repo_root, quarter)
    joined_out = joined.copy()
    duplicate_matches = 0
    source_note = "dispatch_irsr_interval"

    if irsr.empty:
        source_note = "reconstructed_flow_spread_identity"
        joined_out["realised_irsr"] = (
            pd.to_numeric(joined_out["interconnector_flow_mw"], errors="coerce")
            * pd.to_numeric(joined_out["directional_price_spread"], errors="coerce")
            * (5.0 / 60.0)
        )
        joined_out["dq_missing_irsr_flag"] = joined_out["realised_irsr"].isna()
        return joined_out, duplicate_matches, source_note

    corridor = irsr[irsr["interconnector_id"].eq("NSW1-QLD1")].copy()
    if corridor.empty:
        source_note = "reconstructed_flow_spread_identity"
        joined_out["realised_irsr"] = (
            pd.to_numeric(joined_out["interconnector_flow_mw"], errors="coerce")
            * pd.to_numeric(joined_out["directional_price_spread"], errors="coerce")
            * (5.0 / 60.0)
        )
        joined_out["dq_missing_irsr_flag"] = joined_out["realised_irsr"].isna()
        return joined_out, duplicate_matches, source_note

    grouped = corridor.groupby(["interval_timestamp_utc", "from_region"], as_index=False)["residue_aud"].sum()
    duplicate_matches = int(grouped.duplicated(subset=["interval_timestamp_utc", "from_region"]).sum())
    dir_frame = grouped[grouped["from_region"].eq("NSW1")][["interval_timestamp_utc", "residue_aud"]].copy()
    dir_frame = dir_frame.rename(columns={"residue_aud": "realised_irsr"})

    joined_ts = pd.to_datetime(joined_out["interval_timestamp_utc"], utc=True, errors="coerce")
    merged = pd.DataFrame({"interval_timestamp_utc": joined_ts}).merge(dir_frame, on="interval_timestamp_utc", how="left")
    joined_out["realised_irsr"] = pd.to_numeric(merged["realised_irsr"], errors="coerce")
    joined_out["dq_missing_irsr_flag"] = joined_out["realised_irsr"].isna()
    return joined_out, duplicate_matches, source_note


def _quarter_validation_diagnostics(joined: pd.DataFrame, quarter: str) -> dict[str, object]:
    start, end = _quarter_bounds(quarter)
    expected = pd.date_range(start=start, end=end, freq="5min", inclusive="left", tz="UTC")

    timestamps = pd.to_datetime(joined["interval_timestamp_utc"], utc=True, errors="coerce")
    unique_ts = pd.DatetimeIndex(timestamps.dropna().unique()).sort_values()
    missing_intervals = len(expected.difference(unique_ts))
    duplicate_intervals = int(timestamps.duplicated().sum())
    non_5min = int((timestamps.dropna().dt.minute % 5 != 0).sum())

    direction_error_mask = (
        ((pd.to_numeric(joined["interconnector_flow_mw"], errors="coerce") > 0) & (joined["flow_direction"] != "NSW1->QLD1"))
        | ((pd.to_numeric(joined["interconnector_flow_mw"], errors="coerce") < 0) & (joined["flow_direction"] != "QLD1->NSW1"))
    )
    direction_errors = int(direction_error_mask.sum())

    return {
        "quarter": quarter,
        "expected_intervals": int(len(expected)),
        "observed_intervals": int(len(joined)),
        "missing_intervals": int(missing_intervals),
        "duplicate_intervals": int(duplicate_intervals),
        "direction_errors": int(direction_errors),
        "timestamp_mismatches": int(non_5min),
    }


def _correlation_report(joined: pd.DataFrame, alpha_df: pd.DataFrame, quarter: str) -> pd.DataFrame:
    quarter_alpha = alpha_df.copy()
    if "quarter" in quarter_alpha.columns:
        quarter_alpha = quarter_alpha[quarter_alpha["quarter"].astype(str) == quarter].copy()

    sra_payout = pd.NA
    benchmark_deviation = pd.NA
    if not quarter_alpha.empty:
        if "final_realised_payout_per_unit" in quarter_alpha.columns:
            sra_payout = pd.to_numeric(quarter_alpha["final_realised_payout_per_unit"], errors="coerce").mean()
        if "forecast_error_to_realised" in quarter_alpha.columns:
            benchmark_deviation = pd.to_numeric(quarter_alpha["forecast_error_to_realised"], errors="coerce").mean()

    corr_frame = joined.copy()
    corr_frame["sra_payout"] = sra_payout
    corr_frame["benchmark_deviation"] = benchmark_deviation

    rows = []
    for target in ["realised_irsr", "sra_payout", "benchmark_deviation"]:
        pair = corr_frame[["interconnector_stress_index", "demand_anomaly", target]].copy()
        stress_corr = pair[["interconnector_stress_index", target]].dropna().corr().iloc[0, 1] if len(pair[["interconnector_stress_index", target]].dropna()) >= 2 else pd.NA
        demand_corr = pair[["demand_anomaly", target]].dropna().corr().iloc[0, 1] if len(pair[["demand_anomaly", target]].dropna()) >= 2 else pd.NA
        rows.append(
            {
                "target_metric": target,
                "stress_index_corr": stress_corr,
                "demand_anomaly_corr": demand_corr,
                "non_null_pairs_stress": int(len(pair[["interconnector_stress_index", target]].dropna())),
                "non_null_pairs_demand": int(len(pair[["demand_anomaly", target]].dropna())),
            }
        )
    return pd.DataFrame(rows)


def _normalise_contract_quarter(quarter: str) -> str:
    token = str(quarter).strip().upper()
    if not token:
        return token
    return token if token.startswith("C") else f"C{token}"


def _quarter_sort_key(quarter: str) -> tuple[int, int]:
    token = _normalise_contract_quarter(quarter)
    try:
        year = int(token[1:5])
        qtr = int(token.split("Q")[1])
        return year, qtr
    except Exception:
        return 9999, 9


def _quarter_from_timestamp(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    quarter_period = ts.dt.to_period("Q")
    return "C" + quarter_period.astype(str)


def _load_auction_units_quarterly(repo_root: Path) -> pd.DataFrame:
    auction_dir = repo_root / "data" / "raw" / "aemo" / "auction_units"
    rows: list[dict[str, object]] = []
    for file_path in sorted(auction_dir.glob("AUCUNITS_*.R*")):
        try:
            payload = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line in payload:
            if not line.startswith("D,BILLING,AUCTION_UNITS,"):
                continue
            try:
                row = next(csv.reader([line]))
            except Exception:
                continue
            if len(row) < 22:
                continue
            residue_year = pd.to_numeric(row[10], errors="coerce")
            residue_quarter = pd.to_numeric(row[11], errors="coerce")
            if pd.isna(residue_year) or pd.isna(residue_quarter):
                continue
            quarter = f"C{int(residue_year)}Q{int(residue_quarter)}"
            rows.append(
                {
                    "quarter": quarter,
                    "interconnector_id": str(row[12]).strip().upper(),
                    "from_region": str(row[13]).strip().upper(),
                    "purchased_units": pd.to_numeric(row[14], errors="coerce"),
                    "total_surplus": pd.to_numeric(row[15], errors="coerce"),
                    "distributed_surplus": pd.to_numeric(row[16], errors="coerce"),
                    "auction_fees": pd.to_numeric(row[17], errors="coerce"),
                    "net_payment": pd.to_numeric(row[18], errors="coerce"),
                    "net_payment_per_unit": pd.to_numeric(row[19], errors="coerce"),
                    "accumulated_netpayment_per_unit": pd.to_numeric(row[21], errors="coerce"),
                    "bill_run_no": pd.to_numeric(row[6], errors="coerce"),
                    "bill_run_type": str(row[9]).strip(),
                    "week_start": pd.to_datetime(row[7], errors="coerce", dayfirst=False),
                    "source_file": str(file_path),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "purchased_units",
                "total_surplus",
                "distributed_surplus",
                "auction_fees",
                "net_payment",
                "net_payment_per_unit",
                "accumulated_netpayment_per_unit",
                "bill_run_no",
                "bill_run_type",
                "week_start",
                "source_file",
            ]
        )
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(["quarter", "interconnector_id", "from_region", "week_start", "bill_run_no", "source_file"])
    latest = frame.drop_duplicates(subset=["quarter", "interconnector_id", "from_region"], keep="last")
    return latest.reset_index(drop=True)


def _select_phase5c3_quarter(
    market_state_df: pd.DataFrame,
    alpha_df: pd.DataFrame,
    auction_df: pd.DataFrame,
    payout_df: pd.DataFrame,
    irsr_df: pd.DataFrame,
    auction_units_df: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    market_q_series = _quarter_from_timestamp(market_state_df.get("interval_timestamp_utc", pd.Series(dtype=object)))
    market_q = set(market_q_series.dropna().astype(str).unique())

    alpha = alpha_df.copy()
    alpha["quarter"] = alpha.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    alpha_q = set(alpha["quarter"].dropna().unique())
    ruleset_q = set(alpha.loc[alpha.get("ruleset_id", pd.Series(dtype=object)).notna(), "quarter"].unique())
    max_units_q = set(alpha.loc[pd.to_numeric(alpha.get("units_offered"), errors="coerce").notna(), "quarter"].unique())
    unit_prop_q = set(alpha.loc[pd.to_numeric(alpha.get("units_offered"), errors="coerce") > 0, "quarter"].unique())
    unit_cat_q = set(
        alpha.loc[
            alpha.get("interconnector_id", pd.Series(dtype=object)).notna()
            & alpha.get("from_region", pd.Series(dtype=object)).notna(),
            "quarter",
        ].unique()
    )

    auction = auction_df.copy()
    auction["quarter"] = auction.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    auction_q = set(auction["quarter"].dropna().unique())

    payout = payout_df.copy()
    payout["quarter"] = payout.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    payout_q = set(payout["quarter"].dropna().unique())

    irsr = irsr_df.copy()
    irsr["quarter"] = irsr.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    irsr_q = set(irsr["quarter"].dropna().unique())

    auction_units = auction_units_df.copy()
    auction_units["quarter"] = auction_units.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    auction_units_q = set(auction_units["quarter"].dropna().unique())

    all_quarters = sorted(
        market_q | alpha_q | auction_q | payout_q | irsr_q | auction_units_q,
        key=_quarter_sort_key,
    )

    records: list[dict[str, object]] = []
    for quarter in all_quarters:
        market_count = int((market_q_series.astype(str) == quarter).sum())
        has_market = quarter in market_q and market_count > 0
        has_irsr = quarter in irsr_q
        has_payout = quarter in payout_q
        has_auction = quarter in auction_q
        has_ruleset = quarter in ruleset_q
        has_unit_cat = quarter in unit_cat_q
        has_max_units = quarter in max_units_q
        has_unit_prop = quarter in unit_prop_q
        has_auction_units = quarter in auction_units_q
        eligible = all(
            [
                has_market,
                has_irsr,
                has_payout,
                has_auction,
                has_ruleset,
                has_unit_cat,
                has_max_units,
                has_unit_prop,
                has_auction_units,
            ]
        )
        records.append(
            {
                "quarter": quarter,
                "market_state_intervals": market_count,
                "has_market_state": has_market,
                "has_official_quarterly_irsr": has_irsr,
                "has_payout_per_unit": has_payout,
                "has_auction_clearing": has_auction,
                "has_ruleset": has_ruleset,
                "has_unit_category": has_unit_cat,
                "has_max_units": has_max_units,
                "has_unit_proportion": has_unit_prop,
                "has_auction_units_weekly": has_auction_units,
                "eligible": eligible,
            }
        )
    matrix = pd.DataFrame(records)
    selected = None
    eligible_rows = matrix[matrix["eligible"] == True] if not matrix.empty else pd.DataFrame()
    if not eligible_rows.empty:
        selected = eligible_rows.sort_values("quarter", key=lambda s: s.map(_quarter_sort_key)).iloc[0]["quarter"]
    return matrix, selected


def _extract_interconnector_directional_fields(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()

    registry = Interconnector.registry()
    supported_pairs: dict[str, dict[str, object]] = {}
    for canonical_id, reverse_id in [
        ("NSW1-QLD1", "QLD1-NSW1"),
        ("VIC1-NSW1", "NSW1-VIC1"),
        ("VIC1-SA1", "SA1-VIC1"),
    ]:
        canonical = registry.get(canonical_id)
        reverse = registry.get(reverse_id)
        if canonical is None or reverse is None:
            continue
        pair_key = f"{canonical.direction_from_region}|{canonical.direction_to_region}"
        supported_pairs[pair_key] = {
            "canonical_interconnector_id": canonical.interconnector_id,
            "forward_from": canonical.direction_from_region,
            "forward_to": canonical.direction_to_region,
            "forward_direction": f"{canonical.direction_from_region}->{canonical.direction_to_region}",
            "reverse_direction": f"{canonical.direction_to_region}->{canonical.direction_from_region}",
            "reverse_interconnector_id": reverse.interconnector_id,
            "applicable_unit_categories": [canonical.category_id, reverse.category_id],
        }

    alias_to_pair: dict[str, str] = {}
    valid_directions: set[str] = set()
    direction_to_pair: dict[str, str] = {}
    for pair_key, spec in supported_pairs.items():
        canonical_id = str(spec["canonical_interconnector_id"])
        reverse_id = str(spec["reverse_interconnector_id"])
        forward_direction = str(spec["forward_direction"])
        reverse_direction = str(spec["reverse_direction"])
        alias_to_pair[canonical_id] = pair_key
        alias_to_pair[reverse_id] = pair_key
        valid_directions.update([forward_direction, reverse_direction])
        direction_to_pair[forward_direction] = pair_key
        direction_to_pair[reverse_direction] = pair_key

    def _normalise_text_series(column_name: str) -> pd.Series:
        raw = out.get(column_name, pd.Series([pd.NA] * len(out), index=out.index, dtype=object))
        is_str = raw.map(lambda value: isinstance(value, str))
        normalised = pd.Series(pd.NA, index=out.index, dtype=object)
        if is_str.any():
            normalised.loc[is_str] = raw.loc[is_str].str.strip().str.upper()
        return normalised

    corridor_norm = _normalise_text_series("corridor")
    interconnector_norm = _normalise_text_series("interconnector_id")
    direction_norm = _normalise_text_series("direction").str.replace(" ", "", regex=False)
    from_region_norm = _normalise_text_series("from_region")
    to_region_norm = _normalise_text_series("to_region")

    pair_from_id = interconnector_norm.map(alias_to_pair)
    pair_from_corridor = corridor_norm.map(alias_to_pair)
    pair_from_direction = direction_norm.where(direction_norm.isin(valid_directions), pd.NA).map(direction_to_pair)
    region_pair_key = (from_region_norm.astype(str) + "|" + to_region_norm.astype(str)).where(
        from_region_norm.notna() & to_region_norm.notna(),
        pd.NA,
    )
    pair_from_region = region_pair_key.where(region_pair_key.isin(supported_pairs.keys()), pd.NA)

    pair_key = pair_from_id.copy()
    pair_key = pair_key.where(pair_key.notna(), pair_from_corridor)
    pair_key = pair_key.where(pair_key.notna(), pair_from_direction)
    pair_key = pair_key.where(pair_key.notna(), pair_from_region)

    canonical_interconnector = pair_key.map(
        lambda value: supported_pairs.get(value, {}).get("canonical_interconnector_id") if pd.notna(value) else pd.NA
    )

    mw_flow = pd.to_numeric(out.get("mw_flow", pd.Series([pd.NA] * len(out), index=out.index)), errors="coerce")
    zero_flow_flag = pair_key.notna() & mw_flow.eq(0)

    flow_derived_direction = pd.Series(pd.NA, index=out.index, dtype=object)
    for supported_key, spec in supported_pairs.items():
        pair_mask = pair_key == supported_key
        if not pair_mask.any():
            continue
        positive_mask = pair_mask & mw_flow.gt(0)
        negative_mask = pair_mask & mw_flow.lt(0)
        if positive_mask.any():
            flow_derived_direction.loc[positive_mask] = str(spec["forward_direction"])
        if negative_mask.any():
            flow_derived_direction.loc[negative_mask] = str(spec["reverse_direction"])

    region_derived_direction = pd.Series(pd.NA, index=out.index, dtype=object)
    valid_region_pair = pair_key.notna() & from_region_norm.notna() & to_region_norm.notna()
    if valid_region_pair.any():
        candidate = (
            from_region_norm.loc[valid_region_pair].astype(str)
            + "->"
            + to_region_norm.loc[valid_region_pair].astype(str)
        )
        region_derived_direction.loc[valid_region_pair] = candidate.where(candidate.isin(valid_directions), pd.NA)

    direction_final = flow_derived_direction.copy()
    direction_final = direction_final.where(direction_final.notna(), region_derived_direction)
    direction_final = direction_final.where(direction_final.isin(valid_directions), pd.NA)

    expected_from = direction_final.str.split("->").str[0]
    expected_to = direction_final.str.split("->").str[1]
    has_regions = from_region_norm.notna() & to_region_norm.notna()
    mismatch_flag = has_regions & direction_final.notna() & (
        (from_region_norm != expected_from) | (to_region_norm != expected_to)
    )
    direction_final = direction_final.mask(mismatch_flag, pd.NA)

    out["interconnector_id"] = canonical_interconnector.where(direction_final.notna(), pd.NA)
    out["corridor"] = out["interconnector_id"]
    out["direction"] = direction_final
    out["from_region"] = direction_final.str.split("->").str[0]
    out["to_region"] = direction_final.str.split("->").str[1]
    out["direction_zero_flow_flag"] = zero_flow_flag
    out["direction_region_mismatch_flag"] = mismatch_flag
    out["direction_unknown_flag"] = out["direction"].isna()
    return out


def _build_phase5c3_interval_validation(market_state_quarter: pd.DataFrame, quarter: str) -> pd.DataFrame:
    if "interval_timestamp_utc" not in market_state_quarter.columns:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "expected_intervals",
                "observed_intervals",
                "missing_intervals",
                "duplicate_intervals",
                "timestamp_mismatches",
                "missing_price_rows",
                "missing_flow_rows",
                "missing_irsr_rows",
                "missing_demand_rows",
            ]
        )
    frame = _extract_interconnector_directional_fields(market_state_quarter)
    frame["interval_timestamp_utc"] = pd.to_datetime(frame["interval_timestamp_utc"], utc=True, errors="coerce")
    frame = frame[frame["interval_timestamp_utc"].notna()].copy()

    start, end = _quarter_bounds(quarter.replace("C", ""))
    expected_intervals = int(len(pd.date_range(start=start, end=end, freq="5min", inclusive="left", tz="UTC")))

    rows: list[dict[str, object]] = []
    grouped = frame.groupby(["interconnector_id", "from_region"], dropna=False)
    for (interconnector_id, from_region), group in grouped:
        timestamps = pd.to_datetime(group["interval_timestamp_utc"], utc=True, errors="coerce")
        observed = int(timestamps.nunique())
        duplicates = int(timestamps.duplicated().sum())
        ts_bad = int((timestamps.dt.minute % 5 != 0).sum())
        rows.append(
            {
                "quarter": quarter,
                "interconnector_id": interconnector_id,
                "from_region": from_region,
                "expected_intervals": expected_intervals,
                "observed_intervals": observed,
                "missing_intervals": int(max(expected_intervals - observed, 0)),
                "duplicate_intervals": duplicates,
                "timestamp_mismatches": ts_bad,
                "missing_price_rows": int(group[["nsw_rrp", "qld_rrp"]].isna().any(axis=1).sum()),
                "missing_flow_rows": int(pd.to_numeric(group.get("mw_flow"), errors="coerce").isna().sum()),
                "missing_irsr_rows": int(pd.to_numeric(group.get("irsr"), errors="coerce").isna().sum()),
                "missing_demand_rows": int(pd.to_numeric(group.get("regional_operational_demand"), errors="coerce").isna().sum()),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "expected_intervals",
                "observed_intervals",
                "missing_intervals",
                "duplicate_intervals",
                "timestamp_mismatches",
                "missing_price_rows",
                "missing_flow_rows",
                "missing_irsr_rows",
                "missing_demand_rows",
            ]
        )
    return pd.DataFrame(rows).sort_values(["interconnector_id", "from_region"]).reset_index(drop=True)


def _build_phase5c3_quarterly_reconciliation(
    market_state_quarter: pd.DataFrame,
    quarter: str,
    irsr_df: pd.DataFrame,
    payout_df: pd.DataFrame,
) -> pd.DataFrame:
    required_cols = {"corridor", "direction", "irsr"}
    if not required_cols.issubset(set(market_state_quarter.columns)):
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "reconstructed_irsr",
                "official_quarterly_irsr",
                "total_units_sold",
                "payout_per_unit",
                "weighted_avg_clearing_price",
                "irsr_variance",
            ]
        )
    frame = _extract_interconnector_directional_fields(market_state_quarter)
    reconstructed = (
        frame.groupby(["interconnector_id", "from_region"], as_index=False)["irsr"]
        .sum(min_count=1)
        .rename(columns={"irsr": "reconstructed_irsr"})
    )

    official_irsr = irsr_df.copy()
    official_irsr["quarter"] = official_irsr.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    official_irsr = official_irsr[official_irsr["quarter"].eq(quarter)].copy()
    official_irsr = official_irsr.rename(columns={"surplus_aud": "official_quarterly_irsr"})
    official_irsr = official_irsr[["interconnector_id", "from_region", "official_quarterly_irsr"]]

    payout = payout_df.copy()
    payout["quarter"] = payout.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    payout = payout[payout["quarter"].eq(quarter)].copy()
    payout = payout[["interconnector_id", "from_region", "total_units_sold", "payout_per_unit", "weighted_avg_clearing_price"]]

    merged = reconstructed.merge(official_irsr, on=["interconnector_id", "from_region"], how="outer")
    merged = merged.merge(payout, on=["interconnector_id", "from_region"], how="outer")
    merged.insert(0, "quarter", quarter)
    merged["irsr_variance"] = pd.to_numeric(merged["reconstructed_irsr"], errors="coerce") - pd.to_numeric(
        merged["official_quarterly_irsr"], errors="coerce"
    )
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "reconstructed_irsr",
                "official_quarterly_irsr",
                "total_units_sold",
                "payout_per_unit",
                "weighted_avg_clearing_price",
                "irsr_variance",
            ]
        )
    return merged.sort_values(["interconnector_id", "from_region"]).reset_index(drop=True)


def _build_phase5c3_unit_payout_reconciliation(
    quarter: str,
    quarterly_recon: pd.DataFrame,
    auction_units_df: pd.DataFrame,
) -> pd.DataFrame:
    auction = auction_units_df.copy()
    auction["quarter"] = auction.get("quarter", pd.Series(dtype=str)).astype(str).str.upper()
    auction = auction[auction["quarter"].eq(quarter)].copy()
    if not auction.empty:
        auction = auction.sort_values(["interconnector_id", "from_region", "week_start", "bill_run_no", "source_file"])
        auction = auction.drop_duplicates(subset=["interconnector_id", "from_region"], keep="last")
    auction = auction[
        [
            "interconnector_id",
            "from_region",
            "purchased_units",
            "total_surplus",
            "distributed_surplus",
            "auction_fees",
            "net_payment",
            "net_payment_per_unit",
            "accumulated_netpayment_per_unit",
            "bill_run_no",
            "bill_run_type",
            "source_file",
        ]
    ]
    merged = quarterly_recon[
        ["quarter", "interconnector_id", "from_region", "total_units_sold", "payout_per_unit", "weighted_avg_clearing_price"]
    ].merge(auction, on=["interconnector_id", "from_region"], how="left")
    purchased_units = pd.to_numeric(merged.get("purchased_units"), errors="coerce")
    merged["gross_payout_per_unit"] = pd.to_numeric(merged.get("payout_per_unit"), errors="coerce")
    merged["fees_per_unit"] = pd.to_numeric(merged.get("auction_fees"), errors="coerce") / purchased_units
    merged["adjustments_per_unit"] = (
        pd.to_numeric(merged.get("distributed_surplus"), errors="coerce")
        - pd.to_numeric(merged.get("total_surplus"), errors="coerce")
    ) / purchased_units
    merged["reconstructed_net_payout_per_unit"] = pd.to_numeric(merged.get("net_payment"), errors="coerce") / purchased_units
    merged["official_net_payout_per_unit"] = pd.to_numeric(merged.get("net_payment_per_unit"), errors="coerce")
    merged["payout_per_unit_variance_vs_accumulated"] = (
        merged["reconstructed_net_payout_per_unit"] - merged["official_net_payout_per_unit"]
    )
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "total_units_sold",
                "payout_per_unit",
                "weighted_avg_clearing_price",
                "purchased_units",
                "total_surplus",
                "distributed_surplus",
                "auction_fees",
                "net_payment",
                "net_payment_per_unit",
                "accumulated_netpayment_per_unit",
                "bill_run_no",
                "bill_run_type",
                "gross_payout_per_unit",
                "fees_per_unit",
                "adjustments_per_unit",
                "reconstructed_net_payout_per_unit",
                "official_net_payout_per_unit",
                "source_file",
                "payout_per_unit_variance_vs_accumulated",
            ]
        )
    return merged.sort_values(["interconnector_id", "from_region"]).reset_index(drop=True)


def _build_phase5c3_physical_driver_correlations(market_state_quarter: pd.DataFrame, quarter: str) -> pd.DataFrame:
    required_cols = {"corridor", "direction", "irsr"}
    if not required_cols.issubset(set(market_state_quarter.columns)):
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "driver",
                "corr_with_realised_irsr",
                "non_null_pairs",
            ]
        )
    frame = _extract_interconnector_directional_fields(market_state_quarter)
    rows: list[dict[str, object]] = []
    for (interconnector_id, from_region), group in frame.groupby(["interconnector_id", "from_region"], dropna=False):
        metrics = pd.DataFrame(
            {
                "spread": pd.to_numeric(group.get("nsw_qld_spread"), errors="coerce"),
                "flow": pd.to_numeric(group.get("mw_flow"), errors="coerce"),
                "stress": pd.to_numeric(group.get("interconnector_stress_index"), errors="coerce"),
                "demand_anomaly": pd.to_numeric(group.get("demand_anomaly"), errors="coerce"),
                "realised_irsr": pd.to_numeric(group.get("irsr"), errors="coerce"),
            }
        )
        for driver in ["spread", "flow", "stress", "demand_anomaly"]:
            pair = metrics[[driver, "realised_irsr"]].dropna()
            corr = pair.corr().iloc[0, 1] if len(pair) >= 2 else pd.NA
            rows.append(
                {
                    "quarter": quarter,
                    "interconnector_id": interconnector_id,
                    "from_region": from_region,
                    "driver": driver,
                    "corr_with_realised_irsr": corr,
                    "non_null_pairs": int(len(pair)),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "quarter",
                "interconnector_id",
                "from_region",
                "driver",
                "corr_with_realised_irsr",
                "non_null_pairs",
            ]
        )
    return pd.DataFrame(rows).sort_values(["interconnector_id", "from_region", "driver"]).reset_index(drop=True)


def _write_phase5c3_selection_markdown(path: Path, matrix: pd.DataFrame, selected_quarter: str | None) -> None:
    lines = [
        "# Phase 5C.3 Test Quarter Selection",
        "",
        f"- Selected quarter: `{selected_quarter}`" if selected_quarter else "- Selected quarter: `NONE`",
        "- Selection rule: earliest quarter with complete authoritative settlement + auction + ruleset/unit metadata coverage.",
        "",
        "## Coverage Matrix",
        "",
        "| Quarter | Market | IRSR | Payout | Auction | Ruleset | Unit Cat | Max Units | Unit Prop | Auction Units | Eligible |",
        "|---|---:|---|---|---|---|---|---|---|---|---|",
    ]
    for _, row in matrix.sort_values("quarter", key=lambda s: s.map(_quarter_sort_key)).iterrows():
        lines.append(
            "| {quarter} | {market_state_intervals} | {has_official_quarterly_irsr} | {has_payout_per_unit} | {has_auction_clearing} | {has_ruleset} | {has_unit_category} | {has_max_units} | {has_unit_proportion} | {has_auction_units_weekly} | {eligible} |".format(
                **row.to_dict()
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_phase5c3_readiness_summary(
    path: Path,
    quarter: str,
    interval_validation: pd.DataFrame,
    quarterly_recon: pd.DataFrame,
    unit_recon: pd.DataFrame,
) -> str:
    max_missing = int(pd.to_numeric(interval_validation.get("missing_intervals"), errors="coerce").fillna(0).max()) if not interval_validation.empty else 0
    max_irsr_variance = float(pd.to_numeric(quarterly_recon.get("irsr_variance"), errors="coerce").abs().fillna(0.0).max()) if not quarterly_recon.empty else 0.0
    max_payout_variance = float(
        pd.to_numeric(unit_recon.get("payout_per_unit_variance_vs_accumulated"), errors="coerce").abs().fillna(0.0).max()
    ) if not unit_recon.empty else 0.0

    has_valid_quarter = str(quarter).upper() != "NONE"
    has_reconciliation_rows = (not interval_validation.empty) and (not quarterly_recon.empty) and (not unit_recon.empty)
    ready = has_valid_quarter and has_reconciliation_rows and (max_missing == 0) and (max_irsr_variance <= 1.0) and (max_payout_variance <= 5.0)
    verdict = "GO" if ready else "HOLD"
    lines = [
        "# PHASE 5C.3 Readiness Summary",
        "",
        f"- Selected quarter: `{quarter}`",
        f"- Verdict: `{verdict}`",
        f"- Max missing intervals (any direction): `{max_missing}`",
        f"- Max quarterly IRSR variance (AUD): `{max_irsr_variance:.4f}`",
        f"- Max payout-per-unit variance vs AUCTION_UNITS accumulated (AUD): `{max_payout_variance:.4f}`",
        "",
        "## Criteria",
        "",
        "- GO requires zero missing intervals and tight reconciliation on both quarterly IRSR and payout-per-unit.",
        "- HOLD indicates at least one reconciliation or interval-completeness gap.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return verdict


def _write_phase5c3_test_plan(path: Path, quarter: str, verdict: str) -> None:
    lines = [
        "# Phase 5C.3 First SRA Test Plan",
        "",
        f"- Quarter under test: `{quarter}`",
        f"- Readiness verdict: `{verdict}`",
        "",
        "## Steps",
        "",
        "1. Lock the selected quarter and corridor-direction coverage used in reconciliation.",
        "2. Use physical interval drivers (`spread`, `flow`, `stress`, `demand_anomaly`) to build explanatory diagnostics only.",
        "3. Validate payout consistency against authoritative quarterly IRSR and AUCTION_UNITS accumulated net payment per unit.",
        "4. If HOLD, remediate source-mapping gaps before any forecasting work.",
        "5. If GO, proceed to first concept-test design using this quarter as calibration baseline.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase5c3(quarter_override: str | None = None) -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    market_db = MarketStateDatabase()
    price_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchprice"
    flow_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"
    demand_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"

    market_db.ingest_dispatchprice_cache(price_dir)
    market_db.ingest_dispatchinterconnectorres_cache(flow_dir)
    market_db.ingest_dispatchregionsum_cache(demand_dir)
    market_state = market_db.state.copy()
    market_state["interval_timestamp_utc"] = pd.to_datetime(market_state["interval_timestamp_utc"], utc=True, errors="coerce")
    market_state = market_state[market_state["interval_timestamp_utc"].notna()].copy()

    alpha_df = pd.read_csv(REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv")
    auction_df = pd.read_csv(REPO_ROOT / "data" / "derived" / "sra" / "sra_auction_results.csv")
    payout_df = pd.read_csv(REPO_ROOT / "data" / "derived" / "sra" / "sra_payout_history.csv")
    irsr_df = pd.read_csv(REPO_ROOT / "data" / "derived" / "irsr" / "setirsurplus_quarterly_all.csv")
    auction_units_df = _load_auction_units_quarterly(REPO_ROOT)

    selection_matrix, selected_quarter = _select_phase5c3_quarter(
        market_state_df=market_state,
        alpha_df=alpha_df,
        auction_df=auction_df,
        payout_df=payout_df,
        irsr_df=irsr_df,
        auction_units_df=auction_units_df,
    )

    if quarter_override:
        selected_quarter = _normalise_contract_quarter(quarter_override)

    selection_path = reports_dir / "phase5c3_test_quarter_selection.md"
    _write_phase5c3_selection_markdown(selection_path, selection_matrix, selected_quarter)

    if not selected_quarter:
        interval_path = reports_dir / "phase5c3_interval_validation.csv"
        quarterly_path = reports_dir / "phase5c3_quarterly_reconciliation.csv"
        unit_path = reports_dir / "phase5c3_unit_payout_reconciliation.csv"
        corr_path = reports_dir / "phase5c3_physical_driver_correlations.csv"
        readiness_path = reports_dir / "PHASE5C3_READINESS_SUMMARY.md"
        plan_path = reports_dir / "phase5c3_first_sra_test_plan.md"

        _build_phase5c3_interval_validation(pd.DataFrame(), "NONE").to_csv(interval_path, index=False)
        _build_phase5c3_quarterly_reconciliation(pd.DataFrame(), "NONE", irsr_df, payout_df).to_csv(quarterly_path, index=False)
        _build_phase5c3_unit_payout_reconciliation("NONE", pd.DataFrame(columns=["quarter", "interconnector_id", "from_region", "total_units_sold", "payout_per_unit", "weighted_avg_clearing_price"]), auction_units_df).to_csv(unit_path, index=False)
        _build_phase5c3_physical_driver_correlations(pd.DataFrame(), "NONE").to_csv(corr_path, index=False)
        verdict = _write_phase5c3_readiness_summary(readiness_path, "NONE", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        _write_phase5c3_test_plan(plan_path, "NONE", verdict)

        print(
            json.dumps(
                {
                    "status": "NO_ELIGIBLE_QUARTER",
                    "selection_report": str(selection_path.relative_to(REPO_ROOT)),
                    "outputs": {
                        "interval_validation": str(interval_path.relative_to(REPO_ROOT)),
                        "quarterly_reconciliation": str(quarterly_path.relative_to(REPO_ROOT)),
                        "unit_payout_reconciliation": str(unit_path.relative_to(REPO_ROOT)),
                        "physical_driver_correlations": str(corr_path.relative_to(REPO_ROOT)),
                        "readiness_summary": str(readiness_path.relative_to(REPO_ROOT)),
                        "first_test_plan": str(plan_path.relative_to(REPO_ROOT)),
                    },
                },
                indent=2,
            )
        )
        return 2

    start, end = _quarter_bounds(selected_quarter.replace("C", ""))
    market_state_q = market_state[(market_state["interval_timestamp_utc"] >= start) & (market_state["interval_timestamp_utc"] < end)].copy()

    interval_validation = _build_phase5c3_interval_validation(market_state_q, selected_quarter)
    quarterly_recon = _build_phase5c3_quarterly_reconciliation(market_state_q, selected_quarter, irsr_df, payout_df)
    unit_recon = _build_phase5c3_unit_payout_reconciliation(selected_quarter, quarterly_recon, auction_units_df)
    correlations = _build_phase5c3_physical_driver_correlations(market_state_q, selected_quarter)

    interval_path = reports_dir / "phase5c3_interval_validation.csv"
    quarterly_path = reports_dir / "phase5c3_quarterly_reconciliation.csv"
    unit_path = reports_dir / "phase5c3_unit_payout_reconciliation.csv"
    corr_path = reports_dir / "phase5c3_physical_driver_correlations.csv"
    readiness_path = reports_dir / "PHASE5C3_READINESS_SUMMARY.md"
    plan_path = reports_dir / "phase5c3_first_sra_test_plan.md"

    interval_validation.to_csv(interval_path, index=False)
    quarterly_recon.to_csv(quarterly_path, index=False)
    unit_recon.to_csv(unit_path, index=False)
    correlations.to_csv(corr_path, index=False)
    verdict = _write_phase5c3_readiness_summary(readiness_path, selected_quarter, interval_validation, quarterly_recon, unit_recon)
    _write_phase5c3_test_plan(plan_path, selected_quarter, verdict)

    print(
        json.dumps(
            {
                "status": "PHASE5C3_COMPLETED",
                "selected_quarter": selected_quarter,
                "verdict": verdict,
                "outputs": {
                    "quarter_selection": str(selection_path.relative_to(REPO_ROOT)),
                    "interval_validation": str(interval_path.relative_to(REPO_ROOT)),
                    "quarterly_reconciliation": str(quarterly_path.relative_to(REPO_ROOT)),
                    "unit_payout_reconciliation": str(unit_path.relative_to(REPO_ROOT)),
                    "physical_driver_correlations": str(corr_path.relative_to(REPO_ROOT)),
                    "readiness_summary": str(readiness_path.relative_to(REPO_ROOT)),
                    "first_test_plan": str(plan_path.relative_to(REPO_ROOT)),
                },
            },
            indent=2,
        )
    )
    return 0


def main() -> None:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    register_path = reports_dir / "FORECAST_CONTRIBUTION_REGISTER.csv"

    source_status_path = reports_dir / "phase5c_ingestion_lineage.csv"
    feature_store_path = reports_dir / "phase5c_feature_store_nsw1_qld1.csv"
    pit_coverage_path = reports_dir / "phase5c_pit_coverage_report.csv"
    schema_path = reports_dir / "phase5c_market_state_schema.csv"
    market_state_path = reports_dir / "phase5c_market_state.csv"
    validation_path = reports_dir / "phase5c_ingestion_validation.csv"
    walkforward_path = reports_dir / "phase5c_walkforward_results.csv"
    driver_attr_path = reports_dir / "phase5c_driver_attribution.csv"
    manual_reconcile_path = reports_dir / "phase5c_manual_interval_reconciliation.csv"
    summary_path = reports_dir / "PHASE5C_FIRST_PRINCIPLES_SUMMARY.md"
    bottleneck_report_path = reports_dir / "phase5c_runtime_bottleneck_report.json"

    alpha_df = pd.read_csv(alpha_path)
    source_status = assess_source_availability(REPO_ROOT)

    market_db = MarketStateDatabase()
    schema_df = MarketStateDatabase.schema_dictionary()

    dispatchprice_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHPRICE")
    interconnector_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHINTERCONNECTORRES")
    demand_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "REGIONAL_DEMAND")
    constraint_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHCONSTRAINT")

    def _mark_source_available(source_status_frame: pd.DataFrame, requirement, file_path: Path, column_check: str, columns: str) -> pd.DataFrame:
        source_status_frame = source_status_frame[source_status_frame["source_name"] != requirement.source_name].copy()
        source_status_frame = pd.concat(
            [
                source_status_frame,
                pd.DataFrame(
                    [
                        {
                            "source_name": requirement.source_name,
                            "priority": requirement.priority,
                            "required": requirement.required,
                            "status": "AVAILABLE",
                            "file_path": str(file_path),
                            "column_check": column_check,
                            "description": requirement.description,
                            "columns": columns,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        return source_status_frame.sort_values(["priority", "source_name", "status", "file_path"]).reset_index(drop=True)
    dispatchprice_files = discover_files(REPO_ROOT, dispatchprice_requirement.glob_patterns)
    publish_timestamp_utc = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    ingestion_result = _run_with_stall_guard(
        bottleneck_report_path,
        "DISPATCHPRICE_FILES",
        lambda: market_db.ingest_dispatchprice_files(
            dispatchprice_files,
            publish_timestamp_utc=publish_timestamp_utc,
        ),
    )
    if ingestion_result.rows_normalized == 0:
        archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchprice"
        ingestion_result = _run_with_stall_guard(
            bottleneck_report_path,
            "DISPATCHPRICE_CACHE_LOAD",
            lambda: market_db.ingest_dispatchprice_cache(
                raw_archive_dir=archive_dir,
            ),
        )

        if ingestion_result.rows_normalized > 0:
            source_status = _mark_source_available(
                source_status,
                dispatchprice_requirement,
                archive_dir,
                "cache_loaded",
                "SETTLEMENTDATE,REGIONID,RRP",
            )

    interconnector_files = discover_files(REPO_ROOT, interconnector_requirement.glob_patterns)
    interconnector_result = _run_with_stall_guard(
        bottleneck_report_path,
        "DISPATCHINTERCONNECTORRES_FILES",
        lambda: market_db.ingest_dispatchinterconnectorres_files(
            interconnector_files,
            publish_timestamp_utc=publish_timestamp_utc,
        ),
    )
    if interconnector_result.rows_normalized == 0:
        archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"
        interconnector_result = _run_with_stall_guard(
            bottleneck_report_path,
            "DISPATCHINTERCONNECTORRES_CACHE_LOAD",
            lambda: market_db.ingest_dispatchinterconnectorres_cache(
                raw_archive_dir=archive_dir,
            ),
        )

        if interconnector_result.rows_normalized > 0:
            source_status = _mark_source_available(
                source_status,
                interconnector_requirement,
                archive_dir,
                "cache_loaded",
                "SETTLEMENTDATE,INTERCONNECTORID,METEREDMWFLOW,MWFLOW,EXPORTLIMIT,IMPORTLIMIT",
            )

    demand_files = discover_files(REPO_ROOT, demand_requirement.glob_patterns)
    demand_result = _run_with_stall_guard(
        bottleneck_report_path,
        "DISPATCHREGIONSUM_FILES",
        lambda: market_db.ingest_dispatchregionsum_files(
            demand_files,
            publish_timestamp_utc=publish_timestamp_utc,
        ),
    )
    if demand_result.rows_normalized == 0:
        archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"
        demand_result = _run_with_stall_guard(
            bottleneck_report_path,
            "DISPATCHREGIONSUM_CACHE_LOAD",
            lambda: market_db.ingest_dispatchregionsum_cache(
                raw_archive_dir=archive_dir,
            ),
        )

        if demand_result.rows_normalized > 0:
            source_status = _mark_source_available(
                source_status,
                demand_requirement,
                archive_dir,
                "cache_loaded",
                "SETTLEMENTDATE,REGIONID,TOTALDEMAND,DEMANDFORECAST",
            )

    constraint_files = discover_files(REPO_ROOT, constraint_requirement.glob_patterns)
    constraint_result = _run_with_stall_guard(
        bottleneck_report_path,
        "DISPATCHCONSTRAINT_FILES",
        lambda: market_db.ingest_dispatchconstraint_files(
            constraint_files,
            publish_timestamp_utc=publish_timestamp_utc,
        ),
    )
    if constraint_result.rows_normalized == 0:
        archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchconstraint"
        constraint_result = _run_with_stall_guard(
            bottleneck_report_path,
            "DISPATCHCONSTRAINT_ARCHIVE",
            lambda: market_db.ingest_historical_dispatchconstraint_archive(
                raw_archive_dir=archive_dir,
                publish_timestamp_utc=publish_timestamp_utc,
                start_month="2020-01",
            ),
        )

        if constraint_result.rows_normalized > 0:
            source_status = _mark_source_available(
                source_status,
                constraint_requirement,
                archive_dir,
                "archive_ingested",
                "SETTLEMENTDATE,CONSTRAINTID,MARGINALVALUE,VIOLATIONDEGREE,INTERCONNECTORID,REGIONID",
            )

    market_state_df = market_db.state

    manual_reconcile = market_state_df[
        market_state_df["nsw_qld_spread"].notna()
        & market_state_df["mw_flow"].notna()
        & market_state_df["available_capability_mw"].notna()
        & market_state_df["utilisation_pct"].notna()
    ].copy()
    if not manual_reconcile.empty:
        implied_util = (manual_reconcile["mw_flow"].abs() / manual_reconcile["available_capability_mw"]) * 100.0
        manual_reconcile["implied_utilisation_pct"] = implied_util
        manual_reconcile["utilisation_delta_pct"] = manual_reconcile["utilisation_pct"] - implied_util
        manual_reconcile["price_flow_interval_aligned"] = True
        manual_reconcile = manual_reconcile.sort_values("interval_timestamp_utc").head(15)

    feature_store = build_nsw1_qld1_stub_feature_store(alpha_df)
    pit_report = build_pit_coverage_report(source_status, feature_store)
    validation_report = _build_ingestion_validation_report(
        source_status,
        dispatchprice_rows_read=ingestion_result.rows_read,
        dispatchprice_rows_normalized=ingestion_result.rows_normalized,
        dispatchprice_rows_valid=ingestion_result.rows_valid,
        dispatchprice_files_processed=ingestion_result.files_processed,
        dispatchprice_download_attempts=ingestion_result.download_attempts,
        dispatchprice_download_successes=ingestion_result.download_successes,
        interconnector_rows_read=interconnector_result.rows_read,
        interconnector_rows_normalized=interconnector_result.rows_normalized,
        interconnector_rows_valid=interconnector_result.rows_valid,
        interconnector_files_processed=interconnector_result.files_processed,
        interconnector_download_attempts=interconnector_result.download_attempts,
        interconnector_download_successes=interconnector_result.download_successes,
        demand_rows_read=demand_result.rows_read,
        demand_rows_normalized=demand_result.rows_normalized,
        demand_rows_valid=demand_result.rows_valid,
        demand_files_processed=demand_result.files_processed,
        demand_download_attempts=demand_result.download_attempts,
        demand_download_successes=demand_result.download_successes,
        constraint_rows_read=constraint_result.rows_read,
        constraint_rows_normalized=constraint_result.rows_normalized,
        constraint_rows_valid=constraint_result.rows_valid,
        constraint_files_processed=constraint_result.files_processed,
        constraint_download_attempts=constraint_result.download_attempts,
        constraint_download_successes=constraint_result.download_successes,
    )
    walkforward = _build_walkforward_stub(feature_store)
    driver_attr = _build_driver_attribution_stub(source_status)

    verdict_raw = compute_phase5c_verdict(source_status)
    verdict = "PASS" if verdict_raw == "READY_FOR_MODELLING" else "INSUFFICIENT_DATA"

    source_status.to_csv(source_status_path, index=False)
    schema_df.to_csv(schema_path, index=False)
    market_state_df.to_csv(market_state_path, index=False)
    manual_reconcile.to_csv(manual_reconcile_path, index=False)
    feature_store.to_csv(feature_store_path, index=False)
    pit_report.to_csv(pit_coverage_path, index=False)
    validation_report.to_csv(validation_path, index=False)
    walkforward.to_csv(walkforward_path, index=False)
    driver_attr.to_csv(driver_attr_path, index=False)
    _write_summary(
        summary_path,
        source_status,
        pit_report,
        schema_rows=len(schema_df),
        market_state_rows=len(market_state_df),
        dispatchprice_rows_valid=ingestion_result.rows_valid,
        interconnector_rows_valid=interconnector_result.rows_valid,
        demand_rows_valid=demand_result.rows_valid,
        constraint_rows_valid=constraint_result.rows_valid,
        verdict=verdict,
    )
    _update_register(register_path, verdict)

    required_missing = source_status[(source_status["required"] == True) & (source_status["status"] != "AVAILABLE")]

    print(
        json.dumps(
            {
                "verdict": verdict,
                "required_missing_count": int(required_missing["source_name"].nunique()),
                "required_missing_sources": sorted(required_missing["source_name"].unique().tolist()),
                "outputs": {
                    "ingestion_lineage": str(source_status_path.relative_to(REPO_ROOT)),
                    "feature_store": str(feature_store_path.relative_to(REPO_ROOT)),
                    "market_state_schema": str(schema_path.relative_to(REPO_ROOT)),
                    "market_state": str(market_state_path.relative_to(REPO_ROOT)),
                    "manual_interval_reconciliation": str(manual_reconcile_path.relative_to(REPO_ROOT)),
                    "ingestion_validation": str(validation_path.relative_to(REPO_ROOT)),
                    "pit_coverage": str(pit_coverage_path.relative_to(REPO_ROOT)),
                    "walkforward": str(walkforward_path.relative_to(REPO_ROOT)),
                    "driver_attribution": str(driver_attr_path.relative_to(REPO_ROOT)),
                    "summary": str(summary_path.relative_to(REPO_ROOT)),
                },
            },
            indent=2,
        )
    )


def profile_pipeline() -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    profile_rows: list[dict[str, object]] = []

    try:
        alpha_df = _profile_stage(
            stage="Load alpha database",
            function_name="pd.read_csv",
            run=lambda: pd.read_csv(alpha_path),
            profile_rows=profile_rows,
            rows_extractor=lambda frame: int(len(frame)),
            files_extractor=lambda _: 1,
        )
        source_status = _profile_stage(
            stage="Assess source availability",
            function_name="assess_source_availability",
            run=lambda: assess_source_availability(REPO_ROOT),
            profile_rows=profile_rows,
            rows_extractor=lambda frame: int(len(frame)),
            files_extractor=lambda _: 0,
        )
        market_db = _profile_stage(
            stage="Initialize market state db",
            function_name="MarketStateDatabase.__init__",
            run=lambda: MarketStateDatabase(),
            profile_rows=profile_rows,
            rows_extractor=lambda _: 0,
            files_extractor=lambda _: 0,
        )

        dispatchprice_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHPRICE")
        interconnector_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHINTERCONNECTORRES")
        demand_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "REGIONAL_DEMAND")
        constraint_requirement = next(r for r in REQUIRED_SOURCES if r.source_name == "DISPATCHCONSTRAINT")

        publish_timestamp_utc = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

        dispatchprice_files = _profile_stage(
            stage="Discover DISPATCHPRICE files",
            function_name="discover_files",
            run=lambda: discover_files(REPO_ROOT, dispatchprice_requirement.glob_patterns),
            profile_rows=profile_rows,
            rows_extractor=lambda paths: len(paths),
            files_extractor=lambda paths: len(paths),
        )
        ingestion_result = _profile_stage(
            stage="Ingest DISPATCHPRICE files",
            function_name="ingest_dispatchprice_files",
            run=lambda: market_db.ingest_dispatchprice_files(
                dispatchprice_files,
                publish_timestamp_utc=publish_timestamp_utc,
            ),
            profile_rows=profile_rows,
            rows_extractor=lambda result: int(result.rows_read),
            files_extractor=lambda result: int(result.files_processed),
        )
        if ingestion_result.rows_normalized == 0:
            archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchprice"
            _profile_stage(
                stage="Ingest DISPATCHPRICE archive",
                function_name="ingest_historical_dispatchprice_archive",
                run=lambda: market_db.ingest_historical_dispatchprice_archive(
                    raw_archive_dir=archive_dir,
                    publish_timestamp_utc=publish_timestamp_utc,
                    start_month="2020-01",
                ),
                profile_rows=profile_rows,
                rows_extractor=lambda result: int(result.rows_read),
                files_extractor=lambda result: int(result.files_processed),
            )

        interconnector_files = _profile_stage(
            stage="Discover DISPATCHINTERCONNECTORRES files",
            function_name="discover_files",
            run=lambda: discover_files(REPO_ROOT, interconnector_requirement.glob_patterns),
            profile_rows=profile_rows,
            rows_extractor=lambda paths: len(paths),
            files_extractor=lambda paths: len(paths),
        )
        interconnector_result = _profile_stage(
            stage="Ingest DISPATCHINTERCONNECTORRES files",
            function_name="ingest_dispatchinterconnectorres_files",
            run=lambda: market_db.ingest_dispatchinterconnectorres_files(
                interconnector_files,
                publish_timestamp_utc=publish_timestamp_utc,
            ),
            profile_rows=profile_rows,
            rows_extractor=lambda result: int(result.rows_read),
            files_extractor=lambda result: int(result.files_processed),
        )
        if interconnector_result.rows_normalized == 0:
            archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"
            _profile_stage(
                stage="Ingest DISPATCHINTERCONNECTORRES archive",
                function_name="ingest_historical_dispatchinterconnectorres_archive",
                run=lambda: market_db.ingest_historical_dispatchinterconnectorres_archive(
                    raw_archive_dir=archive_dir,
                    publish_timestamp_utc=publish_timestamp_utc,
                    start_month="2020-01",
                ),
                profile_rows=profile_rows,
                rows_extractor=lambda result: int(result.rows_read),
                files_extractor=lambda result: int(result.files_processed),
            )

        demand_files = _profile_stage(
            stage="Discover DISPATCHREGIONSUM files",
            function_name="discover_files",
            run=lambda: discover_files(REPO_ROOT, demand_requirement.glob_patterns),
            profile_rows=profile_rows,
            rows_extractor=lambda paths: len(paths),
            files_extractor=lambda paths: len(paths),
        )
        demand_result = _profile_stage(
            stage="Ingest DISPATCHREGIONSUM files",
            function_name="ingest_dispatchregionsum_files",
            run=lambda: market_db.ingest_dispatchregionsum_files(
                demand_files,
                publish_timestamp_utc=publish_timestamp_utc,
            ),
            profile_rows=profile_rows,
            rows_extractor=lambda result: int(result.rows_read),
            files_extractor=lambda result: int(result.files_processed),
        )
        if demand_result.rows_normalized == 0:
            archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"
            _profile_stage(
                stage="Ingest DISPATCHREGIONSUM archive",
                function_name="ingest_historical_dispatchregionsum_archive",
                run=lambda: market_db.ingest_historical_dispatchregionsum_archive(
                    raw_archive_dir=archive_dir,
                    publish_timestamp_utc=publish_timestamp_utc,
                    start_month="2020-01",
                ),
                profile_rows=profile_rows,
                rows_extractor=lambda result: int(result.rows_read),
                files_extractor=lambda result: int(result.files_processed),
            )

        constraint_files = _profile_stage(
            stage="Discover DISPATCHCONSTRAINT files",
            function_name="discover_files",
            run=lambda: discover_files(REPO_ROOT, constraint_requirement.glob_patterns),
            profile_rows=profile_rows,
            rows_extractor=lambda paths: len(paths),
            files_extractor=lambda paths: len(paths),
        )
        constraint_result = _profile_stage(
            stage="Ingest DISPATCHCONSTRAINT files",
            function_name="ingest_dispatchconstraint_files",
            run=lambda: market_db.ingest_dispatchconstraint_files(
                constraint_files,
                publish_timestamp_utc=publish_timestamp_utc,
            ),
            profile_rows=profile_rows,
            rows_extractor=lambda result: int(result.rows_read),
            files_extractor=lambda result: int(result.files_processed),
        )
        if constraint_result.rows_normalized == 0:
            archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchconstraint"
            _profile_stage(
                stage="Ingest DISPATCHCONSTRAINT archive",
                function_name="ingest_historical_dispatchconstraint_archive",
                run=lambda: market_db.ingest_historical_dispatchconstraint_archive(
                    raw_archive_dir=archive_dir,
                    publish_timestamp_utc=publish_timestamp_utc,
                    start_month="2020-01",
                ),
                profile_rows=profile_rows,
                rows_extractor=lambda result: int(result.rows_read),
                files_extractor=lambda result: int(result.files_processed),
            )

        market_state_df = _profile_stage(
            stage="Build market state frame",
            function_name="MarketStateDatabase.state",
            run=lambda: market_db.state,
            profile_rows=profile_rows,
            rows_extractor=lambda frame: int(len(frame)),
            files_extractor=lambda _: 0,
        )
        _profile_stage(
            stage="Build stub feature store",
            function_name="build_nsw1_qld1_stub_feature_store",
            run=lambda: build_nsw1_qld1_stub_feature_store(alpha_df),
            profile_rows=profile_rows,
            rows_extractor=lambda frame: int(len(frame)),
            files_extractor=lambda _: 0,
        )
        _profile_stage(
            stage="Build PIT coverage report",
            function_name="build_pit_coverage_report",
            run=lambda: build_pit_coverage_report(source_status, pd.DataFrame()),
            profile_rows=profile_rows,
            rows_extractor=lambda frame: int(len(frame)),
            files_extractor=lambda _: 0,
        )

        _write_stage_profile(reports_dir, profile_rows)
        print(
            json.dumps(
                {
                    "status": "PROFILE_COMPLETED",
                    "market_state_rows": int(len(market_state_df)),
                    "profile_output": "reports/phase5c_stage_profile.csv",
                },
                indent=2,
            )
        )
        return 0
    except StageTimeoutError as timeout_error:
        _write_timeout_bottleneck_report(reports_dir, timeout_error, profile_rows)
        _write_stage_profile(reports_dir, profile_rows)
        return 2


def build_dispatchprice_cache(*, diagnostic_one_file: bool, start_month: str, end_month: str | None) -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchprice"

    market_db = MarketStateDatabase()
    publish_timestamp_utc = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    result = market_db.ingest_historical_dispatchprice_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc=publish_timestamp_utc,
        start_month=start_month,
        end_month=end_month,
        reports_dir=reports_dir,
        diagnostic_one_file=diagnostic_one_file,
    )
    print(
        json.dumps(
            {
                "mode": "dispatchprice_cache_build",
                "diagnostic_one_file": diagnostic_one_file,
                "rows_read": result.rows_read,
                "rows_normalized": result.rows_normalized,
                "rows_valid": result.rows_valid,
                "files_processed": result.files_processed,
                "manifest": "reports/phase5c_dispatchprice_ingestion_manifest.csv",
                "cache_report": "reports/phase5c_dispatchprice_cache_report.md",
                "failed_files": "reports/phase5c_dispatchprice_failed_files.csv",
            },
            indent=2,
        )
    )
    return 0


def build_dispatchinterconnectorres_cache(*, diagnostic_one_file: bool, start_month: str, end_month: str | None) -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"

    market_db = MarketStateDatabase()
    publish_timestamp_utc = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    result = market_db.ingest_historical_dispatchinterconnectorres_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc=publish_timestamp_utc,
        start_month=start_month,
        end_month=end_month,
        reports_dir=reports_dir,
        diagnostic_one_file=diagnostic_one_file,
    )
    print(
        json.dumps(
            {
                "mode": "dispatchinterconnectorres_cache_build",
                "diagnostic_one_file": diagnostic_one_file,
                "rows_read": result.rows_read,
                "rows_normalized": result.rows_normalized,
                "rows_valid": result.rows_valid,
                "files_processed": result.files_processed,
                "manifest": "reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv",
                "cache_report": "reports/phase5c_dispatchinterconnectorres_cache_report.md",
                "failed_files": "reports/phase5c_dispatchinterconnectorres_failed_files.csv",
            },
            indent=2,
        )
    )
    return 0


def build_dispatchregionsum_cache(*, diagnostic_one_file: bool, start_month: str, end_month: str | None) -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"

    market_db = MarketStateDatabase()
    publish_timestamp_utc = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    result = market_db.ingest_historical_dispatchregionsum_archive(
        raw_archive_dir=archive_dir,
        publish_timestamp_utc=publish_timestamp_utc,
        start_month=start_month,
        end_month=end_month,
        reports_dir=reports_dir,
        diagnostic_one_file=diagnostic_one_file,
    )
    print(
        json.dumps(
            {
                "mode": "dispatchregionsum_cache_build",
                "diagnostic_one_file": diagnostic_one_file,
                "rows_read": result.rows_read,
                "rows_normalized": result.rows_normalized,
                "rows_valid": result.rows_valid,
                "files_processed": result.files_processed,
                "manifest": "reports/phase5c_dispatchregionsum_ingestion_manifest.csv",
                "cache_report": "reports/phase5c_dispatchregionsum_cache_report.md",
                "failed_files": "reports/phase5c_dispatchregionsum_failed_files.csv",
            },
            indent=2,
        )
    )
    return 0


def build_nsw1_qld1_quarter_market_state(quarter: str = "2020Q1") -> int:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    market_db = MarketStateDatabase()
    price_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchprice"
    flow_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchinterconnectorres"
    demand_dir = REPO_ROOT / "data" / "raw" / "aemo" / "mmsdm_dispatchregionsum"
    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"

    price_result = market_db.ingest_dispatchprice_cache(price_dir)
    flow_result = market_db.ingest_dispatchinterconnectorres_cache(flow_dir)
    demand_result = market_db.ingest_dispatchregionsum_cache(demand_dir)

    state = market_db.state.copy()
    state["interval_timestamp_utc"] = pd.to_datetime(state["interval_timestamp_utc"], utc=True, errors="coerce")
    start, end = _quarter_bounds(quarter)
    state = state[(state["interval_timestamp_utc"] >= start) & (state["interval_timestamp_utc"] < end)].copy()

    demand_component = market_db.load_dispatchregionsum_component_cache(demand_dir)
    demand_component = demand_component.copy()
    if demand_component.empty:
        period = pd.Period(quarter, freq="Q")
        month_periods = pd.period_range(period.start_time, period.end_time, freq="M")
        fallback_frames = []
        for mp in month_periods:
            archive_path = demand_dir / f"PUBLIC_DVD_DISPATCHREGIONSUM_{mp.year}{mp.month:02d}010000.zip"
            if not archive_path.exists():
                continue
            raw = MarketStateDatabase.parse_dispatchregionsum_archive_bytes(archive_path.read_bytes())
            if raw.empty:
                continue
            cols_upper = {str(col).upper(): col for col in raw.columns}
            if not {"SETTLEMENTDATE", "REGIONID", "TOTALDEMAND"}.issubset(cols_upper):
                continue
            fallback = pd.DataFrame(
                {
                    "interval_timestamp_utc": pd.to_datetime(raw[cols_upper["SETTLEMENTDATE"]], utc=True, errors="coerce"),
                    "region_id": raw[cols_upper["REGIONID"]].astype(str).str.upper().str.strip(),
                    "regional_operational_demand": pd.to_numeric(raw[cols_upper["TOTALDEMAND"]], errors="coerce"),
                    "forecast_demand": pd.to_numeric(raw[cols_upper.get("DEMANDFORECAST", "TOTALDEMAND")], errors="coerce") if cols_upper.get("DEMANDFORECAST") else pd.NA,
                    "source_file": str(archive_path),
                    "publish_timestamp_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
            fallback = fallback[
                fallback["interval_timestamp_utc"].notna()
                & fallback["region_id"].isin(["NSW1", "QLD1"])
            ].copy()
            if not fallback.empty:
                fallback_frames.append(fallback)
        if fallback_frames:
            demand_component = pd.concat(fallback_frames, ignore_index=True)
    if not demand_component.empty:
        demand_component["interval_timestamp_utc"] = pd.to_datetime(demand_component["interval_timestamp_utc"], utc=True, errors="coerce")
        demand_component = demand_component[
            (demand_component["interval_timestamp_utc"] >= start)
            & (demand_component["interval_timestamp_utc"] < end)
        ].copy()

    joined = _build_nsw1_qld1_joined_table(state, demand_component)
    joined, duplicate_irsr_matches, irsr_source = _attach_interval_irsr(joined, quarter, REPO_ROOT)

    alpha_df = pd.read_csv(alpha_path)
    alpha_q = alpha_df.copy()
    quarter_key = quarter if quarter.startswith("C") else f"C{quarter}"
    alpha_q = alpha_q[alpha_q.get("quarter", pd.Series(dtype=str)).astype(str).isin([quarter, quarter_key])].copy()
    realised_payout_label = pd.to_numeric(alpha_q.get("final_realised_payout_per_unit", pd.Series(dtype=float)), errors="coerce").mean() if not alpha_q.empty else pd.NA
    seasonal_benchmark_label = pd.to_numeric(alpha_q.get("auction_clearing_price", pd.Series(dtype=float)), errors="coerce").mean() if not alpha_q.empty else pd.NA
    regime_adjusted_benchmark_label = pd.to_numeric(alpha_q.get("fair_value_forecast", pd.Series(dtype=float)), errors="coerce").mean() if not alpha_q.empty else pd.NA
    joined["label_realised_payout_per_unit"] = realised_payout_label
    joined["label_seasonal_benchmark"] = seasonal_benchmark_label
    joined["label_regime_adjusted_benchmark"] = regime_adjusted_benchmark_label
    joined["label_dev_vs_seasonal_benchmark"] = pd.to_numeric(joined["label_realised_payout_per_unit"], errors="coerce") - pd.to_numeric(joined["label_seasonal_benchmark"], errors="coerce")
    joined["label_dev_vs_regime_adjusted_benchmark"] = pd.to_numeric(joined["label_realised_payout_per_unit"], errors="coerce") - pd.to_numeric(joined["label_regime_adjusted_benchmark"], errors="coerce")
    diagnostics = _quarter_validation_diagnostics(joined, quarter)
    corr = _correlation_report(joined, alpha_df, quarter)

    quarterly_reconstructed_irsr = float(pd.to_numeric(joined["realised_irsr"], errors="coerce").fillna(0.0).sum())
    official_quarterly_irsr = pd.NA
    setirsurplus_path = REPO_ROOT / "data" / "derived" / "irsr" / "setirsurplus_quarterly_all.csv"
    if setirsurplus_path.exists():
        qdf = pd.read_csv(setirsurplus_path)
        official = qdf[
            qdf["quarter"].astype(str).isin([quarter, quarter_key])
            & qdf["interconnector_id"].astype(str).str.upper().eq("NSW1-QLD1")
            & qdf["from_region"].astype(str).str.upper().eq("NSW1")
        ]
        if not official.empty:
            official_quarterly_irsr = float(pd.to_numeric(official["surplus_aud"], errors="coerce").sum())

    reconciliation_variance = (
        quarterly_reconstructed_irsr - float(official_quarterly_irsr)
        if pd.notna(official_quarterly_irsr)
        else pd.NA
    )

    diagnostics.update(
        {
            "missing_nsw_demand": int(pd.to_numeric(joined["nsw_demand"], errors="coerce").isna().sum()),
            "missing_qld_demand": int(pd.to_numeric(joined["qld_demand"], errors="coerce").isna().sum()),
            "missing_realised_irsr": int(pd.to_numeric(joined["realised_irsr"], errors="coerce").isna().sum()),
            "duplicate_irsr_matches": int(duplicate_irsr_matches),
            "quarterly_reconstructed_irsr": quarterly_reconstructed_irsr,
            "official_quarterly_irsr": (None if pd.isna(official_quarterly_irsr) else float(official_quarterly_irsr)),
            "reconciliation_variance": (None if pd.isna(reconciliation_variance) else float(reconciliation_variance)),
            "irsr_source": irsr_source,
        }
    )

    manual = joined.copy()
    manual["implied_utilisation_pct"] = (
        pd.to_numeric(manual["interconnector_flow_mw"], errors="coerce").abs()
        / pd.to_numeric(manual["import_capability_mw"], errors="coerce")
    ) * 100.0
    manual["utilisation_delta_pct"] = pd.to_numeric(manual["utilisation_pct"], errors="coerce") - pd.to_numeric(manual["implied_utilisation_pct"], errors="coerce")
    manual = manual.sort_values("interval_timestamp_utc").head(20)

    trace = pd.DataFrame(columns=["raw_interval", "raw_region", "raw_totaldemand", "cache_interval", "cache_region", "cache_totaldemand", "joined_interval", "joined_nsw_demand", "joined_qld_demand"])
    jan_archive = demand_dir / "PUBLIC_DVD_DISPATCHREGIONSUM_202001010000.zip"
    if jan_archive.exists() and not demand_component.empty:
        raw = MarketStateDatabase.parse_dispatchregionsum_archive_bytes(jan_archive.read_bytes())
        raw["raw_interval"] = pd.to_datetime(raw.get("SETTLEMENTDATE"), utc=True, errors="coerce")
        raw["raw_region"] = raw.get("REGIONID", pd.Series(dtype=str)).astype(str).str.upper().str.strip()
        raw["raw_totaldemand"] = pd.to_numeric(raw.get("TOTALDEMAND"), errors="coerce")
        raw = raw[raw["raw_region"].isin(["NSW1", "QLD1"]) & raw["raw_interval"].notna()].copy()
        raw = raw[["raw_interval", "raw_region", "raw_totaldemand"]].head(20)

        cache = demand_component.copy()
        cache = cache.rename(
            columns={
                "interval_timestamp_utc": "cache_interval",
                "region_id": "cache_region",
                "regional_operational_demand": "cache_totaldemand",
            }
        )
        cache = cache[["cache_interval", "cache_region", "cache_totaldemand"]]

        joined_lookup = joined[["interval_timestamp_utc", "nsw_demand", "qld_demand"]].copy()
        joined_lookup["joined_interval"] = pd.to_datetime(joined_lookup["interval_timestamp_utc"], utc=True, errors="coerce")
        joined_lookup = joined_lookup[["joined_interval", "nsw_demand", "qld_demand"]]

        trace = raw.merge(
            cache,
            left_on=["raw_interval", "raw_region"],
            right_on=["cache_interval", "cache_region"],
            how="left",
        ).merge(
            joined_lookup,
            left_on="raw_interval",
            right_on="joined_interval",
            how="left",
        )
        trace["raw_interval"] = trace["raw_interval"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trace["cache_interval"] = pd.to_datetime(trace["cache_interval"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trace["joined_interval"] = pd.to_datetime(trace["joined_interval"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    joined_path = reports_dir / "phase5c_nsw1_qld1_joined_interval_table.csv"
    manual_path = reports_dir / "phase5c_nsw1_qld1_manual_reconciliation_20.csv"
    diagnostics_path = reports_dir / "phase5c_nsw1_qld1_validation_diagnostics.json"
    corr_path = reports_dir / "phase5c_nsw1_qld1_correlation_report.csv"
    trace_path = reports_dir / "phase5c_nsw1_qld1_demand_trace_20.csv"

    joined.to_csv(joined_path, index=False)
    manual.to_csv(manual_path, index=False)
    corr.to_csv(corr_path, index=False)
    trace.to_csv(trace_path, index=False)
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "quarter": quarter,
                "cache_load": {
                    "dispatchprice_files": price_result.files_processed,
                    "interconnector_files": flow_result.files_processed,
                    "demand_files": demand_result.files_processed,
                },
                "joined_rows": int(len(joined)),
                "diagnostics": diagnostics,
                "outputs": {
                    "joined_table": str(joined_path.relative_to(REPO_ROOT)),
                    "manual_reconciliation_20": str(manual_path.relative_to(REPO_ROOT)),
                    "demand_trace_20": str(trace_path.relative_to(REPO_ROOT)),
                    "validation_diagnostics": str(diagnostics_path.relative_to(REPO_ROOT)),
                    "correlation_report": str(corr_path.relative_to(REPO_ROOT)),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 5C pipeline runner")
    parser.add_argument(
        "--full-run",
        action="store_true",
        help="Run full pipeline output generation (default is profiling mode).",
    )
    parser.add_argument(
        "--build-dispatchprice-cache",
        action="store_true",
        help="Build/refresh incremental DISPATCHPRICE normalized cache only.",
    )
    parser.add_argument(
        "--build-dispatchinterconnectorres-cache",
        action="store_true",
        help="Build/refresh incremental DISPATCHINTERCONNECTORRES normalized cache only.",
    )
    parser.add_argument(
        "--build-dispatchregionsum-cache",
        action="store_true",
        help="Build/refresh incremental DISPATCHREGIONSUM normalized cache only.",
    )
    parser.add_argument(
        "--build-quarter-market-state",
        action="store_true",
        help="Build NSW1-QLD1 quarter joined interval table from cached components only.",
    )
    parser.add_argument(
        "--run-phase5c3",
        action="store_true",
        help="Run Phase 5C.3 authoritative quarter selection and reconciliation report pack.",
    )
    parser.add_argument(
        "--diagnostic-one-file",
        action="store_true",
        help="When building DISPATCHPRICE cache, process only one archive.",
    )
    parser.add_argument(
        "--start-month",
        default="2020-01",
        help="Start month for cache build in YYYY-MM format.",
    )
    parser.add_argument(
        "--end-month",
        default=None,
        help="Optional end month for cache build in YYYY-MM format.",
    )
    parser.add_argument(
        "--quarter",
        default="2020Q1",
        help="Quarter token for joined market-state build, e.g. 2020Q1.",
    )
    parser.add_argument(
        "--phase5c3-quarter",
        default=None,
        help="Optional Phase 5C.3 override quarter token, e.g. 2025Q1.",
    )
    args = parser.parse_args()

    if args.build_dispatchprice_cache:
        sys.exit(
            build_dispatchprice_cache(
                diagnostic_one_file=args.diagnostic_one_file,
                start_month=args.start_month,
                end_month=args.end_month,
            )
        )
    elif args.build_dispatchinterconnectorres_cache:
        sys.exit(
            build_dispatchinterconnectorres_cache(
                diagnostic_one_file=args.diagnostic_one_file,
                start_month=args.start_month,
                end_month=args.end_month,
            )
        )
    elif args.build_dispatchregionsum_cache:
        sys.exit(
            build_dispatchregionsum_cache(
                diagnostic_one_file=args.diagnostic_one_file,
                start_month=args.start_month,
                end_month=args.end_month,
            )
        )
    elif args.build_quarter_market_state:
        sys.exit(build_nsw1_qld1_quarter_market_state(quarter=args.quarter))
    elif args.run_phase5c3:
        sys.exit(run_phase5c3(quarter_override=args.phase5c3_quarter))
    elif args.full_run:
        try:
            main()
        except IngestionStalledError:
            sys.exit(2)
    else:
        sys.exit(profile_pipeline())
