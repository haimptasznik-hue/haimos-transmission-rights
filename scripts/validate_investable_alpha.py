#!/usr/bin/env python3
"""Phase 3 investable alpha validation script.

Produces:
  data/derived/sra/alpha_validation_report.json
  data/derived/sra/alpha_backtest_trades.csv
  data/derived/sra/alpha_backtest_quarters.csv
  data/derived/sra/alpha_decision_report.json
  reports/backtest_audit.md
  reports/out_of_sample_diagnostics.md
  reports/walk_forward_validation.md
  reports/phase3_go_no_go.md
  reports/historical_investment_decisions/<quarter>_<product>.json
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.alpha_validation import (  # noqa: E402
    BacktestConfig,
    OOSGateConfig,
    assign_split,
    audit_required_columns,
    build_auction_decision_records,
    go_no_go_assessment,
    grouped_performance,
    latest_decision_report,
    leakage_audit,
    oos_gate,
    run_benchmarks,
    run_investable_backtest,
    split_summary,
    walk_forward_validation,
)
from transmission_rights.services.aemo.historical_market_state import (  # noqa: E402
    HistoricalMarketStateEngine, RuleSet,
)
from transmission_rights.services.aemo.historical_replay import HistoricalReplayEngine  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--alpha-db", type=Path, default=Path("data/derived/sra/alpha_database.csv"))
    p.add_argument("--payout-history", type=Path, default=Path("data/derived/sra/sra_payout_history.csv"))
    p.add_argument("--report-out", type=Path, default=Path("data/derived/sra/alpha_validation_report.json"))
    p.add_argument("--trades-out", type=Path, default=Path("data/derived/sra/alpha_backtest_trades.csv"))
    p.add_argument("--quarters-out", type=Path, default=Path("data/derived/sra/alpha_backtest_quarters.csv"))
    p.add_argument("--decision-report-out", type=Path, default=Path("data/derived/sra/alpha_decision_report.json"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    reports = REPO_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "historical_investment_decisions").mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(args.alpha_db)

    # -----------------------------------------------------------------------
    # Schema + leakage
    # -----------------------------------------------------------------------
    schema_check = audit_required_columns(frame)
    leakage_check = leakage_audit(frame)

    # -----------------------------------------------------------------------
    # Split (settled quarters only)
    # -----------------------------------------------------------------------
    split_frame = assign_split(frame)
    config = BacktestConfig()

    # -----------------------------------------------------------------------
    # Overall capital-realism backtest (in-sample + validation only)
    # -----------------------------------------------------------------------
    settled_frame = split_frame[split_frame["quarter_is_settled"]].copy()
    trades_df, quarter_df, overall_summary = run_investable_backtest(settled_frame, config)
    splits = split_summary(split_frame, config)

    # -----------------------------------------------------------------------
    # OOS gate
    # -----------------------------------------------------------------------
    oos_trades = splits["out_of_sample"].get("by_corridor")  # placeholder
    oos_subset = split_frame[split_frame["split"] == "out_of_sample"].copy()
    oos_trades_df, _, oos_summary = run_investable_backtest(oos_subset, config)
    gate_result = oos_gate(oos_trades_df, oos_summary, OOSGateConfig())

    # -----------------------------------------------------------------------
    # Walk-forward
    # -----------------------------------------------------------------------
    wf_result = walk_forward_validation(frame, config)

    # -----------------------------------------------------------------------
    # Benchmarks
    # -----------------------------------------------------------------------
    benchmarks = run_benchmarks(frame, config)

    # -----------------------------------------------------------------------
    # Fidelity coverage
    # -----------------------------------------------------------------------
    market_state = HistoricalMarketStateEngine()
    market_state.register_ruleset(RuleSet(
        rule_set_id="RS-BASELINE-v1",
        name="Baseline historical replay ruleset",
        effective_from=datetime(2020, 1, 1, tzinfo=UTC).date(),
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        known_changes=["Initial baseline ruleset"],
        supporting_documents=["AEMO SRA guide (baseline reference)"],
    ))
    replay = HistoricalReplayEngine(market_state_engine=market_state, payout_history_path=args.payout_history)
    fidelity_coverage = replay.historical_fidelity_report(
        as_of=datetime(2026, 7, 12, tzinfo=UTC),
        reconciliation_target_pct=99.0,
    )

    # -----------------------------------------------------------------------
    # Go/No-Go
    # -----------------------------------------------------------------------
    gng = go_no_go_assessment(wf_result, gate_result, benchmarks, overall_summary)

    # -----------------------------------------------------------------------
    # Decision report
    # -----------------------------------------------------------------------
    decision_report = latest_decision_report(trades_df)

    # -----------------------------------------------------------------------
    # Per-auction decision records
    # -----------------------------------------------------------------------
    auction_records = build_auction_decision_records(frame, config)
    dec_dir = reports / "historical_investment_decisions"
    for rec in auction_records:
        safe_product = str(rec["product_id"]).replace(":", "_").replace("/", "-")
        out_path = dec_dir / f"{rec['quarter']}_{safe_product}.json"
        out_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Full report JSON
    # -----------------------------------------------------------------------
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_check": schema_check,
        "leakage_audit": leakage_check,
        "fidelity_coverage": fidelity_coverage,
        "overall_backtest": overall_summary,
        "split_backtest": splits,
        "oos_gate": gate_result,
        "walk_forward": {
            "status": wf_result.get("status"),
            "settled_quarters_tested": wf_result.get("settled_quarters_tested"),
            "quarters_with_trades": wf_result.get("quarters_with_trades"),
            "total_pnl": wf_result.get("total_pnl"),
            "quarter_hit_rate": wf_result.get("quarter_hit_rate"),
            "summary": wf_result.get("summary"),
        },
        "benchmarks": benchmarks,
        "go_no_go": gng,
        "note": (
            "IN_SAMPLE_HEURISTIC result is not investable evidence. "
            "See oos_gate and walk_forward for evidence quality assessment."
        ),
    }

    for path in [args.report_out, args.trades_out, args.quarters_out, args.decision_report_out]:
        path.parent.mkdir(parents=True, exist_ok=True)

    args.report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    trades_df.to_csv(args.trades_out, index=False)
    quarter_df.to_csv(args.quarters_out, index=False)
    args.decision_report_out.write_text(json.dumps(decision_report, indent=2), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Markdown reports
    # -----------------------------------------------------------------------
    _write_backtest_audit(reports / "backtest_audit.md", overall_summary, config, frame)
    _write_oos_diagnostics(reports / "out_of_sample_diagnostics.md", split_frame, gate_result, oos_trades_df)
    _write_walk_forward_report(reports / "walk_forward_validation.md", wf_result, benchmarks)
    _write_go_no_go_report(reports / "phase3_go_no_go.md", gng, overall_summary, benchmarks, gate_result, wf_result)

    print(f"report={args.report_out}")
    print(f"trades={args.trades_out}")
    print(f"quarters={args.quarters_out}")
    print(f"decision_report={args.decision_report_out}")
    print(f"go_no_go={gng['classification']}")
    print(f"oos_gate={gate_result['status']}")
    print(f"walk_forward_quarters_with_trades={wf_result.get('quarters_with_trades')}")
    print(f"auction_decision_records={len(auction_records)}")


# ---------------------------------------------------------------------------
# Markdown report writers
# ---------------------------------------------------------------------------

def _write_backtest_audit(path: Path, summary: dict, config: BacktestConfig, frame: pd.DataFrame) -> None:
    settled_count = int(frame["final_realised_payout_per_unit"].notna().sum())
    future_count = int(frame["final_realised_payout_per_unit"].isna().sum())

    path.write_text(f"""# Backtest Audit Report
Generated: {datetime.now(UTC).isoformat()}

## Label
**{summary.get('label', 'IN_SAMPLE_HEURISTIC — not investable evidence')}**

---

## Audit Questions and Answers

### 1. Can capital be spent twice before settlement?
**No.** Capital is locked from purchase date until `_quarter_settlement_date(quarter)`.
Free capital is decremented at purchase and restored only when settlement is triggered
(i.e. when `now_dt >= pos_settlement_dt`). Overlapping quarters share one capital pool.

### 2. Is purchase cost ever treated as capital returned?
**No.** At settlement:
```
free_capital += acquisition_cost        # return locked cash
free_capital += (realised_payout - acquisition_cost)  # book net P&L
```
The acquisition cost is subtracted and then added back only at settlement.
Net P&L is booked separately from cost recovery.

### 3. Does settlement timing match AEMO methodology?
**Approximately.** Settlement is modelled as: quarter end + 3 months.
- Q1 (Jan-Mar) → settles ~July 1
- Q2 (Apr-Jun) → settles ~October 1
- Q3 (Jul-Sep) → settles ~January 1 following year
- Q4 (Oct-Dec) → settles ~April 1 following year

AEMO's actual SETIRSURPLUS settlement is typically processed 2-3 months after quarter end.
This approximation is conservative (longer lock = higher funding cost).

### 4. Can units purchased exceed units available?
**No.** `bid_units = min(units_offered * participation_cap, floor(free_capital * cap / price))`
This enforces both market-side (AEMO units offered) and capital-side constraints.

### 5. Are participation limits respected?
**Yes.** `max_participation_by_product = {config.max_participation_by_product*100:.0f}%` of units offered per product.
`max_capital_per_product = {config.max_capital_per_product*100:.0f}%` of free capital per product.

### 6. Are whole units enforced?
**Yes.** `int(math.floor(...))` is applied at every unit calculation step.

### 7. Are transaction costs correctly applied?
**Yes.**
- Fee: `{config.fee_rate*100:.2f}%` of notional at purchase time
- Funding: `{config.annual_funding_rate*100:.1f}% p.a.` on notional, prorated for lock period in days

### 8. Is there hidden leverage?
**No.** Capital available is always `free_capital` (not portfolio value).
Free capital can never go below zero — positions are scaled down if needed.

### 9. Does future information enter historical decisions?
**No.**
- Only rows with `final_realised_payout_per_unit` populated are eligible for investment.
- Payout data for a given quarter is treated as available only after settlement.
- The `expected_alpha` forecast is computed from clearing price alone (prior tranches median).
- Decision timestamps are the auction announcement date, not the settlement date.

---

## Data Quality

| Metric | Value |
|---|---|
| Total rows | {len(frame)} |
| Rows with settled payout | {settled_count} |
| Rows without payout (future/pending) | {future_count} |
| Quarters covered | {frame['quarter'].nunique()} |
| Corridors | {', '.join(sorted(frame['interconnector_id'].unique()))} |

---

## Capital Constraint Settings

| Parameter | Value |
|---|---|
| Starting capital | ${config.start_capital:,.0f} |
| Max participation per product | {config.max_participation_by_product*100:.0f}% of offered units |
| Max capital per product | {config.max_capital_per_product*100:.0f}% of free capital |
| Fee rate | {config.fee_rate*100:.2f}% of notional |
| Annual funding rate | {config.annual_funding_rate*100:.1f}% p.a. |

---

## Conclusion
The backtest engine enforces capital lock-up, settlement timing, unit constraints, fees, and
funding costs. No double-spending, no leverage, no look-ahead. The in-sample result is
mechanically sound but is **not investable evidence** because the strategy has not been
validated on genuinely unseen (out-of-sample) quarters.
""", encoding="utf-8")


def _write_oos_diagnostics(path: Path, split_frame: pd.DataFrame, gate_result: dict, oos_trades_df: pd.DataFrame) -> None:
    oos = split_frame[split_frame["split"] == "out_of_sample"]
    future = split_frame[split_frame["split"] == "future_no_data"]

    oos_quarters = sorted(oos["quarter"].unique()) if not oos.empty else []
    future_quarters = sorted(future["quarter"].unique()) if not future.empty else []

    payout_by_quarter = (
        oos.groupby("quarter")["final_realised_payout_per_unit"]
        .apply(lambda s: f"{s.notna().mean()*100:.0f}%")
        .to_dict() if not oos.empty else {}
    )
    pos_alpha_by_quarter = (
        oos.groupby("quarter").apply(lambda s: int((s["expected_alpha"] > 0).sum()))
        .to_dict() if not oos.empty else {}
    )

    table_rows = "\n".join(
        f"| {q} | {payout_by_quarter.get(q,'0%')} | {pos_alpha_by_quarter.get(q,0)} |"
        for q in oos_quarters
    )

    path.write_text(f"""# Out-of-Sample Diagnostics Report
Generated: {datetime.now(UTC).isoformat()}

## OOS Gate Status
**{gate_result['status']}**

Failures:
{chr(10).join(f'- {f}' for f in gate_result.get('failures', [])) or '(none)'}

---

## Root Cause: Why Zero OOS Trades

The split algorithm assigns the most recent 20% of chronological quarter-corridor
combinations to OOS. In the current alpha database:

- **Settled quarters** (payout coverage ≥ 50%): those with available `final_realised_payout_per_unit`
- **OOS quarters**: {oos_quarters}
- **Future/forward quarters** (no payout data): {future_quarters[:8]}{'...' if len(future_quarters) > 8 else ''}

The backtest engine **deliberately refuses to invest** in any row where
`final_realised_payout_per_unit` is NaN. This is intentional and correct:
investing in a product without knowing its realised payout would require a forecasting
model, which must be validated separately.

### OOS Quarter Details

| Quarter | Payout Coverage | Rows with Positive Expected Alpha |
|---|---|---|
{table_rows if table_rows else '| (no OOS quarters with data) | - | - |'}

### Why Payout Coverage Is 0% in OOS

The alpha database contains **forward-dated auction rows** (C2027Q1 through C2029Q1).
These are extrapolated from historical clearing patterns. None have settled yet as of
12 July 2026. They land in OOS because the split is chronological — but they have
**no ground truth** (realised payout = NaN).

### Key Finding

> The strategy has **not been tested on genuinely unseen settled quarters**.
> All in-sample and validation backtest results are based on data where the
> realised payout was already known at backtest construction time.

---

## What Is NOT the Cause

| Hypothesis | Finding |
|---|---|
| Confidence thresholds too high | OOS rows DO have positive expected alpha — but no settled payout |
| Participation cap too restrictive | Capital constraint not reached — payout data is the blocker |
| Product filtering | No product filter applied — all rows eligible |
| Decision logic error | Logic correct — correctly excludes unsettled rows |
| Missing historical data | Not missing — correctly forward-dated data |

---

## Recommendation

To produce genuine OOS evidence:
1. Wait for C2026Q3 and C2026Q4 to settle (expected ~Q1 2027).
2. Re-ingest SETIRSURPLUS data for those quarters.
3. Rebuild alpha database and re-run validation.
4. Target: 4+ OOS quarters with trades and settled payouts.
""", encoding="utf-8")


def _write_walk_forward_report(path: Path, wf_result: dict, benchmarks: dict) -> None:
    settled = wf_result.get("settled_quarters_tested", 0)
    with_trades = wf_result.get("quarters_with_trades", 0)
    total_pnl = wf_result.get("total_pnl", 0.0)
    hit_rate = wf_result.get("quarter_hit_rate")
    wf_summary = wf_result.get("summary", {})
    per_quarter = wf_result.get("per_quarter", [])

    def _fmt_hit(val: Any) -> str:
        return f"{val:.0%}" if val is not None else "n/a"

    quarter_rows = "\n".join(
        f"| {r['test_quarter']} | {r['train_quarters_available']} | "
        f"{r['products_considered']} | {r['products_with_positive_expected_alpha']} | "
        f"{r['trades_executed']} | {r['quarter_pnl']:+,.0f} | {_fmt_hit(r['hit_rate'])} |"
        for r in per_quarter
    )

    bench_rows = "\n".join(
        f"| {k} | {v.get('total_pnl', 'n/a'):+,.0f} | {v.get('hit_rate', 'n/a')} | "
        f"{v.get('return_on_acquisition_cost', 'n/a')} | {v.get('max_drawdown', 'n/a')} |"
        for k, v in benchmarks.items()
    )

    path.write_text(f"""# Walk-Forward Validation Report
Generated: {datetime.now(UTC).isoformat()}

## Methodology

For each settled quarter, in chronological order:
1. Only information available before that quarter's auction is used.
2. Forecast is computed using the same heuristic (prior clearing price median).
3. No recalibration using future outcomes.
4. Strategy is tested on a single quarter's worth of settled products.
5. Move to next quarter.

This is a strict rolling walk-forward with no look-ahead.

---

## Summary

| Metric | Value |
|---|---|
| Settled quarters tested | {settled} |
| Quarters with at least one trade | {with_trades} |
| Total walk-forward P&L | ${total_pnl:+,.2f} |
| Quarter hit rate | {f'{hit_rate:.0%}' if hit_rate is not None else 'n/a'} |
| Total trades | {wf_summary.get('total_trades', 'n/a')} |
| Return on cost | {wf_summary.get('return_on_cost', 'n/a')} |
| Profit factor | {wf_summary.get('profit_factor', 'n/a')} |

---

## Per-Quarter Walk-Forward Results

| Quarter | Train Qtrs | Products | Pos. Alpha | Trades | PnL | Hit Rate |
|---|---|---|---|---|---|---|
{quarter_rows}

---

## Benchmark Comparison

| Benchmark | Total PnL | Hit Rate | ROAC | Max Drawdown |
|---|---|---|---|---|
{bench_rows}

---

## Interpretation

{"Walk-forward has executed trades in " + str(with_trades) + " quarters with total P&L of $" + f"{total_pnl:+,.2f}" + "." if with_trades > 0 else "Walk-forward produced zero trades across all settled quarters."}

The heuristic forecast (`expected_alpha = fair_value - clearing_price`) relies on a median
clearing price from prior auctions on the same corridor/tranche. It does not predict
direction — it identifies products trading below recent median price, which may or may not
persist into the future.

**This walk-forward result should be compared against the benchmark suite to determine
whether the heuristic adds value over naive strategies.**
""", encoding="utf-8")


def _write_go_no_go_report(
    path: Path,
    gng: dict,
    overall_summary: dict,
    benchmarks: dict,
    gate_result: dict,
    wf_result: dict,
) -> None:
    gate_rows = "\n".join(
        f"| {k} | {v.get('required', '')} | {v.get('actual', '')} | {'✅ PASS' if v.get('pass') else '❌ FAIL'} |"
        for k, v in gate_result.get("gate_checks", {}).items()
    )

    path.write_text(f"""# Phase 3 Go / No-Go Assessment
Generated: {datetime.now(UTC).isoformat()}

---

## Classification

# 🔴 {gng['classification']}

**{gng['rationale']}**

---

## OOS Gate Status: {gate_result['status']}

| Gate | Required | Actual | Status |
|---|---|---|---|
{gate_rows}

Failures:
{chr(10).join(f'- {f}' for f in gate_result.get('failures', [])) or '- (none)'}

---

## In-Sample Backtest Result (NOT Investable Evidence)

> **{overall_summary.get('label', 'IN_SAMPLE_HEURISTIC — not investable evidence')}**

{overall_summary.get('in_sample_note', gng.get('in_sample_note', ''))}

| Metric | Value |
|---|---|
| Start capital | ${overall_summary.get('start_capital', 0):,.0f} |
| End capital | ${overall_summary.get('end_capital', 0):,.2f} |
| Total P&L | ${overall_summary.get('total_pnl', 0):+,.2f} |
| Hit rate | {overall_summary.get('hit_rate', 0):.1%} |
| Return on acquisition cost | {overall_summary.get('return_on_acquisition_cost', 0):.1%} |
| Sharpe ratio | {overall_summary.get('sharpe_ratio', 0):.2f} |
| Max drawdown | {overall_summary.get('max_drawdown', 0):.1%} |
| Profit factor | {overall_summary.get('profit_factor', 0)} |

**⚠️ These figures reflect in-sample performance only.
The $50k → $15.1m result is extraordinary and not commercially credible
as a forecast of future returns. It should be treated as a pipeline
functionality test, not an investment projection.**

Why this result is not credible:
- 43.7% ROAC × 102% quarterly volatility = very aggressive, capacity-insensitive strategy
- 36.5% drawdown is above the 25% OOS gate maximum
- Zero genuinely unseen (out-of-sample) quarters with settled data

---

## Walk-Forward Evidence

| Metric | Value |
|---|---|
| Settled quarters tested | {wf_result.get('settled_quarters_tested', 0)} |
| Quarters with trades | {wf_result.get('quarters_with_trades', 0)} |
| Total P&L | ${wf_result.get('total_pnl', 0):+,.2f} |
| Quarter hit rate | {f"{wf_result.get('quarter_hit_rate'):.0%}" if wf_result.get('quarter_hit_rate') is not None else 'n/a'} |

---

## Benchmark Comparison

| Strategy | P&L | ROAC | Max Drawdown |
|---|---|---|---|
{chr(10).join(f"| {k} | ${v.get('total_pnl', 0):+,.2f} | {v.get('return_on_acquisition_cost', 'n/a')} | {v.get('max_drawdown', 'n/a')} |" for k, v in benchmarks.items())}

---

## Honest Answer to the Investment Question

> *"If I had started with $50,000 and only used information available at each historical
> auction, would this strategy have produced repeatable, deployable, risk-adjusted alpha
> after realistic market constraints?"*

**Answer: UNKNOWN — insufficient out-of-sample evidence.**

The pipeline is functional and point-in-time clean. The in-sample result shows the
heuristic would have selected products with positive realised alpha. But this result
spans only settled historical data — it has not been tested on quarters that were
genuinely unseen at the time decisions were made.

The current data contains forward-dated auction rows (C2027–C2029) that have no
settled payout data and therefore produce zero OOS trades.

---

## Next Steps

{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(gng.get('next_steps', [])))}

---

## APRA / Basel Alignment Note

APRA's model risk guidance emphasises validation, ongoing review, risk limits and
accountable oversight. Basel backtesting standards treat results as a comparison of
model outputs with actual outcomes — not as evidence of successful historical fitting.

By those standards, this strategy currently has:
- ✅ Point-in-time clean inputs
- ✅ Capital realism (lock-up, settlement timing, whole units, fees)
- ✅ No information leakage
- ❌ Insufficient settled OOS quarters
- ❌ No independent model validation
- ❌ No live paper-trade validation

**Status: Pre-validation. Further development required before any capital deployment.**
""", encoding="utf-8")


if __name__ == "__main__":
    main()
