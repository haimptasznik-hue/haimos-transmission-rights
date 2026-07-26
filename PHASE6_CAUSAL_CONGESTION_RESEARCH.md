# Phase 6: Market Physics Research

**Status:** Building causal hierarchy  
**Baseline:** `digital-twin-v1.0` (frozen, verified against C2024Q4)  
**Research Framework:** Market Intelligence v2 Charter + Market Physics Model  
**Objective:** Understand the physical laws that create prices  

---

## Roadmap: From State to Law

### Why Market Physics Matters
The NEM's prices and residues are not random. They emerge from **physical laws**—deterministic relationships between energy supply, demand, network constraints, and dispatch rules.

Your job as a research analyst is to:

1. **Identify the state** of the NEM at any point in time.
2. **Apply the physics laws** to that state.
3. **Predict what happens next**.

Forecasting is just the application of validated physics to future states.

**Distinction:**
- **Forecasting** = guessing the future state AND what will happen. (Hard, likely overfit.)
- **State estimation** = knowing the current state precisely. (Achievable now.) Then, **applying physics** = deterministic. (Validated through Digital Twin.)

### Market Physics Hierarchy

Every validated relationship goes into `MARKET_PHYSICS_MODEL.md`.

```
Level 1 — Physical Drivers
├─ Regional demand (MWh)
├─ Wind output (MW)
├─ Solar output (MW)
├─ Coal availability
├─ Hydro availability
├─ Battery state
├─ Interconnector outages
├─ Ambient temperature
└─ Generator constraints

         ↓ [Physics Test: how do drivers set the Grid State?]

Level 2 — Grid State (NEM State Vector)
│  This is what the Digital Twin is primarily estimating.
│  Physical drivers do not directly produce congestion;
│  they first produce an observable system state.
├─ Demand by region (MWh)
├─ Wind penetration % by region
├─ Solar penetration % by region
├─ Coal availability %
├─ Hydro availability %
├─ Battery SOC estimate
├─ Gas availability %
├─ Interconnector utilisation %
├─ Constraint count
├─ Constraint severity
├─ Regional price spreads
├─ FCAS scarcity indicators
├─ Temperature anomaly
└─ Outage score (MW off)

         ↓ [Physics Test: how does Grid State drive Network Physics?]

Level 3 — Network Physics
├─ Power flows (MW per direction)
├─ Binding constraint equations
├─ Marginal generator by region
├─ Voltage stability indicators
└─ Flow reversal events

         ↓ [Physics Test: how does Network Physics produce Market Outcomes?]

Level 4 — Market Outcomes
├─ Dispatch prices (AUD/MWh)
├─ Regional price separation
├─ IRSR (AUD per interval)
├─ SRA payouts (AUD per unit)
└─ Volatility regimes

         ↓ [Investment Decision: Given the physics, what's the edge?]

Level 5 — Investment Decisions
├─ SRA portfolio construction
├─ Hedging ratios
├─ Capital allocation
└─ Risk management
```

### Why Grid State Is Its Own Layer

A 40°C day + low wind + coal outage does **not** directly create price separation.

They create a **state**:

```
NSW demand deficit
      +
  High QNI loading
      +
  Battery discharging
      +
  Gas setting price
      +
  Constraint X5 binding
```

*That* state produces regional price separation and settlement residues.

This is why building the **NEM State Vector** is the first task — not Arrow 001.

### Research Loop (State-First, Then Arrow-by-Arrow)

```
Step 0: Define NEM State Vector (STATE_001)
         ↓
Step 1: Select Arrow (e.g., Temperature → Demand [State])
         ↓
Step 2: Design Experiment (PIT-safe, pre-registered)
         ↓
Step 3: Gather Evidence (from Digital Twin v1.0)
         ↓
Step 4: Test: Is arrow valid? (YES / NO / CONDITIONAL)
         ↓
Step 5: Record in MARKET_PHYSICS_MODEL.md with confidence
         ↓
Step 6: Log unresolved questions in KNOWN_UNKNOWNS.md
         ↓
Step 7: Next Arrow
```

---

## Market Physics Model (MARKET_PHYSICS_MODEL.md)

This is the source of truth for all validated causal relationships.

**Structure:**

```
LAW 1: Demand Imbalance Creates Inter-Regional Flow
───────────────────────────────────────────────────
Arrow: (Regional Demand Imbalance) → (Interconnector Flow)

Definition:
High demand in one region + low generation supply
→ must import from neighboring regions
→ drives power flow across interconnectors

Confidence: [To be determined by experiment]

Evidence:
- [Experiment ID]
- [Experiment ID]

Conditions:
- Applies to NSW1↔QLD1 [specify frequency, time of day, season]
- Breaks down when [identify boundary conditions]

Quantification:
- Flow = f(demand imbalance); R² = [value]
- Lag structure: [if any]
- Residual drivers: [what's left unexplained]
```

**Every law** is derived from one arrow-by-arrow experiment.

---

## Arrow Experiments: Template

### Arrow: [Level 1 Driver] → [Level 2 Physics]

Example: **Temperature → Regional Demand**

#### Question
Does ambient temperature drive regional demand variation?

#### Why This Arrow?
Temperature is an exogenous physical variable. On hot days, air conditioning load increases; on cold days (rare in Australia), heating increases. This is a first-principles driver that doesn't depend on forecasting or market-making decisions.

#### Expected Physics
```
↑ Temperature
    ↓
↑ Air conditioning load
    ↓
↑ Regional demand
```

#### Test Design (Pre-registered)

**Sample:** C2024Q4, all intervals, all NEM regions (NSW1, VIC1, QLD1, SA1).

**PIT-safe data:**
- Ambient temperature (external, not dependent on future state).
- Regional demand from DISPATCHREGIONSUM.
- Data cut-off: 2024-12-31T23:55:00Z.

**Metrics:**
- Correlation: ρ(temperature, demand) by region.
- Lagged correlation: ρ(temperature[t-1], demand[t]), ρ(temperature[t-4], demand[t]) [4 intervals = 4 hours].
- Seasonality-adjusted correlation: demand residual after removing day-of-week / hour-of-day / month effects, then correlated with temperature.

**Acceptance Criteria (Pre-registered):**
- ρ > 0.5 for at least 2/4 regions (NSW1, VIC1, QLD1, SA1).
- Lagged correlation exists at 4-hour horizon (ρ > 0.3) [suggests forecasting potential].
- Effect size is consistent across seasons [not just summer].

**Rejection Criteria (Pre-registered):**
- ρ < 0.2 for all regions.
- No lagged effect.
- Effect reverses between summer and winter (suggests alternative driver).

**Output:**
- `reports/ARROW_001_TEMPERATURE_DEMAND.csv`: interval-level detail (timestamp, region, temperature, demand, detrended demand, correlations).
- `reports/ARROW_001_RESULT.md`: acceptance/rejection verdict, confidence level, residual drivers.

---

### Arrow: [Level 2 Physics] → [Level 3 Market Outcomes]

Example: **Interconnector Utilisation → Regional Price Separation**

#### Question
Does high interconnector utilisation predict regional price separation?

#### Why This Arrow?
When an interconnector is at capacity, it becomes a binding constraint. In constrained dispatch, AEMO sets prices regionally to manage flows. High utilisation should precede price separation.

#### Expected Physics
```
↑ Interconnector utilisation
    ↓
Constraint binding
    ↓
↑ Regional price separation
```

#### Test Design (Pre-registered)

**Sample:** C2024Q4 NSW1↔QLD1 corridor (test both directions separately).

**Metrics:**
- Interconnector utilisation = |actual flow| / |max capacity| (%).
- Price separation = |region_A_price - region_B_price|.
- Congestion indicator = 1 if utilisation > 90%, 0 otherwise.

**Acceptance Criteria:**
- On high-utilisation intervals (>90%), mean price separation > AUD 50/MWh.
- On low-utilisation intervals (<50%), mean price separation < AUD 20/MWh.
- Correlation ρ(utilisation, price separation) > 0.6.
- Effect is symmetric across northbound and southbound.

**Output:**
- `reports/ARROW_002_UTILISATION_PRICESEP.csv`
- `reports/ARROW_002_RESULT.md`

---

## Experiment Sequencing

**Phase 6 — Step 0: NEM State Vector Definition (STATE_001)**

Before any arrow experiment: define and populate the NEM State Vector from C2024Q4 Digital Twin data. Log data gaps in KNOWN_UNKNOWNS.md.

**Phase 6a: Level 1 → Level 2 (Physical Drivers to Grid State)**

Arrow 1: Temperature → Grid State (demand dimension)  
Arrow 2: Wind output → Grid State (wind penetration %)  
Arrow 3: Solar output → Grid State (net load)  
Arrow 4: Coal/Gas availability → Grid State (fuel mix %)  
Arrow 5: Hydro availability → Grid State (flexible generation %)  

[Each arrow is one experiment, one ARROW_NNN report, one entry in MARKET_PHYSICS_MODEL.md]

**Phase 6b: Level 2 → Level 3 (Grid State to Network Physics)**

Arrow 6: Grid State (demand imbalance) → Interconnector flow  
Arrow 7: Grid State (fuel mix, demand) → Marginal generator  
Arrow 8: Grid State (interconnector utilisation) → Constraint binding  

**Phase 6c: Level 3 → Level 4 (Network Physics to Market Outcomes)**

Arrow 9: Constraint binding → IRSR generation  
Arrow 10: Price separation → Settlement residues  

**Phase 6d: Composite Physics (Validating the Full Chain)**

Arrow 11: State Vector(t) → Market Outcomes(t) (tests whether the full chain holds)

[If sub-arrows are validated individually, the composite should reproduce Digital Twin results.]

---

## Rules for Phase 6 Research

✅ **Must do:**
1. Design arrow experiments to understand **causality**, not correlation.
2. Pre-register acceptance/rejection criteria before running any experiment.
3. Use only Point-in-Time-safe data (no future information in decision).
4. Document every arrow in MARKET_PHYSICS_MODEL.md with confidence level.
5. Test boundary conditions: when does the arrow hold? When does it break?
6. Identify residual drivers: what's left unexplained by this arrow?
7. Report negative results; they guide the model.
8. Challenge weak hypotheses; demand evidence of physics, not just statistical fit.

❌ **Must not:**
1. Change settlement logic (Layer 3) to "make the arrow work."
2. Use realised settlement values (post-quarter) in pre-quarter state estimation.
3. Run an experiment without pre-registered criteria.
4. Cherry-pick acceptance thresholds after observing results.
5. Assume a correlation is causal without mechanism evidence.
6. Over-fit to one corridor or one quarter; test generalizability.
7. Build a forecasting model before the physics is validated.



---

## MARKET_PHYSICS_MODEL.md (Central Repository)

All validated arrows are recorded in `docs/MARKET_PHYSICS_MODEL.md`.

See that document for the full entry template and LAW structure.

Each entry contains: arrow definition, confidence level, supporting experiments, boundary conditions, and residual drivers.

---

## Research Role (Chief Market Physicist)

Your job is **not** to code.

Your job is to:

1. **Formulate causal questions** — where your engineering background creates the most value.
2. **Design experiments** (what arrow should we test next?).
3. **Challenge assumptions** (does this arrow hold in all conditions?).
4. **Reject weak hypotheses** (if evidence doesn't support causality, say so clearly).
5. **Quantify uncertainty** (what's the confidence level? what's left unexplained?).
6. **Decide what evidence is needed next** (which arrow unblocks downstream understanding?).

The implementation agent:
- implements experiments,
- analyses data,
- challenges your hypotheses,
- quantifies evidence.

You formulate the causal questions. That is where engineering intuition creates lasting value.

---

## Workflow for Phase 6 Arrow Experiments

### Step 1: Select an Arrow
From the hierarchy, pick one untested arrow.

Example: **Temperature → Demand**

### Step 2: Design the Experiment (Pre-register)
- Define metrics.
- Set acceptance/rejection criteria.
- Identify PIT-safe data sources.
- Specify boundary conditions.

**Write this down before running any code.**

### Step 3: Implement the Code (Implementation Detail)
Create `scripts/arrow_NNN_[name].py`:
- Load Market State Database.
- Compute metrics.
- Test acceptance criteria.
- Output evidence CSV and result markdown.

### Step 4: Run and Analyze
Execute the code; examine the evidence.

### Step 5: Challenge the Result
- Does the arrow hold in all subsamples (regions, seasons, hours)?
- Are there boundary conditions?
- What's left unexplained?
- Did you use PIT-safe data?

### Step 6: Record in MARKET_PHYSICS_MODEL.md
Add the arrow to the physics model with confidence level, evidence, and boundary conditions.

### Step 7: Plan Next Arrow
Which arrow should be tested next to validate downstream assumptions?

---

## Example: Temperature → Demand (ARROW_001)

### Pre-registration

**Question:** Does ambient temperature drive regional demand variation?

**Expected Physics:**
- Hot weather → ↑ air conditioning load → ↑ demand.
- Cold weather → ↑ heating load (small in Australia) → ↑ demand.
- Mild weather → ↓ demand.

**Acceptance Criteria:**
- Correlation ρ > 0.5 for at least 2/4 regions.
- Lagged effect exists (temperature at t-4 hours correlates with demand at t).
- Effect consistent across seasons.

**Rejection Criteria:**
- ρ < 0.2 all regions.
- No lagged effect.
- Effect reverses between seasons.

### Implementation (Code)

```python
# scripts/arrow_001_temperature_demand.py

import pandas as pd
from src.core.market_state_database import MarketStateDatabase

# Load data (PIT-safe)
mkt = MarketStateDatabase()
demand = mkt.get_dispatch_region_sum(quarter='C2024Q4')
temperature = load_bom_temperature()  # Bureau of Meteorology

pit_cutoff = pd.Timestamp('2024-12-31T23:55:00Z')
demand = demand[demand['timestamp'] <= pit_cutoff]
temperature = temperature[temperature['timestamp'] <= pit_cutoff]

# Merge and compute
merged = pd.merge(demand, temperature, on='timestamp')

# Test correlations by region
for region in ['NSW1', 'VIC1', 'QLD1', 'SA1']:
    corr = merged[['temperature', f'{region}_demand']].corr().iloc[0, 1]
    print(f"{region}: ρ = {corr:.3f}")

# Test lagged correlation (temperature at t-4h predicts demand at t)
for lag in [4, 8, 12]:
    merged[f'temp_lag_{lag}'] = merged['temperature'].shift(lag)
    corr_lag = merged[[f'temp_lag_{lag}', 'NSW1_demand']].corr().iloc[0, 1]
    print(f"NSW1 lagged {lag}h: ρ = {corr_lag:.3f}")

# Output
merged.to_csv('reports/ARROW_001_TEMPERATURE_DEMAND.csv', index=False)
```

### Analysis & Interpretation

Look at the CSV output:
- Which regions show strong ρ?
- Do lagged effects exist?
- Are there outliers (e.g., demand doesn't rise on hot days)?

If ρ > 0.5 and lagged effect holds, the arrow is **supported**.  
If ρ < 0.2, the arrow is **not supported** (temperature is not the main driver).  
If ρ is moderate (0.3–0.5), the arrow is **conditional** (holds in some seasons, not others).

### Result Markdown

Write `reports/ARROW_001_RESULT.md`:

```
# ARROW 001: Temperature → Demand

## Verdict: SUPPORTED (Confidence: 87%)

## Key Metrics
- NSW1: ρ = 0.62 ✓
- VIC1: ρ = 0.71 ✓
- QLD1: ρ = 0.41 ✗
- SA1: ρ = 0.56 ✓

## Lagged Correlation
- 4-hour lag: ρ = 0.58 (NSW1) → suggests ~15 min advance signal
- 8-hour lag: ρ = 0.35 (NSW1) → weaker
- Interpretation: Temperature signal is mostly contemporaneous; very limited forecasting lookahead.

## Boundary Conditions
- Effect strongest during summer (Dec-Feb): ρ = 0.78 in NSW1
- Effect weaker during mild seasons (Mar-Nov): ρ = 0.42
- Effect holds all hours, but stronger during business hours (stronger AC usage)

## Residual Drivers
- 13% of demand variance unexplained by temperature
- Likely: economic activity (holidays), unexpected outages, renewable output, demand-side management

## Next Arrows to Test
1. ARROW_004: Economic Activity (day-of-week, holidays) → Demand
2. ARROW_005: Generator Availability → Regional Supply Dynamics
```

### Record in MARKET_PHYSICS_MODEL.md

Add to the central physics model:

```
LAW 1: Temperature Drives Regional Demand
──────────────────────────────────────────
Arrow: (Ambient Temperature) → (Regional Demand)

Confidence: 87%

Validated by: ARROW_001

Holds:
- NSW, VIC, SA regions (ρ > 0.55)
- Summer strongest (ρ = 0.78)
- All times of day

Breaks:
- QLD: weak signal (ρ = 0.41) — alternative driver dominates
- During holidays (demand decouples from temperature)

Residual: 13% of variance, likely economic activity and renewable variability
```

---

## Getting Market State Data

The Digital Twin v1.0 provides authoritative Layer 2 state data.

```python
from src.core.market_state_database import MarketStateDatabase

mkt = MarketStateDatabase()

# Regional-level demand
demand = mkt.get_dispatch_region_sum(quarter='C2024Q4')
# Columns: timestamp, region_id, total_demand, total_generation, net_import, etc.

# Interconnector flows
flows = mkt.get_dispatch_interconnector_res(quarter='C2024Q4')
# Columns: timestamp, interconnector_id, from_region, to_region, flow_mw, etc.

# Regional prices
prices = mkt.get_dispatch_price(quarter='C2024Q4')
# Columns: timestamp, region_id, price, etc.

# IRSR (from Layer 3 Digital Twin)
irsr = mkt.get_quarterly_irsr(quarter='C2024Q4')
# Columns: interval, interconnector_id, from_region, irsr_value, etc.
```

---

## Timeline: Phase 6 Arrow Sequencing

**Week 1-2:**
- ARROW_001: Temperature → Demand
- ARROW_002: Wind Output → Generator Dispatch

**Week 3-4:**
- ARROW_003: Coal Availability → Marginal Generator
- ARROW_004: Economic Activity → Demand Deviation

**Week 5-6:**
- ARROW_006: Interconnector Utilisation → Price Separation
- ARROW_007: Regional Imbalance → Flow Requirement

**Week 7-8:**
- ARROW_008: Constraint Binding → IRSR Generation
- ARROW_009: Price Separation → Settlement Residues

**Week 9-10:**
- Composite Validation: Full chain temperature → price → IRSR

**Outcomes (by week 10):**
- NEM State Vector defined; partially populated from C2024Q4 data.
- 10 validated arrows in MARKET_PHYSICS_MODEL.md.
- Every accepted LAW demonstrably reduces unexplained variance and is reproducible across historical periods.
- Causal graph traceable from Level 1 physical drivers → Level 4 market outcomes.
- Boundary conditions and residuals documented for each arrow.
- KNOWN_UNKNOWNS.md populated with all open questions from the research.
- Roadmap for Layer 5 forecasting (state estimation applied forward in time).

---

## Questions for the Chief Market Physicist

1. **"Which arrow should I test next?"**  
   → Pick the highest-leverage arrow: the one that, if validated, most clearly settles a dispute about mechanism. Level 1→2 arrows first (they feed everything downstream); then Level 2→3; then composite.

2. **"What if an arrow is only partially supported?"**  
   → That's valuable and expected. Record boundary conditions precisely. "Temperature drives demand in NSW/VIC/SA (summer: ρ=0.78) but not QLD (ρ=0.41)" tells you QLD has a different dominant driver. That is a discovery, not a failure.

3. **"Should I build a forecasting model yet?"**  
   → No. Forecasting is state estimation applied forward in time. You cannot apply what you haven't validated. Build the physics first.

4. **"What about variables I can't measure?"**  
   → Log them immediately in `docs/KNOWN_UNKNOWNS.md` with priority and required data source. Unmeasured variables in the causal chain are exactly where competitive moat lives.

5. **"When is the physics model sufficient?"**  
   → Not when a single R² threshold is met. The model is sufficient when every accepted LAW materially reduces unexplained variance and is reproducible across historical periods. Temperature explaining 18% and wind explaining 24% are both valuable discoveries. Science is not judged by one aggregate metric.

---

## Next Steps

→ **First:** Define the NEM State Vector (STATE_001). Populate from C2024Q4 Digital Twin. Log all data gaps in `docs/KNOWN_UNKNOWNS.md`.  
→ **Then:** Design ARROW_001 (Temperature → Grid State [demand dimension]) experiment; pre-register all criteria.  
→ **Finally:** Run code, analyze, record result, decide next arrow.

You are the Chief Market Physicist. Your job is to discover and validate the physical principles that govern the NEM, with the Digital Twin acting as the experimental laboratory.
