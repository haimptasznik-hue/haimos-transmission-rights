# Repo Discovery Report

## Objective

Establish a standalone transmission-rights repository without modifying the existing `HaimOS` Vault.

## Safety snapshot

- Vault root: `/Users/haimptasznik/Desktop/HaimOS`
- Treatment: read-only during this project setup
- Observed state: pre-existing dirty working tree in the Vault
- Source provenance baseline: `7ccb04cded0f7c9f4d9cc877f92166bdf93509f0`

## Naming review

Observed sibling naming patterns on Desktop:

- `HaimOS`
- `SolarTool_2026-04-24_v1_Mark1`
- `lanteri-workbench`
- `nem-live-dispatch`

Selected name: `haimos-transmission-rights`

## Relevant reusable capability map

### Strong reuse candidates

- `haimos-app/backend/nem/aemo_fetch.py`
  - live dispatch price ingestion
  - P5MIN and predispatch forecast ingestion
  - historical MMSDM dispatch-price retrieval fallback
  - timezone treatment already aligned to NEM operations
- `haimos-app/backend/nem/aemo_forecast_signals.py`
  - historical forward-looking signal generation
  - adaptive threshold logic
  - event-flag overlay hooks
- `haimos-app/backend/nem/dispatch_runner.py`
  - clean service-style orchestration worth copying patterns from
- `00_Master_Context/EYE_SYSTEM_MAP.md`
  - confirms scenario, simulation, Monte Carlo, and NEM pack architecture intent
- `00_Master_Context/EYE_MODULE_MAP.md`
  - documents market-data and network-related module inventory

### Adjacent but not directly portable

- `haimos-app/backend/nem/fcas_dispatch_engine.py`
  - useful for simulation architecture and NEM timing conventions
  - domain is asset dispatch, not transmission-right valuation
- `haimos-app/backend/server.py`
  - useful API integration reference
  - too coupled to the current monolith to copy directly
- `haimos-app/backend/nna_parser.py`
  - indicates constraint-driver and network-opportunity parsing patterns
  - likely more relevant for congestion context than core SRA settlement logic

### Gaps identified

This repo still needs dedicated modules for:

- controlled SRA product catalog ingestion,
- maximum-unit and unit-proportion versioning,
- exact historical IRSR reconstruction by directional interconnector and quarter,
- auction result ingestion and tranche-level replay,
- position ledger and assignment/cancellation state tracking,
- confidence-band calibration against realised distributions,
- model-risk disclosure and governance evidence.

## Copy strategy summary

- `Copy/adapt`: narrow utilities and data-ingestion patterns where stable and provenance can be preserved
- `Reimplement`: SRA domain model, valuation engine, and product lifecycle logic
- `Defer`: submission automation, MarketNet connectivity, and bilateral assignment workflows requiring legal/AEMO confirmation

## Conclusion

The Vault contains enough NEM market-data and simulation scaffolding to accelerate this project, but not the SRA-specific product and settlement layer. A separate repository is justified and required.
