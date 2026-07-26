# Market Physics Research Log

**Operational Command Centre** — Updated 2026-07-16

## 1. Overall Progress

**Market Physics Program Completion:** ███░░░░░░░ 30%

| Metric | Value |
|---|---:|
| Mechanisms Identified | 22 |
| Mechanisms Tested | 2 |
| Accepted Laws | 0 |
| Conditional Laws | 1 |
| Rejected Laws | 1 |
| Inconclusive Laws | 0 |
| Confidence in Market Model | 24% |

## 2. Research Pipeline

| Phase / Law | Status | Notes |
|---|---|---|
| `Phase 6A` | ✅ Complete | Market State Ontology and coverage architecture defined |
| `Phase 6B.0` | ✅ Complete | Congestion causality tree and mechanism catalogue established |
| `LAW_001` | ❌ Rejected | Regional imbalance alone is insufficient; transmission state mediates flow |
| `LAW_002` | ✅ Conditionally Accepted | Capability/utilisation explains residual flow structure, especially near transfer limits |
| `LAW_003` | ⚪ Waiting | To be chosen from ranked backlog after `LAW_002` decision |

## 3. Highest Value Mechanisms

| Rank | Mechanism | Score | Status |
|---|---|---:|---|
| 1 | Interconnector Capability | 97 | Ready |
| 2 | Binding Constraints | 95 | Ready |
| 3 | Generator Outages | 91 | Planned |
| 4 | Wind Ramps | 89 | Planned |
| 5 | Interconnector Utilisation | 88 | Ready |
| 6 | Planned Outages / Deratings | 86 | Planned |

## 4. Biggest Unknowns

| ID | Unknown | Status | Priority | Next Step |
|---|---|---|---|---|
| `KU-010` | QNI sign convention | CLOSED | Critical | Frozen and validated against AEMO registry orientation |
| `KU-011` | C2024Q4 `DISPATCHREGIONSUM` schema completeness | CLOSED | High | Required fields confirmed present |
| `KU-013` | Residual transmission state | PARTIALLY RESOLVED | HIGH | Capability/utilisation now explains a material share of residual structure; detailed constraints/outages still unresolved |

## 5. Current Objective

**Determine why desired transfer does not equal actual transfer.**

## 6. Commercial Impact

| Research Area | Impact |
|---|---:|
| SRA Valuation | ██████░░░░ |
| BESS Dispatch | ████░░░░░░ |
| Congestion Forecasting | ███░░░░░░░ |
| Renewable Project Valuation | ████░░░░░░ |
| Transmission Planning / Network Investment | ███████░░░ |

## 7. Experiment Queue

| Experiment | EIG | Effort | Priority |
|---|---:|---|---:|
| `LAW_002` | 96 | Medium | 1 |
| `LAW_003` | 78 | Low | 2 |
| `LAW_004` | 41 | High | 7 |

## 8. Program Notes

- **LAW_001:** rejected honestly; strong fit, failed directional and stability gates.
- **Phase 6B.0:** converted research drift into a ranked mechanism backlog.
- **Research posture:** choose experiments from the catalogue, not from residual intuition.
- **Frozen boundary:** the Digital Twin stays locked until a law is pre-registered and approved for execution.

## 9. Governance

- **Model Freeze:** Digital Twin locked; all Phase 6 work uses PIT-safe historical data only.
- **Pre-Registration:** All laws specified before implementation.
- **Immutability:** Rejected results are permanent; no threshold retroactively changes after results.
- **Verdict Taxonomy:** Accepted / Conditionally Accepted / Rejected / Inconclusive.
- **Audit Trail:** All experiments recorded in `docs/Research Journal.md` and related `EXP_*` reports.

---

*Last updated: 2026-07-16*
