# SECURITY_REVIEW.md

- Review date: 2026-07-26
- Reviewer: automated audit (Task 2 — Repository Ignore Policy and Sensitive-Content Review)
- Baseline: REPOSITORY_PRESERVATION_INVENTORY.md (commit `29a7194a6820f690ad5a58644dedf77c04f8729e`)
- Files flagged by scan: 8
- Method: pattern match on `token`, `secret`, `password`, `api_key`, `bearer`, `authorization` (case-insensitive)

---

## Summary

**No real credentials, API keys, bearer tokens, passwords, or secrets were found in any of the 8 flagged files.**

All matches are internal Python variable and parameter names whose identifiers contain the substring `token`. The word is used throughout this codebase as a domain term meaning a normalised string key (e.g. a quarter identifier `2024Q4`, a dataset name `DISPATCHPRICE`, or a month stamp `202410`). None of the matched lines assign, interpolate, or transmit any authentication credential.

**Recommendation: no revocation or redaction is required. No commit should be blocked on security grounds.**

---

## Per-File Findings

### 1. `scripts/build_c2024q4_transfer_constraint_table.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 28 | `token_assignment` | False positive — CLI help string describing a quarter identifier argument (`--quarter`, described as "Quarter token like 2024Q4") | None |
| 35 | `token_assignment` | False positive — local variable `token = quarter.strip().upper()` normalising a CLI arg into a quarter key string | None |
| 51 | `token_assignment` | False positive — local variable `token = f"..."` composing a filename-safe period string from month arguments | None |

No credential. Variable name `token` is a domain term for a normalised period key. Safe to commit.

---

### 2. `scripts/mmsdm_source_utils.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 53 | `token_assignment` | False positive — function parameter `dataset_token: str` naming a dataset identifier (e.g. `DISPATCHPRICE`) | None |
| 54 | `token_assignment` | False positive — local variable `month_token = f"{year}{month:02d}"` composing a YYYYMM string | None |
| 55 | `token_assignment` | False positive — use of `dataset_token` in an f-string that builds a public AEMO archive filename | None |

No credential. `dataset_token` and `month_token` are AEMO filename fragment helpers. Safe to commit.

---

### 3. `scripts/phase5c_first_principles_pipeline.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 675 | `token_assignment` | False positive — local variable `token = str(quarter).strip().upper()` normalising a quarter string | None |
| 676 | `token_assignment` | False positive — conditional on `token` (same variable) | None |
| 682 | `token_assignment` | False positive — `token = _normalise_contract_quarter(quarter)` assigning a normalised quarter key | None |
| 2251 | `token_assignment` | False positive — argparse help string: `"Quarter token for joined market-state build, e.g. 2020Q1."` | None |
| 2256 | `token_assignment` | False positive — argparse help string: `"Optional Phase 5C.3 override quarter token, e.g. 2025Q1."` | None |

No credential. Safe to commit.

---

### 4. `scripts/source_dispatch_unit_scada.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 128 | `token_assignment` | False positive — `month_token = f"{year}{month:02d}"` composing a YYYYMM string | None |
| 129 | `token_assignment` | False positive — use of `month_token` in a `zip_name` f-string | None |
| 135 | `token_assignment` | False positive — use of `month_token` in a print/log statement | None |
| 139 | `token_assignment` | False positive — use of `month_token` in a cache path f-string | None |
| 143 | `token_assignment` | False positive — use of `month_token` in a print/log statement | None |

No credential. Safe to commit.

---

### 5. `scripts/source_dispatchconstraint.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 25 | `token_assignment` | False positive — module-level constant `DATASET_TOKEN = "DISPATCHCONSTRAINT"` (a public AEMO table name) | None |
| 111 | `token_assignment` | False positive — `month_token = f"{year}{month:02d}"` | None |
| 114, 151 | `token_assignment` | False positive — `dataset_token=DATASET_TOKEN` keyword arguments to utility functions | None |
| 120, 128, 136, 152, 160 | `token_assignment` | False positive — log/path/manifest uses of `DATASET_TOKEN` and `month_token` | None |

No credential. Safe to commit.

---

### 6. `scripts/source_dispatchinterconnectorres.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 25 | `token_assignment` | False positive — module-level constant `DATASET_TOKEN = "DISPATCHINTERCONNECTORRES"` | None |
| 157–206 | `token_assignment` | False positive — same pattern as `source_dispatchconstraint.py`; `month_token` and `DATASET_TOKEN` used in paths, logs, and manifests | None |

No credential. Safe to commit.

---

### 7. `scripts/source_dispatchregionsum.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 25 | `token_assignment` | False positive — module-level constant `DATASET_TOKEN = "DISPATCHREGIONSUM"` | None |
| 144–193 | `token_assignment` | False positive — same pattern as above | None |

No credential. Safe to commit.

---

### 8. `src/transmission_rights/services/aemo/market_state_database.py`

| Line | Category | Classification | Remediation |
|---:|---|---|---|
| 174, 213 | `token_assignment` | False positive — function parameter `month_token_resolver` and conditional use; a callable resolving a month string from a file path | None |
| 534, 551, 609, 651 | `token_assignment` | False positive — `_cache_file_month_token` static method and its use as `month_token_resolver`; extracts YYYYMM from filenames | None |
| 1766–1768, 2048–2050, 2380–2381 | `token_assignment` | False positive — `period_token = archive_path.stem.split("_")[-1][:6]`; parses year/month from AEMO archive stem | None |

No credential. Safe to commit.

---

## Verdict

| Finding | Count |
|---|---:|
| Real credentials found | **0** |
| API keys or tokens found | **0** |
| Bearer / auth headers found | **0** |
| False positives (domain `token` variable usage) | **8 files / all matches** |

**No stop-and-revoke action is required.**
All 8 files are safe to include in Git without modification on security grounds.
