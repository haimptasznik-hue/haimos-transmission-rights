# HAIMOS Phase 6 — Market Physics Research

**Launch Date:** 2026-07-15  
**Status:** Ready for Chief Research Analyst  
**Baseline:** `digital-twin-v1.0` (frozen, verified against AEMO C2024Q4)  

---

## The Strategic Shift

You are transitioning from **quantitative trader** to **Chief Research Analyst**.

Your job is no longer to predict prices. Your job is to understand the **physical laws** that create prices.

**Why?** Because understanding provides the edge. Prediction without understanding over-fits. Physics-based prediction is robust.

---

## Your Five Essential Documents

### 1. **PHASE6_QUICK_START.md** ← START HERE (10 min)
- This week's action items (2.5 hours of work)
- What you do vs. what the agent does
- First arrow experiment (ARROW_001) overview

### 2. **CHIEF_RESEARCH_ANALYST_ROLE.md** (20 min)
- Complete job description
- How you work with the implementation agent
- Mindset shift from trader to engineer
- Decision framework

### 3. **PHASE6_CAUSAL_CONGESTION_RESEARCH.md** (Reference)
- Full Phase 6 roadmap
- Causal hierarchy (4 levels of drivers → outcomes)
- Arrow-by-arrow experiment template
- Example: Temperature → Demand (with pre-registered criteria)
- 10-week sequencing plan

### 4. **docs/MARKET_PHYSICS_MODEL.md** (You populate)
- Central repository for validated causal laws
- Template for recording each arrow
- Entry format: Arrow definition, confidence, evidence, boundary conditions, residuals
- Your output: 8+ LAW entries by week 10

### 5. **docs/Research Journal.md** (You write)
- Laboratory notebook for every arrow experiment
- Pre-registration template (criteria BEFORE code)
- 9-section arrow entry format
- Index table of all experiments

---

## The Causal Hierarchy (Your Mental Model)

```
Level 1: Physical Drivers
├─ Temperature ─┐
├─ Wind output ─┤
├─ Solar output┤
├─ Coal avail. ├─→ Level 2: Network Physics ─┐
├─ Hydro avail.┤ ├─ Power flows            ├─→ Level 3: Market Outcomes
├─ Battery ────┤ ├─ Congestion             │   ├─ Prices
├─ Interco.────┤ ├─ Price separation   ────┤   ├─ IRSR
└─ Gen. const. ┘ └─ Marginal generators ───┘   ├─ Residues
                                                └─ SRA payouts
                                                        ↓
                                            Level 4: Investment Decisions
                                            (ONLY after physics validated)
```

Each → is a testable arrow.

Each arrow = one experiment.

---

## Phase 6 in 10 Weeks

| Week | Arrow | Level | From | To | Status |
|------|-------|-------|------|-----|--------|
| 1–2 | ARROW_001 | 1→2 | Temperature | Demand | Design this week |
| 1–2 | ARROW_002 | 1→2 | Wind | Dispatch | Queue |
| 3–4 | ARROW_003 | 1→2 | Coal | Fuel mix | Queue |
| 3–4 | ARROW_004 | 1→2 | Economy | Demand | Queue |
| 5–8 | ARROW_006–009 | 2→3 | Util / Imbalance / Binding / Price | Market Outcomes | Queue |
| 9–10 | ARROW_010 | Full | Temperature→...→IRSR | Composite | Queue |

**Week 10 Outcome:** 10 validated arrows; ~8 added to MARKET_PHYSICS_MODEL.md; quarterly IRSR >75% predictable.

---

## The Research Cycle (Per Arrow, 3 Days)

### Day 1: Design (You as Chief Research Analyst)
- [ ] Define arrow: what causal relationship?
- [ ] Pre-register acceptance criteria (e.g., ρ > 0.5, not "high correlation").
- [ ] Specify rejection criteria (e.g., ρ < 0.2, effect reversal).
- [ ] Identify PIT-safe data and boundary conditions.
- [ ] Brief implementation agent.

### Day 2: Implement & Run (Agent as Coder)
- [ ] Load data; compute metrics.
- [ ] No tuning, no optimization—just validation.
- [ ] Output: CSV + markdown result.

### Day 3: Analyze & Record (You as Chief Research Analyst)
- [ ] Challenge result: Generalize across regions/seasons/hours?
- [ ] Identify boundary conditions and residuals.
- [ ] Record in Research Journal (full 9-section template).
- [ ] Add LAW to MARKET_PHYSICS_MODEL.md.
- [ ] Select next arrow.

---

## Key Rules for Phase 6

✅ **MUST DO:**
- Pre-register criteria BEFORE code
- Use PIT-safe data (no future information)
- Test across subsamples
- Document boundary conditions explicitly
- Quantify uncertainty (confidence, residuals)

❌ **NEVER:**
- Change Digital Twin logic (Layer 3 frozen)
- Assume correlation = causation
- Build Layer 4 (forecasting) before physics validated
- Cherry-pick thresholds after results
- Hide unexplained variance

---

## How to Talk to the Implementation Agent

**You design. Agent implements.**

```
"Test ARROW_001: Temperature → Regional Demand

Pre-registered acceptance:
- Correlation ρ > 0.5 for ≥2 regions (NSW1, VIC1, QLD1, SA1)
- Lagged effect at 4-hour horizon
- Consistent across seasons

Rejection criteria:
- ρ < 0.2 all regions
- No lagged effect
- Effect reverses by season

Data: C2024Q4 DISPATCHREGIONSUM + temperature (PIT cut-off 2024-12-31)

Output:
- ARROW_001_TEMPERATURE_DEMAND.csv
- ARROW_001_RESULT.md (verdict + effect sizes + confidence)"
```

Agent returns data. You analyze and decide.

---

## Success Metrics (Week 10)

- [ ] 10 arrows tested
- [ ] 8+ arrows validated (confidence > 70%)
- [ ] MARKET_PHYSICS_MODEL.md has 8+ LAW entries
- [ ] Quarterly IRSR predictable >75% R² (pre-quarter state only)
- [ ] All boundary conditions documented
- [ ] All residuals <25% per arrow
- [ ] Research Journal complete

When criteria met: **Ready for Layer 4 Forecasting Implementation**

---

## Getting Started This Week

1. **Read PHASE6_QUICK_START.md** (10 min)
2. **Read CHIEF_RESEARCH_ANALYST_ROLE.md** (20 min)
3. **Review ARROW_001 example** in PHASE6_CAUSAL_CONGESTION_RESEARCH.md (15 min)
4. **Design ARROW_001** in docs/Research Journal.md (30 min)
   - Pre-register criteria
   - Identify data sources
   - Specify boundary conditions
5. **Brief agent** on implementation (10 min)
6. **Run & analyze** (agent handles code)
7. **Record in MARKET_PHYSICS_MODEL.md** (30 min)

**Total:** ~2 hours of research work

---

## Documents You'll Use Weekly

| Document | Use | Frequency |
|----------|-----|-----------|
| PHASE6_QUICK_START.md | Reference for weekly tasks | Weekly |
| CHIEF_RESEARCH_ANALYST_ROLE.md | Remind yourself of your role | As needed |
| docs/Research Journal.md | Log every arrow experiment | After each arrow |
| docs/MARKET_PHYSICS_MODEL.md | Record validated laws | After each arrow |
| PHASE6_CAUSAL_CONGESTION_RESEARCH.md | Reference methodology | As needed |

---

## The Mindset

You are no longer a **quant building a model**.

You are an **energy systems engineer** discovering the laws of the NEM.

The difference:
- Quant: "Fit a function that predicts prices"
- Engineer: "Why do prices change? What is the mechanism?"

Once you understand mechanism, prediction becomes application of physics.

That's sustainable edge.

---

## Questions?

**Q: Do I need to code?**  
A: No. Agent handles all code. You design experiments and challenge results.

**Q: When do I forecast?**  
A: After 5+ Level 1→2 and 3+ Level 2→3 arrows validated. Then forecasting = apply physics to predicted physical state.

**Q: What if an arrow fails?**  
A: Document why. Move to next arrow. Failed arrows teach what's NOT the mechanism.

**Q: Is this worth the time?**  
A: Yes. You're building scientific credibility. "The SRA value follows this physical law with 92% confidence" > "Our model predicts..."

---

## Next Steps

→ Read **PHASE6_QUICK_START.md**  
→ Then read **CHIEF_RESEARCH_ANALYST_ROLE.md**  
→ Then design **ARROW_001** in docs/Research Journal.md  
→ Then brief the agent

You are now the Chief Research Analyst for HAIMOS Market Physics Engine.

Welcome to Phase 6.
