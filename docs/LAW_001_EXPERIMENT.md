# LAW_001 Experiment Specification

Status: **Pre-registered scientific experiment design**  
Law ID: `LAW_001`  
Experiment ID: `EXP_001`  
Phase: **Phase 6B — Market Physics Research**  
Implementation scope: **No code, modelling, machine learning, or trading optimisation**

## Objective
Validate the first Market Physics Law.

> **LAW_001**: Regional supply-demand imbalance is the dominant physical driver of interconnector power flow.

This is not a forecasting task. It is a scientific test of a physical mechanism.

## Question
Does regional surplus/deficit explain interconnector power flows, with sufficient stability across seasons, load regimes, and historical periods to justify accepting `LAW_001`?

## Pre-Registered Hypotheses

### Null Hypothesis (H0)
Regional supply-demand imbalance is **not** the dominant driver of interconnector flow once other physical variables are considered.

### Law Hypothesis (H1)
Regional supply-demand imbalance is the dominant physical driver of interconnector flow in normal operating regimes.

### Alternative Hypotheses
- **H2:** Constraint state dominates interconnector flow under high-stress network conditions.
- **H3:** Generator outages and dispatchable capacity shocks dominate flow direction during scarcity events.
- **H4:** Renewable variability dominates short-interval flow changes in high-renewable regimes.

## Physical Mechanism

The proposed mechanism is:

```text
Regional demand
    +
Regional generation
    ↓
Regional surplus / deficit
    ↓
Interconnector flow
    ↓
Interconnector utilisation
    ↓
Constraint probability
    ↓
Regional price separation
    ↓
Settlement residue
    ↓
SRA value
```

The experiment only tests the first critical law in this chain:

```text
Regional supply-demand imbalance → Interconnector power flow
```

If this law is weak or wrong, downstream laws become unstable or mis-specified.

## Mathematical Definition

For region $r$ at interval $t$:

$$
\text{NetBalance}_{r,t} = \text{Generation}_{r,t} - \text{Demand}_{r,t}
$$

For the NSW-QLD corridor, define:

$$
\Delta \text{Balance}_{t} = \text{NetBalance}_{QLD,t} - \text{NetBalance}_{NSW,t}
$$

Target variable:

$$
\text{QNIFlow}_{t}
$$

Primary law statement:

$$
\text{QNIFlow}_{t} = f(\text{NetBalance}_{NSW,t}, \text{NetBalance}_{QLD,t}, \text{Controls}_{t})
$$

where `Controls` may include battery dispatch, wind generation, solar generation, and coal generation if available.

## Variables

### Core inputs
- `demand_nsw_mw`
- `demand_qld_mw`
- `generation_nsw_mw`
- `generation_qld_mw`

### Control inputs
- `battery_dispatch_nsw_qld_proxy_mw`
- `wind_generation_nsw_mw`
- `wind_generation_qld_mw`
- `solar_generation_nsw_mw`
- `solar_generation_qld_mw`
- `coal_generation_nsw_mw`
- `coal_generation_qld_mw`

### Derived variables
- `net_balance_nsw_mw = generation_nsw_mw - demand_nsw_mw`
- `net_balance_qld_mw = generation_qld_mw - demand_qld_mw`
- `balance_difference_mw = net_balance_qld_mw - net_balance_nsw_mw`
- optional normalized variants scaled by regional demand or installed capacity

### Target
- `qni_flow_mw`

## Assumptions
- Dispatch interval is the correct temporal resolution for the law.
- Regional generation and demand provide a sufficient first-order approximation of regional surplus/deficit.
- QNI flow direction convention is consistently defined and documented.
- Controls improve interpretation but are not required for a first-pass test of the law.
- The Digital Twin remains frozen; all analysis uses PIT-safe historical data only.

## Required Datasets

| Dataset | Role | Exists today? | PIT safe? | Notes |
|---|---|---|---|---|
| `DISPATCHREGIONSUM` | NSW/QLD demand and coarse regional generation | Yes | Yes | Core required dataset |
| `DISPATCHINTERCONNECTORRES` | QNI flow target | Yes | Yes | Core required dataset |
| `DISPATCH_UNIT_SCADA` | Wind/solar/coal/battery controls | Unknown / partial | Yes if historical | Required for richer controls |
| DUID fuel mapping | Fuel-type aggregation | Partial / external mapping needed | Yes | Needed for unit-level controls |
| Calendar features | Weekday/weekend segmentation | Yes | Yes | Derived |
| Seasonal partition definition | Summer/winter segmentation | Yes | Yes | Derived |

## Data Lineage

### Already available in verified scope
- `DISPATCHREGIONSUM` through the frozen Digital Twin data path
- `DISPATCHINTERCONNECTORRES` through the frozen Digital Twin data path

### Likely available but not yet confirmed
- `DISPATCH_UNIT_SCADA`
- asset/fuel mapping required to split regional generation into wind, solar, coal, battery

### Missing or unresolved
- battery-specific aggregation method for NSW/QLD control variable
- definitive DUID mapping completeness for C2024Q4

These unresolved items do **not** block the scientific specification. They are part of the implementation contract.

## Experimental Design

### Experimental unit
- One five-minute dispatch interval.

### Primary corridor
- QNI / NSW1↔QLD1.

### Test structure
1. Construct NSW and QLD net-balance variables.
2. Compare net-balance measures to observed QNI flow.
3. Evaluate both raw and signed relationships.
4. Test robustness across:
   - summer vs winter,
   - peak vs off-peak,
   - weekday vs weekend,
   - multiple historical periods if available beyond C2024Q4.
5. Add control variables only to test whether net-balance remains dominant, not to maximize fit.

### Metrics
- $R^2$
- MAE
- Pearson correlation
- Spearman correlation
- Mutual information
- sign accuracy of predicted flow direction
- seasonal robustness
- peak/off-peak robustness
- weekday/weekend robustness

## Acceptance Criteria

`LAW_001` is **accepted** if all are satisfied:

1. **Explanatory power:** $R^2 > 0.5$ on the primary corridor.
2. **Directional correctness:** sign of implied flow is correct in >90% of intervals.
3. **Rank robustness:** Spearman correlation remains materially positive across major subsamples.
4. **Seasonal stability:** the relationship does not collapse or reverse between summer and winter.
5. **Operational stability:** the relationship remains directionally valid in peak and off-peak segments.
6. **Historical reproducibility:** the law remains supported across multiple historical windows when available.
7. **Dominance test:** adding control variables may refine the fit, but the regional net-balance terms remain the dominant explanatory mechanism.

## Falsification Evidence

The law is considered falsified (or at least non-dominant) if any of the following are observed:

1. A physically coherent alternative model (constraints, outages, or renewable variability) consistently outperforms net-balance dominance across core subsamples.
2. Net-balance terms lose explanatory primacy after adding physically justified controls.
3. Directional sign stability fails in major non-extreme regimes.
4. The relationship is only valid in narrow sub-regimes and does not generalize.
5. Replication across additional historical windows breaks the law without a defensible boundary-condition explanation.

## Rejection Criteria

`LAW_001` is **rejected** if any of the following hold:

1. $R^2 \le 0.5$ and no physically interpretable regime split rescues the law.
2. Flow sign is incorrect in >=10% of intervals without a documented boundary-condition explanation.
3. The relationship reverses or becomes unstable across seasons or operating regimes.
4. Control variables dominate to such an extent that regional supply-demand imbalance no longer appears to be the primary driver.
5. The law only appears valid in a narrow subsample and fails to generalize.

## Possible Confounding Variables
- Battery dispatch absorbing or reshaping deficit pressure
- Wind and solar output causing rapid intraday net-load shifts
- Coal outages affecting dispatchable capacity beyond coarse regional generation totals
- Interconnector deratings reducing flow independently of balance signals
- Binding constraints truncating the flow that balance alone would imply
- FCAS scarcity or other ancillary-service stress distorting normal dispatch relationships
- Data-definition mismatch between coarse regional generation and actual dispatchable surplus

## Expected Boundary Conditions

The law is expected to hold most strongly when:
- the corridor is not severely derated by outages,
- energy-market balance dominates ancillary-service effects,
- regional generation and demand are adequately measured,
- and there is no extreme constraint regime overwhelming balance-driven flow.

The law may weaken when:
- QNI is heavily constrained,
- FCAS scarcity distorts dispatch,
- batteries or hydro absorb imbalance locally,
- or regional generation totals fail to capture true flexible supply.

### Explicit stress regimes to test
- Planned network outages / interconnector deratings
- Islanding or near-islanding conditions
- Extreme renewable penetration intervals
- Severe thermal outage events
- High FCAS stress intervals

## Risks
- `DISPATCH_UNIT_SCADA` may be unavailable or incomplete for C2024Q4.
- Coarse regional generation may understate the real supply-side mechanism.
- QNI flow sign convention may create false directional errors if not standardized.
- Constraint-limited flows may reduce observed $R^2$ even if the underlying mechanism is valid.
- Single-quarter testing may overstate or understate the law's generality.

## Commercial Implication

If `LAW_001` is supported, expected product-level improvements include:
- Better congestion-state forecasting inputs.
- Better regional price-spread regime identification.
- Better BESS charge/discharge timing signals in corridor-linked regions.
- Better SRA valuation priors via physically grounded flow expectations.

If `LAW_001` is rejected or conditional, commercial implication is equally valuable:
- Prevents mis-specification of downstream valuation and forecasting logic.
- Redirects effort to the true dominant mechanism (constraints, outages, or renewables).

## Follow-Up Experiments

### If LAW_001 is accepted
- `EXP_002`: test the law across additional quarters and regimes.
- `EXP_003`: add renewable and battery controls to quantify residual improvement.
- `LAW_002`: test how interconnector utilisation emerges from flow.
- `LAW_004`: test how utilisation affects constraint probability.

### If LAW_001 is rejected or only conditional
- partition by season or demand regime,
- isolate constrained vs unconstrained intervals,
- test whether dispatchable capacity margin is a missing dominant variable,
- test whether regional surplus/deficit requires fuel-type weighting rather than raw generation totals.

## Verdict Classification

At conclusion, `LAW_001` must be classified as exactly one of:
- **Accepted**
- **Conditionally Accepted**
- **Rejected**
- **Inconclusive (needs more evidence)**

## Implementation Contract Output

This document is the contract for later implementation.

The implementation phase should therefore produce:
- one PIT-safe interval dataset for NSW/QLD balances and QNI flow,
- one experiment report with all metrics and robustness slices,
- one explicit verdict on `LAW_001`: **Accepted**, **Conditionally Accepted**, **Rejected**, or **Inconclusive**.

## Revision and Audit History Rule

If `LAW_001` reaches **Accepted**, its originating experiment contract (`EXP_001`) is frozen.

New evidence must be recorded as:
- a new experiment ID (e.g., `EXP_007`) and/or
- a law revision entry (e.g., `LAW_001-R2`),

without overwriting the original accepted contract.

This preserves an auditable evolution of scientific understanding.

## Final Note

This experiment is deliberately upstream of prices, residues, and SRA value.

That is the point.

If the research program cannot explain **power flow**, it should not claim to explain **settlement residue**.