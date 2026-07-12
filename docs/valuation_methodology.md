# Valuation Methodology

## Objective

Publish an independent fair value for each directional interconnector-quarter SRA product.

## Baseline formula

Initial scaffold uses:

$\text{Gross per-unit value} = \text{Unit proportion} \times \text{Expected IRSR}$

$\text{Fair value per unit} = \text{Gross per-unit value} \times (1 - \text{model risk discount} - \text{liquidity discount})$

## Confidence bands

The scaffold uses downside and upside IRSR scenarios to form a simple confidence interval:

- low case = downside IRSR × unit proportion × discount factor
- base case = expected IRSR × unit proportion × discount factor
- high case = upside IRSR × unit proportion × discount factor

## Future enhancements

- probability-weighted scenario trees,
- quarterly settlement revision modeling,
- auction-clearing calibration,
- liquidity depth proxies,
- outage/constraint stress scenarios,
- distribution-shape estimation instead of three-point ranges.

## Worked example

Inputs:

- max units: 1,000
- unit proportion: 0.001
- units held: 40
- expected IRSR: $4,000,000
- downside IRSR: $2,800,000
- upside IRSR: $5,200,000
- combined discount: 8%

Outputs:

- gross expected per-unit value: $4,000
- discounted fair value per unit: $3,680
- total fair value for 40 units: $147,200
- low/high band: $2,576 to $4,784

## Model-risk disclosures

Any published mark should explicitly disclose:

- reference data version,
- scenario date/time,
- auction-result calibration status,
- unresolved legal/process assumptions,
- known missing settlement adjustments.
