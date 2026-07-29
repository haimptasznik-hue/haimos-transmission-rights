# GENERATOR MASTER V1.0 — METRIC DEFINITIONS

## Label corrections (audit 2026-07-29)

| Old label | Correct label | Reason |
|---|---|---|
| "62.2% renewable penetration" | `renewable_unit_share_pct` | Numerator/denominator are DUID counts, not generation MW |
| "fossil share" (single figure) | `fossil_unit_share_pct` or `fossil_registered_capacity_share_pct` | Two distinct denominators |

## Recomputed metrics (source: canonical parquet, no inference)

| Metric | Value |
|---|---|
| `total_generator_count` | 384 |
| `total_registered_capacity_mw` | 64336.393 |
| `renewable_unit_count` | 239 |
| `renewable_unit_share_pct` | 62.2395833333 |
| `renewable_registered_capacity_mw` | 30405.797 |
| `renewable_registered_capacity_share_pct` | 47.2606491943 |
| `unknown_unmapped_count` | 3 |

## Five-minute renewable penetration

`renewable_penetration_pct` (renewable generation MW / total generation MW × 100) has **NOT YET BEEN CALCULATED** in Generator Master v1.0. It requires five-minute SCADA generation aggregation and is defined in the Renewable Penetration Feature Contract.

## Fuel-share classification table

Each fuel share is independently provided as:
1. **unit-count share** — percentage of total DUID count
2. **registered-capacity share** — percentage of total registered MW

| Fuel | unit_share_pct | registered_capacity_share_pct |
|---|---:|---:|
| BATTERY | 2.343750 | 0.965239 |
| BIOMASS | 0.781250 | 0.152324 |
| FOSSIL | 34.635417 | 50.654994 |
| HYDRO | 12.760417 | 13.068964 |
| SOLAR | 26.302083 | 15.953345 |
| UNKNOWN | 0.781250 | 1.119118 |
| WIND | 22.395833 | 18.086015 |

## Numeric precision note

All percentage values are computed from canonical integer counts and float capacity sums.
Totals sum to 100% within floating-point precision (tolerance ≤ 1e-6).
