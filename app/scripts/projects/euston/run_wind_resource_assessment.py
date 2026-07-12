"""
Euston Wind Resource Assessment — Main Runner
Run: python scripts/projects/euston/run_wind_resource_assessment.py

Fallback mode: runs without ERA5 credentials using BOM Mildura synthetic proxy.
All outputs clearly labelled with source.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import pandas as pd
from datetime import date

from eye.modules.wind_resource.config import SITE, ALTITUDE_BANDS_M, EYE_WIND, RAW_VAULT, KITE_MODULE, EUSTON_REF, ERA5_CONFIG
from eye.modules.wind_resource.data_sources import generate_synthetic_hourly
from eye.modules.wind_resource.era5_loader import fetch_era5, load_era5_netcdf
from eye.modules.wind_resource.processing import validate, annual_summary, monthly_summary
from eye.modules.wind_resource.altitude_extrapolation import build_altitude_profile, wind_speed_threshold_table, monthly_altitude_summary
from eye.modules.wind_resource.storage import safe_save, safe_write
from eye.modules.wind_resource.reporting import wind_summary_report, metadata_yaml, assumptions_register, methodology_notes

VAULT = "/Users/haimptasznik/Desktop/HaimOS"

print("=" * 60)
print("EUSTON WIND RESOURCE ASSESSMENT")
print(f"Site: {SITE['site_name']} ({SITE['latitude']}, {SITE['longitude']})")
print("=" * 60)

# ── 1. Load wind data ─────────────────────────────────────────────────────────
print("\n[1] Loading wind data...")
era5_path, era5_status = fetch_era5(ERA5_CONFIG, VAULT)
if era5_path and era5_status == "era5":
    df_hourly, source_label = load_era5_netcdf(era5_path, SITE["latitude"], SITE["longitude"])
    if df_hourly is not None:
        ref_col, ref_height = "ws10", 10
        print(f"    Source: ERA5 ✓")
    else:
        df_hourly = None
else:
    df_hourly = None

if df_hourly is None:
    print(f"    ERA5 unavailable ({era5_status}) — using BOM synthetic proxy (Mildura 076031)")
    df_raw = generate_synthetic_hourly(2015, 2024)
    ref_col, ref_height = "ws10", 10
    source_label = "synthetic_bom_proxy (Mildura 076031)"
    df_hourly = df_raw

# ── 2. Validate ───────────────────────────────────────────────────────────────
print("\n[2] Validating...")
df_hourly, issues = validate(df_hourly, ws_col=ref_col)
for issue in issues:
    print(f"    {issue}")
if not issues:
    print("    No issues found.")

# ── 3. Summaries ──────────────────────────────────────────────────────────────
print("\n[3] Calculating summaries...")
annual = annual_summary(df_hourly, ref_col)
monthly_df = monthly_summary(df_hourly, ref_col)
print(f"    Annual mean: {annual['annual_mean_ms']} m/s at {ref_height}m")
print(f"    Hours above 4 m/s: {annual['hours_above_4ms']:,}")
print(f"    Hours above 8 m/s: {annual['hours_above_8ms']:,}")

# ── 4. Altitude profile ───────────────────────────────────────────────────────
print("\n[4] Building altitude profile (10m–500m, power law alpha=0.14)...")
df_altitude = build_altitude_profile(df_hourly, ref_col, ref_height)
threshold_df = wind_speed_threshold_table(df_altitude)
monthly_alt_df = monthly_altitude_summary(df_altitude)
print(f"    Wind at 200m: {threshold_df.loc[threshold_df.altitude_m==200,'annual_mean_ms'].values[0]:.2f} m/s")
print(f"    Wind at 500m: {threshold_df.loc[threshold_df.altitude_m==500,'annual_mean_ms'].values[0]:.2f} m/s")

# ── 5. Save outputs ───────────────────────────────────────────────────────────
print("\n[5] Saving outputs...")
saved = []

# EYE project folder
p = f"{EYE_WIND}/raw/euston_hourly_wind_{ref_height}m_raw.csv"
safe_save(df_hourly[[ref_col, "source"]], p, "raw hourly"); saved.append(p)

p = f"{EYE_WIND}/processed/euston_hourly_wind_speed.csv"
safe_save(df_hourly[[ref_col]], p, "processed hourly"); saved.append(p)

p = f"{EYE_WIND}/processed/euston_altitude_wind_profile_10m_to_500m.csv"
safe_save(df_altitude, p, "altitude profile"); saved.append(p)

p = f"{EYE_WIND}/outputs/euston_wind_thresholds.csv"
safe_save(threshold_df, p, "thresholds"); saved.append(p)

p = f"{EYE_WIND}/outputs/euston_monthly_altitude_summary.csv"
safe_save(monthly_alt_df, p, "monthly altitude"); saved.append(p)

# Kite module vault
p = f"{EUSTON_REF}/euston_altitude_wind_profile_10m_to_500m.csv"
safe_save(df_altitude, p, "kite module altitude profile"); saved.append(p)

p = f"{EUSTON_REF}/euston_wind_thresholds.csv"
safe_save(threshold_df, p, "kite module thresholds"); saved.append(p)

# Raw vault
p = f"{RAW_VAULT}/processed/euston_hourly_wind_speed.csv"
safe_save(df_hourly[[ref_col]], p, "vault processed"); saved.append(p)

# ── 6. Write text outputs ─────────────────────────────────────────────────────
report = wind_summary_report(SITE, annual, monthly_df, threshold_df, source_label)
p = f"{EYE_WIND}/outputs/euston_wind_summary.md"
safe_write(report, p, "summary report"); saved.append(p)

meta = metadata_yaml(SITE, source_label, saved)
p = f"{RAW_VAULT}/metadata/euston_wind_metadata.yaml"
safe_write(meta, p, "metadata"); saved.append(p)

p = f"{KITE_MODULE}/assumptions_register.md"
safe_write(assumptions_register(), p, "assumptions register"); saved.append(p)

p = f"{KITE_MODULE}/methodology_notes.md"
safe_write(methodology_notes(), p, "methodology notes"); saved.append(p)

# ── 7. Print summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ASSESSMENT COMPLETE")
print(f"Source: {source_label}")
print(f"Files saved: {len(saved)}")
print(f"\nKey results (10m surface):")
print(f"  Annual mean: {annual['annual_mean_ms']} m/s")
print(f"  Hours above 4 m/s: {annual['hours_above_4ms']:,} ({annual['hours_above_4ms']/annual['hours_total']*100:.0f}%)")
print(f"  Hours above 8 m/s: {annual['hours_above_8ms']:,} ({annual['hours_above_8ms']/annual['hours_total']*100:.0f}%)")
print(f"\nAt SkySails operating altitude (200m, power law):")
ws200 = threshold_df.loc[threshold_df.altitude_m==200,"annual_mean_ms"].values[0]
hrs200_8 = threshold_df.loc[threshold_df.altitude_m==200,"hrs_above_8ms"].values[0]
print(f"  Annual mean: {ws200} m/s")
print(f"  Hours above 8 m/s: {hrs200_8:,} ({hrs200_8/annual['hours_total']*100:.0f}%)")
print(f"\n⚠  All altitude data is EXTRAPOLATED (power law alpha=0.14)")
print(f"   Replace with ERA5 or SkySails site assessment for production modelling.")
print("=" * 60)
