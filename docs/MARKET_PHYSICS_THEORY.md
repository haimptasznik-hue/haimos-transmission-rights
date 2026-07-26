# Market Physics Theory

**Version:** 0.1  
**Status:** Living theory document  
**Purpose:** Current understanding of how the NEM actually works, independent of any single experiment

## What This Document Is

This is the living textbook for the Market Physics Program.

It is **not**:

- an experiment specification,
- a project dashboard,
- a code artifact,
- or a log of all research activity.

It is the place where the project records its best current explanation of the National Electricity Market.

The theory will evolve as laws are accepted or rejected. Its job is to preserve the current model of reality, not the history of every test.

## Core Claim

Electricity prices are not driven directly by demand.

They emerge from the interaction of:

- regional imbalance,
- transmission capability,
- generator economics,
- constraint equations,
- dispatch optimisation,
- and market rules.

The key revision after `LAW_001` is that demand creates pressure, but not necessarily flow.

## Revised Causal Hierarchy

The current theory of the NEM is:

```text
Demand
    ↓
Desired Transfer
    ↓
Transmission State
    ↓
Actual Transfer
    ↓
Congestion
    ↓
Prices
```

### Why this hierarchy matters

The old intuition was:

```text
Demand → Flow → Congestion → Prices
```

That picture is too simple.

`LAW_001` showed that regional imbalance alone does not determine flow. The missing layer is transmission state: the corridor, its limits, its constraints, its topology, and the operating regime that mediates between desire and reality.

So the theory now says:

- demand creates pressure,
- imbalance creates a desired transfer,
- transmission state decides how much of that desire can become real flow,
- flow and limited capability create congestion,
- congestion and dispatch interaction create price separation,
- and price separation produces settlement residue.

## First Principles of the NEM

These are the current axioms of the theory.

### Axiom 1 — Power follows capability, not intention

Power flows according to network capability.

If the corridor cannot carry additional transfer, imbalance pressure does not magically become flow.

### Axiom 2 — Price separation requires limited transfer capacity

If transfer were unlimited, regional prices would tend to equalise more often.

Persistent price separation implies a bottleneck somewhere in the transfer path.

### Axiom 3 — Congestion requires competing dispatch

Congestion is not just high demand.

It appears when multiple regions or units compete for a limited network path or operating envelope.

### Axiom 4 — Settlement residue is a consequence, not a cause

Settlement residue arises from the interaction of flow, price separation, and market rules.

It does not drive the physical system.

### Axiom 5 — Regional imbalance creates pressure, not guaranteed flow

Imbalance creates a desired transfer.

Whether that desire becomes actual transfer depends on the transmission state.

### Axiom 6 — Dispatch optimisation is constrained optimisation

The market is not a free-response system.

Dispatch selects an outcome subject to physical limits, generator behaviour, constraints, and market rules.

### Axiom 7 — Market rules shape outcomes, but do not replace physics

Rules matter.

But they act on top of the physical network, not instead of it.

## Current Theory of the NEM

### Version 0.1 statement

The NEM is a constrained physical-economics system in which regional supply-demand imbalance creates a desire for transfer, but the realised interconnector flow is determined by transmission state.

That transmission state is formed by:

- capability,
- constraints,
- outages,
- topology,
- generator behaviour,
- battery behaviour,
- and dispatch optimisation.

Observed prices and residues are downstream expressions of that state.

## Current Confidence by Component

This is not a probability model. It is a qualitative confidence map for the current theory.

| Component | Current confidence | Reason |
|---|---:|---|
| Regional imbalance matters | ★★★★★ | Strongly supported by grid intuition and the structure of dispatch behaviour |
| Transmission capability matters | ★★★★☆ | Physically necessary for actual transfer; likely dominant in stressed regimes |
| Constraint equations matter | ★★★★☆ | Mechanistically important but still incomplete in current visibility |
| Actual transfer is distinct from desired transfer | ★★★★★ | Directly supported by the `LAW_001` rejection |
| Congestion mediates price separation | ★★★★☆ | Consistent with market design and observed regime behaviour |
| Battery behaviour matters | ★★☆☆☆ | Plausible and likely important, but not yet fully mapped |
| Generator bidding matters | ★★★☆☆ | Important for dispatch outcomes, but less directly visible than physics state |
| Market rules shape outcomes | ★★★★★ | Structural fact of the market design |
| Settlement residue is downstream | ★★★★★ | Settlement residue is a consequence of separation and flow, not an upstream driver |

## What We Currently Believe

### 1. Demand is not the full story

Demand is necessary to create transfer pressure, but it is not sufficient to explain actual interconnector flow or congestion.

### 2. The key missing variable is transmission state

Transmission state is the bridge between wanting power to move and power actually moving.

It includes:

- effective transfer capability,
- binding constraints,
- outage conditions,
- corridor utilisation,
- and topology.

### 3. Congestion is a state, not a single event

Congestion is not one thing.

It is a regime where transfer is limited, redirected, or truncated by the physical and market environment.

### 4. Prices are an emergent signal

Prices reflect the interaction of supply, demand, constraints, dispatch, and transfer capability.

They are informative, but they are not the causal root.

### 5. Settlement residue is a derivative outcome

Residue becomes meaningful only after the market has already produced price separation and constrained flow.

## What We Do Not Yet Know

The theory is still incomplete.

The biggest open questions are:

- which transmission-state variable dominates QNI in stressed regimes,
- how much of the gap between desired and actual transfer comes from constraints versus capability versus outages,
- how battery and generator behaviour reshape the state,
- and which boundary conditions make the current theory break.

These questions are the job of the research program.

## Theory to Research Link

The research program tests the theory one causal arrow at a time.

The current theory says:

```text
Demand
    ↓
Desired Transfer
    ↓
Transmission State
    ↓
Actual Transfer
    ↓
Congestion
    ↓
Prices
```

The research program then asks:

- which arrow is real,
- which arrow is conditional,
- which arrow is weak,
- and which arrow is missing.

That is why a rejected law is valuable: it updates the theory.

## Commercial Meaning

This theory matters because it connects physics to product value.

If the theory is right, then the same causal structure supports:

- SRA valuation,
- congestion forecasting,
- BESS dispatch optimisation,
- renewable project valuation,
- and future transmission planning applications.

The commercial advantage is not just prediction.

It is explanation.

## Versioning Rule

The theory document evolves slowly.

Update it when:

- a law is accepted,
- a law is rejected in a way that changes the causal picture,
- or a new boundary condition becomes central to the model.

Do not update it for every experiment detail.

That detail belongs in the research journal and experiment records.

## Relationship to Other Documents

- `docs/MARKET_PHYSICS_MANIFESTO.md` explains why the project exists.
- `docs/MARKET_PHYSICS_THEORY.md` explains how the NEM currently appears to work.
- `docs/MARKET_PHYSICS_RESEARCH_LOG.md` tracks program status and prioritisation.
- `docs/MARKET_PHYSICS_MODEL.md` records validated laws and rejected hypotheses.
- `docs/Research Journal.md` preserves the detailed scientific record.

## Current Working Summary

The project is no longer just asking how to trade SRAs.

It is building a physics-informed digital replica of the National Electricity Market capable of reasoning about future market states.

That is a larger system than a trader.

It is the theory layer for the entire platform.
