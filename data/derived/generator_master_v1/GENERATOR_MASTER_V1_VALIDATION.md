# GENERATOR MASTER V1.0 — VALIDATION REPORT (audited 2026-07-29)

## Parquet / CSV semantic parity
- Column order identical: true
- Row count identical: true (parquet=384, csv=384)
- Schema-aware CSV ingestion: string dtype enforced for version identifier columns
- Canonical hash (parquet): `2c1122fcf90e3ccdf1c15efa330f1ad3ae73c05e3af46baa5f9f8fbaa6a61bad`
- Canonical hash (csv, schema-aware): `2c1122fcf90e3ccdf1c15efa330f1ad3ae73c05e3af46baa5f9f8fbaa6a61bad`
- Hash equality: PASS

## CSV interchange note
CSV readers must enforce string dtype for `schema_version`, `generator_master_version`, `snapshot_version`, and `DUID`. Generic pandas `read_csv` inference interprets `"1.0"` as `float64`. This is an interchange-format limitation, not a data-quality defect. The canonical Parquet file is authoritative.

## Metric label corrections
- `renewable_unit_share_pct` = 62.2395833333% — DUID-count numerator, DUID-count denominator
- `renewable_registered_capacity_share_pct` = 47.2606491943% — MW numerator, MW denominator
- `renewable_penetration_pct` — **NOT YET CALCULATED** (five-minute generation share)

## Integrity
- Duplicate DUIDs: 0
- Missing mandatory fields: 0
- Quality-status distribution: {'AUTHORITATIVE': 384}
- Registered capacity range: [2.0, 1500.0] MW
- Negative capacity values: 0
- Valid NEM regions: ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']

## Regional distribution
| Region | Count | Capacity MW |
|---|---:|---:|
| NSW1 | 97 | 21584.875 |
| QLD1 | 98 | 17794.018 |
| SA1 | 70 | 6566.900 |
| TAS1 | 33 | 3211.200 |
| VIC1 | 86 | 15179.400 |

## PIT scope
- `CURRENT_STATE_ONLY` — single snapshot 2026-07-29, no effective-date history.
