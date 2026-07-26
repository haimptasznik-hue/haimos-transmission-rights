# PORTABILITY_SANITISATION_REPORT.md

- Date: 2026-07-26
- Prefix removed: `/Users/haimptasznik/Desktop/haimos-transmission-rights-repo/`
- Replacement: repository-relative path (prefix stripped; filenames and subdirectories preserved)
- Files modified: 9
- Source code modified: 0

---

## Files Changed

| File | Type | Abs. paths before | Abs. paths after | Extra verification |
|---|---|---:|---:|---|
| `reports/EXP_002_METADATA.json` | JSON | 1 | 0 | JSON parses ✓ |
| `reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md` | Markdown | 9 | 0 | Portability note added ✓ |
| `reports/phase4b_component_validation_summary.md` | Markdown | 1 | 0 | Portability note added ✓ |
| `reports/phase5c_dispatchinterconnectorres_cache_report.md` | Markdown | 2 | 0 | Portability note added ✓ |
| `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` | CSV | 12 | 0 | 6 data rows, 10 cols, no blank paths ✓ |
| `reports/phase5c_dispatchprice_cache_report.md` | Markdown | 2 | 0 | Portability note added ✓ |
| `reports/phase5c_dispatchprice_ingestion_manifest.csv` | CSV | 12 | 0 | 6 data rows, 10 cols, no blank paths ✓ |
| `reports/phase5c_dispatchregionsum_cache_report.md` | Markdown | 2 | 0 | Portability note added ✓ |
| `reports/phase5c_dispatchregionsum_ingestion_manifest.csv` | CSV | 12 | 0 | 6 data rows, 10 cols, no blank paths ✓ |
| **Total** | | **53** | **0** | |

---

## Absolute Paths Removed

| Original value (prefix only shown) | Replacement |
|---|---|
| `.../reports/2024Q4_TRANSFER_STATE_TABLE.csv` | `reports/2024Q4_TRANSFER_STATE_TABLE.csv` |
| `.../reports/phase4b_component_export_from_alpha.csv` | `reports/phase4b_component_export_from_alpha.csv` |
| `.../reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` | `reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv` |
| `.../reports/phase5c_dispatchinterconnectorres_failed_files.csv` | `reports/phase5c_dispatchinterconnectorres_failed_files.csv` |
| `.../reports/phase5c_dispatchprice_ingestion_manifest.csv` | `reports/phase5c_dispatchprice_ingestion_manifest.csv` |
| `.../reports/phase5c_dispatchprice_failed_files.csv` | `reports/phase5c_dispatchprice_failed_files.csv` |
| `.../reports/phase5c_dispatchregionsum_ingestion_manifest.csv` | `reports/phase5c_dispatchregionsum_ingestion_manifest.csv` |
| `.../reports/phase5c_dispatchregionsum_failed_files.csv` | `reports/phase5c_dispatchregionsum_failed_files.csv` |
| `.../data/raw/aemo/mmsdm_dispatchprice/PUBLIC_ARCHIVE%23...zip` (×9 rows) | `data/raw/aemo/mmsdm_dispatchprice/PUBLIC_ARCHIVE%23...zip` |
| `.../data/raw/aemo/mmsdm_dispatchinterconnectorres/PUBLIC_DVD_...zip` (×6 rows) | `data/raw/aemo/mmsdm_dispatchinterconnectorres/PUBLIC_DVD_...zip` |
| `.../data/raw/aemo/.../dispatchinterconnectorres_*.csv.gz` (×6 rows) | `data/raw/aemo/.../dispatchinterconnectorres_*.csv.gz` |
| `.../data/raw/aemo/mmsdm_dispatchprice/PUBLIC_DVD_...zip` (×6 rows) | `data/raw/aemo/mmsdm_dispatchprice/PUBLIC_DVD_...zip` |
| `.../data/raw/aemo/.../dispatchprice_*.csv.gz` (×6 rows) | `data/raw/aemo/.../dispatchprice_*.csv.gz` |
| `.../data/raw/aemo/mmsdm_dispatchregionsum/PUBLIC_DVD_...zip` (×6 rows) | `data/raw/aemo/mmsdm_dispatchregionsum/PUBLIC_DVD_...zip` |
| `.../data/raw/aemo/.../dispatchregionsum_*.csv.gz` (×6 rows) | `data/raw/aemo/.../dispatchregionsum_*.csv.gz` |

---

## Row-Count Verification (CSV manifests)

| Manifest | Data rows before | Data rows after | Columns | Blank paths after |
|---|---:|---:|---:|---:|
| `phase5c_dispatchinterconnectorres_ingestion_manifest.csv` | 6 | 6 | 10 | 0 |
| `phase5c_dispatchprice_ingestion_manifest.csv` | 6 | 6 | 10 | 0 |
| `phase5c_dispatchregionsum_ingestion_manifest.csv` | 6 | 6 | 10 | 0 |

All SHA-256 hashes, row counts, timestamps, status fields and schema version columns are unchanged.

---

## JSON Verification

`reports/EXP_002_METADATA.json`: parses successfully after edit. All 11 non-path fields (`primary_sample_size`, `baseline_r2`, `verdict`, etc.) are unchanged. Only the `input` field value was modified (prefix stripped).

---

## Unresolved External Path References

None. All 53 occurrences of the repo-root prefix have been replaced. No external paths (outside the repository) were present in any of the 9 files.

---

## What Was Preserved

- All SHA-256 hash values (exact)
- All timestamps (exact)
- All row counts and column orders
- All report findings, metrics and conclusions
- All filenames and subdirectory structure
- All JSON keys and non-path values
- Valid JSON structure confirmed
- Markdown readability confirmed (portability notes added, no findings rewritten)

---

## Verification Command Output

```
OK  reports/EXP_002_METADATA.json                           0 hits  JSON valid
OK  reports/PHASE5C4_C2024Q4_DOWNLOAD_SUMMARY.md            0 hits
OK  reports/phase4b_component_validation_summary.md         0 hits
OK  reports/phase5c_dispatchinterconnectorres_cache_report.md  0 hits
OK  reports/phase5c_dispatchinterconnectorres_ingestion_manifest.csv  0 hits  6 data rows, 10 cols, no blank paths
OK  reports/phase5c_dispatchprice_cache_report.md           0 hits
OK  reports/phase5c_dispatchprice_ingestion_manifest.csv    0 hits  6 data rows, 10 cols, no blank paths
OK  reports/phase5c_dispatchregionsum_cache_report.md       0 hits
OK  reports/phase5c_dispatchregionsum_ingestion_manifest.csv  0 hits  6 data rows, 10 cols, no blank paths

All checks passed. Zero /Users/ occurrences across all 9 files.
```
