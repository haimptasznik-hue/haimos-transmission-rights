# Known Unknowns

**Purpose:** Every unresolved question in the Market Physics Model is logged here.

This document prevents unknowns from becoming forgotten assumptions.

**Rule:** When you cannot complete an arrow experiment due to missing data, unavailable mechanism, or unresolved interaction — log it here immediately. Do not skip it silently.

**Resolution:** Each entry is either resolved (linked to an experiment result) or promoted to a data acquisition task.

---

## Entry Template

```
ID: KU-NNN
Question: [Plain-English statement of what is unknown]
Domain: [Level 1 / Level 2 (Grid State) / Level 3 (Network Physics) / Level 4 (Market Outcomes)]
Status: Unknown / Partially Supported / Under Investigation / Resolved
Confidence: [XX% or N/A]
Priority: Critical / High / Medium / Low
Required Data: [AEMO dataset or external source needed to resolve this]
Required Experiment: [ARROW_NNN or STATE_NNN once scheduled]
Evidence So Far: [What we do know, if anything]
Owner: [Phase 6 / Phase 7 / Future]
Date Logged: YYYY-MM-DD
Date Resolved: YYYY-MM-DD (or —)
Resolution: [Link to experiment result, or N/A]
```

---

## Open Questions

### KU-001
**Question:** Does battery dispatch materially alter QNI utilisation?

**Domain:** Level 2 — Grid State / Level 3 — Network Physics

**Status:** Unknown

**Confidence:** N/A

**Priority:** High

**Required Data:** DISPATCH_UNIT_SCADA (battery unit IDs, 5-minute dispatch MW)

**Required Experiment:** ARROW_NNN (to be scheduled after STATE_001 is complete)

**Evidence So Far:**
- Battery capacity in NEM is growing. SA has significant battery presence.
- QNI is a NSW↔QLD interconnector; SA battery is more relevant to VIC↔SA.
- No direct test performed; assumption is that battery dispatch is small relative to QNI total MW.

**Owner:** Phase 6

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-002
**Question:** Can hydro storage levels explain residual NSW price spikes?

**Domain:** Level 1 — Physical Drivers / Level 4 — Market Outcomes

**Status:** Partially Supported (Confidence: 42%)

**Confidence:** 42%

**Priority:** High

**Required Data:** Hydro storage (Snowy Hydro water levels), DISPATCH_UNIT_SCADA (hydro dispatch MW)

**Required Experiment:** ARROW_014 (reserved)

**Evidence So Far:**
- Phase 4B attribution noted hydro availability as a residual contributor to NSW price spikes.
- Snowy Hydro is the dominant flexible generator in NSW; its availability is a key state variable.
- No direct test of storage levels vs. price spikes performed.
- Confidence 42% is subjective; requires quantification.

**Owner:** Phase 6

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-003
**Question:** Is DISPATCH_UNIT_SCADA available for C2024Q4, and what generator types are identifiable?

**Domain:** Level 2 — Grid State

**Status:** Unknown

**Confidence:** N/A

**Priority:** Critical

**Required Data:** DISPATCH_UNIT_SCADA (AEMO MMSDM dataset, C2024Q4 monthly files)

**Required Experiment:** State Vector construction (STATE_001)

**Evidence So Far:**
- DISPATCH_UNIT_SCADA provides 5-minute dispatch MW per DUID (Dispatchable Unit Identifier).
- DUID lookup table maps DUIDs to fuel type (coal, gas, hydro, wind, solar, battery, etc.) and region.
- If available for C2024Q4, this unlocks: wind %, solar %, coal availability, gas availability, hydro availability, battery SOC proxy, outage score.
- These are variables 6–14 and 23 in the NEM State Vector candidate list.
- Without DISPATCH_UNIT_SCADA, approximately 9 of 30 State Vector variables are unavailable.

**Owner:** Phase 6 — Immediate

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-004
**Question:** Is DISPATCHCONSTRAINT available for C2024Q4, and what constraint IDs are most relevant to QNI binding?

**Domain:** Level 3 — Network Physics

**Status:** Unknown

**Confidence:** N/A

**Priority:** High

**Required Data:** DISPATCHCONSTRAINT (AEMO MMSDM dataset, C2024Q4 monthly files)

**Required Experiment:** ARROW_008 (Constraint Binding → IRSR Generation)

**Evidence So Far:**
- DISPATCHCONSTRAINT records which constraint equations are binding in each dispatch interval.
- QNI northbound binding (N>>N_NIL_EXPORT) is the primary source of northbound IRSR.
- Without this dataset, we cannot directly observe constraint binding; we must infer from flow + price separation.
- Constraint IDs change over time (network topology changes); mapping to interconnector-level constraints requires interpretation.

**Owner:** Phase 6

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-005
**Question:** How does FCAS scarcity propagate to regional prices and IRSR?

**Domain:** Level 3 — Network Physics / Level 4 — Market Outcomes

**Status:** Unknown

**Confidence:** N/A

**Priority:** Medium

**Required Data:** DISPATCHPRICE (FCAS raise/lower components, already in v1.0 cache); FCAS raise/lower flags extractable from existing data.

**Required Experiment:** ARROW_NNN (to be scheduled after core energy price arrows are validated)

**Evidence So Far:**
- FCAS (Frequency Control Ancillary Services) markets set separate prices for raise and lower services.
- FCAS scarcity events can decouple regional energy prices from their normal relationships.
- If FCAS scarcity is common in C2024Q4, it may explain residual variance in energy price separation.
- DISPATCHPRICE likely contains FCAS price components; needs verification.

**Owner:** Phase 7

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-006
**Question:** Does temperature anomaly (vs. seasonal norm) explain more demand variance than raw temperature?

**Domain:** Level 1 — Physical Drivers → Level 2 — Grid State (demand)

**Status:** Unknown

**Confidence:** N/A

**Priority:** Medium

**Required Data:** BOM (Bureau of Meteorology) temperature data + seasonal climate normals for each NEM region.

**Required Experiment:** ARROW_001 variant (Temperature anomaly → demand residual)

**Evidence So Far:**
- Raw temperature may conflate seasonal variation with genuine anomalies.
- A 25\u00b0C day in July (winter) may drive more demand than the same temperature in December (summer).
- Temperature anomaly (actual minus seasonal norm) likely has a cleaner causal relationship with demand deviation.
- This is an experiment design choice for ARROW_001 rather than a separate unknown.

**Owner:** Phase 6 — ARROW_001 design

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-007
**Question:** Does QLD demand have a different dominant driver than NSW/VIC/SA?

**Domain:** Level 1 — Physical Drivers → Level 2 — Grid State (demand)

**Status:** Partially Supported (Confidence: ~40%)

**Confidence:** ~40%

**Priority:** High

**Required Data:** DISPATCHREGIONSUM (available in v1.0); BOM QLD temperature; QLD industrial load proxies (if available).

**Required Experiment:** ARROW_001 subgroup analysis (QLD specifically)

**Evidence So Far:**
- Phase 5B driver analysis noted QLD demand is less temperature-sensitive than NSW/VIC.
- QLD has significant industrial demand (mining, aluminium smelting) which is less weather-dependent.
- QLD also has the strongest solar penetration; solar self-generation may reduce net demand more in QLD than other states.
- Hypothesis: QLD demand is driven more by industrial activity and solar penetration than temperature.

**Owner:** Phase 6 — ARROW_001 analysis + ARROW_002 follow-up

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-008
**Question:** Can the NEM State Vector be populated with at least 20/30 variables from existing C2024Q4 cache?

**Domain:** Level 2 — Grid State (general)

**Status:** Unknown

**Confidence:** N/A

**Priority:** Critical

**Required Data:** Review what is in the existing Digital Twin v1.0 cache for C2024Q4.

**Required Experiment:** STATE_001 deliverable

**Evidence So Far:**
- From DISPATCHPRICE: regional prices, price spreads (variables 18–20). Available.
- From DISPATCHINTERCONNECTORRES: interconnector utilisation (variables 14–17). Available.
- From DISPATCHREGIONSUM: regional demand (variables 1–5). Available.
- Derived: hour of day, day of week, week of quarter (variables 28–30). Available.
- From BOM temperature (external): temperature anomaly (variables 21–22). Requires acquisition.
- From DISPATCH_UNIT_SCADA: wind %, solar %, coal %, gas %, hydro %, battery SOC, outage score (variables 6–14, 23). Requires acquisition.
- From DISPATCHCONSTRAINT: constraint count, severity (variables 24–25). Requires acquisition.
- From DISPATCHPRICE (FCAS): scarcity flags (variables 26–27). May be derivable.
- Estimate: ~13/30 available immediately; ~17/30 require new data or derivation.

**Owner:** Phase 6 — Immediate (STATE_001 prerequisite)

**Date Logged:** 2026-07-15

**Date Resolved:** —

---

### KU-009
**Question:** Are `DISPATCHABLEGENERATION` and `TOTALINTERMITTENTGENERATION` available from the existing DISPATCHREGIONSUM raw zips, and can they be extracted via a targeted re-parse without touching the Digital Twin data pipeline?

**Domain:** Level 2 — Grid State (generation)

**Status:** Partially Supported — columns confirmed present in raw zips; not in current normalized cache

**Confidence:** 90% (raw data confirmed; extraction effort is low-moderate)

**Priority:** Critical — blocks EXP_001 net-balance variable construction

**Required Data:** `DISPATCHREGIONSUM` raw zips (already downloaded); columns `DISPATCHABLEGENERATION`, `TOTALINTERMITTENTGENERATION`

**Required Experiment:** EXP_001 prerequisite — must be resolved before experiment implementation begins

**Evidence So Far:**
- Raw zip `PUBLIC_DVD_DISPATCHREGIONSUM_202001010000.zip` confirmed to contain `DISPATCHABLEGENERATION` and `TOTALINTERMITTENTGENERATION` in the header row.
- Current normalized cache schema only preserves `regional_operational_demand`, `forecast_demand`, `region_id`, `interval_timestamp_utc`, `source_file`, `publish_timestamp_utc`.
- The Digital Twin normalization script (`market_state_database.py`) intentionally dropped generation columns when ingesting for the SRA backtest use-case.
- Re-extraction can be done as a standalone EXP_001 data-preparation script without modifying the Digital Twin pipeline.

**Owner:** Phase 6 — EXP_001 data preparation

**Date Logged:** 2026-07-16

**Date Resolved:** —

---

### KU-010
**Question:** What is the sign convention for QNI flow in `DISPATCHINTERCONNECTORRES`, and is it consistently positive-northbound or does it flip with direction?

**Domain:** Level 3 — Network Physics

**Status:** Resolved

**Confidence:** 100%

**Priority:** Critical — directly affects directional correctness metric in EXP_001 acceptance criteria (>90% sign accuracy required)

**Required Data:** `DISPATCHINTERCONNECTORRES` (already in cache); AEMO MMS Data Model documentation for QNI sign convention

**Required Experiment:** EXP_001 data preparation — must be documented and locked before running the experiment

**Evidence So Far:**
- Authoritative AEMO definition from `DISPATCHINTERCONNECTORRES` (`Elec20.htm`): “The definition of direction of flow for an interconnector is that positive flow starts from the FROMREGION in the INTERCONNECTOR table.”
- Authoritative `INTERCONNECTOR` table definition (`Elec33.htm`) confirms orientation fields: `INTERCONNECTORID`, `REGIONFROM`, `REGIONTO`.
- C2024Q4 monthly `INTERCONNECTOR` archive rows confirm canonical QNI AC entry:
	- `INTERCONNECTORID = NSW1-QLD1`
	- `REGIONFROM = NSW1`
	- `REGIONTO = QLD1`
- 20 raw C2024Q4 `DISPATCHINTERCONNECTORRES` intervals validated (12 positive, 8 negative, 0 zero):
	- positive `MWFLOW` aligns with NSW1→QLD1
	- negative `MWFLOW` aligns with QLD1→NSW1
	- zero `MWFLOW` treated as no directional transfer
- 20/20 sampled intervals had target-flow sign consistent with `METEREDMWFLOW` sign.

**Owner:** Phase 6 — EXP_001 data preparation

**Date Logged:** 2026-07-16

**Date Resolved:** 2026-07-16

**Resolution:** KU-010 closed. Sign convention locked for EXP_001:
- positive `MWFLOW` = flow from `REGIONFROM` to `REGIONTO`
- for QNI (`NSW1-QLD1`): positive = NSW1→QLD1, negative = QLD1→NSW1, zero = no directional transfer.

---

### KU-011
**Question:** Does the C2024Q4 DISPATCHREGIONSUM raw data have the same column structure as the 2020 files, or were there schema changes between 2020 and 2024?

**Domain:** Level 2 — Grid State

**Status:** Resolved

**Confidence:** 100%

**Priority:** High — EXP_001 targets C2024Q4 as the primary test window

**Required Data:** `PUBLIC_DVD_DISPATCHREGIONSUM_202410010000.zip` (already downloaded) — inspect header row

**Required Experiment:** EXP_001 data preparation

**Evidence So Far:**
- Oct/Nov/Dec 2024 raw DISPATCHREGIONSUM archives all contain required EXP_001 columns with 0.0 null rate:
	- `SETTLEMENTDATE`, `REGIONID`, `TOTALDEMAND`, `DISPATCHABLEGENERATION`, `TOTALINTERMITTENTGENERATION`.
- C2024Q4 schema is internally consistent across all three months.
- 2024 includes additional newer columns (e.g., `SS_SOLAR_*`, `SS_WIND_*`, `BDU_*`) compared with 2020.
- No material change affecting required EXP_001 demand/generation fields.

**Owner:** Phase 6 — EXP_001 data preparation

**Date Logged:** 2026-07-16

**Date Resolved:** 2026-07-16

**Resolution:** KU-011 closed. Required EXP_001 fields are present and stable across C2024Q4; schema differences versus 2020 are additive and non-blocking.

---

### KU-012
**Question:** Is the `phase5c_nsw1_qld1_joined_interval_table.csv` a 2020 artifact or does a C2024Q4 equivalent exist (or need to be built) for EXP_001?

**Domain:** Level 2 — Grid State / Experimental Infrastructure

**Status:** Resolved — artifact confirmed as Jan–Mar 2020 only; C2024Q4 equivalent does not yet exist

**Confidence:** 100% (verified from file contents: first row 2020-01-01, last row 2020-03-31)

**Priority:** Critical — EXP_001 pre-registers C2024Q4 as primary test window; 2020 artifact cannot substitute

**Required Data:** C2024Q4 DISPATCHREGIONSUM + DISPATCHINTERCONNECTORRES (ingestion manifests confirm these were ingested successfully for Oct/Nov/Dec 2024)

**Required Experiment:** EXP_001 data preparation — the experiment build step must create a C2024Q4 equivalent joined table

**Evidence So Far:**
- `reports/phase5c_nsw1_qld1_joined_interval_table.csv`: 26,207 rows, 2020-01-01 to 2020-03-31 only.
- C2024Q4 ingestion manifests show SUCCESS for all three months (Oct/Nov/Dec 2024) for both DISPATCHREGIONSUM and DISPATCHINTERCONNECTORRES.
- The data exists in raw cache; the join has not been constructed for C2024Q4.

**Owner:** Phase 6 — EXP_001 data preparation

**Date Logged:** 2026-07-16

**Date Resolved:** —

---

### KU-013
**Question:** What dominant driver explains the large residuals in `EXP_001` after regional net imbalance is accounted for?

**Domain:** Level 2 — Grid State / Network Physics

**Status:** Partially Supported (Confidence: 66%)

**Confidence:** 66%

**Priority:** High — `EXP_001` was rejected despite strong fit, so the residual structure is now the main research lead

**Required Data:** Constraint state, interconnector limit state, and any other candidate network-physics variables for C2024Q4

**Required Experiment:** `EXP_002` — test whether constraint or network-state variables explain the residual structure better than net imbalance alone

**Evidence So Far:**
- `EXP_001` produced strong fit but failed the pre-registered directional and stability criteria.
- `EXP_002` shows that capability/utilisation variables materially improve explanatory power after imbalance is accounted for: `ΔR² = 0.303577` overall and `ΔR² = 0.535119` near limits.
- Directional accuracy remains below full dominance territory (`0.797989`), but the relationship is stable across months.
- Largest residual in `EXP_002` occurred at `2024-12-17T06:50:00Z` with `|residual| = 1435.913 MW` at `100.00%` utilisation.
- The remaining uncertainty is concentrated in binding constraints, outages, and other unobserved network-state variables.

**Owner:** Phase 6 — follow-up experiment design

**Date Logged:** 2026-07-16

**Date Resolved:** —

---

## Resolved Questions

*(To be populated as experiments are completed)*

| ID | Question (Short) | Resolved By | Date | Confidence |
|----|-----------------|------------|------|-----------|
| — | — | — | — | — |

---

## Data Acquisition Queue

Variables blocked by missing datasets. Prioritised by research impact.

| Priority | Variable | Dataset | AEMO Table | Notes |
|----------|---------|---------|-----------|-------|
| Critical | Wind %, Solar %, Coal %, Gas %, Hydro %, Battery SOC, Outage Score | DISPATCH_UNIT_SCADA | PUBLIC_DISPATCH_UNIT_SCADA | Required for STATE_001 |
| High | Constraint binding | DISPATCHCONSTRAINT | PUBLIC_DISPATCHCONSTRAINT | Required for ARROW_008 |
| High | Hydro storage levels | Snowy Hydro (external) | Not AEMO | Required for KU-002 / ARROW_014 |
| Medium | BOM temperature (hourly, 5 cities) | Bureau of Meteorology | External API | Required for ARROW_001 |
| Medium | FCAS scarcity flags | DISPATCHPRICE (FCAS columns) | PUBLIC_DISPATCHPRICE | May be in existing cache |
| Low | Industrial load proxies (QLD) | ABS/AEMO | Multiple | Required for KU-007 follow-up |

---

## Governance

- **Every arrow experiment** must check this document for relevant open questions before pre-registering criteria.
- **Every arrow result** must log any new unknowns it surfaces.
- **Residual drivers >20%** must be converted into a KU entry immediately.
- **Quarterly review:** all KU entries are assessed for reprioritisation at the start of each research phase.
