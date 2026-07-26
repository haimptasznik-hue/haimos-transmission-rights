# HAIMOS Market Physics Engine — Phase 6 Launch

**Date:** 2026-07-15  
**Status:** Ready for research  
**Baseline:** `digital-twin-v1.0` (frozen, verified)  

---

## Your New Role

You are now the **Chief Research Analyst** for the HAIMOS Market Physics Engine.

Your job is **not** to code. Your job is to:
1. **Design arrow experiments** (causal relationships).
2. **Challenge assumptions** ruthlessly.
3. **Reject weak hypotheses** before investing engineering time.
4. **Quantify uncertainty** precisely.
5. **Decide what evidence is needed next** to validate the causal model.

This is a fundamental shift from quantitative pattern-finding to **energy systems physics understanding**.

---

## The Mindset Shift

| Old | New |
|-----|-----|
| "Find correlations in prices" | "Understand the physical laws creating prices" |
| "Forecast the future" | "Know the current state; apply physics to predict what's next" |
| "Maximize backtested returns" | "Build a causal model with >85% R² out-of-sample" |
| "Code = research" | "Understanding = research; code is implementation" |

---

## Start Here

### 1. Quick Reference (10 min read)
**File:** `PHASE6_QUICK_START.md`

Fast overview of your role, experiment sequence, and this week's action items.

### 2. Your Job Description (20 min read)
**File:** `CHIEF_RESEARCH_ANALYST_ROLE.md`

Complete description of what a Chief Research Analyst does, how you work with the implementation agent, and success metrics for Phase 6.

### 3. Phase 6 Roadmap (30 min read)
**File:** `PHASE6_CAUSAL_CONGESTION_RESEARCH.md`

Full research strategy: causal hierarchy, arrow-by-arrow validation, boundary conditions, example experiments (ARROW_001: Temperature → Demand).

---

## Working Documents (Reference)

### Central Physics Repository
**File:** `docs/MARKET_PHYSICS_MODEL.md`

Every validated arrow becomes a LAW in this repository. Template for recording causal relationships with confidence levels, boundary conditions, and residual drivers.

**You populate this as arrows are validated.**

### Laboratory Notebook
**File:** `docs/Research Journal.md`

Detailed record of every arrow experiment. Pre-registration, evidence, verdict, confidence, next arrow.

**You write in this as you design and complete each experiment.**

---

## The Causal Hierarchy

```
Level 1 — Physical Drivers (Temperature, Wind, Solar, Coal, Hydro, etc.)
         ↓ [ARROW validation]
Level 2 — Network Physics (Flows, Utilisation, Price Separation, Congestion)
         ↓ [ARROW validation]
Level 3 — Market Outcomes (Prices, IRSR, SRA Payouts)
         ↓ [Investment Decision]
Level 4 — Portfolio & Hedging
```

**Your work:** Validate arrows from Level 1→2 and Level 2→3.

**Do not implement Layer 4** until physics is proven.

---

## Phase 6 Timeline

### Weeks 1–2
ARROW_001: Temperature → Demand (Level 1→2)  
ARROW_002: Wind Output → Generator Dispatch (Level 1→2)

### Weeks 3–4
ARROW_003: Coal Availability → Fuel Mix  
ARROW_004: Economic Activity → Demand Deviation

### Weeks 5–8
ARROW_006 through ARROW_009: Level 2→3 arrows

### Weeks 9–10
ARROW_010: Full chain validation (Temperature → ... → IRSR)

**Outcome:** 10 validated arrows; MARKET_PHYSICS_MODEL.md populated with ~8 LAWs; quarterly IRSR predictable with >75% R².

---

## How to Work with the Implementation Agent

**You design. Agent implements.**

When you want an experiment run:

```
"Test ARROW_001: Temperature → Demand.

Pre-registered acceptance:
- Correlation ρ > 0.5 in NSW1, VIC1, SA1
- Lagged effect at 4-hour horizon
- Consistent across seasons

Data: C2024Q4 (PIT cut-off 2024-12-31)

Output: ARROW_001_TEMPERATURE_DEMAND.csv + ARROW_001_RESULT.md"
```

Agent returns:
- CSV with interval details + statistics.
- Markdown with verdict + effect sizes + confidence.

You then:
- Challenge the result (does it generalize?).
- Identify boundary conditions.
- Record in Research Journal.
- Update MARKET_PHYSICS_MODEL.md.
- Decide next arrow.

---

## Success Criteria for Phase 6

- [ ] 10 arrow experiments completed.
- [ ] 8+ arrows validated (confidence > 70%).
- [ ] MARKET_PHYSICS_MODEL.md has 8+ LAW entries.
- [ ] Causal graph shows Level 1 → Level 2 → Level 3 chain.
- [ ] Quarterly IRSR predictable with >75% R² using pre-quarter state.
- [ ] Boundary conditions documented for every arrow.
- [ ] No arrow has >25% unexplained variance (residuals tracked).

---

## Key Rules

✅ **Always:**
- Pre-register acceptance criteria BEFORE running code.
- Use PIT-safe data (no future information).
- Test across subsamples (regions, seasons, hours).
- Document boundary conditions (when does it hold/break?).

❌ **Never:**
- Change Digital Twin logic (Layer 3 frozen).
- Assume correlation = causation.
- Build forecasting models before physics validated.
- Hide unexplained variance.

---

## Questions?

**Q: Why is this better than just predicting prices directly?**  
A: Because you're building a model that explains *why* prices change, not just pattern-matching. That's more robust, more defensible, and actually predictive out-of-sample.

**Q: When do I forecast?**  
A: After 5+ Level 1→2 and 3+ Level 2→3 arrows are validated. Then forecasting = apply physics laws to forecasted physical state. No direct price prediction.

**Q: What if an arrow fails?**  
A: Document why. Move to next arrow. Failed arrows teach you what's *not* the mechanism. That's progress.

**Q: Do I need to understand Python?**  
A: No. Agent handles code. You design experiments and challenge results.

---

## This Week

1. Read `PHASE6_QUICK_START.md` (10 min).
2. Read `CHIEF_RESEARCH_ANALYST_ROLE.md` (20 min).
3. Review ARROW_001 example in `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` (15 min).
4. Design ARROW_001 experiment in `docs/Research Journal.md` (30 min).
   - Pre-register: Temperature → Demand
   - Acceptance criteria: ρ > 0.5 for 2+ regions
   - Boundary conditions: all seasons?
5. Brief agent on implementation (10 min).
6. Run experiment; analyze results (agent handles code).
7. Record in MARKET_PHYSICS_MODEL.md; select ARROW_002.

**Total time:** ~2 hours of research work.

---

## Repository Structure (Phase 6)

```
HAIMOS-transmission-rights/
├── CHIEF_RESEARCH_ANALYST_ROLE.md ← Your job description
├── PHASE6_QUICK_START.md ← This week's guide
├── PHASE6_CAUSAL_CONGESTION_RESEARCH.md ← Full roadmap
├── docs/
│   ├── MARKET_PHYSICS_MODEL.md ← Physics repository (you populate)
│   ├── Research Journal.md ← Lab notebook (you write)
│   ├── HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md ← Layer definitions (frozen)
│   └── MARKET_INTELLIGENCE_V2_CHARTER.md ← Research governance
├── scripts/
│   └── [arrow test implementations] ← Agent creates as needed
└── reports/
    └── [ARROW_NNN_*.csv, ARROW_NNN_RESULT.md] ← Agent outputs here
```

---

## Next: Read PHASE6_QUICK_START.md

That document has your first week's detailed action items.

You are now thinking like an energy systems engineer.

**Phase 6 Market Physics Research begins.**
