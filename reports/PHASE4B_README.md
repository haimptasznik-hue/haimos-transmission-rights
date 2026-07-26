# Phase 4B Attribution Runner

## Purpose

`phase4b_error_attribution.py` identifies which forecast component is costing the most money and ranks improvement areas by estimated P&L benefit.

It produces:
- `reports/phase4b_trade_level_attribution.csv`
- `reports/phase4b_grouped_attribution.csv`
- `reports/PHASE4B_FORENSIC_LARGEST_LOSSES.md`
- `reports/phase4b_ranked_model_improvements.csv`

## Run

```bash
python scripts/phase4b_error_attribution.py
```

With component exports:

```bash
python scripts/phase4b_error_attribution.py --component-exports data/derived/sra/component_exports.csv
```

## Required Baseline Inputs

- `reports/backtest_detailed_trades.csv`
- `data/derived/sra/alpha_database.csv`

## Optional Component Export Input

A CSV keyed by one of:
- `product_id,quarter,tranche,decision_date` (preferred)
- `product_id,quarter,tranche`
- `product_id,decision_date`
- `product_id`

### Supported component fields

Forecast/actual + sensitivity (or direct *_error_aud):
- Regional prices: `regional_price_forecast`, `regional_price_actual`, `regional_price_to_payout_sensitivity`
- Interconnector flows: `interconnector_flow_forecast`, `interconnector_flow_actual`, `flow_to_payout_sensitivity`
- Constraints: `constraint_forecast`, `constraint_actual`, `constraint_to_payout_sensitivity`
- Settlement residue: `settlement_residue_forecast`, `settlement_residue_actual`, `settlement_residue_to_payout_sensitivity`
- Unit payout: `unit_payout_forecast`, `unit_payout_actual`

Direct attribution override fields (AUD):
- `price_error_aud`
- `flow_error_aud`
- `constraint_error_aud`
- `settlement_model_error_aud`
- `unit_table_rules_error_aud`
- `optimiser_execution_error_aud`

## Attribution categories

- `price_error`
- `flow_error`
- `constraint_error`
- `settlement_model_error`
- `unit_table_rules_error`
- `optimiser_execution_error`
- `UNATTRIBUTED` (explicit residual bucket)

## Confidence and data quality

Each trade has:
- `attribution_confidence_score` (0-1)
- `attribution_confidence_label` (`high`/`medium`/`low`)
- `data_quality_flag`

Missing component exports reduce confidence and increase visible `UNATTRIBUTED` residual.

## Notes

- This runner performs attribution only; it does **not** optimize strategy rules.
- If component-level exports are missing, results remain valid but lower-confidence and mostly `UNATTRIBUTED`.
