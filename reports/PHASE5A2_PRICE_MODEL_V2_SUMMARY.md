# Phase 5A.2 – Price Model v2 Walk-Forward Validation

> **Objective:** Test deviation-based forecasting with regime features.
> Ridge regression predicts: actual_payout − seasonal_benchmark.
> Benchmarks: seasonal, regime-adjusted, and ridge model v2.

## Setup
- Warm-up window: `8` settled quarters.
- Test quarters evaluated: `17`
- Minimum test quarters required: `4`

## Benchmarks
| Benchmark | Description |
|---|---|
| `seasonal` | Historical mean payout for same quarter-number |
| `regime_adjusted` | seasonal + 0.25 × weighted recent deviation |
| `ridge_v2` | Ridge regression on deviation features |

## Overall OOS MAE (AUD/unit)
| Model | MAE |
|---|---|
| Seasonal (Phase 5A.1 baseline) | 8,470.02 |
| Seasonal (this fold) | 8,232.44 |
| Regime-adjusted | 8,064.99 |
| **Ridge Model v2** | **8,232.44** |

## Per-Corridor OOS MAE
| Corridor | N | Seasonal | Regime-adj | Ridge v2 | Ridge beats seasonal? | Ridge beats regime? |
|---|---|---|---|---|---|---|
| NSW1-QLD1::NSW1 | 204 | 6,068 | 6,414 | 6,068 | ✅ | ✅ |
| NSW1-QLD1::QLD1 | 204 | 14,826 | 13,629 | 14,826 | ❌ | ❌ |
| V-SA::SA1 | 204 | 2,862 | 2,658 | 2,862 | ❌ | ❌ |
| V-SA::VIC1 | 204 | 9,501 | 10,591 | 9,501 | ❌ | ✅ |
| VIC1-NSW1::NSW1 | 204 | 5,495 | 5,565 | 5,495 | ❌ | ✅ |
| VIC1-NSW1::VIC1 | 204 | 10,644 | 9,532 | 10,644 | ❌ | ❌ |

## Promotion Gate
| Gate | Result |
|---|---|
| OOS MAE beats seasonal | ✅ |
| OOS MAE beats regime-adjusted | ❌ |
| Improves >1 corridor | ✅ (3/6) |
| No single corridor >80% of gain | ✅ (max: 8.3%) |
| ≥4 quarters tested | ✅ (17) |

## Verdict: **FAIL**

Price Model v2 does **not** pass the promotion gate.
- Ridge model OOS MAE exceeds one or both benchmarks.
- Model may not add signal beyond seasonality and recent regime adjustment.
- Status: `REJECTED / RESEARCH ONLY`.

## Feature Coverage by Corridor
| Corridor | Recent Trend | Volatility | Mean Abs Dev | Same-Q Var | Lagged Dev |
|---|---|---|---|---|---|
| NSW1-QLD1::NSW1 | 100% | 0% | 100% | 100% | 100% |
| NSW1-QLD1::QLD1 | 100% | 0% | 100% | 100% | 100% |
| V-SA::SA1 | 100% | 0% | 100% | 100% | 100% |
| V-SA::VIC1 | 100% | 0% | 100% | 100% | 100% |
| VIC1-NSW1::NSW1 | 100% | 0% | 100% | 100% | 100% |
| VIC1-NSW1::VIC1 | 100% | 0% | 100% | 100% | 100% |

## Interpretation
- Ridge v2 predicts deviations from seasonal baseline, not raw payouts.
- Features capture recent trends and volatility in payout swings.
- Regime-adjusted benchmark adds weighted recent deviations on top of seasonality.
- If ridge beats both benchmarks, the model has identified explainable regimes.
- Feature coverage gaps may limit model applicability in sparse corridors.
