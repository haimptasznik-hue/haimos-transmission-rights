# ARTIFACT_RETENTION_REVIEW.md

- Review date: 2026-07-26
- Reviewer: automated audit (Task 2 — Repository Ignore Policy and Sensitive-Content Review)
- Baseline: REPOSITORY_PRESERVATION_INVENTORY.md (commit `29a7194a6820f690ad5a58644dedf77c04f8729e`)
- Candidates flagged by heuristic: 18
- Heuristic labels applied: `possible_v1_superseded`, `possible_iteration_superseded`, `possible_first_vs_final`

> Note: the inventory header reports "10 duplicate/superseded candidates" under _Immediate Risk Flags_ but the detailed list contains 18 entries. This review covers all 18.

---

## Recommendation Legend

| Recommendation | Meaning |
|---|---|
| **COMMIT** | Unique historical evidence — include in Git |
| **COMMIT (v1 archive)** | V1 model preserved alongside V2; retains historical comparability |
| **IGNORE (bulk excluded)** | Already proposed for gitignore; retain locally |
| **IGNORE (superseded bulk)** | Superseded iteration output, also already excluded from Git |

---

## Per-Artifact Findings

### Heuristic label: `possible_v1_superseded`

These artifacts relate to Price Model V1, which has been succeeded by Price Model V2 (`price_model_v2.py`, `PHASE5A2_PRICE_MODEL_V2_SUMMARY.md`).

---

#### 1. `docs/HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md`
- **Category:** C — Research governance document
- **Size:** 2.63 KB
- **Is it unique evidence?** Yes. It records the design rationale of the V1 architecture at a specific point in time. The V2 architecture supersedes the implementation but not the historical record of V1's design intent.
- **Is it superseded?** Partially. V2 architecture is not documented separately; V1 document retains comparative and audit value.
- **Recommendation:** **COMMIT** — retain as historical governance evidence. The document is concise (2.63 KB) and will not bloat the repository.

---

#### 2. `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md`
- **Category:** E — Lightweight report
- **Size:** 2.07 KB
- **Is it unique evidence?** Yes. Records the V1 model's performance metrics and findings. V2 results (`PHASE5A2_PRICE_MODEL_V2_SUMMARY.md`) do not replace V1 findings — they extend them.
- **Is it superseded?** V1 results are superseded by V2 for current decision-making but are retained for research lineage.
- **Recommendation:** **COMMIT** — unique historical evidence; concise.

---

#### 3. `reports/phase5a_price_model_v1_component_export.csv`
- **Category:** F — Large generated output
- **Size:** 401.67 KB
- **Is it unique evidence?** Marginal. The component export for V1 is reproducible by rerunning `scripts/phase5a_price_model_v1.py` against the same input data.
- **Is it superseded?** Yes — V2 component exports would supersede this for current use.
- **Recommendation:** **IGNORE (superseded bulk)** — already excluded from Git. Retain locally for local reproducibility verification if needed; do not commit.

---

#### 4. `reports/phase5a_price_model_v1_predictions.csv`
- **Category:** F — Large generated output
- **Size:** 639.54 KB
- **Is it unique evidence?** Marginal. Reproducible from V1 model and input data.
- **Is it superseded?** Yes — V2 predictions are current.
- **Recommendation:** **IGNORE (superseded bulk)** — already excluded from Git. Retain locally.

---

#### 5. `scripts/phase5a_price_model_v1.py`
- **Category:** A — Source code
- **Size:** 18.95 KB
- **Is it unique evidence?** Yes. This is the V1 model implementation. It serves as the reference point against which V2 improvements were measured and is required for reproducibility of all V1-period backtest results.
- **Is it superseded?** Superseded for production use but not for historical reproducibility.
- **Recommendation:** **COMMIT** — essential for audit trail and reproducibility of V1-period results.

---

#### 6. `src/transmission_rights/services/aemo/price_model_v1.py`
- **Category:** A — Source code
- **Size:** 14.54 KB
- **Is it unique evidence?** Yes. This is the library-form V1 model (as opposed to the script form). It is imported by tests and may differ from the script version.
- **Is it superseded?** Superseded for production use; V2 exists at `price_model_v2.py`.
- **Recommendation:** **COMMIT (v1 archive)** — retain alongside V2 for regression baseline; tests still reference it.

---

#### 7. `tests/services/aemo/test_price_model_v1.py`
- **Category:** B — Tests
- **Size:** 2.81 KB
- **Is it unique evidence?** Yes. These tests verify V1 model behaviour. They remain the only automated guard against V1 regressions and are needed for full test suite coverage.
- **Is it superseded?** Not superseded — no V2 tests cover V1 behaviour.
- **Recommendation:** **COMMIT** — active test coverage; must not be dropped.

---

### Heuristic label: `possible_iteration_superseded`

These artifacts relate to Phase 5A Iteration 1 (walkforward), succeeded by Iteration 2 (`phase5a2_walkforward_validation.py`, `phase5a2_walkforward_results.csv`).

---

#### 8. `reports/PHASE5A1_WALKFORWARD_VALIDATION.md`
- **Category:** E — Lightweight report
- **Size:** 3.65 KB
- **Is it unique evidence?** Yes. Documents the specific findings, parameter choices, and limitations of the Iteration 1 walkforward. Iteration 2's report does not reproduce this content.
- **Is it superseded?** Results are superseded by Iteration 2 for current modelling but are retained for research lineage.
- **Recommendation:** **COMMIT** — historical research evidence; concise.

---

#### 9. `reports/phase5a1_walkforward_results.csv`
- **Category:** F — Large generated output
- **Size:** 293.39 KB
- **Is it unique evidence?** Marginal. Reproducible from `scripts/phase5a1_walkforward_validation.py` and input data.
- **Is it superseded?** Yes — `phase5a2_walkforward_results.csv` supersedes for current use.
- **Recommendation:** **IGNORE (superseded bulk)** — already excluded from Git. Retain locally.

---

#### 10. `scripts/phase5a1_walkforward_validation.py`
- **Category:** A — Source code
- **Size:** 24.94 KB
- **Is it unique evidence?** Yes. The Iteration 1 walkforward implementation differs meaningfully from Iteration 2 (different feature construction, different CV strategy). Required for reproducibility of Iteration 1 results.
- **Is it superseded?** Superseded for new research; not for reproducibility.
- **Recommendation:** **COMMIT** — required for historical reproducibility of Iteration 1 results.

---

### Heuristic label: `possible_first_vs_final`

These artifacts are labelled as possible first-pass artifacts that may have been superseded by a final version.

---

#### 11. `reports/FORENSIC_FIRST_VIC_NSW_LOSS.md`
- **Category:** E — Lightweight report
- **Size:** 1.10 KB
- **Is it unique evidence?** Yes. Records the first forensic reconstruction of the VIC1-NSW1 loss, establishing the starting point of the root-cause attribution chain. Later reports (`PHASE4_ROOT_CAUSE_ATTRIBUTION.md`, `backtest_audit_detailed.md`) build on this first reconstruction.
- **Recommendation:** **COMMIT** — unique evidence of the first divergence identified; essential to Phase 4 narrative.

---

#### 12. `reports/PHASE5C8_FIRST_HISTORICAL_SRA_CONCEPT_TEST.md`
- **Category:** E — Lightweight report
- **Size:** 612 B
- **Is it unique evidence?** Yes. Documents the first-ever historical SRA concept test result and its readiness conditions. `PHASE5C8_FINAL_READINESS.md` confirms final readiness but does not reproduce the initial test narrative.
- **Recommendation:** **COMMIT** — unique first-test evidence; 612 B.

---

#### 13. `reports/PHASE5C_FIRST_PRINCIPLES_SUMMARY.md`
- **Category:** E — Lightweight report
- **Size:** 1.43 KB
- **Is it unique evidence?** Yes. Summarises the first-principles pipeline methodology. No later document replaces it.
- **Recommendation:** **COMMIT** — unique methodological summary.

---

#### 14. `reports/forensic_first_vic_nsw_loss.json`
- **Category:** F — Generated output
- **Size:** 876 B
- **Is it unique evidence?** Yes in content, but it is a machine-readable companion to `FORENSIC_FIRST_VIC_NSW_LOSS.md`. The markdown document provides the human-readable narrative; the JSON provides the structured data backing it.
- **Is it superseded?** The JSON output is reproducible by rerunning `scripts/forensic_first_vic_nsw_loss.py`. It adds limited auditability beyond the markdown.
- **Recommendation:** **IGNORE (bulk excluded)** — already excluded from Git. The markdown companion is committed and provides sufficient evidence. Retain locally.

---

#### 15. `reports/phase5c3_first_sra_test_plan.md`
- **Category:** E — Lightweight report
- **Size:** 591 B
- **Is it unique evidence?** Yes. This is the pre-registered test plan for the first SRA concept test (Phase 5C.3). It is the planning document that preceded the actual test results.
- **Is it superseded?** The test plan has been executed and is documented by the results, but the plan itself is distinct evidence of pre-registration intent.
- **Recommendation:** **COMMIT** — concise pre-registered test plan; 591 B.

---

#### 16. `reports/phase5c8_first_historical_sra_concept_test.csv`
- **Category:** F — Generated output
- **Size:** 661 B
- **Is it unique evidence?** Marginal. Reproducible from the pipeline. Human-readable summary is in the companion `.md`.
- **Recommendation:** **IGNORE (bulk excluded)** — already excluded from Git. Retain locally.

---

#### 17. `scripts/forensic_first_vic_nsw_loss.py`
- **Category:** A — Source code
- **Size:** 5.51 KB
- **Is it unique evidence?** Yes. This script implements the forensic reconstruction logic for the first VIC1-NSW1 loss. It is referenced by the Phase 4 root-cause attribution narrative and required for reproducibility of `forensic_first_vic_nsw_loss.json`.
- **Recommendation:** **COMMIT** — required for reproducibility of key forensic evidence.

---

#### 18. `scripts/phase5c_first_principles_pipeline.py`
- **Category:** A — Source code
- **Size:** 102.20 KB (largest source file in the working tree)
- **Is it unique evidence?** Yes. This is the primary Phase 5C pipeline implementation. Despite the `first_principles` naming, it is **not** a superseded draft — it is the production pipeline that generated `phase5c_market_state.csv`, all ingestion manifests, and all Stage 1–3 reconciliation outputs.
- **Is it superseded?** No. No successor pipeline exists in the working tree. The label `possible_first_vs_final` appears to be a false-positive heuristic match on the word "first" in the filename.
- **Recommendation:** **COMMIT** — active production pipeline; essential to the project.

---

## Summary

### Recommend COMMIT (14 artifacts)

| Artifact | Rationale |
|---|---|
| `docs/HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md` | V1 design governance; historical comparability |
| `reports/FORENSIC_FIRST_VIC_NSW_LOSS.md` | First VIC1-NSW1 forensic record; unique audit evidence |
| `reports/PHASE5A1_WALKFORWARD_VALIDATION.md` | Iteration 1 research record; historical lineage |
| `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md` | V1 model results; historical lineage |
| `reports/PHASE5C8_FIRST_HISTORICAL_SRA_CONCEPT_TEST.md` | First SRA concept test summary |
| `reports/PHASE5C_FIRST_PRINCIPLES_SUMMARY.md` | Pipeline methodology summary |
| `reports/phase5c3_first_sra_test_plan.md` | Pre-registered test plan |
| `scripts/forensic_first_vic_nsw_loss.py` | Forensic reconstruction script; reproducibility |
| `scripts/phase5a1_walkforward_validation.py` | Iteration 1 implementation; reproducibility |
| `scripts/phase5a_price_model_v1.py` | V1 model script; reproducibility of V1 backtests |
| `scripts/phase5c_first_principles_pipeline.py` | Active production pipeline (not superseded) |
| `src/transmission_rights/services/aemo/price_model_v1.py` | V1 library; regression baseline for tests |
| `tests/services/aemo/test_price_model_v1.py` | Active test coverage of V1 model |

*Note: `reports/phase4b_component_validation_summary.md` is not in the 18-candidate list but is proposed for commit with portability remediation.*

### Recommend IGNORE — superseded bulk outputs (3 artifacts)

| Artifact | Rationale |
|---|---|
| `reports/forensic_first_vic_nsw_loss.json` | Machine-readable companion; markdown committed; reproducible |
| `reports/phase5a1_walkforward_results.csv` | Superseded by Iteration 2 results; reproducible |
| `reports/phase5a_price_model_v1_predictions.csv` | Superseded by V2 predictions; reproducible |
| `reports/phase5a_price_model_v1_component_export.csv` | Superseded by V2 exports; reproducible |
| `reports/phase5c8_first_historical_sra_concept_test.csv` | Companion to committed markdown; reproducible |

*(5 IGNORE entries — heuristic list had 18 candidates total, only 3–5 are bulk outputs; the rest are committed.)*

---

## Unresolved Items

None. All 18 candidates have been assessed and classified. No manual review is required beyond the portability remediation identified in `PORTABILITY_REVIEW.md`.
