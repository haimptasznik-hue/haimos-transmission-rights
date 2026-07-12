"""
Altitude extrapolation using power law.
V_z = V_ref * (z / z_ref) ^ alpha
"""
import numpy as np
import pandas as pd
from .config import ALTITUDE_BANDS_M, WIND_SHEAR_ALPHA, WIND_SPEED_THRESHOLDS_MS


def extrapolate_to_altitude(v_ref, z_ref, z_target, alpha=None):
    """Extrapolate wind speed from reference height to target height."""
    if alpha is None:
        alpha = WIND_SHEAR_ALPHA["default"]
    return v_ref * (z_target / z_ref) ** alpha


def build_altitude_profile(df_hourly, ref_col, ref_height_m, alpha=None):
    """
    Given a DataFrame with hourly wind speed at ref_height_m,
    return a DataFrame with columns for each altitude band.
    Source label is embedded in each column name.
    """
    if alpha is None:
        alpha = WIND_SHEAR_ALPHA["default"]

    result = pd.DataFrame(index=df_hourly.index)
    result[f"ws_{ref_height_m}m_observed"] = df_hourly[ref_col]

    for z in ALTITUDE_BANDS_M:
        if z == ref_height_m:
            result[f"ws_{z}m"] = df_hourly[ref_col]
        else:
            result[f"ws_{z}m"] = extrapolate_to_altitude(
                df_hourly[ref_col], ref_height_m, z, alpha
            )
            if z > ref_height_m:
                result[f"ws_{z}m_note"] = "extrapolated_power_law"

    return result


def wind_speed_threshold_table(df_altitude_profile):
    """
    For each altitude band, calculate hours above each threshold per year.
    Returns a DataFrame: rows = altitude, cols = threshold m/s.
    """
    rows = []
    hours_total = len(df_altitude_profile)

    for z in ALTITUDE_BANDS_M:
        col = f"ws_{z}m"
        if col not in df_altitude_profile.columns:
            continue
        row = {"altitude_m": z}
        ws = df_altitude_profile[col]
        row["annual_mean_ms"] = round(ws.mean(), 2)
        row["annual_p50_ms"] = round(ws.median(), 2)
        for t in WIND_SPEED_THRESHOLDS_MS:
            hrs = int((ws >= t).sum())
            row[f"hrs_above_{t}ms"] = hrs
            row[f"pct_above_{t}ms"] = round(hrs / hours_total * 100, 1)
        rows.append(row)

    return pd.DataFrame(rows)


def monthly_altitude_summary(df_altitude_profile):
    """Monthly mean wind speed at each altitude band."""
    df = df_altitude_profile.copy()
    df["month"] = df.index.month
    cols = [f"ws_{z}m" for z in ALTITUDE_BANDS_M if f"ws_{z}m" in df.columns]
    return df.groupby("month")[cols].mean().round(2)
