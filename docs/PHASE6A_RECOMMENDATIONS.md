# Phase 6A Recommendations

Status: **Phase 6A completion memo**  
Scope: architecture and scientific design only  
Implementation constraint: **no ingestion, modelling, or Digital Twin modifications permitted**

## Executive Summary
Phase 6A defines the information architecture for Market Physics Research.

The central design conclusion is:

> The Digital Twin should be treated as an experimental laboratory for reconstructing **Grid State**, not merely market outcomes.

Accordingly, the correct internal object is the **Market State Ontology**, with the **State Vector** representing one practical numerical implementation of that ontology at dispatch interval $t$.

Four conclusions follow:
- The NEM should be described using a five-layer causal hierarchy: **Physical Drivers → Grid State → Network Physics → Market Outcomes → Investment Decisions**.
- A useful Version 1 State Vector can be built now from a subset of ontology variables without waiting for total data completeness.
- The largest scientific gaps are not in price data; they are in supply-side state, constraints, outages, and weather normalization.
- Phase 6B should begin with state-forming arrows, not outcome-predicting arrows.

## 1. Major Knowledge Gaps

### Gap A — Unit-level supply state
The single most important unresolved issue is whether the repository can support unit-level reconstruction of:
- wind output,
- solar output,
- coal availability,
- gas availability,
- hydro availability,
- battery dispatch,
- outage proxies.

This largely depends on validating `DISPATCH_UNIT_SCADA` availability for C2024Q4 and mapping DUIDs to fuel categories.

### Gap B — Constraint observability
Constraint activity is likely one of the most important bridges between Grid State and market outcomes, but the current readiness of `DISPATCHCONSTRAINT` has not yet been established.

Without constraint data, the research program risks inferring binding behavior indirectly from price and flow — useful, but scientifically weaker.

### Gap C — Weather normalization
Raw temperature is likely not the best weather driver representation. Temperature anomaly, wind resource, and solar irradiance are probably more causally precise.

These data appear publicly available, but they are not yet integrated into the current research assets.

### Gap D — Outage and transfer-capability shocks
Generation outages and network outages are likely major residual drivers of price and residue stress. These remain only partially represented in current data planning.

### Gap E — Region-specific mechanisms
QLD demand behavior, hydro-driven NSW spikes, and battery effects on corridor loading all appear likely to differ by region and regime.

This implies that the final Market Physics Laws will likely include explicit boundary conditions rather than universal parameterizations.

## 2. Variables Already Available

The following variables appear usable today or with minimal derivation from existing verified assets:

### Strongly available now
- Regional demand by NSW/QLD/VIC/SA from `DISPATCHREGIONSUM`
- Regional total generation (coarse) from `DISPATCHREGIONSUM`
- QNI / VIC-NSW / VIC-SA interconnector flows from `DISPATCHINTERCONNECTORRES`
- Regional price series and price spreads from `DISPATCHPRICE`
- IRSR interval-level outcomes from the verified Digital Twin
- Calendar features such as weekday / holiday flags

### Likely derivable with modest effort
- Flow reversal flags
- Demand imbalance scores
- Coarse interconnector utilisation, if capability denominator is standardized
- FCAS scarcity indicators from `DISPATCHPRICE`, subject to field confirmation

These variables are sufficient to define a meaningful but incomplete Version 1 State Vector.

## 3. Variables Requiring Acquisition or Methodology Work

### High-priority acquisition / validation
- `DISPATCH_UNIT_SCADA`
- DUID-to-fuel mapping table
- `DISPATCHCONSTRAINT`
- Relevant constraint ID mapping for key corridors
- BOM temperature history by region
- Climate normals for anomaly construction

### Secondary acquisition / methodology
- Generation outage notices / outage metadata
- Network outage / capability derating metadata
- Hydro storage state data
- External industrial-load proxies for QLD and other special-demand regimes

### Likely deferred beyond Version 1
- Battery SOC estimation
- Fuel cost curves
- market concentration metrics
- detailed marginal cost stacks

## 4. Initial State Vector Recommendation (Version 1)

### Recommended Version 1 design principle
Version 1 should optimize for:
- high physical interpretability,
- PIT safety,
- immediate research usefulness,
- manageable acquisition burden,
- and strong relevance to SRA / congestion mechanics.

### Recommended Version 1 State Vector components

#### Core load and supply balance
- `demand_nsw_mw`
- `demand_qld_mw`
- `demand_vic_mw`
- `demand_sa_mw`
- `regional_demand_imbalance_score`
- coarse regional generation totals

#### Core transmission state
- `qni_flow_mw`
- `vic_nsw_flow_mw`
- `vic_sa_flow_mw`
- `interconnector_utilisation_pct`
- `flow_reversal_flag`

#### Core market tension state
- `regional_price_spread_qld_nsw`
- `regional_price_spread_vic_nsw`
- `binding_constraint_count` if feasible, otherwise placeholder gap
- `constraint_severity_score` if feasible, otherwise placeholder gap
- `fcas_raise_scarcity_flag`
- `fcas_lower_scarcity_flag`

#### Core exogenous drivers
- `temperature_region_c`
- `temperature_anomaly_c`
- `business_day_flag`
- `holiday_flag`

#### Core supply-composition state (target for early expansion)
- `wind_penetration_pct`
- `solar_penetration_pct`
- `coal_availability_pct`
- `gas_availability_pct`
- `hydro_availability_pct`
- `battery_dispatch_mw`
- `outage_score_total`

### Why these variables
These variables jointly cover:
- demand stress,
- transmission stress,
- supply flexibility,
- renewable pressure,
- thermal adequacy,
- and observed market tension.

They are the minimum scientifically credible substrate for later arrow experiments.

### Intentionally excluded from Version 1
- battery SOC proxy,
- fuel cost proxy,
- market concentration metrics,
- marginal cost-stack constructs,
- full voltage stability metrics,
- direct downstream SRA valuation constructs.

These are not excluded because they are unimportant, but because they are either not sufficiently observable yet or they belong too far downstream for Phase 6A.

## 5. Recommended First Five Phase 6B Laws

The first five laws should be chosen not by trading value alone, but by how much causal structure they unlock.

### LAW_001 — Regional Supply-Demand Imbalance Drives Interconnector Power Flow
- **Hypothesis:** Regional supply-demand imbalance is the dominant physical driver of interconnector power flow.
- **Physical mechanism:** Regions with generation deficits import from regions with surplus generation; interconnector flow is the balancing channel.
- **Required datasets:** `DISPATCHREGIONSUM`, `DISPATCHINTERCONNECTORRES`, and if available `DISPATCH_UNIT_SCADA` for supply-composition controls.
- **Acceptance criteria:** $R^2 > 0.5$, correct sign in >90% of intervals, stable across summer/winter and peak/off-peak, and reproducible across historical periods.
- **Estimated implementation effort:** Low-Medium.
- **Expected uncertainty:** Medium.
- **Expected explanatory power:** Very High.
- **Scientific value:** Very High.
- **Commercial value:** Very High.

### LAW_002 — Renewable Output Shifts Net Load State
- **Hypothesis:** Wind and solar output materially reshape regional surplus/deficit by altering net load.
- **Physical mechanism:** Variable renewable output changes the dispatch burden on thermal and hydro fleets.
- **Required datasets:** `DISPATCH_UNIT_SCADA`, DUID fuel mapping, regional demand.
- **Acceptance criteria:** renewable state variables materially reduce unexplained variance in regional net-balance metrics across historical intervals.
- **Estimated implementation effort:** Medium.
- **Expected uncertainty:** Medium.
- **Expected explanatory power:** High.
- **Scientific value:** High.
- **Commercial value:** High.

### LAW_003 — Thermal Availability Sets Dispatchable Capacity Margin
- **Hypothesis:** Coal and gas availability explain a large share of dispatchable capacity margin and scarcity state.
- **Physical mechanism:** Reduced thermal availability increases reliance on imports, peaking plant, and constrained dispatch.
- **Required datasets:** `DISPATCH_UNIT_SCADA`, outage metadata, DUID fuel map.
- **Acceptance criteria:** availability variables materially reduce residual variance in state-stress metrics across periods.
- **Estimated implementation effort:** Medium-High.
- **Expected uncertainty:** Medium-High.
- **Expected explanatory power:** High.
- **Scientific value:** Very High.
- **Commercial value:** Very High.

### LAW_004 — Interconnector Utilisation Raises Constraint Probability
- **Hypothesis:** High interconnector utilisation materially raises the probability of corridor-relevant constraint binding.
- **Physical mechanism:** As flows approach effective capability, the system becomes increasingly likely to bind thermal/network/security constraints.
- **Required datasets:** interconnector flows, capability denominator, `DISPATCHCONSTRAINT`.
- **Acceptance criteria:** utilisation regimes materially explain binding frequency and severity across operating conditions.
- **Estimated implementation effort:** Medium-High.
- **Expected uncertainty:** Medium.
- **Expected explanatory power:** High.
- **Scientific value:** Very High.
- **Commercial value:** Very High.

### LAW_005 — Constraint State Produces Regional Price Separation and Residue
- **Hypothesis:** Constraint state is the dominant bridge between physical network stress and settlement residue.
- **Physical mechanism:** Binding constraints decouple regional prices, and the combination of flow plus separation generates IRSR.
- **Required datasets:** `DISPATCHCONSTRAINT`, `DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, verified Digital Twin outcomes.
- **Acceptance criteria:** constraint-state variables materially reduce unexplained variance in price separation and IRSR across historical periods.
- **Estimated implementation effort:** Medium-High.
- **Expected uncertainty:** Medium.
- **Expected explanatory power:** Very High.
- **Scientific value:** Very High.
- **Commercial value:** Very High.

## 6. Ranking of Initial Laws

| Rank | Arrow | Explanatory power | Ease | Data availability | Scientific value | Commercial value |
|---|---|---|---|---|---|---|
| 1 | LAW_001: Supply-demand imbalance → Interconnector flow | Very High | High | High | Very High | Very High |
| 2 | LAW_005: Constraint state → Price separation / IRSR | Very High | Medium-Low | Low-Medium | Very High | Very High |
| 3 | LAW_003: Thermal availability → Capacity margin | High | Medium-Low | Low-Medium | Very High | Very High |
| 4 | LAW_002: Renewable output → Net load state | High | Medium | Low-Medium | High | High |
| 5 | LAW_004: Utilisation → Constraint probability | High | Medium-Low | Low-Medium | Very High | Very High |

## 7. Recommended Phase 6B Roadmap

### Phase 6B.1 — State completion
- validate and populate Version 1 State Vector,
- explicitly mark which variables are real vs placeholder gaps,
- update `KNOWN_UNKNOWNS.md` with unresolved coverage issues.

### Phase 6B.2 — LAW_001 first
Start with a single scientific law before broad sequencing:
1. `LAW_001`: regional supply-demand imbalance → interconnector power flow
2. run `EXP_001` as the first formal experiment specification
3. only then branch into supporting laws on renewables, thermal availability, and constraints

### Phase 6B.3 — Supporting state-formation laws
Once LAW_001 is specified and gaps are clear:
4. `LAW_002`: renewable output → net load state
5. `LAW_003`: thermal availability → dispatchable capacity margin

### Phase 6B.4 — Downstream network laws
After state variables and constraints are visible:
6. `LAW_004`: interconnector utilisation → constraint probability
7. `LAW_005`: constraint state → price separation and IRSR

This order preserves mechanistic clarity and avoids jumping too early to market outcomes.

## 8. Overall Readiness Score

### Recommended readiness score: **64 / 100**

### Rationale
#### What is ready
- research governance is strong,
- the Digital Twin baseline is frozen and verified,
- demand, flows, and price outcomes are already well-grounded,
- the ontology can be designed now without technical blockers.

#### What is not yet ready
- unit-level supply state is not yet confirmed,
- constraint-state visibility is not yet confirmed,
- weather and outage data are not yet integrated,
- several of the highest-value explanatory variables remain only partial.

### Interpretation
A score of 64 means:
- **ready to design**,
- **ready to define the state**,
- **ready to start carefully chosen early arrows**,
- but **not yet ready for broad, high-confidence mechanistic coverage**.

That is the correct state for Phase 6A. The goal of this phase is not completeness; it is scientific structure.

## 9. Final Recommendation
Proceed with Phase 6B only after the following are explicitly reviewed:
1. Version 1 State Vector definition approved,
2. data coverage matrix accepted,
3. major unknowns logged in `KNOWN_UNKNOWNS.md`,
4. first arrow criteria pre-registered before implementation.

The most important conceptual achievement of Phase 6A is this:

> The project is no longer asking how to predict payouts directly. It is defining what the NEM physically is at each interval, so that future predictions become applications of validated market physics rather than statistical shortcuts.
