# Phase 6: Quick Start Guide

**Your role:** Chief Market Physicist (Energy Systems Engineer)  
**Your job:** Discover and validate the physical laws that govern the NEM  
**Your laboratory:** Digital Twin v1.0 (frozen, verified against C2024Q4)  
**Your timeline:** 10 weeks of systematic law and experiment design  

---

## Three Essential Documents

### 1. CHIEF_RESEARCH_ANALYST_ROLE.md
**Read first.** This is your job description.
- What you do (design experiments, challenge assumptions, reject weak hypotheses).
- How you work with the implementation agent.
- Success metrics for Phase 6.

### 2. MARKET_PHYSICS_MODEL.md
**Your output repository.** Every validated arrow becomes a LAW.
- Template for recording causal relationships.
- Tracks confidence level and evidence.
- Central reference for all validated physics.

### 3. `docs/LAW_001_EXPERIMENT.md`
**Your first scientific contract.**
- Physical mechanism for `LAW_001`.
- Mathematical definition, variables, assumptions, and data lineage.
- Acceptance criteria, rejection criteria, confounders, and follow-up experiments.

---

## The Causal Hierarchy (Your Mental Model)

```
Level 1: Physical Drivers
├─ Temperature
├─ Wind, Solar output
├─ Coal, Hydro availability
├─ Battery state
├─ Interconnector status
└─ Generator constraints

        ↓ [Test each arrow]

Level 2: Network Physics
├─ Regional power flows
├─ Interconnector utilisation
├─ Price separation
├─ Marginal generators
└─ Constraint binding

        ↓ [Test each arrow]

Level 3: Market Outcomes
├─ Dispatch prices
├─ IRSR residues
├─ SRA payouts
└─ Volatility regimes

        ↓ [Only here]

Level 4: Investment Decisions
```

**Your job this quarter:** Validate Level 1→2 and Level 2→3 arrows.

---

## Phase 6 Experiment Sequence

### Week 1: First law

| Law / Experiment | From | To | Status |
|-------|------|-----|--------|
| LAW_001 / EXP_001 | Regional supply-demand imbalance | QNI flow | **Start here** |

### Weeks 2–4: Supporting laws

| Law | From | To |
|-------|------|-----|
| LAW_002 | Renewable output | Net load state |
| LAW_003 | Thermal availability | Capacity margin |

### Weeks 5–8: Downstream network laws

| Law | From | To |
|-------|------|-----|
| LAW_004 | Interconnector utilisation | Constraint probability |
| LAW_005 | Constraint state | Price separation / IRSR |

### Weeks 9–10: Replication and boundary testing

| Experiment | Scope | Result |
|-------|-------|--------|
| EXP_002+ | Cross-season / cross-period replication | Law robustness |

---

## Each Law / Experiment: 3-Day Cycle

**Day 1: Design (You as Chief Market Physicist)**
- [ ] Define the law (what physical mechanism?).
- [ ] Pre-register acceptance criteria (ρ > X, R² > Y).
- [ ] Identify PIT-safe data and boundary conditions.
- [ ] Brief implementation agent.

**Day 2: Implement & Run (Agent as Coder)**
- [ ] Code test; generate CSV + markdown result.
- [ ] No tuning, no optimization—just mechanistic validation.

**Day 3: Analyze & Record (You as Chief Market Physicist)**
- [ ] Challenge the result: Does it hold across subsamples?
- [ ] Identify boundary conditions and residual drivers.
- [ ] Record in Research Journal (full 9-section template).
- [ ] Add LAW to MARKET_PHYSICS_MODEL.md.
- [ ] Select next law or experiment.

---

## Key Rules

✅ **Always:**
- Pre-register criteria BEFORE running code.
- Use PIT-safe data (no future information).
- Test across subsamples (regions, seasons, hours).
- Quantify uncertainty (confidence level, residuals).
- Document boundary conditions (when does it hold/break?).

❌ **Never:**
- Change Digital Twin logic (Layer 3 is frozen).
- Assume correlation = causation.
- Cherry-pick thresholds after seeing results.
- Build forecasting models before physics is validated.
- Hide unexplained variance (if R² = 0.7, say so; don't claim perfect).

---

## Communication with Implementation Agent

**When you request an experiment:**

```
Phase 6B — LAW_001 / EXP_001

Objective

Validate the first Market Physics Law.

LAW_001

Regional supply-demand imbalance is the dominant physical driver of interconnector power flow.

Do NOT build a forecasting model.
Do NOT optimise trading.
Do NOT use machine learning.
Do NOT tune parameters.

This is a scientific experiment.

Tasks
1. Design the experiment.
2. Identify every required dataset.
3. Identify which datasets already exist.
4. Identify missing datasets.
5. Define derived variables.
6. Define acceptance criteria BEFORE implementation.
7. Define rejection criteria BEFORE implementation.
8. Identify possible confounding variables.
9. Identify expected boundary conditions.
10. Produce `docs/LAW_001_EXPERIMENT.md`.

No code.
No modelling.
No implementation.

Only produce the scientific experiment specification.
```

**What the agent should return:**
- One scientific experiment specification document.
- Clear law/experiment separation.
- No implementation until the contract is accepted.

---

## Success Signals

- **Week 1:** `LAW_001` / `EXP_001` contract accepted.
- **Week 4:** supporting laws identified with gaps clearly separated from mechanisms.
- **Week 8:** 2–3 downstream laws specified with explicit boundary conditions.
- **Week 10:** MARKET_PHYSICS_MODEL.md has a traceable law structure and replication plan.

---

## File Locations

| Document | Path | Purpose |
|----------|------|---------|
| Role Description | `CHIEF_RESEARCH_ANALYST_ROLE.md` | Your job; mindset shift |
| Phase 6 Roadmap | `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` | Experiment sequence; law templates |
| First Law Contract | `docs/LAW_001_EXPERIMENT.md` | First scientific experiment specification |
| Physics Repository | `docs/MARKET_PHYSICS_MODEL.md` | Central record of validated laws |
| Lab Notebook | `docs/Research Journal.md` | Detailed record of every experiment |
| This Guide | `PHASE6_QUICK_START.md` | Quick reference (you are here) |

---

## This Week's Action Items

1. **Read** `CHIEF_RESEARCH_ANALYST_ROLE.md` (15 min).
2. **Review** `docs/LAW_001_EXPERIMENT.md` (20 min).
3. **Check** `docs/NEM_DATA_COVERAGE_MATRIX.md` for dataset gaps affecting `LAW_001` (15 min).
4. **Pre-register** `LAW_001` / `EXP_001` in `docs/Research Journal.md` (20 min).
5. **Brief** implementation agent only after the contract is accepted (10 min).
6. **Run** implementation later against the accepted contract.

**Total time:** ~1.5–2 hours of research work this week.

---

## Questions Before You Start?

**Q: Do I need to understand all the details in PHASE6_CAUSAL_CONGESTION_RESEARCH.md?**  
A: No. Read `docs/LAW_001_EXPERIMENT.md` first, then use the broader roadmap as reference.

**Q: How detailed should pre-registered criteria be?**  
A: Detailed enough that you could hand it to someone else and they'd run the same test. Specific thresholds (ρ > 0.6, not "high correlation"). Subsamples specified (NSW1, VIC1, QLD1, SA1, not "all regions").

**Q: What if `LAW_001` fails?**  
A: That's valuable science. Reject or condition the law, document boundary conditions, and avoid building downstream assumptions on a weak mechanism.

**Q: When do I start forecasting?**  
A: After Week 8. When you've validated 5+ Level 1→2 arrows and 3+ Level 2→3 arrows. Then you can ask: "Given the current physical state, what do the physics laws predict?"

**Q: Is all this overhead worth it?**  
A: Yes. You're building scientific credibility. When you tell investors "the SRA value follows this physical law with 92% confidence," you have evidence. That's worth the research time.

---

## Next Step

→ Read `CHIEF_RESEARCH_ANALYST_ROLE.md`.  
→ Then review `docs/LAW_001_EXPERIMENT.md`.  
→ Then pre-register `LAW_001` / `EXP_001` in `docs/Research Journal.md`.  
→ Then brief the implementation agent.

Good luck. You're thinking like an engineer now.
