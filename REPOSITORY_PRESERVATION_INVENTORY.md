# REPOSITORY_PRESERVATION_INVENTORY

- Baseline commit reference: `29a7194a6820f690ad5a58644dedf77c04f8729e`
- Generated from current working tree via `git status --porcelain`
- Total paths inventoried: `210`

## Category Legend
- `A`: Source code
- `B`: Tests
- `C`: Research governance documents
- `D`: Experiment specifications
- `E`: Lightweight reports and summaries
- `F`: Large generated outputs
- `G`: Raw AEMO data
- `H`: Cache and derived datasets
- `I`: Temporary/debug/profiling
- `J`: Unknown/manual review

## Summary by Category
| Category | Count | Total Size |
|---|---:|---:|
| A (Source code) | 33 | 646.58 KB |
| B (Tests) | 5 | 21.40 KB |
| C (Research governance documents) | 25 | 233.49 KB |
| D (Experiment specifications) | 2 | 22.56 KB |
| E (Lightweight reports and summaries) | 53 | 195.81 KB |
| F (Large generated outputs) | 80 | 230.22 MB |
| G (Raw AEMO data) | 5 | 5.41 GB |
| H (Cache and derived datasets) | 3 | 8.55 MB |
| I (Temporary/debug/profiling) | 4 | 3.53 KB |
| J (Unknown/manual review) | 0 | 0 B |

## Immediate Risk Flags
- Files/directories over 10 MB: `9`
- Duplicate/superseded candidates: `18`
- Credential/token pattern matches: `8`
- Local absolute path pattern matches: `18`

### Over 10 MB
- `data/raw/aemo/mmsdm_dispatch_unit_scada/` — 397.48 MB
- `data/raw/aemo/mmsdm_dispatchconstraint/` — 4.83 GB
- `data/raw/aemo/mmsdm_dispatchinterconnectorres/` — 23.95 MB
- `data/raw/aemo/mmsdm_dispatchprice/` — 113.07 MB
- `data/raw/aemo/mmsdm_dispatchregionsum/` — 57.90 MB
- `reports/2024Q4_TRANSFER_STATE_TABLE.csv` — 52.65 MB
- `reports/EXP_001_PREPARED_DATA.csv` — 36.53 MB
- `reports/phase5c_market_state.csv` — 109.43 MB
- `reports/phase5c_nsw1_qld1_joined_interval_table.csv` — 19.01 MB

### Duplicate/Superseded Candidates (Heuristic)
- `docs/HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md`
- `reports/FORENSIC_FIRST_VIC_NSW_LOSS.md`
- `reports/PHASE5A1_WALKFORWARD_VALIDATION.md`
- `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md`
- `reports/PHASE5C8_FIRST_HISTORICAL_SRA_CONCEPT_TEST.md`
- `reports/PHASE5C_FIRST_PRINCIPLES_SUMMARY.md`
- `reports/forensic_first_vic_nsw_loss.json`
- `reports/phase5a1_walkforward_results.csv`
- `reports/phase5a_price_model_v1_component_export.csv`
- `reports/phase5a_price_model_v1_predictions.csv`
- `reports/phase5c3_first_sra_test_plan.md`
- `reports/phase5c8_first_historical_sra_concept_test.csv`
- `scripts/forensic_first_vic_nsw_loss.py`
- `scripts/phase5a1_walkforward_validation.py`
- `scripts/phase5a_price_model_v1.py`
- `scripts/phase5c_first_principles_pipeline.py`
- `src/transmission_rights/services/aemo/price_model_v1.py`
- `tests/services/aemo/test_price_model_v1.py`

### Credential/Token Pattern Matches
- `scripts/build_c2024q4_transfer_constraint_table.py`
- `scripts/mmsdm_source_utils.py`
- `scripts/phase5c_first_principles_pipeline.py`
- `scripts/source_dispatch_unit_scada.py`
- `scripts/source_dispatchconstraint.py`
- `scripts/source_dispatchinterconnectorres.py`
- `scripts/source_dispatchregionsum.py`
- `src/transmission_rights/services/aemo/market_state_database.py`

### Local Absolute Path Pattern Matches
- `reports/EXP_002_METADATA.json`
- `reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md`
- `reports/phase4b_component_validation_summary.md`
- `reports/phase5c3_unit_payout_reconciliation.csv`
- `reports/phase5c4_c2024q4_download_inventory.csv`
- `reports/phase5c4b_c2024q4_filename_compatibility.csv`
- `reports/phase5c7_payout_forensic_step_by_step.csv`
- `reports/phase5c_dispatchinterconnectorres_cache_report.md`
- `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv`
- `reports/phase5c_dispatchprice_cache_report.md`
- `reports/phase5c_dispatchprice_ingestion_manifest.csv`
- `reports/phase5c_dispatchregionsum_cache_report.md`
- `reports/phase5c_dispatchregionsum_ingestion_manifest.csv`
- `reports/phase5c_driver_attribution.csv`
- `reports/phase5c_ingestion_lineage.csv`
- `reports/phase5c_nsw1_qld1_manual_reconciliation_20.csv`
- `reports/phase5c_stage1_manual_reconciliation.csv`
- `reports/phase5c_stage23_market_state_sample.csv`

## Detailed Inventory
| Path | Category | File Size | Proposed Action | Reason | Commit Group | Reproducibility Required | Safe to Exclude from Git |
|---|---|---:|---|---|---|---|---|
| `CHIEF_RESEARCH_ANALYST_ROLE.md` | C (Research governance documents) | 18.65 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` | C (Research governance documents) | 19.94 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `PHASE6_INDEX.md` | C (Research governance documents) | 7.62 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `PHASE6_LAUNCH_CHECKLIST.md` | C (Research governance documents) | 6.63 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `PHASE6_QUICK_START.md` | C (Research governance documents) | 7.71 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `PHASE6_README.md` | C (Research governance documents) | 6.98 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `STRATEGIC_RESTRUCTURING_SUMMARY.txt` | C (Research governance documents) | 12.54 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `TOP_3_ELIGIBILITY_BLOCKERS.md` | C (Research governance documents) | 3.88 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `WHY_NO_ELIGIBLE_QUARTER.md` | C (Research governance documents) | 5.20 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `data/derived/c2024q4_transfer_constraint/` | H (Cache and derived datasets) | 1.74 MB | Preserve locally + manifest; exclude from Git | Derived/cache dataset, reproducible from pipeline | Excluded (data/cache/bulk) | Yes | Yes |
| `data/derived/correlation_library/` | H (Cache and derived datasets) | 4.16 MB | Preserve locally + manifest; exclude from Git | Derived/cache dataset, reproducible from pipeline | Excluded (data/cache/bulk) | Yes | Yes |
| `data/derived/market_state_feature_store/` | H (Cache and derived datasets) | 2.64 MB | Preserve locally + manifest; exclude from Git | Derived/cache dataset, reproducible from pipeline | Excluded (data/cache/bulk) | Yes | Yes |
| `data/raw/aemo/mmsdm_dispatch_unit_scada/` | G (Raw AEMO data) | 397.48 MB | Preserve locally + manifest; exclude from Git | Raw external source dataset (AEMO); >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `data/raw/aemo/mmsdm_dispatchconstraint/` | G (Raw AEMO data) | 4.83 GB | Preserve locally + manifest; exclude from Git | Raw external source dataset (AEMO); >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `data/raw/aemo/mmsdm_dispatchinterconnectorres/` | G (Raw AEMO data) | 23.95 MB | Preserve locally + manifest; exclude from Git | Raw external source dataset (AEMO); >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `data/raw/aemo/mmsdm_dispatchprice/` | G (Raw AEMO data) | 113.07 MB | Preserve locally + manifest; exclude from Git | Raw external source dataset (AEMO); >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `data/raw/aemo/mmsdm_dispatchregionsum/` | G (Raw AEMO data) | 57.90 MB | Preserve locally + manifest; exclude from Git | Raw external source dataset (AEMO); >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `docs/EXP_001_READINESS_ASSESSMENT.md` | E (Lightweight reports and summaries) | 9.46 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `docs/HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md` | C (Research governance documents) | 2.63 KB | Commit | Program governance/architecture context; possible_v1_superseded | Commit 1 | Yes | No |
| `docs/KNOWN_UNKNOWNS.md` | C (Research governance documents) | 17.33 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/LAW_001_EXPERIMENT.md` | D (Experiment specifications) | 11.54 KB | Commit | Pre-registered experiment contract | Commit 4 | Yes | No |
| `docs/LAW_002_EXPERIMENT.md` | D (Experiment specifications) | 11.02 KB | Commit | Pre-registered experiment contract | Commit 4 | Yes | No |
| `docs/MARKET_INTELLIGENCE_V2_CHARTER.md` | C (Research governance documents) | 1.49 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/MARKET_PHYSICS_KNOWLEDGE_GRAPH.md` | C (Research governance documents) | 10.93 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/MARKET_PHYSICS_MANIFESTO.md` | C (Research governance documents) | 5.42 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/MARKET_PHYSICS_MODEL.md` | C (Research governance documents) | 12.20 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/MARKET_PHYSICS_RESEARCH_LOG.md` | C (Research governance documents) | 3.31 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/MARKET_PHYSICS_THEORY.md` | C (Research governance documents) | 8.31 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/NEM_DATA_COVERAGE_MATRIX.md` | C (Research governance documents) | 10.91 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/NEM_STATE_DEPENDENCY_MAP.md` | C (Research governance documents) | 9.99 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/NEM_STATE_VECTOR.md` | C (Research governance documents) | 23.50 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/PHASE6A_RECOMMENDATIONS.md` | C (Research governance documents) | 13.45 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/PHASE_6B_0_RESEARCH_PROGRAM_DESIGN.md` | C (Research governance documents) | 9.56 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/RESEARCH_CYCLE_001A_BRIEF.md` | C (Research governance documents) | 5.24 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/Research Journal.md` | C (Research governance documents) | 8.92 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `docs/roadmap.md` | C (Research governance documents) | 1.15 KB | Commit | Program governance/architecture context | Commit 1 | Yes | No |
| `reports/2024Q4_TRANSFER_STATE_INTERVENTION_AUDIT.csv` | F (Large generated outputs) | 7.87 MB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/2024Q4_TRANSFER_STATE_METADATA.json` | E (Lightweight reports and summaries) | 4.28 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/2024Q4_TRANSFER_STATE_QUALITY.md` | E (Lightweight reports and summaries) | 567 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/2024Q4_TRANSFER_STATE_TABLE.csv` | F (Large generated outputs) | 52.65 MB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/AUDIT_EXECUTIVE_SUMMARY.txt` | E (Lightweight reports and summaries) | 6.63 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/AUDIT_SUMMARY_CRITICAL_FINDINGS.md` | E (Lightweight reports and summaries) | 11.23 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/CRITICAL_VIC_NSW_CORRIDOR_ANALYSIS.md` | E (Lightweight reports and summaries) | 5.68 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/DECISION_MEMO.md` | E (Lightweight reports and summaries) | 6.95 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/EXP_001_DATA_QUALITY.md` | E (Lightweight reports and summaries) | 586 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/EXP_001_PREPARED_DATA.csv` | F (Large generated outputs) | 36.53 MB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/EXP_001_RESULTS.csv` | F (Large generated outputs) | 331 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/EXP_001_RESULTS.md` | E (Lightweight reports and summaries) | 1.06 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/EXP_002_INTERVENTION_SENSITIVITY.csv` | F (Large generated outputs) | 838 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/EXP_002_METADATA.json` | E (Lightweight reports and summaries) | 492 B | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/EXP_002_RESULTS.csv` | F (Large generated outputs) | 1.39 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/EXP_002_RESULTS.md` | E (Lightweight reports and summaries) | 2.53 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/FILTERED_BACKTEST_ANALYSIS.md` | E (Lightweight reports and summaries) | 9.37 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/FILTERED_BACKTEST_QUICK_REFERENCE.md` | E (Lightweight reports and summaries) | 5.14 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/FORECAST_CONTRIBUTION_REGISTER.csv` | F (Large generated outputs) | 1.79 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/FORENSIC_FIRST_VIC_NSW_LOSS.md` | E (Lightweight reports and summaries) | 1.10 KB | Commit (concise artifact) | Human-readable concise outcome/report; possible_first_vs_final | Commit 5 | Yes | No |
| `reports/PHASE4B_FORENSIC_LARGEST_LOSSES.md` | E (Lightweight reports and summaries) | 5.76 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4B_QUANT_RESEARCH_SUMMARY.md` | E (Lightweight reports and summaries) | 1.72 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4B_README.md` | E (Lightweight reports and summaries) | 2.31 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4_COMPREHENSIVE_ANALYSIS.md` | E (Lightweight reports and summaries) | 11.31 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4_INDEX.md` | E (Lightweight reports and summaries) | 9.95 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4_ROOT_CAUSE_ATTRIBUTION.md` | E (Lightweight reports and summaries) | 5.93 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE4_SUMMARY.md` | E (Lightweight reports and summaries) | 9.32 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5A1_WALKFORWARD_VALIDATION.md` | E (Lightweight reports and summaries) | 3.65 KB | Commit (concise artifact) | Human-readable concise outcome/report; possible_iteration_superseded | Commit 5 | Yes | No |
| `reports/PHASE5A2_PRICE_MODEL_V2_SUMMARY.md` | E (Lightweight reports and summaries) | 2.62 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5A_FORENSIC_LARGEST_LOSSES.md` | E (Lightweight reports and summaries) | 5.76 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5A_PRICE_MODEL_DATA_AUDIT.md` | E (Lightweight reports and summaries) | 2.16 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5A_PRICE_MODEL_V1_SUMMARY.md` | E (Lightweight reports and summaries) | 2.07 KB | Commit (concise artifact) | Human-readable concise outcome/report; possible_v1_superseded | Commit 5 | Yes | No |
| `reports/PHASE5B_DATA_ACQUISITION.md` | E (Lightweight reports and summaries) | 3.68 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5B_DRIVER_DISCOVERY_SUMMARY.md` | E (Lightweight reports and summaries) | 7.89 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5C3_READINESS_SUMMARY.md` | E (Lightweight reports and summaries) | 442 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md` | E (Lightweight reports and summaries) | 4.40 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/PHASE5C5_DISPATCHPRICE_BULKLOAD_FIX.md` | E (Lightweight reports and summaries) | 1.52 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5C8_FINAL_READINESS.md` | E (Lightweight reports and summaries) | 490 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/PHASE5C8_FIRST_HISTORICAL_SRA_CONCEPT_TEST.md` | E (Lightweight reports and summaries) | 612 B | Commit (concise artifact) | Human-readable concise outcome/report; possible_first_vs_final | Commit 5 | Yes | No |
| `reports/PHASE5C_FIRST_PRINCIPLES_SUMMARY.md` | E (Lightweight reports and summaries) | 1.43 KB | Commit (concise artifact) | Human-readable concise outcome/report; possible_first_vs_final | Commit 5 | Yes | No |
| `reports/README_BACKTEST_AUDIT.md` | E (Lightweight reports and summaries) | 6.63 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/backtest_audit_detailed.md` | E (Lightweight reports and summaries) | 4.90 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/backtest_detailed_trades.csv` | F (Large generated outputs) | 221.75 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/backtest_monthly_summary.csv` | F (Large generated outputs) | 1.80 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/filtered_baseline.txt` | E (Lightweight reports and summaries) | 676 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/forensic_first_vic_nsw_loss.json` | F (Large generated outputs) | 876 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; possible_first_vs_final | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/iteration2_scenarios.csv` | F (Large generated outputs) | 636 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/iteration2_scenarios.md` | E (Lightweight reports and summaries) | 705 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/jan_2025_capital_constrained.csv` | F (Large generated outputs) | 1.96 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/jan_2025_predicted_vs_actual.csv` | F (Large generated outputs) | 2.21 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/jan_2025_proof_of_concept.md` | E (Lightweight reports and summaries) | 4.08 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase4_grouped_attribution.csv` | F (Large generated outputs) | 94.94 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4_trade_level_attribution.csv` | F (Large generated outputs) | 356.01 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_blocked_reasons.csv` | F (Large generated outputs) | 274.74 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_completeness_by_trade.csv` | F (Large generated outputs) | 67.88 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_coverage_by_corridor.csv` | F (Large generated outputs) | 155 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_coverage_by_tranche.csv` | F (Large generated outputs) | 365 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_export_from_alpha.csv` | F (Large generated outputs) | 317.91 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_export_template.csv` | F (Large generated outputs) | 549 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_row_diagnostics.csv` | F (Large generated outputs) | 362.80 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_validated_for_attribution.csv` | F (Large generated outputs) | 143 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_component_validation_summary.md` | E (Lightweight reports and summaries) | 1.68 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase4b_error_waterfall.csv` | F (Large generated outputs) | 269 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_forecast_maturity.csv` | F (Large generated outputs) | 218 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_grouped_attribution.csv` | F (Large generated outputs) | 8.16 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_ranked_missing_fields_by_value.csv` | F (Large generated outputs) | 1.95 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_ranked_model_improvements.csv` | F (Large generated outputs) | 472 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_rd_roi_table.csv` | F (Large generated outputs) | 291 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase4b_trade_level_attribution.csv` | F (Large generated outputs) | 579.50 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a1_walkforward_results.csv` | F (Large generated outputs) | 293.39 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; possible_iteration_superseded | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a2_corridor_results.csv` | F (Large generated outputs) | 903 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a2_walkforward_results.csv` | F (Large generated outputs) | 348.16 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a_grouped_attribution.csv` | F (Large generated outputs) | 8.16 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a_price_model_v1_component_export.csv` | F (Large generated outputs) | 401.67 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; possible_v1_superseded | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a_price_model_v1_predictions.csv` | F (Large generated outputs) | 639.54 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; possible_v1_superseded | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a_ranked_model_improvements.csv` | F (Large generated outputs) | 472 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5a_trade_level_attribution.csv` | F (Large generated outputs) | 515.55 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_correlation_matrix.csv` | F (Large generated outputs) | 10.80 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_driver_catalogue.csv` | F (Large generated outputs) | 9.62 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_driver_ranking.csv` | F (Large generated outputs) | 1.11 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_interaction_report.csv` | F (Large generated outputs) | 8.06 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_quarterly_features.csv` | F (Large generated outputs) | 52.49 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5b_regime_report.csv` | F (Large generated outputs) | 3.70 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c3_first_sra_test_plan.md` | E (Lightweight reports and summaries) | 591 B | Commit (concise artifact) | Human-readable concise outcome/report; possible_first_vs_final | Commit 5 | Yes | No |
| `reports/phase5c3_interval_validation.csv` | F (Large generated outputs) | 262 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c3_physical_driver_correlations.csv` | F (Large generated outputs) | 170 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c3_quarterly_reconciliation.csv` | F (Large generated outputs) | 820 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c3_test_quarter_selection.md` | E (Lightweight reports and summaries) | 3.80 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase5c3_unit_payout_reconciliation.csv` | F (Large generated outputs) | 2.65 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c4_c2024q4_download_inventory.csv` | E (Lightweight reports and summaries) | 9.88 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c4_c2024q4_source_inventory.csv` | E (Lightweight reports and summaries) | 117 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase5c4b_c2024q4_cache_summary.md` | E (Lightweight reports and summaries) | 939 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase5c4b_c2024q4_eligibility.json` | E (Lightweight reports and summaries) | 484 B | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase5c4b_c2024q4_filename_compatibility.csv` | F (Large generated outputs) | 3.66 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c4b_c2024q4_market_state_coverage.csv` | F (Large generated outputs) | 653 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c5_dispatchprice_bulkload_profile.csv` | I (Temporary/debug/profiling) | 277 B | Preserve locally + manifest; exclude from Git | Profiling/debug by-product | Excluded (data/cache/bulk) | No | Yes |
| `reports/phase5c6_supported_sra_corridor_mapping.csv` | F (Large generated outputs) | 1.12 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_corridor.csv` | F (Large generated outputs) | 29 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_from_region.csv` | F (Large generated outputs) | 32 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_interconnector_id.csv` | F (Large generated outputs) | 38 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_month.csv` | F (Large generated outputs) | 53 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_source_file.csv` | F (Large generated outputs) | 34 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_by_to_region.csv` | F (Large generated outputs) | 30 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_direction_summary.csv` | F (Large generated outputs) | 123 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c6_unknown_sample_50.csv` | F (Large generated outputs) | 2.70 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c7_payout_forensic_step_by_step.csv` | F (Large generated outputs) | 2.41 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c7_payout_variance_decomposition.csv` | F (Large generated outputs) | 673 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c8_first_historical_sra_concept_test.csv` | F (Large generated outputs) | 661 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; possible_first_vs_final | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c8_missing_interval_diagnostic.csv` | F (Large generated outputs) | 919 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_dispatchinterconnectorres_cache_report.md` | E (Lightweight reports and summaries) | 640 B | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_dispatchinterconnectorres_failed_files.csv` | F (Large generated outputs) | 162 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` | E (Lightweight reports and summaries) | 3.42 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_dispatchprice_cache_report.md` | E (Lightweight reports and summaries) | 604 B | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_dispatchprice_failed_files.csv` | F (Large generated outputs) | 162 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_dispatchprice_ingestion_manifest.csv` | E (Lightweight reports and summaries) | 3.06 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_dispatchregionsum_cache_report.md` | E (Lightweight reports and summaries) | 616 B | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_dispatchregionsum_failed_files.csv` | F (Large generated outputs) | 162 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_dispatchregionsum_ingestion_manifest.csv` | E (Lightweight reports and summaries) | 3.21 KB | Commit (concise artifact) | Human-readable concise outcome/report; contains local absolute path pattern | Commit 5 | Yes | No |
| `reports/phase5c_driver_attribution.csv` | F (Large generated outputs) | 604 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_feature_store_nsw1_qld1.csv` | F (Large generated outputs) | 177.97 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_ingestion_lineage.csv` | F (Large generated outputs) | 698 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_ingestion_validation.csv` | F (Large generated outputs) | 283 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_market_state.csv` | F (Large generated outputs) | 109.43 MB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_market_state_schema.csv` | E (Lightweight reports and summaries) | 1.92 KB | Commit (concise artifact) | Human-readable concise outcome/report | Commit 5 | Yes | No |
| `reports/phase5c_nsw1_qld1_correlation_report.csv` | F (Large generated outputs) | 167 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_nsw1_qld1_demand_trace_20.csv` | F (Large generated outputs) | 2.17 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_nsw1_qld1_joined_interval_table.csv` | F (Large generated outputs) | 19.01 MB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; >10MB flagged | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_nsw1_qld1_manual_reconciliation_20.csv` | F (Large generated outputs) | 15.55 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_nsw1_qld1_validation_diagnostics.json` | F (Large generated outputs) | 475 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_pit_coverage_report.csv` | F (Large generated outputs) | 188 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_profile_bottleneck.json` | I (Temporary/debug/profiling) | 358 B | Preserve locally + manifest; exclude from Git | Profiling/debug by-product | Excluded (data/cache/bulk) | No | Yes |
| `reports/phase5c_stage1_manual_reconciliation.csv` | F (Large generated outputs) | 10.56 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_stage23_market_state_sample.csv` | F (Large generated outputs) | 21.90 KB | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact; contains local absolute path pattern | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/phase5c_stage_profile.csv` | I (Temporary/debug/profiling) | 513 B | Preserve locally + manifest; exclude from Git | Profiling/debug by-product | Excluded (data/cache/bulk) | No | Yes |
| `reports/phase5c_walkforward_results.csv` | F (Large generated outputs) | 236 B | Preserve locally + manifest; exclude from Git | Bulk generated tabular artifact | Excluded (data/cache/bulk) | Yes | Yes |
| `reports/scalability_analysis.txt` | I (Temporary/debug/profiling) | 2.41 KB | Preserve locally + manifest; exclude from Git | Profiling/debug by-product | Excluded (data/cache/bulk) | No | Yes |
| `scripts/backtest_audit_detailed.py` | A (Source code) | 18.95 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/backtest_capital_constrained.py` | A (Source code) | 11.40 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/backtest_filtered_corridors.py` | A (Source code) | 10.42 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/backtest_iteration_scenarios.py` | A (Source code) | 8.98 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/build_c2024q4_transfer_constraint_table.py` | A (Source code) | 21.33 KB | Commit | Executable project code changes; credential/token pattern match | Commit 4 | Yes | No |
| `scripts/build_correlation_ready_dataset.py` | A (Source code) | 2.10 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/build_market_state_feature_store.py` | A (Source code) | 1.92 KB | Commit | Executable project code changes | Commit 2 | Yes | No |
| `scripts/exp_001_data_preparation.py` | A (Source code) | 13.47 KB | Commit | Executable project code changes | Commit 4 | Yes | No |
| `scripts/exp_001_run.py` | A (Source code) | 9.28 KB | Commit | Executable project code changes | Commit 4 | Yes | No |
| `scripts/exp_002_run.py` | A (Source code) | 21.65 KB | Commit | Executable project code changes | Commit 4 | Yes | No |
| `scripts/forensic_first_vic_nsw_loss.py` | A (Source code) | 5.51 KB | Commit | Executable project code changes; possible_first_vs_final | Commit 3 | Yes | No |
| `scripts/jan_2025_proof_of_concept.py` | A (Source code) | 17.12 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/mmsdm_source_utils.py` | A (Source code) | 4.36 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `scripts/phase4_root_cause_attribution.py` | A (Source code) | 7.61 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase4b_component_validator.py` | A (Source code) | 17.40 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase4b_error_attribution.py` | A (Source code) | 20.82 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase4b_research_analyst.py` | A (Source code) | 11.20 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase5a1_walkforward_validation.py` | A (Source code) | 24.94 KB | Commit | Executable project code changes; possible_iteration_superseded | Commit 3 | Yes | No |
| `scripts/phase5a2_walkforward_validation.py` | A (Source code) | 20.69 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase5a_price_model_v1.py` | A (Source code) | 18.95 KB | Commit | Executable project code changes; possible_v1_superseded | Commit 3 | Yes | No |
| `scripts/phase5b_driver_discovery.py` | A (Source code) | 29.15 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `scripts/phase5c_first_principles_pipeline.py` | A (Source code) | 102.20 KB | Commit | Executable project code changes; possible_first_vs_final; credential/token pattern match | Commit 3 | Yes | No |
| `scripts/source_dispatch_unit_scada.py` | A (Source code) | 4.92 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `scripts/source_dispatchconstraint.py` | A (Source code) | 5.54 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `scripts/source_dispatchinterconnectorres.py` | A (Source code) | 7.46 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `scripts/source_dispatchregionsum.py` | A (Source code) | 7.06 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `scripts/test_scalability.py` | B (Tests) | 3.67 KB | Commit | Automated verification coverage | Commit 3 | Yes | No |
| `src/transmission_rights/services/aemo/dataset_library.py` | A (Source code) | 16.83 KB | Commit | Executable project code changes | Commit 2 | Yes | No |
| `src/transmission_rights/services/aemo/driver_catalogue.py` | A (Source code) | 26.20 KB | Commit | Executable project code changes | Commit 4 | Yes | No |
| `src/transmission_rights/services/aemo/market_state_database.py` | A (Source code) | 117.67 KB | Commit | Executable project code changes; credential/token pattern match | Commit 2 | Yes | No |
| `src/transmission_rights/services/aemo/market_state_feature_store.py` | A (Source code) | 22.05 KB | Commit | Executable project code changes | Commit 2 | Yes | No |
| `src/transmission_rights/services/aemo/phase5c_pipeline.py` | A (Source code) | 10.22 KB | Commit | Executable project code changes | Commit 2 | Yes | No |
| `src/transmission_rights/services/aemo/price_model_v1.py` | A (Source code) | 14.54 KB | Commit | Executable project code changes; possible_v1_superseded | Commit 3 | Yes | No |
| `src/transmission_rights/services/aemo/price_model_v2.py` | A (Source code) | 14.66 KB | Commit | Executable project code changes | Commit 3 | Yes | No |
| `tests/services/aemo/test_dataset_library.py` | B (Tests) | 4.78 KB | Commit | Automated verification coverage | Commit 3 | Yes | No |
| `tests/services/aemo/test_market_state_database.py` | B (Tests) | 7.88 KB | Commit | Automated verification coverage | Commit 3 | Yes | No |
| `tests/services/aemo/test_market_state_feature_store.py` | B (Tests) | 2.26 KB | Commit | Automated verification coverage | Commit 3 | Yes | No |
| `tests/services/aemo/test_price_model_v1.py` | B (Tests) | 2.81 KB | Commit | Automated verification coverage; possible_v1_superseded | Commit 3 | Yes | No |

## Manual Review Required
- None auto-flagged by current rules.

## Historical Feature Store v1.0 Local Bulk Artifact Manifest

Generation command baseline:
- `python scripts/historical_build_manager.py start --start-date 2020-01-01 --output-dir data/derived/historical_feature_store`

| Path | Size (bytes) | SHA-256 | Row Count | Date Range | Schema Version | Required for Exact Reproduction | Stored Locally Only |
|---|---:|---|---:|---|---|---|---|
| `data/derived/historical_feature_store/historical_market_feature_store_5min.csv.gz` | 11,989,403 | `3d331a002edd78cb33cb2da6faaedea17d6cdf99ca0bb8b844dc1be61dd45810` | 691,106 | `2020-01-01..2026-07-27` | `5bd6bd9423870ac8` | Yes | Yes |
| `data/derived/historical_feature_store/historical_dataset_status.csv` | 61,178 | `22bd0c4beb292e70f7f4e3760f62a7d73c11b58787a51b9fc40800375e6eb7d7` | 790 | `2020-01-01..2026-07-27` | `n/a` | Yes | Yes |
| `data/derived/historical_feature_store/historical_intervention_audit.csv` | 8,908,758 | `93400e47a2283ee0e33656620ecac3f3e6b6d151f5acf5d01c1f949ac84c330c` | 212,544 | `2020-01-01..2026-07-27` | `INTERVENTION_AUDIT_COLUMNS` | Yes | Yes |
| `data/derived/historical_feature_store/checkpoints` | 72,886,710 | `18d494a35cc1fe7ce36e8face6d5c775146be4a3ee2a41ec94d58b1973b66591` | 691,106 | `2020-01-01..2026-07-27` | `monthly checkpoint schema` | Yes | Yes |
| `MONTHLY_BUILD_STATUS.csv` | 10,178 | `503f8999e77902231b206caa84625853cbf4e06d80a0975df711203755c516d3` | 79 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |
| `MONTHLY_DATASET_COVERAGE.csv` | 54,684 | `a3365334cb9bb58e34f9127eda8aba11f248f90ce8dcbe073a4f52aa57235f0e` | 790 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |
| `MONTHLY_QUALITY_REPORT.csv` | 4,666 | `c4549fd6cba471ef3e4faf2d4879a331b3ec6e63ecbe028b83fa6d4bacf0cec4` | 79 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |
| `MONTHLY_LINEAGE_REPORT.csv` | 38,494 | `9187cfe7fdf087961d5ccb06232e079177eb481201287a1527ab2a74bde1b366` | 790 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |
| `MONTHLY_SCHEMA_REPORT.csv` | 32,191 | `6bbed9847563ebd19e3750a0c75c47e4719120543d0cee81e18682212548f991` | 79 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |
| `MONTHLY_BUILD_CHECKPOINTS.csv` | 36,317 | `8828d3e955bf3e6c90e45efcab0233219a96bbc31a2a34b18f692bf278599524` | 79 | `2020-01-01..2026-07-27` | `report schema` | Yes | No |