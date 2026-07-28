# Feature Store Lineage Report

- Global lineage hash: 7a3cd0d383883ff768636bb5d9b92fb54b99fac82f1ed2f963ea3324d7856026

                  dataset           status  files                                                     lineage_hash                                                     blocker
            DISPATCHPRICE          MISSING    NaN                                                              NaN                                                         NaN
        DISPATCHREGIONSUM        AVAILABLE    1.0 9846533e4096f620b36323c877cc922d8037f663a136269bc293fed8ba09fb7f                                                         NaN
DISPATCHINTERCONNECTORRES        AVAILABLE    1.0 e17da30144e97c4b3fda25ea8877490711871221ca608152a54340b69aa6f61b                                                         NaN
       DISPATCHCONSTRAINT          MISSING    NaN                                                              NaN                                                         NaN
      DISPATCH_UNIT_SCADA          MISSING    NaN                                                              NaN                                                         NaN
        GENERATOR_OUTAGES BLOCKED_EXTERNAL    0.0                                                              NaN                     External outage source not ingested yet
          UNIT_COMMITMENT  DERIVED_PARTIAL    0.0                                                              NaN Derived proxy from SCADA only (no unit technology register)
     RENEWABLE_GENERATION  DERIVED_PARTIAL    0.0                                                              NaN                     No DUID technology map in repo snapshot
                  WEATHER BLOCKED_EXTERNAL    0.0                                                              NaN                            No BOM weather ingest configured
                     FCAS BLOCKED_EXTERNAL    0.0                                                              NaN                  No FCAS dataset ingest in current snapshot
