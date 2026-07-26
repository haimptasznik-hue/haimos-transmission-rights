# Phase 4B Quant Research Analyst Summary

## Core Attribution KPIs
- Explained forecast error: `$0.00` (0.00%)
- Unattributed residual: `$173,794,731.05` (100.00%)
- Target check (>90% explained): `FAIL`

## Residual Progress vs Baseline
- Baseline residual reference: `$92,859,173.49`
- Current residual: `$173,794,731.05`
- Residual reduction: `$-80,935,557.56` (-87.16%)

## Dominant Loss Driver
- Dominant component: `unattributed_investigation`
- Estimated cost contribution: `$173,794,731.05`

## Best Single Improvement This Month
- Improvement: `unattributed_investigation`
- Expected P&L gain (50% error reduction scenario): `$46,429,586.75`
- Effort: `High`
- Priority: `1`

## Validation Integrity
- Rows checked: `926`
- Blocked attribution rows: `926`
- Timestamp leakage rows: `0`
- Stale component rows: `0`

## Weakest Component Coverage

### Corridors
| corridor | rows | mean_coverage | pct_invalid | mean_completeness_score |
|---|---:|---:|---:|---:|
| NSW1-QLD1 | 393 | 0.125 | 100.0% | 0.125 |
| V-SA | 208 | 0.125 | 100.0% | 0.125 |
| VIC1-NSW1 | 325 | 0.125 | 100.0% | 0.125 |

### Tranches
| tranche | rows | mean_coverage | pct_invalid | mean_completeness_score |
|---|---:|---:|---:|---:|
| T01 | 119 | 0.125 | 100.0% | 0.125 |
| T02 | 40 | 0.125 | 100.0% | 0.125 |
| T03 | 69 | 0.125 | 100.0% | 0.125 |
| T04 | 80 | 0.125 | 100.0% | 0.125 |
| T05 | 70 | 0.125 | 100.0% | 0.125 |

## Core Quant Outputs
- `reports/phase4b_error_waterfall.csv`
- `reports/phase4b_rd_roi_table.csv`
- `reports/phase4b_forecast_maturity.csv`
- `reports/phase4b_component_validation_summary.md`
- `reports/phase4b_component_row_diagnostics.csv`
- `reports/phase4b_component_blocked_reasons.csv`
- `reports/phase4b_ranked_missing_fields_by_value.csv`
