# Phase 5B – Data Acquisition Brief

## Summary
- Total candidate drivers catalogued: 29
- Available / derivable in repo: 8
- Missing (require external sourcing): 21

## Available in repo
| Variable | Source | PIT-safe |
|---|---|---|
| auction_clearing_price | data/derived/sra/sra_auction_results.csv | ✅ |
| auction_clearing_price_momentum | data/derived/sra/sra_auction_results.csv | ✅ |
| auction_fill_probability_trend | data/derived/sra/alpha_database.csv | ✅ |
| tranche_price_gradient | data/derived/sra/sra_auction_results.csv | ✅ |
| setirsurplus_quarterly | data/derived/irsr/setirsurplus_quarterly_all.csv | ❌ |
| quarter_number | data/derived/sra/alpha_database.csv | ✅ |
| years_elapsed_since_market_start | data/derived/sra/alpha_database.csv | ✅ |
| payout_regime_break | data/derived/sra/sra_payout_history.csv | ❌ |

## High-priority external data to acquire
| Variable | Group | Source URL |
|---|---|---|
| regional_reference_price_rrp | Market | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| renewable_penetration_regime | Structural | nan |
| wind_resource_index | Weather | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem |
| temperature_anomaly_quarterly | Weather | http://www.bom.gov.au/climate/data/ |
| network_outage_days | Transmission | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/network-outage-schedule |
| constraint_binding_frequency | Transmission | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| interconnector_utilisation_pct | Transmission | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| major_coal_retirement | Structural | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/planning-and-forecasting/generation-information |
| interconnector_flow_quarterly | Transmission | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| solar_generation_quarterly | Generation | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem |
| wind_generation_quarterly | Generation | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem |
| coal_generation_quarterly | Generation | https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem |
| price_spread_volatility | Market | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| regional_price_spread | Market | https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/ |
| transmission_augmentation | Structural | nan |

## Engineering assessment
- **Most likely dominant drivers (not yet in repo):**
  1. Regional price spread (RRP differential between corridor endpoints)
  2. Interconnector utilisation and constraint binding frequency
  3. Regional renewable penetration regime (wind in SA, solar in QLD/NSW)
  4. Temperature anomaly (heatwave events drive demand spikes)
  5. Major coal retirement flags (structural breaks in baseload pricing)

- **Available in repo today:**
  - Auction clearing price momentum
  - Tranche price gradient (steepness of clearing curve)
  - Fill probability trend
  - CUSUM structural break detection on payout series
  - Quarterly and seasonal indices

- **Conclusion:** The variables most likely to explain settlement residue
  are ALL missing from this repo. The correlation discovery engine can
  quantify the limits of in-repo data, confirm the seasonal benchmark
  is near-optimal for available data, and produce a prioritised acquisition
  roadmap for the data that would enable a genuinely causal model.
