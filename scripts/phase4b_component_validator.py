#!/usr/bin/env python3
"""Strict component-export validator for Phase 4B.

Outputs:
- reports/phase4b_component_validation_summary.md
- reports/phase4b_component_row_diagnostics.csv
- reports/phase4b_component_blocked_reasons.csv
- reports/phase4b_component_completeness_by_trade.csv
- reports/phase4b_component_coverage_by_corridor.csv
- reports/phase4b_component_coverage_by_tranche.csv
- reports/phase4b_ranked_missing_fields_by_value.csv
- reports/phase4b_component_validated_for_attribution.csv

If --component-exports is omitted, generates a minimal derived export from alpha db:
- reports/phase4b_component_export_from_alpha.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

KEY_FIELDS = ["product_id", "quarter", "tranche"]

COMPONENT_GROUPS = {
    "price_forecasts": [
        "regional_price_forecast",
        "regional_price_actual",
        "regional_price_to_payout_sensitivity",
        "price_published_timestamp",
    ],
    "flow_forecasts": [
        "interconnector_flow_forecast",
        "interconnector_flow_actual",
        "flow_to_payout_sensitivity",
        "flow_published_timestamp",
    ],
    "constraint_forecasts": [
        "constraint_forecast",
        "constraint_actual",
        "constraint_to_payout_sensitivity",
        "constraint_published_timestamp",
    ],
    "settlement_model_outputs": [
        "settlement_residue_forecast",
        "settlement_residue_actual",
        "settlement_residue_to_payout_sensitivity",
        "unit_payout_forecast",
        "unit_payout_actual",
        "settlement_published_timestamp",
    ],
    "unit_table_rule_metadata": [
        "ruleset_id",
        "unit_table_version",
        "product_definition_version",
        "metadata_published_timestamp",
    ],
    "optimiser_execution_outputs": [
        "execution_price_forecast",
        "execution_price_actual",
        "execution_to_payout_sensitivity",
        "optimiser_version",
        "execution_published_timestamp",
    ],
}

TIMESTAMP_FIELDS = [
    "price_published_timestamp",
    "flow_published_timestamp",
    "constraint_published_timestamp",
    "settlement_published_timestamp",
    "metadata_published_timestamp",
    "execution_published_timestamp",
    "published_timestamp",
]

NUMERIC_FIELDS = {
    "regional_price_forecast",
    "regional_price_actual",
    "regional_price_to_payout_sensitivity",
    "interconnector_flow_forecast",
    "interconnector_flow_actual",
    "flow_to_payout_sensitivity",
    "constraint_forecast",
    "constraint_actual",
    "constraint_to_payout_sensitivity",
    "settlement_residue_forecast",
    "settlement_residue_actual",
    "settlement_residue_to_payout_sensitivity",
    "unit_payout_forecast",
    "unit_payout_actual",
    "execution_price_forecast",
    "execution_price_actual",
    "execution_to_payout_sensitivity",
}



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 4B strict component export validator")
    parser.add_argument(
        "--component-exports",
        type=str,
        default="",
        help="Path to component export CSV. If omitted, derives minimal export from alpha database.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=60,
        help="Max age (days) before component data is flagged stale relative to decision date.",
    )
    return parser.parse_args()



def derive_minimal_component_export(out_path: Path) -> Path:
    alpha_path = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    alpha = pd.read_csv(alpha_path)

    export = pd.DataFrame(
        {
            "product_id": alpha["product_id"],
            "quarter": alpha["quarter"].astype(str),
            "tranche": alpha["tranche"].astype(str),
            "decision_date": pd.to_datetime(alpha["decision_timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "unit_payout_forecast": alpha["fair_value_forecast"],
            "unit_payout_actual": alpha["final_realised_payout_per_unit"],
            "ruleset_id": alpha["ruleset_id"],
            "published_timestamp": alpha["source_timestamp_max"],
            "settlement_published_timestamp": alpha["information_cutoff"],
        }
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_path, index=False)
    return out_path



def load_base_trades() -> pd.DataFrame:
    tpath = REPO_ROOT / "reports" / "backtest_detailed_trades.csv"
    t = pd.read_csv(tpath)
    t["decision_date"] = pd.to_datetime(t["decision_date"], utc=True)
    t["trade_total_error_abs_aud"] = ((t["payout_per_unit"] - t["fair_value_forecast"]) * t["units"]).abs()
    return t



def ensure_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.to_datetime(pd.Series([None] * len(df), index=df.index), utc=True, errors="coerce")
    return pd.to_datetime(df[col], utc=True, errors="coerce")



def main() -> None:
    args = parse_args()
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if args.component_exports:
        comp_path = Path(args.component_exports)
        if not comp_path.is_absolute():
            comp_path = REPO_ROOT / args.component_exports
    else:
        comp_path = derive_minimal_component_export(reports_dir / "phase4b_component_export_from_alpha.csv")

    comp = pd.read_csv(comp_path)
    trades = load_base_trades()

    # Normalize key fields
    for k in KEY_FIELDS:
        if k not in comp.columns:
            comp[k] = np.nan
    comp["quarter"] = comp["quarter"].astype(str)
    comp["tranche"] = comp["tranche"].astype(str)

    # Attach trade context (decision date, corridor, tranche, quarter, outcome, error magnitude)
    join_cols = ["product_id", "quarter", "tranche"]
    trade_ctx = trades[
        [
            "product_id",
            "quarter",
            "tranche",
            "decision_date",
            "corridor",
            "alpha",
            "trade_total_error_abs_aud",
        ]
    ].copy()

    merged = trade_ctx.merge(comp, on=join_cols, how="left", suffixes=("_trade", ""))
    merged["decision_date_trade"] = pd.to_datetime(merged["decision_date"], utc=True, errors="coerce")
    if "decision_date" in comp.columns:
        merged["decision_date_component"] = pd.to_datetime(merged["decision_date"], utc=True, errors="coerce")
    else:
        merged["decision_date_component"] = pd.NaT

    # Parse timestamps
    for ts in TIMESTAMP_FIELDS:
        merged[f"{ts}__parsed"] = ensure_datetime(merged, ts)

    # Validate types for numeric fields if present
    dtype_issues = []
    for col in NUMERIC_FIELDS:
        if col in merged.columns:
            parsed = pd.to_numeric(merged[col], errors="coerce")
            bad = merged[col].notna() & parsed.isna()
            if bad.any():
                dtype_issues.append((col, int(bad.sum())))
            merged[col] = parsed

    # Completeness by component group
    for group, fields in COMPONENT_GROUPS.items():
        present_mask = pd.Series(0, index=merged.index, dtype=float)
        required_count = len(fields)
        for f in fields:
            if f in merged.columns:
                if f in TIMESTAMP_FIELDS:
                    present_mask += merged[f"{f}__parsed"].notna().astype(float)
                else:
                    present_mask += merged[f].notna().astype(float)
            else:
                present_mask += 0.0
        merged[f"completeness_{group}"] = present_mask / required_count

    comp_cols = [f"completeness_{g}" for g in COMPONENT_GROUPS]
    merged["completeness_score"] = merged[comp_cols].mean(axis=1)

    # Timestamp leakage and staleness checks
    merged["timestamp_leakage"] = False
    merged["timestamp_stale"] = False
    merged["timestamp_alignment_issue"] = False

    pub_candidates = [
        "price_published_timestamp__parsed",
        "flow_published_timestamp__parsed",
        "constraint_published_timestamp__parsed",
        "settlement_published_timestamp__parsed",
        "metadata_published_timestamp__parsed",
        "execution_published_timestamp__parsed",
        "published_timestamp__parsed",
    ]

    merged["decision_date_trade"] = pd.to_datetime(merged["decision_date_trade"], utc=True, errors="coerce")
    decision = merged["decision_date_trade"]

    for pc in pub_candidates:
        if pc in merged.columns:
            pub = pd.to_datetime(merged[pc], utc=True, errors="coerce")
            has_both = pub.notna() & decision.notna()
            merged.loc[has_both & (pub > decision), "timestamp_leakage"] = True

            age_days = (decision - pub).dt.total_seconds() / 86400.0
            merged.loc[has_both & (age_days > args.stale_days), "timestamp_stale"] = True
            merged.loc[decision.isna() & pub.notna(), "timestamp_alignment_issue"] = True
            merged.loc[decision.notna() & pub.isna(), "timestamp_alignment_issue"] = True

    # Blocked reasons
    reasons = []
    for idx, row in merged.iterrows():
        r = []

        missing_keys = [k for k in KEY_FIELDS if pd.isna(row.get(k))]
        if missing_keys:
            r.append(f"missing_key_fields:{','.join(missing_keys)}")

        for group in COMPONENT_GROUPS:
            comp_val = row[f"completeness_{group}"]
            if comp_val < 1.0:
                r.append(f"missing_fields_{group}")

        if row["timestamp_leakage"]:
            r.append("future_information_leakage")
        if row["timestamp_stale"]:
            r.append("stale_component_data")
        if row["timestamp_alignment_issue"]:
            r.append("timestamp_alignment_issue")

        reasons.append("|".join(sorted(set(r))) if r else "")

    merged["blocked_attribution_reasons"] = reasons
    merged["is_valid_for_attribution"] = merged["blocked_attribution_reasons"].eq("")

    # Missing fields ranked by expected attribution value
    # Value proxy = sum(abs(trade forecast error)) over rows where field is missing.
    value_proxy = merged["trade_total_error_abs_aud"].fillna(0.0)

    field_rows = []
    for group, fields in COMPONENT_GROUPS.items():
        for f in fields:
            if f in merged.columns:
                if f in TIMESTAMP_FIELDS:
                    miss = merged[f"{f}__parsed"].isna()
                else:
                    miss = merged[f].isna()
            else:
                miss = pd.Series([True] * len(merged), index=merged.index)

            field_rows.append(
                {
                    "component_group": group,
                    "field_name": f,
                    "missing_rows": int(miss.sum()),
                    "missing_pct": float(miss.mean() * 100) if len(miss) else 0.0,
                    "expected_attribution_value_aud": float(value_proxy[miss].sum()),
                }
            )

    ranked_missing = pd.DataFrame(field_rows).sort_values(
        ["expected_attribution_value_aud", "missing_rows"], ascending=[False, False]
    )

    # Coverage weakness by corridor and tranche
    cov = merged.copy()
    if "corridor" not in cov.columns:
        cov["corridor"] = "UNKNOWN"
    if "tranche" not in cov.columns:
        cov["tranche"] = "UNKNOWN"

    cov["component_coverage_mean"] = cov[comp_cols].mean(axis=1)

    by_corridor = (
        cov.groupby("corridor", dropna=False)
        .agg(
            rows=("product_id", "count"),
            mean_coverage=("component_coverage_mean", "mean"),
            pct_invalid=("is_valid_for_attribution", lambda s: (1 - s.mean()) * 100),
            mean_completeness_score=("completeness_score", "mean"),
        )
        .reset_index()
        .sort_values("mean_coverage")
    )

    by_tranche = (
        cov.groupby("tranche", dropna=False)
        .agg(
            rows=("product_id", "count"),
            mean_coverage=("component_coverage_mean", "mean"),
            pct_invalid=("is_valid_for_attribution", lambda s: (1 - s.mean()) * 100),
            mean_completeness_score=("completeness_score", "mean"),
        )
        .reset_index()
        .sort_values("mean_coverage")
    )

    # Blocked reasons table
    blocked = (
        merged[merged["blocked_attribution_reasons"] != ""]
        .copy()[["product_id", "quarter", "tranche", "blocked_attribution_reasons", "completeness_score", "trade_total_error_abs_aud"]]
    )

    # Write outputs
    row_diag_cols = [
        "product_id",
        "quarter",
        "tranche",
        "decision_date_trade",
        "corridor",
        "alpha",
        "trade_total_error_abs_aud",
    ] + comp_cols + [
        "completeness_score",
        "timestamp_leakage",
        "timestamp_stale",
        "timestamp_alignment_issue",
        "blocked_attribution_reasons",
        "is_valid_for_attribution",
    ]

    # ensure columns exist
    for c in row_diag_cols:
        if c not in merged.columns:
            merged[c] = np.nan

    # Validated export for Phase 4B rerun (valid rows only)
    validated = merged[merged["is_valid_for_attribution"]].copy()

    # Keep original export columns to avoid surprising merge behavior in phase4b script
    export_cols = list(comp.columns)
    for c in export_cols:
        if c not in validated.columns:
            validated[c] = np.nan

    summary_md = reports_dir / "phase4b_component_validation_summary.md"
    row_csv = reports_dir / "phase4b_component_row_diagnostics.csv"
    blocked_csv = reports_dir / "phase4b_component_blocked_reasons.csv"
    comp_by_trade_csv = reports_dir / "phase4b_component_completeness_by_trade.csv"
    by_corridor_csv = reports_dir / "phase4b_component_coverage_by_corridor.csv"
    by_tranche_csv = reports_dir / "phase4b_component_coverage_by_tranche.csv"
    ranked_csv = reports_dir / "phase4b_ranked_missing_fields_by_value.csv"
    validated_csv = reports_dir / "phase4b_component_validated_for_attribution.csv"

    merged[row_diag_cols].to_csv(row_csv, index=False)
    merged[["product_id", "quarter", "tranche", *comp_cols, "completeness_score", "is_valid_for_attribution"]].to_csv(
        comp_by_trade_csv, index=False
    )
    blocked.to_csv(blocked_csv, index=False)
    by_corridor.to_csv(by_corridor_csv, index=False)
    by_tranche.to_csv(by_tranche_csv, index=False)
    ranked_missing.to_csv(ranked_csv, index=False)
    validated[export_cols].to_csv(validated_csv, index=False)

    total_rows = len(merged)
    valid_rows = int(merged["is_valid_for_attribution"].sum())
    blocked_rows = total_rows - valid_rows

    leakage_rows = int(merged["timestamp_leakage"].sum())
    stale_rows = int(merged["timestamp_stale"].sum())
    alignment_rows = int(merged["timestamp_alignment_issue"].sum())

    dtype_lines = [f"- {col}: {cnt} bad rows" for col, cnt in dtype_issues] if dtype_issues else ["- none"]

    weakest_corr = by_corridor.head(5)
    weakest_tr = by_tranche.head(5)

    lines = [
        "# Phase 4B Component Export Validation Summary",
        "",
        f"- Source export: `{comp_path}`",
        f"- Total rows checked: `{total_rows:,}`",
        f"- Valid for attribution: `{valid_rows:,}` ({(valid_rows / total_rows * 100) if total_rows else 0:.1f}%)",
        f"- Blocked rows: `{blocked_rows:,}` ({(blocked_rows / total_rows * 100) if total_rows else 0:.1f}%)",
        "",
        "## Timestamp Integrity",
        f"- Leakage rows (published after decision timestamp): `{leakage_rows:,}`",
        f"- Stale rows (older than {args.stale_days} days): `{stale_rows:,}`",
        f"- Alignment issue rows: `{alignment_rows:,}`",
        "",
        "## Data Type Issues",
        *dtype_lines,
        "",
        "## Component Completeness (mean by group)",
    ]

    for g in COMPONENT_GROUPS:
        lines.append(f"- {g}: `{merged[f'completeness_{g}'].mean():.3f}`")

    lines.extend(
        [
            "",
            "## Weakest Coverage Corridors",
            "",
            "| corridor | rows | mean_coverage | pct_invalid | mean_completeness_score |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for _, r in weakest_corr.iterrows():
        lines.append(
            f"| {r['corridor']} | {int(r['rows'])} | {r['mean_coverage']:.3f} | {r['pct_invalid']:.1f}% | {r['mean_completeness_score']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Weakest Coverage Tranches",
            "",
            "| tranche | rows | mean_coverage | pct_invalid | mean_completeness_score |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for _, r in weakest_tr.iterrows():
        lines.append(
            f"| {r['tranche']} | {int(r['rows'])} | {r['mean_coverage']:.3f} | {r['pct_invalid']:.1f}% | {r['mean_completeness_score']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Output Files",
            f"- `{summary_md.relative_to(REPO_ROOT)}`",
            f"- `{row_csv.relative_to(REPO_ROOT)}`",
            f"- `{blocked_csv.relative_to(REPO_ROOT)}`",
            f"- `{comp_by_trade_csv.relative_to(REPO_ROOT)}`",
            f"- `{by_corridor_csv.relative_to(REPO_ROOT)}`",
            f"- `{by_tranche_csv.relative_to(REPO_ROOT)}`",
            f"- `{ranked_csv.relative_to(REPO_ROOT)}`",
            f"- `{validated_csv.relative_to(REPO_ROOT)}`",
        ]
    )

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {summary_md}")
    print(f"Saved: {row_csv}")
    print(f"Saved: {blocked_csv}")
    print(f"Saved: {comp_by_trade_csv}")
    print(f"Saved: {by_corridor_csv}")
    print(f"Saved: {by_tranche_csv}")
    print(f"Saved: {ranked_csv}")
    print(f"Saved: {validated_csv}")


if __name__ == "__main__":
    main()
