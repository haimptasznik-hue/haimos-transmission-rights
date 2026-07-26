# Forensic Audit: First Losing VIC1-NSW1 Trade

## Trade
- Decision date: `2025-01-01 00:00:00+00:00`
- Product: `C2021Q3:VIC1-NSW1:NSW1:T11`
- Quarter / Tranche: `C2021Q3` / `T11`
- Ruleset: `RS-BASELINE-v1`

## Reconstruction (Auction → Settlement)
- Units: `108`
- Cost per unit: `$500.4400`
- Fair value forecast per unit: `$1,650.0000`
- Realized payout per unit: `$-553.6045`
- Forecast miss per unit: `$-2,203.6045`

- Notional reconstructed vs ledger delta: `0.00000000`
- Total cost reconstructed vs ledger delta: `0.00000000`
- Payout reconstructed vs ledger delta: `0.00000000`
- Alpha reconstructed vs ledger delta: `0.00000000`

- Settlement reconstruction delta (`realised_alpha` consistency): `0.00000000`

## First Divergence Point
All arithmetic checks reconcile. The first material divergence is forecasted unit payout versus realized unit payout.
- Forecast: `$1,650.0000` per unit
- Realized: `$-553.6045` per unit
- Divergence: `$-2,203.6045` per unit

This localizes root-cause work to forecast/valuation components (price, flow, constraints, settlement expectation), not trade accounting arithmetic.
