# PHASE5C5 DISPATCHPRICE Bulkload Fix

## Root Cause
- `ingest_dispatchprice_cache` previously called `upsert` for every cache partition, triggering repeated full-table merge/groupby work.

## Old Algorithm
- Read each partition, then call `upsert(norm)` per file.
- `upsert` performed concat + sort + groupby merge over the whole in-memory table each call.
- Operation style: mask/groupby-based repeated whole-table recomputation.
- Estimated complexity: approximately O(F * N log N) to O(F * N^2)-like growth as table size increases.

## New Algorithm
- `load_dispatchprice_cache_bulk(start, end)` loads target partitions once.
- Concatenate once, deduplicate once on canonical key (`interval_timestamp_utc`, `region_id`), sort once, assign once.
- Operation style: bulk vectorized batch path (no row-by-row upsert loop for bulk cache loading).
- Estimated complexity: O(N log N) dominated by one global sort/dedup.

## Run Metrics (C2024Q4 only)
- Input row count: `26496`
- Existing table row count: `0`
- Key columns used: `interval_timestamp_utc, region_id`
- Duplicates before deduplication: `0`
- Duplicates after deduplication: `0`
- Rows loaded (rows_normalized): `26496`
- Files processed: `3`
- Runtime seconds (wall): `0.357`
- Runtime target (<30s): `PASS`

## Stage Timings
- file reads: `0.035033`
- concatenation: `0.001574`
- deduplication: `0.020618`
- final assignment: `0.208873`
- total runtime: `0.266098`

## Retry Readiness
- Phase 5C3 is ready to retry from a DISPATCHPRICE cache-loading perspective with this bulk-load path.
