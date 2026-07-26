# PORTABILITY_REVIEW.md

- Review date: 2026-07-26
- Reviewer: automated audit (Task 2 — Repository Ignore Policy and Sensitive-Content Review)
- Baseline: REPOSITORY_PRESERVATION_INVENTORY.md (commit `29a7194a6820f690ad5a58644dedf77c04f8729e`)
- Files flagged with `/Users/...` occurrences: 18
- Username embedded: `haimptasznik`
- Repo-root prefix embedded: `/Users/haimptasznik/Desktop/haimos-transmission-rights-repo`

---

## Classification Legend

| Class | Meaning | Action |
|---|---|---|
| **IGNORE** | Generated report or bulk output already proposed for exclusion from Git | No source-code change needed; file will be gitignored |
| **MANIFEST-SANITISE** | Committed manifest containing absolute paths in data columns | Strip repo-root prefix before committing; preserve filenames and hashes |
| **REPORT-NOTE** | Committed concise report referencing an absolute path in prose | Add a `> Note` callout explaining paths are machine-local; no code change |
| **HARMLESS-DOC** | Harmless documentation example or generated markdown link | No action |

---

## Per-File Findings

### 1. `reports/EXP_002_METADATA.json` — **MANIFEST-SANITISE**

- Proposed action: **Commit** (concise metadata artifact)
- Hit: line 2, field `"input"` contains the full absolute path to `reports/2024Q4_TRANSFER_STATE_TABLE.csv`
- Classification: manifest field recording the input file used in Experiment 002
- Required action: Replace the absolute path with a repository-relative path (`reports/2024Q4_TRANSFER_STATE_TABLE.csv`) before committing. The filename and all other fields are unchanged.

---

### 2. `reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md` — **REPORT-NOTE**

- Proposed action: **Commit** (concise summary)
- Hits: lines 27–35, the Results table `Destination` column contains 9 absolute download destination paths
- Classification: generated markdown report; the absolute paths are the runtime download destinations recorded at the time of the script run
- Required action: Add a callout block at the top of the file:
  ```
  > Note: Destination paths in the table below were recorded at the time of download and are machine-local.
  > Substitute your own `data/raw/aemo/…` directory when reproducing.
  ```
  No code or data change needed beyond the callout.

---

### 3. `reports/phase4b_component_validation_summary.md` — **REPORT-NOTE**

- Proposed action: **Commit** (concise summary)
- Hit: line 3, a backtick-wrapped path reference to `phase4b_component_export_from_alpha.csv`
- Classification: documentary prose reference to a local file path
- Required action: Replace the absolute path in the prose with the repository-relative path `reports/phase4b_component_export_from_alpha.csv`.

---

### 4. `reports/phase5c3_unit_payout_reconciliation.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 4–13, column recording the AEMO auction units source file path (`AUCUNITS_20241229.R015`)
- Classification: generated forensic reconciliation CSV; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 5. `reports/phase5c4_c2024q4_download_inventory.csv` — **MANIFEST-SANITISE**

- Proposed action: **Commit** (concise download inventory)
- Hits: lines 2–10, column `local_path` contains absolute paths to downloaded zip files
- Classification: download audit manifest; the filename, URL, HTTP status, and size columns are portable — only `local_path` embeds the machine prefix
- Required action: Strip `/Users/haimptasznik/Desktop/haimos-transmission-rights-repo/` prefix from the `local_path` column, leaving paths relative to the repo root (e.g. `data/raw/aemo/mmsdm_dispatchprice/PUBLIC_ARCHIVE%23...zip`).

---

### 6. `reports/phase5c4b_c2024q4_filename_compatibility.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 2–19, local path columns for both archive and DVD filenames
- Classification: generated compatibility check artifact; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 7. `reports/phase5c7_payout_forensic_step_by_step.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 4–13, column recording the source auction-units file path (`AUCUNITS_20241229.R015`)
- Classification: generated forensic payout CSV; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 8. `reports/phase5c_dispatchinterconnectorres_cache_report.md` — **REPORT-NOTE**

- Proposed action: **Commit** (concise cache status report)
- Hits: lines 11–12, markdown list items citing the manifest and failed-files CSV by absolute path
- Classification: generated summary report with machine-local file references
- Required action: Replace absolute paths with repository-relative paths:
  - `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv`
  - `reports/phase5c_dispatchinterconnectorres_failed_files.csv`

---

### 9. `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` — **MANIFEST-SANITISE**

- Proposed action: **Commit** (ingestion auditability manifest)
- Hits: lines 2–7, columns `source_file_path` and `output_partition_path` contain absolute paths
- Classification: ingestion manifest; filenames, SHA-256 hashes, row counts, timestamps, and statuses are all portable — only the directory prefix is machine-local
- Required action: Strip repo-root prefix from `source_file_path` and `output_partition_path` columns. Preserve all other columns including hashes exactly.

---

### 10. `reports/phase5c_dispatchprice_cache_report.md` — **REPORT-NOTE**

- Proposed action: **Commit** (concise cache status report)
- Hits: lines 11–12, same pattern as `phase5c_dispatchinterconnectorres_cache_report.md`
- Required action: Replace absolute paths with:
  - `reports/phase5c_dispatchprice_ingestion_manifest.csv`
  - `reports/phase5c_dispatchprice_failed_files.csv`

---

### 11. `reports/phase5c_dispatchprice_ingestion_manifest.csv` — **MANIFEST-SANITISE**

- Proposed action: **Commit** (ingestion auditability manifest)
- Hits: lines 2–7, same column pattern as the interconnectorres manifest
- Required action: Strip repo-root prefix from `source_file_path` and `output_partition_path`. Preserve all other columns.

---

### 12. `reports/phase5c_dispatchregionsum_cache_report.md` — **REPORT-NOTE**

- Proposed action: **Commit** (concise cache status report)
- Hits: lines 11–12, same pattern
- Required action: Replace absolute paths with:
  - `reports/phase5c_dispatchregionsum_ingestion_manifest.csv`
  - `reports/phase5c_dispatchregionsum_failed_files.csv`

---

### 13. `reports/phase5c_dispatchregionsum_ingestion_manifest.csv` — **MANIFEST-SANITISE**

- Proposed action: **Commit** (ingestion auditability manifest)
- Hits: lines 2–7, same column pattern
- Required action: Strip repo-root prefix from `source_file_path` and `output_partition_path`. Preserve all other columns.

---

### 14. `reports/phase5c_driver_attribution.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hit: line 2, a column referencing `mmsdm_dispatchprice` by absolute path
- Classification: generated driver attribution output; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 15. `reports/phase5c_ingestion_lineage.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hit: line 2, a column referencing `mmsdm_dispatchprice` directory by absolute path
- Classification: generated lineage record; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 16. `reports/phase5c_nsw1_qld1_manual_reconciliation_20.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 2–9, `source_hash_path` column recording absolute paths to `.csv.gz` cache partitions
- Classification: large generated reconciliation sample; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 17. `reports/phase5c_stage1_manual_reconciliation.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 2–20, `source_files` column recording absolute paths to AEMO zip archives
- Classification: generated stage-1 reconciliation sample; already proposed for exclusion
- Required action: None — file will be gitignored.

---

### 18. `reports/phase5c_stage23_market_state_sample.csv` — **IGNORE**

- Proposed action: **Exclude from Git** (bulk generated tabular artifact)
- Hits: lines 2–31+, `source_files` column recording pipe-delimited absolute paths to four zip archives per interval
- Classification: generated market-state sample; already proposed for exclusion
- Required action: None — file will be gitignored.

---

## Summary by Classification

| Class | Files | Action Required Before Commit |
|---|---:|---|
| MANIFEST-SANITISE | 4 | Strip repo-root prefix from path columns; preserve filenames, hashes |
| REPORT-NOTE | 5 | Add callout or replace absolute path references in prose |
| IGNORE | 9 | No action — these files will be excluded from Git |
| **Total flagged** | **18** | |

---

## Files Requiring Action Before Commit

The following 9 files are proposed for Git and must be remediated before staging:

| File | Class | Change Required |
|---|---|---|
| `reports/EXP_002_METADATA.json` | MANIFEST-SANITISE | Replace `input` value with repo-relative path |
| `reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md` | REPORT-NOTE | Add machine-local path callout block |
| `reports/phase4b_component_validation_summary.md` | REPORT-NOTE | Replace absolute path with repo-relative path |
| `reports/phase5c_dispatchinterconnectorres_cache_report.md` | REPORT-NOTE | Replace absolute manifest/failed-files paths |
| `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` | MANIFEST-SANITISE | Strip repo-root prefix from two path columns |
| `reports/phase5c_dispatchprice_cache_report.md` | REPORT-NOTE | Replace absolute manifest/failed-files paths |
| `reports/phase5c_dispatchprice_ingestion_manifest.csv` | MANIFEST-SANITISE | Strip repo-root prefix from two path columns |
| `reports/phase5c_dispatchregionsum_cache_report.md` | REPORT-NOTE | Replace absolute manifest/failed-files paths |
| `reports/phase5c_dispatchregionsum_ingestion_manifest.csv` | MANIFEST-SANITISE | Strip repo-root prefix from two path columns |

## Files Requiring No Action (already excluded)

`reports/phase5c3_unit_payout_reconciliation.csv`, `reports/phase5c4b_c2024q4_filename_compatibility.csv`, `reports/phase5c7_payout_forensic_step_by_step.csv`, `reports/phase5c_driver_attribution.csv`, `reports/phase5c_ingestion_lineage.csv`, `reports/phase5c_nsw1_qld1_manual_reconciliation_20.csv`, `reports/phase5c_stage1_manual_reconciliation.csv`, `reports/phase5c_stage23_market_state_sample.csv`, `reports/phase5c4_c2024q4_download_inventory.csv` *(see note below)*.

> **Note on `phase5c4_c2024q4_download_inventory.csv`**: The inventory file is proposed for **commit** in the preservation plan but contains a `local_path` column with absolute paths. It should be sanitised (strip prefix) before staging, or alternatively reclassified to IGNORE if the URL and hash columns in the summary markdown are considered sufficient. This review recommends sanitisation and commit — it is unique auditability evidence.

---

## Source Code Review

No Python source files in `scripts/` or `src/` were found to contain hardcoded `/Users/...` absolute paths. All path construction in source code uses `pathlib.Path`, repository-relative constants, or runtime arguments. **No source code changes are required for portability.**
