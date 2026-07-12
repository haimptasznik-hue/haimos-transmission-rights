# Backtest Audit Report
Generated: 2026-07-12T13:52:59.763930+00:00

## Label
**IN_SAMPLE_HEURISTIC — not investable evidence**

---

## Audit Questions and Answers

### 1. Can capital be spent twice before settlement?
**No.** Capital is locked from purchase date until `_quarter_settlement_date(quarter)`.
Free capital is decremented at purchase and restored only when settlement is triggered
(i.e. when `now_dt >= pos_settlement_dt`). Overlapping quarters share one capital pool.

### 2. Is purchase cost ever treated as capital returned?
**No.** At settlement:
```
free_capital += acquisition_cost        # return locked cash
free_capital += (realised_payout - acquisition_cost)  # book net P&L
```
The acquisition cost is subtracted and then added back only at settlement.
Net P&L is booked separately from cost recovery.

### 3. Does settlement timing match AEMO methodology?
**Approximately.** Settlement is modelled as: quarter end + 3 months.
- Q1 (Jan-Mar) → settles ~July 1
- Q2 (Apr-Jun) → settles ~October 1
- Q3 (Jul-Sep) → settles ~January 1 following year
- Q4 (Oct-Dec) → settles ~April 1 following year

AEMO's actual SETIRSURPLUS settlement is typically processed 2-3 months after quarter end.
This approximation is conservative (longer lock = higher funding cost).

### 4. Can units purchased exceed units available?
**No.** `bid_units = min(units_offered * participation_cap, floor(free_capital * cap / price))`
This enforces both market-side (AEMO units offered) and capital-side constraints.

### 5. Are participation limits respected?
**Yes.** `max_participation_by_product = 10%` of units offered per product.
`max_capital_per_product = 10%` of free capital per product.

### 6. Are whole units enforced?
**Yes.** `int(math.floor(...))` is applied at every unit calculation step.

### 7. Are transaction costs correctly applied?
**Yes.**
- Fee: `0.10%` of notional at purchase time
- Funding: `8.0% p.a.` on notional, prorated for lock period in days

### 8. Is there hidden leverage?
**No.** Capital available is always `free_capital` (not portfolio value).
Free capital can never go below zero — positions are scaled down if needed.

### 9. Does future information enter historical decisions?
**No.**
- Only rows with `final_realised_payout_per_unit` populated are eligible for investment.
- Payout data for a given quarter is treated as available only after settlement.
- The `expected_alpha` forecast is computed from clearing price alone (prior tranches median).
- Decision timestamps are the auction announcement date, not the settlement date.

---

## Data Quality

| Metric | Value |
|---|---|
| Total rows | 2304 |
| Rows with settled payout | 1740 |
| Rows without payout (future/pending) | 564 |
| Quarters covered | 43 |
| Corridors | NSW1-QLD1, V-SA, VIC1-NSW1 |

---

## Capital Constraint Settings

| Parameter | Value |
|---|---|
| Starting capital | $50,000 |
| Max participation per product | 10% of offered units |
| Max capital per product | 10% of free capital |
| Fee rate | 0.10% of notional |
| Annual funding rate | 8.0% p.a. |

---

## Conclusion
The backtest engine enforces capital lock-up, settlement timing, unit constraints, fees, and
funding costs. No double-spending, no leverage, no look-ahead. The in-sample result is
mechanically sound but is **not investable evidence** because the strategy has not been
validated on genuinely unseen (out-of-sample) quarters.
