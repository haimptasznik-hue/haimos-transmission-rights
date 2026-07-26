# EXP_001 Readiness Assessment

**Assessment ID:** READY_EXP_001_v1  
**Date:** 2026-07-16  
**Experiment:** EXP_001 — LAW_001 Supply-Demand Imbalance → QNI Flow  
**Assessor:** Phase 6 Research Governance  
**Status: ✅ CONDITIONAL GO — core data confirmed; one data-prep step required before implementation**

---

## Executive Summary

EXP_001 can proceed to implementation. All core required datasets are present in the repository with confirmed ingestion success. The experiment is not blocked by missing source data.

One pre-implementation data-preparation step must be completed before the experiment script is written:

1. **Re-extract generation columns** from existing DISPATCHREGIONSUM raw zips.
2. ~~**Confirm and lock QNI sign convention** from DISPATCHINTERCONNECTORRES.~~ **Completed 2026-07-16.**

These are data-prep tasks, not new data acquisitions. They do not require touching the Digital Twin pipeline.

---

## Required Dataset Checklist

| Dataset | EXP_001 Role | In repo? | PIT safe? | Cache complete? | Blocker? |
|---|---|---|---|---|---|
| `DISPATCHREGIONSUM` raw zips | NSW/QLD demand + generation | ✅ Yes | ✅ Yes | ✅ Oct/Nov/Dec 2024 (C2024Q4) | No |
| `DISPATCHINTERCONNECTORRES` raw zips | QNI flow target | ✅ Yes | ✅ Yes | ✅ Oct/Nov/Dec 2024 (C2024Q4) | No |
| `DISPATCHREGIONSUM` normalized cache | Demand only | ✅ Yes | ✅ Yes | ✅ All months 2020–2024 | No (demand present) |
| DISPATCHABLEGENERATION (from raw) | Regional generation for net-balance | ⚠️ Not in cache — in raw zips | ✅ Yes | Requires re-extraction | **Data prep required** |
| TOTALINTERMITTENTGENERATION (from raw) | Intermittent gen component | ⚠️ Not in cache — in raw zips | ✅ Yes | Requires re-extraction | **Data prep required** |
| QNI sign convention | Directional accuracy metric | ✅ Confirmed | ✅ N/A | Locked on 2026-07-16 | No |
| Calendar features | Peak/off-peak, weekday/weekend | ✅ Derivable | ✅ Yes | Trivial to construct | No |
| Seasonal partition | Summer/winter segmentation | ✅ Derivable | ✅ Yes | Trivial to construct | No |
| `DISPATCH_UNIT_SCADA` | Wind/solar/coal controls | ❌ Not in repo | ✅ Yes if sourced | Not ingested | No — controls are optional for first pass |
| DUID fuel mapping | Control variable construction | ❌ Not in repo | ✅ Yes | Not ingested | No — optional for first pass |

---

## PIT Safety Assessment

| Dataset | PIT Risk | Assessment |
|---|---|---|
| `DISPATCHREGIONSUM` (demand) | None | Sourced from pre-dispatch settled files; publication timestamp recorded per row |
| `DISPATCHINTERCONNECTORRES` (flow) | None | Same sourcing model; publication timestamp recorded |
| C2024Q4 generation (raw re-extract) | None | Same files; generation columns are in the same source zip as demand |
| Derived calendar/seasonal features | None | All derivable from the interval timestamp; no future data required |
| Control variables (SCADA) | N/A | Not used in first-pass experiment |

**PIT verdict: CLEAN.** No look-ahead risk exists for EXP_001 core inputs. All data originates from settled dispatch files with source lineage already recorded in the joined table.

---

## Coverage Assessment

| Window | Coverage | Assessment |
|---|---|---|
| C2024Q4 (Oct 2024) | ✅ 17,856 rows ingested (DISPATCHREGIONSUM) | Full month confirmed |
| C2024Q4 (Nov 2024) | ✅ Ingestion manifest SUCCESS | Full month confirmed |
| C2024Q4 (Dec 2024) | ✅ Ingestion manifest SUCCESS | Full month confirmed |
| QNI NSW1→QLD1 corridor | ✅ 26,495/26,496 joined intervals = 99.996% | Near-perfect interval coverage |
| Historical reproducibility window (2020 Q1) | ✅ Joined interval table exists (26,207 rows) | Available for cross-period robustness test |

**Interval-level coverage verdict: SUFFICIENT.** C2024Q4 represents ~26,000+ dispatch intervals. This is adequate for seasonal subsample analysis (summer/winter, peak/off-peak, weekday/weekend).

---

## Identified Blockers and Resolutions

### Blocker 1 — Generation columns not in normalized cache (KU-009)
**Status:** Data-prep task — LOW EFFORT  
**Evidence:** Raw zip `PUBLIC_DVD_DISPATCHREGIONSUM_202001010000.zip` confirmed to contain `DISPATCHABLEGENERATION` and `TOTALINTERMITTENTGENERATION`. C2024Q4 zip confirmed downloaded and ingested (manifest SUCCESS).  
**Resolution:** Write a standalone EXP_001 data-preparation script that re-reads the raw zips for C2024Q4 only and extracts the two generation columns alongside `TOTALDEMAND`, `REGIONID`, and `SETTLEMENTDATE`. Do not modify the Digital Twin normalization pipeline.  
**Schema version check required:** Must confirm C2024Q4 header matches 2020 structure (KU-011).

### QNI Sign Convention Validation — Completed (KU-010)
**Status:** Resolved  
**Authoritative AEMO definition:**
- `DISPATCHINTERCONNECTORRES` (`Elec20.htm`): “The definition of direction of flow for an interconnector is that positive flow starts from the FROMREGION in the INTERCONNECTOR table.”
- `INTERCONNECTOR` (`Elec33.htm`): `INTERCONNECTORID`, `REGIONFROM`, `REGIONTO` define the corridor orientation.

**Canonical QNI registry entry (C2024Q4):**
- `INTERCONNECTORID`: `NSW1-QLD1`
- `REGIONFROM`: `NSW1`
- `REGIONTO`: `QLD1`

**Sign semantics locked:**
- Positive `MWFLOW`: `NSW1 -> QLD1`
- Negative `MWFLOW`: `QLD1 -> NSW1`
- Zero `MWFLOW`: no directional transfer (treat as neutral / no-flow interval)

**Raw validation (C2024Q4):**
- 20 raw `DISPATCHINTERCONNECTORRES` intervals validated (`12` positive, `8` negative, `0` zero)
- 20/20 sign-consistent with `METEREDMWFLOW` sign
- Registry orientation (`NSW1` → `QLD1`) is identical across Oct/Nov/Dec 2024 archive snapshots

**Conclusion:** QNI sign convention is fully locked for EXP_001 and no longer blocks implementation.

### Non-blocker — SCADA controls absent
**Assessment:** Controls (wind, solar, coal, battery) are classified as optional for the first-pass experiment per the pre-registered contract. EXP_001 tests whether net-balance dominates; controls are only needed to check whether net-balance *remains* dominant after adding them. The first-pass result is valid without controls. Controls become required for EXP_003.

### Non-blocker — C2024Q4 joined table not pre-built
**Assessment:** Building the C2024Q4 joined interval table is part of the EXP_001 implementation step, not a readiness gate. The raw inputs required to build it are all confirmed present.

---

## Pre-Registered Threshold Lock Confirmation

The following acceptance thresholds from `LAW_001_EXPERIMENT.md` are confirmed locked and must not be changed after implementation begins:

| Criterion | Threshold | Locked? |
|---|---|---|
| Explanatory power | R² > 0.5 on QNI primary corridor | ✅ Locked |
| Directional correctness | >90% sign accuracy | ✅ Locked |
| Rank robustness | Spearman positive across major subsamples | ✅ Locked |
| Seasonal stability | No collapse or reversal summer vs winter | ✅ Locked |
| Operational stability | Valid in peak and off-peak | ✅ Locked |
| Historical reproducibility | Holds across multiple windows when available | ✅ Locked |
| Dominance test | Net-balance remains dominant after controls | ✅ Locked |

**These thresholds are immutable from this point forward.** Any threshold change requires a new EXP_### with documented rationale and is not permitted on EXP_001.

---

## Known Unknowns Relevant to EXP_001

| KU ID | Question | Impact on EXP_001 | Action Required |
|---|---|---|---|
| KU-003 | DISPATCH_UNIT_SCADA availability | Controls only — does not block first pass | Defer to EXP_003 |
| KU-009 | Generation columns not in cache | **Blocks net-balance construction** | Re-extract from raw zips in data-prep step |
| KU-010 | QNI flow sign convention | Resolved | Closed 2026-07-16 with AEMO docs + raw interval validation |
| KU-011 | C2024Q4 schema vs 2020 schema | Resolved | Closed 2026-07-16 with Oct/Nov/Dec schema comparison |
| KU-012 | Joined table is 2020, not C2024Q4 | Understood — C2024Q4 join is the implementation step | No additional action needed |

---

## Recommended Implementation Sequence

**Phase 6B — EXP_001 implementation steps, in order:**

1. **Data-prep step:** Write `scripts/exp_001_data_preparation.py` — re-read C2024Q4 DISPATCHREGIONSUM raw zips, extract `DISPATCHABLEGENERATION`, `TOTALINTERMITTENTGENERATION`, `TOTALDEMAND`, join with `DISPATCHINTERCONNECTORRES` QNI flow, output a clean C2024Q4 experiment dataset.
2. **Experiment step:** Write `scripts/exp_001_run.py` — execute pre-registered analysis exactly as specified in `LAW_001_EXPERIMENT.md`. No deviations permitted.
3. **Result step:** Write `reports/EXP_001_RESULTS.md` — record all metrics, verdict, and any new known unknowns surfaced.

---

## Final Readiness Verdict

| Gate | Status |
|---|---|
| Core source data present | ✅ PASS |
| PIT safety confirmed | ✅ PASS |
| C2024Q4 interval coverage confirmed | ✅ PASS |
| Acceptance thresholds pre-registered and locked | ✅ PASS |
| Generation columns in analysis-ready cache | ⚠️ DATA PREP REQUIRED (not a blocker — raw data exists) |
| QNI sign convention locked | ✅ PASS |
| Digital Twin frozen (not modified) | ✅ PASS |
| SCADA controls available | ❌ NOT AVAILABLE — deferred to EXP_003 per contract |

### Decision: ✅ CONDITIONAL GO

**EXP_001 implementation may begin immediately.**  
Data-prep steps 1–3 above must be completed before the experiment script writes any analysis output. They are fast (hours, not days) and do not require new data acquisitions.

The experiment can then run exactly as pre-registered, producing a valid first-pass verdict on LAW_001.
