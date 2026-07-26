# WHY_NO_ELIGIBLE_QUARTER

## Selector Rule
A quarter is eligible only if all are true: `has_market_state`, `has_official_quarterly_irsr`, `has_payout_per_unit`, `has_auction_clearing`, `has_ruleset`, `has_unit_category`, `has_max_units`, `has_unit_proportion`, `has_auction_units_weekly`.

## Required Input Audit
| Required dataset | Exists? | Rows available | Quarter coverage | Earliest quarter | Latest quarter | Required schema present? | Used by quarter selector? |
|---|---:|---:|---|---|---|---:|---:|
| Auction results | Yes | 2304 | C2018Q3, C2018Q4, C2019Q1, C2019Q2, C2019Q3, C2019Q4 ... C2027Q4, C2028Q1, C2028Q2, C2028Q3, C2028Q4, C2029Q1 | C2018Q3 | C2029Q1 | Yes | Yes |
| Unit tables (auction units weekly) | Yes | 1460 | C2024Q4, C2025Q1, C2025Q2, C2025Q3, C2025Q4, C2026Q1, C2026Q2, C2026Q3 | C2024Q4 | C2026Q3 | Yes | Yes |
| RuleSets (from alpha database) | Yes | 2304 | C2018Q3, C2018Q4, C2019Q1, C2019Q2, C2019Q3, C2019Q4 ... C2027Q4, C2028Q1, C2028Q2, C2028Q3, C2028Q4, C2029Q1 | C2018Q3 | C2029Q1 | Yes | Yes |
| IRSR (interval-level raw dispatch_irsr) | Yes | 5 | C2025Q3, C2025Q4, C2026Q1, C2026Q2, C2026Q3 | C2025Q3 | C2026Q3 | Yes | No |
| Official quarterly IRSR | Yes | 300 | C2020Q2, C2020Q3, C2020Q4, C2021Q1, C2021Q2, C2021Q3 ... C2025Q1, C2025Q2, C2025Q3, C2025Q4, C2026Q1, C2026Q2 | C2020Q2 | C2026Q2 | Yes | Yes |
| Official payout per unit | Yes | 150 | C2020Q2, C2020Q3, C2020Q4, C2021Q1, C2021Q2, C2021Q3 ... C2025Q1, C2025Q2, C2025Q3, C2025Q4, C2026Q1, C2026Q2 | C2020Q2 | C2026Q2 | Yes | Yes |
| DISPATCHPRICE | Yes | 3 | C2020Q1 | C2020Q1 | C2020Q1 | Yes | No |
| DISPATCHINTERCONNECTORRES | Yes | 3 | C2020Q1 | C2020Q1 | C2020Q1 | Yes | No |
| REGIONAL_DEMAND | Yes | 3 | C2020Q1 | C2020Q1 | C2020Q1 | Yes | No |

## Candidate Quarter Rejections
| Quarter | Eligible | Missing selector conditions |
|---|---:|---|
| C2018Q3 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2018Q4 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2019Q1 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2019Q2 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2019Q3 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2019Q4 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2020Q1 | No | has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2020Q2 | No | has_market_state, has_auction_units_weekly |
| C2020Q3 | No | has_market_state, has_auction_units_weekly |
| C2020Q4 | No | has_market_state, has_auction_units_weekly |
| C2021Q1 | No | has_market_state, has_auction_units_weekly |
| C2021Q2 | No | has_market_state, has_auction_units_weekly |
| C2021Q3 | No | has_market_state, has_auction_units_weekly |
| C2021Q4 | No | has_market_state, has_auction_units_weekly |
| C2022Q1 | No | has_market_state, has_auction_units_weekly |
| C2022Q2 | No | has_market_state, has_auction_units_weekly |
| C2022Q3 | No | has_market_state, has_auction_units_weekly |
| C2022Q4 | No | has_market_state, has_auction_units_weekly |
| C2023Q1 | No | has_market_state, has_auction_units_weekly |
| C2023Q2 | No | has_market_state, has_auction_units_weekly |
| C2023Q3 | No | has_market_state, has_auction_units_weekly |
| C2023Q4 | No | has_market_state, has_auction_units_weekly |
| C2024Q1 | No | has_market_state, has_auction_units_weekly |
| C2024Q2 | No | has_market_state, has_auction_units_weekly |
| C2024Q3 | No | has_market_state, has_auction_units_weekly |
| C2024Q4 | No | has_market_state |
| C2025Q1 | No | has_market_state |
| C2025Q2 | No | has_market_state |
| C2025Q3 | No | has_market_state |
| C2025Q4 | No | has_market_state |
| C2026Q1 | No | has_market_state |
| C2026Q2 | No | has_market_state |
| C2026Q3 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit |
| C2026Q4 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2027Q1 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2027Q2 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2027Q3 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2027Q4 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2028Q1 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2028Q2 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2028Q3 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2028Q4 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |
| C2029Q1 | No | has_market_state, has_official_quarterly_irsr, has_payout_per_unit, has_auction_units_weekly |

## Conclusion
- `NO_ELIGIBLE_QUARTER` occurs because no candidate quarter satisfies all selector conditions simultaneously.
