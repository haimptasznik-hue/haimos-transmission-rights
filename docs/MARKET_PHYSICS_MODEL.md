# Market Physics Model

**Purpose:** Single source of truth for all validated causal relationships in the NEM.

This is the equivalent of Maxwell's equations for electricity market price formation.

**Status:** Phase 6 research in progress  
**Baseline:** Digital Twin v1.0  
**Last Updated:** 2026-07-15

---

## Causal Hierarchy

```
Level 1 — Physical Drivers
├─ Temperature
├─ Wind output
├─ Solar output
├─ Coal availability
├─ Hydro availability
├─ Battery state of charge
├─ Interconnector status
└─ Generator constraints

         ↓ [Arrow: how do drivers set the grid state?]

Level 2 — Grid State (NEM State Vector)
│  The Digital Twin is primarily estimating this layer.
│  Physical drivers do not directly create market outcomes;
│  they first produce a measurable system state.
├─ Demand by region (MWh)
├─ Wind penetration % by region
├─ Solar penetration % by region
├─ Coal availability %
├─ Hydro availability %
├─ Battery state of charge estimate
├─ Gas availability %
├─ Interconnector utilisation %
├─ Constraint count
├─ Constraint severity
├─ Regional price spreads
├─ FCAS scarcity indicators
├─ Temperature anomaly (vs. seasonal norm)
└─ Outage score (MW off)

         ↓ [Arrow: how does grid state drive network physics?]

Level 3 — Network Physics
├─ Regional power flows (MW)
├─ Binding constraint equations
├─ Marginal generator by region
├─ Voltage stability indicators
└─ Flow reversal events

         ↓ [Arrow: how does network physics produce market outcomes?]

Level 4 — Market Outcomes
├─ Dispatch prices (AUD/MWh)
├─ Regional price separation
├─ IRSR (AUD per interval)
├─ SRA payouts (AUD per unit)
└─ Volatility regimes

         ↓ [Investment Decision]

Level 5 — Investment Decisions
├─ SRA portfolio construction
├─ Hedging strategies
├─ Capital allocation
└─ Risk management
```

### Why Grid State Is Its Own Layer

A 40°C day + low wind + coal outage does **not** directly create congestion.

They create a **state**:
- NSW demand deficit
- High QNI loading
- Battery discharging
- Gas setting the marginal price
- Constraint X5 binding

That state then produces price separation and settlement residues.

The Digital Twin's job is to reconstruct the state at each interval.
Physics laws describe how that state evolves into market outcomes.
Forecasting asks: given expected drivers, what state will the NEM be in?

---

## Entry Template

Every validated arrow follows this structure:

```
LAW [N]: [Arrow Name]
────────────────────────────────────────
Arrow: [Level N Driver] → [Level N+1 Outcome]

Physics:
[Plain-English description of the causal mechanism]

Confidence: [XX%]

Validated by:
- [ARROW_NNN experiment ID]
- [ARROW_MMM experiment ID]

Holds:
[Under what conditions is this arrow valid?]
- Which regions?
- Which time periods?
- Which seasons?

Breaks:
[Under what conditions does the arrow fail?]
- Interconnector outages?
- Extreme events?
- Alternative regimes?

Residual drivers:
[What's left unexplained? What percentage of variance?]

Quantification:
[Specific equations, R², correlation, effect size]

Notes:
[Any caveats or refinements]
```

## Research Numbering

The Phase 6 research program uses two numbering systems:

- **`LAW_###`**: the physical law or hypothesis being tested.
- **`EXP_###`**: the specific experiment used to test a law.

This separation matters because one law may require multiple experiments across:
- seasons,
- regions,
- operating regimes,
- and historical periods

before it is accepted or rejected.

## Auditability Rule

Once a law reaches **Accepted**, its originating experiment record is immutable.

If new evidence changes understanding:
- create a new experiment (e.g., `EXP_007`) and/or
- create a law revision entry (e.g., `LAW_001-R2`),

without editing the historical accepted record.

This preserves full scientific lineage and prevents retrospective confirmation bias edits.

---

## Validated Laws (Phase 6 Results)

[To be populated as arrows are tested and validated]

### LAW_001: Regional Supply-Demand Imbalance Drives Interconnector Power Flow
**Status:** Rejected by `EXP_001` (2026-07-16)

**Evidence:**
- `EXP_001` produced `R² = 0.872068` but failed directional accuracy at `0.797667` against the pre-registered threshold of `> 0.90`.
- Correlation was negative (`Pearson = -0.812097`, `Spearman = -0.794645`), and the stability slices were not robust.

**Interpretation:**
- Regional supply-demand imbalance alone does not survive as the dominant QNI flow law under the pre-registered test contract.
- Follow-up work should test constraint state / network physics as candidate dominant drivers.

### LAW_002: Interconnector Capability Constrains Transfer Conversion
**Status:** Conditionally Accepted by `EXP_002` (2026-07-23)

**Evidence:**
- Primary sample size: `26,362` rows with `12` differing intervention rows excluded.
- Baseline imbalance-only model: `R² = 0.056287`.
- Capability/state model: `R² = 0.359864`.
- Incremental explanatory lift: `ΔR² = 0.303577`.
- Near-limit regime: `R² = 0.601758`, `ΔR² = 0.535119`.
- Directional accuracy: `0.797989`.
- Monthly directional stability: `true`.

**Interpretation:**
- Interconnector capability, utilisation, and transfer-capability margin explain a meaningful share of the residual structure left after regional imbalance is accounted for.
- The effect is strongest near corridor limits, which is the expected transmission-physics boundary condition.
- Detailed constraint and outage records remain the next unresolved layer.

### LAW_002: [Reserved]
**Status:** Not yet scheduled

### LAW_003: [Reserved]
**Status:** Not yet scheduled

---

## Experiment Tracking

| Law ID | Experiment ID | Level | From | To | Status | Next Step |
|--------|---------------|-------|------|-----|--------|-----------|
| LAW_001 | EXP_001 | 2→3 | Regional supply-demand imbalance | Interconnector power flow | In Design | Scientific experiment contract approved |
| LAW_002 | EXP_002 | 2→3 | Grid state | Interconnector capability / utilisation | Conditionally Accepted | `EXP_002` |
| LAW_003 | – | 3→4 | Constraint state | Regional price separation | Not Started | Queue |
| LAW_004 | – | 3→4 | Price separation + flow | Settlement residue | Not Started | Queue |
| LAW_005 | – | 1→2 | Temperature anomaly | Regional demand | Not Started | Queue |

---

## Decision Rules for Law Acceptance

### Accepted
- Acceptance criteria met (pre-registered thresholds).
- Effect size is meaningful (R² > 0.5 or ρ > 0.6).
- Holds across multiple subsamples (regions, seasons, hours).
- No evidence of spurious causation.

→ **Decision:** Include in Market Physics Model with high confidence (>80%).

### Conditionally Accepted
- Acceptance criteria partially met.
- Effect holds in some conditions but not others.
- Boundary conditions are clear and documented.

→ **Decision:** Include with conditional confidence (60–80%); specify boundary conditions precisely.

### Rejected
- Acceptance criteria not met.
- Effect size is weak or inconsistent.
- Contradicts other validated arrows.

→ **Decision:** Reject law; record why in experiment report. Update alternative hypothesis list.

### Inconclusive
- Evidence is mixed or insufficient.
- Data readiness gaps prevent reliable adjudication.
- Additional experiments are required before acceptance/rejection.

→ **Decision:** keep law open; schedule follow-up `EXP_###` runs.

---

## Research Quality Rules

✅ **Every arrow experiment must:**
1. Pre-register acceptance/rejection criteria before running code.
2. Use only Point-in-Time-safe data (no future information).
3. Test generalizability across subsamples.
4. Identify boundary conditions and residual drivers.
5. Report effect size and uncertainty.
6. Document confounding variables and controls.

❌ **Arrows cannot:**
1. Rely on fitted/tuned parameters from the same test sample.
2. Use realised settlement values (post-quarter) in state estimation.
3. Change Digital Twin logic to "make the arrow work."
4. Assume correlation is causation without mechanism evidence.

---

## Expected Outcomes (Phase 6, Week 10)

- A validated set of laws and experiments across Levels 1 → 2 → 3 → 4.
- NEM State Vector defined and at least partially populated from C2024Q4 data.
- Causal graph showing how physical state produces market outcomes.
- Confidence levels and boundary conditions documented for every arrow.
- Each accepted LAW demonstrably reduces unexplained variance and is reproducible across historical periods.
- KNOWN_UNKNOWNS.md populated with open questions and residual drivers.
- Roadmap for Layer 5 forecasting (application of physics laws to estimated future state).

---

## Integration with Digital Twin (Layer 3)

The Market Physics Model is **explanatory**: it answers "why did this happen?"

The Digital Twin is **reconstructive**: it answers "what actually happened?"

When an arrow is validated, it means:
- The Digital Twin correctly reproduced the causal chain.
- We now understand the mechanism that produced the observed market outcomes.
- We can apply this mechanism to forecast future outcomes (subject to forecasting error on the input state).

**No arrow can contradict a Digital Twin result.** If it does, the arrow is incomplete or incorrect.

---

## Forecasting Application (Layer 5, Future)

Once State Vector definition is complete and 5+ arrows are validated:

```
Estimate future physical drivers (Level 1: temp, wind, solar, etc.)
         ↓
Apply Physics Laws → estimate future Grid State (Level 2)
         ↓
Apply Physics Laws → predict Network Physics (Level 3)
         ↓
Apply Physics Laws → predict Market Outcomes (Level 4)
         ↓
Investment Decision (Level 5)
```

Forecasting is not prediction. It is **state estimation applied forward in time**.

**Direct forecasting (fragile):** Temperature → Price (one-step, misses mechanism, easy to overfit).

**Physics-based state estimation (robust):** Estimate Grid State(t+1) from known drivers → apply validated arrows to derive outcomes. Each arrow has been independently validated; the composite is mechanistically grounded.

---

## Version History

| Date | Status | Summary |
|------|--------|---------|
| 2026-07-15 | Initiated | Template created; Phase 6 research begins |
| – | – | – |

---

## Questions for the Chief Market Physicist

**Q: How do I know which arrow to test next?**  
A: Prioritize by impact on the causal chain. Level 1→2 arrows first (they feed everything downstream). Within Level 1→2, prioritize high-variance drivers (temperature, wind, demand patterns) over rare events (outages).

**Q: What if two arrows contradict each other?**  
A: Re-examine both experiments. Check for:
- PIT safety violations (did you use future data?).
- Sample selection bias (did you test on a representative sample?).
- Confounding variables (is there a third arrow affecting both?).
Fix the experiment or update the mechanism.

**Q: Can I use statistical ML (e.g., random forests) to test arrows?**  
A: Yes, but only for evidence gathering. Use it to rank drivers (feature importance). Then design a mechanistic arrow experiment to validate the top drivers. ML can suggest hypotheses; only causal experiments can validate them.

**Q: When is the model "complete"?**  
A: A physics model is never "complete" — but it is sufficient when every accepted LAW materially reduces unexplained variance *and* remains reproducible across historical periods. That's a stronger standard than any single R² target. Temperature might explain 18%, wind 24%, hydro 8%: none of those individually "passes" a 75% threshold, but together you've discovered something extremely valuable. Judge each law on its own scientific merit.

**Q: What if residual drivers are >20%?**  
A: Means the model is incomplete — which is expected and honest. Either:
- You're missing an important Level 1 or Level 2 variable (add it to `docs/KNOWN_UNKNOWNS.md`).
- The physics varies by regime (e.g., different causal chains in summer vs. winter).
- There is genuine irreducible uncertainty you cannot capture.
Document and continue digging. A well-characterised 30% residual is more valuable than an over-fitted 5% residual.

