# TOP_3_ELIGIBILITY_BLOCKERS

Source: `WHY_NO_ELIGIBLE_QUARTER.md` (43 rejected quarters).

## Gate Failure Ranking (43 rejected quarters)
1. `has_market_state` — failed in **42/43** quarters
2. `has_auction_units_weekly` — failed in **35/43** quarters
3. `has_official_quarterly_irsr` — failed in **18/43** quarters *(tied with `has_payout_per_unit` at 18/43)*

## Top Three Blockers

### 1) `has_market_state`
- **Exact missing condition:** quarter has no market-state coverage in selector input.
- **Affected quarters:** all rejected quarters except `C2020Q1` (42 quarters).
- **Issue type:** missing data coverage (targeted physical dataset gap), not schema.
- **Authoritative source needed:** AEMO dispatch physical datasets for target quarter (`DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, `DISPATCHREGIONSUM`).
- **Smallest practical fix:** ingest/build market-state for **one** target quarter first (not full history), then refresh selector input quarter set.
- **Would fixing this alone create eligible quarters?** **Yes.** If fixed for `C2024Q4` through `C2026Q2`, those quarters already pass all other gates.

### 2) `has_auction_units_weekly`
- **Exact missing condition:** no auction-units-weekly records for quarter.
- **Affected quarters:** `C2018Q3–C2024Q3`, `C2026Q4–C2029Q1` (35 quarters).
- **Issue type:** missing data coverage (raw auction units files only cover `C2024Q4–C2026Q3`).
- **Authoritative source needed:** AEMO auction units weekly files (`AUCUNITS_*.R*`) for missing quarters.
- **Smallest practical fix:** acquire auction-unit files only for the selected first-test quarter (if not already covered).
- **Would fixing this alone create eligible quarters?** **No.** Those quarters still fail `has_market_state` (and some also fail IRSR/payout).

### 3) `has_official_quarterly_irsr`
- **Exact missing condition:** no official quarterly IRSR row for quarter.
- **Affected quarters:** `C2018Q3–C2020Q1`, `C2026Q3–C2029Q1` (18 quarters).
- **Issue type:** missing data coverage in official quarterly IRSR series.
- **Authoritative source needed:** `data/derived/irsr/setirsurplus_quarterly_all.csv` (official quarterly IRSR source feed covering target quarter).
- **Smallest practical fix:** backfill official quarterly IRSR for the chosen first-test quarter only (if missing).
- **Would fixing this alone create eligible quarters?** **No.** Most affected quarters also fail `has_market_state` and/or `has_payout_per_unit`.

## Closest-to-Eligible Quarter
- **Quarter:** `C2024Q4` *(earliest of 7 tied quarters with one failed gate: `C2024Q4`, `C2025Q1`, `C2025Q2`, `C2025Q3`, `C2025Q4`, `C2026Q1`, `C2026Q2`)*
- **Gates passed (8/9):** `has_official_quarterly_irsr`, `has_payout_per_unit`, `has_auction_clearing`, `has_ruleset`, `has_unit_category`, `has_max_units`, `has_unit_proportion`, `has_auction_units_weekly`
- **Gates failed (1/9):** `has_market_state`
- **Exact files/fields needed to make eligible:**
  - Add quarter coverage for `C2024Q4` in physical inputs feeding market-state build from:
    - `DISPATCHPRICE`
    - `DISPATCHINTERCONNECTORRES`
    - `DISPATCHREGIONSUM`
  - Ensure selector-visible market-state contains `interval_timestamp_utc` values in `C2024Q4`.

## Recommended First End-to-End SRA Test Quarter
- **Recommendation:** `C2024Q4`
- **Why:** already satisfies 8/9 gates; only targeted market-state ingestion is missing.
- **Do not broaden scope:** no need for broad historical ingestion before first end-to-end test.

## Exact Next Action (single action)
Acquire and ingest **only `C2024Q4`** physical dispatch datasets (`DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, `DISPATCHREGIONSUM`) so `has_market_state` passes for `C2024Q4`.

## Estimated Work Remaining Before First End-to-End Test
- **Data acquisition + targeted cache build for `C2024Q4`:** ~3–5 hours
- **Quarter-level validation checks:** ~1–2 hours
- **Total:** **~0.5–1 working day** to first end-to-end SRA test attempt.
