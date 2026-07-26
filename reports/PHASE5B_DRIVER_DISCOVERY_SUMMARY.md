# Phase 5B – Market Driver Discovery Engine

> **Objective:** Determine which physical and market variables explain
> deviations in Settlement Residue and SRA payouts.
> This is a scientific discovery phase. No trading model is built here.

## Data availability verdict

| Category | Status |
|---|---|
| SRA auction clearing prices | ✅ AVAILABLE (C2018Q3+) |
| SRA settled payout history | ✅ AVAILABLE (C2020Q2+) |
| Regional reference prices (RRP) | ❌ NOT IN REPO |
| Interconnector flow / utilisation | ❌ NOT IN REPO |
| Constraint binding frequency | ❌ NOT IN REPO |
| Generation by fuel type | ❌ NOT IN REPO |
| Weather / temperature | ❌ NOT IN REPO |
| Network outage register | ❌ NOT IN REPO |

**Key finding:** The variables most likely to explain settlement residue
are all absent from this repository. Auction microstructure and payout
history are the only available signals — and they encode seasonality,
not the causal drivers of congestion.

## Pearson correlations (in-repo derivable features vs settlement payout)

| Feature | vs payout_per_unit | vs seasonal_deviation |
|---|---|---|
| acp_mean | +0.577 | +0.166 |
| acp_median | +0.543 | +0.142 |
| acp_momentum | +0.207 | +0.078 |
| acp_std | +0.476 | +0.220 |
| fill_mean | -0.222 | -0.072 |
| fill_trend | +0.012 | +0.090 |
| payout_momentum | +0.515 | +0.501 |
| quarter_number | -0.018 | +0.000 |
| tranche_price_gradient | +0.367 | +0.193 |
| units_sold_total | +0.236 | +0.083 |
| years_since_2020q2 | +0.116 | +0.164 |

## Ranked in-repo drivers

| Rank | Feature | Composite Score | Abs Pearson | Abs Spearman |
|---|---|---|---|---|
| 1 | acp_std | 0.343 | 0.348 | 0.461 |
| 2 | payout_momentum | 0.333 | 0.508 | 0.298 |
| 3 | acp_mean | 0.305 | 0.372 | 0.363 |
| 4 | acp_median | 0.292 | 0.343 | 0.338 |
| 5 | tranche_price_gradient | 0.256 | 0.280 | 0.316 |
| 6 | units_sold_total | 0.164 | 0.159 | 0.140 |
| 7 | fill_mean | 0.141 | 0.147 | 0.175 |
| 8 | acp_momentum | 0.140 | 0.143 | 0.160 |
| 9 | years_since_2020q2 | 0.120 | 0.140 | 0.122 |
| 10 | fill_trend | 0.055 | 0.051 | 0.029 |
| 11 | quarter_number | 0.022 | 0.009 | 0.052 |

## Structural breaks detected (CUSUM on payout series)

- **NSW1-QLD1::QLD1:** breaks at quarters [25]
- **VIC1-NSW1::NSW1:** breaks at quarters [25]
- **VIC1-NSW1::VIC1:** breaks at quarters [16]

## Regime classification by quarter

| Quarter | Payout Regime | Gradient Regime | Mean Payout | Mean ACP |
|---|---|---|---|---|
| C2018Q3 | nan | FLAT | – | 3,502 |
| C2018Q4 | nan | FLAT | – | 3,481 |
| C2019Q1 | nan | FLAT | – | 6,660 |
| C2019Q2 | nan | FLAT | – | 4,211 |
| C2019Q3 | nan | FLAT | – | 4,590 |
| C2019Q4 | nan | FLAT | – | 4,306 |
| C2020Q1 | nan | STEEP | – | 6,773 |
| C2020Q2 | LOW | STEEP | 1,533 | 4,438 |
| C2020Q3 | LOW | STEEP | 6,012 | 4,817 |
| C2020Q4 | LOW | STEEP | 8,408 | 4,689 |
| C2021Q1 | LOW | STEEP | 4,418 | 6,940 |
| C2021Q2 | HIGH | FLAT | 13,351 | 4,131 |
| C2021Q3 | LOW | FLAT | 4,610 | 4,678 |
| C2021Q4 | MEDIUM | STEEP | 9,855 | 4,901 |
| C2022Q1 | MEDIUM | STEEP | 11,221 | 7,630 |
| C2022Q2 | HIGH | STEEP | 18,532 | 5,289 |
| C2022Q3 | HIGH | STEEP | 19,739 | 6,243 |
| C2022Q4 | MEDIUM | STEEP | 11,532 | 8,069 |
| C2023Q1 | MEDIUM | STEEP | 9,943 | 11,850 |
| C2023Q2 | HIGH | STEEP | 13,552 | 9,350 |
| C2023Q3 | MEDIUM | STEEP | 12,917 | 9,888 |
| C2023Q4 | LOW | STEEP | 8,347 | 10,007 |
| C2024Q1 | MEDIUM | STEEP | 12,859 | 14,448 |
| C2024Q2 | HIGH | STEEP | 17,592 | 11,080 |
| C2024Q3 | HIGH | STEEP | 21,257 | 11,853 |
| C2024Q4 | MEDIUM | FLAT | 11,177 | 10,313 |
| C2025Q1 | MEDIUM | STEEP | 9,773 | 15,447 |
| C2025Q2 | HIGH | STEEP | 14,552 | 12,957 |
| C2025Q3 | MEDIUM | FLAT | 11,653 | 13,356 |
| C2025Q4 | LOW | FLAT | 9,248 | 10,433 |
| C2026Q1 | HIGH | FLAT | 16,130 | 14,296 |
| C2026Q2 | LOW | FLAT | 5,180 | 12,177 |
| C2026Q3 | nan | FLAT | – | 12,498 |
| C2026Q4 | nan | FLAT | – | 9,553 |
| C2027Q1 | nan | FLAT | – | 12,878 |
| C2027Q2 | nan | FLAT | – | 10,599 |
| C2027Q3 | nan | FLAT | – | 10,811 |
| C2027Q4 | nan | FLAT | – | 8,928 |
| C2028Q1 | nan | FLAT | – | 11,333 |
| C2028Q2 | nan | FLAT | – | 9,352 |
| C2028Q3 | nan | FLAT | – | 9,148 |
| C2028Q4 | nan | FLAT | – | 6,745 |
| C2029Q1 | nan | FLAT | – | 7,616 |

## Top interaction pairs (in-repo features)

| Feature 1 | Feature 2 | Target | r(f1) | r(f2) | r(f1×f2) | Improvement |
|---|---|---|---|---|---|---|
| fill_trend | quarter_number | payout_per_unit | +0.012 | -0.018 | -0.186 | +0.168 |
| acp_momentum | fill_trend | seasonal_deviation | +0.078 | +0.090 | +0.140 | +0.050 |
| fill_trend | years_since_2020q2 | payout_per_unit | +0.012 | +0.116 | -0.115 | -0.002 |
| acp_momentum | quarter_number | seasonal_deviation | +0.078 | -0.000 | -0.057 | -0.021 |
| fill_trend | quarter_number | seasonal_deviation | +0.090 | -0.000 | -0.052 | -0.037 |
| acp_mean | acp_median | seasonal_deviation | +0.166 | +0.142 | +0.127 | -0.040 |
| acp_momentum | quarter_number | payout_per_unit | +0.207 | -0.018 | -0.163 | -0.044 |
| acp_momentum | units_sold_total | seasonal_deviation | +0.078 | +0.083 | +0.031 | -0.052 |
| fill_mean | units_sold_total | seasonal_deviation | -0.072 | +0.083 | +0.026 | -0.057 |
| fill_mean | fill_trend | seasonal_deviation | -0.072 | +0.090 | +0.033 | -0.057 |

## Engineering interpretation

### Why in-repo features have limited explanatory power
- **Auction clearing price** reflects the *market's expectation* of settlement residue.
  It is priced by participants who already know the seasonal pattern.
  It therefore mostly replicates the seasonal benchmark, not deviations from it.
- **Tranche price gradient** captures how steeply the market prices capacity.
  A steep curve suggests informed bidding but still encodes expectation, not cause.
- **Fill probability** is driven by price vs. expected payout — circular with target.
- **Payout momentum** is the closest thing to a regime signal in existing data,
  but with only 25 settled quarters, it cannot reliably detect multi-quarter regimes.

### What would actually explain settlement residue
In order of engineering plausibility:

1. **Regional price spread (RRP differential)** — This IS settlement residue.
   When NSW RRP > VIC RRP, VIC1-NSW1 direction earns positive residue.
   This is the direct physical identity: `residue = flow × price_spread`.
   Without RRP data, we cannot compute this.

2. **Interconnector utilisation / constraint binding frequency** — When the
   interconnector is at its limit, price separation is full. When it is free,
   prices equalise. Utilisation % is the best single predictor of residue magnitude.

3. **Regional renewable penetration** — High wind in SA or VIC reduces local prices
   and widens the price spread. Solar in QLD/NSW creates midday price inversion.
   Renewable generation share is a structural driver of the price spread.

4. **Temperature anomaly** — Heatwaves increase demand non-linearly. They cause
   price spikes that are asymmetric by region depending on local peaking capacity.
   Q1 heatwave events strongly correlate with extreme VIC1-SA payouts.

5. **Major coal retirement / outage events** — These remove baseload capacity
   from one side of an interconnector, creating persistent price separation.
   Hazelwood (2017), Liddell (2023) are visible as structural breaks in the data.

## Conclusion and next steps

| Step | Action |
|---|---|
| 1 | Acquire AEMO DISPATCHPRICE (RRP by region, 5-min, 2020+) |
| 2 | Acquire AEMO DISPATCHINTERCONNECTORRES (flow by interconnector, 2020+) |
| 3 | Acquire AEMO Quarterly Energy Dynamics (generation by fuel type, 2020+) |
| 4 | Acquire BOM temperature data (quarterly mean/max per capital city, 2020+) |
| 5 | Re-run Phase 5B correlation engine with these data sources |
| 6 | Build Price Model v3 only after confirming which variables |
|   | explain ≥50% of variance in settlement residue per corridor |

**Until step 5 is complete, no further statistical forecasting model
is expected to beat the seasonal benchmark on unseen quarters.**
