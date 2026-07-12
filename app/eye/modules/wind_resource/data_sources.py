"""
Fallback synthetic wind data generator.
Uses BOM Mildura climatology (station 076031) as reference.
Clearly marked as SYNTHETIC / ESTIMATED — not measured data.

BOM Mildura monthly mean wind speeds (10m, m/s) — approximate climatology:
Source: BOM Climate Data Online, station 076031, long-term averages.
These are surface 10m monthly means.
"""
import numpy as np
import pandas as pd

# BOM Mildura monthly mean wind speed at 10m (m/s) — approximate long-term averages
# ASSUMPTION: used as Euston proxy (25km separation, similar flat terrain)
BOM_MILDURA_MONTHLY_WS10 = {
    1: 4.2,  # Jan
    2: 3.9,  # Feb
    3: 3.7,  # Mar
    4: 3.4,  # Apr
    5: 3.2,  # May
    6: 3.0,  # Jun
    7: 3.3,  # Jul
    8: 3.6,  # Aug
    9: 3.9,  # Sep
    10: 4.1, # Oct
    11: 4.3, # Nov
    12: 4.4, # Dec
}


def generate_synthetic_hourly(year_start=2015, year_end=2024, seed=42):
    """
    Generate synthetic hourly wind speed time series based on BOM Mildura climatology.
    Uses Weibull distribution per month, with diurnal variation overlay.
    LABEL: synthetic / bom_proxy — not measured data.
    """
    np.random.seed(seed)
    periods = pd.date_range(
        start=f"{year_start}-01-01",
        end=f"{year_end}-12-31 23:00",
        freq="h"
    )

    ws = np.zeros(len(periods))
    for i, ts in enumerate(periods):
        # Monthly mean
        mean = BOM_MILDURA_MONTHLY_WS10[ts.month]
        # Weibull shape k=2 (common for inland Australia)
        scale = mean / 0.8862  # Gamma(1 + 1/k) for k=2
        base = np.random.weibull(2) * scale
        # Diurnal factor: winds higher midday, lower overnight
        hour_factor = 1.0 + 0.25 * np.sin(np.pi * (ts.hour - 6) / 12)
        ws[i] = max(0.0, base * hour_factor)

    df = pd.DataFrame({
        "ws10": ws,
        "source": "synthetic_bom_proxy",
    }, index=periods)
    df.index.name = "timestamp"
    return df
