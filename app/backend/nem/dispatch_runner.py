"""
dispatch_runner.py — HaimOS BESS Dispatch Runner
=================================================
Thin wrapper around fcas_dispatch_engine.dispatch_bess() that:
  1. Takes a live AEMO price DataFrame (from aemo_fetch.py)
  2. Applies configurable BESS parameters + a named dispatch strategy
  3. Returns a serialisable dict of per-interval dispatch results
     + revenue summary ready for the HaimOS NEM dashboard API.

Dispatch Strategies
-------------------
All available strategies are defined in dispatch_strategies.py.  Pass a
strategy_id (e.g. "co_optimised_revenue_max") to run_dispatch() to select the
algorithm.  Use run_dispatch_compare() to run multiple strategies in a single
call and receive side-by-side results.

No Streamlit session_state dependency — parameters are plain dicts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

_LOG = logging.getLogger(__name__)

# ── Default BESS configuration ────────────────────────────────────────────
@dataclass
class BESSConfig:
    """
    BESS system parameters for the dispatch simulation.

    Dispatch decisions are driven entirely by the adaptive dynamic-price
    engine in aemo_forecast_signals.py (percentile-based forecast+backcast
    thresholds derived from live AEMO prices).  The two *_threshold fields
    below are only used as seed fallbacks for the very first intervals of a
    series where insufficient history exists — they do NOT drive live dispatch.
    """
    bess_power_mw: float = 5.0
    bess_energy_mwh: float = 10.0
    enable_fcas: bool = True
    # Seed fallbacks for the adaptive threshold engine — NOT fixed thresholds.
    # The engine replaces these with percentile-derived values once it has data.
    adaptive_seed_charge_aud: float = 50.0
    adaptive_seed_discharge_aud: float = 100.0
    dc_coupled: bool = True
    grid_connected: bool = True
    export_capacity_mw: Optional[float] = None
    nem_region: str = "VIC1"
    # Solar co-location — set solar_dc_mw > 0 to inject a solar profile
    solar_dc_mw: float = 0.0          # DC nameplate, e.g. 6.0 for 6 MW DC
    solar_lat: float = -37.8136       # Site latitude (default Melbourne)
    solar_lon: float = 144.9631       # Site longitude
    solar_tilt_deg: float = 25.0      # Panel tilt
    solar_az_deg: float = 0.0         # Panel azimuth (0=North in SH)
    solar_inv_kw: Optional[float] = None  # Inverter kW; defaults to DC×0.85


def _inject_solar_profile(df: pd.DataFrame, config: "BESSConfig") -> pd.DataFrame:
    """
    Inject a solar generation column into the price DataFrame so that
    fcas_dispatch_engine.dispatch_bess() auto-detects it via the
    ``solar_*_mw_ac`` column-name pattern.

    Strategy (in order of preference):
      1. SolarTool solar_engine.run_sim() with Open-Meteo weather data
         — physically correct, cloud-derated, uses C1-C16 cell-level model
         internally; we only need the aggregate AC output (kWac column).
      2. Sinusoidal fallback — if run_sim() can't be imported or fails.

    The column is named  ``solar_{N}mwdc_mw_ac``  (e.g. ``solar_6mwdc_mw_ac``)
    so the dispatch engine picks it up automatically.
    """
    dc_mw = config.solar_dc_mw
    dc_mwdc = int(round(dc_mw))
    solar_col = f"solar_{dc_mwdc}mwdc_mw_ac"

    # Inverter kW: default to DC × 0.85 (typical ILR for utility-scale)
    inv_kw = config.solar_inv_kw or (dc_mw * 1000.0 * 0.85)

    if "timestamp" not in df.columns or df.empty:
        df[solar_col] = 0.0
        return df

    ts_series = pd.to_datetime(df["timestamp"])
    start_str = ts_series.min().strftime("%Y-%m-%d %H:%M")
    end_str   = ts_series.max().strftime("%Y-%m-%d %H:%M")

    # ── Attempt Option A: SolarTool solar_engine.run_sim() ────────────────
    _SOLARTOOL_PATH = "/Users/haimptasznik/Desktop/SolarTool_2026-04-24_v1_Mark1"
    try:
        import sys as _sys
        if _SOLARTOOL_PATH not in _sys.path:
            _sys.path.insert(0, _SOLARTOOL_PATH)

        from solar_engine import run_sim as _run_solar_sim  # type: ignore

        # Attempt to get weather service (Open-Meteo, no API key needed)
        weather_svc = None
        try:
            from csiro_weather_service import CSIROWeatherService  # type: ignore
            try:
                weather_svc = CSIROWeatherService(allow_openmeteo_only=True)
            except Exception:
                weather_svc = None
        except ImportError:
            pass

        sim_df = _run_solar_sim(
            lat_deg=config.solar_lat,
            lon_deg=config.solar_lon,
            tz_utc_offset=10.0,
            start=start_str,
            end=end_str,
            freq="5min",
            panel_az_deg=config.solar_az_deg,
            panel_tilt_deg=config.solar_tilt_deg,
            dc_array_size_kw=dc_mw * 1000.0,
            inv_capacity_kw=inv_kw,
            inv_efficiency=0.975,
            irradiance_scale=0.85,
            weather_service=weather_svc,
            use_csiro_weather=(weather_svc is not None),
        )

        # sim_df has DateTime + "Array Output PV (kWac)" — convert to MW
        sim_df = sim_df.copy()
        sim_df["hm"] = (
            pd.to_datetime(sim_df["DateTime"]).dt.hour * 60
            + pd.to_datetime(sim_df["DateTime"]).dt.minute
        )
        sim_df["_mw"] = sim_df["Array Output PV (kWac)"] / 1000.0
        lookup = sim_df.set_index("hm")["_mw"].to_dict()

        df = df.copy()
        df["_hm"] = ts_series.dt.hour * 60 + ts_series.dt.minute
        df[solar_col] = df["_hm"].map(lookup).fillna(0.0)
        df.drop(columns=["_hm"], inplace=True)

        ws = getattr(sim_df, "attrs", {}).get("weather_source", "open-meteo")
        _LOG.info(
            "Solar profile injected via solar_engine.run_sim() [%s]: "
            "%s  mean=%.2f MW  peak=%.2f MW",
            ws, solar_col, df[solar_col].mean(), df[solar_col].max(),
        )
        return df

    except Exception as exc:
        _LOG.warning("solar_engine.run_sim() unavailable (%s); using sinusoidal fallback", exc)

    # ── Option B: sinusoidal fallback ─────────────────────────────────────
    df = df.copy()
    hours = ts_series.dt.hour + ts_series.dt.minute / 60.0
    shape = np.maximum(0.0, np.sin((hours - 6.0) / 13.0 * np.pi))
    peak_mw = (inv_kw / 1000.0) * 0.85   # irr_scale ≈ 0.85 clear-sky
    df[solar_col] = shape * peak_mw
    _LOG.info(
        "Solar profile injected via sinusoidal fallback: %s  mean=%.2f MW",
        solar_col, df[solar_col].mean(),
    )
    return df


def run_dispatch(
    prices_df: pd.DataFrame,
    config: Optional[BESSConfig] = None,
    strategy_id: Optional[str] = None,
) -> dict:
    """
    Run the BESS dispatch engine over a price DataFrame.

    Args:
        prices_df: DataFrame with at minimum:
            - timestamp (datetime)
            - price_mwh (NEM spot $/MWh)
            - fcas_raise_6sec_aud_per_mw, fcas_lower_6sec_aud_per_mw, ...
              (all 10 FCAS columns — present if fetched via aemo_fetch.py)
        config: BESSConfig — defaults to 5 MW / 10 MWh VIC1 unit.
        strategy_id: Named dispatch strategy from dispatch_strategies.py.
            Overrides enable_fcas, allocation_strategy, force_dispatch_mode,
            and any engine_overrides defined in the strategy spec.
            Defaults to "co_optimised_revenue_max".

    Returns:
        {
          "strategy_id":   the active strategy identifier,
          "strategy_name": human-readable strategy name,
          "intervals": [ {timestamp, spot, soc_pct, action, dispatch_mw,
                          fcas_service, revenue_aud, cumulative_revenue_aud} ],
          "summary": { total_revenue, arb_revenue, fcas_revenue,
                       intervals_dispatched, intervals_charged,
                       peak_soc_pct, min_soc_pct }
        }
    """
    if config is None:
        config = BESSConfig()

    # ── Resolve strategy ──────────────────────────────────────────────────
    try:
        from nem.dispatch_strategies import (
            get_strategy, DEFAULT_STRATEGY_ID, strategy_overrides
        )
    except ImportError:
        try:
            from dispatch_strategies import (  # type: ignore
                get_strategy, DEFAULT_STRATEGY_ID, strategy_overrides
            )
        except ImportError:
            get_strategy = None  # type: ignore

    active_strategy_id = strategy_id or DEFAULT_STRATEGY_ID
    active_strategy_name = active_strategy_id
    strat_overrides: dict = {}

    if get_strategy is not None:
        try:
            spec = get_strategy(active_strategy_id)
            active_strategy_name = spec.name
            strat_overrides = strategy_overrides(active_strategy_id)
            # Apply top-level strategy flags to config
            config.enable_fcas = strat_overrides.get("enable_fcas", config.enable_fcas)
        except KeyError as exc:
            _LOG.warning("Unknown strategy '%s', using default: %s", strategy_id, exc)
            active_strategy_id = DEFAULT_STRATEGY_ID
            active_strategy_name = DEFAULT_STRATEGY_ID

    # Map aemo_fetch.py column names → dispatch engine column names
    df = prices_df.copy()
    col_map = {
        "price_mwh": "spot_price_aud_per_mwh",
    }
    df.rename(columns=col_map, inplace=True)

    # Try to import the dispatch engine
    try:
        from nem.fcas_dispatch_engine import dispatch_bess
    except ImportError:
        try:
            from fcas_dispatch_engine import dispatch_bess
        except ImportError:
            _LOG.error("fcas_dispatch_engine not found")
            return _empty_result()

    if "spot_price_aud_per_mwh" not in df.columns or df.empty:
        return _empty_result()

    # Inject solar profile before dispatch (engine auto-detects solar_*_mw_ac)
    if config.solar_dc_mw > 0:
        df = _inject_solar_profile(df, config)

    # Build engine kwargs — strategy overrides take precedence
    engine_kwargs: dict = {
        "df":                  df,
        "bess_rated_mw":       config.bess_power_mw,
        "energy_mwh":          config.bess_energy_mwh,
        "enable_fcas":         config.enable_fcas,
        "charge_threshold":    config.adaptive_seed_charge_aud,
        "discharge_threshold": config.adaptive_seed_discharge_aud,
        "region":              config.nem_region,
        "dc_coupled":          config.dc_coupled,
        "grid_connected":      config.grid_connected,
        "export_capacity_mw":  config.export_capacity_mw or config.bess_power_mw,
    }

    # Merge strategy-specific engine overrides (allocation_strategy, force_dispatch_mode, etc.)
    if strat_overrides:
        for k, v in strat_overrides.items():
            if k in ("enable_fcas",):
                continue  # already applied to config above
            if k == "adaptive_thresholds" and not v:
                # Static threshold mode: engine_overrides from the strategy spec
                # carry the explicit charge_threshold / discharge_threshold values
                pass
            elif k in ("charge_threshold", "discharge_threshold"):
                engine_kwargs[k] = v
            elif k not in ("adaptive_thresholds",):
                # Everything else (allocation_strategy, force_dispatch_mode, reg_min_frac, …)
                # is forwarded as extra cfg keys inside the engine's fcas_config dict
                engine_kwargs.setdefault("fcas_config", {})[k] = v

    # Strip any kwargs that dispatch_bess doesn't accept (safety net)
    import inspect as _inspect
    _valid = set(_inspect.signature(dispatch_bess).parameters.keys())
    engine_kwargs = {k: v for k, v in engine_kwargs.items() if k in _valid}

    try:
        result = dispatch_bess(**engine_kwargs)
    except Exception as exc:
        _LOG.warning("dispatch_bess failed: %s", exc)
        return _empty_result()

    # Build per-interval records
    n = len(df)
    timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else list(range(n))
    spots = df["spot_price_aud_per_mwh"].tolist()

    soc_pct     = _arr(result.get("soc_pct"), n)
    charge_mw   = _arr(result.get("charge_mw"), n)
    discharge_mw = _arr(result.get("discharge_mw"), n)
    rev         = _arr(result.get("total_revenue_aud"), n)
    fcas_svc    = result.get("fcas_raise_service", ["—"] * n)
    if not isinstance(fcas_svc, (list, np.ndarray)):
        fcas_svc = ["—"] * n

    cum_rev = float(0)
    intervals = []
    for i in range(n):
        cum_rev += float(rev[i])
        net_mw = float(discharge_mw[i]) - float(charge_mw[i])
        if net_mw > 0.05:
            action = "discharge"
        elif net_mw < -0.05:
            action = "charge"
        else:
            action = "idle"
        ts = timestamps[i]
        intervals.append({
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "spot_aud_per_mwh": round(float(spots[i]), 2),
            "soc_pct": round(float(soc_pct[i]), 1),
            "action": action,
            "dispatch_mw": round(net_mw, 3),
            "fcas_service": str(fcas_svc[i]) if i < len(fcas_svc) else "—",
            "interval_revenue_aud": round(float(rev[i]), 2),
            "cumulative_revenue_aud": round(cum_rev, 2),
        })

    total_rev  = float(sum(rev))
    arb_rev    = float(sum(_arr(result.get("arb_revenue_aud"), n)))
    fcas_rev   = float(sum(_arr(result.get("fcas_revenue_aud"), n)))
    dispatched = sum(1 for iv in intervals if iv["action"] == "discharge")
    charged    = sum(1 for iv in intervals if iv["action"] == "charge")
    soc_vals   = [iv["soc_pct"] for iv in intervals]

    return {
        "strategy_id":   active_strategy_id,
        "strategy_name": active_strategy_name,
        "intervals": intervals,
        "summary": {
            "total_revenue_aud": round(total_rev, 2),
            "arb_revenue_aud": round(arb_rev, 2),
            "fcas_revenue_aud": round(fcas_rev, 2),
            "intervals_dispatched": dispatched,
            "intervals_charged": charged,
            "peak_soc_pct": round(max(soc_vals), 1) if soc_vals else 0,
            "min_soc_pct": round(min(soc_vals), 1) if soc_vals else 0,
        },
    }


def run_dispatch_compare(
    prices_df: pd.DataFrame,
    strategy_ids: list[str],
    config: Optional[BESSConfig] = None,
) -> dict:
    """
    Run multiple named strategies against the same price data and return
    side-by-side results.

    Args:
        prices_df:    Shared price + FCAS DataFrame.
        strategy_ids: List of strategy IDs to compare (from dispatch_strategies.py).
        config:       Shared BESS hardware config (power, energy, region, etc.).
                      Strategy-specific algorithm params override relevant fields.

    Returns:
        {
          "strategies_compared": [...],        # list of strategy ids run
          "results": {
              "<strategy_id>": {
                  "strategy_id", "strategy_name", "summary", "intervals"
              }, ...
          },
          "comparison": {
              "<strategy_id>": {               # summary-only for quick comparison table
                  "strategy_name": str,
                  "total_revenue_aud": float,
                  "arb_revenue_aud": float,
                  "fcas_revenue_aud": float,
                  "intervals_dispatched": int,
              }, ...
          }
        }
    """
    results = {}
    for sid in strategy_ids:
        cfg_copy = BESSConfig(
            bess_power_mw=config.bess_power_mw if config else 5.0,
            bess_energy_mwh=config.bess_energy_mwh if config else 10.0,
            dc_coupled=config.dc_coupled if config else True,
            grid_connected=config.grid_connected if config else True,
            nem_region=config.nem_region if config else "VIC1",
            export_capacity_mw=config.export_capacity_mw if config else None,
            adaptive_seed_charge_aud=config.adaptive_seed_charge_aud if config else 50.0,
            adaptive_seed_discharge_aud=config.adaptive_seed_discharge_aud if config else 100.0,
        )
        results[sid] = run_dispatch(prices_df, cfg_copy, strategy_id=sid)

    comparison = {
        sid: {
            "strategy_name":       r["strategy_name"],
            "total_revenue_aud":   r["summary"]["total_revenue_aud"],
            "arb_revenue_aud":     r["summary"]["arb_revenue_aud"],
            "fcas_revenue_aud":    r["summary"]["fcas_revenue_aud"],
            "intervals_dispatched": r["summary"]["intervals_dispatched"],
            "intervals_charged":   r["summary"]["intervals_charged"],
        }
        for sid, r in results.items()
    }

    # Rank strategies by total revenue
    ranked = sorted(comparison.items(), key=lambda x: x[1]["total_revenue_aud"], reverse=True)
    for rank_i, (sid, _) in enumerate(ranked, start=1):
        comparison[sid]["rank"] = rank_i

    return {
        "strategies_compared": strategy_ids,
        "comparison": comparison,
        "results": results,
    }


def run_backcast(
    region: str = "VIC1",
    days: int = 365,
    strategy_ids: Optional[list] = None,
    config: Optional[BESSConfig] = None,
) -> dict:
    """
    Simulate each dispatch strategy over historical AEMO spot prices.

    Uses AEMO MMSDM DISPATCHPRICE archive (spot prices only — FCAS columns
    are not present in that file so FCAS revenue will show $0 in backcast).
    The live Digital Twin runs against real-time prices that include all 10
    FCAS columns, so co-optimised FCAS revenue is captured there.

    Returns per-strategy monthly breakdown + YTD totals for Jan 1 → today.
    """
    from datetime import date as _date

    try:
        from nem.aemo_fetch import fetch_historical_prices
    except ImportError:
        from aemo_fetch import fetch_historical_prices  # type: ignore

    try:
        from nem.dispatch_strategies import STRATEGIES
    except ImportError:
        try:
            from dispatch_strategies import STRATEGIES  # type: ignore
        except ImportError:
            STRATEGIES = {}

    if strategy_ids is None or strategy_ids == ["all"]:
        strategy_ids = list(STRATEGIES.keys()) if STRATEGIES else [
            "co_optimised_revenue_max", "arb_only", "fcas_only",
        ]

    if config is None:
        config = BESSConfig(nem_region=region)

    _LOG.info("Fetching %d days of historical prices for %s ...", days, region)
    hist_df = fetch_historical_prices(region=region, days=days)
    if hist_df.empty:
        return {"error": "No historical price data available", "strategies": {}}

    ytd_start = pd.Timestamp(_date.today().year, 1, 1)
    results: dict = {}

    for sid in strategy_ids:
        cfg_copy = BESSConfig(
            bess_power_mw=config.bess_power_mw,
            bess_energy_mwh=config.bess_energy_mwh,
            nem_region=region,
            dc_coupled=config.dc_coupled,
            grid_connected=config.grid_connected,
            export_capacity_mw=config.export_capacity_mw,
        )
        dispatch = run_dispatch(hist_df, cfg_copy, strategy_id=sid)
        intervals = dispatch.get("intervals", [])

        # Aggregate by month
        monthly: dict = {}
        ytd_revenue = 0.0
        for iv in intervals:
            try:
                ts  = pd.Timestamp(iv["timestamp"])
                key = ts.strftime("%Y-%m")
                if key not in monthly:
                    monthly[key] = {"revenue": 0.0, "discharge_intervals": 0, "charge_intervals": 0}
                rev = iv.get("interval_revenue_aud", 0.0)
                monthly[key]["revenue"] += rev
                if iv.get("action") == "discharge":
                    monthly[key]["discharge_intervals"] += 1
                elif iv.get("action") == "charge":
                    monthly[key]["charge_intervals"] += 1
                if ts >= ytd_start:
                    ytd_revenue += rev
            except Exception:
                continue

        monthly_list = [
            {
                "month": k,
                "revenue_aud":          round(v["revenue"], 2),
                "discharge_intervals":  v["discharge_intervals"],
                "charge_intervals":     v["charge_intervals"],
            }
            for k, v in sorted(monthly.items())
        ]

        # Annual revenue: sum over twelve calendar months of the request window
        annual_start = pd.Timestamp(_date.today().year, 1, 1)
        annual_end   = pd.Timestamp(_date.today().year, 12, 31, 23, 59, 59)
        annual_revenue = sum(
            iv.get("interval_revenue_aud", 0.0)
            for iv in intervals
            if annual_start <= pd.Timestamp(iv["timestamp"]) <= annual_end
        )

        results[sid] = {
            "strategy_name":      dispatch.get("strategy_name", sid),
            "strategy_id":        sid,
            "monthly":            monthly_list,
            "ytd_revenue_aud":    round(ytd_revenue, 2),
            "annual_revenue_aud": round(annual_revenue, 2),
            "total_revenue_aud":  dispatch["summary"]["total_revenue_aud"],
            "arb_revenue_aud":    dispatch["summary"]["arb_revenue_aud"],
            "fcas_revenue_aud":   dispatch["summary"]["fcas_revenue_aud"],
            "fcas_note":          "FCAS revenue = $0 in backcast (spot-price-only "
                                  "MMSDM archive). Live Digital Twin captures real FCAS.",
        }

    return {
        "region":       region,
        "days":         days,
        "ytd_year":     _date.today().year,
        "strategies":   results,
    }


def _arr(v, n: int) -> list:
    if v is None:
        return [0.0] * n
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, list):
        return v
    return [float(v)] * n


def _empty_result() -> dict:
    return {
        "intervals": [],
        "summary": {
            "total_revenue_aud": 0,
            "arb_revenue_aud": 0,
            "fcas_revenue_aud": 0,
            "intervals_dispatched": 0,
            "intervals_charged": 0,
            "peak_soc_pct": 0,
            "min_soc_pct": 0,
        },
    }
