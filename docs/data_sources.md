# Data Sources

## Controlled AEMO reference data

Highest-priority inputs:

- SRA product definitions by directional interconnector and relevant quarter
- maximum Units and unit proportions
- tranche schedules and quantities offered
- auction calendars
- historical auction outcomes and clearing prices
- assignment / cancellation process reference materials

## NEM operational data

Required for reconstruction and forecasting:

- regional reference prices
- interconnector directional flows
- loss-adjusted settlement components
- outages and constraint context
- predispatch and P5MIN forecasts where useful for near-term marks

## Existing Vault discovery inputs

Read-only source modules identified:

- `haimos-app/backend/nem/aemo_fetch.py`
- `haimos-app/backend/nem/aemo_forecast_signals.py`
- `haimos-app/backend/nem/dispatch_runner.py`
- `00_Master_Context/EYE_SYSTEM_MAP.md`
- `00_Master_Context/EYE_MODULE_MAP.md`

## Data quality rules

- version controlled reference tables
- explicit effective dates for unit-proportion changes
- timezone normalization to NEM operational convention
- reproducible raw-to-derived lineage
- no silent overwrites of controlled product definitions

## Deferred integrations

- MarketNet / EMMS submission flows
- participant-specific acknowledgements and settlement files
- assignment-consent workflow artifacts that require current AEMO confirmation
