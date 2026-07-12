"""
Wind Resource Module — Configuration
All site-specific and model parameters live here.
Do NOT embed API keys — use environment variables or credentials.yaml.
"""

# ── Site ──────────────────────────────────────────────────────────────────────
SITE = {
    "project_name": "AIIGP Kite Power — Euston",
    "site_name": "Euston",
    "latitude": -34.5667,
    "longitude": 142.7333,
    "elevation_m": 59,          # AHD approx (BOM Mildura reference)
    "terrain": "flat_open",     # flat irrigated agriculture, Sunraysia
}

# ── Altitude bands (kite power operating envelope) ───────────────────────────
ALTITUDE_BANDS_M = [10, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]

# ── Wind shear exponents (power law) — ASSUMPTIONS, require site validation ──
# alpha = (V_z / V_ref) = (z / z_ref) ^ alpha
WIND_SHEAR_ALPHA = {
    "low_open":    0.10,   # flat open / offshore-like — lower bound
    "neutral":     0.14,   # standard neutral atmosphere default
    "moderate":    0.20,   # moderate terrain roughness
    "default":     0.14,   # used unless overridden
}

# ── Kite operating thresholds (m/s) — for hours-above analysis ───────────────
WIND_SPEED_THRESHOLDS_MS = [4, 6, 8, 10, 12]

# ── Data source priority ──────────────────────────────────────────────────────
DATA_SOURCE_PRIORITY = ["era5", "gwa", "bom_synthetic", "fallback_synthetic"]

# ── ERA5 / CDS config (credentials via env or credentials.yaml) ──────────────
ERA5_CONFIG = {
    "dataset": "reanalysis-era5-single-levels",
    "variables": ["10m_u_component_of_wind", "10m_v_component_of_wind",
                  "100m_u_component_of_wind", "100m_v_component_of_wind"],
    "years": list(range(2015, 2025)),   # 10-year baseline
    "months": list(range(1, 13)),
    "area": [-34.0, 142.0, -35.5, 143.5],  # N/W/S/E bounding box
    "credentials_file": "06_Raw_Data/Wind/credentials.yaml",
}

# ── File paths ────────────────────────────────────────────────────────────────
import os
VAULT = "/Users/haimptasznik/Desktop/HaimOS"
EYE_WIND = os.path.join(VAULT, "02_EYE/projects/euston/wind")
RAW_VAULT = os.path.join(VAULT, "06_Raw_Data/Wind/Euston")
KITE_MODULE = os.path.join(VAULT, "02_Projects/Kite_Power_Module/wind_resource_foundation")
EUSTON_REF = os.path.join(KITE_MODULE, "Euston_reference_dataset")
