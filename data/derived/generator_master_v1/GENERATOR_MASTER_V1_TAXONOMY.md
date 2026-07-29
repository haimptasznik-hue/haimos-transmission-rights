# GENERATOR MASTER V1.0 — TAXONOMY REVIEW

## Taxonomy version
`gm_v1_taxonomy_audit_2026-07-29`

## Governance rules

- **BATTERY** is storage and is **not** primary renewable generation by default.
- **PUMPED_HYDRO** is storage conversion and is classified **separately** from primary renewable generation.
- **HYDRO** denotes conventional (gravity / run-of-river) hydro generation only.
- **renewable_flag** = True when `fuel_type` ∈ {WIND, SOLAR, HYDRO, BIOENERGY}. BATTERY and PUMPED_HYDRO are excluded.
- **No DUID-name inference** is used at any stage. All classifications derive from raw AEMO registration descriptor fields.
- **UNKNOWN** is retained explicitly for unresolved mappings.
- Charging loads are distinct from generation and remain in the LOAD / SCHEDULED_LOAD classes.

## Fuel taxonomy — counts and shares

| Fuel category | Count | unit_share_pct | Registered MW | registered_capacity_share_pct |
|---|---:|---:|---:|---:|
| BLACK_COAL | 34 | 8.854167 | 16405.000 | 25.498787 |
| BROWN_COAL | 10 | 2.604167 | 4690.000 | 7.289809 |
| NATURAL_GAS | 72 | 18.750000 | 9720.996 | 15.109638 |
| DIESEL | 10 | 2.604167 | 537.600 | 0.835608 |
| DISTILLATE | 3 | 0.781250 | 419.000 | 0.651264 |
| WIND | 86 | 22.395833 | 11635.890 | 18.086015 |
| SOLAR | 101 | 26.302083 | 10263.807 | 15.953345 |
| HYDRO | 48 | 12.500000 | 7808.100 | 12.136366 |
| BIOENERGY | 3 | 0.781250 | 98.000 | 0.152324 |
| BATTERY | 9 | 2.343750 | 621.000 | 0.965239 |
| LOAD | 4 | 1.041667 | 1320.000 | 2.051716 |
| OTHER | 4 | 1.041667 | 817.000 | 1.269888 |
| UNKNOWN | 0 | 0.000000 | 0.000 | 0.000000 |

## Technology taxonomy — counts

| Technology category | Count | Registered MW |
|---|---:|---:|
| STEAM_TURBINE | 51 | 22293.000 |
| GAS_TURBINE | 68 | 7125.000 |
| COMBINED_CYCLE | 10 | 2794.600 |
| RECIPROCATING_ENGINE | 7 | 474.996 |
| WIND_TURBINE | 86 | 11635.890 |
| SOLAR_PV | 101 | 10263.807 |
| HYDRO_TURBINE | 46 | 7238.100 |
| PUMPED_HYDRO | 2 | 570.000 |
| BATTERY_STORAGE | 9 | 621.000 |
| SCHEDULED_LOAD | 4 | 1320.000 |
| OTHER | 0 | 0.000 |
| UNKNOWN | 0 | 0.000 |

## Storage classification result

| Attribute | Value |
|---|---|
| storage_units (BATTERY + PUMPED_HYDRO) | 11 |
| storage_capacity_mw | 1191.000 |
| battery_is_storage_not_primary_renewable | true |
| pumped_hydro_classified_separately | true |

## Pumped-hydro treatment

| Attribute | Value |
|---|---|
| units | 2 |
| capacity_mw | 570.000 |
| classified_as | PUMPED_HYDRO (storage conversion) |
| counted_as_primary_renewable | false |

## Ambiguous raw AEMO descriptor mappings

| DUID | Field | Raw descriptor | Production treatment |
|---|---|---|---|
| AGLHAL | Fuel Source - Descriptor | NATURAL GAS / DIESEL | OTHER |
| TORRB2 | Fuel Source - Descriptor | NATURAL GAS / FUEL OIL | OTHER |
| TORRB3 | Fuel Source - Descriptor | NATURAL GAS / FUEL OIL | OTHER |
| TORRB4 | Fuel Source - Descriptor | NATURAL GAS / FUEL OIL | OTHER |
| W/HOE#1 | Technology Type - Descriptor | PUMP STORAGE | PUMPED_HYDRO — storage conversion, excluded from primary renewable generation |
| W/HOE#2 | Technology Type - Descriptor | PUMP STORAGE | PUMPED_HYDRO — storage conversion, excluded from primary renewable generation |

## Unknown / unmapped
- `unknown_unmapped_count`: 3
