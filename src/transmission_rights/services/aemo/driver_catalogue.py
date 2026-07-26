"""Phase 5B – Driver Catalogue

Registry of all candidate explanatory variables for Settlement Residue / SRA payouts.

Each entry records:
  - group: variable category
  - variable: specific variable name
  - description: what it measures
  - in_repo: whether data exists in this repo
  - source_file: path if in_repo is True
  - publish_timing: when AEMO publishes (lag from settlement)
  - historical_availability: how far back it goes
  - latency_days: publication latency in days
  - point_in_time_safe: usable before auction decision date
  - confidence: HIGH / MEDIUM / LOW (data quality)
  - engineering_plausibility: HIGH / MEDIUM / LOW
  - priority_to_acquire: HIGH / MEDIUM / LOW / NA
  - aemo_data_url: where to source externally
  - notes: any additional context

STATUS CODES (in_repo):
  AVAILABLE   – present and usable in this repo
  PARTIAL     – exists but incomplete (e.g. only recent quarters)
  MISSING     – not present; must be sourced externally
  DERIVABLE   – can be computed from existing data
"""
from __future__ import annotations

import pandas as pd

# ── Catalogue definition ──────────────────────────────────────────────────────

DRIVER_CATALOGUE: list[dict] = [

    # ── MARKET ───────────────────────────────────────────────────────────────

    {
        "group": "Market",
        "variable": "auction_clearing_price",
        "description": "SRA auction clearing price per unit by corridor and tranche",
        "in_repo": "AVAILABLE",
        "source_file": "data/derived/sra/sra_auction_results.csv",
        "publish_timing": "Day of auction",
        "historical_availability": "C2018Q3+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "NA",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-data-nemweb/reports/current-reports/srres",
        "notes": "Direct market price; available at bid time. Core feature.",
    },
    {
        "group": "Market",
        "variable": "auction_clearing_price_momentum",
        "description": "Quarter-on-quarter change in clearing price for same corridor/tranche",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/sra_auction_results.csv",
        "publish_timing": "Day of auction",
        "historical_availability": "C2018Q3+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "NA",
        "aemo_data_url": "",
        "notes": "Derivable from existing clearing price series. Captures price trend signal.",
    },
    {
        "group": "Market",
        "variable": "auction_fill_probability_trend",
        "description": "Quarter-on-quarter change in fill probability for same corridor/tranche",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/alpha_database.csv",
        "publish_timing": "Day of auction",
        "historical_availability": "C2018Q3+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "NA",
        "aemo_data_url": "",
        "notes": "Fill probability encodes market demand for transmission rights at a price.",
    },
    {
        "group": "Market",
        "variable": "tranche_price_gradient",
        "description": "Steepness of clearing price curve across tranches within a quarter-corridor",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/sra_auction_results.csv",
        "publish_timing": "Day of auction",
        "historical_availability": "C2018Q3+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "NA",
        "aemo_data_url": "",
        "notes": "Steep curves imply informed bidding / constrained capacity. Potentially a strong regime signal.",
    },
    {
        "group": "Market",
        "variable": "regional_reference_price_rrp",
        "description": "5-min and trading interval RRP for each NEM region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Real-time (5-min); historical via MMS",
        "historical_availability": "1998+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "DISPATCHPRICE table. Key driver: price spread between regions determines interconnector shadow value.",
    },
    {
        "group": "Market",
        "variable": "regional_price_spread",
        "description": "RRP differential between corridor endpoints (e.g. NSW1 - VIC1)",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Real-time; quarterly aggregate derivable",
        "historical_availability": "1998+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "The single most important driver of SRA settlement residue. Large price spread = large residue.",
    },
    {
        "group": "Market",
        "variable": "price_spread_volatility",
        "description": "Standard deviation of regional price spread within a quarter",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Quarterly aggregate; computed from DISPATCHPRICE",
        "historical_availability": "1998+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "High volatility implies unpredictable congestion events; affects SRA payout distribution.",
    },
    {
        "group": "Market",
        "variable": "fcas_prices",
        "description": "Frequency Control Ancillary Services prices (raise/lower 6s/60s/5min/reg)",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Real-time; MMS archive",
        "historical_availability": "2001+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "FCAS prices spike during system stress events that often coincide with congestion.",
    },

    # ── GENERATION ───────────────────────────────────────────────────────────

    {
        "group": "Generation",
        "variable": "duid_generation",
        "description": "Per-unit dispatch output (MW) for each DUID in the NEM",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "5-min dispatch; MMS archive 4–5 months latency",
        "historical_availability": "1998+",
        "latency_days": 150,
        "point_in_time_safe": False,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "DISPATCHLOAD. Granular but large; quarterly aggregation by fuel type is more tractable.",
    },
    {
        "group": "Generation",
        "variable": "coal_generation_quarterly",
        "description": "Quarterly total coal-fired generation (GWh) per region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO Quarterly Energy Dynamics report",
        "historical_availability": "2009+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "Coal availability drives baseload pricing. Unplanned coal outages are a primary congestion driver.",
    },
    {
        "group": "Generation",
        "variable": "wind_generation_quarterly",
        "description": "Quarterly total wind generation (GWh) per region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO Quarterly Energy Dynamics",
        "historical_availability": "2009+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "High wind in SA/VIC reduces local prices; creates conditions for large V-SA price spreads.",
    },
    {
        "group": "Generation",
        "variable": "solar_generation_quarterly",
        "description": "Quarterly total solar generation (GWh) per region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO Quarterly Energy Dynamics",
        "historical_availability": "2014+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "Solar suppresses midday prices. As solar grows, price shape changes affect SRA settlement.",
    },
    {
        "group": "Generation",
        "variable": "hydro_generation_quarterly",
        "description": "Quarterly total hydro generation (GWh) — primarily Snowy, Tas",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO Quarterly Energy Dynamics",
        "historical_availability": "2009+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "Snowy hydro operations affect VIC1-NSW1 flows. Drought affects Tas-Vic interconnector.",
    },
    {
        "group": "Generation",
        "variable": "battery_dispatch_quarterly",
        "description": "Quarterly total battery charge/discharge (GWh) per region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO Quarterly Energy Dynamics",
        "historical_availability": "2017+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "Growing fleet. Battery arbitrage can reduce price spread volatility or amplify it.",
    },

    # ── TRANSMISSION ─────────────────────────────────────────────────────────

    {
        "group": "Transmission",
        "variable": "interconnector_flow_quarterly",
        "description": "Quarterly average / peak / minimum interconnector flow (MW)",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "MMS archive; DISPATCHINTERCONNECTORRES",
        "historical_availability": "2000+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "Most direct physical driver. Flow at or near limit = binding constraint = settlement residue.",
    },
    {
        "group": "Transmission",
        "variable": "interconnector_utilisation_pct",
        "description": "Fraction of time interconnector was at or near physical limit",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Derivable from DISPATCHINTERCONNECTORRES",
        "historical_availability": "2000+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "High utilisation % directly explains when SRA holders collect. Core causal variable.",
    },
    {
        "group": "Transmission",
        "variable": "constraint_binding_frequency",
        "description": "Number of dispatch intervals per quarter where a constraint was binding on each interconnector",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "DISPATCHCONSTRAINT; MMS archive",
        "historical_availability": "2000+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "Direct cause of congestion rent. Binding constraint frequency is strongly correlated with SRA payout.",
    },
    {
        "group": "Transmission",
        "variable": "flow_reversal_count",
        "description": "Number of times flow direction reversed within a quarter",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Derivable from DISPATCHINTERCONNECTORRES",
        "historical_availability": "2000+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/",
        "notes": "Frequent reversals indicate unstable price spread; relevant for SRA direction mismatch.",
    },
    {
        "group": "Transmission",
        "variable": "network_outage_days",
        "description": "Number of days per quarter with planned or forced network outages per corridor",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO network outage register; MT PASA",
        "historical_availability": "2010+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/network-outage-schedule",
        "notes": "Outages reduce physical capacity → higher constraint frequency → higher SRA payout.",
    },
    {
        "group": "Transmission",
        "variable": "setirsurplus_quarterly",
        "description": "Total quarterly SETIRSURPLUS (settlement residue AUD) per corridor-direction",
        "in_repo": "AVAILABLE",
        "source_file": "data/derived/irsr/setirsurplus_quarterly_all.csv",
        "publish_timing": "~6 months after quarter end",
        "historical_availability": "C2020Q2+",
        "latency_days": 180,
        "point_in_time_safe": False,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "NA",
        "notes": "The target variable itself. Available for closed quarters only. Not usable as a predictor (lookahead risk).",
    },

    # ── WEATHER ───────────────────────────────────────────────────────────────

    {
        "group": "Weather",
        "variable": "temperature_anomaly_quarterly",
        "description": "Quarterly average temperature anomaly from long-run mean, per NEM region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "BOM Climate Data Online",
        "historical_availability": "1950+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "http://www.bom.gov.au/climate/data/",
        "notes": "Extreme heat → high demand → price spikes. Q1/Q4 heatwaves strongly associated with VIC1-SA residue.",
    },
    {
        "group": "Weather",
        "variable": "wind_resource_index",
        "description": "Quarterly wind capacity factor proxy (actual wind / installed wind capacity)",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Derivable from AEMO Generation & AEMO QED",
        "historical_availability": "2009+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem",
        "notes": "Wind-rich quarters in SA reduce SA prices → widen V-SA spread. Critical for V-SA corridor.",
    },
    {
        "group": "Weather",
        "variable": "rainfall_and_hydrology",
        "description": "Quarterly rainfall index for hydro catchments (Snowy, Hume, Dartmouth, Gordon)",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "BOM; Snowy Hydro reports",
        "historical_availability": "1950+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "MEDIUM",
        "aemo_data_url": "http://www.bom.gov.au/hydrology/",
        "notes": "Drought conditions reduce hydro availability, affect VIC1-NSW1 corridor flow patterns.",
    },

    # ── SEASONALITY (DERIVABLE) ───────────────────────────────────────────────

    {
        "group": "Seasonality",
        "variable": "quarter_number",
        "description": "Calendar quarter number (1–4)",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/alpha_database.csv",
        "publish_timing": "Known at auction",
        "historical_availability": "C2018Q3+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "NA",
        "notes": "Q1 (Jan–Mar) and Q4 (Oct–Dec) are summer/heatwave seasons in southern NEM.",
    },
    {
        "group": "Seasonality",
        "variable": "years_elapsed_since_market_start",
        "description": "Years since NEM start — captures structural trend in renewable penetration",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/alpha_database.csv",
        "publish_timing": "Known at auction",
        "historical_availability": "All",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "NA",
        "notes": "Renewable penetration has risen monotonically; time index proxies structural regime shift.",
    },

    # ── STRUCTURAL BREAKS ────────────────────────────────────────────────────

    {
        "group": "Structural",
        "variable": "renewable_penetration_regime",
        "description": "Categorical regime: low / medium / high renewable share in each region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Derivable from AEMO QED (30d lag)",
        "historical_availability": "2009+",
        "latency_days": 30,
        "point_in_time_safe": True,
        "confidence": "MEDIUM",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "notes": "Post-2021 VIC/SA renewable penetration meaningfully changed price spread dynamics.",
    },
    {
        "group": "Structural",
        "variable": "major_coal_retirement",
        "description": "Binary flag: quarter in which a major coal unit retired (>500MW) in a region",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "Public knowledge; AEMO Generation Information",
        "historical_availability": "2012+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "aemo_data_url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/planning-and-forecasting/generation-information",
        "notes": "Hazelwood (2017), Liddell (2023), Eraring (2025 planned). Each creates a structural break.",
    },
    {
        "group": "Structural",
        "variable": "transmission_augmentation",
        "description": "Binary flag: quarter in which major transmission augmentation became operational",
        "in_repo": "MISSING",
        "source_file": "",
        "publish_timing": "AEMO ISP; publicly known",
        "historical_availability": "2010+",
        "latency_days": 0,
        "point_in_time_safe": True,
        "confidence": "HIGH",
        "engineering_plausibility": "HIGH",
        "priority_to_acquire": "HIGH",
        "notes": "VNI (C2021), EnergyConnect (post-2026). Each increases corridor capacity, reducing congestion rent.",
    },
    {
        "group": "Structural",
        "variable": "payout_regime_break",
        "description": "Detected structural break in settlement payout time series (CUSUM method)",
        "in_repo": "DERIVABLE",
        "source_file": "data/derived/sra/sra_payout_history.csv",
        "publish_timing": "Post-settlement; known after each quarter",
        "historical_availability": "C2020Q2+",
        "latency_days": 180,
        "point_in_time_safe": False,
        "confidence": "MEDIUM",
        "engineering_plausibility": "MEDIUM",
        "priority_to_acquire": "NA",
        "notes": "Can detect regime shifts in the payout series without knowing the cause. Not usable for prediction.",
    },
]


def build_catalogue_df() -> pd.DataFrame:
    """Return the driver catalogue as a DataFrame."""
    return pd.DataFrame(DRIVER_CATALOGUE)


def available_drivers(df: pd.DataFrame) -> pd.DataFrame:
    """Return only drivers with data available or derivable in repo."""
    return df[df["in_repo"].isin(["AVAILABLE", "DERIVABLE"])].copy()


def missing_drivers_by_priority(df: pd.DataFrame) -> pd.DataFrame:
    """Return missing drivers ranked by acquisition priority."""
    missing = df[df["in_repo"] == "MISSING"].copy()
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    missing["_sort"] = missing["priority_to_acquire"].map(priority_order).fillna(9)
    return missing.sort_values("_sort").drop(columns=["_sort"])


def data_acquisition_report(df: pd.DataFrame) -> str:
    """Generate a plain-text data acquisition brief."""
    missing = missing_drivers_by_priority(df)
    available = available_drivers(df)
    lines = [
        "# Phase 5B – Data Acquisition Brief",
        "",
        f"## Summary",
        f"- Total candidate drivers catalogued: {len(df)}",
        f"- Available / derivable in repo: {len(available)}",
        f"- Missing (require external sourcing): {len(missing)}",
        "",
        "## Available in repo",
        "| Variable | Source | PIT-safe |",
        "|---|---|---|",
    ]
    for _, row in available.iterrows():
        lines.append(f"| {row['variable']} | {row['source_file'] or 'derivable'} | {'✅' if row['point_in_time_safe'] else '❌'} |")

    lines += [
        "",
        "## High-priority external data to acquire",
        "| Variable | Group | Source URL |",
        "|---|---|---|",
    ]
    for _, row in missing[missing["priority_to_acquire"] == "HIGH"].iterrows():
        lines.append(f"| {row['variable']} | {row['group']} | {row['aemo_data_url'] or 'see notes'} |")

    lines += [
        "",
        "## Engineering assessment",
        "- **Most likely dominant drivers (not yet in repo):**",
        "  1. Regional price spread (RRP differential between corridor endpoints)",
        "  2. Interconnector utilisation and constraint binding frequency",
        "  3. Regional renewable penetration regime (wind in SA, solar in QLD/NSW)",
        "  4. Temperature anomaly (heatwave events drive demand spikes)",
        "  5. Major coal retirement flags (structural breaks in baseload pricing)",
        "",
        "- **Available in repo today:**",
        "  - Auction clearing price momentum",
        "  - Tranche price gradient (steepness of clearing curve)",
        "  - Fill probability trend",
        "  - CUSUM structural break detection on payout series",
        "  - Quarterly and seasonal indices",
        "",
        "- **Conclusion:** The variables most likely to explain settlement residue",
        "  are ALL missing from this repo. The correlation discovery engine can",
        "  quantify the limits of in-repo data, confirm the seasonal benchmark",
        "  is near-optimal for available data, and produce a prioritised acquisition",
        "  roadmap for the data that would enable a genuinely causal model.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    df = build_catalogue_df()
    print(data_acquisition_report(df))
