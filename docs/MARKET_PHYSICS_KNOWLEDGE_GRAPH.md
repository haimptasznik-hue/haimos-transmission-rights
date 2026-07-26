# Market Physics Knowledge Graph

**Version:** 1.0  
**Status:** Living knowledge structure  
**Purpose:** Machine-readable reasoning layer for the National Electricity Market

## What This Is

This document defines the first version of the HAIMOS Knowledge Graph.

It is **not** a graph database implementation.

It is a structured representation of the current understanding of the NEM so that the system can reason about market state, causal mechanisms, evidence, and commercial relevance without reading every markdown document manually.

The graph is the bridge between:

- the theory of how the NEM works,
- the research program that tests that theory,
- and the commercial products that use the results.

## Why It Exists

The project now has enough structure that further value comes from reasoning, not more framework documents.

The knowledge graph exists so the platform can answer questions such as:

- What are the most uncertain mechanisms affecting NSW→QLD congestion?
- Which missing dataset would reduce the most uncertainty?
- Which edge in the causal chain is weakest?
- Which law most strongly supports or weakens a given relationship?
- Which commercial application benefits most from understanding a mechanism?

## Graph Design Principles

1. **Physics first** — every edge must represent a physically meaningful relationship.
2. **Evidence attached** — every edge must point to the experiments that support or contradict it.
3. **Explicit status** — each edge must be labelled as observed, hypothesised, conditionally supported, validated, or rejected.
4. **Commercial awareness** — every relationship should note which products benefit from understanding it.
5. **PIT discipline** — edges must respect point-in-time availability and frozen-history rules.
6. **No speculative closure** — if evidence is weak, the graph must say so.

## Core Node Types

The graph should represent the NEM as linked concepts rather than isolated documents.

### Physical driver nodes

- `Regional Demand`
- `Weather`
- `Temperature Anomaly`
- `Wind Output`
- `Solar Output`
- `Generator Availability`
- `Battery Behaviour`
- `Hydro State`
- `Fuel Availability`
- `Outages`

### State nodes

- `Regional Imbalance`
- `Desired Transfer`
- `Transmission State`
- `Interconnector Capability`
- `Interconnector Utilisation`
- `Constraint State`
- `Network Topology`
- `Actual Flow`
- `Congestion`

### Market outcome nodes

- `Regional Price Separation`
- `Dispatch Prices`
- `Settlement Residue`
- `SRA Value`

### Program / evidence nodes

- `LAW_001`
- `LAW_002`
- `EXP_001`
- `EXP_002`
- `Known Unknown`
- `Boundary Condition`

### Commercial nodes

- `SRA Valuation`
- `Congestion Forecasting`
- `BESS Dispatch Optimisation`
- `Renewable Project Valuation`
- `Transmission Planning`

## Edge Model

Each edge should represent a directional relationship.

Example:

```text
Regional Demand → Regional Imbalance
```

Each edge record should store:

- `source_node`
- `target_node`
- `relationship_type`
- `status`
- `confidence`
- `supporting_experiments`
- `contradicting_experiments`
- `accepted_laws`
- `boundary_conditions`
- `known_unknowns`
- `commercial_relevance`
- `last_updated`

## Edge Status Taxonomy

Each edge must have one of the following states:

- **Observed** — directly measured and not materially disputed.
- **Hypothesised** — plausible, but not yet validated.
- **Conditionally Supported** — supported only under specific regimes or boundary conditions.
- **Validated** — repeatedly supported by pre-registered evidence.
- **Rejected** — evidence is contrary to the edge as a general claim.

## Version 1 Node Set

Version 1 should focus on the smallest graph that can support real reasoning about congestion and market outcomes.

### Required nodes

1. `Regional Demand`
2. `Regional Imbalance`
3. `Desired Transfer`
4. `Transmission State`
5. `Interconnector Capability`
6. `Constraint State`
7. `Actual Flow`
8. `Congestion`
9. `Regional Price Separation`
10. `Settlement Residue`
11. `SRA Value`

### Important supporting nodes

- `Generator Availability`
- `Wind Output`
- `Solar Output`
- `Battery Behaviour`
- `Outages`
- `Network Topology`
- `Dispatch Prices`
- `Market Rules`

## Version 1 Edge Set

The following edges are the first working theory of the NEM.

| Source | Target | Status | Confidence | Evidence |
|---|---|---|---:|---|
| Regional Demand | Regional Imbalance | Validated | 0.95 | Structural market logic; common dispatch behaviour |
| Regional Imbalance | Desired Transfer | Validated | 0.90 | Supported by theory and operational intuition |
| Desired Transfer | Transmission State | Conditionally Supported | 0.84 | `LAW_002` shows capability/headroom materially mediates the conversion, especially near limits |
| Transmission State | Actual Flow | Validated | 0.92 | Supported by `LAW_001` rejection and `LAW_002` near-limit capability lift |
| Actual Flow | Congestion | Validated | 0.86 | Congestion is a flow-limited state |
| Constraint State | Congestion | Validated | 0.89 | Binding constraints produce congestion regimes |
| Congestion | Regional Price Separation | Validated | 0.91 | Consistent with dispatch price formation |
| Regional Price Separation | Settlement Residue | Validated | 0.93 | Settlement residue is downstream of separation |
| Settlement Residue | SRA Value | Observed | 0.85 | Direct commercial linkage in the current platform |
| Interconnector Capability | Actual Flow | Validated | 0.92 | Strongest in stressed or near-limit regimes; `EXP_002` shows large near-limit explanatory lift |
| Generator Availability | Transmission State | Hypothesised | 0.77 | Affects how much transfer pressure survives locally |
| Wind Output | Regional Imbalance | Hypothesised | 0.78 | Alters net load and desired transfer pressure |
| Battery Behaviour | Regional Imbalance | Hypothesised | 0.70 | Can absorb or release imbalance locally |
| Outages | Interconnector Capability | Hypothesised | 0.82 | Reduces available transfer headroom |
| Network Topology | Transmission State | Validated | 0.90 | Physical routing constraint |
| Market Rules | Dispatch Prices | Validated | 0.93 | Rules affect dispatch outcome formation |

## Canonical Causal Chains

These are the core chains that the graph should preserve.

### Chain A — imbalance to flow

```text
Regional Demand
    ↓
Regional Imbalance
    ↓
Desired Transfer
    ↓
Transmission State
    ↓
Actual Flow
```

### Chain B — flow to residue

```text
Actual Flow
    ↓
Congestion
    ↓
Regional Price Separation
    ↓
Settlement Residue
    ↓
SRA Value
```

### Chain C — supply flexibility to imbalance

```text
Wind Output / Solar Output / Battery Behaviour / Generator Availability
    ↓
Regional Imbalance
```

## Example Edge Records

### Example 1 — `Transmission State → Actual Flow`

- **Status:** Validated
- **Confidence:** 0.88
- **Supporting experiments:** `EXP_001`
- **Contradicting experiments:** none yet as a general physical claim
- **Accepted laws:** `LAW_001` rejected as a direct law, which strengthens this mediated interpretation
- **Boundary conditions:** strongest in constrained or near-capacity corridors
- **Commercial relevance:** high for congestion forecasting, BESS dispatch, and SRA valuation

### Example 2 — `Constraint State → Congestion`

- **Status:** Validated
- **Confidence:** 0.89
- **Supporting experiments:** future `LAW_002` class work; current theory basis
- **Contradicting experiments:** none yet
- **Boundary conditions:** weaker where constraint observability is incomplete
- **Commercial relevance:** high

### Example 3 — `Regional Imbalance → Desired Transfer`

- **Status:** Conditionally Supported
- **Confidence:** 0.82
- **Supporting experiments:** `EXP_001` indicates imbalance matters, but not enough to explain flow alone
- **Contradicting experiments:** `EXP_001` rejected the direct jump from imbalance to flow
- **Boundary conditions:** transfer desire is a better concept than realised transfer
- **Commercial relevance:** high

## Evidence Attachment Rules

Every edge should cite evidence from one or more of the following:

- pre-registered law experiments,
- validated state-vector measurements,
- frozen Digital Twin replay outputs,
- or authoritative AEMO/market documentation where relevant.

If no evidence exists, the edge must remain hypothesised.

## Commercial Link Model

Each edge should have one or more downstream commercial associations.

Example:

- `Transmission State → Actual Flow` supports `SRA Valuation`, `Congestion Forecasting`, and `BESS Dispatch Optimisation`.
- `Settlement Residue → SRA Value` supports `SRA Valuation` directly.
- `Regional Demand → Regional Imbalance` supports `Renewable Project Valuation` and `Transmission Planning` indirectly.

This lets the platform answer not only what is true, but why it matters commercially.

## Uncertainty Handling

The graph should explicitly store uncertainty.

Uncertainty is not a defect; it is the point of the research program.

For each edge, maintain:

- confidence score,
- evidence count,
- contradiction count,
- boundary conditions,
- open unknowns,
- and last review date.

### Weakest-edge principle

The graph should be able to identify the weakest edge in a chain.

That makes it possible to ask:

- which relationship is least certain?
- which experiment would improve confidence the most?
- which missing dataset would reduce the most uncertainty?

## Expected Queries

The knowledge graph should answer questions like:

1. What are the three most uncertain mechanisms affecting NSW→QLD congestion?
2. Which missing dataset would reduce uncertainty the most?
3. Which laws support the `Transmission State → Actual Flow` edge?
4. Which edges are rejected, and what should replace them?
5. Which commercial product depends most heavily on a given edge?
6. Which boundary conditions make an edge stop holding?

## Update Rules

The graph should be updated when:

- a law is accepted,
- a law is rejected,
- a new boundary condition is found,
- a new dataset becomes available,
- or a contradiction is resolved.

It should **not** be updated casually after every experiment run.

The research journal remains the detailed history.
The knowledge graph remains the current causal state.

## Relationship to Other Documents

- `docs/MARKET_PHYSICS_MANIFESTO.md` explains why the project exists.
- `docs/MARKET_PHYSICS_THEORY.md` explains how the NEM currently works.
- `docs/MARKET_PHYSICS_RESEARCH_LOG.md` prioritises research work.
- `docs/PHASE_6B_0_RESEARCH_PROGRAM_DESIGN.md` defines the mechanism catalogue.
- `docs/MARKET_PHYSICS_MODEL.md` records validated laws and rejected hypotheses.
- `docs/Research Journal.md` preserves the detailed scientific trail.

## Practical Use

The knowledge graph is the operational representation of the theory.

It allows the system to move from text to machine reasoning:

- markdown explains the idea,
- the graph encodes the relationships,
- experiments change edge status,
- and commercial tools consume the current belief state.

That is the foundation of a market intelligence platform.
