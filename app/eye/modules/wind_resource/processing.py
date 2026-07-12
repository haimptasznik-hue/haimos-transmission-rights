"""
Processing — clean, validate, and summarise wind data.
"""
import numpy as np
import pandas as pd


def validate(df, ws_col="ws10"):
    """Basic wind data validation. Returns (df_clean, issues_list)."""
    issues = []

    # Negative wind speeds
    neg = (df[ws_col] < 0).sum()
    if neg:
        issues.append(f"WARNING: {neg} negative wind speed values — set to 0")
        df[ws_col] = df[ws_col].clip(lower=0)

    # Unrealistic highs (>60 m/s extreme)
    extreme = (df[ws_col] > 60).sum()
    if extreme:
        issues.append(f"WARNING: {extreme} wind speed values > 60 m/s flagged")

    # Timestamp continuity
    if hasattr(df.index, "freq") and df.index.freq is None:
        gaps = df.index.to_series().diff().dropna()
        expected = gaps.mode()[0]
        bad_gaps = (gaps != expected).sum()
        if bad_gaps:
            issues.append(f"WARNING: {bad_gaps} timestamp gaps detected")

    # Missing data
    missing = df[ws_col].isna().sum()
    if missing:
        issues.append(f"WARNING: {missing} missing values in {ws_col}")
        df[ws_col] = df[ws_col].interpolate(method="time")

    return df, issues


def annual_summary(df, ws_col="ws10"):
    """Annual summary statistics."""
    ws = df[ws_col].dropna()
    return {
        "annual_mean_ms": round(ws.mean(), 3),
        "annual_median_ms": round(ws.median(), 3),
        "annual_max_ms": round(ws.max(), 3),
        "annual_p75_ms": round(ws.quantile(0.75), 3),
        "annual_p90_ms": round(ws.quantile(0.90), 3),
        "hours_total": len(ws),
        "hours_above_4ms": int((ws >= 4).sum()),
        "hours_above_6ms": int((ws >= 6).sum()),
        "hours_above_8ms": int((ws >= 8).sum()),
        "hours_above_10ms": int((ws >= 10).sum()),
    }


def monthly_summary(df, ws_col="ws10"):
    """Monthly mean wind speed."""
    df = df.copy()
    df["month"] = df.index.month
    return df.groupby("month")[ws_col].agg(["mean", "median", "max", "std"]).round(3)
