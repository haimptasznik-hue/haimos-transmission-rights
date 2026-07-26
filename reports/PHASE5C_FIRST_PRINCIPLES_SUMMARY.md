# Phase 5C – Commercial Market State Database (Foundation)

## Objective
- Build a point-in-time clean Commercial Market State Database.
- Scope corridor: `NSW1-QLD1`.
- Store schema + PIT timestamps + versioning + normalization + validation APIs.
- Plug `DISPATCHPRICE` into the same database as first ingestor.
- Do not build a new payout model until required external datasets are available.

## Market State Database Build
- Schema fields defined: `35`
- Stored market-state rows: `482112`
- Rows with usable NSW-QLD spread: `482112`

## Source Availability
| Source | Priority | Required | Status |
|---|---|---|---|
| DISPATCHPRICE | 1 | Yes | AVAILABLE |
| DISPATCHINTERCONNECTORRES | 2 | Yes | MISSING |
| DISPATCHCONSTRAINT | 3 | No | MISSING |
| REGIONAL_DEMAND | 4 | No | MISSING |
| DUID_GENERATION | 5 | No | MISSING |

## PIT Coverage
- Required source coverage: `50.00%`
- Feature store rows are currently PIT-invalid placeholders pending external ingestion.

## Required Missing Sources
- `DISPATCHINTERCONNECTORRES`: MISSING (no_files_found)

## Success Gate Status
- Benchmark to beat (future model): `$8,065/unit` regime-adjusted OOS MAE.
- Current stage: ingestion only, modelling deferred until required data is available.
- Verdict: `INSUFFICIENT_DATA`

## Next Action
- Ingest `DISPATCHPRICE` and `DISPATCHINTERCONNECTORRES` with PIT lineage fields.
- Then recompute NSW1-QLD1 spread/flow/utilisation feature store and run walk-forward.
