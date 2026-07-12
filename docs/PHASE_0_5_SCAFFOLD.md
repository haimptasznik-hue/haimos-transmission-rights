# Phase 0.5: AEMO Digital Twin Scaffold

**Status:** ✅ Complete (11 modules, data models, golden test stubs)  
**Date:** 11 July 2026  
**Deliverable:** Module structure for Phases 1–4 development

---

## Overview

Phase 0.5 establishes the complete module architecture for the AEMO digital twin. All 11 native modules are scaffolded with:
- Full Pydantic/dataclass schemas
- Core method signatures and docstrings
- Golden test stubs (to be filled in Phase 1–2)
- Comprehensive type hints

This enables parallel work on:
- **Phase 1:** Product registry ingestion, historical data download
- **Phase 2:** IRSR calculation and distribution engine calibration
- **Phase 3:** Fair-value model and mark engine
- **Phase 4:** Position ledger and execution adapter

---

## Module Manifest

### Core Modules (`services/aemo/`)

#### 1. **sra_product_registry.py**
**Responsibility:** Directional interconnectors, categories, quarters, tranches, max units and proportions.

**Key classes:**
- `SRAProduct`: Immutable versioned product definition
- `SRAProductRegistry`: Registry with historical point-in-time queries

**Phase 1 objective:** Ingest AEMO's max-units and proportions table (effective 1 May 2026 onwards) and all historical snapshots.

```python
registry = SRAProductRegistry()
product = SRAProduct(
    product_id="NSW1-VIC1_C2028Q1",
    ...
    effective_date=date(2026, 5, 1),
)
registry.register_product(product)
product_at_date = registry.get_product("NSW1-VIC1_C2028Q1", as_of_date=date(2027, 9, 1))
```

---

#### 2. **sra_market_calendar.py**
**Responsibility:** Auction opening/closing dates, notices and product availability.

**Key classes:**
- `AuctionEvent`: Calendar entry for an SRA auction
- `SRAMarketCalendar`: Calendar manager

**Phase 1 objective:** Fetch and store SRA auction dates 2025–2026 from AEMO.

```python
calendar = SRAMarketCalendar()
calendar.add_event(event)
active = calendar.get_active_auctions()
upcoming = calendar.get_upcoming_auctions(limit=5)
```

---

#### 3. **sra_irssr_calculator.py**
**Responsibility:** Interval IRSR calculation using prices, adjusted flows and losses.

**Key classes:**
- `IRSRInterval`: Calculated IRSR for a single 5-minute interval
- `SRAIRSRCalculator`: Static calculator methods

**Phase 2 objective:** Implement AEMO's interval IRSR formula and validate golden test (Appendix B1).

```python
irsr = SRAIRSRCalculator.calculate_interval_irsr(
    trading_interval="2026-07-10T15:55:00Z",
    from_region_price=Decimal("30"),
    to_region_price=Decimal("50"),
    notional_flow_mw=Decimal("30"),
    transmission_loss_mw=Decimal("3"),
)
# Expected: $490 per AEMO Appendix B1
```

**Golden test:** `test_golden_test_appendix_b1()` validates exact reproduction of AEMO worked example.

---

#### 4. **sra_distribution_engine.py**
**Responsibility:** Settlement allocation, unsold-unit treatment, negative-residue rules, settlement revisions, minimum payment and fees.

**Key classes:**
- `CategoryDistribution`: Distributable IRSR for a category/quarter
- `SettlementRunEnum`: R0, R1, R2, FINAL
- `SRADistributionEngine`: Allocation calculator

**Phase 2 objective:** Implement full settlement rules and reconcile to AEMO settlement runs.

```python
distribution = SRADistributionEngine.create_distribution_record(
    category_id="NSW1-VIC1",
    relevant_quarter="C2028Q1",
    settlement_run=SettlementRunEnum.FINAL,
    total_irsr_dollars=Decimal("5500000"),
    settlement_costs_dollars=Decimal("50000"),
    units_issued=1000,
    units_sold=840,
)
payout = SRADistributionEngine.payout_per_unit(distribution)
```

---

#### 5. **sra_auction_parser.py**
**Responsibility:** Bid/offer schemas, public results, clearing and cancellation prices.

**Key classes:**
- `AuctionResult`: Result of a single SRA auction
- `CancellationResult`: Secondary auction result
- `SRAAuctionParser`: Parser and query interface

**Phase 1 objective:** Ingest SRA_Results clearing prices and Units for all completed tranches.

```python
parser = SRAAuctionParser()
parser.add_auction_result(result)
clearing_price = parser.get_clearing_price("NSW1-VIC1", "C2028Q1", tranche_no=1)
units_sold = parser.get_units_sold("NSW1-VIC1", "C2028Q1")
```

---

#### 6. **sra_position_ledger.py**
**Responsibility:** SRDAs, Units, acquisition cost, cancellations, assignments, accrued/settled value.

**Key classes:**
- `SRDAPosition`: Single position with status and valuations
- `PositionStatusEnum`: BID, ALLOCATED, OFFERED, CANCELLED, ASSIGNED, SETTLED, EXPIRED
- `SRAPositionLedger`: Full ledger with P&L tracking

**Phase 4 objective:** Track all positions with full audit trail and partial assignment support.

```python
ledger = SRAPositionLedger()
ledger.add_position(position)
ledger.update_valuations("SRDA_001", accrued=Decimal("50000"), forward=Decimal("120000"))
pnl = ledger.portfolio_pnl()
new_srda = ledger.partial_assignment("SRDA_001", units_assigned=10)
```

---

#### 7. **sra_historical_replay.py**
**Responsibility:** Point-in-time reconstruction of IRSR and distributions with settlement revisions.

**Key classes:**
- `HistoricalSnapshot`: Point-in-time IRSR/distribution record
- `SRAHistoricalReplay`: Versioned snapshot registry

**Phase 2 objective:** Reconstruct historical IRSR and distributions using effective-date snapshots.

```python
replay = SRAHistoricalReplay()
replay.add_snapshot(snapshot)
snapshot = replay.get_snapshot("NSW1-VIC1", "C2028Q1", as_of_date=date(2028, 3, 31), settlement_run=SettlementRunEnum.FINAL)
all_runs = replay.get_all_runs("NSW1-VIC1", "C2028Q1")
deltas = replay.reconciliation_delta("NSW1-VIC1", "C2028Q1")
```

---

#### 8. **sra_forecast_engine.py**
**Responsibility:** Scenario and probabilistic future IRSR.

**Key classes:**
- `IRSRScenario`: Probabilistic forecast (low/base/high)
- `ScenarioTypeEnum`: LOW, BASE, HIGH
- `SRAForecastEngine`: Scenario manager and aggregator

**Phase 3 objective:** Build scenario trees and probability distributions.

```python
forecast = SRAForecastEngine()
forecast.add_scenario(scenario_low)
forecast.add_scenario(scenario_base)
forecast.add_scenario(scenario_high)
expected_irsr = forecast.probability_weighted_irsr("NSW1-VIC1", "C2028Q1")
p95_irsr = forecast.percentile_irsr("NSW1-VIC1", "C2028Q1", percentile=95)
```

---

#### 9. **sra_mark_engine.py**
**Responsibility:** Clean value, risk-adjusted value, bid/mid/offer and confidence.

**Key classes:**
- `SRAMark`: Complete valuation mark (updated every 5 minutes)
- `SRAMarkEngine`: Mark calculator and validator

**Phase 3 objective:** Compute 5-minute marks with confidence scores and driver attribution.

```python
mark = SRAMarkEngine.compute_mark(
    product_id="NSW1-VIC1_C2028Q1",
    category_id="NSW1-VIC1",
    relevant_quarter="C2028Q1",
    accrued_value_per_unit=Decimal("0"),
    forward_expected_value_per_unit=Decimal("4000"),
    model_risk_discount=Decimal("0.05"),
    liquidity_discount=Decimal("0.03"),
)
# mark.clean_fair_value, mark.bid_mark, mark.mid_mark, mark.offer_mark, mark.confidence_score
is_valid, msg = SRAMarkEngine.validate_mark(mark)
```

---

#### 10. **sra_execution_adapter.py**
**Responsibility:** AEMO file generation, validation, submission and acknowledgements.

**Key classes:**
- `BidOfferOrder`: Single bid/offer for submission
- `BidOfferTypeEnum`: BID or OFFER
- `SubmissionAcknowledgement`: AEMO receipt confirmation
- `SRAExecutionAdapter`: Submission orchestrator

**Phase 4 objective:** Generate AEMO-compliant files and manage submission workflow.

```python
adapter = SRAExecutionAdapter(participant_id="PARTICIPANT_001")
adapter.add_order(order1)
adapter.add_order(order2)
is_valid, errors = adapter.validate_orders([order1, order2])
csv_file = adapter.generate_aemo_file([order1, order2], file_format="csv")
adapter.register_acknowledgement(ack)
recon = adapter.reconcile_with_aemo_results(aemo_results_dict)
```

---

### Adapter Modules (`adapters/aemo/`)

#### 11. **historical_data_fetcher.py**
**Responsibility:** Downloads and manages archived DISPATCH_IRSR, SRA_Results and product definitions.

**Key classes:**
- `HistoricalDataFetcher`: Archive manager with reconciliation reporting

**Phase 1 objective:** Integrate with existing `aemo_feeds.py` to fetch and cache historical data.

```python
fetcher = HistoricalDataFetcher()
fetcher.fetch_dispatch_irsr_range("C2027Q3", "C2028Q2")
fetcher.fetch_sra_results_range("C2027Q3", "C2028Q2")
report = fetcher.reconciliation_report("NSW1-VIC1", "C2028Q1")
```

---

## Test Coverage

### Test file: `tests/test_aemo_modules.py`

**Golden tests (Blueprint compliance):**
- ✅ `test_golden_test_appendix_b1()` — Validates IRSR calculation against AEMO worked example
- ⏳ `test_reconciliation_quarterly_totals()` — (Phase 2) Reconcile historical quarters to AEMO settlement
- ⏳ `test_historical_replay_point_in_time()` — (Phase 2) Verify effective-date queries
- ⏳ `test_fair_value_backtest_mape()` — (Phase 3) Validate <5% MAPE on historical data

**Unit tests:**
- ✅ `TestSRAProductRegistry`: Registration, versioning, queries by interconnector/quarter
- ✅ `TestSRAIRSRCalculator`: Forward/reverse flows, loss apportionment
- ✅ `TestSRADistributionEngine`: Distribution calculations, payout per unit
- ✅ `TestSRAMarkEngine`: Mark computation, bid/mid/offer, validation
- ✅ `TestSRAPositionLedger`: Position tracking, P&L, partial assignments
- ⏳ `TestSRAAuctionParser`: Result ingestion, price queries
- ⏳ `TestSRAHistoricalReplay`: Snapshot storage and reconciliation
- ⏳ `TestSRAForecastEngine`: Scenario aggregation, percentiles
- ⏳ `TestSRAExecutionAdapter`: File generation, validation, reconciliation

**Run tests:**
```bash
cd /Users/haimptasznik/Desktop/haimos-transmission-rights
python -m pytest tests/test_aemo_modules.py -v
```

---

## Integration Points

### With existing codebase:

1. **`domain/models.py`:** Existing Pydantic models (SRAProduct, FairValueRequest, etc.)
   - Phase 0.5: No changes; existing models remain as is
   - Phase 3: Integrate with `SRAMark` output

2. **`adapters/aemo_feeds.py`:** Existing NEMWeb data fetcher
   - Phase 1: Refactor to use `HistoricalDataFetcher` for archive management
   - Phase 1: Keep live DISPATCH_IRSR and SRA_Results fetchers

3. **`services/valuation.py`:** Existing MVP fair-value engine
   - Phase 3: Refactor to use `SRAMarkEngine` for full mark computation
   - Phase 3: Integrate `SRAForecastEngine` for scenario weighting

4. **`api/main.py`:** Existing FastAPI application
   - Phase 1: No changes; add new endpoints in Phase 3
   - Phase 3: Add `/v1/sra/products/{id}/mark`, `/v1/sra/products/{id}/drivers`, etc.

---

## Phased Implementation Roadmap

### Phase 1 (Weeks 3–4): Product Registry & Historical Data
- [ ] Implement `SRAProductRegistry.ingest_aemo_product_data()`
- [ ] Implement `SRAMarketCalendar.fetch_and_parse_aemo_calendar()`
- [ ] Implement `SRAAuctionParser.ingest_historical_results()`
- [ ] Implement `HistoricalDataFetcher.fetch_dispatch_irsr_range()` and `.fetch_sra_results_range()`
- [ ] Golden test: Reproduce AEMO Appendix B1 (passing)

### Phase 2 (Weeks 5–6): IRSR & Distribution
- [ ] Validate `SRAIRSRCalculator` against historical quarters (0.1% tolerance)
- [ ] Implement `SRADistributionEngine` settlement logic (R0/R1/R2/final)
- [ ] Implement `SRAHistoricalReplay` with effective-date queries
- [ ] Golden tests: Historical reconciliation (4–8 quarters passing)

### Phase 3 (Weeks 6–7): Fair Value & Marks
- [ ] Integrate `SRAForecastEngine` with EYE price/flow models
- [ ] Build scenario trees (low/base/high cases)
- [ ] Implement `SRAMarkEngine` with confidence scoring
- [ ] Back-test against historical clearing prices and distributions (<5% MAPE)

### Phase 4 (Weeks 7–8): Execution & Position Tracking
- [ ] Implement `SRAPositionLedger` full ledger logic
- [ ] Implement `SRAExecutionAdapter` file generation (CSV/XML)
- [ ] Pre-production testing with AEMO sandbox
- [ ] Reconciliation service

---

## Key Design Decisions

1. **Immutability:** Core domain objects (`SRAProduct`, `SRDAPosition`, `SRAMark`) are immutable (dataclass `frozen=True`) for audit and replay integrity.

2. **Versioning:** All entities support effective-date versioning (e.g., product definitions, settlements runs R0/R1/R2/final).

3. **Separation of concerns:**
   - **Physical layer:** IRSR calculation, distribution, allocation (Modules 3–7)
   - **Valuation layer:** Forecasting, marking, P&L (Modules 8–9)
   - **Execution layer:** Bidding, submission, reconciliation (Modules 10–11)

4. **Golden tests:** Every module has a golden test against AEMO published data (not just unit tests).

5. **No runtime Vault dependency:** AEMO modules are self-contained; Vault is read-only for discovery.

---

## Next Immediate Actions

1. ✅ **Phase 0.5 scaffold:** All 11 modules created, tests stubbed, ready for Phase 1
2. ⏳ **Phase 1 kickoff:** Begin data ingestion (product registry, historical IRSR/results)
3. ⏳ **Parallel:** Haim schedules AEMO pre-application meeting (Phase 0 regulatory discovery)

---

**Document owner:** Agent  
**Created:** 11 July 2026  
**Next review:** Upon Phase 1 completion (target: 14 July 2026)
