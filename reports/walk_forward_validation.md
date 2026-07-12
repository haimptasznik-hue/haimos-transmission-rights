# Walk-Forward Validation Report
Generated: 2026-07-12T13:52:59.766417+00:00

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
| Settled quarters tested | 25 |
| Quarters with at least one trade | 24 |
| Total walk-forward P&L | $+2,261,184.69 |
| Quarter hit rate | 54% |
| Total trades | 281 |
| Return on cost | 1.3323385026340573 |
| Profit factor | 2.3606462001073396 |

---

## Per-Quarter Walk-Forward Results

| Quarter | Train Qtrs | Products | Pos. Alpha | Trades | PnL | Hit Rate |
|---|---|---|---|---|---|---|
| C2020Q2 | 0 | 48 | 31 | 17 | -26,808 | 0% |
| C2020Q3 | 1 | 54 | 30 | 25 | +26,559 | 40% |
| C2020Q4 | 2 | 60 | 26 | 19 | +6,002 | 42% |
| C2021Q1 | 3 | 66 | 31 | 8 | -14,917 | 12% |
| C2021Q2 | 4 | 72 | 43 | 38 | +1,442,949 | 66% |
| C2021Q3 | 5 | 72 | 46 | 24 | -14,857 | 58% |
| C2021Q4 | 6 | 72 | 36 | 30 | +508,683 | 53% |
| C2022Q1 | 7 | 72 | 18 | 7 | +109,665 | 43% |
| C2022Q2 | 8 | 72 | 25 | 22 | +303,174 | 59% |
| C2022Q3 | 9 | 72 | 24 | 19 | +513,749 | 100% |
| C2022Q4 | 10 | 72 | 22 | 11 | -22,212 | 27% |
| C2023Q1 | 11 | 72 | 13 | 1 | -1,671 | 0% |
| C2023Q2 | 12 | 72 | 12 | 10 | +487 | 50% |
| C2023Q3 | 13 | 72 | 12 | 7 | +25,680 | 43% |
| C2023Q4 | 14 | 72 | 15 | 7 | -132,146 | 29% |
| C2024Q1 | 15 | 72 | 18 | 2 | +2,159 | 100% |
| C2024Q2 | 16 | 72 | 20 | 4 | +32,955 | 75% |
| C2024Q3 | 17 | 72 | 22 | 5 | +66,450 | 100% |
| C2024Q4 | 18 | 72 | 28 | 5 | -298,802 | 20% |
| C2025Q1 | 19 | 72 | 22 | 0 | +0 | n/a |
| C2025Q2 | 20 | 72 | 26 | 4 | -78,337 | 0% |
| C2025Q3 | 21 | 72 | 35 | 5 | +13,131 | 80% |
| C2025Q4 | 22 | 72 | 33 | 4 | -170,180 | 0% |
| C2026Q1 | 23 | 72 | 25 | 2 | -14,069 | 0% |
| C2026Q2 | 24 | 72 | 29 | 5 | -16,459 | 0% |

---

## Benchmark Comparison

| Benchmark | Total PnL | Hit Rate | ROAC | Max Drawdown |
|---|---|---|---|---|
| buy_all | +16,979,858 | 0.45545977011494254 | 0.1739708858019898 | 0.5216304353999999 |
| cheapest_products | -3,121,887 | 0.449438202247191 | -0.4690128987011542 | 0.4493153304438357 |
| highest_historical_payout | +2,821,777 | 0.5894736842105263 | 0.37304604073284714 | 0.3476628764712331 |
| no_trade | +0 | None | 0.0 | 0.0 |

---

## Interpretation

Walk-forward has executed trades in 24 quarters with total P&L of $+2,261,184.69.

The heuristic forecast (`expected_alpha = fair_value - clearing_price`) relies on a median
clearing price from prior auctions on the same corridor/tranche. It does not predict
direction — it identifies products trading below recent median price, which may or may not
persist into the future.

**This walk-forward result should be compared against the benchmark suite to determine
whether the heuristic adds value over naive strategies.**
