# Market Intelligence v2 — Operating Charter

## Mission
Use the verified Digital Twin baseline to produce reliable, testable market intelligence.

## Core Loop (mandatory)
1. **Hypothesis**
2. **Evidence**
3. **Digital Twin test**
4. **Result**
5. **Keep or reject hypothesis**

No coding changes without a defined research objective tied to this loop.

## Separation of Sciences
- **Digital Twin (v1):** explanatory/reconstructive science (what happened).
- **Market Intelligence (v2):** inferential/predictive science (what will likely happen).

v2 must not alter v1 baseline mechanics.

## Research Quality Rules
- Point-in-time safety is required.
- Every test must define acceptance and rejection criteria before execution.
- Negative results are valid outcomes and must be recorded.
- Reproducibility is required for all reported findings.

## Implementation Gating
A code change is allowed only if all conditions hold:
- The associated hypothesis and test are documented in `docs/Research Journal.md`.
- Evidence shows measurable value beyond baseline.
- No breach of v1 architectural invariants.
- Change impact and rollback path are explicit.

## Initial v2 Focus Areas
- Congestion mechanism attribution.
- Directional spread persistence under regime changes.
- Auction behavior and clearing-price explainability.
- Capital-aware decision robustness.

## Definition of Progress
Progress is not line count.  
Progress is: higher-confidence hypotheses, better out-of-sample evidence, and tighter decision discipline.
