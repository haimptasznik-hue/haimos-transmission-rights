"""
dispatch_strategies.py — HaimOS BESS Dispatch Strategy Registry
================================================================
Named, toggleable strategy presets for the BESS dispatch engine.

Each strategy is a fully-specified set of algorithm parameters that can be:
  1. Selected by a user on the dashboard to run a single scenario.
  2. Compared side-by-side across multiple strategies.
  3. Exported as a specification document for software providers who will
     implement the algorithm directly in the asset controller (EMS/BMS).

Usage
-----
  from nem.dispatch_strategies import STRATEGIES, get_strategy, strategy_overrides

  cfg_overrides = strategy_overrides("co_optimised_revenue_max")
  # → dict of kwargs to pass to dispatch_bess() / BESSConfig

Strategy Design Layers
----------------------
Top-level dispatch mode (how the BESS chooses its operating mode each interval):
  - co_optimised   : Pick the highest-value option from {discharge+FCAS, charge+FCAS, FCAS-only, idle}
  - fcas_only      : Never dispatch energy; capacity reserved entirely for FCAS
  - arb_only       : Energy arbitrage only; FCAS disabled

FCAS allocation strategy (how available FCAS MW is split across services):
  - contingency_first    : Fill highest-paying contingency service first, then spill to regulation
  - revenue_maximising   : Enumerate all co-stack combinations, pick globally optimal split
  - guaranteed_reg_min   : Reserve cfg["reg_min_frac"] of inverter capacity for regulation
                           before allocating remainder to contingency

These two axes combine to produce the named presets below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Strategy metadata dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DispatchStrategySpec:
    """
    Full specification of a named dispatch strategy.

    Attributes
    ----------
    id : str
        Machine-readable identifier — used in API query params and comparison keys.
    name : str
        Human-readable display name shown on the dashboard.
    description : str
        Plain-English description of what this strategy does and when to use it.
    category : str
        Grouping label: "energy_arb" | "fcas" | "co_optimised" | "conservative"
    enable_fcas : bool
        Whether the FCAS co-optimisation engine is active.
    allocation_strategy : str
        FCAS capacity allocation algorithm: "contingency_first" |
        "revenue_maximising" | "guaranteed_reg_min"
    force_mode : str | None
        If set, overrides the per-interval revenue comparison and forces the
        engine to always operate in this mode: "fcas_only" | "discharge" | None.
        None = full co-optimised revenue selection per interval.
    adaptive_thresholds : bool
        If True, charge/discharge thresholds are derived from adaptive percentile
        signals (forecast + backcast). If False, the seed values from BESSConfig
        are used as static thresholds (useful for simple benchmark comparisons).
    engine_overrides : dict
        Additional kwargs forwarded directly to dispatch_bess(). These allow
        fine-grained algorithm flags to be adjusted per strategy.
    provider_spec_notes : str
        Specification notes for software/hardware providers describing how to
        implement this strategy in the asset controller (EMS/BMS/SCADA).
    """
    id: str
    name: str
    description: str
    category: str
    enable_fcas: bool
    allocation_strategy: str
    force_mode: str | None
    adaptive_thresholds: bool
    engine_overrides: dict = field(default_factory=dict)
    provider_spec_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":                    self.id,
            "name":                  self.name,
            "description":           self.description,
            "category":              self.category,
            "enable_fcas":           self.enable_fcas,
            "allocation_strategy":   self.allocation_strategy,
            "force_mode":            self.force_mode,
            "adaptive_thresholds":   self.adaptive_thresholds,
            "engine_overrides":      self.engine_overrides,
            "provider_spec_notes":   self.provider_spec_notes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Strategy registry
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES: dict[str, DispatchStrategySpec] = {}

def _reg(spec: DispatchStrategySpec) -> None:
    STRATEGIES[spec.id] = spec


# ── 1. Co-Optimised — Revenue Maximising ─────────────────────────────────────
_reg(DispatchStrategySpec(
    id="co_optimised_revenue_max",
    name="Co-Optimised · Revenue Maximising",
    description=(
        "Each 5-min interval, the engine evaluates all candidate dispatch modes "
        "(discharge+FCAS, charge+FCAS, FCAS-only, idle) and selects the globally "
        "revenue-maximising option. FCAS capacity is allocated by exhaustive "
        "co-stack enumeration. Charge/discharge thresholds are derived dynamically "
        "from a rolling percentile of forecast + backcast prices — no fixed values. "
        "This is the primary production strategy."
    ),
    category="co_optimised",
    enable_fcas=True,
    allocation_strategy="revenue_maximising",
    force_mode=None,
    adaptive_thresholds=True,
    engine_overrides={},
    provider_spec_notes=(
        "EMS must implement: (1) 5-min interval co-optimisation loop evaluating "
        "energy arb + FCAS co-stack revenue; (2) dynamic price threshold derived "
        "from rolling P25/P75 percentile of last 288 dispatch intervals + MMS "
        "pre-dispatch forecast; (3) FCAS co-stack: enumerate all valid raise/lower "
        "service combinations, select maximum-revenue allocation subject to inverter "
        "MW budget, SOC limits, and ramp-rate constraints; (4) AGC regulation "
        "enablement block when regulation service is selected."
    ),
))

# ── 2. Co-Optimised — Contingency First ──────────────────────────────────────
_reg(DispatchStrategySpec(
    id="co_optimised_contingency_first",
    name="Co-Optimised · Contingency First",
    description=(
        "Same as Revenue Maximising but FCAS allocation prioritises contingency "
        "services (6s, 60s, 5min raise/lower) before regulation. Regulation is "
        "only enabled after contingency capacity is filled. "
        "Preferred when regulation enablement overhead is a concern."
    ),
    category="co_optimised",
    enable_fcas=True,
    allocation_strategy="contingency_first",
    force_mode=None,
    adaptive_thresholds=True,
    engine_overrides={},
    provider_spec_notes=(
        "EMS must implement: same co-optimisation loop as Revenue Maximising, "
        "but FCAS allocation is greedy: rank available contingency services by "
        "$/MW, fill highest first up to inverter MW limit, then offer residual "
        "capacity to regulation if headroom remains. Regulation AGC mode is only "
        "entered after all contingency offers are placed."
    ),
))

# ── 3. Co-Optimised — Guaranteed Regulation Minimum ─────────────────────────
_reg(DispatchStrategySpec(
    id="co_optimised_reg_guaranteed",
    name="Co-Optimised · Guaranteed Regulation Min",
    description=(
        "Co-optimised dispatch with a reserved minimum fraction of inverter "
        "capacity always offered to regulation FCAS. This ensures AGC participation "
        "in every eligible interval while still capturing contingency and arb value "
        "on remaining capacity. Suitable for assets with regulation obligations."
    ),
    category="co_optimised",
    enable_fcas=True,
    allocation_strategy="guaranteed_reg_min",
    force_mode=None,
    adaptive_thresholds=True,
    engine_overrides={"reg_min_frac": 0.30},
    provider_spec_notes=(
        "EMS must implement: reserve a fixed fraction (default 30%) of rated "
        "inverter MW for regulation raise + lower at all times when SOC is "
        "within bounds (10%–90%). Remaining 70% capacity is co-optimised for "
        "contingency and energy arb. Regulation offer must be maintained "
        "continuously during the dispatch interval — do not withdraw mid-interval."
    ),
))

# ── 4. FCAS-Only — No Energy Dispatch ────────────────────────────────────────
_reg(DispatchStrategySpec(
    id="fcas_only",
    name="FCAS Only · No Energy Dispatch",
    description=(
        "The BESS never dispatches energy to/from the grid for arbitrage. All "
        "inverter capacity is reserved exclusively for FCAS services (both raise "
        "and lower, all speed tiers). Charge and discharge are only triggered by "
        "FCAS activations. Best for assets with export constraints or where "
        "frequency services are the primary revenue target."
    ),
    category="fcas",
    enable_fcas=True,
    allocation_strategy="revenue_maximising",
    force_mode="fcas_only",
    adaptive_thresholds=False,
    engine_overrides={},
    provider_spec_notes=(
        "EMS must implement: disable active energy dispatch bids in the energy "
        "market. All MW capacity is offered to FCAS markets only. SOC management "
        "is passive — charge/discharge only occurs via FCAS activation responses. "
        "Implement SOC recovery logic: if SOC falls below 15% or above 85%, "
        "temporarily reduce FCAS offer size to allow passive rebalancing."
    ),
))

# ── 5. Energy Arbitrage Only — No FCAS ───────────────────────────────────────
_reg(DispatchStrategySpec(
    id="arb_only",
    name="Energy Arbitrage Only · No FCAS",
    description=(
        "Pure energy arbitrage: charge when prices are below the adaptive P25 "
        "threshold, discharge when prices exceed the adaptive P75 threshold. "
        "No FCAS co-stack. Adaptive thresholds are derived from rolling percentile "
        "of recent prices + pre-dispatch forecast. Useful as a baseline benchmark "
        "to quantify the incremental value of FCAS co-optimisation."
    ),
    category="energy_arb",
    enable_fcas=False,
    allocation_strategy="contingency_first",  # irrelevant — FCAS disabled
    force_mode=None,
    adaptive_thresholds=True,
    engine_overrides={},
    provider_spec_notes=(
        "EMS must implement: (1) rolling P25/P75 percentile price threshold "
        "derived from last 288 intervals + forecast; (2) charge when spot < P25 "
        "threshold and SOC < 90%; (3) discharge when spot > P75 threshold and "
        "SOC > 10%; (4) ramp rate limits per AEMO GPS requirements; (5) no FCAS "
        "offers in any market. This is the simplest implementation path."
    ),
))

# ── 6. Conservative — Discharge Peak Only ────────────────────────────────────
_reg(DispatchStrategySpec(
    id="conservative_peak_discharge",
    name="Conservative · Peak Discharge Only",
    description=(
        "Only discharge during price spikes above $300/MWh. Never charge from "
        "the grid (solar charge only). FCAS enabled with contingency-first "
        "allocation. Suitable for assets with limited cycling budget or warranty "
        "constraints. Acts as a conservative benchmark."
    ),
    category="conservative",
    enable_fcas=True,
    allocation_strategy="contingency_first",
    force_mode=None,
    adaptive_thresholds=False,
    engine_overrides={
        "charge_threshold": 0.0,    # grid charge disabled (solar only via solar_mw)
        "discharge_threshold": 300.0,
    },
    provider_spec_notes=(
        "EMS must implement: (1) discharge only when spot > $300/MWh and "
        "SOC > 10%; (2) grid charging disabled — charge from co-located solar "
        "only; (3) FCAS contingency offers at all times when SOC is in bounds; "
        "This minimises cycle count while capturing extreme peak events."
    ),
))


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_strategy(strategy_id: str) -> DispatchStrategySpec:
    """Return strategy spec or raise KeyError with helpful message."""
    if strategy_id not in STRATEGIES:
        valid = sorted(STRATEGIES.keys())
        raise KeyError(
            f"Unknown strategy '{strategy_id}'. "
            f"Valid strategies: {valid}"
        )
    return STRATEGIES[strategy_id]


def list_strategies() -> list[dict]:
    """Return all strategies as a list of dicts (for API serialisation)."""
    return [s.to_dict() for s in STRATEGIES.values()]


def strategy_overrides(strategy_id: str) -> dict:
    """
    Return the dict of kwargs needed to configure dispatch_bess() and
    BESSConfig for a given strategy.

    Merges engine_overrides on top of the top-level strategy flags so callers
    get a single flat dict to apply.
    """
    spec = get_strategy(strategy_id)
    overrides = {
        "enable_fcas":           spec.enable_fcas,
        "allocation_strategy":   spec.allocation_strategy,
        "force_dispatch_mode":   spec.force_mode,  # passed into engine cfg
        "adaptive_thresholds":   spec.adaptive_thresholds,
    }
    overrides.update(spec.engine_overrides)
    return overrides


DEFAULT_STRATEGY_ID = "co_optimised_revenue_max"
