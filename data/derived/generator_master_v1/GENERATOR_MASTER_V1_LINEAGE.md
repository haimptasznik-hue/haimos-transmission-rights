# GENERATOR MASTER V1.0 — DATA LINEAGE REPORT (audited 2026-07-29)

## Source files
1. AEMO NEM Registration and Exemption List — sheet `PU and Scheduled Loads`, snapshot 2026-07-29.
2. DISPATCH_UNIT_SCADA archives — 2023-12-01 to 2024-08-01 (8 monthly ZIP archives, 33,136,679 rows).

## Provenance classes

| Class | Fields |
|---|---|
| Authoritative registration | DUID, station_name, participant, region, registered_capacity_mw, snapshot_date, snapshot_version |
| Authoritative SCADA observations | first_seen_utc, last_seen_utc, observed_max_mw, observed_min_mw, observed_mean_mw, interval_count, positive_interval_count, zero_interval_count, negative_interval_count, positive_energy_mwh_proxy, negative_energy_mwh_proxy |
| Derived normalized classifications | fuel_type, technology_type, dispatch_classification, renewable_flag |
| Derived dataset metadata | authoritative_source, classification_confidence, quality_status, schema_version, generator_master_version, pit_scope, effective_from, effective_to |

No field in this dataset was inferred from DUID name patterns.
Normalized categories are derived transformations of raw AEMO registration descriptors.

## Classification notes
- BATTERY is storage; not counted as primary renewable generation by default.
- PUMPED_HYDRO is storage conversion; classified separately from primary renewable generation.
- Mixed-fuel descriptors (`NATURAL GAS / FUEL OIL`, `NATURAL GAS / DIESEL`) are mapped to OTHER pending finer disaggregation.

## PIT limitations
- `CURRENT_STATE_ONLY` — no historical effective-date tracking.
- 101 unmatched historical SCADA DUIDs — temporal archive boundary artefact, not data loss.
- 185 registration-only inactive DUIDs — outside SCADA observation window.
- Generation-weighted SCADA coverage: 99.116983%.

## CSV interchange note
String dtype must be enforced for version-identifier columns on CSV re-read. See validation report.
