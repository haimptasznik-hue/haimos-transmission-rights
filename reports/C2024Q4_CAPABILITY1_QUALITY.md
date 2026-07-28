# C2024Q4 Capability 1 Quality

- Rows produced: 158970
- Expected intervals: 26496
- Actual intervals: 26495
- Interval coverage (%): 99.996226
- Duplicate canonical keys: 0
- Missing MWFLOW: 0
- Missing export limits: 0
- Missing import limits: 0
- Missing directional capability: 0
- Missing utilisation: 2118
- Zero-limit intervals: 2103
- Null-limit intervals: 0
- Over-limit intervals: 12124
- Maximum utilisation: 100300020.0
- Timestamp continuity OK: False
- Lineage completeness (%): 100.0
- Excluded INTERVENTION=1 rows: 72
- Paired intervention differences: 69

## Directional checks
- Positive flow intervals: 78627 (correct directional limit rows: 78627)
- Negative flow intervals: 73139 (correct directional limit rows: 73139)
- Zero flow intervals: 7204 (correct directional limit rows: 7204)

## Verdict
- CAPABILITY1_VALIDATED
- Blocker: None

## By direction

flow_direction  intervals  mean_utilisation_pct  max_utilisation_pct  over_limit_count
      negative      73139           2055.123661         1.003000e+08              8920
      positive      78627             67.535395         1.825825e+03              3204
          zero       7204              0.000000         0.000000e+00                 0
