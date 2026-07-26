# LAW_002 Experiment Specification

Status: **Pre-registered residual investigation**  
Law ID: `LAW_002`  
Phase: **Phase 6B — Market Physics Research**  
Implementation scope: **No code, no statistical residual mining, no model tuning, no Market Physics Model changes**

## Purpose

`LAW_001` was rejected. That is a scientific success, not a failure.

This experiment does **not** attempt to invent a new predictive model from the residuals. Its purpose is narrower and more disciplined:

> identify which physical transmission mechanisms prevent regional supply-demand imbalance from becoming actual interconnector flow.

The question is not “what residual fits best?”
The question is “what physical state limits the transfer?”

## Research Question

Why couldn’t the power flow where the imbalance wanted it to go?

More formally:

> Given regional imbalance-driven desired transfer, which transmission-state variables explain the gap between desired transfer and observed flow?

## Proposed Law

`LAW_002` is a mechanism hypothesis, not a curve-fit:

> Regional supply-demand imbalance creates desired interconnector transfer. Actual transfer is determined by transmission capability and network state.

This is intentionally different from `LAW_001`.

- `LAW_001` asked whether imbalance explains flow.
- `LAW_002` asks what prevents imbalance from becoming flow.

## Physical Interpretation

The causal chain under investigation is:

```text
Regional imbalance
    ↓
Desired transfer
    ↓
Transmission capability / network state
    ↓
Actual transfer
    ↓
Constraint binding
    ↓
Price separation
    ↓
Settlement residue
```

`LAW_002` is focused on the middle of that chain.

It treats the residual from `LAW_001` as a signal that transmission capability, constraints, or outages are intervening between imbalance and realized flow.

## Core Objective

Determine which physical transmission variables best explain the remaining structure after regional imbalance has already been accounted for.

The outcome should be a ranked shortlist of mechanisms, not a fitted predictive model.

## Candidate Mechanisms

### Tier 1 — Highest Priority

1. **Interconnector available transfer capability**
   - Physical reasoning: if the corridor is near its effective transfer limit, imbalance can create desired flow without producing actual flow.
   - Expected role: primary limiter of the imbalance-to-flow conversion.
   - Research priority: highest.

2. **Binding constraints**
   - Physical reasoning: network constraints can truncate, redirect, or cap the flow implied by regional imbalance.
   - Expected role: direct blocker of desired transfer.
   - Research priority: highest.

3. **Constraint RHS margin**
   - Physical reasoning: the margin between the current operating point and the constraint boundary indicates how much additional transfer is physically possible.
   - Expected role: quantitative proxy for headroom.
   - Research priority: highest.

4. **Interconnector utilisation**
   - Physical reasoning: high utilisation indicates proximity to transfer saturation and therefore reduced responsiveness to further imbalance.
   - Expected role: observable saturation indicator.
   - Research priority: highest.

5. **Planned outages / deratings**
   - Physical reasoning: maintenance or derating reduces available capability regardless of imbalance pressure.
   - Expected role: structural capacity reducer.
   - Research priority: highest.

### Tier 2 — Secondary Priority

6. **Generator outages**
   - Physical reasoning: local loss of dispatchable supply changes the transfer requirement and may alter how much flow is practically achievable.
   - Expected role: local capacity shock and boundary-condition modifier.

7. **Battery dispatch**
   - Physical reasoning: batteries can absorb or release energy locally, reducing or amplifying transfer pressure.
   - Expected role: fast local balancing mechanism.

8. **Renewable variability**
   - Physical reasoning: wind and solar volatility can change desired transfer faster than corridor capability adapts.
   - Expected role: short-interval driver of transfer pressure.

### Tier 3 — Contextual / Exogenous

9. **Weather**
   - Physical reasoning: weather affects both load and renewable output, which can shift transfer demand indirectly.

10. **Fuel availability / fuel stress**
   - Physical reasoning: fuel constraints can alter dispatchable generation and hence change transfer demand.

11. **Hydro state**
   - Physical reasoning: hydro dispatch can absorb or relieve regional imbalance depending on water and operational strategy.

## Dataset Requirements

This experiment should only use datasets that are physically justified and PIT-safe for the chosen historical window.

| Mechanism | Required datasets | Already exists? | Notes |
|---|---|---:|---|
| Interconnector capability | `DISPATCHINTERCONNECTORRES`, interconnector definition / ratings, outage or derating records | Partial | Some fields exist; capability state may require additional mapping |
| Binding constraints | `DISPATCHCONSTRAINT` or equivalent constraint outputs | Unknown / partial | Needed to identify whether flow was capped by network state |
| Constraint RHS margin | Constraint equations / RHS time series | Unknown | May require derived or external constraint metadata |
| Interconnector utilisation | `DISPATCHINTERCONNECTORRES`, capability / limit reference | Partial | Can be derived once transfer limit is known |
| Planned outages / deratings | outage schedules / corridor availability | Unknown / partial | May need separate AEMO or asset records |
| Generator outages | dispatchable unit status / outage records | Partial | Higher resolution than regional generation aggregates |
| Battery dispatch | `DISPATCH_UNIT_SCADA` or equivalent dispatchable unit data | Unknown / partial | Requires unit-level aggregation by technology |
| Renewable variability | `DISPATCH_UNIT_SCADA`, renewable unit mappings | Unknown / partial | Requires unit-level wind / solar identification |
| Weather | BOM or equivalent external source | External | Contextual, not primary |
| Fuel / hydro | external or operational datasets | External / partial | Contextual, not primary |

## Measurable Variables

### Desired transfer proxy

The experiment should retain the imbalance-based desire term from `LAW_001` as a baseline reference.

Candidate forms:
- regional net balance difference,
- signed imbalance pressure toward the corridor,
- normalized imbalance per regional demand.

### Actual transfer

- observed interconnector `MWFLOW`.

### Transmission-state variables

- available transfer capability,
- effective corridor limit,
- utilisation ratio,
- binding constraint indicator,
- constraint margin / RHS headroom,
- outage flag,
- derating flag.

### Context variables

- generator outage state,
- battery dispatch proxy,
- renewable dispatch variability,
- weather context,
- fuel / hydro context where available.

## Expected Causal Direction

The expected direction of influence is not “more of everything increases flow.”

The physical expectation is:

- more imbalance increases desired transfer,
- lower transfer capability reduces actual transfer,
- binding constraints reduce or redirect transfer,
- higher utilisation indicates less remaining headroom,
- outages and deratings reduce the conversion of desired transfer into actual flow,
- local flexibility resources can absorb imbalance before it reaches the interconnector.

## Confounding Variables

These must be treated as confounders or boundary conditions, not as excuses to retune the hypothesis:

- sign-convention errors,
- interval misalignment,
- boundary rows across month joins,
- saturation effects from corridor limits,
- simultaneous constraint and outage conditions,
- local flexibility masking transfer pressure,
- coarse regional aggregates hiding unit-level scarcity,
- seasonality that is actually an artefact of network state.

## Boundary Conditions

`LAW_002` should be expected to hold most strongly when:

- the corridor is near but not fully saturated,
- constraint and outage states are observable,
- transfer capability can be measured or reliably proxied,
- local flexibility does not entirely absorb imbalance,
- interval alignment remains PIT-safe and exact.

The law may weaken when:

- transfer capability is missing or unobservable,
- constraints are not captured in the available data,
- the corridor is fully islanded or nearly islanded,
- local flexibility dominates the transfer response,
- only coarse regional aggregates are available.

## Acceptance Criteria

This experiment should be accepted as a valid mechanism investigation if it meets all of the following:

1. **Mechanism clarity:** the ranked shortlist distinguishes capability / constraint variables from purely demand-side variables.
2. **Physical interpretability:** the leading variables have a clear transmission-physics explanation.
3. **Data adequacy:** the needed datasets are available or can be built without modifying the frozen Digital Twin.
4. **Directional coherence:** the candidate mechanisms consistently point in the expected physical direction.
5. **Implementation feasibility:** the top-ranked mechanism(s) can be measured without speculative model construction.

## Rejection Criteria

This experiment should be rejected as a useful scientific path if:

1. the proposed mechanisms are not physically distinct,
2. the required data cannot be obtained at acceptable quality,
3. the investigation collapses back into simple residual fitting,
4. the main explanatory variables are only statistical artefacts with no operational meaning,
5. the design requires changing thresholds or redefining `LAW_001` after the fact.

## Ranking Method

Rank candidate mechanisms by:

1. **Physical plausibility** — does the mechanism match power-systems engineering intuition?
2. **Expected explanatory power** — does it plausibly explain the mismatch between desired and actual transfer?
3. **Data availability** — can the variable be measured or proxied with existing PIT-safe data?
4. **Implementation effort** — how difficult is it to assemble a reliable variable?
5. **Commercial value** — would the mechanism materially improve corridor valuation, congestion awareness, or operational interpretation?

## Expected Research Outcome

The deliverable from `EXP_002` should be:

- a ranked mechanism list,
- a dataset readiness assessment,
- a clear recommendation for the next experiment,
- and a narrower understanding of the physics preventing imbalance from becoming flow.

It should **not** be a new trading model.
It should **not** be a threshold-tuned restatement of `LAW_001`.
It should **not** be a statistical rescue of a rejected law.

## Commercial Implication

If `LAW_002` is supported, the likely value is stronger than a generic predictive lift:

- better congestion-state interpretation,
- better corridor-capability awareness,
- better price-separation intuition,
- better product valuation under network stress,
- better explanation of why imbalance does not always become flow.

If `LAW_002` is not supported, that still narrows the research space and improves the next physical hypothesis.
