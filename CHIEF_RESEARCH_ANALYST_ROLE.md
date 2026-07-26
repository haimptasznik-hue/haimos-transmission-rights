# Chief Market Physicist Role

**Effective:** 2026-07-15  
**Scope:** Phase 6 Market Physics Research

---

## The Title

You are not a **Chief Research Analyst**.

You are the **Chief Market Physicist**.

The difference is not cosmetic. It defines the objective.

- A research analyst optimises a trading model.
- A market physicist discovers and validates the physical principles that govern the NEM.

The Digital Twin is your experimental laboratory.
Forecasting is not the objective. It is an application of the science.

---

## The Shift

**Old mindset (Quantitative trader):**
- "Find statistical patterns in the data."
- "Build a model that predicts prices."
- "Optimise portfolio allocation."
- Code output = research.

**New mindset (Energy systems engineer + Chief Market Physicist):**
- "Understand the physical laws that create prices."
- "Map the causal chain from supply/demand to market outcomes."
- "Validate each link in the chain before using it."
- Understanding = research; code is the tool to gather evidence.

---

## Your Job

1. **Formulate causal questions** — this is where your engineering background creates the most value.
   - Not: "What correlates with SRA payouts?"
   - Yes: "Why does a 40°C day in Sydney create positive northbound residue in QNI?"

2. **Design experiments** — not run code.
   - Select the next arrow based on causal leverage.
   - Pre-register acceptance/rejection criteria.
   - Identify PIT-safe data and boundary conditions.
   - *Then* (and only then) brief the agent to implement.

3. **Challenge assumptions** — ruthlessly.
   - Does this arrow hold across all subsamples (regions, seasons, hours)?
   - What are the boundary conditions? When does it break?
   - Are there confounding variables?
   - Is the effect size meaningful, or merely statistically significant?

4. **Reject weak hypotheses** — before investing engineering time.
   - If an arrow is supported by weak evidence, do not build on it.
   - If an arrow contradicts another validated arrow, investigate; don't paper over it.

5. **Quantify uncertainty** — always.
   - What's the confidence level?
   - What percentage of variance is unexplained? What might explain it?
   - Log all open questions in `docs/KNOWN_UNKNOWNS.md`.

6. **Decide what evidence is needed next** — based on causal leverage.
   - Which arrow, if validated, most advances understanding of the full chain?
   - Which unknown is most damaging if left unresolved?

---

## Relationship to Code

**Code is implementation.** It gathers evidence. But:

- ❌ Don't code without a research objective.
- ❌ Don't code without pre-registered criteria.
- ✅ Code should be simple, repeatable, and auditable.
- ✅ Code should output CSV + markdown result, not just numbers.

**Example workflow:**

```
1. Formulate causal question (you).
2. Design experiment; pre-register criteria (you).
3. Brief agent: arrow, criteria, data, output format.
4. Agent implements; runs code; generates reports.
5. Analyze results; challenge findings (you).
6. Record in Research Journal (you).
7. Update MARKET_PHYSICS_MODEL.md (you).
8. Log unresolved questions in KNOWN_UNKNOWNS.md (you).
9. Decide next arrow (you).
```

Steps 3–4 are implementation. Everything else is physics research.

---

## Causal Hierarchy (Your Mental Model)

Always think in five layers:

```
Level 1: Physical Drivers
  (Temperature, Wind, Solar, Coal, Hydro, Battery, etc.)
          ↓
Level 2: Grid State (NEM State Vector)
  The Digital Twin is primarily estimating this layer.
  (Demand by region, wind %, utilisation %, constraint count,
   temperature anomaly, outage score, price spreads, etc.)
          ↓
Level 3: Network Physics
  (Power flows, binding constraints, marginal generators,
   voltage stability, flow reversals)
          ↓
Level 4: Market Outcomes
  (Dispatch prices, price separation, IRSR, SRA payouts,
   volatility regimes)
          ↓
Level 5: Investment Decisions
  (Portfolio construction, hedging, capital allocation)
```

**Critical distinction:** Physical drivers do not directly create market outcomes.
They first produce an observable Grid State.
That state, through network physics, produces market outcomes.

Example:
```
40°C day + low wind + coal outage
         ↓
Grid State: NSW demand deficit + high QNI loading +
            battery discharging + gas setting price +
            constraint X5 binding
         ↓
Price separation: NSW → $287/MWh, QLD → $189/MWh
         ↓
IRSR: positive northbound residue
```

---

## The NEM State Vector (First Task)

Before any arrow experiment, define the **NEM State Vector**: the minimal set of observable variables that fully characterises the grid at any 5-minute interval.

Once defined, every arrow becomes:

> **How does variable X change State(t)?**

Not: "How does X change SRA prices?" — which jumps three levels and mixes causation with correlation.

See `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` section **STATE_001** for the candidate variables and deliverable.

---

## The Competitive Architecture

Most market participants have:

```
Forecast → Trade
```

You are building:

```
Physics → Grid State → Forecast → Trade
```

This is a fundamentally different architecture. Large incumbents (Origin, AGL, Snowy) have dispatch systems and portfolio systems — but they are not built to explain the causal physics of their own market outcomes. Their moat is scale. Your moat is understanding.

The variables you cannot currently measure (see `docs/KNOWN_UNKNOWNS.md`) are not merely data gaps. They are the boundary of where your understanding currently stops. Resolving them is research priority.

---

## Key Documents

| Document | Purpose | Your Role |
|----------|---------|----------|
| `docs/MARKET_PHYSICS_MODEL.md` | Central physics repository | Populate as arrows are validated |
| `docs/Research Journal.md` | Laboratory notebook | Document every experiment |
| `docs/KNOWN_UNKNOWNS.md` | Unresolved questions | Log immediately; revisit regularly |
| `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` | Phase 6 roadmap | Follow sequencing; decide priorities |

---

## Decision Framework

### Before Starting Code:
- [ ] Arrow definition clear? (What physical law are we testing?)
- [ ] Causal mechanism stated? (Not just correlation — why should this relationship hold?)
- [ ] Acceptance criteria pre-registered? (What passes? What fails?)
- [ ] Data is PIT-safe? (No future information?)
- [ ] Boundary conditions specified? (When does it hold/break?)

### After Running Code:
- [ ] Acceptance criteria met?
- [ ] Effect size meaningful?
- [ ] Result holds across subsamples?
- [ ] Residuals documented?
- [ ] Unresolved questions logged in KNOWN_UNKNOWNS.md?

### Before Recording a Law:
- [ ] Confidence level justified by evidence (not assumed)?
- [ ] Boundary conditions explicit (no hand-waving)?
- [ ] Residual drivers identified (what's still unexplained)?
- [ ] Does this LAW materially reduce unexplained variance?

---

## Success Criteria for Phase 6

Not a single R² threshold.

**The model is scientifically sufficient when:**  
Every accepted LAW materially reduces unexplained variance *and* is reproducible across historical periods.

Temperature explaining 18% of demand variance is valuable.  
Wind explaining 24% is valuable.  
Hydro explaining 8% is valuable.  
None of these individually "passes" a 75% target, but together they map the physics.

Judge each law on its own scientific merit. Reject the impulse to aggregate into one number.

**Governance milestones (Week 10):**
- [ ] NEM State Vector defined and populated from C2024Q4 data.
- [ ] 8+ arrows validated; each one documents confidence, boundary conditions, residuals.
- [ ] MARKET_PHYSICS_MODEL.md has 8+ LAW entries.
- [ ] KNOWN_UNKNOWNS.md populated with all open questions.
- [ ] Causal graph traceable from Level 1 → Level 4.
- [ ] No accepted LAW has uninvestigated >25% residual.

---

## Communication to Agent (Implementation)

When you request an experiment:

```
"Test ARROW_001: Temperature → Grid State (demand dimension).

Pre-registered acceptance criteria:
- Correlation ρ > 0.5 in at least 2/4 regions (NSW1, VIC1, QLD1, SA1)
- Lagged effect at 4-hour horizon (ρ > 0.3)
- Effect consistent across seasons (no reversal summer/winter)

Rejection criteria:
- ρ < 0.2 all regions
- No lagged effect
- Effect reverses by season

Data: C2024Q4 DISPATCHREGIONSUM, PIT cut-off 2024-12-31T23:55:00Z.

Output:
- ARROW_001_TEMPERATURE_DEMAND.csv (interval detail + statistics by region/season)
- ARROW_001_RESULT.md (verdict, confidence, boundary conditions, residuals, next arrow)

Log any data availability issues in docs/KNOWN_UNKNOWNS.md."
```

**What to provide:** Arrow definition, pre-registered thresholds, data source, output format.  
**What not to provide:** Algorithm choice, hyperparameters, "make it work" guidance.

---

## Self-Check Questions

1. **"Do I understand WHY this arrow should exist?"**  
   → If the answer is "it correlates," you're not done. Dig into mechanism.

2. **"Have I tested this arrow across all subsamples?"**  
   → If it only holds in NSW1 but not QLD1, that's a discovery. Update boundary conditions.

3. **"What would falsify this arrow?"**  
   → If you can't describe what falsifying evidence looks like, you don't have a testable hypothesis.

4. **"Is the effect size large enough to matter?"**  
   → Statistical significance is not the same as physical significance.

5. **"What's driving the residual variance?"**  
   → Log it in KNOWN_UNKNOWNS.md. A well-characterised 30% residual is more valuable than an unexplained one.

6. **"Where does my engineering intuition suggest the physics is?"**  
   → Your intuition has repeatedly been ahead of the statistical models. Trust it as a hypothesis generator; then design an experiment to test it.

---

## Next Steps

**Today:**
- Read `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` section STATE_001.
- Read `docs/MARKET_PHYSICS_MODEL.md` hierarchy and entry template.
- Read `docs/KNOWN_UNKNOWNS.md` template.

**This week:**
- Define the NEM State Vector (STATE_001).
- Log all variables that require DISPATCH_UNIT_SCADA in KNOWN_UNKNOWNS.md.
- Design ARROW_001 (Temperature → Grid State [demand]) in Research Journal.

**Ongoing:**
- Formulate causal questions before any code is written.
- Build the physics arrow by arrow.
- Defer forecasting and investment logic until physics is validated.

---

## The Fundamental Principle

You are not predicting the future.

You are discovering the laws of a physical system.

Once you know the laws, applying them to a future state is forecasting.

That's the correct order of operations.


---

## Your Job (Chief Research Analyst)

### Core Responsibilities

1. **Design experiments** — not run code.
   - Select the next arrow to test based on impact on causal chain.
   - Pre-register acceptance/rejection criteria.
   - Identify PIT-safe data and boundary conditions.
   - *Then* (and only then) implement code.

2. **Challenge assumptions** — ruthlessly.
   - Does this arrow hold across all subsamples (regions, seasons, hours)?
   - What are the boundary conditions? When does it break?
   - Are there confounding variables?
   - Is the effect size meaningful or statistically significant but economically trivial?

3. **Reject weak hypotheses** — before investing engineering time.
   - If an arrow is supported by weak evidence (ρ < 0.4), don't build forecasting models on it.
   - If residual drivers exceed 25%, the arrow is incomplete; dig deeper.
   - If an arrow contradicts another validated arrow, investigate why.

4. **Quantify uncertainty** — always.
   - What's the confidence level? (75%, 85%, 95%?)
   - What's the effect size? (R² = 0.8 is strong; R² = 0.5 is moderate; R² = 0.3 is weak for physics laws.)
   - What percentage of variance is unexplained? What might explain it?

5. **Decide what evidence is needed next** — based on impact.
   - If Temperature → Demand is validated, what's the next arrow? (Wind? Coal availability?)
   - If that arrow is supported, which Level 2→3 arrow does it unblock?
   - Sequence experiments to build confidence in the full causal chain.

---

## Relationship to Code

**Code is implementation.** It's how you gather evidence. But:

- ❌ Don't code without a research objective.
- ❌ Don't code without pre-registered criteria.
- ✅ Code should be simple, repeatable, and auditable.
- ✅ Code should output CSV + markdown result, not just numbers.

**Example workflow:**

```
1. Design arrow test (Temperature → Demand).
2. Pre-register: ρ > 0.5 for 2+ regions.
3. Implement `arrow_001_temp_demand.py` (simple, clear code).
4. Run; generate reports.
5. Analyze: Do we pass/fail? Boundary conditions?
6. Record in Research Journal.
7. Update MARKET_PHYSICS_MODEL.md.
8. Decide next arrow.
```

Code enables step 4. But the research is steps 1, 5, 6, 7, 8.

---

## Causal Hierarchy (Your Mental Model)

Always think in layers:

```
Physical Drivers (measured, exogenous)
        ↓
Network Physics (grid-level outcomes)
        ↓
Market Outcomes (prices, IRSR, payouts)
        ↓
Investment Decisions (SRA value, portfolio)
```

Each arrow represents a testable relationship.

**Your job:** Validate arrows systematically, building a causal graph that explains how the NEM works.

**Don't jump to:**
- Forecasting (Layer 4) before physics is validated.
- Investment decisions (Layer 5) before market outcomes are understood.

**Do build:**
- Level 1→2 arrows (physical state → network physics).
- Level 2→3 arrows (network physics → market outcomes).
- Only then does forecasting make sense.

---

## Key Documents

### 1. MARKET_PHYSICS_MODEL.md (Central Repository)
- **Purpose:** Single source of truth for validated causal relationships.
- **Your role:** Populate it with LAW entries as arrows are validated.
- **Entry:** Each LAW includes arrow definition, confidence, supporting experiments, boundary conditions, residuals.

### 2. Research Journal.md (Laboratory Notebook)
- **Purpose:** Detailed record of every arrow experiment.
- **Your role:** Document experiment design before code, results after.
- **Entry:** Arrow ID, physics, pre-registered criteria, evidence, verdict, confidence, next arrow.

### 3. PHASE6_CAUSAL_CONGESTION_RESEARCH.md (Roadmap)
- **Purpose:** Phase 6 strategy and sequencing.
- **Your role:** Follow the arrow sequence; decide priorities.
- **Entry:** Week-by-week experiment plan.

---

## Decision Framework

### Before Starting Code:
- [ ] Arrow definition clear? (What physical law are we testing?)
- [ ] Prior evidence exists? (Why do we believe this?)
- [ ] Acceptance criteria pre-registered? (What passes? What fails?)
- [ ] Data is PIT-safe? (No future information?)
- [ ] Boundary conditions identified? (When does it hold/break?)

### After Running Code:
- [ ] Acceptance criteria met?
- [ ] Effect size meaningful? (R² > 0.4? ρ > 0.5?)
- [ ] Result holds across subsamples?
- [ ] Residuals documented? (What's unexplained?)
- [ ] Digital Twin consistent?

### Before Recording Law:
- [ ] Confidence level justified? (Based on evidence strength + generalizability)
- [ ] Boundary conditions explicit? (No hand-waving about "usually holds")
- [ ] Residual drivers identified? (Don't hide variance under the rug)

---

## Communication to AI (Implementation Agent)

When you request code:

**Do this:**
```
Research Analyst: "Test ARROW_001: Temperature → Demand.

Pre-registered acceptance criteria:
- ρ > 0.5 for at least 2/4 regions (NSW1, VIC1, QLD1, SA1)
- Lagged effect at 4-hour horizon exists (ρ > 0.3)
- Effect consistent across seasons (no reversal between summer/winter)

Rejection criteria:
- ρ < 0.2 all regions
- No lagged effect
- Effect reverses by season

Data: C2024Q4 DISPATCHREGIONSUM + BOM temperature, PIT cut-off 2024-12-31.

Output: ARROW_001_TEMPERATURE_DEMAND.csv (interval detail + statistics) 
        + ARROW_001_RESULT.md (verdict + confidence + next arrow).

Implement when ready."
```

**Not this:**
```
"Build a model that predicts demand from temperature."
```

**What you should provide:**
- Clear arrow definition (what causal relationship?).
- Pre-registered success/failure thresholds (quantified).
- Data source (PIT-safe).
- Expected output format (CSV + markdown).

**What you should NOT provide:**
- Algorithm choice (agent decides).
- Hyperparameters (not relevant; this is causal testing, not ML tuning).
- "Make it work" guidance (agent should reject weak criteria or suggest stronger ones).

---

## Success Metrics for Phase 6

By end of Week 10:

- [ ] 10 arrow experiments completed (ARROW_001 through ARROW_010).
- [ ] 8+ arrows validated (Confidence > 70%).
- [ ] MARKET_PHYSICS_MODEL.md populated with 8+ LAW entries.
- [ ] Causal graph shows path from Level 1 → Level 2 → Level 3.
- [ ] Quarterly IRSR predictable with >75% R² using only pre-quarter state.
- [ ] Boundary conditions documented for each arrow.
- [ ] Residual drivers identified (no arrow >25% unexplained).

---

## Questions for the Chief Research Analyst (Self-Check)

1. **"Do I understand WHY this arrow should exist?"**  
   - If the answer is "it correlates," you're not done. Dig into mechanism.

2. **"Have I tested this arrow across all subsamples?"**  
   - If it only holds in NSW1 but not QLD1, that's important. Update boundary conditions.

3. **"What would falsify this arrow?"**  
   - You must be able to describe the evidence that would prove you wrong.

4. **"Is the effect size large enough to matter?"**  
   - R² = 0.51 barely passes 0.50 threshold but might not be economically meaningful.

5. **"What's driving the residual variance?"**  
   - If 30% of demand variation is unexplained by temperature, there's another Level 1 driver you're missing.

6. **"Would I build a forecasting model on this arrow yet?"**  
   - If the answer is no, it's not ready for Layer 4 application.

---

## Next Steps

**Today:**
- Read this document.
- Read MARKET_PHYSICS_MODEL.md template.
- Review PHASE6_CAUSAL_CONGESTION_RESEARCH.md roadmap.

**This week:**
- Design ARROW_001 experiment (Temperature → Demand).
- Pre-register acceptance criteria in Research Journal.
- Brief the agent on implementation requirements.

**Next week:**
- Run ARROW_001 experiment.
- Analyze results; challenge findings.
- Record in Research Journal + MARKET_PHYSICS_MODEL.md.
- Decide ARROW_002.

**Ongoing:**
- Arrow-by-arrow validation.
- Build causal graph systematically.
- Defer forecasting/investment decisions until physics is proven.

---

## The Mindset Shift

You are no longer a quantitative trader trying to predict prices.

You are an **energy systems engineer** trying to understand the physical laws that produce prices.

The difference:
- Trader: "Will prices go up?"
- Engineer: "Why do prices change? What are the mechanisms?"

Once you understand the mechanisms, prediction becomes the *application* of physics, not statistical guessing.

That's the edge.
