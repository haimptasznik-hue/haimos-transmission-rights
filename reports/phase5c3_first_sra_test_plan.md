# Phase 5C.3 First SRA Test Plan

- Quarter under test: `C2024Q4`
- Readiness verdict: `HOLD`

## Steps

1. Lock the selected quarter and corridor-direction coverage used in reconciliation.
2. Use physical interval drivers (`spread`, `flow`, `stress`, `demand_anomaly`) to build explanatory diagnostics only.
3. Validate payout consistency against authoritative quarterly IRSR and AUCTION_UNITS accumulated net payment per unit.
4. If HOLD, remediate source-mapping gaps before any forecasting work.
5. If GO, proceed to first concept-test design using this quarter as calibration baseline.
