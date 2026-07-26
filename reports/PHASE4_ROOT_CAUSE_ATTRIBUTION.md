# Phase 4 – Root Cause Attribution (Deterministic Layer)

This report does **attribution with currently available observables** and separates what is proven from what still needs deeper model instrumentation.

## Coverage
- Total bid-eligible settled trade rows: `642`
- Negative realized alpha rows: `343` (53.4%)
- Overvaluation rows (`realized < forecast`): `395` (61.5%)
- Distinct ruleset versions observed: `1`

## Deterministic Findings
- Trade arithmetic fields are reconstructible from stored primitives (cost, payout, alpha definitions).
- Ruleset variation cannot explain losses in this dataset snapshot because only one ruleset appears (`RS-BASELINE-v1`).
- The dominant direct error signal is valuation miss (`final_realised_payout_per_unit - fair_value_forecast`).

## Requested Breakdown Availability
- By interconnector: available (`interconnector_id`).
- By direction: proxied as `direction_key = corridor|from_region|unit_region` from product fields.
- By tranche: available (`tranche`).
- By quarter: available (`quarter`).
- By RuleSet version: available (`ruleset_id`) but single version in sample.
- By unit table/version: **not explicitly present** in current dataset columns.

## What this does NOT yet identify
- Price forecast vs flow forecast vs constraint forecast decomposition (requires model internal component outputs).
- Settlement methodology branch attribution beyond current realized payout primitives.

## Top groups by trade count

| interconnector_id | direction_key | tranche | quarter | ruleset_id | error_bucket | trades | mean_valuation_miss_per_unit | mean_realised_alpha_per_unit | pct_negative_realised_alpha |
|---|---|---|---|---|---|---:|---:|---:|---:|
| NSW1-QLD1 | NSW1-QLD1|from=NSW1|unit=NSW1 | T01 | C2021Q3 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -218.52 | 52.48 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T05 | C2024Q1 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 17.18 | 18.28 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2024Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -25822.39 | -25111.39 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2025Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -10680.28 | -9345.88 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2025Q3 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 1527.97 | 2443.69 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2025Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -11714.58 | -10562.58 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2026Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -1585.18 | -924.28 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2021Q3 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -2761.60 | -2528.60 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2021Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -5354.07 | -4997.08 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2022Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -2026.43 | -1917.43 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2022Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -5912.48 | -5470.88 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2023Q1 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -10221.65 | -9464.39 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2023Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -4251.38 | -4040.42 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2023Q3 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -2099.00 | -2008.91 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2023Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -10687.44 | -10273.69 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2024Q1 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 18.28 | 185.89 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2025Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -10562.58 | -10500.18 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2026Q1 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -8384.70 | -8114.70 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T02 | C2026Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -924.28 | -648.18 | 100.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2024Q3 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 3518.76 | 4469.91 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2024Q2 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 2453.45 | 3851.95 | 0.0% |
| VIC1-NSW1 | VIC1-NSW1|from=NSW1|unit=NSW1 | T01 | C2023Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -11894.44 | -10687.44 | 100.0% |
| V-SA | V-SA|from=VIC1|unit=VIC1 | T12 | C2025Q2 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -8471.86 | -7847.78 | 100.0% |
| V-SA | V-SA|from=VIC1|unit=VIC1 | T11 | C2025Q4 | RS-BASELINE-v1 | Forecast overvaluation (upstream driver unresolved) | 1 | -6418.78 | -4068.53 | 100.0% |
| V-SA | V-SA|from=VIC1|unit=VIC1 | T11 | C2026Q1 | RS-BASELINE-v1 | Forecast undervaluation (upstream driver unresolved) | 1 | 35857.68 | 35897.37 | 0.0% |

## Output Files
- `reports/phase4_trade_level_attribution.csv`
- `reports/phase4_grouped_attribution.csv`

These are the Phase 4 base tables for deeper attribution once internal forecast components are exported.
