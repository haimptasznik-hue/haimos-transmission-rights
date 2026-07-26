# EXP_001 Results

## Locked Contract
- R² acceptance threshold: `> 0.5`
- Directional accuracy acceptance threshold: `> 0.90`
- QNI sign convention: positive `MWFLOW = NSW1->QLD1`, negative `MWFLOW = QLD1->NSW1`

## Core Metrics
- Pearson correlation: `-0.812097`
- Spearman correlation: `-0.794645`
- R²: `0.872068`
- MAE (MW): `108.918574`
- Directional sign accuracy: `0.797667`
- High-imbalance congestion rate: `0.580338`

## Stability
- Monthly stability (Spearman > 0 in each month): `False`
- Peak vs off-peak stability: `False`
- Weekday vs weekend stability: `False`
- Stability result: `UNSTABLE_OR_PARTIAL`

## Residual Analysis
- Dominant unexplained residual: Largest residual at 2024-10-06T09:55:00Z with |residual|=603.805 MW; utilisation=90.80%

## Verdict
- LAW_001 classification: `REJECTED`
- Reason: Core acceptance threshold failure (R² or directional accuracy).

## Recommended Next Experiment
- `EXP_002`: Replicate LAW_001 across additional historical windows (e.g., 2020Q1 + 2025 windows) and constrained/unconstrained partitions with unchanged thresholds.
