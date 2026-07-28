# Feature Store Build Status

## Build Summary
- Start date: 2024-10-01
- End date: 2024-10-31
- Interval coverage (%): 100.0
- Feature columns: 31
- Duplicate interval keys: 0

## Blockers
             dataset           status  rows  files lineage_hash min_interval max_interval  intervention1_rows_excluded  intervention_pairs_differ                                                     blocker build_window
   GENERATOR_OUTAGES BLOCKED_EXTERNAL     0    0.0          NaN          NaN          NaN                          NaN                        NaN                     External outage source not ingested yet      2024-10
     UNIT_COMMITMENT  DERIVED_PARTIAL     0    0.0          NaN          NaN          NaN                          NaN                        NaN Derived proxy from SCADA only (no unit technology register)      2024-10
RENEWABLE_GENERATION  DERIVED_PARTIAL     0    0.0          NaN          NaN          NaN                          NaN                        NaN                     No DUID technology map in repo snapshot      2024-10
             WEATHER BLOCKED_EXTERNAL     0    0.0          NaN          NaN          NaN                          NaN                        NaN                            No BOM weather ingest configured      2024-10
                FCAS BLOCKED_EXTERNAL     0    0.0          NaN          NaN          NaN                          NaN                        NaN                  No FCAS dataset ingest in current snapshot      2024-10
