#!/usr/bin/env python3
"""Phase 4B Quant Research Analyst Runner.

Runs strict validator + attribution and generates recurring research outputs:
1) error waterfall
2) R&D ROI table
3) forecast maturity score
4) executive summary answering key questions
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

EFFORT_MAP = {
    "price_error": "Medium",
    "flow_error": "Medium",
    "constraint_error": "High",
    "settlement_model_error": "High",
    "unit_table_rules_error": "Low",
    "optimiser_execution_error": "Low",
    "unattributed_investigation": "High",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 4B quant research analyst runner")
    parser.add_argument("--baseline-residual", type=float, default=92_859_173.4917)
    parser.add_argument("--stale-days", type=int, default=60)
    parser.add_argument(
        "--component-exports",
        type=str,
        default="",
        help="Optional external component export; if omitted validator derives from alpha db.",
    )
    return parser.parse_args()


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, check=True, cwd=REPO_ROOT)


def maturity_from_coverage(coverage: float, residual_share: float) -> float:
    # conservative maturity: mostly coverage-driven, penalized by unattributed residual.
    score = 100.0 * (0.7 * coverage + 0.3 * (1.0 - residual_share))
    return max(0.0, min(100.0, score))


def main() -> None:
    args = parse_args()
    reports = REPO_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    # 1) validator
    validator_cmd = ["python", "scripts/phase4b_component_validator.py", "--stale-days", str(args.stale_days)]
    if args.component_exports:
        validator_cmd += ["--component-exports", args.component_exports]
    run_cmd(validator_cmd)

    # 2) attribution with validated rows only
    run_cmd(
        [
            "python",
            "scripts/phase4b_error_attribution.py",
            "--component-exports",
            "reports/phase4b_component_validated_for_attribution.csv",
        ]
    )

    # Load outputs
    trade = pd.read_csv(reports / "phase4b_trade_level_attribution.csv")
    grouped = pd.read_csv(reports / "phase4b_grouped_attribution.csv")
    coverage_trade = pd.read_csv(reports / "phase4b_component_completeness_by_trade.csv")
    coverage_corridor = pd.read_csv(reports / "phase4b_component_coverage_by_corridor.csv")
    coverage_tranche = pd.read_csv(reports / "phase4b_component_coverage_by_tranche.csv")
    missing_rank = pd.read_csv(reports / "phase4b_ranked_missing_fields_by_value.csv")
    improvements = pd.read_csv(reports / "phase4b_ranked_model_improvements.csv")
    validation_diag = pd.read_csv(reports / "phase4b_component_row_diagnostics.csv")

    # Core explained vs residual
    total_abs = float(trade["total_error_aud_abs"].sum())
    known_abs = float(trade["known_error_aud_abs_sum"].sum())
    unattributed_abs = float(trade["unattributed_error_aud_abs"].sum())

    explained_pct = (known_abs / total_abs * 100.0) if total_abs else 0.0
    residual_pct = (unattributed_abs / total_abs * 100.0) if total_abs else 0.0

    baseline_residual = args.baseline_residual
    residual_reduction = baseline_residual - unattributed_abs
    residual_reduction_pct = (residual_reduction / baseline_residual * 100.0) if baseline_residual else 0.0

    # Waterfall
    components = [
        "price_error",
        "flow_error",
        "constraint_error",
        "settlement_model_error",
        "unit_table_rules_error",
        "optimiser_execution_error",
    ]

    rows = [
        {"stage": "Total Forecast Error", "aud_abs": total_abs, "pct_of_total": 100.0 if total_abs else 0.0},
    ]
    for c in components:
        aud = float(trade[f"{c}_aud_abs"].sum())
        rows.append({"stage": c, "aud_abs": aud, "pct_of_total": (aud / total_abs * 100.0) if total_abs else 0.0})
    rows.append({"stage": "Unattributed Error", "aud_abs": unattributed_abs, "pct_of_total": residual_pct})

    waterfall = pd.DataFrame(rows)
    waterfall.to_csv(reports / "phase4b_error_waterfall.csv", index=False)

    # R&D ROI table from improvements
    roi = improvements.copy()
    roi["Effort"] = roi["improvement_area"].map(EFFORT_MAP).fillna("Medium")
    roi["Estimated_PnL_Gain_AUD"] = roi["estimated_gain_if_50pct_reduced_aud"]
    roi = roi.sort_values("Estimated_PnL_Gain_AUD", ascending=False).reset_index(drop=True)
    roi["Priority"] = roi.index + 1
    roi = roi[["improvement_area", "Estimated_PnL_Gain_AUD", "Effort", "Priority"]]
    roi.to_csv(reports / "phase4b_rd_roi_table.csv", index=False)

    # Maturity score by component group
    comp_groups = [
        "price_forecasts",
        "flow_forecasts",
        "constraint_forecasts",
        "settlement_model_outputs",
        "unit_table_rule_metadata",
        "optimiser_execution_outputs",
    ]

    # Map from component group to corresponding error category for residual weighting
    group_to_category = {
        "price_forecasts": "price_error",
        "flow_forecasts": "flow_error",
        "constraint_forecasts": "constraint_error",
        "settlement_model_outputs": "settlement_model_error",
        "unit_table_rule_metadata": "unit_table_rules_error",
        "optimiser_execution_outputs": "optimiser_execution_error",
    }

    maturity_rows = []
    for g in comp_groups:
        cov_col = f"completeness_{g}"
        coverage = float(coverage_trade[cov_col].mean()) if cov_col in coverage_trade.columns else 0.0

        cat = group_to_category[g]
        cat_abs = float(trade[f"{cat}_aud_abs"].sum())
        # local residual proxy: if component contributes little due missing data, keep maturity low via low coverage.
        local_residual_share = 1.0 - (cat_abs / total_abs) if total_abs else 1.0

        maturity = maturity_from_coverage(coverage, local_residual_share)
        maturity_rows.append(
            {
                "Component": g,
                "CoveragePct": coverage * 100.0,
                "MaturityScore": maturity,
            }
        )

    maturity_df = pd.DataFrame(maturity_rows).sort_values("MaturityScore", ascending=False)
    maturity_df.to_csv(reports / "phase4b_forecast_maturity.csv", index=False)

    # Dominant source
    non_total = waterfall[~waterfall["stage"].isin(["Total Forecast Error", "Unattributed Error"])].copy()
    if len(non_total):
        dominant_row = non_total.sort_values("aud_abs", ascending=False).iloc[0]
        dominant_component = str(dominant_row["stage"])
        dominant_component_cost = float(dominant_row["aud_abs"])
    else:
        dominant_component = "none"
        dominant_component_cost = 0.0

    # If all known components are zero, dominant is unattributed investigation
    if dominant_component_cost <= 0:
        dominant_component = "unattributed_investigation"
        dominant_component_cost = unattributed_abs

    # Best next improvement by commercial value
    best = roi.iloc[0] if len(roi) else None

    # Weakest coverage corridors/tranches
    weak_corr = coverage_corridor.sort_values("mean_coverage").head(5)
    weak_tr = coverage_tranche.sort_values("mean_coverage").head(5)

    # Validation quality stats
    total_rows = len(validation_diag)
    leakage_rows = int(validation_diag["timestamp_leakage"].sum()) if "timestamp_leakage" in validation_diag.columns else 0
    stale_rows = int(validation_diag["timestamp_stale"].sum()) if "timestamp_stale" in validation_diag.columns else 0
    blocked_rows = int((~validation_diag["is_valid_for_attribution"]).sum()) if "is_valid_for_attribution" in validation_diag.columns else 0

    summary = [
        "# Phase 4B Quant Research Analyst Summary",
        "",
        "## Core Attribution KPIs",
        f"- Explained forecast error: `${known_abs:,.2f}` ({explained_pct:.2f}%)",
        f"- Unattributed residual: `${unattributed_abs:,.2f}` ({residual_pct:.2f}%)",
        f"- Target check (>90% explained): `{'PASS' if explained_pct >= 90 else 'FAIL'}`",
        "",
        "## Residual Progress vs Baseline",
        f"- Baseline residual reference: `${baseline_residual:,.2f}`",
        f"- Current residual: `${unattributed_abs:,.2f}`",
        f"- Residual reduction: `${residual_reduction:,.2f}` ({residual_reduction_pct:.2f}%)",
        "",
        "## Dominant Loss Driver",
        f"- Dominant component: `{dominant_component}`",
        f"- Estimated cost contribution: `${dominant_component_cost:,.2f}`",
        "",
        "## Best Single Improvement This Month",
    ]

    if best is not None:
        summary.extend(
            [
                f"- Improvement: `{best['improvement_area']}`",
                f"- Expected P&L gain (50% error reduction scenario): `${best['Estimated_PnL_Gain_AUD']:,.2f}`",
                f"- Effort: `{best['Effort']}`",
                f"- Priority: `{int(best['Priority'])}`",
            ]
        )
    else:
        summary.append("- No ranked improvements available")

    summary.extend(
        [
            "",
            "## Validation Integrity",
            f"- Rows checked: `{total_rows:,}`",
            f"- Blocked attribution rows: `{blocked_rows:,}`",
            f"- Timestamp leakage rows: `{leakage_rows:,}`",
            f"- Stale component rows: `{stale_rows:,}`",
            "",
            "## Weakest Component Coverage",
            "",
            "### Corridors",
            "| corridor | rows | mean_coverage | pct_invalid | mean_completeness_score |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for _, r in weak_corr.iterrows():
        summary.append(
            f"| {r['corridor']} | {int(r['rows'])} | {r['mean_coverage']:.3f} | {r['pct_invalid']:.1f}% | {r['mean_completeness_score']:.3f} |"
        )

    summary.extend(
        [
            "",
            "### Tranches",
            "| tranche | rows | mean_coverage | pct_invalid | mean_completeness_score |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for _, r in weak_tr.iterrows():
        summary.append(
            f"| {r['tranche']} | {int(r['rows'])} | {r['mean_coverage']:.3f} | {r['pct_invalid']:.1f}% | {r['mean_completeness_score']:.3f} |"
        )

    summary.extend(
        [
            "",
            "## Core Quant Outputs",
            "- `reports/phase4b_error_waterfall.csv`",
            "- `reports/phase4b_rd_roi_table.csv`",
            "- `reports/phase4b_forecast_maturity.csv`",
            "- `reports/phase4b_component_validation_summary.md`",
            "- `reports/phase4b_component_row_diagnostics.csv`",
            "- `reports/phase4b_component_blocked_reasons.csv`",
            "- `reports/phase4b_ranked_missing_fields_by_value.csv`",
        ]
    )

    out = reports / "PHASE4B_QUANT_RESEARCH_SUMMARY.md"
    out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("PHASE 4B QUANT RESEARCH SUMMARY COMPLETE")
    print("=" * 88)
    print(f"Explained: {explained_pct:.2f}% | Unattributed: {residual_pct:.2f}%")
    print(f"Dominant: {dominant_component} (${dominant_component_cost:,.2f})")
    if best is not None:
        print(f"Top improvement: {best['improvement_area']} (${best['Estimated_PnL_Gain_AUD']:,.2f})")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
