# Repository Discovery Report

**Repository:** `haimos-transmission-rights`  
**Date:** 2026-07-12  
**Scope:** Phase 1 repository discovery and separation planning

## Current state

The repository already contains a strong base for deterministic AEMO replication and a separate heuristic valuation stack. The main risk is that some modules currently mix forecast assumptions, historical analytics, and AEMO-style calculations in the same service namespace.

## Baseline git state

- Current commit: `298fdfd29d72b46a5566a2760df8c06fd0f04b46`
- Working tree status at snapshot: clean

## Relevant file map

### API
- `src/transmission_rights/api/main.py`
  - FastAPI application entrypoint
  - Builds fair value, recommendations, quarter views, analytics, and portfolio outputs
  - Imports both deterministic and heuristic engines
- `src/transmission_rights/api/discovery.py`
  - AEMO/NEMWeb file discovery endpoints
  - Uses `adapters/aemo_feeds.py` and `services/irsr_engine.py`

### Domain and data contracts
- `src/transmission_rights/domain/models.py`
  - `SRAProduct`, `PortfolioPosition`, `ValuationInputs`, `FairValueRequest`, `FairValueResponse`
- `src/transmission_rights/data/contracts.py`
  - Example product builders and data-layer helpers
- `src/transmission_rights/domain/interconnectors.py`
  - Interconnector identity and directional mapping helpers

### Deterministic AEMO-style services
- `src/transmission_rights/services/aemo/sra_irssr_calculator.py`
  - Interval IRSR calculator
  - Contains forward/reverse direction handling and loss apportionment
- `src/transmission_rights/services/aemo/sra_distribution_engine.py`
  - Category payout and unit distribution logic
  - Handles unsold units, fees, negative residue guards, and settlement runs
- `src/transmission_rights/services/aemo/sra_historical_replay.py`
  - Historical snapshots and settlement run replay
- `src/transmission_rights/services/aemo/sra_product_registry.py`
  - Canonical SRA product registry with effective-date support
- `src/transmission_rights/services/aemo/sra_market_calendar.py`
  - Quarter boundaries, auction timing, and date handling
- `src/transmission_rights/services/aemo/sra_auction_parser.py`
  - Parses `PUBLIC_SRRES_*.csv` records
- `src/transmission_rights/adapters/aemo/historical_data_fetcher.py`
  - NEMWeb fetch / parse / snapshot loading
  - Reconstructs IRSR and product definition data from raw files

### Heuristic / mixed logic
- `src/transmission_rights/services/aemo/fill_rate_fair_value_engine.py`
  - Heuristic fair value model based on fill-rate and volume signals
- `src/transmission_rights/services/valuation.py`
  - Proportional valuation scaffold with discounting
- `src/transmission_rights/services/aemo/sra_forecast_engine.py`
  - Scenario-based forecast engine mixing assumptions with value projection
- `src/transmission_rights/services/aemo/market_analytics.py`
  - Correlation, trend, and backtest analytics
- `src/transmission_rights/services/aemo/recommendation_ledger.py`
  - Opportunity scoring and ranking

### Wrappers / unclear roles
- `src/transmission_rights/services/irsr_engine.py`
  - Simplified historical IRSR reconstructor wrapper
- `src/transmission_rights/services/aemo/sra_mark_engine.py`
  - Continuous mark / bid / offer valuation layer
- `src/transmission_rights/services/aemo/sra_position_ledger.py`
  - Position tracking / holding ledger
- `src/transmission_rights/services/aemo/sra_execution_adapter.py`
  - Execution interface; must remain non-trading in this sprint

### Tests
- `tests/test_irsr_reconstruction.py`
- `tests/test_aemo_auction_parser.py`
- `tests/test_aemo_ingestion.py`
- `tests/test_aemo_modules.py`
- `tests/test_api_endpoints.py`
- `tests/test_fair_value_backtest.py`
- `tests/test_valuation.py`

## Key reusable modules

- `sra_irssr_calculator.py` for deterministic interval residue computation
- `sra_product_registry.py` for versioned product definitions
- `sra_distribution_engine.py` for quarter payout allocation
- `sra_historical_replay.py` for settlement run replay
- `sra_market_calendar.py` for quarter timing and DST handling
- `historical_data_fetcher.py` for ingestion and parse helpers
- `sra_auction_parser.py` for SRA result parsing

## Heuristic logic to isolate

- `fill_rate_fair_value_engine.py`
- `services/valuation.py`
- `sra_forecast_engine.py`
- `market_analytics.py`
- `recommendation_ledger.py`
- any API routes built on top of the above

## Missing deterministic logic

- Effective-dated rule / unit tables separated from product registry
- Canonical product registry with source file hash and ingestion lineage
- Explicit interval replication output schema for audit/debugging
- Quarter aggregation with duplicate / missing interval detection
- Reconciliation engine that compares against published AEMO outputs
- Backcast harness with point-in-time data cutoff enforcement

## Modules that should remain untouched for now

- `src/transmission_rights/data/contracts.py`
- `src/transmission_rights/config.py`
- `src/transmission_rights/utils/time.py`
- raw data files under `data/raw/aemo/`
- existing tests unless a new deterministic path needs coverage

## Recommended separation approach

1. Preserve existing deterministic AEMO-style code.
2. Move the heuristic fair-value logic behind `src/transmission_rights/legacy/`.
3. Create a dedicated `src/transmission_rights/replication/` package for deterministic AEMO reconstruction.
4. Create a dedicated `src/transmission_rights/assumptions/` package for forecast inputs only.
5. Create a dedicated `src/transmission_rights/valuation/` package that consumes assumptions and calls replication logic.
6. Keep current APIs working by introducing adapters or thin compatibility wrappers rather than breaking routes immediately.

## Gaps affecting AEMO replication

- No effective-dated rule registry yet
- No canonical source-lineage tracking yet
- No quarter-level reconciliation report
- No AEMO worked-example regression suite
- No point-in-time backcast enforcement layer

## Next implementation step

Create the new package structure and move the heuristic model behind `legacy/` without deleting the current implementation.
