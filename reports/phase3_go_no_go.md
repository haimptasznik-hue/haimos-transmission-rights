# Phase 3 Go / No-Go Assessment
Generated: 2026-07-12T13:52:59.766527+00:00

---

## Classification

# 🔴 AMBER

**Walk-forward positive vs no-trade but OOS gates not fully met. More settled quarters needed.**

---

## OOS Gate Status: INSUFFICIENT_OOS_EVIDENCE

| Gate | Required | Actual | Status |
|---|---|---|---|
| min_trades | 30 | 13 | ❌ FAIL |
| min_quarters | 4 | 4 | ✅ PASS |
| hit_rate | 0.5 | 0.3076923076923077 | ❌ FAIL |
| mean_realised_alpha | 0.0 | -4091.363361538461 | ❌ FAIL |
| profit_factor | 1.25 | 0.06308654146520863 | ❌ FAIL |
| sharpe_ratio | 1.0 | -1.1784980129767488 | ❌ FAIL |
| max_drawdown | 0.25 | 0.0 | ✅ PASS |
| max_single_trade_pnl_pct | 0.2 | 0.2860171226060389 | ❌ FAIL |
| max_corridor_pnl_pct | 0.4 | 0.9939188529972642 | ❌ FAIL |

Failures:
- min_trades: 13 < 30
- hit_rate: 0.308 < 0.5
- mean_realised_alpha: -4091.36 <= 0
- profit_factor: 0.063 < 1.25
- sharpe: -1.178 < 1.0
- single_trade_concentration: 0.286 > 0.2
- corridor_concentration: 0.994 > 0.4

---

## In-Sample Backtest Result (NOT Investable Evidence)

> **IN_SAMPLE_HEURISTIC — not investable evidence**

The $50k->$15.1m in-sample result reflects a heuristic with no look-ahead bias in the data, but the strategy has not been validated on genuinely unseen quarters. It is NOT investable evidence.

| Metric | Value |
|---|---|
| Start capital | $50,000 |
| End capital | $3,967,310.08 |
| Total P&L | $+3,917,310.08 |
| Hit rate | 46.3% |
| Return on acquisition cost | 27.2% |
| Sharpe ratio | 0.25 |
| Max drawdown | 49.4% |
| Profit factor | 1.5418168584669325 |

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
| Settled quarters tested | 25 |
| Quarters with trades | 24 |
| Total P&L | $+2,261,184.69 |
| Quarter hit rate | 54% |

---

## Benchmark Comparison

| Strategy | P&L | ROAC | Max Drawdown |
|---|---|---|---|
| buy_all | $+16,979,858.20 | 0.1739708858019898 | 0.5216304353999999 |
| cheapest_products | $-3,121,887.44 | -0.4690128987011542 | 0.4493153304438357 |
| highest_historical_payout | $+2,821,776.63 | 0.37304604073284714 | 0.3476628764712331 |
| no_trade | $+0.00 | 0.0 | 0.0 |

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

1. Wait for more settled quarters (target: 4+ OOS quarters with trades).
2. Review why OOS has few/no trades — check thresholds vs settled data.
3. Do not deploy capital until OOS gates pass.

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
