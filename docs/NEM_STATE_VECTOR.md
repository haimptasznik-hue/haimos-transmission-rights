# NEM State Vector

Status: **Phase 6A design artifact**  
Phase: **Market Physics Research Program**  
Baseline: `digital-twin-v1.0` is frozen and must not be modified  
Scope: **Ontology and state definition only — no modelling or ingestion work**

## Purpose
This document defines the complete set of variables needed to describe the physical state of the National Electricity Market at a single five-minute dispatch interval.

Internally, this is better understood as the **Market State Ontology**.

- **Ontology:** defines what exists, how entities relate, and what each variable means.
- **State Vector:** one numerical implementation of that ontology at time $t$.

Phase 6A designs the ontology first so that future state vectors, forecasting systems, valuation tools, and trading applications all inherit a consistent physical vocabulary.

## Design Principles
- **Point-in-time first:** every variable must be assessed for PIT safety explicitly.
- **Physical meaning before prediction:** variables are included because they represent system state, not because they improve a backtest.
- **Explainability over exhaustiveness:** the first practical vector should capture most market behavior without attempting to encode every possible detail.
- **Frozen Digital Twin boundary:** no Phase 6A output may require modification to the Settlement Engine, Replay Engine, Market State Database, RuleSet Engine, unit calculations, or PIT framework.
- **Research governance:** every future arrow experiment should reference variables defined here.

## Metadata Schema
Every state variable is documented using the following fields:
- **Variable name**
- **Description**
- **Units**
- **Dispatch interval frequency**
- **Geographic scope**
- **Historical availability**
- **Point-in-time safe?**
- **Public or proprietary?**
- **Expected data quality**
- **Source dataset**
- **Refresh frequency**
- **Missing-data handling**
- **Expected importance**
- **Confidence**
- **Dependent Market Physics arrows**

## Market State Ontology Structure
The ontology is organized into the following groups:
1. Demand
2. Generation
3. Renewable generation
4. Storage
5. Transmission
6. Constraints
7. Weather
8. Fuel availability
9. Generator outages
10. Network outages
11. FCAS
12. Economics
13. Market structure
14. Derived variables

## Variable Catalogue

### Demand

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `demand_nsw_mw` | NSW scheduled demand at dispatch interval | MW | 5 min | NSW1 | Strong in AEMO dispatch history | Yes | Public | High | `DISPATCHREGIONSUM` | 5 min | Forward-fill only within same trading day; otherwise missing | Critical | High | ARROW_001, ARROW_004, ARROW_006 |
| `demand_qld_mw` | QLD scheduled demand | MW | 5 min | QLD1 | Strong | Yes | Public | High | `DISPATCHREGIONSUM` | 5 min | Same as above | Critical | High | ARROW_001, ARROW_006 |
| `demand_vic_mw` | VIC scheduled demand | MW | 5 min | VIC1 | Strong | Yes | Public | High | `DISPATCHREGIONSUM` | 5 min | Same as above | High | High | ARROW_001 |
| `demand_sa_mw` | SA scheduled demand | MW | 5 min | SA1 | Strong | Yes | Public | High | `DISPATCHREGIONSUM` | 5 min | Same as above | High | High | ARROW_001 |
| `demand_tas_mw` | TAS scheduled demand | MW | 5 min | TAS1 | Likely available; not yet verified in current research scope | Yes | Public | Medium | `DISPATCHREGIONSUM` | 5 min | Missing if TAS excluded from scope; document explicitly | Medium | Medium | Future TAS arrows |
| `regional_demand_imbalance_score` | Cross-region demand imbalance indicator, e.g. deficits/surpluses normalized by total demand | index | 5 min | NEM-wide | Derived from region demand once base demand exists | Yes | Public | Medium | Derived from `DISPATCHREGIONSUM` | 5 min | Recompute from source; never impute directly | Critical | Medium | ARROW_006, ARROW_007 |

### Generation

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `generation_nsw_mw` | Total scheduled generation in NSW | MW | 5 min | NSW1 | Partial if only regional totals; fuller with unit-level SCADA | Yes | Public | Medium | `DISPATCHREGIONSUM`, optionally `DISPATCH_UNIT_SCADA` | 5 min | Use regional totals first; refine with unit-level later | High | Medium | ARROW_003, ARROW_006 |
| `generation_qld_mw` | Total scheduled generation in QLD | MW | 5 min | QLD1 | Partial | Yes | Public | Medium | `DISPATCHREGIONSUM`, optionally `DISPATCH_UNIT_SCADA` | 5 min | Same as above | High | Medium | ARROW_003 |
| `generation_vic_mw` | Total scheduled generation in VIC | MW | 5 min | VIC1 | Partial | Yes | Public | Medium | Same | 5 min | Same as above | Medium | Medium | Future arrows |
| `generation_sa_mw` | Total scheduled generation in SA | MW | 5 min | SA1 | Partial | Yes | Public | Medium | Same | 5 min | Same as above | Medium | Medium | Future arrows |
| `marginal_generation_cost_proxy` | Proxy for short-run marginal generating mix setting energy price | AUD/MWh proxy | 5 min | Region | Derived; needs bid/dispatch context for robustness | Potentially | Mixed | Low-Medium | Derived from bids + dispatch, not yet standardized | 5 min | Do not impute; mark unavailable if bids absent | High | Low | ARROW_008, ARROW_009 |

### Renewable Generation

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `wind_output_region_mw` | Aggregate wind generation by region | MW | 5 min | Region | Unknown until `DISPATCH_UNIT_SCADA` validated | Yes if sourced historically | Public | Medium | `DISPATCH_UNIT_SCADA` + DUID fuel map | 5 min | No imputation; use missing flag | Critical | Low-Medium | ARROW_002, ARROW_006 |
| `solar_output_region_mw` | Aggregate solar generation by region | MW | 5 min | Region | Unknown until unit-level data confirmed | Yes | Public | Medium | `DISPATCH_UNIT_SCADA` + DUID fuel map | 5 min | Same as above | High | Low-Medium | ARROW_005 |
| `wind_penetration_pct` | Wind output as share of regional generation or demand | % | 5 min | Region | Derived once wind and demand exist | Yes | Public | Medium | Derived | 5 min | Recompute from components | Critical | Medium | ARROW_002 |
| `solar_penetration_pct` | Solar output share | % | 5 min | Region | Derived | Yes | Public | Medium | Derived | 5 min | Recompute from components | High | Medium | ARROW_005 |
| `renewable_ramp_rate_mw` | 5-minute change in renewable generation | MW/5min | 5 min | Region | Derived when wind/solar available | Yes | Public | Medium | Derived | 5 min | Leave blank where prior interval unavailable | Medium | Medium | Future ramp arrows |

### Storage

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `battery_dispatch_mw` | Net battery charging/discharging by region | MW | 5 min | Region | Unknown pending unit-level data | Yes | Public | Medium | `DISPATCH_UNIT_SCADA` + battery DUID map | 5 min | Missing until SCADA verified | High | Low-Medium | KU-001, future arrows |
| `battery_soc_proxy` | Estimated state of charge from dispatch history | % or MWh proxy | 5 min | Asset/region | Not directly public; requires estimation | Potentially | Mixed | Low | Derived from SCADA and capacity metadata | 5 min | Do not impute across long gaps | Medium | Low | Future storage arrows |
| `pumped_hydro_dispatch_mw` | Net pumped hydro output/charging | MW | 5 min | Region | Likely via unit-level data | Yes | Public | Medium | `DISPATCH_UNIT_SCADA` | 5 min | Missing until SCADA verified | Medium | Low-Medium | Future hydro arrows |

### Transmission

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `qni_flow_mw` | Actual QNI directional flow | MW | 5 min | NSW1↔QLD1 | Strong | Yes | Public | High | `DISPATCHINTERCONNECTORRES` | 5 min | No interpolation across missing intervals | Critical | High | ARROW_006, ARROW_007 |
| `vic_nsw_flow_mw` | Actual VIC-NSW flow | MW | 5 min | VIC1↔NSW1 | Strong | Yes | Public | High | `DISPATCHINTERCONNECTORRES` | 5 min | Same | High | High | Future interconnector arrows |
| `vic_sa_flow_mw` | Actual VIC-SA flow | MW | 5 min | VIC1↔SA1 | Strong | Yes | Public | High | `DISPATCHINTERCONNECTORRES` | 5 min | Same | High | High | Future interconnector arrows |
| `interconnector_utilisation_pct` | Actual flow divided by transfer capability | % | 5 min | Interconnector | Partial; capability source must be standardized | Yes | Public | Medium | `DISPATCHINTERCONNECTORRES` + capability metadata | 5 min | Recompute only where denominator known | Critical | Medium | ARROW_007, ARROW_008 |
| `flow_reversal_flag` | Indicator that an interconnector changed direction from prior interval | binary | 5 min | Interconnector | Derived | Yes | Public | High | Derived from interconnector flow | 5 min | False if no previous interval | Medium | High | Future regime arrows |

### Constraints

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `binding_constraint_count` | Number of binding or near-binding dispatch constraints | count | 5 min | NEM/region | Unknown pending `DISPATCHCONSTRAINT` verification | Yes | Public | Medium | `DISPATCHCONSTRAINT` | 5 min | Missing until acquired | Critical | Low-Medium | ARROW_008 |
| `constraint_severity_score` | Aggregate severity of active constraints | index | 5 min | NEM/interconnector | Unknown pending constraint data | Yes | Public | Low-Medium | Derived from `DISPATCHCONSTRAINT` | 5 min | No imputation; mark unavailable | Critical | Low | ARROW_008 |
| `qni_binding_flag` | Whether a QNI-relevant constraint is binding | binary | 5 min | QNI | Unknown pending constraint IDs | Yes | Public | Medium | `DISPATCHCONSTRAINT` | 5 min | Missing until mapping exists | Critical | Low | ARROW_008 |

### Weather

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `temperature_region_c` | Ambient temperature representative of each region | °C | 5 min or hourly resampled | Region | Public but not yet integrated | Yes | Public | Medium | BOM or equivalent | Hourly/daily source, resampled to 5 min | Short-gap interpolation with source flag | Critical | Medium | ARROW_001 |
| `temperature_anomaly_c` | Temperature minus seasonal norm | °C anomaly | 5 min/hourly | Region | Derived once temperature and normals exist | Yes | Public | Medium | Derived from BOM + climate normals | Daily/hourly | Compute only where normals available | High | Medium | KU-006 |
| `wind_speed_region_ms` | Physical wind condition proxy for generation availability | m/s | Hourly or finer | Region | Public external source; not yet integrated | Yes | Public | Medium | BOM / reanalysis | Hourly | Interpolate carefully with provenance flag | Medium | Low-Medium | ARROW_002 |
| `solar_irradiance_region_wm2` | Solar resource proxy | W/m² | Hourly or finer | Region | Public external source | Yes | Public | Medium | BOM / satellite-derived | Hourly | Interpolate with source flag | Medium | Low-Medium | ARROW_005 |

### Fuel Availability

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `coal_availability_pct` | Available coal generation as share of installed or expected capacity | % | 5 min/daily hybrid | Region/NEM | Partial; unit availability needs outage/unit data | Potentially | Mixed | Low-Medium | SCADA + outage notices + capacity metadata | 5 min/daily | Missing until data model defined | Critical | Low-Medium | ARROW_003 |
| `gas_availability_pct` | Gas generation availability | % | 5 min/daily hybrid | Region | Partial | Potentially | Mixed | Low-Medium | SCADA + outage metadata | 5 min/daily | Same | High | Low-Medium | ARROW_003 |
| `hydro_availability_pct` | Hydro dispatchable availability | % | 5 min/daily hybrid | Region | Partial; storage level adds complexity | Potentially | Mixed | Low | SCADA + storage data | 5 min/daily | Same | High | Low | KU-002 |

### Generator Outages

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `generator_outage_score_mw` | Aggregate MW of unavailable generation due to outages | MW | 5 min/daily hybrid | Region/NEM | Partial | Potentially | Mixed | Low-Medium | outage notices + SCADA deviation | Daily / event | Leave unavailable if notices absent | High | Low-Medium | ARROW_003, future resilience arrows |
| `coal_outage_mw` | Coal-specific outage MW | MW | 5 min/daily hybrid | Region/NEM | Partial | Potentially | Mixed | Low-Medium | outage notices + SCADA | Daily / event | Same | High | Low-Medium | ARROW_003 |
| `unit_trip_event_flag` | Sudden forced outage/trip inferred from dispatch collapse | binary | 5 min | Unit/region | Possible from SCADA if available | Yes | Public | Medium | Derived from `DISPATCH_UNIT_SCADA` | 5 min | False unless event threshold met | Medium | Low-Medium | Future outage arrows |

### Network Outages

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `network_outage_score` | Aggregate severity of network outages affecting transfer capability | index | 5 min/daily hybrid | Interconnector/NEM | Partial; public notices exist but ingestion absent | Potentially | Public | Low-Medium | outage notices, network outage tables | Event-driven | Missing until acquisition plan exists | High | Low | ARROW_007, ARROW_008 |
| `interconnector_derating_pct` | Reduction in transfer capability due to outages | % | 5 min | Interconnector | Partial | Potentially | Public | Low-Medium | capability notices + dispatch data | Event-driven | Missing until standardized | High | Low | ARROW_007 |

### FCAS

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `fcas_raise_scarcity_flag` | Indicator of FCAS raise scarcity | binary | 5 min | Region/NEM | Likely available from dispatch prices | Yes | Public | Medium | `DISPATCHPRICE` FCAS components | 5 min | False only if verified absent | Medium | Medium | KU-005 |
| `fcas_lower_scarcity_flag` | Indicator of FCAS lower scarcity | binary | 5 min | Region/NEM | Likely available | Yes | Public | Medium | `DISPATCHPRICE` FCAS components | 5 min | Same | Medium | Medium | KU-005 |
| `fcas_price_stress_index` | Aggregate FCAS stress measure | index | 5 min | Region/NEM | Derived | Yes | Public | Medium | Derived from FCAS prices | 5 min | Recompute from source | Medium | Medium | Future FCAS arrows |

### Economics

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `business_day_flag` | Indicator for weekday/business activity | binary | Daily | NEM | Fully available | Yes | Public | High | Calendar-derived | Daily | Deterministic | Medium | High | ARROW_004 |
| `holiday_flag` | Public holiday indicator by region | binary | Daily | Region | Fully available | Yes | Public | High | Calendar-derived | Daily | Deterministic | Medium | High | ARROW_004 |
| `industrial_load_proxy` | Proxy for non-weather demand | index | Daily/5 min | Region | Weak without external data | Potentially | Mixed | Low | Derived / external industry data | Daily | Missing until source chosen | Medium | Low | KU-007 |
| `fuel_cost_proxy` | Simplified gas/coal fuel cost backdrop | AUD/MWh proxy | Daily | NEM/region | External, likely public/commercial mix | Potentially | Mixed | Low | Market data / commodity curves | Daily | Missing until source licensed | Medium | Low | Future economics arrows |

### Market Structure

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `market_concentration_proxy` | Share of dispatch by top participants | % | 5 min/daily | Region | Partial with participant mapping | Potentially | Public | Low-Medium | unit dispatch + participant metadata | Daily | Missing until mapping exists | Low-Medium | Low | Future structure arrows |
| `marginal_fuel_type` | Fuel type of marginal generator | category | 5 min | Region | Partial | Potentially | Public | Low-Medium | bids + unit dispatch | 5 min | Missing until bid stack methodology defined | High | Low | ARROW_009 |

### Derived Variables

| Variable name | Description | Units | Freq | Scope | Hist. availability | PIT safe? | Public? | Data quality | Source dataset | Refresh | Missing-data handling | Importance | Confidence | Dependent arrows |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `regional_price_spread_qld_nsw` | QLD minus NSW energy price | AUD/MWh | 5 min | QLD1↔NSW1 | Strong | Yes | Public | High | `DISPATCHPRICE` | 5 min | No imputation | Critical | High | ARROW_008, ARROW_009 |
| `regional_price_spread_vic_nsw` | VIC minus NSW price | AUD/MWh | 5 min | VIC1↔NSW1 | Strong | Yes | Public | High | `DISPATCHPRICE` | 5 min | No imputation | High | High | Future arrows |
| `irsr_interval_qni` | Interval IRSR on QNI direction | AUD | 5 min | Interconnector direction | Derived in verified Digital Twin | Yes | Internal derived from public data | High | Digital Twin Layer 3 output | 5 min/quarterly reconstruction | Recompute only from verified logic | Critical | High | ARROW_008, ARROW_010 |
| `sra_value_proxy` | Simplified economic value proxy for rights | AUD/unit proxy | 5 min/quarterly | Corridor | Derived, not for Phase 6A modelling | Potentially | Internal | Low-Medium | Derived | Event/quarter | Not used in Phase 6A | Low for 6A | Low | Future Layer 5 work |
| `outage_score_total` | Combined generation + network outage severity | index | 5 min | NEM/region | Derived once outage data available | Potentially | Mixed | Low | Derived | 5 min | Missing until sources acquired | High | Low | Future resilience arrows |

## Practical Version 1 State Vector
The full ontology is intentionally broader than the first implementable vector.

### Inclusion criteria for Version 1
A variable should enter the practical Version 1 State Vector if it is:
1. physically meaningful,
2. likely explanatory of market behavior,
3. plausibly available from current or near-term public datasets,
4. PIT-safe, and
5. sufficiently interpretable for arrow experiments.

### Recommended Version 1 variables
The initial practical vector should include the following:

| Include? | Variable | Why included |
|---|---|---|
| Yes | Regional demand by NSW/QLD/VIC/SA | Core load state; directly observable; foundational to most arrows |
| Yes | QNI / VIC-NSW / VIC-SA flows | Direct transmission state for major SRA corridors |
| Yes | Interconnector utilisation % | Key bridge between state and network stress |
| Yes | Regional price spreads | Observable summary of market tension; useful state descriptor even before full causal validation |
| Yes | FCAS scarcity flags | Helps separate energy-only effects from ancillary-service stress |
| Yes | Binding constraint count | Core representation of system tightness if constraint data is acquired |
| Yes | Constraint severity score | Converts raw constraint activity into a usable state variable |
| Yes | Temperature by region | Foundational exogenous driver |
| Yes | Temperature anomaly | Likely superior weather signal for demand deviations |
| Yes | Wind penetration % | Core renewable state variable |
| Yes | Solar penetration % | Core daylight/net-load state variable |
| Yes | Coal availability % | Central thermal adequacy measure |
| Yes | Gas availability % | Important for price-setting flexibility |
| Yes | Hydro availability % | Important for peaking and residual price dynamics |
| Yes | Battery dispatch MW | Emerging flexibility state variable |
| Yes | Outage score | Compact measure of generation/network stress |

### Intentionally excluded from Version 1

| Variable | Reason excluded from Version 1 |
|---|---|
| Battery SOC estimate | Conceptually important but difficult to estimate robustly without bespoke methodology |
| Market concentration proxy | Likely secondary to physical state in Phase 6A |
| Fuel cost proxy | Valuable later, but outside core physical-state definition and may add external licensing complexity |
| SRA value proxy | Too close to downstream investment layer; not needed for state definition |
| Voltage stability indicators | Important but currently low-readiness and less central to initial corridor-focused work |
| Marginal generation cost proxy | Useful later; methodology not yet standardized |
| Industrial load proxy | Potentially useful, but external data weak and indirect |

## Major Design Choices
- **Ontology first, vector second:** the ontology is broader than any first implementation.
- **Regional aggregation before unit granularity:** Phase 6A prefers variables that are explainable and observable before high-dimensional unit models.
- **Derived variables are allowed:** if derived from PIT-safe inputs and physically interpretable.
- **Unknowns must remain explicit:** if a variable cannot yet be populated, it still belongs in the ontology if it is physically real and potentially important.

## Phase 6A Outputs Enabled by This Document
This ontology supports:
- `docs/NEM_STATE_DEPENDENCY_MAP.md`
- `docs/NEM_DATA_COVERAGE_MATRIX.md`
- `docs/PHASE6A_RECOMMENDATIONS.md`
- future `STATE_001` construction work
- future Market Physics arrow design

## Summary
The Market State Ontology defines the informational boundary of what the NEM "is" at dispatch time. The practical Version 1 State Vector is the subset that is both scientifically valuable and operationally feasible for early experiments.

Phase 6A succeeds if this ontology becomes stable enough that future research asks:

> Which variables change the state, and how does state produce market outcomes?

rather than:

> Which correlations seem useful for trading?
