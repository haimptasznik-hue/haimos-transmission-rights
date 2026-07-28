# Feature Store Completeness Report

- Expected intervals: 8929
- Actual intervals: 8929
- Interval coverage (%): 100.0
- Duplicate interval keys: 0

## Dataset Status

                  dataset           status  rows  files                                                     lineage_hash         min_interval         max_interval  intervention1_rows_excluded  intervention_pairs_differ                                                     blocker build_window
            DISPATCHPRICE          MISSING     0    NaN                                                              NaN                  NaN                  NaN                          NaN                        NaN                                                         NaN      2024-10
        DISPATCHREGIONSUM        AVAILABLE  8928    1.0 9846533e4096f620b36323c877cc922d8037f663a136269bc293fed8ba09fb7f 2024-09-30T14:05:00Z 2024-10-31T14:00:00Z                          NaN                        NaN                                                         NaN      2024-10
DISPATCHINTERCONNECTORRES        AVAILABLE  8928    1.0 e17da30144e97c4b3fda25ea8877490711871221ca608152a54340b69aa6f61b 2024-09-30T14:05:00Z 2024-10-31T14:00:00Z                          0.0                        0.0                                                         NaN      2024-10
       DISPATCHCONSTRAINT          MISSING     0    NaN                                                              NaN                  NaN                  NaN                          NaN                        NaN                                                         NaN      2024-10
      DISPATCH_UNIT_SCADA          MISSING     0    NaN                                                              NaN                  NaN                  NaN                          NaN                        NaN                                                         NaN      2024-10
        GENERATOR_OUTAGES BLOCKED_EXTERNAL     0    0.0                                                              NaN                  NaN                  NaN                          NaN                        NaN                     External outage source not ingested yet      2024-10
          UNIT_COMMITMENT  DERIVED_PARTIAL     0    0.0                                                              NaN                  NaN                  NaN                          NaN                        NaN Derived proxy from SCADA only (no unit technology register)      2024-10
     RENEWABLE_GENERATION  DERIVED_PARTIAL     0    0.0                                                              NaN                  NaN                  NaN                          NaN                        NaN                     No DUID technology map in repo snapshot      2024-10
                  WEATHER BLOCKED_EXTERNAL     0    0.0                                                              NaN                  NaN                  NaN                          NaN                        NaN                            No BOM weather ingest configured      2024-10
                     FCAS BLOCKED_EXTERNAL     0    0.0                                                              NaN                  NaN                  NaN                          NaN                        NaN                  No FCAS dataset ingest in current snapshot      2024-10
