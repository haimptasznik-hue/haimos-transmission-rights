# Phase 6B.0 — Research Program Design

Status: **Design only**  
Scope: **Program architecture, mechanism catalogue, and experiment prioritisation**  
Constraint: **No code, no residual mining, no model tuning, no Market Physics Model changes**

## Purpose

`LAW_001` was rejected. That is a useful scientific result.

The next risk is not technical implementation. It is research drift.

Phase 6B.0 exists to prevent the program from jumping immediately from a rejected law to an unconstrained new hypothesis.

Instead, the project should first build a complete research program map:

- what physical mechanisms could influence congestion,
- which of them are observable,
- which of them are PIT-safe,
- which of them are commercially valuable,
- and which should be investigated first.

This phase is the research director layer.

It does not write the next law.
It decides how the next laws are chosen.

## Program Question

If data were unlimited, what are all the physically plausible mechanisms that could influence:

- interconnector flow,
- congestion,
- price separation,
- and settlement residue?

The goal is to build the backlog of scientifically valid candidate mechanisms before choosing the next law.

## Congestion Causality Tree

The program should be organised around a causality tree rather than around isolated predictors.

```text
Settlement Residue
    ↓
Price Separation
    ↓
Interconnector Flow
    ↓
Desired Transfer + Transmission Capability
    ↓
Regional Net Balance + Constraint System + Network Topology + Generator Behaviour + Battery Behaviour
    ↓
Demand + Generation + Weather + Fuel + Outages
```

### Interpretation

- **Desired transfer** is the flow the system would like to achieve from regional imbalance.
- **Transmission capability** is the physical limit on whether that transfer can actually occur.
- **Constraint system** decides whether the desired transfer is truncated, rerouted, or blocked.
- **Network topology** determines where transfer can physically go.
- **Generator and battery behaviour** determine how much local flexibility absorbs the imbalance before it becomes interconnector flow.
- **Demand, generation, weather, fuel, and outages** are the upstream drivers that shape the state.

This tree is the backbone of the next year of research.

## Research Philosophy

The project should not ask:

> Which variable gives the best fit?

It should ask:

> Which physical mechanism sits between imbalance and actual flow?

That distinction matters.

The first question invites overfitting.
The second question builds a physical research program.

## Mechanism Catalogue

The mechanism catalogue is the program backlog.

Each mechanism should be scored on:

- physical plausibility,
- expected causal strength,
- data availability,
- PIT safety,
- implementation effort,
- commercial value,
- and scientific priority.

### Scoring model

Use a simple 1–5 scale for each dimension:

- **Physical Plausibility** — does the mechanism match power-systems engineering?
- **Causal Strength** — how strongly could it change congestion or flow?
- **Data Availability** — is there an existing dataset or a feasible proxy?
- **PIT Safety** — can it be measured without leakage or hindsight?
- **Implementation Effort** — how hard is it to build the variable?
- **Commercial Value** — would the result matter for SRA, pricing, or valuation?
- **Scientific Priority** — does it meaningfully reduce uncertainty in the causal chain?

Suggested ranking rule:

$$
\text{Priority Score} = (\text{Plausibility} \times 2) + \text{Causal Strength} + \text{Data Availability} + \text{PIT Safety} + \text{Commercial Value} - \text{Implementation Effort}
$$

The formula is only a prioritisation aid.
It does not replace scientific judgment.

## Catalogue of Candidate Mechanisms

The list below is intentionally broad. It should be pruned by evidence, not by intuition.

### Tier 1 — corridor and network state

| Mechanism | Physical plausibility | Data exists? | PIT safe? | Difficulty | Commercial value | Why it matters |
|---|---|---|---|---|---|---|
| Interconnector available transfer capability | High | Partial | Yes if historical ratings exist | Medium | High | Sets the maximum flow the corridor can carry |
| Binding constraints | High | Partial | Yes if archived constraint outputs exist | High | High | Explains why flow is truncated or redirected |
| Constraint RHS margin | High | Partial | Yes if constraint equations are archived | High | High | Measures headroom to the binding boundary |
| Interconnector utilisation | High | Yes / partial | Yes | Low | High | Shows proximity to saturation |
| Planned outages / deratings | High | Partial | Yes if archived | Medium | High | Reduces capability independent of imbalance |
| Network topology / islanding state | High | Partial | Yes | High | High | Changes what physical transfers are possible |

### Tier 2 — supply-side flexibility

| Mechanism | Physical plausibility | Data exists? | PIT safe? | Difficulty | Commercial value | Why it matters |
|---|---|---|---|---|---|---|
| Generator outages | High | Partial | Yes | Medium | High | Reduces dispatchable capacity and transfer pressure |
| Thermal availability | High | Partial | Yes | Medium | High | Determines how much firm supply can respond |
| Battery dispatch | High | Partial | Yes | Medium | High | Absorbs or releases imbalance locally |
| Hydro dispatch / storage state | High | Partial | Partial | High | High | Strongly affects flexible response in NSW-linked states |
| Wind ramps | High | Yes / partial | Yes | Medium | High | Creates rapid net-load changes |
| Solar ramps | High | Yes / partial | Yes | Medium | Medium-High | Drives midday and shoulder-period transfer pressure |

### Tier 3 — market stress and ancillary mechanisms

| Mechanism | Physical plausibility | Data exists? | PIT safe? | Difficulty | Commercial value | Why it matters |
|---|---|---|---|---|---|---|
| FCAS enablement / scarcity | Medium-High | Yes / partial | Yes | High | Medium | Can distort normal dispatch relationships |
| Voltage constraints | High | Partial | Partial | High | Medium-High | Can cap transfer even when energy balance suggests otherwise |
| Frequency control stress | Medium | Partial | Yes | High | Medium | May correlate with stressed operating regimes |
| Security constraints / system strength | High | Partial | Partial | High | High | Can dominate corridor availability in stressed conditions |

### Tier 4 — upstream drivers

| Mechanism | Physical plausibility | Data exists? | PIT safe? | Difficulty | Commercial value | Why it matters |
|---|---|---|---|---|---|---|
| Regional demand | High | Yes | Yes | Low | High | Baseline transfer driver |
| Regional demand shape | High | Yes / partial | Yes | Low-Medium | Medium-High | Changes intraday transfer profile |
| Weather | High | Yes / external | Yes | Medium | Medium | Affects demand and renewable output |
| Temperature anomaly | High | Yes / external | Yes | Medium | Medium | Better than raw temperature for stress states |
| Fuel availability / fuel stress | Medium-High | Partial / external | Partial | High | Medium | Shapes dispatchable response |
| Industrial load shocks | Medium | Partial | Yes if available | High | Medium | Can shift regional imbalance abruptly |

## Initial Ranking Guidance

Without running any new statistics, the likely first-pass ranking should favour mechanisms that are:

1. physically direct,
2. observable in PIT-safe data,
3. commercially consequential,
4. and able to explain why imbalance does not always become flow.

That usually places the following near the top:

1. interconnector available transfer capability,
2. binding constraints,
3. generator outages,
4. wind generation / wind ramps,
5. regional demand imbalance,
6. interconnector utilisation,
7. planned outages / deratings,
8. battery dispatch.

This ranking should be treated as a starting hypothesis, not a conclusion.

## What the Catalogue Must Capture

For every mechanism, the catalogue should record:

- physical reasoning,
- required datasets,
- whether the dataset already exists,
- whether it is PIT safe,
- measurable variables,
- expected causal direction,
- confounding variables,
- boundary conditions,
- acceptance criteria,
- rejection criteria,
- implementation effort,
- commercial value,
- and scientific priority.

## Minimum Output of Phase 6B.0

The phase should end with three artefacts:

1. **Congestion Causality Tree** — the conceptual map of the mechanism chain.
2. **Mechanism Catalogue** — the ranked backlog of all physically plausible mechanisms.
3. **Research Roadmap** — the sequence of experiments to run next.

## Decision Rule for the Next Law

`LAW_002` should not be chosen because it sounds interesting.

It should be chosen because the catalogue says it has:

- high physical plausibility,
- high expected causal strength,
- strong commercial relevance,
- and acceptable data readiness.

That is how the program minimises research risk and maximises expected information gain.

## Deliverable Format

The final program design package should be short enough for quick review and detailed enough for execution.

Recommended layout:

- `MARKET_PHYSICS_RESEARCH_LOG.md` — operational command centre,
- `MARKET_PHYSICS_MANIFESTO.md` — research philosophy,
- `PHASE_6B_0_RESEARCH_PROGRAM_DESIGN.md` — mechanism catalogue and roadmap,
- `LAW_002_EXPERIMENT.md` — only after the catalogue has chosen the best next mechanism.

## Success Criteria

Phase 6B.0 succeeds if the next year of research is no longer driven by ad hoc intuition.

It should be driven by a ranked causal backlog.

That makes the project more scientific, more defensible, and more valuable.
