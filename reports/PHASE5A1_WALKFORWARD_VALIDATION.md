# Phase 5A.1 – Walk-Forward Price Validation

> **Objective:** Prove that Price Model v1 (or a successor) can predict
> genuinely *unseen* quarters — not just produce a larger historical P&L.
> Training is strictly frozen on quarters settled before the test quarter.
> Models are never trained on any row from the quarter being predicted.

## Setup
- Warm-up window: `8` settled quarters (minimum before first test).
- Test quarters evaluated: `17`
- Promotion gate minimum: `4` unseen quarters.

## Model
- **Ridge Model v1** — same feature set as `price_model_v1.py`; coefficients frozen per test quarter.

## Benchmarks (no-lookahead, direction-level)
| Benchmark | Description |
|---|---|
| `bench_hist_seasonal` | Mean payout for same quarter-number in all prior years |
| `bench_last_quarter` | Mean payout from immediately prior settled quarter |
| `bench_same_q_prior_yr` | Mean payout for same quarter one year earlier |
| `bench_trend` | Linear extrapolation over last 4 settled quarters |

## OOS MAE by quarter (AUD/unit, mean absolute error)

| Quarter | N | Ridge v1 | Hist Seasonal | Last Quarter | Prior Year Q | Trend |
|---|---|---|---|---|---|---|
| C2022Q2 | 72 | 10531.5 | 11132.9 | 17910.3 | 8895.1 | 17910.3 |
| C2022Q3 | 72 | 7402.0 | 14527.7 | 8162.0 | 15128.7 | 8162.0 |
| C2022Q4 | 72 | 14858.8 | 4629.0 | 8393.1 | 6487.1 | 8393.1 |
| C2023Q1 | 72 | 10148.1 | 6257.3 | 6033.1 | 8541.5 | 6033.1 |
| C2023Q2 | 72 | 11901.6 | 4545.3 | 6709.2 | 6892.4 | 6709.2 |
| C2023Q3 | 72 | 6622.4 | 7003.4 | 3534.3 | 7419.8 | 3534.3 |
| C2023Q4 | 72 | 8022.1 | 5993.0 | 11284.3 | 7613.5 | 11284.3 |
| C2024Q1 | 72 | 5915.9 | 6050.9 | 5741.3 | 8241.6 | 5741.3 |
| C2024Q2 | 72 | 17872.6 | 18293.5 | 17022.4 | 17611.5 | 17022.4 |
| C2024Q3 | 72 | 10203.9 | 10117.1 | 16892.9 | 9774.4 | 16892.9 |
| C2024Q4 | 72 | 10352.6 | 8838.5 | 13507.5 | 9622.0 | 13507.5 |
| C2025Q1 | 72 | 8092.0 | 5398.2 | 9709.2 | 5789.7 | 9709.2 |
| C2025Q2 | 72 | 17011.8 | 12611.0 | 11594.7 | 5177.5 | 11594.7 |
| C2025Q3 | 72 | 9987.5 | 2650.7 | 12155.2 | 9604.1 | 12155.2 |
| C2025Q4 | 72 | 4227.9 | 3939.2 | 5175.7 | 6701.8 | 5175.7 |
| C2026Q1 | 72 | 12274.4 | 12369.0 | 11401.0 | 9805.5 | 11401.0 |
| C2026Q2 | 72 | 15119.8 | 9633.7 | 12693.5 | 13302.5 | 12693.5 |

## Overall OOS MAE summary
| Model | Overall MAE (AUD/unit) |
|---|---|
| Ridge Model v1 | **10,620.28** |
| Benchmark: Historical Seasonal | 8,470.02 |
| Benchmark: Last Quarter | 10,465.86 |
| Benchmark: Same Quarter Prior Year | 9,212.27 |
| Benchmark: Trend | 10,465.86 |
| **Best benchmark** | **8,470.02** |

## Promotion gate
| Gate | Result |
|---|---|
| OOS MAE beats best benchmark | ❌ |
| ≥4 unseen quarters tested | ✅ |
| Improvement across >1 corridor | ❌ (1 corridors) |
| No single corridor >80% of gain | ❌ (max share: nan) |

### Verdict: **FAIL**

Price Model v1 does **not** pass the promotion gate on walk-forward OOS evaluation.
Status: `REJECTED / RESEARCH ONLY`.
Required next step before promotion: reduce OOS MAE below best benchmark across multiple corridors.

## Corridor-level improvement detail
| Corridor | Ridge v1 beats benchmark |
|---|---|
| NSW1-QLD1::NSW1 | ❌ |
| NSW1-QLD1::QLD1 | ✅ |
| V-SA::SA1 | ❌ |
| V-SA::VIC1 | ❌ |
| VIC1-NSW1::NSW1 | ❌ |
| VIC1-NSW1::VIC1 | ❌ |

## Interpretation guardrails
- Walk-forward evaluation is the minimum bar for promotion; it does not validate live production use.
- Backtest P&L from walk-forward is not computed here — a separate capital-constrained simulation is required.
- Price Model v1 was rejected in Phase 5A because its backtest gain was training-set amplification, not genuine OOS edge.
- This phase isolates the OOS question before any backtest signal is trusted.
