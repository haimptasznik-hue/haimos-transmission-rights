# HISTORICAL_FEATURE_STORE_V1_KNOWN_GAPS

## Persistent External Gaps
- `FCAS`: blocked external for all 79 months (no ingested FCAS source yet).
- `GENERATOR_OUTAGES`: blocked external for all 79 months (no ingested outage source yet).
- `WEATHER`: blocked external for all 79 months (no BOM/weather ingest configured yet).

## Persistent Partial Internal Proxies
- `UNIT_COMMITMENT`: `DERIVED_PARTIAL` in all 79 months; proxy limited by absent DUID technology register.
- `RENEWABLE_GENERATION`: `DERIVED_PARTIAL` in all 79 months; absent DUID technology mapping in this snapshot.

## Coverage Notes
- Core interval coverage remains `100.0%` with `0` duplicate canonical keys.
- Historical checkpoint topology is complete (`79/79` month directories present with required artifacts).
- Quality score has no infinities, but includes nulls in intervals where feature availability is structurally absent.
