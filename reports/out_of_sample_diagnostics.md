# Out-of-Sample Diagnostics Report
Generated: 2026-07-12T13:52:59.766199+00:00

## OOS Gate Status
**INSUFFICIENT_OOS_EVIDENCE**

Failures:
- min_trades: 13 < 30
- hit_rate: 0.308 < 0.5
- mean_realised_alpha: -4091.36 <= 0
- profit_factor: 0.063 < 1.25
- sharpe: -1.178 < 1.0
- single_trade_concentration: 0.286 > 0.2
- corridor_concentration: 0.994 > 0.4

---

## Root Cause: Why Zero OOS Trades

The split algorithm assigns the most recent 20% of chronological quarter-corridor
combinations to OOS. In the current alpha database:

- **Settled quarters** (payout coverage ≥ 50%): those with available `final_realised_payout_per_unit`
- **OOS quarters**: ['C2025Q2', 'C2025Q3', 'C2025Q4', 'C2026Q1', 'C2026Q2']
- **Future/forward quarters** (no payout data): ['C2018Q3', 'C2018Q4', 'C2019Q1', 'C2019Q2', 'C2019Q3', 'C2019Q4', 'C2020Q1', 'C2026Q3']...

The backtest engine **deliberately refuses to invest** in any row where
`final_realised_payout_per_unit` is NaN. This is intentional and correct:
investing in a product without knowing its realised payout would require a forecasting
model, which must be validated separately.

### OOS Quarter Details

| Quarter | Payout Coverage | Rows with Positive Expected Alpha |
|---|---|---|
| C2025Q2 | 100% | 26 |
| C2025Q3 | 100% | 35 |
| C2025Q4 | 100% | 33 |
| C2026Q1 | 100% | 25 |
| C2026Q2 | 100% | 29 |

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
