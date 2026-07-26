# Phase 5A Data Audit – Price Model v1

## Framing
- This phase preserves the attribution-first approach.
- No direct regional price time-series dataset is present in the repository snapshot.
- `Price Model v1` therefore forecasts settled unit payout using only in-repo market proxies and lagged settled outcomes.
- No claims about seasonality, corridor failure, or capacity are introduced here.

## Available datasets used
- `data/derived/sra/alpha_database.csv`: 2,304 auction-direction rows with point-in-time clearing observations and realised payout where settled.
- `data/derived/sra/sra_payout_history.csv`: 150 settled quarter-direction payout rows.
- `data/derived/sra/sra_auction_results.csv`: loaded upstream into the alpha database and preserved through auction context columns.

## Direct data availability check
- `regional_price_actual/forecast`: not available as a standalone dataset in this repo snapshot.
- `interconnector_flow_actual/forecast`: not available as a standalone point-in-time forecast dataset in this repo snapshot.
- `constraint_actual/forecast`: not available as a standalone point-in-time forecast dataset in this repo snapshot.
- `settlement residue / unit payout`: available and auditable.

## Usable features in Price Model v1
- Auction microstructure: clearing price, fill probability, units offered, units sold, tranche number.
- Product identity: directional corridor (`interconnector_id`, `from_region`).
- Quarter seasonality proxy: quarter number encoded cyclically, without claiming causal seasonality.
- Same-quarter earlier tranche clears: available at decision time from prior auction results.
- Historical settled payout statistics by direction and tranche: available only after settlement and used with a strict no-lookahead gate.

## Coverage
- Settled rows available for training/evaluation: `1740`
- Distinct direction buckets: `6`
- Prediction rows generated: `2304`
- Model feature columns: `31`

## Output files
- `reports/PHASE5A_PRICE_MODEL_DATA_AUDIT.md`
- `reports/phase5a_price_model_v1_predictions.csv`
- `reports/phase5a_price_model_v1_component_export.csv`
- `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md`
- `reports/FORECAST_CONTRIBUTION_REGISTER.csv`
