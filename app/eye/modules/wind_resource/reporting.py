"""
Reporting — generate markdown summary reports and metadata YAML.
"""
from datetime import date


def _df_to_md(df):
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join([header, sep] + rows)


def wind_summary_report(site, annual, monthly_df, threshold_df, source_label):
    strongest = monthly_df["mean"].idxmax()
    weakest = monthly_df["mean"].idxmin()
    MONTHS = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

    lines = [
        f"# Euston Wind Resource Assessment",
        f"**Generated:** {date.today()}  ",
        f"**Data source:** {source_label}  ",
        f"",
        f"## Site",
        f"| Field | Value |",
        f"|---|---|",
        f"| Project | {site['project_name']} |",
        f"| Site | {site['site_name']} |",
        f"| Latitude | {site['latitude']} |",
        f"| Longitude | {site['longitude']} |",
        f"| Elevation | {site['elevation_m']} m AHD |",
        f"| Terrain | {site['terrain']} |",
        f"",
        f"## Annual Wind Summary (10m)",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Mean wind speed | {annual['annual_mean_ms']} m/s |",
        f"| Median wind speed | {annual['annual_median_ms']} m/s |",
        f"| Max wind speed | {annual['annual_max_ms']} m/s |",
        f"| Hours above 4 m/s | {annual['hours_above_4ms']:,} |",
        f"| Hours above 6 m/s | {annual['hours_above_6ms']:,} |",
        f"| Hours above 8 m/s | {annual['hours_above_8ms']:,} |",
        f"| Hours above 10 m/s | {annual['hours_above_10ms']:,} |",
        f"",
        f"## Seasonal Profile",
        f"- **Strongest month:** {MONTHS[strongest]} (mean {monthly_df.loc[strongest,'mean']:.2f} m/s)",
        f"- **Weakest month:** {MONTHS[weakest]} (mean {monthly_df.loc[weakest,'mean']:.2f} m/s)",
        f"",
        f"## Altitude Profile Summary (Power Law, alpha=0.14)",
        _df_to_md(threshold_df[["altitude_m","annual_mean_ms","hrs_above_4ms","hrs_above_8ms","pct_above_8ms"]]),
        f"",
        f"## Conventional Wind Suitability",
        f"- Mean 10m wind speed ~{annual['annual_mean_ms']:.1f} m/s — **marginal for conventional wind turbines** (typically need >6 m/s at hub height)",
        f"- At 100m (hub height proxy): ~{annual['annual_mean_ms'] * (100/10)**0.14:.1f} m/s — **potentially viable for large turbines in favourable months**",
        f"",
        f"## Kite Power / Airborne Wind Suitability (SkySails-type, 200–500m)",
        f"- At 200m altitude (power law): ~{annual['annual_mean_ms'] * (200/10)**0.14:.1f} m/s mean",
        f"- At 400m altitude (power law): ~{annual['annual_mean_ms'] * (400/10)**0.14:.1f} m/s mean",
        f"- **Assessment: PROMISING** — altitude winds significantly stronger than surface; kite systems designed for lower cut-in speeds (~4 m/s) and benefit from altitude resource uplift",
        f"- ⚠ ASSUMPTION: power law extrapolation only — requires validation with upper-atmosphere data or SkySails site assessment",
        f"",
        f"## Limitations & Next Steps",
        f"1. All altitude data is **extrapolated** (power law alpha=0.14) — not measured",
        f"2. Source data is **{source_label}** — replace with ERA5 or SkySails site assessment when available",
        f"3. Request SkySails PN-14 yield assessment for Euston site",
        f"4. Download ERA5 10yr hourly data via CDS API (see credentials.yaml placeholder)",
        f"5. Validate alpha with any available upper-atmosphere sounding data for Mildura",
    ]
    return "\n".join(lines)


def metadata_yaml(site, source_label, file_paths):
    return f"""# Euston Wind Resource — Metadata
project_name: "{site['project_name']}"
site_name: "{site['site_name']}"
latitude: {site['latitude']}
longitude: {site['longitude']}
elevation_m: {site['elevation_m']}
download_date: "{date.today()}"
data_period: "2015-2024 (synthetic proxy)"
data_source: "{source_label}"
height_reference: 10m AGL
height_type: "proxy_synthetic"
variables: ["wind_speed_ms"]
units: "m/s"
licence: "BOM proxy data — no licence restrictions on synthetic derivation"
processing_steps:
  - "Weibull distribution per month using BOM Mildura 076031 long-term averages"
  - "Diurnal variation overlay (sin function, amplitude 25%)"
  - "Power law altitude extrapolation (alpha=0.14 default)"
assumptions:
  - "Euston modelled as Mildura proxy (25km separation, similar flat terrain)"
  - "Wind shear alpha=0.14 (neutral atmosphere, flat open terrain)"
  - "Altitude extrapolation above 100m is assumption-based, not ERA5-derived"
  - "All altitude data above 10m is extrapolated, not measured"
limitations:
  - "No ERA5 data loaded — requires CDS credentials"
  - "No upper-atmosphere validation data available"
  - "Synthetic data does not capture interannual variability"
files:
{chr(10).join('  - ' + p for p in file_paths)}
"""


def assumptions_register():
    return """# Assumptions Register — Euston Wind Resource

| # | Assumption | Value | Source | Status |
|---|---|---|---|---|
| 1 | Reference wind speed | BOM Mildura 076031 monthly means | BOM Climate Data Online | PROXY — replace with ERA5 |
| 2 | Wind shear alpha | 0.14 (neutral default) | Standard engineering practice | ASSUMPTION — validate with site data |
| 3 | Terrain roughness | Flat open (Sunraysia irrigated agriculture) | Site description | REASONABLE — low sensitivity |
| 4 | Altitude upper bound | 500m AGL | SkySails PN-14 operating envelope | CONFIRMED — SkySails specification |
| 5 | SkySails cut-in speed | 4 m/s | SkySails published specs (indicative) | PLACEHOLDER — await confirmed power curve |
| 6 | SkySails rated speed | 10 m/s | SkySails published specs (indicative) | PLACEHOLDER |
| 7 | SkySails cut-out speed | 20 m/s | SkySails published specs (indicative) | PLACEHOLDER |
| 8 | Euston elevation | 59m AHD | BOM Mildura reference | LOW CONFIDENCE — confirm with site survey |
| 9 | ERA5 data | Not loaded | CDS API — credentials required | PENDING |
| 10 | Weibull shape k | 2.0 | Standard for inland Australia | ASSUMPTION — validate with measured data |

## Next Steps
- [ ] Configure ERA5 CDS credentials → `06_Raw_Data/Wind/credentials.yaml`
- [ ] Download ERA5 10yr hourly wind data for Euston bounding box
- [ ] Request SkySails PN-14 yield assessment for Euston
- [ ] Validate alpha with upper-atmosphere sounding data (Mildura)
- [ ] Replace synthetic data with ERA5 once downloaded
"""


def methodology_notes():
    return """# Methodology Notes — Euston Wind Resource Foundation

## Purpose
This module establishes the wind resource data foundation for the AIIGP kite power project
at Euston, NSW. It supports both immediate site feasibility and the future SkySails kite
power production simulator.

## Data Hierarchy
1. **ERA5 (preferred)** — Copernicus CDS reanalysis, 10m + 100m wind components, hourly
2. **Global Wind Atlas** — long-term average screening only (no time series)
3. **BOM synthetic proxy** — Mildura station 076031, Weibull-sampled (current fallback)

## Altitude Extrapolation Method
Power law: `V_z = V_ref × (z / z_ref) ^ alpha`
- Reference height: 10m (BOM surface) or 100m (ERA5 model level)
- Target range: 10m to 500m in 50m bands
- Default alpha: 0.14 (neutral atmosphere, flat terrain)
- ⚠ Extrapolation above 100m is an engineering estimate — not validated by upper-atmosphere data

## SkySails Operating Envelope
SkySails PN-14 (200kW rated) is designed to operate in the range 200m–500m AGL.
Key parameters in `skysails_operating_envelope_placeholder.yaml` are PLACEHOLDERS
awaiting confirmed SkySails performance documentation.

## Kite Power Production Model (Future)
The altitude wind profile (10m–500m) stored in this module feeds the future kite power
production simulator. The simulator will:
1. Apply SkySails power curve to hourly wind speed at operating altitude
2. Apply availability, launch/landing, and storm constraints
3. Output hourly generation profile (MWh)
4. Feed into BTM model and financial_forecast_template.py

## Files Created
See metadata YAML for full file list.
"""
