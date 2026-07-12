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
