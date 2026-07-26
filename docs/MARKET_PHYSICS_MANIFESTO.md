# Market Physics Manifesto

## Why HAIMOS Exists

Electricity markets are not random.

They are the economic expression of physical systems.

Prices emerge from supply, demand, network topology, engineering constraints, and market rules—not from statistical coincidence.

The objective of HAIMOS is not to predict prices directly.

The objective is to understand the physical mechanisms that produce them.

## Research Philosophy

Every forecasting model must therefore be built on validated physical laws rather than statistical accident.

A model that fits historical data without understanding *why* the data behaves that way will break when the physical system changes state.

A model built on physical first principles will survive market regime shifts because it is grounded in the real constraints and incentives that govern dispatch.

## The Problem with Pure Statistics

- **Overfitting risk:** A statistically good fit may be a coincidence that breaks under new conditions.
- **Black-box danger:** Models that work without explanation are fragile and undefeatable.
- **Downstream instability:** A mis-specified first law propagates error through the entire decision chain.
- **No learning:** When a statistical model breaks, you cannot learn why. When a physical law breaks, it teaches you something profound about the system.

## The Market Physics Approach

1. **Hypothesize a physical mechanism** — not a curve fit, but a causal chain.
2. **Pre-register the test** — fix acceptance criteria before seeing data.
3. **Run the experiment** — use PIT-safe data and frozen model logic.
4. **Accept or reject** — immutably record the outcome.
5. **Learn from rejection** — a failed law reveals a gap in the causal chain.
6. **Refine the hypothesis** — the next law incorporates what the rejection taught.

This is how science works in physics, chemistry, and biology. It is how electricity markets should be modeled.

## Why Rejection Matters

A law that is rejected tells you something vital: there is another governing variable between the cause and the effect.

`LAW_001` asked: *Does regional supply-demand imbalance explain interconnector flow?*

Nature answered: *No.*

That answer is more valuable than a model that passed one statistical test. It narrows the search space and prevents you from building downstream logic on a foundation that will not hold.

Every rejected law is a discovery. It reveals where your understanding is incomplete.

## Frozen Model Doctrine

The Digital Twin is locked during Phase 6 research.

This prevents the temptation to tweak the model until hypotheses pass.

Research that relies on changing the underlying system is not science—it is curve fitting with extra steps.

When a law is rejected, we refine the hypothesis, not the model. We ask better questions about the data, not different questions about the system.

## The Decision Chain

Market Physics Laws support a decision cascade:

```
Market State (measured)
    ↓
Market Physics Laws (validated)
    ↓
Digital Twin (frozen, simulation only)
    ↓
Scenario Engine (probabilistic)
    ↓
Fair Value Estimation (bayesian)
    ↓
Trading Decisions (disciplined)
```

Each layer depends on the layer below. If the foundation is wrong, everything above it is wrong.

Therefore, the foundation must be built on physics, not statistics.

## Commercial Implication

This discipline is slower than throwing machine learning at the problem.

It will also survive market regime shifts that machine learning models cannot.

A transmission rights valuation model built on physical laws can confidently operate across:

- network topology changes,
- new constraint regimes,
- generation mix evolution,
- storage and flexibility deployment,
- market rule adjustments.

A model built on pure statistics will fail at each of these transitions.

## The North Star

When someone suggests:

> "Let's just use XGBoost to predict flow / prices / congestion"

The answer is not "that won't work."

The answer is:

> "XGBoost can tell us whether a pattern exists. It cannot tell us why. A trading system built on a pattern it does not understand is fragile. We build on physical laws instead."

This manifesto is the rationale for that choice.

## What Good Looks Like

Phase 6B will be successful when:

- [ ] Multiple laws have been tested (not just `LAW_001`).
- [ ] Some laws are accepted because they pass rigorous gates, not because they fit well.
- [ ] Rejected laws teach us about causal gaps in our understanding.
- [ ] The research record shows immutable pre-registration and honest rejection.
- [ ] Downstream models (forecasting, fair value, trading) reference specific validated laws.
- [ ] Contributors new to the project can read this manifesto and understand why the project takes a physics-first approach.

## References

- `docs/LAW_001_EXPERIMENT.md` — First market physics law specification and result.
- `docs/LAW_002_EXPERIMENT.md` — Residual investigation following `LAW_001` rejection.
- `docs/MARKET_PHYSICS_THEORY.md` — Living theory of how the NEM currently works.
- `docs/MARKET_PHYSICS_KNOWLEDGE_GRAPH.md` — Machine-readable causal structure for the NEM.
- `docs/Research Journal.md` — Detailed lab notebook for all experiments.
- `docs/MARKET_PHYSICS_RESEARCH_LOG.md` — Command centre for program status, metrics, and experiment prioritisation.

---

*Version 1.0 — 2026-07-16*

*This manifesto will be updated as Phase 6B evolves. Each major program milestone will be reflected in an updated version.*
