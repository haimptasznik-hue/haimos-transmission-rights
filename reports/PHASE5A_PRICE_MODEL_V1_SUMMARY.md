# Phase 5A – Price Model v1 Summary

## Evaluation frame
- Settled rows evaluated: `1740`
- Baseline absolute forecast error (AUD/unit sum): `15,340,206.08`
- Price Model v1 absolute forecast error (AUD/unit sum): `15,797,451.77`
- Forecast error reduction: `-457,245.69` (-2.98%)

## Attribution loop
- Total traded absolute error (AUD): `173,794,731.05`
- Known explained error after model wiring (AUD): `0.00`
- Unattributed residual before wiring (AUD): `173,794,731.05`
- Unattributed residual after wiring (AUD): `173,794,731.05`
- Unattributed residual reduction: `0.00` (0.00%)

## Backtest impact
- Baseline audit P&L (AUD): `22,287,319.68`
- Price Model v1 audit P&L (AUD): `5,932,984,471.26`
- Estimated P&L impact (AUD): `5,910,697,151.58`

## ⚠ Backtest inflation caveat
- The Price Model v1 P&L figure above is **not credible as an out-of-sample result**.
- The model is trained on all rows prior to each decision timestamp, including historical settled outcomes for the same direction.
- Because VIC1→SA historically produced extreme payouts (>$20,000/unit in 2022 Q2), the model learns to forecast high values for that corridor and triggers many more bids (11,162 vs 926 baseline).
- The in-sample backtest therefore amplifies the result by ~12× trade count, not because of genuine predictive edge.
- A valid out-of-sample evaluation requires a forward holdout period not yet present in this repository snapshot.
- **Conclusion:** Backtest P&L comparison is suppressed from the audit summary until a proper holdout split is available.

## Interpretation guardrails
- This summary does not claim root cause beyond improved payout forecasting on available data.
- The -2.98% absolute forecast error change is modest and slightly negative: the model has higher per-unit error than the baseline fair_value_forecast.
- No improvement is claimed in attribution coverage (unattributed residual unchanged at 0.00 AUD — attribution pipeline requires component export wiring through phase4b).
- Direct price, flow, and constraint decomposition still requires those datasets or exported component forecasts.
