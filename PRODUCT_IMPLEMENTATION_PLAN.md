# Product Implementation Plan

This plan is the delivery sequence for the next phase of HAIMOS.
It is derived from `VISION.md`, `PROJECT_CONSTITUTION.md`, and the Market Physics corpus.
The repository snapshot does not include a separate product roadmap file, so this document serves as the implementation reference for the next work cycle.

## Program Intent

The Digital Twin is complete. The repository is preserved. The next objective is not to improve engineering for its own sake, but to convert deterministic market understanding into institutional investment intelligence.

The delivery path is:

Raw Data
↓
Digital Twin
↓
Market Physics
↓
Knowledge Graph
↓
Forecast Engine
↓
Fair Value Engine
↓
Opportunity Engine
↓
Portfolio Optimiser
↓
Investment Lifecycle Engine
↓
Bloomberg Dashboard

## Phase 6B — Complete the Market State

**Objective**
Complete the NEM State Vector so every major physical driver of congestion is represented.

**Dependencies**
- Frozen Digital Twin baseline
- Existing market-state infrastructure
- PIT-safe historical raw datasets
- State vector ontology and lineage conventions

**Entry Criteria**
- State vector definition is stable
- Required source datasets are identified
- Lineage and validation standards are agreed

**Exit Criteria**
- Observable physical state is represented at every dispatch interval
- Deterministic datasets exist for the major state drivers
- Each dataset has lineage, PIT validation, completeness, and quality reporting

**Estimated Effort**
- Medium to high

**Commercial Capability Unlocked**
- A complete observable market-state foundation for valuation and causal reasoning
- Better congestion visibility and stronger explainability for downstream decisions

**Technical Risk**
- Data completeness gaps
- Schema drift across source files
- Hard-to-reconcile point-in-time state reconstruction

**Research Risk**
- Some drivers may be observable only indirectly or with partial coverage
- Hidden state may remain after all practical datasets are added

## Phase 6C — Mechanism Discovery

**Objective**
Discover causal market laws, one mechanism per research cycle.

**Dependencies**
- Completed market state
- Research doctrine and pre-registration discipline
- Knowledge Graph update rules
- Research Journal and evidence logging

**Entry Criteria**
- Mechanism selection is ranked and pre-registered
- Uncertainty statement is defined
- Acceptance and falsification criteria are fixed before testing

**Exit Criteria**
- Each cycle ends with an accepted, rejected, or conditional law
- Accepted laws are added permanently to the theory and knowledge graph
- Rejected laws remain documented and auditable

**Estimated Effort**
- Ongoing / medium per cycle

**Commercial Capability Unlocked**
- Causal narratives for congestion, transfer, and value creation
- Explainable differentiation between signal and noise

**Technical Risk**
- Overfitting a mechanism to one regime
- Threshold drift after seeing results
- Incomplete causal observability

**Research Risk**
- The strongest mechanism may not be the most obvious one
- Some candidate laws may be rejected repeatedly before the dominant causal structure is found

## Phase 6D — State Forecasting

**Objective**
Forecast future Market State, not prices.

**Dependencies**
- Completed market state
- Validated or conditionally supported mechanisms
- Knowledge Graph relationships for state transitions

**Entry Criteria**
- State variables and causal drivers are defined
- Forecast targets are limited to observable state quantities
- Explainability requirements are explicit

**Exit Criteria**
- Forecasts exist for demand, generation, transfer capability, congestion probability, constraint activation, and transmission utilisation
- Forecast outputs remain explainable and PIT-safe

**Estimated Effort**
- Medium

**Commercial Capability Unlocked**
- Better forward visibility into physical market conditions
- Inputs required for fair value and opportunity evaluation

**Technical Risk**
- Forecasting the wrong layer
- Black-box drift
- Weak out-of-sample stability across regimes

**Research Risk**
- Forecast utility may depend more on regime detection and causal completeness than model complexity

## Phase 7 — Fair Value Engine

**Objective**
Calculate intrinsic value for every SRA product.

**Dependencies**
- Forecasted market state
- Validated causal relationships
- Product definitions and settlement logic
- Historical IRSR and valuation reference data

**Entry Criteria**
- Product universe is defined
- Forecast state feeds are available
- Valuation conventions are fixed

**Exit Criteria**
- Every product has expected IRSR, fair value, uncertainty, confidence, scenario range, downside, and upside
- A fair value database is produced

**Estimated Effort**
- Medium to high

**Commercial Capability Unlocked**
- Product-level intrinsic valuation
- Basis for ranking opportunity and allocating capital

**Technical Risk**
- Mis-specified cashflow assumptions
- Boundary mismatches between state forecast and product economics
- Scenario inconsistency

**Research Risk**
- Fair value may be sensitive to regime segmentation and settlement assumptions

## Phase 8 — Opportunity Engine

**Objective**
Determine whether each auction product is overpriced, fairly priced, or underpriced.

**Dependencies**
- Fair value engine
- Product pricing and auction data
- Risk and confidence conventions

**Entry Criteria**
- Fair value outputs are stable enough to compare against auction price
- Ranking methodology is defined

**Exit Criteria**
- Every opportunity is ranked by expected edge, confidence, expected return, risk-adjusted return, expected IRR, and capital efficiency
- Opportunity classifications are reproducible and auditable

**Estimated Effort**
- Medium

**Commercial Capability Unlocked**
- Opportunity ranking across the full product set
- Decision support for auction participation

**Technical Risk**
- Ranking instability
- Sensitivity to confidence calibration
- Overstating edge when uncertainty is high

**Research Risk**
- Opportunity may be unevenly distributed across corridors, quarters, and regimes

## Phase 9 — Portfolio Optimiser

**Objective**
Determine what to buy, how much, when, and under what capital and risk constraints.

**Dependencies**
- Opportunity engine
- Capital and liquidity constraints
- Portfolio risk framework
- Investment lifecycle assumptions

**Entry Criteria**
- Ranked opportunities exist
- Portfolio constraints are defined
- Exposure, diversification, and cash usage rules are set

**Exit Criteria**
- Optimal portfolio recommendations are produced
- Capital allocation, diversification, liquidity, risk, and maximum exposure are jointly considered

**Estimated Effort**
- Medium

**Commercial Capability Unlocked**
- Portfolio construction rather than single-product ranking
- A capital allocation layer suitable for institutional use

**Technical Risk**
- Optimiser overfits to assumptions
- Constraint mis-specification
- Concentration risk hidden by aggregate metrics

**Research Risk**
- The highest-edge product may not be the best portfolio choice
- Portfolio-level trade-offs may dominate product-level attractiveness

## Phase 10 — Investment Lifecycle Engine

**Objective**
Model the complete investment lifecycle from auction to capital release and reinvestment.

**Dependencies**
- Portfolio optimiser
- Settlement and cashflow conventions
- Timing assumptions
- Product-level expected returns

**Entry Criteria**
- Investment recommendations exist
- Settlement schedule logic is defined
- Cashflow mapping is reproducible

**Exit Criteria**
- For every investment, the system can calculate auction date, purchase cost, capital committed, lock-up duration, settlement timing, expected quarterly and monthly cashflows, IRR, NPV, capital release date, reinvestment opportunity, and portfolio cash balance through time
- Institutional cashflow model is available

**Estimated Effort**
- Medium

**Commercial Capability Unlocked**
- Capital planning across time
- Full lifecycle analysis rather than point-estimate valuation

**Technical Risk**
- Cashflow timing errors
- Misalignment between settlement and accounting periods
- Circular dependence between release timing and reinvestment capacity

**Research Risk**
- Lifecycle value may depend on portfolio scale, turnover, and auction cadence

## Phase 11 — Bloomberg Dashboard

**Objective**
Create the institutional interface that ends with portfolio outcomes, not recommendations.

**Dependencies**
- Market state
- Knowledge graph
- Forecast state
- Fair value engine
- Opportunity engine
- Portfolio optimiser
- Investment lifecycle engine

**Entry Criteria**
- Core investment intelligence outputs exist
- Explainability requirements are defined
- Portfolio outcome metrics are available

**Exit Criteria**
- The dashboard presents market overview, current state, physical drivers, knowledge graph, forecast state, opportunity scanner, fair value rankings, recommended purchases, portfolio allocation, cash position, locked capital, expected income, IRR, NPV, scenario analysis, historical performance, and explainability
- The dashboard answers: what should I buy, why, how much, when, how confident, how it affects the portfolio, and when capital becomes available again

**Estimated Effort**
- High

**Commercial Capability Unlocked**
- Institutional-grade decision interface
- Portfolio outcome visibility and executive-level usability

**Technical Risk**
- Information overload
- Weak hierarchy between insight layers
- Poor explainability of recommendations or portfolio outcomes

**Research Risk**
- The dashboard may expose gaps in upstream causal or valuation logic
- The final product must remain faithful to the evidence rather than cosmetically polished

## Cross-Phase Dependencies

- Phase 6B is required before Phase 6C, 6D, 7, 8, 9, 10, and 11.
- Phase 6C improves the Knowledge Graph and theory used by all downstream phases.
- Phase 6D is required before fair value, opportunity ranking, and portfolio optimisation.
- Phase 7 is required before Phases 8 through 11.
- Phase 8 is required before portfolio optimisation and lifecycle modelling.
- Phase 9 is required before lifecycle modelling and dashboard recommendation logic.
- Phase 10 is required for portfolio outcome reporting.
- Phase 11 is the final presentation layer and must not outrun upstream evidence.

## North Star

Every experiment, every model, every line of code, and every product feature must demonstrably improve the quality of an investment decision.
