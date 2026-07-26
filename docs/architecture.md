ok # Architecture

## Design principles

- keep the new repository operationally independent from the Vault,
- treat AEMO controlled tables as first-class reference data,
- separate historical reconstruction from forward valuation,
- make calculation lineage inspectable for every published mark,
- defer execution automation until valuation quality is trusted.

## Bounded contexts

### Product Catalog

Responsible for controlled product definitions:

- directional interconnector,
- unit category,
- relevant quarter,
- tranche,
- allocation type,
- maximum units,
- unit proportion,
- auction status.

### Market Data

Responsible for regional price, interconnector flow, losses, outages, constraints, and auction-result inputs.

### IRSR Reconstruction

Transforms historical price and flow inputs into product-level distributable residue estimates that match published AEMO mechanics as closely as possible.

### Valuation Engine

Produces:

- point fair value,
- confidence bands,
- sensitivities,
- scenario decomposition,
- model-risk overlays.

### Position & Lifecycle

Tracks:

- bid intent,
- allocations,
- cancellations,
- assignments,
- settlement periods,
- revisions.

### API & Presentation

Exposes product catalog, valuation, and audit-ready calculation outputs to internal tools and future UI clients.

## Initial component map

- `transmission_rights.domain`: product and valuation models
- `transmission_rights.data`: controlled catalog loaders and reference contracts
- `transmission_rights.adapters`: external-source integration boundaries
- `transmission_rights.services`: fair-value and scenario engines
- `transmission_rights.api`: FastAPI application

## Planned evolution

### Phase 1

- controlled product ingestion
- historical IRSR calculator
- transparent baseline fair-value model
- auction result replay

### Phase 2

- probabilistic forward curves
- outage and constraint scenario overlays
- calibration against realised distributions and auction clears

### Phase 3

- target bid curve generation
- human-in-the-loop auction submission prep
- position and settlement reconciliation

### Phase 4

- OTC assignment support
- indicative marketplace quotes
- transfer workflow orchestration subject to legal and AEMO confirmation
