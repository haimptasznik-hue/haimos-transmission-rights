# EXP_002 Results

## Locked Contract
- Baseline model: `mwflow ~ balance_difference_mw`
- Mechanism model: `mwflow ~ balance_difference_mw + utilisation_pct + transfer_capability_margin_mw + flow_ramp_mw + near_export_limit_flag + near_import_limit_flag`
- Direction metric: `expected_flow_direction_from_balance` vs `actual_qni_flow_direction`
- Near-limit regime: `utilisation_pct >= 90` or near-limit flags set
- Monthly stability rule: directional accuracy must stay above `75%` in each month, with no more than a `5` percentage-point spread

## Sample
- Primary sample size: `26362`
- Intervention rows excluded: `12`
- Full-sample sensitivity size: `26374`

## Core Metrics
- Baseline R²: `0.056287`
- Baseline MAE (MW): `303.231595`
- Extended R²: `0.359864`
- Extended MAE (MW): `255.370805`
- Incremental R²: `0.303577`
- Directional accuracy: `0.797989`

## Boundary Conditions
- Near-limit sample size: `10386`
- Near-limit extended R²: `0.601758`
- Near-limit incremental R²: `0.535119`
- Near-limit directional accuracy: `0.794531`
- Far-from-limit sample size: `15976`
- Far-from-limit extended R²: `0.102437`
- Far-from-limit incremental R²: `0.048696`
- Far-from-limit directional accuracy: `0.800238`

## Stability
- Monthly directional accuracy minimum: `0.774637`
- Monthly directional accuracy maximum: `0.820174`
- Monthly spread: `0.045537`
- Monthly stability: `True`

## Residuals
- Dominant unexplained residual: Largest residual at 2024-12-17 06:50:00+00:00 with |residual|=1435.913 MW; utilisation=100.00%
- Top residual correlate: `utilisation_pct`
- Top residual correlate Spearman: `-0.083355`

## Verdict
- LAW_002 classification: `CONDITIONALLY_ACCEPTED`
- Reason: Transmission-capability variables materially improve explanatory power, especially near corridor limits, but detailed constraint and outage data remain unresolved.
- Research Value Score: `66.94/100`

## Sensitivity
- Primary vs full-sample metrics are essentially unchanged, so intervention selection does not drive the result.
- The mechanism lift concentrates in the near-limit regime, which is the expected physical boundary condition.
- Detailed binding-constraint and outage data remain the best next mechanism layer.

## Mechanism Ranking
1. Interconnector capability / utilisation / transfer-capability margin
2. Binding constraints / constraint headroom
3. Planned outages / deratings
4. Short-interval flow motion (`flow_ramp_mw`) as a secondary correlate

## Next Step
- Prioritise a constraint/outage-aware follow-up experiment on the same frozen `2024Q4` state vector.
