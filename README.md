# Start Here

Anyone contributing to HAIMOS must read these documents in this order before beginning work:

1. `VISION.md` — the long-term purpose and North Star for the platform.
2. `docs/HAIMOS_MARKET_PHYSICS_ENGINE_V1_ARCHITECTURE.md` — the frozen architectural baseline.
3. `docs/MARKET_PHYSICS_MANIFESTO.md` — the physics-first research rationale.
4. `docs/MARKET_PHYSICS_THEORY.md` — the current causal theory of the market.
5. `docs/MARKET_PHYSICS_KNOWLEDGE_GRAPH.md` — the structured reasoning layer and evidence graph.
6. `docs/Research Journal.md` — the laboratory notebook and experiment record.
7. `docs/MARKET_PHYSICS_RESEARCH_LOG.md` — the operational command centre for the research program.

For contribution rules and project governance, also read:

- `CONTRIBUTING.md` — how research and engineering work is performed.
- `PROJECT_CONSTITUTION.md` — the governing charter for decisions, research, and product scope.
- `docs/DOCUMENTATION_MAP.md` — the navigation map from vision to implementation.

## Phase 6 Navigation

The following documents define the active Phase 6 program and are reachable from this repository entry point:

- `CHIEF_RESEARCH_ANALYST_ROLE.md` — the operating role definition for research leadership.
- `PHASE6_INDEX.md` — index of the Phase 6 corpus and reading path.
- `PHASE6_README.md` — high-level overview of Phase 6 work.
- `PHASE6_QUICK_START.md` — the shortest path to the current Phase 6 workflow.
- `PHASE6_LAUNCH_CHECKLIST.md` — the launch checklist for Phase 6 work.
- `PHASE6_CAUSAL_CONGESTION_RESEARCH.md` — the Phase 6 causal congestion research frame.
- `docs/PHASE6A_RECOMMENDATIONS.md` — recommendations that followed the Phase 6A research phase.
- `docs/PHASE_6B_0_RESEARCH_PROGRAM_DESIGN.md` — design for the Phase 6B research program.
- `docs/LAW_001_EXPERIMENT.md` — first pre-registered market physics experiment.
- `docs/LAW_002_EXPERIMENT.md` — follow-on experiment focused on residual transmission state.
- `docs/EXP_001_READINESS_ASSESSMENT.md` — readiness assessment for the first experiment cycle.
- `reports/EXP_001_DATA_QUALITY.md` — concise quality summary for the first experiment cycle.
- `reports/EXP_001_RESULTS.md` — results from the first experiment cycle.
- `reports/EXP_002_METADATA.json` — compact metadata for the second experiment cycle.
- `reports/EXP_002_RESULTS.md` — results from the second experiment cycle.
- `docs/MARKET_PHYSICS_MANIFESTO.md` — physics-first research rationale.
- `docs/MARKET_PHYSICS_THEORY.md` — current theory of the NEM.
- `docs/MARKET_PHYSICS_KNOWLEDGE_GRAPH.md` — evidence-backed causal structure.
- `docs/MARKET_PHYSICS_RESEARCH_LOG.md` — operating command centre for the research program.
- `docs/Research Journal.md` — experiment notebook and falsification record.

# HaimOS Transmission Rights

Independent price discovery engine for Australian NEM transmission rights, focused first on AEMO Settlement Residue Auction (SRA) products.

## Scope

This repository is intentionally separate from the main `HaimOS` Vault. The Vault was treated as read-only discovery input only. Any reuse from that codebase must occur through explicit copy, adaptation, or API boundaries recorded in `migration/`.

## Initial objective

Build a transparent valuation terminal and API for directional interconnector-quarter SRA products with:

- controlled product definitions,
- historical IRSR reconstruction,
- forward fair value estimation,
- confidence bands and sensitivities,
- auction-result replay,
- clear model lineage and disclosure.

## Why a separate repo

- protects the existing Vault from accidental change,
- preserves clean git history for transmission-rights work,
- forces explicit dependency and provenance tracking,
- supports eventual standalone deployment and governance.

## Chosen repository name

`haimos-transmission-rights`

Reasoning:

- consistent with the wider `haimos-*` naming pattern,
- broader than only auction execution,
- accommodates SRA valuation, secondary transfer support, APIs, and future OTC tooling.

## Current scaffold

- `src/transmission_rights/`: domain models, valuation logic, API stubs, adapters
- `docs/`: architecture, methodology, data sources, roadmap, discovery
- `migration/`: provenance, dependency mapping, copy/adapt/defer register
- `tests/`: initial unit coverage for valuation logic

## Initial API surface

- `GET /health`
- `GET /products/example`
- `POST /valuation/fair-value`

## UX-ready API surface

For the first UI integration pass, the API now exposes read-oriented fair-value endpoints:

- `GET /ux/fair-value/summary`
- `GET /ux/fair-value/quarterly?limit=50`
- `GET /ux/fair-value/diagnostics?limit=50`
- `GET /ux/fair-value/dashboard?quarterly_limit=20&diagnostics_limit=20`

These endpoints read generated artifacts from `data/derived/fair_value/` and return safe
`status="missing"` payloads when artifacts are not present yet.

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn transmission_rights.api.main:app --reload
pytest
```

## Read-only discovery summary

Existing Vault capabilities relevant to this repo include:

- live NEM dispatch and forecast ingestion in `haimos-app/backend/nem/aemo_fetch.py`,
- forecast/backcast signal logic in `haimos-app/backend/nem/aemo_forecast_signals.py`,
- dispatch and backcast orchestration in `haimos-app/backend/nem/dispatch_runner.py`,
- architecture references in `00_Master_Context/EYE_SYSTEM_MAP.md`, `00_Master_Context/EYE_MODULE_MAP.md`, and `05_System/HaimOS - NEM Module.md`,
- network and constraint-adjacent parsing hints in `haimos-app/backend/nna_parser.py`.

Those findings are captured formally in `docs/repo_discovery_report.md` and `migration/`.

## Next implementation phases

1. ingest controlled AEMO product and auction reference tables,
2. build exact historical IRSR reconstruction by directional interconnector,
3. calibrate fair-value models against realised distributions and auction clears,
4. add scenario and probabilistic overlays,
5. layer auction execution and OTC transfer tooling only after price discovery is credible.

## Phase 1 ingestion (implemented)

`HistoricalDataFetcher` now includes concrete ingestion methods for:

- listing/downloading `SRA_Results`, `Auction_Units_Reports`, `SRA_Bids`, and `SRA_Offers`,
- parsing `SRA_Results` into contract-level product snapshots,
- loading `SRAProductRegistry` and `SRAMarketCalendar` from ingested data,
- fetching AUCUNITS snapshots as-of an effective date.

Run the ingestion harness:

```bash
python scripts/ingest_aemo_phase1.py
```

Run ingestion tests:

```bash
pytest tests/test_aemo_ingestion.py -v
```

Bulk-download product datasets (results, units, bids, offers):

```bash
python scripts/download_aemo_product_data.py
```

Reconstruct historical IRSR from `Dispatch_IRSR` and optionally reconcile with `AUCUNITS`:

```bash
python scripts/reconstruct_historical_irsr.py --start-quarter C2026Q2 --end-quarter C2026Q3 --reconcile-quarter C2026Q3
```
