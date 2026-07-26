# Research Cycle Brief — RC-001A: Knowledge Gap Prioritisation

**Cycle ID:** `RC-001A`  
**Status:** Proposed for approval  
**Type:** Planning cycle (no code, no experiment execution)  
**Date:** 2026-07-16

## 1) Objective

Identify the **single highest-value unknown** whose resolution would most improve understanding of congestion in the NSW↔QLD corridor and most improve the Knowledge Graph.

This cycle is a gate before `LAW_002`.

## 2) Decision Question

If we could ask one oracle question about the NEM to reduce uncertainty fastest, what should it be?

Candidate questions:

1. Does interconnector capability / transfer limit explain most of the `LAW_001` residual structure?
2. Do binding constraints explain most of the residual structure?
3. Do generator outages explain most of the residual structure?
4. Do wind/solar ramps explain most of the residual structure?
5. Does battery dispatch explain most of the residual structure?

## 3) Highest-Value Unknown (Current Recommendation)

**Leading unknown:** Transmission capability / effective transfer limit mediation.

### Why this is currently highest value

- It sits directly on the weakest edge in the current causal chain: `Desired Transfer → Actual Flow`.
- It is physically first-order and compatible with the `LAW_001` rejection finding.
- It has high commercial leverage across SRA valuation, congestion forecasting, and BESS dispatch.
- It appears to have higher near-term data readiness than full constraint-equation ingestion.

## 4) Prioritisation Table (RC-001A)

| Candidate mechanism | Physical plausibility | Data availability | Commercial impact | Estimated EIG | Effort | RC-001A rank |
|---|---|---|---|---:|---|---:|
| Transmission capability / transfer limits | Very High | High | Very High | 96 | Medium | 1 |
| Binding constraints | Very High | Medium | Very High | 90 | High | 2 |
| Generator outages | High | High | High | 78 | Medium | 3 |
| Wind & solar ramps | High | High | Medium | 62 | Medium | 4 |
| Battery dispatch | Medium | Medium | High | 58 | Medium-High | 5 |

## 5) Evidence Required to Resolve Top Unknown

To resolve whether transmission capability is the dominant mediator, we need evidence that:

1. Capability state explains a substantial part of the mismatch between desired transfer and actual flow.
2. The relationship remains directionally coherent across monthly and regime slices.
3. The effect is robust under key boundary conditions (high utilisation, outage periods, near-limit conditions).
4. The mechanism improves the relevant Knowledge Graph edge confidence without ad hoc threshold tuning.

## 6) Required Datasets

### Minimum set for top candidate

- `DISPATCHINTERCONNECTORRES` (already available)
- Interconnector capability / limit fields and historical ratings metadata
- Planned outage / derating metadata for the corridor
- Existing PIT-safe interval alignment artifacts from the frozen framework

### Optional but useful for stress tests

- Constraint activity indicators for boundary condition slicing
- Regional demand/generation context already used in `EXP_001`

## 7) Estimated Implementation Effort

If `LAW_002` is approved with capability focus:

- **Data assembly:** Medium (capability denominator and historical limit normalization)
- **Quality controls:** Medium (PIT checks, interval alignment, boundary flags)
- **Experiment execution:** Medium
- **Total cycle estimate:** ~1 focused research cycle

## 8) Expected Knowledge Graph Improvement

If uncertainty is reduced successfully:

- `Desired Transfer → Transmission State` confidence increases materially.
- `Transmission State → Actual Flow` moves from broad support to stronger quantified support.
- Fewer competing hypotheses remain at top priority, improving experiment sequencing quality.

## 9) Expected Commercial Capability Unlocks

If the top uncertainty is reduced, likely immediate gains are:

1. **SRA valuation:** Better corridor state priors under stressed transfer regimes.
2. **Congestion forecasting:** Stronger causal discrimination between pressure and realised flow.
3. **BESS dispatch:** Improved identification of intervals where local flexibility can substitute for constrained transfer.
4. **Portfolio risk:** Better scenario framing for transfer-limited spread events.

## 10) RC-001A Approval Decision

### Approve if:

- Leadership agrees transmission capability is the highest-EIG target.
- Required datasets are available at acceptable PIT quality.
- The cycle is scoped as one law + one experiment + one graph update.

### Do not approve yet if:

- Capability metadata quality is insufficient to support a credible test.
- Constraint data is found to be easier and clearly higher-EIG.
- Team cannot commit to no-threshold-tuning and frozen process discipline.

## 11) Recommended Next Step (Post-Approval)

If approved, proceed to **Research Cycle 001**:

- Author `LAW_002` focused on transmission capability mediation.
- Pre-register `EXP_002` acceptance/rejection criteria.
- Execute once with PIT-safe data.
- Update Knowledge Graph, Theory, and Commercial Impact sections from evidence only.

---

## RC-001A Outcome Template (to fill after review)

- **What did we learn?**
- **How much uncertainty did we remove?**
- **How much did Knowledge Graph confidence improve?**
- **What commercial capability did it unlock?**
