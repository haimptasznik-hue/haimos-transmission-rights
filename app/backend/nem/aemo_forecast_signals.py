"""
aemo_forecast_signals.py — Dynamic AEMO market signal engine for the Solar Controller.

Builds per-interval forward-looking price signals that the BESS+solar dispatch
engine uses to make smarter solar allocation decisions:

  • stored_energy_value_per_mwh   — dynamic value of storing free solar now
                                     (based on expected future discharge price)
  • price_trend_signal            — short-horizon price direction (+1 rising, −1 falling)
  • negative_price_ahead          — True when forecast shows upcoming negative price
  • event_flag                    — contingency event detected (price spike / req jump)
  • volatility_index              — rolling stddev of forward prices (high = opportunity)

Data hierarchy (best → worst):
  1. AEMO P5MIN forecast (5-min granularity, ~1h horizon)   [live only]
  2. AEMO Pre-dispatch (30-min, ~36h horizon)               [live only]
  3. Historical intraday profile from master table           [always available]
  4. Static thresholds (charge/discharge)                    [fallback]

For the pre-computed dispatch table (historical years), we use (3) — the
same-day-ahead rolling price statistics from the price table itself,
because AEMO forecast APIs only serve real-time data.

Note: "forecast" in this module refers to intraday price signals used by
the dispatch engine, NOT the multi-year Financial Forecast.

Output
------
A numpy array of shape (n_intervals,) containing the per-interval
stored-energy value in $/MWh, plus auxiliary signal arrays.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

_LOG = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
#  1. Historical forward-looking signals from the master table
# ─────────────────────────────────────────────────────────────────────────

def build_historical_price_signals(
    spot_prices: np.ndarray,
    *,
    lookahead_intervals: int = 36,       # 3 hours forward (36 × 5 min)
    lookback_intervals: int = 12,        # 1 hour backward for volatility
    discharge_threshold: float = 100.0,  # seed fallback only — replaced by adaptive percentiles
    charge_threshold: float = 50.0,      # seed fallback only — replaced by adaptive percentiles
    roundtrip_eff: float = 0.90,
    trend_flat_band: float = 5.0,        # $/MWh — changes within band are "flat"
    trend_normalisation: float = 50.0,   # $/MWh — delta at which trend saturates ±1.0
    **kwargs,
) -> dict[str, np.ndarray]:
    """
    Compute forward-looking price signals from a complete spot price series.

    This is used for pre-computed dispatch on historical data where we
    don't have AEMO P5MIN/pre-dispatch forecasts, but we DO have the
    actual future prices (perfect foresight within the lookahead window).

    In production use, this simulates what a sophisticated BESS controller
    would know from AEMO's pre-dispatch/P5MIN forecasts plus its own
    price models — the lookahead window is deliberately limited to keep
    the advantage realistic.

    Parameters
    ----------
    spot_prices : np.ndarray
        Full year spot price series ($/MWh), one value per 5-min interval.
    lookahead_intervals : int
        How many future intervals to consider.  Default 36 = 3 hours,
        which matches the practical horizon of AEMO P5MIN + pre-dispatch.
    lookback_intervals : int
        Lookback window for volatility calculation.
    discharge_threshold : float
        Static fallback discharge threshold ($/MWh).
    charge_threshold : float
        Static fallback charge threshold ($/MWh).
    roundtrip_eff : float
        Battery round-trip efficiency.
    trend_flat_band : float
        Price delta ($/MWh) within which trend is treated as flat (noise).
    trend_normalisation : float
        Price delta ($/MWh) at which the trend signal saturates at ±1.0.

    Returns
    -------
    dict with keys:
        stored_energy_value : np.ndarray  — $/MWh value of storing energy now
        price_trend         : np.ndarray  — +1 rising, 0 flat, −1 falling
        neg_price_ahead     : np.ndarray  — bool, True if any future interval is negative
        volatility          : np.ndarray  — rolling stddev of forward prices
        forward_max_price   : np.ndarray  — max price in lookahead window
        forward_min_price   : np.ndarray  — min price in lookahead window
        forward_mean_price  : np.ndarray  — mean price in lookahead window
    """
    n = len(spot_prices)
    prices = np.asarray(spot_prices, dtype=np.float64)

    # Pre-allocate output arrays
    stored_energy_value = np.zeros(n, dtype=np.float64)
    price_trend = np.zeros(n, dtype=np.float64)
    neg_price_ahead = np.zeros(n, dtype=bool)
    volatility = np.zeros(n, dtype=np.float64)
    forward_max = np.zeros(n, dtype=np.float64)
    forward_min = np.zeros(n, dtype=np.float64)
    forward_mean = np.zeros(n, dtype=np.float64)
    adaptive_discharge = np.zeros(n, dtype=np.float64)
    adaptive_charge = np.zeros(n, dtype=np.float64)

    # Adaptive threshold config (from kwargs or sensible defaults)
    discharge_pctile = kwargs.get("adaptive_discharge_percentile", 75)
    charge_pctile = kwargs.get("adaptive_charge_percentile", 25)
    backcast_intervals = kwargs.get("adaptive_backcast_intervals", 288)  # 24h

    # Static fallback value
    static_value = max(0.0, (discharge_threshold + charge_threshold) / 2.0)

    for i in range(n):
        # ── Forward window ──────────────────────────────────────────
        fwd_end = min(i + lookahead_intervals + 1, n)
        fwd_slice = prices[i + 1 : fwd_end] if i + 1 < n else np.array([])

        if len(fwd_slice) > 0:
            fwd_max = float(np.nanmax(fwd_slice))
            fwd_min = float(np.nanmin(fwd_slice))
            fwd_mean = float(np.nanmean(fwd_slice))

            forward_max[i] = fwd_max
            forward_min[i] = fwd_min
            forward_mean[i] = fwd_mean

            # Stored energy value = expected discharge price × RTE
            # Use the max price in the lookahead window as the expected
            # discharge price (BESS controller would target the peak).
            # Discount by RTE to reflect energy lost in round-trip.
            stored_energy_value[i] = max(0.0, fwd_max * roundtrip_eff)

            # Price trend: compare forward mean to current price
            current = prices[i]
            if not np.isnan(current) and not np.isnan(fwd_mean):
                delta = fwd_mean - current
                if abs(delta) < trend_flat_band:
                    price_trend[i] = 0.0    # flat (within noise band)
                elif delta > 0:
                    price_trend[i] = min(1.0, delta / trend_normalisation)   # normalised rising
                else:
                    price_trend[i] = max(-1.0, delta / trend_normalisation)  # normalised falling

            # Negative price ahead
            neg_price_ahead[i] = bool(fwd_min < 0)
        else:
            # End of series — use static fallback
            stored_energy_value[i] = static_value
            forward_max[i] = prices[i] if not np.isnan(prices[i]) else static_value
            forward_min[i] = prices[i] if not np.isnan(prices[i]) else 0.0
            forward_mean[i] = prices[i] if not np.isnan(prices[i]) else static_value

        # ── Backward window (volatility + adaptive charge threshold) ─
        back_start = max(0, i - lookback_intervals)
        back_slice = prices[back_start : i + 1]
        if len(back_slice) > 1:
            volatility[i] = float(np.nanstd(back_slice))
        else:
            volatility[i] = 0.0

        # ── Adaptive thresholds ─────────────────────────────────────
        # Discharge: P75 of forward window — "discharge when price is
        #   in the top quartile of what's coming".
        if len(fwd_slice) > 2:
            adaptive_discharge[i] = float(np.nanpercentile(fwd_slice, discharge_pctile))
        else:
            adaptive_discharge[i] = discharge_threshold  # fallback

        # Charge: P25 of extended backward window (24h) — "charge when
        #   price is cheap relative to recent trading".
        back_ext_start = max(0, i - backcast_intervals)
        back_ext_slice = prices[back_ext_start : i + 1]
        if len(back_ext_slice) > 2:
            adaptive_charge[i] = float(np.nanpercentile(back_ext_slice, charge_pctile))
        else:
            adaptive_charge[i] = charge_threshold  # fallback

    return {
        "stored_energy_value": stored_energy_value,
        "price_trend": price_trend,
        "neg_price_ahead": neg_price_ahead,
        "volatility": volatility,
        "forward_max_price": forward_max,
        "forward_min_price": forward_min,
        "forward_mean_price": forward_mean,
        "adaptive_discharge_threshold": adaptive_discharge,
        "adaptive_charge_threshold": adaptive_charge,
    }


# ─────────────────────────────────────────────────────────────────────────
#  2. Event flag integration from NEM Data Pack v2
# ─────────────────────────────────────────────────────────────────────────

def load_event_flags_for_dispatch(
    region: str,
    year: int,
    n_intervals: int,
    timestamps: Optional[pd.DatetimeIndex] = None,
) -> np.ndarray:
    """
    Load contingency event flags (price spikes, requirement jumps) from
    the NEM Data Pack v2 event cache.

    Returns a boolean array of shape (n_intervals,).  True = event interval
    where FCAS prices are likely elevated → favour FCAS over solar export.
    """
    event_flags = np.zeros(n_intervals, dtype=bool)
    try:
        from src.nem_data_pack_v2.loaders import load_event_flags
        edf = load_event_flags(region, year)
        if edf.empty:
            return event_flags

        edf["timestamp"] = pd.to_datetime(edf["timestamp"], utc=True)

        if timestamps is not None:
            # Align to dispatch index
            merged = pd.DataFrame({"timestamp": timestamps}).merge(
                edf[["timestamp", "event_flag"]], on="timestamp", how="left"
            )
            event_flags = merged["event_flag"].fillna(False).values.astype(bool)
        else:
            # Assume 1:1 alignment by position
            flags = edf["event_flag"].values[:n_intervals]
            event_flags[:len(flags)] = flags

    except Exception as exc:
        _LOG.warning("Event flags not available for %s %d: %s", region, year, exc)

    return event_flags


# ─────────────────────────────────────────────────────────────────────────
#  3. Live AEMO forecast overlay (for real-time dispatch)
# ─────────────────────────────────────────────────────────────────────────

def fetch_live_aemo_forecast(region: str) -> Optional[pd.DataFrame]:
    """
    Fetch AEMO P5MIN + Pre-dispatch price forecasts for the given region.

    Returns a DataFrame with columns:
        timestamp  (NEM time, tz-naive)
        price_mwh  ($/MWh)
        source     ("p5min_5min" or "predispatch_30min")

    Returns None if fetching fails or no data is available.

    NOTE: This uses the same AEMO NEMWeb endpoints as the Live Wholesale
    tracker dashboard.  The P5MIN feed provides ~1 hour of 5-minute
    forecasts; Pre-dispatch extends to end of next trading day at 30-min
    resolution.
    """
    import requests
    import zipfile
    import io
    import re

    NEMWEB_P5MIN_URL = "https://nemweb.com.au/Reports/Current/P5_Reports/"
    NEMWEB_PREDISPATCH_URL = "https://nemweb.com.au/Reports/Current/PredispatchIS_Reports/"

    records_p5 = []
    records_pd = []

    # ── P5MIN (5-min resolution, ~1h ahead) ─────────────────────────
    try:
        resp = requests.get(NEMWEB_P5MIN_URL, timeout=15)
        resp.raise_for_status()
        zips = sorted(set(re.findall(r'(PUBLIC_P5MIN_[^"]*\.zip)', resp.text)))
        if zips:
            url = NEMWEB_P5MIN_URL + zips[-1]
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    if not name.upper().endswith(".CSV"):
                        continue
                    with zf.open(name) as f:
                        for raw_line in f:
                            line = raw_line.decode("utf-8", errors="ignore").strip()
                            if not line.startswith("D,P5MIN,REGIONSOLUTION,"):
                                continue
                            parts = line.split(",")
                            if len(parts) < 10:
                                continue
                            rid = parts[7].strip()
                            if rid != region:
                                continue
                            dt_str = parts[6].strip().strip('"')
                            rrp = parts[8].strip()
                            try:
                                records_p5.append({
                                    "timestamp": pd.to_datetime(dt_str),
                                    "price_mwh": float(rrp),
                                    "source": "p5min_5min",
                                })
                            except (ValueError, TypeError):
                                continue
    except Exception as exc:
        _LOG.warning("P5MIN fetch failed: %s", exc)

    # ── Pre-dispatch (30-min resolution, ~36h ahead) ─────────────────
    try:
        resp = requests.get(NEMWEB_PREDISPATCH_URL, timeout=15)
        resp.raise_for_status()
        zips = sorted(set(re.findall(r'(PUBLIC_PREDISPATCHIS_[^"]*\.zip)', resp.text)))
        if zips:
            url = NEMWEB_PREDISPATCH_URL + zips[-1]
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    if not name.upper().endswith(".CSV"):
                        continue
                    with zf.open(name) as f:
                        for raw_line in f:
                            line = raw_line.decode("utf-8", errors="ignore").strip()
                            if not line.startswith("D,PREDISPATCH,REGION_PRICES,"):
                                continue
                            parts = line.split(",")
                            if len(parts) < 29:
                                continue
                            rid = parts[6].strip()
                            if rid != region:
                                continue
                            rrp = parts[9].strip()
                            dt_str = parts[28].strip().strip('"')
                            try:
                                records_pd.append({
                                    "timestamp": pd.to_datetime(dt_str),
                                    "price_mwh": float(rrp),
                                    "source": "predispatch_30min",
                                })
                            except (ValueError, TypeError):
                                continue
    except Exception as exc:
        _LOG.warning("Pre-dispatch fetch failed: %s", exc)

    # ── Merge: P5MIN takes priority where both overlap ───────────────
    all_records = records_p5 + records_pd
    if not all_records:
        return None

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    df = df.sort_values("timestamp")

    # P5MIN priority: remove pre-dispatch rows that overlap with P5MIN
    if records_p5 and records_pd:
        p5_max = pd.to_datetime([r["timestamp"] for r in records_p5]).max()
        if hasattr(p5_max, 'tz_localize'):
            p5_max = p5_max.tz_localize(None)
        mask_keep = (df["source"] == "p5min_5min") | (df["timestamp"] > p5_max)
        df = df[mask_keep]

    df = df.drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    return df


def overlay_live_forecast_on_signals(
    signals: dict[str, np.ndarray],
    forecast_df: pd.DataFrame,
    dispatch_timestamps: pd.DatetimeIndex,
    roundtrip_eff: float = 0.90,
) -> dict[str, np.ndarray]:
    """
    Overlay live AEMO forecasts onto historical-based signals for intervals
    where forecast data is available.

    This improves the stored-energy-value and price-trend signals for the
    near-term future using AEMO's actual P5MIN and pre-dispatch forecasts.

    Parameters
    ----------
    signals : dict
        Output from build_historical_price_signals().
    forecast_df : pd.DataFrame
        Output from fetch_live_aemo_forecast().
    dispatch_timestamps : pd.DatetimeIndex
        The master table timestamps (NEM time, tz-naive).
    roundtrip_eff : float
        Battery round-trip efficiency.

    Returns
    -------
    Updated signals dict with live forecast overlaid where available.
    """
    if forecast_df is None or forecast_df.empty:
        return signals

    # Build a timestamp → forecast price lookup
    fc = forecast_df.set_index("timestamp")["price_mwh"].sort_index()

    # Strip timezone from dispatch timestamps if present
    ts = dispatch_timestamps
    if hasattr(ts, 'tz') and ts.tz is not None:
        ts = ts.tz_localize(None)

    for i, t in enumerate(ts):
        # Find forecast prices ahead of this interval
        future_mask = fc.index > t
        future_prices = fc[future_mask]
        if len(future_prices) < 2:
            continue

        fwd_max = float(future_prices.max())
        fwd_min = float(future_prices.min())
        fwd_mean = float(future_prices.mean())

        # Override stored energy value with live forecast peak
        signals["stored_energy_value"][i] = max(0.0, fwd_max * roundtrip_eff)
        signals["forward_max_price"][i] = fwd_max
        signals["forward_min_price"][i] = fwd_min
        signals["forward_mean_price"][i] = fwd_mean
        signals["neg_price_ahead"][i] = bool(fwd_min < 0)

        # Update price trend
        current = signals.get("_spot_prices", np.array([]))[i] if "_spot_prices" in signals else None
        if current is not None and not np.isnan(current):
            delta = fwd_mean - current
            if abs(delta) < 5.0:
                signals["price_trend"][i] = 0.0
            elif delta > 0:
                signals["price_trend"][i] = min(1.0, delta / 50.0)
            else:
                signals["price_trend"][i] = max(-1.0, delta / 50.0)

    return signals
