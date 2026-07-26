# NEM Data Coverage Matrix

Status: **Phase 6A design artifact**  
Purpose: assess practical data readiness for the Market State Ontology  
Scope: **documentation only; no ingestion or modelling work**

## Purpose
This matrix evaluates whether each important ontology variable can be supported today using the current repository, adjacent public AEMO data, or external public sources.

Each variable is categorized as:
- **READY** — available today with acceptable PIT safety and manageable implementation effort.
- **PARTIAL** — conceptually available, but incomplete in historical depth, ingestion, mapping, or PIT treatment.
- **NOT AVAILABLE** — currently missing or not practically obtainable for current scope.

## Readiness Criteria
A variable is considered **READY** if all are true:
1. historical source is identified,
2. PIT safety is clear,
3. public access is established,
4. implementation effort is low-to-moderate,
5. semantic meaning is stable enough for Phase 6 work.

## Coverage Matrix

| Variable | Group | Available today | Historical depth | PIT safe | Public | Download source | Already ingested? | Implementation effort | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Regional demand by NSW/QLD/VIC/SA | Demand | Yes | Strong | Yes | Yes | AEMO MMSDM `DISPATCHREGIONSUM` | Yes | Low | READY | Foundational state layer variable |
| TAS demand | Demand | Likely | Strong | Yes | Yes | `DISPATCHREGIONSUM` | Probably | Low | PARTIAL | Not central to initial SRA corridors |
| Regional total generation | Generation | Partial | Strong | Yes | Yes | `DISPATCHREGIONSUM` | Yes | Low | READY | Coarse but usable before unit-level split |
| Wind output by region | Renewable | Unknown | Unknown pending validation | Yes if sourced | Yes | `DISPATCH_UNIT_SCADA` + DUID map | No | Medium | PARTIAL | Blocked by KU-003 |
| Solar output by region | Renewable | Unknown | Unknown pending validation | Yes if sourced | Yes | `DISPATCH_UNIT_SCADA` + DUID map | No | Medium | PARTIAL | Same dependency as wind |
| Wind penetration % | Renewable | Partial | Dependent on wind output | Yes | Yes | Derived | No | Medium | PARTIAL | Ready once regional wind exists |
| Solar penetration % | Renewable | Partial | Dependent on solar output | Yes | Yes | Derived | No | Medium | PARTIAL | Ready once regional solar exists |
| Renewable ramp rate | Renewable | Partial | Dependent on output series | Yes | Yes | Derived | No | Medium | PARTIAL | Useful later |
| QNI flow | Transmission | Yes | Strong | Yes | Yes | AEMO `DISPATCHINTERCONNECTORRES` | Yes | Low | READY | Verified corridor-relevant |
| VIC-NSW flow | Transmission | Yes | Strong | Yes | Yes | `DISPATCHINTERCONNECTORRES` | Yes | Low | READY | Verified |
| VIC-SA flow | Transmission | Yes | Strong | Yes | Yes | `DISPATCHINTERCONNECTORRES` | Yes | Low | READY | Verified |
| Interconnector utilisation % | Transmission | Partial | Strong | Yes | Yes | Flow + capability metadata | Partial | Medium | PARTIAL | Need capability denominator standard |
| Flow reversal flag | Transmission | Yes | Strong | Yes | Yes | Derived from flows | No | Low | READY | Easy derived variable |
| Binding constraint count | Constraints | Unknown | Unknown pending validation | Yes | Yes | AEMO `DISPATCHCONSTRAINT` | No | Medium | PARTIAL | Critical gap; KU-004 |
| Constraint severity score | Constraints | No | No standardized history yet | Yes if built | Yes | `DISPATCHCONSTRAINT` | No | Medium-High | PARTIAL | Needs methodology definition |
| QNI-specific binding flag | Constraints | Unknown | Unknown pending mapping | Yes | Yes | `DISPATCHCONSTRAINT` | No | Medium-High | PARTIAL | Depends on relevant constraint IDs |
| Temperature by region | Weather | No in repo | Public history likely available | Yes | Yes | BOM / external weather | No | Medium | PARTIAL | Not ingested yet |
| Temperature anomaly | Weather | No in repo | Depends on normals | Yes | Yes | BOM + climate normals | No | Medium | PARTIAL | Likely better explanatory construct |
| Wind speed by region | Weather | No in repo | Public history likely available | Yes | Yes | BOM / reanalysis | No | Medium | PARTIAL | Optional support for wind arrows |
| Solar irradiance by region | Weather | No in repo | Public history likely available | Yes | Yes | BOM / satellite/reanalysis | No | Medium | PARTIAL | Optional support for solar arrows |
| Coal availability % | Fuel availability | No clean series yet | Partial via outages + SCADA if available | Potentially | Mixed public | SCADA + outage notices | No | High | PARTIAL | High value, unresolved data model |
| Gas availability % | Fuel availability | No clean series yet | Partial | Potentially | Mixed public | SCADA + outage notices | No | High | PARTIAL | Similar issue |
| Hydro availability % | Fuel availability | No clean series yet | Weak without storage context | Potentially | Mixed | SCADA + hydro storage | No | High | PARTIAL | Major knowledge gap |
| Battery dispatch MW | Storage | Unknown | Unknown pending SCADA | Yes | Yes | `DISPATCH_UNIT_SCADA` | No | Medium | PARTIAL | Critical for newer NEM state |
| Battery SOC proxy | Storage | No | No direct source | Potentially | Mixed | Derived from SCADA/capacity | No | High | NOT AVAILABLE | Research concept, not Phase 6A-ready |
| Pumped hydro dispatch | Storage | Unknown | Unknown pending SCADA | Yes | Yes | `DISPATCH_UNIT_SCADA` | No | Medium | PARTIAL | Secondary priority |
| Generator outage score | Generator outages | No clean historical series in repo | Partial | Potentially | Mixed | Outage notices + SCADA | No | High | PARTIAL | Valuable but effortful |
| Coal outage MW | Generator outages | Partial | Event history likely public | Potentially | Public/Mixed | outage notices | No | High | PARTIAL | Could be approximated |
| Network outage score | Network outages | No | Partial | Potentially | Public | network outage notices | No | High | PARTIAL | Important for capability effects |
| Interconnector derating % | Network outages | No standardized series | Partial | Potentially | Public | outage/capability notices | No | High | PARTIAL | Useful but requires synthesis |
| FCAS raise scarcity flag | FCAS | Likely | Strong if FCAS components present | Yes | Yes | `DISPATCHPRICE` | Partial | Low-Medium | PARTIAL | Needs extraction verification |
| FCAS lower scarcity flag | FCAS | Likely | Strong if components present | Yes | Yes | `DISPATCHPRICE` | Partial | Low-Medium | PARTIAL | Same |
| FCAS stress index | FCAS | Partial | Dependent on FCAS component extraction | Yes | Yes | Derived from `DISPATCHPRICE` | No | Medium | PARTIAL | Good explanatory add-on |
| Business day flag | Economics | Yes | Complete | Yes | Yes | Calendar | No | Low | READY | Simple and useful |
| Holiday flag | Economics | Yes | Complete | Yes | Yes | Calendar | No | Low | READY | Simple and useful |
| Industrial load proxy | Economics | No robust series | Weak | Potentially | Mixed | External industry datasets | No | High | NOT AVAILABLE | May remain conceptual initially |
| Fuel cost proxy | Economics | No in repo | External market data needed | Potentially | Mixed | commodity/market feeds | No | Medium-High | NOT AVAILABLE | Outside core Phase 6A need |
| Regional price spreads | Derived | Yes | Strong | Yes | Yes | `DISPATCHPRICE` | Partially | Low | READY | Core observable state descriptor |
| IRSR interval values | Derived | Yes | Verified for C2024Q4 | Yes | Internal derived from public data | Digital Twin Layer 3 | Yes | Low | READY | Outcome, not ontology core |
| Outage score total | Derived | No | Depends on outage acquisition | Potentially | Mixed | Derived | No | High | PARTIAL | Good compact summary if sources acquired |
| Marginal fuel type | Market structure | No | Possible with bids + dispatch | Potentially | Yes | bids + SCADA | No | High | PARTIAL | High value, significant methodology effort |
| Market concentration proxy | Market structure | No | Possible with participant map | Potentially | Public | participant metadata + dispatch | No | Medium | PARTIAL | Secondary priority |

## Status Summary

### READY
Variables that can support Phase 6A and early Phase 6B immediately:
- Regional demand (NSW/QLD/VIC/SA)
- Regional total generation (coarse)
- QNI / VIC-NSW / VIC-SA flows
- Flow reversal flag
- Regional price spreads
- Business day flag
- Holiday flag
- IRSR interval values as validated outcome reference

### PARTIAL
High-value variables that likely exist but require validation, mapping, or acquisition discipline:
- Wind/solar output by region
- Wind/solar penetration
- Interconnector utilisation %
- Binding constraint count / severity / QNI constraint flags
- Temperature and temperature anomaly
- Coal/gas/hydro availability
- Battery dispatch
- Generator and network outage scores
- FCAS scarcity indicators
- Marginal fuel type

### NOT AVAILABLE
Variables not ready for Phase 6A practical use:
- Battery SOC proxy
- Industrial load proxy
- Fuel cost proxy

## Major Blocking Dependencies

| Blocking dependency | Variables affected | Why it matters |
|---|---|---|
| `DISPATCH_UNIT_SCADA` availability and mapping | wind, solar, coal, gas, hydro, battery, outage proxies | Unlocks most supply-side state variables |
| `DISPATCHCONSTRAINT` availability and mapping | constraint count, severity, QNI binding flags | Essential bridge from state to network physics |
| External weather data integration | temperature, anomaly, wind speed, irradiance | Needed for the first exogenous driver arrows |
| Outage/capability metadata | coal outages, network outages, deratings | Needed to explain residual stress and capability shocks |

## Estimated Readiness by Group

| Group | Readiness | Comment |
|---|---|---|
| Demand | High | Strongest group today |
| Transmission | High-Medium | Core flow variables ready; capability variables partial |
| Derived market-state summaries | Medium-High | Price spreads ready; richer summaries partial |
| Weather | Medium | Sources are public but not yet integrated |
| Renewable generation | Medium-Low | Likely available once unit-level data is verified |
| Constraints | Medium-Low | High importance, but data readiness not yet proven in current repo |
| Fuel availability | Low-Medium | Scientifically critical but data model incomplete |
| Storage | Low-Medium | Battery dispatch likely possible; SOC not ready |
| Economics | Medium-Low | Calendar variables ready; richer economic proxies weak |
| Market structure | Low-Medium | Useful later, but not core to Phase 6A |

## Coverage Conclusion
The ontology is broader than current data availability, which is expected and acceptable.

Phase 6A does **not** require all variables to be ready. It requires clarity on:
1. what variables matter,
2. which are available now,
3. which require acquisition or methodology work, and
4. which should be excluded from Version 1.

The current repository appears strong enough to support a meaningful Version 1 Market State Vector focused on:
- demand,
- flows,
- price spreads,
- calendar effects,
- and selected constraint/weather/supply variables once a small number of upstream gaps are resolved.
