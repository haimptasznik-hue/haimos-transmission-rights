# Historical Feature Store Architecture

## Objective
Build a deterministic, PIT-safe, appendable 5-minute historical market feature store for the NEM.

## Pipeline
1. Ingest raw AEMO MMSDM cached datasets.
2. Normalize settlement timestamps to canonical UTC 5-minute intervals.
3. Aggregate each dataset to interval-level canonical features.
4. Merge onto a single canonical timeline from 2020-01-01 to latest available.
5. Attach PIT metadata (`observation_timestamp_utc`, `publication_timestamp_utc`, `effective_timestamp_utc`).
6. Attach lineage and quality (`lineage_hash`, `quality_score`, `point_in_time_available`).
7. Persist output and dataset-level status/completeness artifacts.

## Append Strategy
- Schema is fixed at interval-level wide features.
- New raw files are appended in cache and merged by interval key without historical schema redesign.
- Lineage hash is recomputed from source files for auditability.

## Determinism
- No forecasting or ML logic.
- Pure transformations from raw source to canonical features.

