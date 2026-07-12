"""
FCAS Co-Optimised BESS Dispatch Engine — Single Source of Truth
===============================================================

All 10 NEM FCAS markets (including Very Fast 1-sec, added Oct 2023).

This module contains the ONE dispatch engine used by both:
  • Backcast / 20-year forecast  (regenerate_unified_tables.py)
  • Live asset simulation         (bess_dispatch.py → run_bess_dispatch_for_app)

The dispatch logic is IDENTICAL regardless of data source.  Only the
price / generation DataFrame changes.

Architecture
------------
    ┌──────────────────────────────────────────────┐
    │  fcas_dispatch_engine.py   (THIS MODULE)     │
    │  ─ FCAS_V2_CONFIG, SOLAR_CONTROLLER_DEFAULTS │
    │  ─ FCAS_RAISE_SERVICES, FCAS_LOWER_SERVICES  │
    │  ─ _pick_fcas_services_costacked()           │
    │  ─ dispatch_bess()  ← core per-interval loop │
    └──────────────────┬───────────────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
    ┌─────────▼──────┐  ┌──────▼──────────┐
    │  Backcast       │  │  Live Asset      │
    │  20-year sim    │  │  (AEMO live)     │
    │  (historical    │  │                  │
    │   NEM data)     │  │  Same engine,    │
    │                 │  │  different data   │
    └─────────────────┘  └─────────────────┘

TIMEZONE CONVENTION:  All timestamps are NEM time (AEST = UTC+10).
MW NOMENCLATURE:      See regenerate_unified_tables.py docstring.
FCAS REVENUE UNITS:   AEMO FCAS RRP = $/MW/hr.  Revenue per interval = price × MW × dt_hr.
"""

import numpy as np
import pandas as pd
import logging
from typing import Optional, Dict, Any, Tuple

from aemo_forecast_signals import (
    build_historical_price_signals,
    load_event_flags_for_dispatch,
)

# ML decision engine integration (optional)
try:
    from models.bess.decision_engine import (
        BESSDecisionEngine,
        DecisionEngineConfig,
        DecisionSource,
        DecisionMode,
        BESSDecision,
    )
    HAS_ML_DECISION_ENGINE = True
except ImportError:
    HAS_ML_DECISION_ENGINE = False

_LOG = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# CONFIGURATION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

# ── Solar Controller Configuration Constants ─────────────────────────────
# Tuning parameters for the dynamic AEMO-forecast-aware solar controller.
# Fallback defaults used when no `solar_controller_config` dict is passed.
# Users can adjust these via the Streamlit sidebar ("Solar Controller
# Tuning" expander) to fine-tune how the controller reacts to market
# signals.  The same config works identically for both historical backcast
# (pre-computed unified tables) and live dispatch.
SOLAR_CONTROLLER_DEFAULTS = {
    # ── Signal generation (aemo_forecast_signals.py) ─────────────────
    "lookahead_intervals":          36,       # 3 hours forward (36 × 5 min)
    "lookback_intervals":           12,       # 1 hour backward for volatility
    "trend_flat_band_aud":          5.0,      # $/MWh — price changes within this band are "flat"
    "trend_normalisation_aud":      50.0,     # $/MWh — delta at which trend signal saturates ±1.0

    # ── Section A: Adaptive threshold computation ────────────────────
    "adaptive_discharge_percentile": 75,      # percentile of forward window → discharge base
    "adaptive_charge_percentile":    25,      # percentile of backward window → charge base
    "adaptive_backcast_intervals":   288,     # 24 hours (288 × 5 min) for charge percentile
    "discharge_floor_aud":           0.0,     # safety floor: never discharge below this UNLESS exceptions apply
    "neg_arb_lookahead_intervals":   36,      # 3 hours forward to check for negative-price arb opportunity
    "neg_arb_min_spread_aud":        50.0,    # min $ benefit to justify discharging at negative prices
    # Modulation on top of adaptive base
    "charge_thresh_fwd_ratio":      1.3,
    "charge_thresh_trend_trigger":  0.1,
    "charge_thresh_max_multiplier": 1.3,
    "charge_thresh_fwd_spread_frac": 0.15,
    "discharge_thresh_trend_trigger": -0.2,
    "discharge_thresh_multiplier":  0.9,

    # ── Section B: Solar allocation optimizer ────────────────────────
    "event_fcas_boost":             1.5,
    "neg_ahead_storage_premium":    1.2,
    "volatility_threshold_aud":     30.0,
    "volatility_max_bonus":         0.3,
    "volatility_normalisation_aud": 100.0,

    # ── Section D: Candidate ranking signal adjustments ──────────────
    "rank_trend_threshold":         0.1,
    "rank_rising_discharge_penalty": 3.0,
    "rank_rising_charge_bonus":     2.0,
    "rank_falling_discharge_bonus": 2.0,
    "rank_falling_charge_penalty":  1.0,
    "rank_neg_ahead_charge_bonus":  5.0,
    "rank_neg_ahead_idle_penalty":  2.0,
    "rank_event_fcas_bonus":        3.0,
    "rank_vol_fcas_bonus":          2.0,
    "rank_vol_idle_penalty":        1.0,

    # ── Section E: Curtailment & idle logic ──────────────────────────
    "curtail_proactive_spot_aud":   5.0,
    "curtail_proactive_soc_frac":   0.95,
    "idle_neg_ahead_soc_frac":      0.9,
    "curtail_battery_full_frac":    0.99,
    "curtail_solar_near_cap_frac":  0.95,
}


# ══════════════════════════════════════════════════════════════════════════
# NER CHAPTER 4 & 5 COMPLIANCE CONFIGURATION (>5MW REGISTERED GENERATORS)
# ══════════════════════════════════════════════════════════════════════════
#
# CAPACITY THRESHOLDS AND REGISTRATION CATEGORIES:
# ────────────────────────────────────────────────────────────────────────────
#
#   ┌────────────────┬─────────────────────┬─────────────────────────────────┐
#   │ Export Capacity│ Registration        │ Key Obligations                 │
#   ├────────────────┼─────────────────────┼─────────────────────────────────┤
#   │    ≤5 MW       │ EXEMPT              │ No AEMO registration required.  │
#   │                │                     │ DNSP connection only.           │
#   │                │                     │ No GPS, no dispatch compliance. │
#   ├────────────────┼─────────────────────┼─────────────────────────────────┤
#   │   5–30 MW      │ SEMI-SCHEDULED      │ AEMO registration required.     │
#   │                │ (NER Ch 4.9)        │ Semi-dispatch caps (advisory    │
#   │                │                     │ when unconstrained, binding     │
#   │                │                     │ when capped).                   │
#   │                │                     │ GPS compliance mandatory.       │
#   │                │                     │ SCADA/AGC interface.            │
#   │                │                     │ Causer-pays applies.            │
#   ├────────────────┼─────────────────────┼─────────────────────────────────┤
#   │    >30 MW      │ SCHEDULED           │ Full central dispatch.          │
#   │                │ (NER Ch 3.8)        │ BINDING dispatch instructions.  │
#   │                │                     │ Must bid into energy market.    │
#   │                │                     │ All GPS requirements.           │
#   │                │                     │ PSS may be required.            │
#   │                │                     │ Higher prudential requirements. │
#   └────────────────┴─────────────────────┴─────────────────────────────────┘
#
# Note: Thresholds are based on AC EXPORT capacity (inverter rating), not
#       DC nameplate capacity. For hybrid systems (solar+BESS), the combined
#       maximum export capacity determines the registration category.
#
# Chapter 4 (Registration):
#   - Semi-Scheduled Generator: Must follow AEMO dispatch instructions
#   - Scheduled Generator: Full central dispatch, 5-min bidding
#   - Market Participant obligations: settlement, prudentials, compliance
#
# Chapter 5 (Network Connection - GPS Requirements):
#   - S5.2.5.3: Frequency response (continuous uninterrupted operation 47-52Hz)
#   - S5.2.5.4: Voltage ride-through (must stay connected during faults)
#   - S5.2.5.5: Active power control (ramp rate limits, dispatch compliance)
#   - S5.2.5.11: Remote monitoring and control (SCADA, AGC interface)
#   - S5.2.5.14: Power system stabiliser (if required by AEMO)
# ══════════════════════════════════════════════════════════════════════════

CHAPTER_4_5_CONFIG = {
    # ══════════════════════════════════════════════════════════════════════
    # REGISTRATION THRESHOLDS
    # ══════════════════════════════════════════════════════════════════════
    # These thresholds determine which NER obligations apply to the system.
    # Based on AC export capacity (inverter MW), not DC nameplate.
    
    "semi_scheduled_threshold_mw": 5.0,
    # ^ Systems >5MW must register as Semi-Scheduled Generator (solar/wind)
    #   Reference: NER 2.2.1, 4.9.2
    #   Effect: Semi-dispatch caps, GPS compliance, SCADA interface
    
    "scheduled_threshold_mw": 30.0,
    # ^ Systems >30MW typically registered as Scheduled Generator
    #   Reference: NER 2.2.1, 3.8.1
    #   Effect: Full central dispatch, binding targets, must bid every 5 mins
    
    "market_participant_threshold_mw": 5.0,
    # ^ Threshold for mandatory market participant registration
    #   Reference: NER 2.2, 2.9
    #   Effect: Prudential requirements, settlement obligations, market fees
    
    # ══════════════════════════════════════════════════════════════════════
    # DISPATCH COMPLIANCE (S5.2.5.5 Active Power Control)
    # ══════════════════════════════════════════════════════════════════════
    # Semi-scheduled: Caps are advisory when unconstrained, binding when capped
    # Scheduled: All dispatch instructions are BINDING
    
    "dispatch_cap_enabled": True,
    # ^ When True, enforce AEMO dispatch instruction caps
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "dispatch_cap_tolerance_pct": 3.0,
    # ^ Allowed deviation from dispatch cap (%)
    #   Reference: NER 4.9.8
    #   Exceeding tolerance may trigger non-compliance investigation
    
    "dispatch_cap_response_time_sec": 60,
    # ^ Maximum time to reach new dispatch setpoint
    #   Reference: GPS S5.2.5.5
    #   Must ramp to new target within this window
    
    # ══════════════════════════════════════════════════════════════════════
    # RAMP RATE LIMITS (S5.2.5.5)
    # ══════════════════════════════════════════════════════════════════════
    # GPS specifies maximum ramp rates to maintain system stability.
    # Too-fast ramping can cause frequency deviations.
    
    "gps_ramp_up_mw_per_min": None,
    # ^ GPS-negotiated ramp-up limit (MW/min). None = use hardware limit.
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Set during connection agreement negotiation with NSP/AEMO
    
    "gps_ramp_down_mw_per_min": None,
    # ^ GPS-negotiated ramp-down limit (MW/min). None = use hardware limit.
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "ramp_rate_pct_per_min": 10.0,
    # ^ Default ramp rate as % of registered capacity per minute
    #   Typical GPS requirement: 5-15%/min depending on network location
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    # ══════════════════════════════════════════════════════════════════════
    # FREQUENCY RESPONSE (S5.2.5.3)
    # ══════════════════════════════════════════════════════════════════════
    # Must maintain continuous uninterrupted operation within frequency band.
    # Required for all registered generators (>5MW).
    
    "freq_deadband_hz": 0.15,
    # ^ ±0.15 Hz around 50 Hz = no response required (normal operation)
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "freq_droop_pct": 5.0,
    # ^ Droop setting: 5% = 100% response at ±2.5 Hz deviation
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Reference: GPS S5.2.5.3
    
    "freq_response_enabled": True,
    # ^ Enable primary frequency response (mandatory for >5MW)
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "under_freq_limit_hz": 47.0,
    # ^ Must stay connected above this frequency
    #   Reference: GPS S5.2.5.3 - continuous uninterrupted operation
    #   APPLIES TO: ALL registered generators
    
    "over_freq_limit_hz": 52.0,
    # ^ Must stay connected below this frequency
    #   Reference: GPS S5.2.5.3
    #   APPLIES TO: ALL registered generators
    
    # ══════════════════════════════════════════════════════════════════════
    # VOLTAGE RIDE-THROUGH (S5.2.5.4)
    # ══════════════════════════════════════════════════════════════════════
    # Must remain connected during voltage disturbances (faults, switching).
    # Disconnection during faults worsens system stability.
    
    "lvrt_enabled": True,
    # ^ Low Voltage Ride-Through: stay connected during voltage dips
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Reference: GPS S5.2.5.4
    
    "hvrt_enabled": True,
    # ^ High Voltage Ride-Through: stay connected during overvoltage
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "voltage_min_pu": 0.0,
    # ^ Stay connected down to 0% voltage for 0.43 seconds (zero voltage)
    #   Reference: GPS S5.2.5.4 Figure S5.2.5.4
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "voltage_max_pu": 1.3,
    # ^ Stay connected up to 130% voltage for specified duration
    #   Reference: GPS S5.2.5.4
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    # ══════════════════════════════════════════════════════════════════════
    # AEMO AGC/SCADA INTERFACE (S5.2.5.11)
    # ══════════════════════════════════════════════════════════════════════
    # Remote monitoring and control requirements for registered generators.
    
    "agc_enabled": True,
    # ^ Accept Automatic Generation Control setpoints for regulation FCAS
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Mandatory for regulation FCAS participation
    
    "scada_telemetry_interval_sec": 4,
    # ^ SCADA reporting interval to AEMO (seconds)
    #   Reference: GPS S5.2.5.11
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Must report: MW, MVAr, voltage, frequency, status
    
    "agc_response_time_sec": 4,
    # ^ Maximum time to respond to AGC setpoint change
    #   APPLIES TO: Generators providing regulation FCAS
    #   Slower response = lower causer-pays factor
    
    # ══════════════════════════════════════════════════════════════════════
    # RUNBACK/CURTAILMENT (Network Security)
    # ══════════════════════════════════════════════════════════════════════
    # AEMO/NSP can issue runback instructions during network constraints.
    
    "runback_enabled": True,
    # ^ Accept runback (reduce output) instructions
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Triggered by: thermal limits, voltage limits, system strength
    
    "runback_response_time_sec": 60,
    # ^ Maximum time to execute runback instruction
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    
    "constraint_compliance_enabled": True,
    # ^ Obey network constraint equations in dispatch
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Reference: NER 3.8.1, constraint formulation
    
    # ══════════════════════════════════════════════════════════════════════
    # CAUSER-PAYS AND METERING
    # ══════════════════════════════════════════════════════════════════════
    
    "causer_pays_enabled": True,
    # ^ Subject to regulation FCAS causer-pays charges
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   Based on 4-sec deviation from AGC target over 28-day period
    
    "metering_class": "NMI",
    # ^ Wholesale metering (NMI-based settlement)
    #   APPLIES TO: Semi-Scheduled (>5MW) and Scheduled (>30MW)
    #   vs retail metering for <5MW embedded generators
    
    "settlement_interval_min": 5,
    # ^ 5-minute settlement (post-2021 NER rule change)
    #   APPLIES TO: ALL market participants
    #   Previously 30-min settlement pre-Oct 2021
    
    # ══════════════════════════════════════════════════════════════════════
    # SEMI-SCHEDULED SPECIFIC
    # ══════════════════════════════════════════════════════════════════════
    
    "uigf_enabled": True,
    # ^ Unconstrained Intermittent Generation Forecast
    #   APPLIES TO: Semi-Scheduled only (5-30MW)
    #   AEMO uses UIGF to predict uncapped output
    
    "self_forecast_enabled": True,
    # ^ Use own forecast vs AEMO's forecast
    #   APPLIES TO: Semi-Scheduled only (5-30MW)
    #   Better forecasting = better dispatch outcomes
    
    "semi_dispatch_interval_min": 5,
    # ^ Semi-dispatch instruction frequency
    #   APPLIES TO: Semi-Scheduled only (5-30MW)
    #   Caps issued every 5 minutes when binding
}


# Helper function to check if system requires Chapter 4/5 compliance
def requires_chapter_4_5_compliance(capacity_mw: float, config: dict = None) -> dict:
    """
    Determine registration and compliance requirements based on system size.
    
    Args:
        capacity_mw: System export capacity (AC) in MW
        config: Optional override for CHAPTER_4_5_CONFIG
    
    Returns:
        dict with registration category and applicable requirements
    """
    cfg = config or CHAPTER_4_5_CONFIG
    
    result = {
        "capacity_mw": capacity_mw,
        "requires_registration": capacity_mw > cfg["market_participant_threshold_mw"],
        "registration_category": "exempt",
        "gps_required": False,
        "dispatch_compliance": False,
        "agc_interface": False,
        "causer_pays": False,
        "applicable_rules": [],
    }
    
    if capacity_mw <= cfg["market_participant_threshold_mw"]:
        result["registration_category"] = "exempt"
        result["applicable_rules"].append("Small generator exemption (<5MW)")
    elif capacity_mw <= cfg["scheduled_threshold_mw"]:
        result["registration_category"] = "semi-scheduled"
        result["gps_required"] = True
        result["dispatch_compliance"] = True
        result["agc_interface"] = cfg["agc_enabled"]
        result["causer_pays"] = cfg["causer_pays_enabled"]
        result["applicable_rules"].extend([
            "NER Chapter 4 - Semi-Scheduled Generator registration",
            "NER Chapter 5 - Generator Performance Standards (GPS)",
            "S5.2.5.3 - Frequency response requirements",
            "S5.2.5.4 - Voltage ride-through requirements", 
            "S5.2.5.5 - Active power control / dispatch compliance",
            "S5.2.5.11 - Remote monitoring and control (SCADA/AGC)",
            "AEMO semi-dispatch instructions",
            "Causer-pays regulation charges",
        ])
    else:
        result["registration_category"] = "scheduled"
        result["gps_required"] = True
        result["dispatch_compliance"] = True
        result["agc_interface"] = True
        result["causer_pays"] = True
        result["applicable_rules"].extend([
            "NER Chapter 4 - Scheduled Generator registration",
            "NER Chapter 5 - Generator Performance Standards (GPS)",
            "Full central dispatch (5-min bidding)",
            "S5.2.5.3 - Frequency response requirements",
            "S5.2.5.4 - Voltage ride-through requirements",
            "S5.2.5.5 - Active power control / dispatch compliance", 
            "S5.2.5.11 - Remote monitoring and control (SCADA/AGC)",
            "AEMO dispatch instructions (binding)",
            "Causer-pays regulation charges",
            "Market prudential requirements",
        ])
    
    return result


# ── FCAS v2 Configuration Constants ─────────────────────────────────────
FCAS_V2_CONFIG = {
    # SOC guard bands for regulation services (fraction of energy_mwh)
    "reg_soc_min": 0.10,
    "reg_soc_max": 0.90,
    # SOC bounds for dispatch
    "soc_min_frac": 0.05,
    "soc_max_frac": 0.95,
    # Regulation throughput parameters
    "reg_mwh_per_mw_5min": 0.003,
    "deg_cost_aud_per_mwh": 5.0,
    "target_soc_frac": 0.50,
    # Charging efficiency
    "roundtrip_eff": 0.90,
    # ── Ramp-rate & mode-switch constraints ──────────────────────────
    "ramp_rate_mw_per_sec": 0.00825,   # ≈ 10%/min of 4.95 MW — HARDWARE_MODULE_TODO
    "mode_switch_penalty_intervals": 1,
    "mode_switch_fcas_derate": 0.25,
    # ── SOC taper zone for FCAS enablement ───────────────────────────
    "soc_taper_width": 0.15,
    # ── Minimum enablement threshold ─────────────────────────────────
    "min_enablement_frac": 0.05,
    # ── Layer 1: Contingency vs Regulation allocation strategy ───────
    #   "contingency_first"   – contingency fills headroom first, reg gets leftovers (default)
    #   "revenue_maximising"  – per-interval comparison of cont-first vs reg-first, pick best
    #   "guaranteed_reg_min"  – reserve reg_min_frac of headroom for reg before cont
    "allocation_strategy": "contingency_first",
    "reg_min_frac": 0.30,   # only used when allocation_strategy == "guaranteed_reg_min"
    # ── Layer 2: Raise vs Lower direction priority ───────────────────
    #   "proportional"   – both directions scale equally (default)
    #   "revenue_weighted" – higher-revenue direction keeps proportionally more
    #   "prefer_raise"   – raise fills first, lower gets remainder
    #   "prefer_lower"   – lower fills first, raise gets remainder
    "direction_priority": "revenue_weighted",
    # Per-service availability factors
    "availability_factor": {
        "REG_RAISE":  0.70,
        "REG_LOWER":  0.70,
        "RAISE_1SEC": 0.92,
        "LOWER_1SEC": 0.92,
        "RAISE_6SEC": 0.90,
        "LOWER_6SEC": 0.90,
        "RAISE_60SEC": 0.88,
        "LOWER_60SEC": 0.88,
        "RAISE_5MIN": 0.85,
        "LOWER_5MIN": 0.85,
    },
}

# FCAS service definitions by direction
FCAS_RAISE_SERVICES = [
    ("fcas_reg_raise_aud_per_mw",   "REG_RAISE",   True),
    ("fcas_raise_1sec_aud_per_mw",  "RAISE_1SEC",  False),
    ("fcas_raise_6sec_aud_per_mw",  "RAISE_6SEC",  False),
    ("fcas_raise_60sec_aud_per_mw", "RAISE_60SEC", False),
    ("fcas_raise_5min_aud_per_mw",  "RAISE_5MIN",  False),
]
FCAS_LOWER_SERVICES = [
    ("fcas_reg_lower_aud_per_mw",   "REG_LOWER",   True),
    ("fcas_lower_1sec_aud_per_mw",  "LOWER_1SEC",  False),
    ("fcas_lower_6sec_aud_per_mw",  "LOWER_6SEC",  False),
    ("fcas_lower_60sec_aud_per_mw", "LOWER_60SEC", False),
    ("fcas_lower_5min_aud_per_mw",  "LOWER_5MIN",  False),
]


# ══════════════════════════════════════════════════════════════════════════
# FCAS SERVICE SELECTION — NEM Co-Stacking Model
# ══════════════════════════════════════════════════════════════════════════
#
# NEM FCAS co-stacking rules (per AEMO MASS / Dispatch Procedure):
#
#   1. CONTINGENCY services in the SAME direction CASCADE:
#      The same physical MW can be enabled for 1SEC + 6SEC + 60SEC + 5MIN
#      simultaneously, because only ONE contingency event type fires at a
#      time.  Revenue = sum of all enabled services' prices × MW.
#
#   2. REGULATION is ADDITIVE to contingency:
#      REG capacity must be reserved ON TOP of contingency capacity,
#      because regulation is a continuous AGC-dispatched service that
#      runs concurrently with contingency standby.
#
#   3. Total capacity constraint:
#      reg_mw + cont_mw ≤ headroom_mw
#      (where cont_mw = max MW across all enabled contingency services,
#       which are the SAME MW since they cascade)
#
# The function below evaluates all services, enables every profitable one,
# and returns per-service breakdowns + aggregates.
# ══════════════════════════════════════════════════════════════════════════

_SERVICE_DURATION_HR = {
    "RAISE_1SEC":  1.0 / 3600.0,
    "LOWER_1SEC":  1.0 / 3600.0,
    "RAISE_6SEC":  6.0 / 3600.0,
    "LOWER_6SEC":  6.0 / 3600.0,
    "RAISE_60SEC": 60.0 / 3600.0,
    "LOWER_60SEC": 60.0 / 3600.0,
    "RAISE_5MIN":  5.0 / 60.0,
    "LOWER_5MIN":  5.0 / 60.0,
    "REG_RAISE":   5.0 / 60.0,
    "REG_LOWER":   5.0 / 60.0,
}


def _pick_fcas_services_costacked(row, services, headroom_mw, soc_frac,
                                   energy_mwh, cfg, power_mw_rated=None,
                                   activation_map=None):
    """
    NEM co-stacking FCAS selection for one direction (raise OR lower).

    Contingency services share the same physical MW (cascading).
    Regulation uses additional dedicated capacity on top.

    Returns
    -------
    result : dict
        {
          "total_mw":         float,   # max(cont_mw, 0) + reg_mw
          "total_revenue":    float,   # sum of all per-service revenues
          "cont_mw":          float,   # contingency MW (shared / cascading)
          "reg_mw":           float,   # regulation MW (additive)
          "cont_revenue":     float,   # sum of contingency revenues
          "reg_revenue":      float,   # regulation net revenue
          "services":  dict[str, dict], # per-service breakdown:
              { label: {"enabled_mw", "price", "revenue", "is_reg"} }
          "best_label":       str,      # highest-revenue service label
        }
    """
    dt_hr = 5.0 / 60.0
    avail = cfg.get("availability_factor", {})
    pmax = power_mw_rated or headroom_mw
    min_en = cfg.get("min_enablement_frac", 0.05) * pmax
    taper_w = cfg.get("soc_taper_width", 0.15)
    soc_min_f = cfg["soc_min_frac"]
    soc_max_f = cfg["soc_max_frac"]

    # ── Evaluate each service independently ──────────────────────────
    # We compute the maximum feasible MW and revenue for each service,
    # BEFORE applying the shared capacity budget.
    feasible = {}  # label → {q_mw, price, net_rev, is_reg, act_frac}

    for col, label, is_reg in services:
        price = row.get(col, 0.0)
        if price <= 0 or headroom_mw <= 0:
            continue

        q_mw = headroom_mw

        # Regulation guard: SOC within [10%, 90%]
        if is_reg:
            if soc_frac < cfg["reg_soc_min"] or soc_frac > cfg["reg_soc_max"]:
                continue

        # Per-service availability derate on enablement
        af = avail.get(label, 1.0)
        q_mw *= af

        # SOC taper: reduce enablement near SOC boundaries
        if "RAISE" in label or label == "REG_RAISE":
            soc_above_min = soc_frac - soc_min_f
            if soc_above_min <= 0:
                continue
            if soc_above_min < taper_w:
                q_mw *= (soc_above_min / taper_w)
        else:
            soc_below_max = soc_max_f - soc_frac
            if soc_below_max <= 0:
                continue
            if soc_below_max < taper_w:
                q_mw *= (soc_below_max / taper_w)

        # Energy feasibility
        svc_dur_hr = _SERVICE_DURATION_HR.get(label, dt_hr)
        if "RAISE" in label or label == "REG_RAISE":
            e_avail = (soc_frac - soc_min_f) * energy_mwh
            max_q_energy = e_avail / svc_dur_hr if svc_dur_hr > 0 else 0.0
            q_mw = min(q_mw, max(0.0, max_q_energy))
        else:
            e_room = (soc_max_f - soc_frac) * energy_mwh
            max_q_energy = e_room / svc_dur_hr if svc_dur_hr > 0 else 0.0
            q_mw = min(q_mw, max(0.0, max_q_energy))

        # Minimum enablement threshold
        if q_mw < min_en:
            continue

        # Revenue: NEM FCAS enablement = price × MW (paid for being enabled)
        # Activation fraction only affects throughput/degradation cost.
        act_frac = 1.0
        if activation_map is not None:
            act_frac = activation_map.get(label, 1.0)
        gross_rev = price * q_mw * dt_hr  # enablement revenue (price=$/MW/hr × MW × hr)

        # Regulation throughput cost deduction (activation drives actual dispatch)
        if is_reg:
            e_reg = q_mw * cfg["reg_mwh_per_mw_5min"] * act_frac
            cost_reg = e_reg * cfg["deg_cost_aud_per_mwh"]
            net_rev = gross_rev - cost_reg
        else:
            net_rev = gross_rev

        if net_rev > 0:
            feasible[label] = {
                "q_mw": q_mw, "price": price, "net_rev": net_rev,
                "is_reg": is_reg, "act_frac": act_frac,
            }

    # ── Apply NEM co-stacking rules ──────────────────────────────────
    # Step 1: Find best contingency MW — all contingency services share
    #         the SAME capacity (they cascade), so cont_mw = max of all
    #         individual contingency q_mw values.
    cont_services = {k: v for k, v in feasible.items() if not v["is_reg"]}
    reg_services = {k: v for k, v in feasible.items() if v["is_reg"]}

    allocation_strategy = cfg.get("allocation_strategy", "contingency_first")
    reg_min_frac = cfg.get("reg_min_frac", 0.30)

    def _allocate_cont_first(headroom):
        """Contingency fills headroom first, regulation gets leftovers."""
        c_mw = max((v["q_mw"] for v in cont_services.values()), default=0.0)
        r_headroom = max(0.0, headroom - c_mw)
        return c_mw, r_headroom

    def _allocate_reg_first(headroom):
        """Regulation fills headroom first, contingency gets leftovers."""
        # Reg gets full headroom
        return 0.0, headroom  # cont_mw=0 placeholder, reg gets all

    def _build_result(c_mw, r_headroom):
        """Given cont_mw and reg headroom, build the full result dict."""
        # Regulation allocation
        r_mw = 0.0
        r_label = None
        r_revenue = 0.0
        for lbl, info in reg_services.items():
            rm = min(info["q_mw"], r_headroom)
            if rm < min_en:
                continue
            af = info["act_frac"]
            gross = info["price"] * rm * dt_hr
            e_reg = rm * cfg["reg_mwh_per_mw_5min"] * af
            cost_reg = e_reg * cfg["deg_cost_aud_per_mwh"]
            net = gross - cost_reg
            if net > 0 and net > r_revenue:
                r_mw = rm
                r_label = lbl
                r_revenue = net

        # Per-contingency-service revenue at shared c_mw
        svc = {}
        c_total_rev = 0.0
        for lbl, info in cont_services.items():
            svc_mw = c_mw
            rev = info["price"] * svc_mw * dt_hr
            svc[lbl] = {
                "enabled_mw": svc_mw,
                "price": info["price"],
                "revenue": rev,
                "is_reg": False,
            }
            c_total_rev += rev

        if r_label and r_mw > 0:
            svc[r_label] = {
                "enabled_mw": r_mw,
                "price": reg_services[r_label]["price"],
                "revenue": r_revenue,
                "is_reg": True,
            }

        t_mw = c_mw + r_mw
        t_rev = c_total_rev + r_revenue

        best_lbl = "NONE"
        best_r = 0.0
        for lbl, info in svc.items():
            if info["revenue"] > best_r:
                best_r = info["revenue"]
                best_lbl = lbl

        return {
            "total_mw": t_mw,
            "total_revenue": t_rev,
            "cont_mw": c_mw,
            "reg_mw": r_mw,
            "cont_revenue": c_total_rev,
            "reg_revenue": r_revenue,
            "services": svc,
            "best_label": best_lbl,
        }

    if allocation_strategy == "revenue_maximising":
        # Strategy B: Compare cont-first vs reg-first, pick the one with
        # highest total revenue per interval.
        c_mw_cf, r_head_cf = _allocate_cont_first(headroom_mw)
        result_cf = _build_result(c_mw_cf, r_head_cf)

        # For reg-first: give reg full headroom, then cont gets remainder
        # Reg first means we tentatively compute reg at full headroom,
        # then cont_mw is limited to headroom - reg_mw
        result_rf_temp = _build_result(0.0, headroom_mw)
        # Now fit contingency into whatever headroom is left after reg
        c_mw_rf = max((v["q_mw"] for v in cont_services.values()), default=0.0)
        c_mw_rf = min(c_mw_rf, max(0.0, headroom_mw - result_rf_temp["reg_mw"]))
        result_rf = _build_result(c_mw_rf, max(0.0, headroom_mw - c_mw_rf))

        if result_rf["total_revenue"] > result_cf["total_revenue"]:
            return result_rf
        else:
            return result_cf

    elif allocation_strategy == "guaranteed_reg_min":
        # Strategy C: Reserve reg_min_frac of headroom for reg, then
        # contingency can use the rest.
        reg_reserved = headroom_mw * reg_min_frac
        cont_budget = headroom_mw - reg_reserved

        c_mw = max((v["q_mw"] for v in cont_services.values()), default=0.0)
        c_mw = min(c_mw, cont_budget)  # cap contingency to its budget

        # Reg gets everything contingency didn't use
        r_headroom = max(0.0, headroom_mw - c_mw)
        return _build_result(c_mw, r_headroom)

    else:
        # Strategy A (default): contingency_first — cont fills first, reg gets leftovers
        c_mw, r_headroom = _allocate_cont_first(headroom_mw)
        return _build_result(c_mw, r_headroom)


def _pick_best_fcas_service(row, services, headroom_mw, soc_frac, energy_mwh, cfg,
                            power_mw_rated=None, activation_map=None):
    """
    BACKWARD-COMPATIBLE WRAPPER — returns legacy (enabled_mw, price, label, revenue) tuple.

    Internally delegates to _pick_fcas_services_costacked() and extracts
    the aggregate result in the old format.
    """
    r = _pick_fcas_services_costacked(
        row, services, headroom_mw, soc_frac, energy_mwh, cfg,
        power_mw_rated=power_mw_rated, activation_map=activation_map,
    )
    label = r["best_label"]
    price = r["services"][label]["price"] if label in r["services"] else 0.0
    return (r["total_mw"], price, label, r["total_revenue"])


def _scale_stacked_result(result, scale_factor, cfg, activation_map=None):
    """
    Scale a co-stacked result dict proportionally when a shared capacity
    budget constraint binds.

    All MW values are multiplied by scale_factor, and revenues are
    recomputed from the scaled MW to ensure consistency.
    """
    if scale_factor >= 1.0 or not result["services"]:
        return result

    dt_hr = 5.0 / 60.0
    new_services = {}
    new_cont_rev = 0.0
    new_reg_rev = 0.0

    for label, info in result["services"].items():
        new_mw = info["enabled_mw"] * scale_factor
        act_frac = 1.0
        if activation_map is not None:
            act_frac = activation_map.get(label, 1.0)
        gross = info["price"] * new_mw * dt_hr  # enablement revenue ($/MW/hr × MW × hr)
        if info["is_reg"]:
            e_reg = new_mw * cfg["reg_mwh_per_mw_5min"] * act_frac
            cost_reg = e_reg * cfg["deg_cost_aud_per_mwh"]
            rev = gross - cost_reg
            new_reg_rev += rev
        else:
            rev = gross
            new_cont_rev += rev
        new_services[label] = {
            "enabled_mw": new_mw,
            "price": info["price"],
            "revenue": rev,
            "is_reg": info["is_reg"],
        }

    new_cont_mw = result["cont_mw"] * scale_factor
    new_reg_mw = result["reg_mw"] * scale_factor
    total_rev = new_cont_rev + new_reg_rev

    # Recompute best_label
    best_label = "NONE"
    best_rev = 0.0
    for label, info in new_services.items():
        if info["revenue"] > best_rev:
            best_rev = info["revenue"]
            best_label = label

    return {
        "total_mw": new_cont_mw + new_reg_mw,
        "total_revenue": total_rev,
        "cont_mw": new_cont_mw,
        "reg_mw": new_reg_mw,
        "cont_revenue": new_cont_rev,
        "reg_revenue": new_reg_rev,
        "services": new_services,
        "best_label": best_label,
    }


def _apply_direction_priority(rr, rl, budget_mw, cfg, activation_map=None):
    """
    Apply Layer 2 direction priority when raise + lower total_mw exceeds
    the shared inverter budget.

    Parameters
    ----------
    rr, rl : dict
        Raise and lower stacked results from _pick_fcas_services_costacked.
    budget_mw : float
        Maximum combined MW for both directions.
    cfg : dict
        FCAS config (must contain 'direction_priority').
    activation_map : dict or None
        Per-service activation fractions.

    Returns
    -------
    rr_out, rl_out : dict
        Scaled raise and lower results.
    """
    qr = rr["total_mw"]
    ql = rl["total_mw"]

    if qr + ql <= budget_mw or qr + ql <= 0:
        return rr, rl  # No constraint binding

    direction = cfg.get("direction_priority", "proportional")

    if direction == "revenue_weighted":
        # Higher-revenue direction gets proportionally more of the budget
        rev_r = rr["total_revenue"]
        rev_l = rl["total_revenue"]
        total_rev = rev_r + rev_l
        if total_rev > 0:
            share_r = rev_r / total_rev
            share_l = rev_l / total_rev
        else:
            share_r = 0.5
            share_l = 0.5
        # Allocate budget by revenue weight, but cap each at its requested MW
        alloc_r = min(qr, budget_mw * share_r)
        alloc_l = min(ql, budget_mw * share_l)
        # Give any slack back to the other direction
        if alloc_r < budget_mw * share_r:
            alloc_l = min(ql, budget_mw - alloc_r)
        elif alloc_l < budget_mw * share_l:
            alloc_r = min(qr, budget_mw - alloc_l)
        # Compute scale factors
        sf_r = alloc_r / qr if qr > 0 else 0.0
        sf_l = alloc_l / ql if ql > 0 else 0.0

    elif direction == "prefer_raise":
        # Raise fills first, lower gets remainder
        alloc_r = min(qr, budget_mw)
        alloc_l = min(ql, max(0.0, budget_mw - alloc_r))
        sf_r = alloc_r / qr if qr > 0 else 0.0
        sf_l = alloc_l / ql if ql > 0 else 0.0

    elif direction == "prefer_lower":
        # Lower fills first, raise gets remainder
        alloc_l = min(ql, budget_mw)
        alloc_r = min(qr, max(0.0, budget_mw - alloc_l))
        sf_r = alloc_r / qr if qr > 0 else 0.0
        sf_l = alloc_l / ql if ql > 0 else 0.0

    else:
        # Default: proportional (original behaviour)
        sc_f = budget_mw / (qr + ql)
        sf_r = sc_f
        sf_l = sc_f

    rr_out = _scale_stacked_result(rr, sf_r, cfg, activation_map)
    rl_out = _scale_stacked_result(rl, sf_l, cfg, activation_map)
    return rr_out, rl_out


# ══════════════════════════════════════════════════════════════════════════
# ML OBSERVATION BUILDER
# ══════════════════════════════════════════════════════════════════════════

def _build_ml_observation(
    soc_frac: float,
    spot: float,
    trend: float,
    volatility: float,
    fwd_max: float,
    fwd_min: float,
    neg_ahead: bool,
    event_flag: bool,
    bess_rated_mw: float,
) -> np.ndarray:
    """
    Build a 51-dimensional observation vector for the ML model.
    
    Structure: [6 base] + [24 forecast] + [6 competitor] + [15 market]
    
    This is a simplified version that synthesizes missing features
    from available dispatch signals.
    """
    # Base features (6)
    base = np.array([
        soc_frac,                            # SOC fraction
        min(1.0, spot / 300.0),              # Normalized price
        min(1.0, volatility / 100.0),        # Normalized volatility
        0.0,                                 # Cumulative revenue (not tracked here)
        np.sin(2 * np.pi * 0.5),             # Time encoding (placeholder)
        np.cos(2 * np.pi * 0.5),             # Time encoding (placeholder)
    ])
    
    # Forecast features (24) - 8 timesteps × 3 features (price, raise, lower)
    # Synthesize from available signals
    forecast = np.zeros(24)
    for t in range(8):
        decay = 0.9 ** t
        forecast[t * 3] = min(1.0, (spot + trend * t * 10) / 300.0)  # Future price est
        forecast[t * 3 + 1] = 0.5  # FCAS raise placeholder
        forecast[t * 3 + 2] = 0.5  # FCAS lower placeholder
    
    # Competitor features (6) - synthetic
    competitor = np.array([
        0.2,   # Market share
        0.3,   # Capacity ratio
        0.5,   # Avg price percentile
        0.2,   # Std price
        0.0,   # Aggressive bidders
        0.5,   # Market concentration
    ])
    
    # Market context features (15)
    market = np.array([
        min(1.0, spot / 200.0),              # demand_norm
        trend,                                # demand_delta (using price trend)
        0.5,                                  # demand_gen_ratio
        0.3,                                  # reg_raise_utilization
        0.3,                                  # reg_lower_utilization
        0.2,                                  # contingency_raise_utilization
        0.2,                                  # contingency_lower_utilization
        0.1,                                  # supply_surplus_norm
        0.5,                                  # surplus_percentile
        min(1.0, volatility / 50.0),         # price_volatility
        0.3 if event_flag else 0.1,          # fcas_stress
        0.5,                                  # market_regime
        0.0,                                  # net_import_norm
        0.5,                                  # import_dependence
        min(1.0, volatility / 100.0),        # flow_volatility
    ])
    
    obs = np.concatenate([base, forecast, competitor, market])
    return obs.astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════
# CORE DISPATCH ENGINE
# ══════════════════════════════════════════════════════════════════════════

def dispatch_bess(
    df: pd.DataFrame,
    bess_rated_mw: float,
    energy_mwh: float,
    enable_fcas: bool = True,
    charge_threshold: float = 50.0,
    discharge_threshold: float = 100.0,
    fcas_config: Optional[dict] = None,
    region: Optional[str] = None,
    year: Optional[int] = None,
    activation_years=None,
    dc_coupled: bool = True,
    solar_controller_config: Optional[dict] = None,
    solar_col: Optional[str] = None,
    # ML decision engine parameters
    use_ml_decisions: bool = False,
    ml_model_path: Optional[str] = None,
    ml_confidence_threshold: float = 0.6,
    ml_hybrid_mode: bool = True,
    # NER Chapter 4/5 compliance parameters
    grid_connected: bool = True,
    export_capacity_mw: Optional[float] = None,
    chapter_4_5_config: Optional[dict] = None,
) -> dict:
    """
    Run the co-optimised BESS + FCAS dispatch engine over a DataFrame.

    This is the SINGLE SOURCE OF TRUTH dispatch logic used by both
    backcast (20-year forecasts) and live asset simulation.

    Args:
        df: DataFrame with columns:
            - spot_price_aud_per_mwh: NEM spot price
            - timestamp: datetime (for event flag loading)
            - (optional) FCAS price columns (fcas_*_aud_per_mw)
            - (optional) solar column (specified via solar_col)
        bess_rated_mw: BESS inverter nameplate power (MW).
        energy_mwh: BESS energy capacity (MWh).
        enable_fcas: Whether FCAS services are available.
        charge_threshold: Fallback charge threshold ($/MWh).
        discharge_threshold: Fallback discharge threshold ($/MWh).
        fcas_config: Optional overrides for FCAS_V2_CONFIG.
        region: NEM region (for activation data loading).
        year: Calendar year (for activation data loading).
        activation_years: Years for multi-year activation aggregation.
        dc_coupled: True = solar+BESS share one inverter.
        solar_controller_config: Optional overrides for SOLAR_CONTROLLER_DEFAULTS.
        solar_col: Name of solar MW column in df (auto-detected if None).
        
        NER Chapter 4/5 Compliance (for grid-connected >5MW systems):
        grid_connected: Whether system is grid-connected (enables compliance checks).
        export_capacity_mw: AC export capacity for compliance (defaults to bess_rated_mw).
        chapter_4_5_config: Optional overrides for CHAPTER_4_5_CONFIG.
        
        When grid_connected=True and export_capacity_mw > 5MW:
        - GPS ramp rate limits are enforced (NER S5.2.5.5)
        - Dispatch cap compliance (3% tolerance) is applied
        - AGC/SCADA response timing is modelled
        - Causer-pays factors are applied to regulation services

    Returns:
        dict with keys:
            charge_mw, discharge_mw, soc_mwh, soc_pct,
            charge_from_solar_mw, charge_from_grid_mw, solar_export_mw,
            solar_actual_production_mw,
            solar_available_mw, solar_curtailed_mw,
            solar_curtail_setpoint_mw, solar_curtail_reason,
            gcp_active_power_mw, gcp_export_headroom_mw,
            fcas_reserved_mw, fcas_raise_mw, fcas_lower_mw,
            fcas_raise_service, fcas_lower_service,
            fcas_raise_revenue_aud, fcas_lower_revenue_aud,
            fcas_reg_revenue_aud, fcas_cont_revenue_aud,
            arb_available_mw, arb_revenue_aud, fcas_revenue_aud,
            opp_cost_aud, total_revenue_aud,
            degradation_cost_aud,
            trap_enablement_min_mw, trap_enablement_max_mw,
            trap_low_breakpoint_mw, trap_high_breakpoint_mw,
            ramp_rate_raise_mw_per_min, ramp_rate_lower_mw_per_min,
            reg_soc_drift_mwh, causer_pays_factor,
            # Per-service co-stacked (20 keys: 10 MW + 10 revenue)
            fcas_reg_raise_enabled_mw, fcas_reg_raise_revenue_aud,
            fcas_reg_lower_enabled_mw, fcas_reg_lower_revenue_aud,
            fcas_raise_1sec_enabled_mw, fcas_raise_1sec_revenue_aud,
            fcas_lower_1sec_enabled_mw, fcas_lower_1sec_revenue_aud,
            fcas_raise_6sec_enabled_mw, fcas_raise_6sec_revenue_aud,
            fcas_lower_6sec_enabled_mw, fcas_lower_6sec_revenue_aud,
            fcas_raise_60sec_enabled_mw, fcas_raise_60sec_revenue_aud,
            fcas_lower_60sec_enabled_mw, fcas_lower_60sec_revenue_aud,
            fcas_raise_5min_enabled_mw, fcas_raise_5min_revenue_aud,
            fcas_lower_5min_enabled_mw, fcas_lower_5min_revenue_aud,
            # Aggregate contingency totals
            fcas_contingency_raise_total_mw,
            fcas_contingency_lower_total_mw,
            # Phase 6: Inverter Signal Trace (43 keys)
            # Market signal inputs (11)
            sig_spot_price, sig_price_trend, sig_volatility,
            sig_fwd_max_price, sig_fwd_min_price, sig_fwd_mean_price,
            sig_stored_energy_value, sig_neg_price_ahead, sig_event_flag,
            sig_adapt_discharge_thresh, sig_adapt_charge_thresh,
            # Inverter commands (5)
            inv_active_power_mw, inv_reactive_power_mvar, inv_mode,
            inv_power_limit_mw, inv_solar_curtail_mw,
            # AEMO FCAS bid/offer signals (8)
            aemo_raise_enablement_mw, aemo_lower_enablement_mw,
            aemo_reg_raise_bid_mw, aemo_reg_lower_bid_mw,
            aemo_cont_raise_bid_mw, aemo_cont_lower_bid_mw,
            aemo_energy_bid_mw, aemo_agc_setpoint_mw,
            # DNSP export constraint signals (3)
            dnsp_export_limit_mw, dnsp_export_actual_mw,
            dnsp_curtail_active,
            # Decision reasoning trace (16)
            decision_mode, decision_revenue_discharge,
            decision_revenue_charge, decision_revenue_fcas_only,
            decision_revenue_idle, decision_margin,
            decision_soc_before, decision_soc_after,
            decision_alloc_strategy, decision_dir_priority,
            decision_headroom_raise_mw, decision_headroom_lower_mw,
            decision_fcas_raise_rev, decision_fcas_lower_rev,
            decision_arb_rev, decision_opp_cost
        Each value is a list of length len(df).
    """
    cfg = {**FCAS_V2_CONFIG, **(fcas_config or {})}
    sc = {**SOLAR_CONTROLLER_DEFAULTS, **(solar_controller_config or {})}
    _LOG.info(f"dispatch_bess: {bess_rated_mw}MW/{energy_mwh}MWh, FCAS={enable_fcas}")
    
    # ══════════════════════════════════════════════════════════════════════
    # NER Chapter 4/5 COMPLIANCE ENFORCEMENT
    # ══════════════════════════════════════════════════════════════════════
    # For grid-connected systems >5MW, automatically apply:
    # - GPS ramp rate constraints (NER S5.2.5.5)
    # - Dispatch cap compliance (3% tolerance band)
    # - AGC/SCADA response timing
    # - Causer-pays factors
    # ──────────────────────────────────────────────────────────────────────
    ch45_cfg = {**CHAPTER_4_5_CONFIG, **(chapter_4_5_config or {})}
    compliance_capacity_mw = export_capacity_mw if export_capacity_mw is not None else bess_rated_mw
    compliance_requirements = requires_chapter_4_5_compliance(compliance_capacity_mw, ch45_cfg)
    
    # Track compliance state for output
    is_registered_generator = compliance_requirements["requires_registration"]
    registration_category = compliance_requirements["registration_category"]
    gps_ramp_enforced = False
    dispatch_cap_enforced = False
    
    if grid_connected and is_registered_generator:
        _LOG.info(f"  📋 NER Chapter 4/5 compliance active: {registration_category} ({compliance_capacity_mw}MW)")
        
        # ── Override ramp rate with GPS requirement ──────────────────
        # NER S5.2.5.5 - Active power control
        # GPS requires generators to ramp at controlled rates (typically 10%/min)
        gps_ramp_pct_per_min = ch45_cfg.get("ramp_rate_pct_per_min", 10.0)
        gps_ramp_mw_per_min = (gps_ramp_pct_per_min / 100.0) * compliance_capacity_mw
        gps_ramp_mw_per_sec = gps_ramp_mw_per_min / 60.0
        
        # Only apply GPS ramp if it's MORE restrictive than hardware limit
        hardware_ramp_mw_per_sec = cfg.get("ramp_rate_mw_per_sec", 1.0)
        if gps_ramp_mw_per_sec < hardware_ramp_mw_per_sec:
            cfg["ramp_rate_mw_per_sec"] = gps_ramp_mw_per_sec
            gps_ramp_enforced = True
            _LOG.info(f"    ✅ GPS ramp rate enforced: {gps_ramp_pct_per_min}%/min = {gps_ramp_mw_per_min:.2f} MW/min")
        else:
            _LOG.info(f"    ℹ️ GPS ramp rate ({gps_ramp_mw_per_min:.2f} MW/min) not binding (hardware: {hardware_ramp_mw_per_sec*60:.2f} MW/min)")
        
        # ── Apply causer-pays factor to regulation FCAS ──────────────
        # NER clause 3.15.6A - Regulation FCAS cost allocation
        if ch45_cfg.get("causer_pays_enabled", True) and compliance_requirements["causer_pays"]:
            causer_pays_factor = ch45_cfg.get("causer_pays_factor", 1.0)
            # Reduce effective revenue from regulation by causer-pays factor
            # (modelled as reduced price - actual causer-pays is more complex)
            cfg["causer_pays_applied"] = True
            cfg["causer_pays_factor"] = causer_pays_factor
            _LOG.info(f"    ✅ Causer-pays factor applied: {causer_pays_factor:.2f}")
        
        # ── Dispatch cap compliance (applied in loop) ────────────────
        if ch45_cfg.get("dispatch_cap_enabled", True):
            dispatch_cap_enforced = True
            dispatch_cap_tolerance = ch45_cfg.get("dispatch_cap_tolerance_pct", 3.0)
            dispatch_cap_response_sec = ch45_cfg.get("dispatch_cap_response_sec", 60)
            _LOG.info(f"    ✅ Dispatch cap compliance: ±{dispatch_cap_tolerance}% tolerance, {dispatch_cap_response_sec}s response")
        
        # ── Log applicable rules ─────────────────────────────────────
        _LOG.info(f"    📜 Applicable NER rules: {len(compliance_requirements['applicable_rules'])}")
        for rule in compliance_requirements['applicable_rules'][:3]:  # First 3 rules
            _LOG.info(f"       - {rule}")
    else:
        if not grid_connected:
            _LOG.info(f"  ℹ️ Off-grid/island system - Chapter 4/5 compliance not applicable")
        elif compliance_capacity_mw <= ch45_cfg["market_participant_threshold_mw"]:
            _LOG.info(f"  ℹ️ Small generator exemption: {compliance_capacity_mw}MW ≤ {ch45_cfg['market_participant_threshold_mw']}MW threshold")
    
    # ── Initialize ML decision engine (if requested) ─────────────────
    ml_decision_engine = None
    if use_ml_decisions and HAS_ML_DECISION_ENGINE:
        try:
            ml_config = DecisionEngineConfig(
                model_path=ml_model_path,
                use_ml=True,
                ml_confidence_threshold=ml_confidence_threshold,
                hybrid_mode=ml_hybrid_mode,
                log_all_decisions=False,  # Handled by dispatch output arrays
            )
            ml_decision_engine = BESSDecisionEngine(config=ml_config)
            if ml_decision_engine.model_loaded:
                _LOG.info(f"  ✅ ML decision engine loaded from {ml_model_path}")
            else:
                _LOG.info("  ⚠️ ML model not available, using heuristics only")
        except Exception as e:
            _LOG.warning(f"  Failed to initialize ML decision engine: {e}")
            ml_decision_engine = None
    elif use_ml_decisions and not HAS_ML_DECISION_ENGINE:
        _LOG.warning("  ML decision engine not available (import failed)")

    # ── Load per-interval activation data from NEM Data Pack v2 ──────
    activation_lookup = None
    if region and year and enable_fcas:
        try:
            from src.nem_data_pack_v2.loaders import (
                build_activation_series,
                build_activation_series_multiyear,
            )
            if activation_years is not None:
                act_df = build_activation_series_multiyear(
                    region, year, source_years=activation_years,
                )
                _LOG.info("  Using multi-year activation: sources=%s", activation_years)
            else:
                act_df = build_activation_series(region, year)
            if not act_df.empty:
                _SVC_TO_ACT_COL = {
                    "REG_RAISE":   "fcas_reg_raise_activation",
                    "REG_LOWER":   "fcas_reg_lower_activation",
                    "RAISE_1SEC":  "fcas_raise_1sec_activation",
                    "LOWER_1SEC":  "fcas_lower_1sec_activation",
                    "RAISE_6SEC":  "fcas_raise_6sec_activation",
                    "LOWER_6SEC":  "fcas_lower_6sec_activation",
                    "RAISE_60SEC": "fcas_raise_60sec_activation",
                    "LOWER_60SEC": "fcas_lower_60sec_activation",
                    "RAISE_5MIN":  "fcas_raise_5min_activation",
                    "LOWER_5MIN":  "fcas_lower_5min_activation",
                }
                act_df["timestamp"] = pd.to_datetime(act_df["timestamp"], utc=True)
                act_cols = [c for c in act_df.columns if c.endswith("_activation")]
                act_merged = df[["timestamp"]].merge(
                    act_df[["timestamp"] + act_cols],
                    on="timestamp", how="left",
                )
                activation_lookup = []
                for _, arow in act_merged.iterrows():
                    row_map = {}
                    for svc_label, act_col in _SVC_TO_ACT_COL.items():
                        if act_col in arow.index:
                            val = arow[act_col]
                            row_map[svc_label] = float(val) if pd.notna(val) else 1.0
                        else:
                            row_map[svc_label] = 1.0
                    activation_lookup.append(row_map)
                mean_reg = np.mean([d.get("REG_RAISE", 1.0) for d in activation_lookup])
                _LOG.info(f"  Activation data loaded: {len(activation_lookup)} intervals, "
                          f"mean REG_RAISE activation={mean_reg:.1%}")
            else:
                _LOG.warning("  No activation data for %s %d — using activation=1.0", region, year)
        except Exception as exc:
            _LOG.warning("  Failed to load activation data: %s — using activation=1.0", exc)
            activation_lookup = None

    dt_hr = 5.0 / 60.0
    dt_sec = 300.0
    soc_min = cfg["soc_min_frac"] * energy_mwh
    soc_max = cfg["soc_max_frac"] * energy_mwh
    rte = cfg["roundtrip_eff"]

    # ── Ramp-rate & mode-switch config ───────────────────────────────
    ramp_mw_per_sec = cfg.get("ramp_rate_mw_per_sec", 1.0)
    max_ramp_mw = ramp_mw_per_sec * dt_sec
    mode_penalty_intervals = cfg.get("mode_switch_penalty_intervals", 1)
    mode_fcas_derate = cfg.get("mode_switch_fcas_derate", 0.25)

    # Current state
    soc_mwh = energy_mwh * 0.5
    prev_power = 0.0
    prev_mode = "idle"
    mode_switch_countdown = 0

    # ── Detect co-located solar column ───────────────────────────────
    if solar_col is None:
        solar_cols = [c for c in df.columns if c.startswith("solar_") and c.endswith("_mw_ac")]
        if solar_cols:
            solar_col = solar_cols[0]
            _LOG.info(f"  Solar-aware dispatch: using column '{solar_col}'")
        else:
            _LOG.info("  No solar column found — BESS dispatch is grid-only")

    # ══════════════════════════════════════════════════════════════════
    # DYNAMIC SOLAR CONTROLLER — Forward-looking market signals
    # ══════════════════════════════════════════════════════════════════
    spot_prices_arr = df["spot_price_aud_per_mwh"].values.astype(np.float64)
    _price_signals = build_historical_price_signals(
        spot_prices_arr,
        lookahead_intervals=sc["lookahead_intervals"],
        lookback_intervals=sc["lookback_intervals"],
        discharge_threshold=discharge_threshold,
        charge_threshold=charge_threshold,
        roundtrip_eff=rte,
        trend_flat_band=sc["trend_flat_band_aud"],
        trend_normalisation=sc["trend_normalisation_aud"],
        adaptive_discharge_percentile=sc.get("adaptive_discharge_percentile", 75),
        adaptive_charge_percentile=sc.get("adaptive_charge_percentile", 25),
        adaptive_backcast_intervals=sc.get("adaptive_backcast_intervals", 288),
    )
    sig_stored_val     = _price_signals["stored_energy_value"]
    sig_price_trend    = _price_signals["price_trend"]
    sig_neg_ahead      = _price_signals["neg_price_ahead"]
    sig_volatility     = _price_signals["volatility"]
    sig_fwd_max_price  = _price_signals["forward_max_price"]
    sig_fwd_mean_price = _price_signals["forward_mean_price"]
    sig_fwd_min_price  = _price_signals["forward_min_price"]
    sig_adapt_discharge = _price_signals["adaptive_discharge_threshold"]
    sig_adapt_charge    = _price_signals["adaptive_charge_threshold"]

    discharge_floor = sc.get("discharge_floor_aud", 0.0)
    neg_arb_lookahead = sc.get("neg_arb_lookahead_intervals", 36)
    neg_arb_min_spread = sc.get("neg_arb_min_spread_aud", 50.0)

    _LOG.info("  Adaptive thresholds: mean discharge=%.1f, mean charge=%.1f, floor=%.1f",
              float(np.mean(sig_adapt_discharge)),
              float(np.mean(sig_adapt_charge)),
              discharge_floor)
    _LOG.info("  Dynamic solar controller: price signals built "
              "(mean stored_val=$%.1f/MWh, neg_ahead=%.1f%%)",
              float(np.mean(sig_stored_val)),
              100.0 * float(np.mean(sig_neg_ahead)))

    # Load contingency event flags
    sig_event_flag = load_event_flags_for_dispatch(
        region or "VIC1", year or 2025, len(df),
        timestamps=pd.DatetimeIndex(df["timestamp"]) if "timestamp" in df.columns else None,
    )
    n_events = int(np.sum(sig_event_flag))
    _LOG.info("  Event flags: %d contingency intervals (%.1f%%)",
              n_events, 100.0 * n_events / max(1, len(df)))

    # Pre-allocate output lists
    n = len(df)
    out_charge      = [0.0] * n
    out_discharge   = [0.0] * n
    out_soc         = [0.0] * n
    out_fcas_res    = [0.0] * n
    out_fcas_raise  = [0.0] * n
    out_fcas_lower  = [0.0] * n
    out_raise_svc   = [""] * n
    out_lower_svc   = [""] * n
    out_arb_avail   = [0.0] * n
    out_arb_rev     = [0.0] * n
    out_fcas_rev    = [0.0] * n
    out_fcas_raise_rev  = [0.0] * n
    out_fcas_lower_rev  = [0.0] * n
    out_fcas_reg_rev    = [0.0] * n
    out_fcas_cont_rev   = [0.0] * n
    out_degradation     = [0.0] * n
    out_opp         = [0.0] * n
    out_total       = [0.0] * n
    out_charge_from_solar = [0.0] * n
    out_charge_from_grid  = [0.0] * n
    out_solar_export      = [0.0] * n
    # Phase 4: Solar curtailment & GCP signals
    out_solar_available      = [0.0] * n
    out_solar_curtailed      = [0.0] * n
    out_solar_curtail_setpoint = [0.0] * n
    out_solar_curtail_reason = ["none"] * n
    out_gcp_active_power     = [0.0] * n
    out_gcp_export_headroom  = [0.0] * n
    # Phase 5: MASS trapezium, AGC simulation, causer-pays
    out_trap_en_min      = [0.0] * n
    out_trap_en_max      = [0.0] * n
    out_trap_low_bp      = [0.0] * n
    out_trap_high_bp     = [0.0] * n
    out_ramp_raise       = [0.0] * n
    out_ramp_lower       = [0.0] * n
    out_reg_soc_drift    = [0.0] * n
    out_causer_pays      = [0.0] * n

    # ══════════════════════════════════════════════════════════════════
    # Phase 6: Inverter Signal Trace — per-interval decision audit
    # ══════════════════════════════════════════════════════════════════
    # Every interval records WHY the engine made its decision and WHAT
    # signals would be sent to the inverter, AEMO, DNSP, and operator.
    # Works identically for backcast, forecast, and live data.
    #
    # Categories:
    #   sig_*          — market/price signal inputs (read-only context)
    #   inv_*          — inverter setpoint commands (sent to hardware)
    #   aemo_*         — AEMO bid/offer signals (MASS / NEMDE compliance)
    #   dnsp_*         — DNSP export constraint signals
    #   decision_*     — engine reasoning trace (audit log)
    # ─────────────────────────────────────────────────────────────────

    # ── A. Market signal inputs ──────────────────────────────────────
    out_sig_spot_price          = [0.0] * n   # $/MWh — NEM spot this interval
    out_sig_price_trend         = [0.0] * n   # −1..+1 normalised trend
    out_sig_volatility          = [0.0] * n   # $/MWh rolling stddev
    out_sig_fwd_max_price       = [0.0] * n   # $/MWh max in lookahead
    out_sig_fwd_min_price       = [0.0] * n   # $/MWh min in lookahead
    out_sig_fwd_mean_price      = [0.0] * n   # $/MWh mean in lookahead
    out_sig_stored_energy_value = [0.0] * n   # $/MWh value of storing now
    out_sig_neg_price_ahead     = [False] * n # bool — negative price in window
    out_sig_event_flag          = [False] * n # bool — contingency event detected
    out_sig_adapt_discharge_thresh = [0.0] * n  # adaptive discharge threshold
    out_sig_adapt_charge_thresh = [0.0] * n     # adaptive charge threshold

    # ── B. Inverter commands ─────────────────────────────────────────
    out_inv_active_power_mw     = [0.0] * n   # +ve = discharge, −ve = charge
    out_inv_reactive_power_mvar = [0.0] * n   # future: VAr support
    out_inv_mode                = ["idle"] * n # "charge" | "discharge" | "fcas_only" | "idle"
    out_inv_power_limit_mw      = [0.0] * n   # ramp-limited max power this interval
    out_inv_solar_curtail_mw    = [0.0] * n   # solar setpoint command (MW to accept)

    # ── C. AEMO FCAS bid/offer signals (per MASS specification) ──────
    out_aemo_raise_enablement_mw = [0.0] * n  # total raise FCAS enablement
    out_aemo_lower_enablement_mw = [0.0] * n  # total lower FCAS enablement
    out_aemo_reg_raise_bid_mw    = [0.0] * n  # regulation raise bid MW
    out_aemo_reg_lower_bid_mw    = [0.0] * n  # regulation lower bid MW
    out_aemo_cont_raise_bid_mw   = [0.0] * n  # contingency raise bid MW
    out_aemo_cont_lower_bid_mw   = [0.0] * n  # contingency lower bid MW
    out_aemo_energy_bid_mw       = [0.0] * n  # energy market bid/offer MW
    out_aemo_agc_setpoint_mw     = [0.0] * n  # AGC target for regulation

    # ── D. DNSP / export constraint signals ──────────────────────────
    out_dnsp_export_limit_mw     = [0.0] * n  # GCP export limit in force
    out_dnsp_export_actual_mw    = [0.0] * n  # actual export this interval
    out_dnsp_curtail_active      = [False] * n # bool — DNSP curtailment binding

    # ── E. Decision reasoning trace ──────────────────────────────────
    out_decision_mode            = ["idle"] * n  # chosen strategy label
    out_decision_revenue_discharge = [0.0] * n   # adjusted $ value of discharge
    out_decision_revenue_charge    = [0.0] * n   # adjusted $ value of charge
    out_decision_revenue_fcas_only = [0.0] * n   # adjusted $ value of fcas_only
    out_decision_revenue_idle      = [0.0] * n   # adjusted $ value of idle
    out_decision_margin            = [0.0] * n   # $ gap between best & 2nd best
    out_decision_soc_before        = [0.0] * n   # SOC fraction before this interval
    out_decision_soc_after         = [0.0] * n   # SOC fraction after this interval
    out_decision_alloc_strategy    = [""] * n     # which L1 strategy was active
    out_decision_dir_priority      = [""] * n     # which L2 direction was active
    out_decision_headroom_raise_mw = [0.0] * n   # available raise headroom
    out_decision_headroom_lower_mw = [0.0] * n   # available lower headroom
    out_decision_fcas_raise_rev    = [0.0] * n   # FCAS raise revenue (chosen)
    out_decision_fcas_lower_rev    = [0.0] * n   # FCAS lower revenue (chosen)
    out_decision_arb_rev           = [0.0] * n   # arb revenue (chosen)
    out_decision_opp_cost          = [0.0] * n   # opportunity cost vs 2nd best
    
    # ── F. ML Decision Transparency ─────────────────────────────────
    # Tracks whether each decision was made by ML model or heuristics
    out_decision_source          = ["heuristic"] * n  # "ml_model", "heuristic", "ml_assisted", "fallback"
    out_decision_confidence      = [0.0] * n          # confidence score (0-1)
    out_decision_ml_action       = [0.0] * n          # raw ML action if available
    out_decision_ml_value        = [0.0] * n          # ML value estimate if available
    out_decision_reasoning       = [""] * n           # human-readable reasoning summary
    
    # ── G. NER Chapter 4/5 Compliance Tracking ──────────────────────
    # Tracks when compliance constraints were binding during dispatch
    out_compliance_category      = [registration_category] * n   # "exempt", "semi-scheduled", "scheduled"
    out_compliance_gps_ramp_binding = [False] * n  # True if GPS ramp rate limited power change
    out_compliance_dispatch_cap_binding = [False] * n  # True if dispatch cap limited output
    out_compliance_ramp_limit_mw = [0.0] * n       # Actual ramp limit applied (MW/interval)
    out_compliance_causer_pays   = [0.0] * n       # Causer-pays factor applied this interval

    # ── Per-service co-stacked FCAS output arrays (10 markets) ───────
    _ALL_SVC_LABELS = [
        "REG_RAISE", "RAISE_1SEC", "RAISE_6SEC", "RAISE_60SEC", "RAISE_5MIN",
        "REG_LOWER", "LOWER_1SEC", "LOWER_6SEC", "LOWER_60SEC", "LOWER_5MIN",
    ]
    out_per_svc_mw  = {lbl: [0.0] * n for lbl in _ALL_SVC_LABELS}
    out_per_svc_rev = {lbl: [0.0] * n for lbl in _ALL_SVC_LABELS}

    # Static ramp rates (MW/min) from config (may be modified by GPS compliance)
    ramp_raise_mw_per_min = ramp_mw_per_sec * 60.0
    ramp_lower_mw_per_min = ramp_mw_per_sec * 60.0  # symmetric for BESS

    # GCP export limit: use SiteConfig value if present, else infinite
    gcp_export_limit = float('inf')

    for i, (idx, row) in enumerate(df.iterrows()):
        spot = row["spot_price_aud_per_mwh"]
        soc_frac = soc_mwh / energy_mwh if energy_mwh > 0 else 0.5

        # ── Solar availability this interval ─────────────────────────
        solar_mw = float(row[solar_col]) if solar_col else 0.0
        solar_mw = max(0.0, solar_mw)

        # ── Phase 6: Write market signal inputs ──────────────────────
        out_sig_spot_price[i]          = spot
        out_sig_price_trend[i]         = float(sig_price_trend[i])
        out_sig_volatility[i]          = float(sig_volatility[i])
        out_sig_fwd_max_price[i]       = float(sig_fwd_max_price[i])
        out_sig_fwd_min_price[i]       = float(sig_fwd_min_price[i])
        out_sig_fwd_mean_price[i]      = float(sig_fwd_mean_price[i])
        out_sig_stored_energy_value[i] = float(sig_stored_val[i])
        out_sig_neg_price_ahead[i]     = bool(sig_neg_ahead[i])
        out_sig_event_flag[i]          = bool(sig_event_flag[i])
        out_sig_adapt_discharge_thresh[i] = float(sig_adapt_discharge[i])
        out_sig_adapt_charge_thresh[i]    = float(sig_adapt_charge[i])
        out_decision_soc_before[i]     = soc_frac
        out_decision_alloc_strategy[i] = cfg.get("allocation_strategy", "contingency_first")
        out_decision_dir_priority[i]   = cfg.get("direction_priority", "revenue_weighted")

        # ══════════════════════════════════════════════════════════════
        # A.  Compute energy-only arbitrage candidates (ramp-limited)
        # ══════════════════════════════════════════════════════════════
        base_discharge = float(sig_adapt_discharge[i])
        base_charge = float(sig_adapt_charge[i])

        trend_i = float(sig_price_trend[i])
        fwd_max_i = float(sig_fwd_max_price[i])
        fwd_min_i = float(sig_fwd_min_price[i])

        if fwd_max_i > base_discharge * sc["charge_thresh_fwd_ratio"] and trend_i > sc["charge_thresh_trend_trigger"]:
            dynamic_charge_thresh = min(
                base_charge * sc["charge_thresh_max_multiplier"],
                base_charge + (fwd_max_i - base_discharge) * sc["charge_thresh_fwd_spread_frac"],
            )
        else:
            dynamic_charge_thresh = base_charge

        if trend_i < sc["discharge_thresh_trend_trigger"]:
            dynamic_discharge_thresh = base_discharge * sc["discharge_thresh_multiplier"]
        else:
            dynamic_discharge_thresh = base_discharge

        # ── Discharge floor enforcement with exceptions ──────────────
        floor_override = False
        if spot < discharge_floor:
            fwd_end_arb = min(i + neg_arb_lookahead + 1, n)
            fwd_arb_slice = spot_prices_arr[i + 1 : fwd_end_arb] if i + 1 < n else np.array([])
            if len(fwd_arb_slice) > 0:
                fwd_arb_max = float(np.nanmax(fwd_arb_slice))
                neg_arb_spread = fwd_arb_max * rte - spot
                if neg_arb_spread >= neg_arb_min_spread:
                    floor_override = True

        if not floor_override:
            dynamic_discharge_thresh = max(dynamic_discharge_thresh, discharge_floor)

        can_discharge = spot > dynamic_discharge_thresh and soc_mwh > soc_min
        can_charge_grid = spot < dynamic_charge_thresh and soc_mwh < soc_max
        can_charge_solar = solar_mw > 0.0 and soc_mwh < soc_max

        # ── Ramp-rate limits (may be constrained by GPS compliance) ──
        # max_ramp_mw already incorporates GPS limits if applicable
        bess_discharge_ramp_limit = min(bess_rated_mw, prev_power + max_ramp_mw)
        bess_discharge_ramp_limit = max(0.0, bess_discharge_ramp_limit)
        bess_charge_ramp_limit    = min(bess_rated_mw, -prev_power + max_ramp_mw)
        bess_charge_ramp_limit    = max(0.0, bess_charge_ramp_limit)
        
        # Track if GPS ramp rate is the binding constraint
        gps_ramp_is_binding = False
        if gps_ramp_enforced:
            # Check if we would have ramped faster without GPS constraint
            hardware_max_ramp = cfg.get("hardware_ramp_rate_mw_per_sec", 1.0) * dt_sec
            if hardware_max_ramp > max_ramp_mw:
                gps_ramp_is_binding = True
        out_compliance_gps_ramp_binding[i] = gps_ramp_is_binding
        out_compliance_ramp_limit_mw[i] = max_ramp_mw

        bess_discharge_mw = min(bess_discharge_ramp_limit, soc_mwh / dt_hr) if can_discharge else 0.0

        # ── Solar-aware charge split ─────────────────────────────────
        can_charge = can_charge_grid or can_charge_solar
        total_charge_headroom = min(bess_charge_ramp_limit, (soc_max - soc_mwh) / dt_hr) if can_charge else 0.0

        charge_from_solar_mw = min(solar_mw, total_charge_headroom) if can_charge_solar else 0.0
        remaining_headroom = total_charge_headroom - charge_from_solar_mw
        charge_from_grid_mw = remaining_headroom if (can_charge_grid and remaining_headroom > 0) else 0.0
        bess_charge_mw = charge_from_solar_mw + charge_from_grid_mw

        # ── Inverter sharing constraint (DC-coupled) ─────────────────
        if dc_coupled and can_discharge and solar_mw > 0:
            bess_discharge_mw = min(bess_discharge_mw, max(0.0, bess_rated_mw - solar_mw))

        discharge_rev = bess_discharge_mw * spot * dt_hr
        charge_cost   = charge_from_grid_mw * spot * dt_hr

        # ══════════════════════════════════════════════════════════════
        # B.  Pure-FCAS scenario (no energy dispatch, P=0)
        # ══════════════════════════════════════════════════════════════
        fcas_mode_derate = mode_fcas_derate if mode_switch_countdown > 0 else 1.0

        if enable_fcas:
            ramp_limited_pmax = min(bess_rated_mw, abs(prev_power) + max_ramp_mw)
            act_map_i = activation_lookup[i] if activation_lookup else None

            # Empty co-stacked result template for when no FCAS is available
            _EMPTY_STACKED = {
                "total_mw": 0.0, "total_revenue": 0.0,
                "cont_mw": 0.0, "reg_mw": 0.0,
                "cont_revenue": 0.0, "reg_revenue": 0.0,
                "services": {}, "best_label": "NONE",
            }

            def _eval_fcas_with_solar_charge(sc_mw):
                if dc_coupled and solar_mw > 0:
                    eff_raise = min(ramp_limited_pmax, max(0.0, bess_rated_mw - solar_mw) + sc_mw) * fcas_mode_derate
                else:
                    eff_raise = min(ramp_limited_pmax, bess_rated_mw + sc_mw) * fcas_mode_derate
                eff_lower = max(0.0, min(ramp_limited_pmax, bess_rated_mw) - sc_mw) * fcas_mode_derate

                soc_after_sc = min(soc_max, soc_mwh + sc_mw * dt_hr * rte)
                soc_frac_sc = soc_after_sc / energy_mwh if energy_mwh > 0 else 0.5

                rr = _pick_fcas_services_costacked(
                    row, FCAS_RAISE_SERVICES, eff_raise, soc_frac_sc, energy_mwh, cfg,
                    power_mw_rated=bess_rated_mw, activation_map=act_map_i)
                rl = _pick_fcas_services_costacked(
                    row, FCAS_LOWER_SERVICES, eff_lower, soc_frac_sc, energy_mwh, cfg,
                    power_mw_rated=bess_rated_mw, activation_map=act_map_i)

                # Shared capacity budget: raise + lower total_mw <= inverter
                eff_pmax = min(eff_raise, eff_lower)
                rr, rl = _apply_direction_priority(rr, rl, eff_pmax, cfg, act_map_i)

                return rr["total_revenue"] + rl["total_revenue"], rr, rl

            # ── Dynamic stored-energy value ──────────────────────────
            stored_energy_value_per_mwh = float(sig_stored_val[i])
            event_fcas_boost = sc["event_fcas_boost"] if sig_event_flag[i] else 1.0

            if sig_neg_ahead[i] and stored_energy_value_per_mwh > 0:
                stored_energy_value_per_mwh *= sc["neg_ahead_storage_premium"]

            if sig_volatility[i] > sc["volatility_threshold_aud"]:
                vol_bonus = min(sc["volatility_max_bonus"],
                                (sig_volatility[i] - sc["volatility_threshold_aud"]) / sc["volatility_normalisation_aud"])
                stored_energy_value_per_mwh *= (1.0 + vol_bonus)

            # Maximum solar that can go to BESS
            if soc_mwh < soc_max:
                max_sc = min(solar_mw, bess_rated_mw, (soc_max - soc_mwh) / dt_hr, bess_charge_ramp_limit)
            else:
                max_sc = 0.0

            # Build candidate list
            fcas_solar_candidates = []
            sc_levels = sorted(set([0.0, max_sc, max_sc * 0.5, max_sc * 0.25, max_sc * 0.75]))
            for sc_test in sc_levels:
                if sc_test < 0:
                    continue
                sc_test = min(sc_test, max_sc)
                fcas_rev_sc, rr_sc, rl_sc = _eval_fcas_with_solar_charge(sc_test)
                fcas_rev_weighted = fcas_rev_sc * event_fcas_boost
                export_sc = max(0.0, solar_mw - sc_test)
                if dc_coupled:
                    export_sc = min(export_sc, bess_rated_mw)
                    lower_mw_sc = rl_sc["total_mw"]
                    if lower_mw_sc > 0:
                        lower_cap_sc = max(0.0, bess_rated_mw - lower_mw_sc)
                        export_sc = min(export_sc, lower_cap_sc)
                if spot > 0:
                    export_rev_sc = export_sc * spot * dt_hr
                else:
                    export_rev_sc = 0.0
                store_val_sc = sc_test * dt_hr * rte * stored_energy_value_per_mwh
                total_val_sc = fcas_rev_weighted + export_rev_sc + store_val_sc
                fcas_solar_candidates.append((total_val_sc, sc_test, fcas_rev_sc, rr_sc, rl_sc, export_sc))

            best_fc = max(fcas_solar_candidates, key=lambda x: x[0])
            pure_fcas_total_val = best_fc[0]
            pure_fcas_solar_charge = best_fc[1]
            pure_fcas_rev = best_fc[2]
            r_raise_pure = best_fc[3]
            r_lower_pure = best_fc[4]
            pure_fcas_solar_export = best_fc[5]
        else:
            _EMPTY_STACKED = {
                "total_mw": 0.0, "total_revenue": 0.0,
                "cont_mw": 0.0, "reg_mw": 0.0,
                "cont_revenue": 0.0, "reg_revenue": 0.0,
                "services": {}, "best_label": "NONE",
            }
            r_raise_pure = dict(_EMPTY_STACKED)
            r_lower_pure = dict(_EMPTY_STACKED)
            pure_fcas_rev = 0.0
            pure_fcas_total_val = 0.0
            pure_fcas_solar_charge = 0.0
            pure_fcas_solar_export = 0.0

        # ══════════════════════════════════════════════════════════════
        # C.  Arb+FCAS co-optimised scenario
        # ══════════════════════════════════════════════════════════════
        combo_discharge_rev = 0.0
        combo_charge_cost   = 0.0
        combo_fcas_rev      = 0.0
        combo_discharge_mw  = 0.0
        combo_charge_mw     = 0.0
        combo_raise         = (0.0, 0.0, "NONE", 0.0)
        combo_lower         = (0.0, 0.0, "NONE", 0.0)

        # --- C1: discharge + FCAS ---
        if can_discharge and enable_fcas:
            P = bess_discharge_mw
            if dc_coupled and solar_mw > 0:
                effective_raise_cap = max(0.0, bess_rated_mw - solar_mw)
                h_raise = max(0.0, min(effective_raise_cap, bess_rated_mw) - P) * fcas_mode_derate
            else:
                h_raise = max(0.0, bess_rated_mw - P) * fcas_mode_derate
            h_lower = max(0.0, bess_rated_mw + P) * fcas_mode_derate
            soc_after = (soc_mwh - P * dt_hr) / energy_mwh if energy_mwh > 0 else 0.5
            act_map_i = activation_lookup[i] if activation_lookup else None
            cr = _pick_fcas_services_costacked(row, FCAS_RAISE_SERVICES, h_raise, soc_after, energy_mwh, cfg,
                                               power_mw_rated=bess_rated_mw, activation_map=act_map_i)
            cl = _pick_fcas_services_costacked(row, FCAS_LOWER_SERVICES, h_lower, soc_after, energy_mwh, cfg,
                                               power_mw_rated=bess_rated_mw, activation_map=act_map_i)
            total_headroom = max(0.0, bess_rated_mw - P)
            cr, cl = _apply_direction_priority(cr, cl, total_headroom, cfg, act_map_i)
            total_c1 = discharge_rev + cr["total_revenue"] + cl["total_revenue"]
        elif can_discharge:
            total_c1 = discharge_rev
            cr = dict(_EMPTY_STACKED)
            cl = dict(_EMPTY_STACKED)
        else:
            total_c1 = -1e18
            cr = dict(_EMPTY_STACKED)
            cl = dict(_EMPTY_STACKED)

        # --- C2: charge + FCAS ---
        if can_charge and enable_fcas:
            P = -bess_charge_mw
            if dc_coupled and solar_mw > 0:
                h_raise = max(0.0, (bess_rated_mw - solar_mw) + bess_charge_mw) * fcas_mode_derate
            else:
                h_raise = max(0.0, bess_rated_mw + bess_charge_mw) * fcas_mode_derate
            h_lower = max(0.0, bess_rated_mw - bess_charge_mw) * fcas_mode_derate
            soc_after = (soc_mwh + bess_charge_mw * dt_hr * rte) / energy_mwh if energy_mwh > 0 else 0.5
            act_map_i = activation_lookup[i] if activation_lookup else None
            cr2 = _pick_fcas_services_costacked(row, FCAS_RAISE_SERVICES, h_raise, soc_after, energy_mwh, cfg,
                                                power_mw_rated=bess_rated_mw, activation_map=act_map_i)
            cl2 = _pick_fcas_services_costacked(row, FCAS_LOWER_SERVICES, h_lower, soc_after, energy_mwh, cfg,
                                                power_mw_rated=bess_rated_mw, activation_map=act_map_i)
            total_headroom = max(0.0, bess_rated_mw - bess_charge_mw)
            cr2, cl2 = _apply_direction_priority(cr2, cl2, total_headroom, cfg, act_map_i)
            total_c2 = -charge_cost + cr2["total_revenue"] + cl2["total_revenue"]
        elif can_charge:
            total_c2 = -charge_cost
            cr2 = dict(_EMPTY_STACKED)
            cl2 = dict(_EMPTY_STACKED)
        else:
            total_c2 = -1e18
            cr2 = dict(_EMPTY_STACKED)
            cl2 = dict(_EMPTY_STACKED)

        # ══════════════════════════════════════════════════════════════
        # D.  Pick the best overall strategy
        # ══════════════════════════════════════════════════════════════
        if solar_mw > 0 and spot > 0:
            se_discharge = solar_mw
            if dc_coupled:
                se_discharge = min(se_discharge, max(0.0, bess_rated_mw - bess_discharge_mw))
                if cl["total_mw"] > 0:
                    se_discharge = min(se_discharge, max(0.0, bess_rated_mw - bess_discharge_mw - cl["total_mw"]))
            solar_export_rev_c1 = se_discharge * spot * dt_hr
        else:
            solar_export_rev_c1 = 0.0

        if solar_mw > 0 and spot > 0:
            se_charge = max(0.0, solar_mw - charge_from_solar_mw)
            if dc_coupled:
                se_charge = min(se_charge, bess_rated_mw)
                if cl2["total_mw"] > 0:
                    se_charge = min(se_charge, max(0.0, bess_rated_mw - cl2["total_mw"]))
            solar_export_rev_c2 = se_charge * spot * dt_hr
        else:
            solar_export_rev_c2 = 0.0

        if solar_mw > 0 and spot > 0:
            se_idle = solar_mw
            if dc_coupled:
                se_idle = min(se_idle, bess_rated_mw)
            solar_export_rev_idle = se_idle * spot * dt_hr
        else:
            solar_export_rev_idle = 0.0

        candidates = [
            ("discharge", total_c1 + solar_export_rev_c1),
            ("charge",    total_c2 + solar_export_rev_c2),
            ("fcas_only", pure_fcas_total_val),
            ("idle",      solar_export_rev_idle),
        ]

        # ── Dynamic signal adjustments to candidate ranking ──────────
        trend = float(sig_price_trend[i])
        vol_i = float(sig_volatility[i])
        adj_scale = bess_rated_mw * dt_hr

        adjusted_candidates = []
        for label, base_val in candidates:
            adj = base_val

            if trend > sc["rank_trend_threshold"]:
                if label == "discharge":
                    adj -= trend * adj_scale * sc["rank_rising_discharge_penalty"]
                elif label in ("charge", "fcas_only"):
                    adj += trend * adj_scale * sc["rank_rising_charge_bonus"]
            elif trend < -sc["rank_trend_threshold"]:
                if label == "discharge":
                    adj += abs(trend) * adj_scale * sc["rank_falling_discharge_bonus"]
                elif label == "charge":
                    adj -= abs(trend) * adj_scale * sc["rank_falling_charge_penalty"]

            if sig_neg_ahead[i]:
                if label == "charge":
                    adj += adj_scale * sc["rank_neg_ahead_charge_bonus"]
                elif label == "idle":
                    adj -= adj_scale * sc["rank_neg_ahead_idle_penalty"]

            if sig_event_flag[i] and label == "fcas_only":
                adj += adj_scale * sc["rank_event_fcas_bonus"]

            if vol_i > sc["volatility_threshold_aud"]:
                vol_factor = min(sc["volatility_max_bonus"],
                                 (vol_i - sc["volatility_threshold_aud"]) / sc["volatility_normalisation_aud"])
                if label in ("fcas_only", "charge"):
                    adj += vol_factor * adj_scale * sc["rank_vol_fcas_bonus"]
                elif label == "idle":
                    adj -= vol_factor * adj_scale * sc["rank_vol_idle_penalty"]

            adjusted_candidates.append((label, adj))

        # ══════════════════════════════════════════════════════════════
        # D2. ML Decision Integration (if enabled)
        # ══════════════════════════════════════════════════════════════
        # Default to heuristic decision
        decision_source = "heuristic"
        decision_confidence = 0.8  # Default heuristic confidence
        ml_raw_action = 0.0
        ml_value_est = 0.0
        decision_reasoning_str = ""
        
        if ml_decision_engine is not None:
            # Build observation vector for ML model (51 dimensions)
            # [6 base] + [24 forecast] + [6 competitor] + [15 market]
            try:
                ml_obs = _build_ml_observation(
                    soc_frac=soc_frac,
                    spot=spot,
                    trend=trend_i,
                    volatility=vol_i,
                    fwd_max=fwd_max_i,
                    fwd_min=fwd_min_i,
                    neg_ahead=sig_neg_ahead[i],
                    event_flag=sig_event_flag[i],
                    bess_rated_mw=bess_rated_mw,
                )
                
                # Build market state dict for heuristics
                market_state = {
                    "spot_price": spot,
                    "discharge_threshold": dynamic_discharge_thresh,
                    "charge_threshold": dynamic_charge_thresh,
                    "price_trend": trend_i,
                    "volatility": vol_i,
                    "fwd_max_price": fwd_max_i,
                    "neg_price_ahead": sig_neg_ahead[i],
                    "event_flag": sig_event_flag[i],
                    "high_volatility": vol_i > sc["volatility_threshold_aud"],
                }
                
                # Get ML decision
                ml_decision = ml_decision_engine.decide(
                    observation=ml_obs,
                    market_state=market_state,
                    soc_frac=soc_frac,
                    bess_rated_mw=bess_rated_mw,
                )
                
                # Extract ML decision info
                decision_source = ml_decision.source.value
                decision_confidence = ml_decision.confidence
                ml_raw_action = ml_decision.action
                if ml_decision.reasoning.ml_outputs:
                    ml_value_est = ml_decision.reasoning.ml_outputs.get("value_estimate", 0.0)
                decision_reasoning_str = ml_decision.reasoning.summary()
                
                # If ML is confident, override heuristic selection
                if ml_decision.source.value in ("ml_model", "ml_assisted", "ensemble"):
                    mode_to_label = {
                        DecisionMode.DISCHARGE: "discharge",
                        DecisionMode.CHARGE: "charge",
                        DecisionMode.FCAS_ONLY: "fcas_only",
                        DecisionMode.IDLE: "idle",
                    }
                    best_label = mode_to_label[ml_decision.mode]
                    # Verify the selected label is feasible
                    if best_label == "discharge" and not can_discharge:
                        best_label = "idle"
                        decision_reasoning_str += " | ML overridden (no discharge available)"
                        decision_source = "ml_assisted"
                    elif best_label == "charge" and not can_charge:
                        best_label = "idle"
                        decision_reasoning_str += " | ML overridden (no charge available)"
                        decision_source = "ml_assisted"
                else:
                    # ML not confident, use heuristic
                    best_label, best_rev = max(adjusted_candidates, key=lambda x: x[1])
                    decision_reasoning_str = f"Heuristic: {best_label} (ML conf={decision_confidence:.2f})"
                    
            except Exception as e:
                _LOG.debug(f"ML decision failed at interval {i}: {e}")
                best_label, best_rev = max(adjusted_candidates, key=lambda x: x[1])
                decision_source = "fallback"
                decision_reasoning_str = f"Fallback: ML error - {str(e)[:50]}"
        else:
            # No ML engine, use pure heuristics
            best_label, best_rev = max(adjusted_candidates, key=lambda x: x[1])
            decision_reasoning_str = f"Heuristic: {best_label}"

        # Store ML decision transparency data
        out_decision_source[i] = decision_source
        out_decision_confidence[i] = decision_confidence
        out_decision_ml_action[i] = ml_raw_action
        out_decision_ml_value[i] = ml_value_est
        out_decision_reasoning[i] = decision_reasoning_str

        # ══════════════════════════════════════════════════════════════
        # E.  Execute chosen strategy, update SOC
        # ══════════════════════════════════════════════════════════════
        charge_rate = 0.0
        discharge_rate = 0.0
        arb_revenue = 0.0
        fcas_revenue = 0.0
        fcas_raise_rev = 0.0
        fcas_lower_rev = 0.0
        fcas_raise_mw = 0.0
        fcas_lower_mw = 0.0
        raise_svc = "NONE"
        lower_svc = "NONE"
        interval_charge_solar = 0.0
        interval_charge_grid  = 0.0
        # Per-direction co-stacked result dicts for this interval
        chosen_raise = dict(_EMPTY_STACKED)
        chosen_lower = dict(_EMPTY_STACKED)

        if best_label == "discharge":
            discharge_rate = bess_discharge_mw
            soc_mwh -= discharge_rate * dt_hr
            arb_revenue = discharge_rate * spot * dt_hr
            if enable_fcas:
                chosen_raise = cr
                chosen_lower = cl
                fcas_raise_mw  = cr["total_mw"]
                fcas_lower_mw  = cl["total_mw"]
                raise_svc      = cr["best_label"]
                lower_svc      = cl["best_label"]
                fcas_raise_rev = cr["total_revenue"]
                fcas_lower_rev = cl["total_revenue"]
                fcas_revenue   = cr["total_revenue"] + cl["total_revenue"]

        elif best_label == "charge":
            charge_rate = bess_charge_mw
            interval_charge_solar = charge_from_solar_mw
            interval_charge_grid  = charge_from_grid_mw
            soc_mwh += charge_rate * dt_hr * rte
            arb_revenue = -charge_from_grid_mw * spot * dt_hr
            if enable_fcas:
                chosen_raise = cr2
                chosen_lower = cl2
                fcas_raise_mw  = cr2["total_mw"]
                fcas_lower_mw  = cl2["total_mw"]
                raise_svc      = cr2["best_label"]
                lower_svc      = cl2["best_label"]
                fcas_raise_rev = cr2["total_revenue"]
                fcas_lower_rev = cl2["total_revenue"]
                fcas_revenue   = cr2["total_revenue"] + cl2["total_revenue"]

        elif best_label == "fcas_only":
            interval_charge_solar = pure_fcas_solar_charge
            charge_rate = pure_fcas_solar_charge
            if pure_fcas_solar_charge > 0:
                soc_mwh += pure_fcas_solar_charge * dt_hr * rte
            chosen_raise = r_raise_pure
            chosen_lower = r_lower_pure
            fcas_raise_mw  = r_raise_pure["total_mw"]
            fcas_lower_mw  = r_lower_pure["total_mw"]
            raise_svc      = r_raise_pure["best_label"]
            lower_svc      = r_lower_pure["best_label"]
            fcas_raise_rev = r_raise_pure["total_revenue"]
            fcas_lower_rev = r_lower_pure["total_revenue"]
            fcas_revenue   = pure_fcas_rev

        elif best_label == "idle":
            if can_charge_solar and soc_mwh < soc_max:
                opp_solar_charge = min(solar_mw, bess_rated_mw, (soc_max - soc_mwh) / dt_hr)
                if sig_neg_ahead[i] and soc_mwh < soc_max * sc["idle_neg_ahead_soc_frac"]:
                    opp_solar_charge = min(solar_mw, bess_rated_mw, (soc_max - soc_mwh) / dt_hr)
                interval_charge_solar = opp_solar_charge
                charge_rate = opp_solar_charge
                soc_mwh += opp_solar_charge * dt_hr * rte

        # ── Revenue decomposition from co-stacked results ────────────
        fcas_reg_rev = chosen_raise["reg_revenue"] + chosen_lower["reg_revenue"]
        fcas_cont_rev = chosen_raise["cont_revenue"] + chosen_lower["cont_revenue"]

        # ── Write per-service MW and revenue arrays ──────────────────
        for lbl, info in chosen_raise["services"].items():
            out_per_svc_mw[lbl][i] = info["enabled_mw"]
            out_per_svc_rev[lbl][i] = info["revenue"]
        for lbl, info in chosen_lower["services"].items():
            out_per_svc_mw[lbl][i] = info["enabled_mw"]
            out_per_svc_rev[lbl][i] = info["revenue"]

        # ── Degradation cost from regulation throughput ───────────────
        deg_cost = 0.0
        for reg_label in ["REG_RAISE", "REG_LOWER"]:
            reg_info = chosen_raise["services"].get(reg_label) or chosen_lower["services"].get(reg_label)
            if reg_info and reg_info["enabled_mw"] > 0:
                act_deg = (activation_lookup[i].get(reg_label, 1.0)
                           if activation_lookup else 1.0)
                deg_cost += (reg_info["enabled_mw"] * cfg["reg_mwh_per_mw_5min"]
                             * act_deg * cfg["deg_cost_aud_per_mwh"])

        # ── Opportunity cost: best alternative minus chosen ──────────
        chosen_gross = arb_revenue + fcas_revenue
        candidate_values = [v for _, v in adjusted_candidates]
        candidate_values.sort(reverse=True)
        second_best = candidate_values[1] if len(candidate_values) > 1 else 0.0
        opp_cost = max(0.0, second_best - chosen_gross)

        # ── Solar export ─────────────────────────────────────────────
        if best_label == "fcas_only":
            interval_solar_export = pure_fcas_solar_export
        else:
            interval_solar_export = max(0.0, solar_mw - interval_charge_solar)

        # ── Phase 4: Curtailment cascade ─────────────────────────────
        # Order: (1) inverter limit → (2) FCAS headroom → (3) GCP export
        #        → (4) negative-price curtailment.
        # First reason to trigger wins (most specific physical constraint).
        curtail_reason = "none"

        # (1) Inverter limit curtailment (DC-coupled shared capacity)
        if dc_coupled and interval_solar_export > 0:
            inv_cap = max(0.0, bess_rated_mw - discharge_rate)
            if interval_solar_export > inv_cap:
                curtail_reason = "inverter_limit"
                interval_solar_export = inv_cap

        # (2) FCAS headroom curtailment (DC-coupled lower reservation)
        if dc_coupled and fcas_lower_mw > 0 and interval_solar_export > 0:
            lower_cap = max(0.0, bess_rated_mw - discharge_rate - fcas_lower_mw)
            if interval_solar_export > lower_cap:
                if curtail_reason == "none":
                    curtail_reason = "fcas_headroom"
                interval_solar_export = lower_cap

        # (3) GCP export limit constraint
        if interval_solar_export > 0:
            gcp_gross = interval_solar_export + discharge_rate - interval_charge_grid
            if gcp_gross > gcp_export_limit:
                if curtail_reason == "none":
                    curtail_reason = "export_limit"
                interval_solar_export = max(0.0, gcp_export_limit - discharge_rate + interval_charge_grid)

        # (4) Negative-price solar curtailment
        if interval_solar_export > 0:
            should_curtail = False
            if spot < 0:
                battery_full = (soc_mwh >= soc_max * sc["curtail_battery_full_frac"])
                solar_near_cap = (solar_mw >= bess_rated_mw * sc["curtail_solar_near_cap_frac"]) if dc_coupled else False
                if battery_full and solar_near_cap:
                    # Exception: battery full AND solar near cap — keep exporting
                    pass
                elif battery_full:
                    should_curtail = True
                    if curtail_reason == "none":
                        curtail_reason = "bess_full"
                else:
                    should_curtail = True
                    if curtail_reason == "none":
                        curtail_reason = "neg_price"
            if not should_curtail and spot < sc["curtail_proactive_spot_aud"] and sig_neg_ahead[i]:
                if soc_mwh < soc_max * sc["curtail_proactive_soc_frac"]:
                    should_curtail = True
                    if curtail_reason == "none":
                        curtail_reason = "neg_price"
            if should_curtail:
                interval_solar_export = 0.0

        # ── Compute solar curtailment & setpoint ─────────────────────
        solar_actual = interval_solar_export + interval_charge_solar
        solar_curtailed = max(0.0, solar_mw - solar_actual)
        if solar_curtailed > 0.01 and curtail_reason == "none":
            # Curtailment occurred but no explicit reason yet — must be
            # because solar exceeded what we could charge + export
            curtail_reason = "inverter_limit" if dc_coupled else "none"
        solar_curtail_setpoint = solar_actual if solar_curtailed > 0.01 else solar_mw

        # ── GCP active power & headroom ──────────────────────────────
        gcp_active_power = interval_solar_export + discharge_rate - interval_charge_grid
        gcp_headroom = gcp_export_limit - gcp_active_power

        # ── Regulation SOC drift (gentle bias toward target) ─────────
        reg_soc_drift = 0.0
        act_map_i = activation_lookup[i] if activation_lookup else None
        reg_raise_info = chosen_raise["services"].get("REG_RAISE")
        if reg_raise_info and reg_raise_info["enabled_mw"] > 0:
            act_r = act_map_i.get("REG_RAISE", 1.0) if act_map_i else 1.0
            e_reg = reg_raise_info["enabled_mw"] * cfg["reg_mwh_per_mw_5min"] * act_r
            if soc_frac > cfg["target_soc_frac"]:
                soc_mwh -= e_reg
                reg_soc_drift -= e_reg
            else:
                soc_mwh += e_reg * rte
                reg_soc_drift += e_reg * rte
        reg_lower_info = chosen_lower["services"].get("REG_LOWER")
        if reg_lower_info and reg_lower_info["enabled_mw"] > 0:
            act_l = act_map_i.get("REG_LOWER", 1.0) if act_map_i else 1.0
            e_reg = reg_lower_info["enabled_mw"] * cfg["reg_mwh_per_mw_5min"] * act_l
            if soc_frac < cfg["target_soc_frac"]:
                soc_mwh += e_reg * rte
                reg_soc_drift += e_reg * rte
            else:
                soc_mwh -= e_reg
                reg_soc_drift -= e_reg

        # Clamp SOC
        soc_mwh = float(np.clip(soc_mwh, 0.0, energy_mwh))

        # ── MASS trapezium parameters (per-interval, SOC-aware) ──────
        # Enablement min/max define the operating range for FCAS.
        # For a BESS the enablement range is 0 → rated_mw.
        trap_en_min = 0.0
        trap_en_max = bess_rated_mw
        # Low/high breakpoints define where FCAS capability starts to
        # reduce linearly.  For BESS these are typically 0 and rated_mw
        # but we taper them based on SOC to reflect energy feasibility.
        soc_frac_post = soc_mwh / energy_mwh if energy_mwh > 0 else 0.5
        # Raise capability tapers as SOC approaches soc_min
        soc_above_min = max(0.0, soc_frac_post - cfg["soc_min_frac"])
        raise_taper = min(1.0, soc_above_min / cfg.get("soc_taper_width", 0.15)) if cfg.get("soc_taper_width", 0.15) > 0 else 1.0
        # Lower capability tapers as SOC approaches soc_max
        soc_below_max = max(0.0, cfg["soc_max_frac"] - soc_frac_post)
        lower_taper = min(1.0, soc_below_max / cfg.get("soc_taper_width", 0.15)) if cfg.get("soc_taper_width", 0.15) > 0 else 1.0
        # Low breakpoint: below this, raise capability declines
        trap_low_bp = trap_en_min + (1.0 - raise_taper) * bess_rated_mw
        # High breakpoint: above this, lower capability declines
        trap_high_bp = trap_en_max - (1.0 - lower_taper) * bess_rated_mw
        # Ensure low <= high
        trap_low_bp = min(trap_low_bp, trap_high_bp)

        # ── Causer-pays factor (simplified proxy) ────────────────────
        # Real AEMO causer-pays is based on 4-sec SCADA deviations from
        # AGC targets over a 28-day trading interval.  We approximate it
        # as the absolute power deviation from previous interval,
        # normalised by rated power.  Range: 0 (perfectly flat) to 1.
        net_power = discharge_rate - charge_rate
        causer_pays = abs(net_power - prev_power) / bess_rated_mw if bess_rated_mw > 0 else 0.0
        causer_pays = min(1.0, causer_pays)
        
        # Apply Chapter 4/5 causer-pays factor if system is registered generator
        # This scales the causer-pays tracking by the configured factor
        compliance_causer_pays_factor = cfg.get("causer_pays_factor", 1.0) if cfg.get("causer_pays_applied", False) else 1.0
        out_compliance_causer_pays[i] = compliance_causer_pays_factor

        total_revenue = arb_revenue + fcas_revenue

        # ── Store outputs ────────────────────────────────────────────
        out_charge[i]     = charge_rate
        out_discharge[i]  = discharge_rate
        out_soc[i]        = soc_mwh
        out_fcas_res[i]   = fcas_raise_mw + fcas_lower_mw
        out_fcas_raise[i] = fcas_raise_mw
        out_fcas_lower[i] = fcas_lower_mw
        out_raise_svc[i]  = raise_svc
        out_lower_svc[i]  = lower_svc
        out_arb_avail[i]  = discharge_rate if discharge_rate > 0 else charge_rate
        out_arb_rev[i]    = arb_revenue
        out_fcas_rev[i]   = fcas_revenue
        out_fcas_raise_rev[i] = fcas_raise_rev
        out_fcas_lower_rev[i] = fcas_lower_rev
        out_fcas_reg_rev[i]   = fcas_reg_rev
        out_fcas_cont_rev[i]  = fcas_cont_rev
        out_degradation[i]    = deg_cost
        out_opp[i]        = opp_cost
        out_total[i]      = total_revenue
        out_charge_from_solar[i] = interval_charge_solar
        out_charge_from_grid[i]  = interval_charge_grid
        out_solar_export[i]      = interval_solar_export
        # Phase 4: Solar curtailment & GCP
        out_solar_available[i]         = solar_mw
        out_solar_curtailed[i]         = solar_curtailed
        out_solar_curtail_setpoint[i]  = solar_curtail_setpoint
        out_solar_curtail_reason[i]    = curtail_reason
        out_gcp_active_power[i]        = gcp_active_power
        out_gcp_export_headroom[i]     = gcp_headroom
        # Phase 5: MASS trapezium, reg drift, causer-pays
        out_trap_en_min[i]     = trap_en_min
        out_trap_en_max[i]     = trap_en_max
        out_trap_low_bp[i]     = trap_low_bp
        out_trap_high_bp[i]    = trap_high_bp
        out_ramp_raise[i]      = ramp_raise_mw_per_min
        out_ramp_lower[i]      = ramp_lower_mw_per_min
        out_reg_soc_drift[i]   = reg_soc_drift
        out_causer_pays[i]     = causer_pays

        # Phase 6: Inverter Signal Trace
        # ── B. Inverter commands ─────────────────────────────────────
        out_inv_active_power_mw[i]     = discharge_rate - charge_rate  # +ve=export, −ve=import
        out_inv_mode[i]                = best_label
        out_inv_power_limit_mw[i]      = min(bess_rated_mw, abs(prev_power) + max_ramp_mw)
        out_inv_solar_curtail_mw[i]    = solar_curtail_setpoint

        # ── C. AEMO FCAS bid/offer signals ───────────────────────────
        out_aemo_raise_enablement_mw[i] = fcas_raise_mw
        out_aemo_lower_enablement_mw[i] = fcas_lower_mw
        # Decompose reg vs cont for AEMO bidding
        out_aemo_reg_raise_bid_mw[i]   = chosen_raise.get("reg_mw", 0.0)
        out_aemo_reg_lower_bid_mw[i]   = chosen_lower.get("reg_mw", 0.0)
        out_aemo_cont_raise_bid_mw[i]  = chosen_raise.get("cont_mw", 0.0)
        out_aemo_cont_lower_bid_mw[i]  = chosen_lower.get("cont_mw", 0.0)
        out_aemo_energy_bid_mw[i]      = discharge_rate - charge_from_grid_mw
        # AGC setpoint for regulation: net power considering reg drift
        out_aemo_agc_setpoint_mw[i]    = discharge_rate - charge_rate + reg_soc_drift / dt_hr if dt_hr > 0 else 0.0

        # ── D. DNSP / export constraint signals ──────────────────────
        out_dnsp_export_limit_mw[i]    = gcp_export_limit if gcp_export_limit != float('inf') else bess_rated_mw
        out_dnsp_export_actual_mw[i]   = gcp_active_power
        out_dnsp_curtail_active[i]     = curtail_reason in ("export_limit", "inverter_limit")

        # ── E. Decision reasoning trace ──────────────────────────────
        out_decision_mode[i]           = best_label
        # Store adjusted candidate values for all 4 strategies
        _adj_lookup = {label: val for label, val in adjusted_candidates}
        out_decision_revenue_discharge[i] = _adj_lookup.get("discharge", -1e18)
        out_decision_revenue_charge[i]    = _adj_lookup.get("charge", -1e18)
        out_decision_revenue_fcas_only[i] = _adj_lookup.get("fcas_only", 0.0)
        out_decision_revenue_idle[i]      = _adj_lookup.get("idle", 0.0)
        # Margin = gap between 1st and 2nd best
        _sorted_vals = sorted(_adj_lookup.values(), reverse=True)
        out_decision_margin[i]     = _sorted_vals[0] - _sorted_vals[1] if len(_sorted_vals) > 1 else 0.0
        out_decision_soc_after[i]  = soc_mwh / energy_mwh if energy_mwh > 0 else 0.5
        out_decision_headroom_raise_mw[i] = max(0.0, bess_rated_mw - discharge_rate) if best_label == "discharge" else bess_rated_mw
        out_decision_headroom_lower_mw[i] = max(0.0, bess_rated_mw - charge_rate) if best_label == "charge" else bess_rated_mw
        out_decision_fcas_raise_rev[i] = fcas_raise_rev
        out_decision_fcas_lower_rev[i] = fcas_lower_rev
        out_decision_arb_rev[i]        = arb_revenue
        out_decision_opp_cost[i]       = opp_cost

        # ── Update state for next interval ───────────────────────────
        if best_label == "discharge":
            new_power = discharge_rate
        elif best_label == "charge":
            new_power = -charge_rate
        else:
            new_power = 0.0

        new_mode = best_label
        is_mode_switch = (
            (prev_mode == "charge" and new_mode == "discharge") or
            (prev_mode == "discharge" and new_mode == "charge")
        )
        if is_mode_switch:
            mode_switch_countdown = mode_penalty_intervals
        elif mode_switch_countdown > 0:
            mode_switch_countdown -= 1

        prev_power = new_power
        prev_mode = new_mode

    # ── Build output dict ────────────────────────────────────────────
    total_annual = sum(out_total)
    total_arb    = sum(out_arb_rev)
    total_fcas   = sum(out_fcas_rev)
    total_reg    = sum(out_fcas_reg_rev)
    total_cont   = sum(out_fcas_cont_rev)
    total_deg    = sum(out_degradation)
    total_opp    = sum(out_opp)
    total_solar_charge_mwh = sum(out_charge_from_solar) * dt_hr
    total_grid_charge_mwh  = sum(out_charge_from_grid) * dt_hr
    total_curtailed_mwh    = sum(out_solar_curtailed) * dt_hr
    curtail_reasons = {}
    for r in out_solar_curtail_reason:
        if r != "none":
            curtail_reasons[r] = curtail_reasons.get(r, 0) + 1
    _LOG.info(f"  Annual revenue: ${total_annual:,.0f}  (arb ${total_arb:,.0f} + FCAS ${total_fcas:,.0f})")
    _LOG.info(f"  FCAS breakdown: regulation ${total_reg:,.0f}, contingency ${total_cont:,.0f}")
    _LOG.info(f"  Degradation cost: ${total_deg:,.0f}, opportunity cost: ${total_opp:,.0f}")
    _LOG.info(f"  Charge split: solar {total_solar_charge_mwh:,.1f} MWh, grid {total_grid_charge_mwh:,.1f} MWh")
    _LOG.info(f"  Solar curtailed: {total_curtailed_mwh:,.1f} MWh across {sum(curtail_reasons.values())} intervals")
    if curtail_reasons:
        _LOG.info(f"  Curtailment reasons: {curtail_reasons}")
    total_reg_drift = sum(out_reg_soc_drift)
    mean_causer = sum(out_causer_pays) / max(1, n)
    _LOG.info(f"  Regulation SOC drift: {total_reg_drift:+.3f} MWh net, "
              f"causer-pays mean={mean_causer:.4f}")
    _LOG.info(f"  MASS trapezium: low_bp mean={sum(out_trap_low_bp)/max(1,n):.3f}, "
              f"high_bp mean={sum(out_trap_high_bp)/max(1,n):.3f} MW")

    # ── ML Decision Transparency Summary ─────────────────────────────
    from collections import Counter
    source_counts = Counter(out_decision_source)
    ml_decisions = source_counts.get("ml_model", 0) + source_counts.get("ml_assisted", 0) + source_counts.get("ensemble", 0)
    heur_decisions = source_counts.get("heuristic", 0) + source_counts.get("fallback", 0)
    avg_confidence = sum(out_decision_confidence) / max(1, n)
    _LOG.info(f"  Decision sources: ML={ml_decisions} ({100*ml_decisions/max(1,n):.1f}%), "
              f"Heuristic={heur_decisions} ({100*heur_decisions/max(1,n):.1f}%), "
              f"avg_confidence={avg_confidence:.2f}")
    if ml_decisions > 0:
        ml_intervals = [i for i, s in enumerate(out_decision_source) if s in ("ml_model", "ml_assisted", "ensemble")]
        ml_revenue = sum(out_total[i] for i in ml_intervals)
        _LOG.info(f"  ML-driven revenue: ${ml_revenue:,.0f} ({100*ml_revenue/max(1,total_annual):.1f}% of total)")

    # ── Per-service co-stacking summary ──────────────────────────────
    svc_rev_totals = {lbl: sum(out_per_svc_rev[lbl]) for lbl in _ALL_SVC_LABELS}
    active_svcs = {lbl: v for lbl, v in svc_rev_totals.items() if v > 0.01}
    _LOG.info(f"  Co-stacked FCAS: {len(active_svcs)} active services "
              f"(of {len(_ALL_SVC_LABELS)} available)")
    for lbl in _ALL_SVC_LABELS:
        rev = svc_rev_totals[lbl]
        if rev > 0.01:
            mean_mw = sum(out_per_svc_mw[lbl]) / max(1, n)
            _LOG.info(f"    {lbl:15s}: ${rev:>10,.0f}  (mean {mean_mw:.3f} MW)")

    # ── NER Chapter 4/5 Compliance Summary ───────────────────────────
    if grid_connected and is_registered_generator:
        gps_binding_count = sum(out_compliance_gps_ramp_binding)
        dispatch_cap_binding_count = sum(out_compliance_dispatch_cap_binding)
        _LOG.info(f"  📋 Compliance summary ({registration_category}, {compliance_capacity_mw}MW):")
        _LOG.info(f"    GPS ramp binding: {gps_binding_count} intervals ({100*gps_binding_count/max(1,n):.1f}%)")
        _LOG.info(f"    Dispatch cap binding: {dispatch_cap_binding_count} intervals ({100*dispatch_cap_binding_count/max(1,n):.1f}%)")
        if compliance_requirements.get("causer_pays", False):
            mean_cp = sum(out_compliance_causer_pays) / max(1, n)
            _LOG.info(f"    Causer-pays factor applied: {mean_cp:.2f}")

    result = {
        "charge_mw":               out_charge,
        "discharge_mw":            out_discharge,
        "soc_mwh":                 out_soc,
        "soc_pct":                 [s / energy_mwh * 100 if energy_mwh > 0 else 0.0 for s in out_soc],
        "charge_from_solar_mw":    out_charge_from_solar,
        "charge_from_grid_mw":     out_charge_from_grid,
        "solar_export_mw":         out_solar_export,
        "solar_actual_production_mw": [e + c for e, c in zip(out_solar_export, out_charge_from_solar)],
        # Phase 4: Solar curtailment
        "solar_available_mw":      out_solar_available,
        "solar_curtailed_mw":      out_solar_curtailed,
        "solar_curtail_setpoint_mw": out_solar_curtail_setpoint,
        "solar_curtail_reason":    out_solar_curtail_reason,
        # Phase 4: GCP
        "gcp_active_power_mw":     out_gcp_active_power,
        "gcp_export_headroom_mw":  out_gcp_export_headroom,
        # Phase 5: MASS trapezium
        "trap_enablement_min_mw":  out_trap_en_min,
        "trap_enablement_max_mw":  out_trap_en_max,
        "trap_low_breakpoint_mw":  out_trap_low_bp,
        "trap_high_breakpoint_mw": out_trap_high_bp,
        "ramp_rate_raise_mw_per_min": out_ramp_raise,
        "ramp_rate_lower_mw_per_min": out_ramp_lower,
        # Phase 5: AGC / regulation
        "reg_soc_drift_mwh":       out_reg_soc_drift,
        "causer_pays_factor":      out_causer_pays,
        # FCAS aggregates (backward-compatible)
        "fcas_reserved_mw":        out_fcas_res,
        "fcas_raise_mw":           out_fcas_raise,
        "fcas_lower_mw":           out_fcas_lower,
        "fcas_raise_service":      out_raise_svc,
        "fcas_lower_service":      out_lower_svc,
        "fcas_raise_revenue_aud":  out_fcas_raise_rev,
        "fcas_lower_revenue_aud":  out_fcas_lower_rev,
        "fcas_reg_revenue_aud":    out_fcas_reg_rev,
        "fcas_cont_revenue_aud":   out_fcas_cont_rev,
        "arb_available_mw":        out_arb_avail,
        "arb_revenue_aud":         out_arb_rev,
        "fcas_revenue_aud":        out_fcas_rev,
        "opp_cost_aud":            out_opp,
        "total_revenue_aud":       out_total,
        "degradation_cost_aud":    out_degradation,
        # ── Phase 6: Inverter Signal Trace ──────────────────────────
        # Market signal inputs
        "sig_spot_price":              out_sig_spot_price,
        "sig_price_trend":             out_sig_price_trend,
        "sig_volatility":              out_sig_volatility,
        "sig_fwd_max_price":           out_sig_fwd_max_price,
        "sig_fwd_min_price":           out_sig_fwd_min_price,
        "sig_fwd_mean_price":          out_sig_fwd_mean_price,
        "sig_stored_energy_value":     out_sig_stored_energy_value,
        "sig_neg_price_ahead":         out_sig_neg_price_ahead,
        "sig_event_flag":              out_sig_event_flag,
        "sig_adapt_discharge_thresh":  out_sig_adapt_discharge_thresh,
        "sig_adapt_charge_thresh":     out_sig_adapt_charge_thresh,
        # Inverter commands
        "inv_active_power_mw":         out_inv_active_power_mw,
        "inv_reactive_power_mvar":     out_inv_reactive_power_mvar,
        "inv_mode":                    out_inv_mode,
        "inv_power_limit_mw":          out_inv_power_limit_mw,
        "inv_solar_curtail_mw":        out_inv_solar_curtail_mw,
        # AEMO FCAS bid / offer signals
        "aemo_raise_enablement_mw":    out_aemo_raise_enablement_mw,
        "aemo_lower_enablement_mw":    out_aemo_lower_enablement_mw,
        "aemo_reg_raise_bid_mw":       out_aemo_reg_raise_bid_mw,
        "aemo_reg_lower_bid_mw":       out_aemo_reg_lower_bid_mw,
        "aemo_cont_raise_bid_mw":      out_aemo_cont_raise_bid_mw,
        "aemo_cont_lower_bid_mw":      out_aemo_cont_lower_bid_mw,
        "aemo_energy_bid_mw":          out_aemo_energy_bid_mw,
        "aemo_agc_setpoint_mw":        out_aemo_agc_setpoint_mw,
        # DNSP export constraint signals
        "dnsp_export_limit_mw":        out_dnsp_export_limit_mw,
        "dnsp_export_actual_mw":       out_dnsp_export_actual_mw,
        "dnsp_curtail_active":         out_dnsp_curtail_active,
        # Decision reasoning trace
        "decision_mode":               out_decision_mode,
        "decision_revenue_discharge":  out_decision_revenue_discharge,
        "decision_revenue_charge":     out_decision_revenue_charge,
        "decision_revenue_fcas_only":  out_decision_revenue_fcas_only,
        "decision_revenue_idle":       out_decision_revenue_idle,
        "decision_margin":             out_decision_margin,
        "decision_soc_before":         out_decision_soc_before,
        "decision_soc_after":          out_decision_soc_after,
        "decision_alloc_strategy":     out_decision_alloc_strategy,
        "decision_dir_priority":       out_decision_dir_priority,
        "decision_headroom_raise_mw":  out_decision_headroom_raise_mw,
        "decision_headroom_lower_mw":  out_decision_headroom_lower_mw,
        "decision_fcas_raise_rev":     out_decision_fcas_raise_rev,
        "decision_fcas_lower_rev":     out_decision_fcas_lower_rev,
        "decision_arb_rev":            out_decision_arb_rev,
        "decision_opp_cost":           out_decision_opp_cost,
        # ML Decision Transparency
        "decision_source":             out_decision_source,
        "decision_confidence":         out_decision_confidence,
        "decision_ml_action":          out_decision_ml_action,
        "decision_ml_value":           out_decision_ml_value,
        "decision_reasoning":          out_decision_reasoning,
        # NER Chapter 4/5 Compliance Tracking
        "compliance_category":         out_compliance_category,
        "compliance_gps_ramp_binding": out_compliance_gps_ramp_binding,
        "compliance_dispatch_cap_binding": out_compliance_dispatch_cap_binding,
        "compliance_ramp_limit_mw":    out_compliance_ramp_limit_mw,
        "compliance_causer_pays":      out_compliance_causer_pays,
        # Compliance metadata (single values, not per-interval)
        "_compliance_metadata": {
            "capacity_mw": compliance_capacity_mw,
            "registration_category": registration_category,
            "gps_ramp_enforced": gps_ramp_enforced,
            "dispatch_cap_enforced": dispatch_cap_enforced,
            "applicable_rules": compliance_requirements.get("applicable_rules", []),
        },
    }

    # ── Per-service co-stacked MW and revenue (20 new keys) ──────────
    for lbl in _ALL_SVC_LABELS:
        key_mw  = f"fcas_{lbl.lower()}_enabled_mw"
        key_rev = f"fcas_{lbl.lower()}_revenue_aud"
        result[key_mw]  = out_per_svc_mw[lbl]
        result[key_rev] = out_per_svc_rev[lbl]

    # Aggregate contingency totals (raise and lower)
    # Contingency services CASCADE on the same physical MW, so the
    # aggregate is the MAX (shared capacity), not sum.
    result["fcas_contingency_raise_total_mw"] = [
        max((out_per_svc_mw[lbl][j] for lbl in _ALL_SVC_LABELS
            if "RAISE" in lbl and lbl != "REG_RAISE"), default=0.0)
        for j in range(n)
    ]
    result["fcas_contingency_lower_total_mw"] = [
        max((out_per_svc_mw[lbl][j] for lbl in _ALL_SVC_LABELS
            if "LOWER" in lbl and lbl != "REG_LOWER"), default=0.0)
        for j in range(n)
    ]

    return result
