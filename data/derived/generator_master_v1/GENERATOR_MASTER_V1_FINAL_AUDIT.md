# GENERATOR MASTER V1.0 — FINAL AUDIT (2026-07-29)

## Parquet / CSV parity
| Check | Result |
|---|---|
| Row count match | PASS (384 / 384) |
| Column count match | PASS (30 / 30) |
| Column order equal | PASS |
| DUID set equal | PASS |
| DUID duplicates | PASS (0) |
| Per-column semantic equality | PASS (all 30 columns) |
| Canonical hash equality (schema-aware) | PASS |
| Mismatch classification | SERIALISATION_REPRESENTATION_MISMATCH — resolved by schema-aware ingestion |

## Recomputed metrics
| Metric | Value |
|---|---|
| total_generator_count | 384 |
| total_registered_capacity_mw | 64336.393 |
| renewable_unit_share_pct | 62.2395833333 |
| renewable_registered_capacity_share_pct | 47.2606491943 |
| unknown_unmapped_count | 3 |
| storage_units | 11 |
| pumped_hydro_units | 2 |
| ambiguous_taxonomy_mappings | 6 |

## Validation checks
| Check | Result |
|---|---|
| JSON serialisation valid | PASS |
| No NaN/Infinity in JSON | PASS |
| No absolute local paths | PASS |
| Required metadata keys present | PASS |
| Fuel unit shares sum to 100% | PASS |
| Fuel capacity shares sum to 100% | PASS |
| Renewable count reconciliation | PASS |
| Renewable capacity reconciliation | PASS |
| Mandatory field completeness | PASS (0 missing) |
| Negative capacity values | PASS (0) |
| Valid NEM regions only | PASS |
| schema_version explicit | PASS (string "1.0") |
| generator_master_version explicit | PASS (string "1.0") |

## Taxonomy governance
| Rule | Result |
|---|---|
| BATTERY excluded from primary renewable | PASS |
| PUMPED_HYDRO classified separately | PASS |
| HYDRO treatment documented | PASS |
| renewable_flag rule consistent | PASS |
| UNKNOWN explicit | PASS |
| No DUID-name inference | PASS |

## Verdict
- **AUDIT_PASS**
- **READY_TO_PRESERVE_GENERATOR_MASTER_V1_0**
- Commit may proceed once reviewer confirms this report.
