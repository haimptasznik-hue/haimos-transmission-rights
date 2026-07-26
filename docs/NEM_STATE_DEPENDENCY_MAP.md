# NEM State Dependency Map

Status: **Phase 6A design artifact**  
Purpose: document the currently understood dependency structure of the NEM state ontology  
Scope: **scientific design only; not a forecasting model**

## Purpose
This document maps how physical drivers influence the NEM, how those influences first appear in the **Market State Ontology / State Vector**, and how they propagate through network physics into market outcomes and investment consequences.

The dependency map is not a fully validated causal graph yet.

It is a research scaffold with three edge classes:
- **Understood:** mechanism is physically plausible and already supported by domain knowledge.
- **Partially understood:** mechanism likely exists but is not yet cleanly quantified.
- **Unknown:** relationship is plausible but not yet evidenced or data-ready.

## Layer Structure

```text
Level 1 — Physical Drivers
        ↓
Level 2 — Grid State / Market State Ontology
        ↓
Level 3 — Network Physics
        ↓
Level 4 — Market Outcomes
        ↓
Level 5 — Investment Decisions
```

## Canonical Chain

```text
Temperature
    ↓
Regional Demand
    ↓
Generator Dispatch Mix
    ↓
Interconnector Flow
    ↓
Constraint Binding
    ↓
Regional Price Separation
    ↓
Settlement Residues
    ↓
SRA Value
```

This chain is the simplest useful backbone of Phase 6 research. The full NEM dependency structure is richer and branches in multiple directions.

## Dependency Conventions
- `A → B` means A is believed to influence B.
- `[U]` = Understood
- `[P]` = Partially understood
- `[X]` = Unknown / unresolved
- `STATE` marks relationships that terminate in the Grid State layer.

## Dependency Map by Group

### 1. Weather and Exogenous Environment

```text
Temperature anomaly → Regional demand                              [U]
Temperature anomaly → Rooftop/self-generation net load effect      [P]
Wind speed / wind resource → Utility-scale wind output             [U]
Solar irradiance → Utility-scale solar output                      [U]
Solar irradiance → Net operational demand                          [U]
Storm / extreme weather → Network outage risk                      [P]
Extreme heat → Generator derating / outage risk                    [P]
```

**Commentary**
- Temperature is a high-confidence driver of demand, but its region-specific form is still unresolved.
- Wind and solar relationships are physically strong, but data access for historical unit-level reconstruction is not yet fully verified.
- Extreme-weather impacts on outages are plausible but not yet formalized in current research assets.

### 2. Supply Adequacy and Generator Availability

```text
Coal outage MW → Coal availability %                               [U]
Gas outage MW → Gas availability %                                 [P]
Hydro storage / water value → Hydro availability %                 [P]
Battery SOC / dispatch constraints → Battery dispatch flexibility   [P]
Fuel availability → Regional generation capacity margin            [U]
Generation capacity margin → Marginal fuel type                    [P]
```

**Commentary**
- Coal availability is likely one of the most important missing explanatory variables.
- Hydro remains a major unresolved residual driver for NSW spikes.
- Battery flexibility likely matters in some regions/corridors but remains an open question.

### 3. Physical Drivers → Grid State

These are the critical Phase 6A and 6B dependencies.

```text
Temperature → Demand by region                                     [U] STATE
Business day / holiday → Demand by region                          [U] STATE
Wind output → Wind penetration %                                   [U] STATE
Solar output → Solar penetration %                                 [U] STATE
Coal availability → Coal availability % state variable             [U] STATE
Gas availability → Gas availability % state variable               [P] STATE
Hydro availability → Hydro availability % state variable           [P] STATE
Battery dispatch → Battery dispatch MW                             [P] STATE
Network outages → Interconnector derating %                        [P] STATE
Outages (gen + network) → Outage score                             [P] STATE
Regional demand & supply → Demand imbalance score                  [U] STATE
Constraint activity → Constraint count / severity                  [P] STATE
FCAS price components → FCAS scarcity indicators                   [P] STATE
```

**Commentary**
- This section defines how external reality enters the state representation.
- A major Phase 6A goal is to make these mappings explicit even when data is incomplete.

### 4. Grid State Internal Dependencies

```text
Demand by region + generation by region → Regional demand deficit  [U]
Wind penetration + solar penetration → Net load                    [U]
Coal availability + gas availability + hydro availability
    → Dispatchable capacity margin                                 [P]
Dispatchable capacity margin + demand deficit
    → Price-setting stress                                          [P]
Interconnector utilisation + outage score
    → Constraint severity                                           [P]
Constraint count + severity + utilisation
    → Network stress regime                                         [P]
```

**Commentary**
- The Grid State layer should not be treated as a bag of unrelated features.
- State variables influence one another and may be grouped into regime descriptors.

### 5. Grid State → Network Physics

```text
Regional demand imbalance score → Interconnector flow requirement  [U]
Interconnector derating % → Utilisation %                          [U]
Interconnector utilisation % → Flow reversal risk                  [P]
Constraint severity score → Binding constraint equations           [P]
Dispatchable capacity margin → Marginal generator by region        [P]
Network stress regime → Voltage stability indicators               [X]
Battery dispatch MW → QNI / corridor utilisation                   [X]
```

**Commentary**
- This is the heart of the market-physics program: state should explain network behavior.
- Some relationships are strongly intuitive but not yet evidenced in this repository.
- `Battery dispatch → corridor utilisation` remains a known unknown.

### 6. Network Physics → Market Outcomes

```text
Binding constraints → Regional price separation                    [U]
Marginal generator by region → Dispatch price                      [U]
Interconnector flow at limit → Price separation                    [U]
Price separation + flow → IRSR                                     [U]
Constraint binding pattern → IRSR volatility regime                [P]
FCAS scarcity + network stress → Energy price dislocation          [P]
```

**Commentary**
- This section is closest to the verified Digital Twin and should be high-priority for later validation.
- `Price separation + flow → IRSR` is already structurally central to settlement outcomes.

### 7. Market Outcomes → Investment Layer

```text
IRSR expectations → SRA fair value                                 [U]
SRA payout uncertainty → Risk-adjusted value                       [P]
Price volatility regime → Position sizing                          [P]
Constraint-driven residue pattern → Corridor selection             [P]
```

**Commentary**
- These dependencies are downstream and explicitly out of scope for Phase 6A implementation.
- They remain in the map so the research program preserves end-to-end coherence.

## Unknown or Explicitly Unresolved Dependencies

The following relationships are important enough to name, but not yet mature enough to treat as understood:

| Relationship | Status | Why unresolved | Likely source of resolution |
|---|---|---|---|
| Battery dispatch → QNI utilisation | Unknown | Need unit-level battery dispatch and corridor attribution | `DISPATCH_UNIT_SCADA`, future arrow |
| Hydro storage → NSW spike suppression | Partial | Storage state not presently modeled | Hydro storage data + dispatch analysis |
| FCAS scarcity → regional energy spread regime | Partial | FCAS interaction exists but not yet isolated | `DISPATCHPRICE` FCAS decomposition |
| Temperature anomaly → demand residual vs raw temperature | Partial | Better construct likely exists but untested | BOM normals + ARROW_001 variant |
| Industrial load proxy → QLD demand behavior | Unknown | QLD likely differs from southern states | External industrial proxy + QLD subgroup study |
| Constraint severity score → IRSR magnitude | Partial | Need robust severity measure and binding IDs | `DISPATCHCONSTRAINT` |
| Network outages → effective transfer capability | Partial | Outage/capability mapping not yet standardized | Network outage sources + capability metadata |
| Marginal fuel type → price spike amplitude | Partial | Requires bid stack / unit mapping discipline | Bid/dispatch analysis |

## Research Priorities Implied by the Dependency Map

### Priority 1 — Establish the Grid State ontology
Without a stable Grid State layer, arrow experiments jump directly from drivers to prices and blur mechanism.

### Priority 2 — Resolve data gaps on dispatchable supply
Coal, gas, hydro, and battery state variables are likely among the highest-value missing components.

### Priority 3 — Formalize constraint-state relationships
Constraint count, severity, and QNI-specific binding flags are likely essential bridges between state and market outcomes.

### Priority 4 — Separate energy and FCAS regimes
Some price outcomes may not be explained by energy state alone.

## Dependency Map Summary
The current best understanding of the NEM is not:

```text
Weather → Price
```

It is:

```text
Physical Drivers
    ↓
Grid State
    ↓
Network Physics
    ↓
Market Outcomes
```

That distinction matters because the Digital Twin is fundamentally reconstructing **state**, not merely outcomes.

The job of the Market Physics Research Program is to convert this map from plausible structure into validated scientific law, one dependency at a time.
