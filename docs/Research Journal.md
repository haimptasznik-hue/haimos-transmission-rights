# Research Journal

Purpose: Maintain a defensible, cumulative record of Market Physics laws, experiments, and causal evidence.

**This is your laboratory notebook.** Every law and experiment is documented here.

## Operating Rule
No code implementation starts unless:
1. A law (causal relationship) has been identified.
2. Acceptance/rejection criteria are pre-registered (before running code).
3. A test design exists (PIT-safe data, sample, metrics).
4. Falsification evidence has been pre-defined.
5. Commercial implication has been stated.

## Research Numbering

- **`LAW_###`** identifies the physical mechanism being tested.
- **`EXP_###`** identifies a specific experiment testing that law.

One law may require multiple experiments before acceptance or rejection.

## Law + Experiment Template

### 1) Law Definition
- **Law ID:** `LAW_###`
- **Experiment ID:** `EXP_###`
- **Level:** [1→2 / 2→3 / composite]
- **From:** [Physical driver or network state]
- **To:** [Outcome or downstream driver]
- **Physics:** Plain-English explanation of why this arrow should exist.

### 2) Prior Evidence
- Why do we believe this arrow exists?
- Prior research, market intuition, or anomaly motivating the test.

### 3) Hypothesis Structure
- **Null hypothesis (H0):** what would imply this law is not dominant?
- **Law hypothesis (H1):** primary mechanism claim.
- **Alternative hypotheses (H2+):** plausible competing mechanisms.

### 4) Boundary Conditions
- When should this arrow hold?
- When should it break?
- Regional, seasonal, or regime-specific conditions?

### 5) Required Datasets (PIT-safe)
- Data sources (Layer 2: Market State Database, Layer 3: Digital Twin).
- Effective dates / versions.
- Known quality constraints.
- Cut-off date (no future information).

### 6) Test Design (Pre-registered)

**Metrics:**
- Primary metric (e.g., correlation ρ, R², effect size).
- Secondary metrics (lagged effects, subgroup analysis).

**Acceptance Criteria:**
- Threshold for supporting the law (e.g., ρ > 0.6).
- Consistency requirements (e.g., holds in 3/4 regions).

**Rejection Criteria:**
- Threshold for rejecting the law (e.g., ρ < 0.2).
- Contradictory evidence (e.g., effect reverses by season).

**Falsification Criteria:**
- Explicit evidence that would overturn dominance of this law.

**Subsamples:**
- Test across regions, seasons, hours, regimes.
- Confirm generalizability.

### 7) Evidence
- Key statistics: correlations, R², effect sizes, confidence intervals.
- Reconciliation checks: Does this match Digital Twin results?
- Visualizations: scatter plots, time series, distributions.

### 8) Result
- **Verdict:** Accepted / Conditionally Accepted / Rejected / Inconclusive.
- **Confidence:** [XX%] (based on strength of evidence, generalizability).
- **Quantification:** Explicit equations, parameters, residuals.

### 9) Boundary Conditions (Refined)
- Arrow holds under these conditions: [list].
- Arrow breaks under these conditions: [list].
- Residual drivers: [What's left unexplained? XX% of variance].

### 10) Commercial Implication
- If accepted, how does this improve one or more products?
- If rejected, what wrong commercial assumptions were prevented?

### 11) Decision
- **Law Status:** Add to Market Physics Model / Reject / Refine hypothesis.
- **Next Experiment:** Which experiment should be run next against this or another law?
- **Implementation Gating:** If this arrow will unlock downstream code, document the gate.

### 12) Revision Protocol
- If accepted, freeze the originating experiment record.
- Record new evidence as a new `EXP_###` and/or `LAW_###-R#`.
- Do not rewrite accepted historical entries.

---

## Entry Index

| Date | Law ID | Experiment ID | Level | From | To | Confidence | Status | Physics Model Entry |
|------|--------|---------------|-------|------|-----|-----------|--------|-------------------|
| – | LAW_001 | EXP_001 | 2→3 | Regional supply-demand imbalance | Interconnector power flow | – | In Design | – |
| 2026-07-23 | LAW_002 | EXP_002 | 2→3 | Grid state | Interconnector capability / utilisation | 66% | Conditionally Accepted | Yes |
| – | LAW_003 | – | 3→4 | Constraint state | Price separation | – | Not Started | – |

### EXP_001 Outcome

**Date:** 2026-07-16  
**Law ID:** LAW_001  
**Experiment ID:** EXP_001  
**Level:** 2→3

**Law Definition:**  
Regional supply-demand imbalance → interconnector power flow

**Evidence:**
- Pearson correlation: `-0.812097`
- Spearman correlation: `-0.794645`
- R²: `0.872068`
- MAE: `108.918574 MW`
- Directional sign accuracy: `0.797667`
- High-imbalance congestion rate: `0.580338`

**Verdict:** `REJECTED`

**Boundary Conditions (Refined):**
- Relationship is unstable across monthly, peak/off-peak, and weekday/weekend splits.
- Directional dominance does not hold at the pre-registered threshold.

**Commercial Implication:**
- Prevents downstream products from assuming a stable balance→flow law for QNI.

**Next Experiment:**
- `EXP_002` — test whether constraint state or network limits dominate the residual flow structure without changing thresholds.

**Revision Protocol:**
- `EXP_001` is frozen as the canonical rejected attempt for LAW_001.

### EXP_002 Outcome

**Date:** 2026-07-23  
**Law ID:** LAW_002  
**Experiment ID:** EXP_002  
**Level:** 2→3

**Law Definition:**  
Interconnector capability and utilisation constrain the conversion of regional imbalance into actual flow.

**Evidence:**
- Primary sample size: `26,362`
- Intervention rows excluded: `12`
- Baseline R²: `0.056287`
- Capability/state R²: `0.359864`
- Incremental R²: `0.303577`
- Near-limit R²: `0.601758`
- Near-limit incremental R²: `0.535119`
- Directional accuracy: `0.797989`
- Monthly stability: `True`

**Verdict:** `CONDITIONALLY_ACCEPTED`

**Boundary Conditions (Refined):**
- Relationship is strongest near corridor limits.
- Far-from-limit intervals retain much weaker explanatory lift.
- Detailed binding-constraint and outage data remain the principal unresolved layer.

**Commercial Implication:**
- Improves congestion-state interpretation, corridor-capability awareness, and SRA valuation priors under stress.

**Next Experiment:**
- `EXP_003` — add binding-constraint and outage-state variables to test whether they explain the remaining far-from-limit residual structure.

**Revision Protocol:**
- `EXP_002` is frozen as the canonical conditional acceptance for LAW_002.

---

## Entry Template

**Date:** YYYY-MM-DD  
**Law ID:** LAW_NNN  
**Experiment ID:** EXP_NNN  
**Level:** [1→2 / 2→3 / composite]

### Law Definition
**From:** [Physical driver]  
**To:** [Outcome]  

**Physics:**  
[Plain English: why does this causal relationship exist?]

### Prior Evidence
[What makes you believe this arrow exists? Prior research, intuition, preliminary data?]

### Hypothesis Structure

**Null Hypothesis (H0):**
[What would imply this law is not dominant?]

**Law Hypothesis (H1):**
[Primary mechanism claim]

**Alternative Hypotheses (H2+):**
- [Competing physical mechanism 1]
- [Competing physical mechanism 2]

### Boundary Conditions

**Should Hold:**
- [Region / season / time of day / regime]

**Should Break:**
- [When does the arrow fail?]

### Datasets (PIT-safe)

**Sources:**
- [Layer 2 / Layer 3 data]

**Cut-off:**
- [No data after YYYY-MM-DD HH:MM:SS Z]

### Test Design (Pre-registered)

**Primary Metric:**
- [ρ, R², effect size]

**Acceptance Criteria:**
- [Threshold for supporting law]
- [Consistency requirements across subsamples]

**Rejection Criteria:**
- [Threshold for rejecting law]
- [Contradictory evidence]

**Falsification Criteria:**
- [Explicit evidence that would overturn the law]

### Evidence

**Key Statistics:**
- [ρ = X, R² = Y, confidence interval = [a, b]]
- [Holds in regions: NSW, VIC, SA (not QLD)]
- [Strongest in summer, weaker in winter]

**Reconciliation:**
- [Does Digital Twin reproduce this relationship?]

### Result

**Verdict:** Supported / Not Supported / Conditional
**Verdict:** Accepted / Conditionally Accepted / Rejected / Inconclusive

**Confidence:** [XX%]

**Effect Size:**
- [Y = f(X); quantification]
- [Residual: ZZ% of variance unexplained]

### Boundary Conditions (Refined)

**Arrow Holds:**
- All seasons ✓
- All hours of day ✓
- NSW1, VIC1, SA1 (ρ > 0.5) ✓
- QLD1 (ρ = 0.41, weak) ✗

**Arrow Breaks:**
- During holidays (demand decouples)
- Extreme weather events (outside normal envelope)

**Residuals:**
- 15% of variance: [other drivers hypothesized]

### Commercial Implication

**If Accepted:**
- [How this improves congestion, spread, BESS, SRA, or related products]

**If Rejected/Conditional:**
- [What commercial mis-specification this prevents]

### Decision

**Add to Market Physics Model?** YES / NO

**If Yes:**
- LAW N entry in MARKET_PHYSICS_MODEL.md
- Confidence: [XX%]
- Evidence: [this ARROW_NNN]

**Next Experiment:**
- [EXP_MMM or LAW_MMM: what should be tested next?]

### Revision Protocol
- [If accepted, freeze this entry; new evidence requires new EXP or LAW revision]

### Notes
[Any caveats, data quality issues, or implementation notes]
