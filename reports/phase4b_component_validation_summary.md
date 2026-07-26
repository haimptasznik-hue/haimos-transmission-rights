# Phase 4B Component Export Validation Summary

- Source export: `reports/phase4b_component_export_from_alpha.csv`

> Paths are recorded relative to the repository root.
- Total rows checked: `926`
- Valid for attribution: `0` (0.0%)
- Blocked rows: `926` (100.0%)

## Timestamp Integrity
- Leakage rows (published after decision timestamp): `0`
- Stale rows (older than 60 days): `0`
- Alignment issue rows: `926`

## Data Type Issues
- none

## Component Completeness (mean by group)
- price_forecasts: `0.000`
- flow_forecasts: `0.000`
- constraint_forecasts: `0.000`
- settlement_model_outputs: `0.500`
- unit_table_rule_metadata: `0.250`
- optimiser_execution_outputs: `0.000`

## Weakest Coverage Corridors

| corridor | rows | mean_coverage | pct_invalid | mean_completeness_score |
|---|---:|---:|---:|---:|
| NSW1-QLD1 | 393 | 0.125 | 100.0% | 0.125 |
| V-SA | 208 | 0.125 | 100.0% | 0.125 |
| VIC1-NSW1 | 325 | 0.125 | 100.0% | 0.125 |

## Weakest Coverage Tranches

| tranche | rows | mean_coverage | pct_invalid | mean_completeness_score |
|---|---:|---:|---:|---:|
| T01 | 119 | 0.125 | 100.0% | 0.125 |
| T02 | 40 | 0.125 | 100.0% | 0.125 |
| T03 | 69 | 0.125 | 100.0% | 0.125 |
| T04 | 80 | 0.125 | 100.0% | 0.125 |
| T05 | 70 | 0.125 | 100.0% | 0.125 |

## Output Files
- `reports/phase4b_component_validation_summary.md`
- `reports/phase4b_component_row_diagnostics.csv`
- `reports/phase4b_component_blocked_reasons.csv`
- `reports/phase4b_component_completeness_by_trade.csv`
- `reports/phase4b_component_coverage_by_corridor.csv`
- `reports/phase4b_component_coverage_by_tranche.csv`
- `reports/phase4b_ranked_missing_fields_by_value.csv`
- `reports/phase4b_component_validated_for_attribution.csv`
