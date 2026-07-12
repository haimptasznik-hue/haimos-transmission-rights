"""
nna_map_module.py  —  Standalone NNA Opportunity Map + Leaderboard
====================================================================
A self-contained Streamlit component that renders the Network Non-Network
Alternative (NNA) opportunity map, leaderboard, and full investment workings.

DATA FRESHNESS
  Source data is from FY2024-25 DNSP System Limitation Reports (DAPRs/TAPRs).
  New reports are released each July.
  NEXT_UPDATE_DATE = 2027-07-01  ->  warning banner appears from that date.
  STALE_DATE       = 2028-07-01  ->  error banner; data is 2 years stale.

  When new reports drop, update the XLSX files in:
    map_builder/real_data/dnsp_nna/
  then run:
    python nna_data_pipeline.py --rebuild

USAGE:
  1. Embedded:  from nna_map_module import render_nna_tab
  2. Standalone: streamlit run nna_map_module.py
  3. New project: copy nna_map_module.py + nna_data_pipeline.py + data/geospatial/
"""

from __future__ import annotations

import math
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
_MODULE_DIR = Path(__file__).resolve().parent
_GEO_DIR    = _MODULE_DIR / "data" / "geospatial"
_PARQUET    = _GEO_DIR / "nna_master.parquet"
_PIPELINE   = _MODULE_DIR / "nna_data_pipeline.py"

# ── Data freshness ─────────────────────────────────────────────────────────
DATA_YEAR        = 2025
NEXT_UPDATE_DATE = date(2027, 7, 1)
STALE_DATE       = date(2028, 7, 1)

# ── Network metadata ───────────────────────────────────────────────────────
_NET_COLOUR: dict[str, str] = {
    "Ausgrid":           "#e63946",
    "AusNet Services":   "#2196F3",
    "CitiPower":         "#9C27B0",
    "Powercor":          "#FF9800",
    "Endeavour Energy":  "#4CAF50",
    "Evoenergy":         "#00BCD4",
    "SA Power Networks": "#F44336",
    "Energex":           "#FFC107",
    "Ergon Energy":      "#8BC34A",
    "Essential Energy":  "#009688",
    "Jemena":            "#3F51B5",
    "United Energy":     "#E91E63",
    "TasNetworks":       "#795548",
    "Western Power":     "#FF5722",
}
_DEFAULT_COLOUR = "#607D8B"

_NETWORK_STATE: dict[str, str] = {
    "Ausgrid":           "NSW",
    "Endeavour Energy":  "NSW",
    "AusNet Services":   "VIC",
    "CitiPower":         "VIC",
    "Powercor":          "VIC",
    "Evoenergy":         "ACT",
    "SA Power Networks": "SA",
    "Ergon Energy":      "QLD",
    "Energex":           "QLD",
    "Western Power":     "WA",
    "TasNetworks":       "TAS",
}

_NETWORK_REGION: dict[str, str] = {
    "Ausgrid":           "NSW1",
    "Endeavour Energy":  "NSW1",
    "AusNet Services":   "VIC1",
    "CitiPower":         "VIC1",
    "Powercor":          "VIC1",
    "Evoenergy":         "NSW1",
    "SA Power Networks": "SA1",
    "Ergon Energy":      "QLD1",
    "Energex":           "QLD1",
    "TasNetworks":       "TAS1",
    "Essential Energy":  "NSW1",
    "Jemena":            "VIC1",
    "United Energy":     "VIC1",
    "Western Power":     "WEM",
}

_STATE_ALIASES: dict[str, list[str]] = {
    "NSW": ["NSW", "New South Wales", "new south wales"],
    "VIC": ["VIC", "Victoria", "victoria"],
    "QLD": ["QLD", "Queensland", "queensland"],
    "SA":  ["SA",  "South Australia", "south australia"],
    "WA":  ["WA",  "Western Australia", "western australia"],
    "TAS": ["TAS", "Tasmania", "tasmania"],
    "ACT": ["ACT", "Australian Capital Territory"],
    "NT":  ["NT",  "Northern Territory"],
}

# Per-DNSP portal URLs for NNA/network planning pages
_NETWORK_URLS: dict[str, str] = {
    "Ausgrid":           "https://www.ausgrid.com.au/Industry/Network-planning/Non-network-alternatives",
    "Endeavour Energy":  "https://www.endeavourenergy.com.au/network-investment/non-network-alternatives",
    "AusNet Services":   "https://www.ausnetservices.com.au/electricity/network-planning",
    "CitiPower":         "https://www.citipower.com.au/our-network/network-planning",
    "Powercor":          "https://www.powercor.com.au/our-network/network-planning",
    "Evoenergy":         "https://www.evoenergy.com.au/network/network-planning",
    "SA Power Networks": "https://www.sapowernetworks.com.au/industry/network-planning",
    "Ergon Energy":      "https://www.ergon.com.au/network/network-management/non-network-solutions",
    "Energex":           "https://www.energex.com.au/network/network-management/non-network-solutions",
    "TasNetworks":       "https://www.tasnetworks.com.au/network-planning",
    "Western Power":     "https://www.westernpower.com.au/industry/connections/non-network-solutions",
}

# Per-DNSP approach strategy notes (5-step)
_NETWORK_STRATEGY: dict[str, str] = {
    "Ausgrid":           "Ausgrid publishes a DAPR each July and runs a formal NNA tender via their <i>Non-Network Alternatives</i> portal. EOIs close ~Oct each year.",
    "Endeavour Energy":  "Endeavour Energy issues a DAPR each July. NNA procurement is advertised on their network planning page; register interest via their online EOI form.",
    "AusNet Services":   "AusNet publishes a TAPR each July. NNA opportunities are listed under <i>System Limitation Reports</i>; contact their Network Planning team directly to register.",
    "CitiPower":         "CitiPower and Powercor publish a joint DAPR. NNA procurement is managed jointly; submit one EOI covering both networks if site spans both zones.",
    "Powercor":          "Powercor and CitiPower publish a joint DAPR. NNA procurement is managed jointly; submit one EOI covering both networks if site spans both zones.",
    "Evoenergy":         "Evoenergy publishes an annual network planning report. NNA procurement is less formalised; approach their asset management team directly with a scoped proposal.",
    "SA Power Networks": "SA Power Networks issues an annual DAPR. Contact their Network Investment team; tender documents are posted to their industry portal.",
    "Ergon Energy":      "Ergon Energy publishes an annual DAPR for regional QLD. Engage via their <i>Non-Network Solutions</i> page; formal RIT-D tender when constraints exceed threshold.",
    "Energex":           "Energex publishes an annual DAPR for SEQ. Engage via their <i>Non-Network Solutions</i> page; formal RIT-D tender when constraints exceed threshold.",
    "TasNetworks":       "TasNetworks publishes an annual network plan. Engage their Network Development team directly; formal NNA process follows AER RIT-D guidelines.",
    "Western Power":     "Western Power operates under SWIS rules (not NEM NER); NNA engagement is via their <i>Non-Network Solutions</i> process under ERA oversight.",
}


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _fmt_dollar(value: float, *, per_yr: bool = False) -> str:
    if value == 0:
        return "—"
    if abs(value) >= 1_000_000:
        s = f"${value / 1_000_000:.2f}M"
    elif abs(value) >= 1_000:
        s = f"${value / 1_000:.0f}k"
    else:
        s = f"${value:,.0f}"
    return s + "/yr" if per_yr else s


def _colour(network: str) -> str:
    return _NET_COLOUR.get(network, _DEFAULT_COLOUR)


def _normalise_state(state_str: str) -> str:
    if not state_str:
        return ""
    s = str(state_str).strip()
    for abbr, aliases in _STATE_ALIASES.items():
        if s in aliases or s.upper() == abbr:
            return abbr
    return s.upper()[:3]


def _safe(val, default=None):
    """Return default (not pd.NA) for any missing value."""
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


# ══════════════════════════════════════════════════════════════════════════════
# Data freshness check
# ══════════════════════════════════════════════════════════════════════════════

def check_freshness() -> None:
    today = date.today()
    if today >= STALE_DATE:
        st.error(
            f"NNA data is **{today.year - DATA_YEAR} years stale** "
            f"(FY{DATA_YEAR}-{DATA_YEAR+1} vintage). "
            f"Update map_builder/real_data/dnsp_nna/ and run "
            f"`python nna_data_pipeline.py --rebuild` immediately."
        )
    elif today >= NEXT_UPDATE_DATE:
        st.warning(
            f"NNA source data is from FY{DATA_YEAR}-{DATA_YEAR+1}. "
            f"New DNSP System Limitation Reports are now available. "
            f"Update the XLSX files and re-run the pipeline."
        )


# ══════════════════════════════════════════════════════════════════════════════
# NNA Master Table
# Enriches raw Parquet with system sizing, ADV, contract term
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _build_nna_master_table() -> pd.DataFrame:
    """
    Build enriched NNA master table from three CSVs in data/geospatial/:
      ena_proposed_investment.csv          - one row per asset
      ena_deferral_values_timeseries.csv   - annual_deferral_aud per year
      ena_available_capacity_timeseries.csv - capacity/load/available per year

    Added columns:
      deferrable_m    aug_cost_aud / 1e6  (display in $M)
      adv_real        annual_deferral_aud in $ (fallback: aug_cost * 8%)
      deficit_mw      abs(available_mva) where negative
      ideal_bess_mw   sized to cover deficit
      ideal_solar_mw  2.5 x BESS (40% CF assumption)
      nna_term_yrs    years until invest needed, capped 1-15
      nem_region      for loss factor lookup
    """
    inv_path = _GEO_DIR / "ena_proposed_investment.csv"
    def_path = _GEO_DIR / "ena_deferral_values_timeseries.csv"
    cap_path = _GEO_DIR / "ena_available_capacity_timeseries.csv"

    if not inv_path.exists():
        return pd.DataFrame()

    inv = pd.read_csv(inv_path)

    # Merge latest ADV from deferral timeseries
    if def_path.exists():
        defs = pd.read_csv(def_path)
        latest_yr = int(defs["year"].max()) if not defs.empty else DATA_YEAR
        adv_latest = (
            defs[defs["year"] == latest_yr][["asset_code", "annual_deferral_aud"]]
            .rename(columns={"annual_deferral_aud": "adv_ts"})
        )
        inv = inv.merge(adv_latest, on="asset_code", how="left")
        inv["annual_deferral_aud"] = inv["adv_ts"].combine_first(
            pd.to_numeric(inv.get("annual_deferral_aud"), errors="coerce")
        )
        inv.drop(columns=["adv_ts"], errors="ignore", inplace=True)
    else:
        inv["annual_deferral_aud"] = pd.to_numeric(
            inv.get("annual_deferral_aud"), errors="coerce"
        )

    # Merge latest capacity from timeseries
    if cap_path.exists():
        caps = pd.read_csv(cap_path)
        latest_cap = (
            caps.sort_values("year", ascending=False)
            .drop_duplicates("asset_code", keep="first")
            [["asset_code", "capacity", "load", "available_capacity"]]
            .rename(columns={
                "capacity":           "cap_ts",
                "load":               "load_ts",
                "available_capacity": "avail_ts",
            })
        )
        inv = inv.merge(latest_cap, on="asset_code", how="left")
        inv["capacity_mva"]    = inv["cap_ts"].combine_first(
            pd.to_numeric(inv.get("capacity_mva"), errors="coerce")
        )
        inv["peak_demand_mva"] = inv["load_ts"].combine_first(
            pd.to_numeric(inv.get("peak_demand_mva"), errors="coerce")
        )
        inv["available_mva"]   = inv["avail_ts"].combine_first(
            pd.to_numeric(inv.get("available_mva"), errors="coerce")
        )
        inv.drop(columns=["cap_ts", "load_ts", "avail_ts"], errors="ignore", inplace=True)
    else:
        for col in ("capacity_mva", "peak_demand_mva", "available_mva"):
            inv[col] = pd.to_numeric(inv.get(col), errors="coerce")

    # Numeric cleanup
    inv["aug_cost_aud"] = pd.to_numeric(inv.get("aug_cost_aud"), errors="coerce").fillna(0)
    inv["latitude"]     = pd.to_numeric(inv.get("latitude"),     errors="coerce")
    inv["longitude"]    = pd.to_numeric(inv.get("longitude"),    errors="coerce")

    # Derived columns
    if "state" not in inv.columns or inv["state"].isna().all():
        inv["state"] = inv["network"].map(_NETWORK_STATE).fillna("")
    inv["nem_region"] = inv["network"].map(_NETWORK_REGION).fillna("")

    # deferrable_m in $M (for display)
    inv["deferrable_m"] = inv["aug_cost_aud"] / 1_000_000

    # adv_real: published annual deferral, fallback to 8% of aug cost
    inv["adv_real"] = inv["annual_deferral_aud"].where(
        inv["annual_deferral_aud"].notna() & (inv["annual_deferral_aud"] > 0),
        other=inv["aug_cost_aud"] * 0.08,
    ).fillna(0)

    # deficit_mw
    # available_mva is stored in VA (volt-amps) by the pipeline, not MVA.
    # Divide by 1,000,000 to convert VA → MW/MVA.
    inv["deficit_mw"] = inv["available_mva"].apply(
        lambda x: abs(float(x)) / 1_000_000 if pd.notna(x) and float(x) < 0 else 0.0
    )

    # Ideal system sizing
    def _sizing(row) -> pd.Series:
        deficit = float(row["deficit_mw"]) if pd.notna(row["deficit_mw"]) else 0.0
        aug_m   = float(row["deferrable_m"]) if pd.notna(row["deferrable_m"]) else 0.0
        if deficit > 0:
            bess  = round(max(deficit, 1.0), 1)
            solar = round(deficit * 2.5, 1)
        elif aug_m > 0:
            est   = round(max(aug_m * 3.0, 2.0), 1)
            bess  = est
            solar = round(est * 2.0, 1)
        else:
            bess, solar = 5.0, 10.0
        return pd.Series({"ideal_bess_mw": bess, "ideal_solar_mw": solar})

    sizing = inv.apply(_sizing, axis=1)
    inv = pd.concat([inv, sizing], axis=1)

    # NNA contract term = years until investment, capped 1-15
    current_year = date.today().year

    def _calc_term(timing_val) -> int:
        try:
            yr   = int(str(timing_val)[:4])
            term = yr - current_year
            return max(1, min(term, 15))
        except (ValueError, TypeError):
            return 5

    inv["nna_term_yrs"] = inv["proposed_timing"].apply(_calc_term)

    # Filter to rows with valid coordinates
    mask   = inv["latitude"].notna() & inv["longitude"].notna()
    result = inv.loc[mask].copy().reset_index(drop=True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# NNA contract workings HTML
# ══════════════════════════════════════════════════════════════════════════════

def _nna_contract_explainer(
    deferrable_m: float,
    adv_real: float,
    ideal_bess_mw: float,
    *,
    aug_cost_aud: float = 0.0,
    nna_term_yrs: int = 5,
    network: str = "",
    data_source_file: str = "",
) -> str:
    """Full step-by-step NNA revenue workings as HTML string."""
    if deferrable_m <= 0 and adv_real <= 0:
        return ""

    deferrable_real = deferrable_m * 1_000_000
    parts: list[str] = []

    parts.append(
        "<div style='background:#fff3e0;border:1px solid #ffcc80;"
        "border-radius:6px;padding:8px;margin:4px 0'>"
        f"<b>NNA Revenue: {_fmt_dollar(deferrable_real)} Augmentation Deferral</b>"
        "<hr style='margin:4px 0;border-color:#ffcc80'>"
    )

    parts.append(
        f"The DNSP has <b>{_fmt_dollar(deferrable_real)}</b> of planned capital "
        f"works deferrable for up to <b>{nna_term_yrs} years</b> under an NNA contract."
        "<br><br>"
    )

    # Contract revenue
    if adv_real > 0:
        contract_total = adv_real * nna_term_yrs
        parts.append(
            "<b>NNA Contract Revenue:</b><br>"
            "<table style='font-size:10px;margin:2px 0 6px 8px;border-collapse:collapse'>"
            f"<tr><td style='padding:1px 8px'>Annual payment (ADV):</td>"
            f"<td style='padding:1px 8px;font-weight:bold'>{_fmt_dollar(adv_real, per_yr=True)}</td></tr>"
            f"<tr><td style='padding:1px 8px'>{nna_term_yrs}-yr contract value:</td>"
            f"<td style='padding:1px 8px;font-weight:bold'>{_fmt_dollar(contract_total)}</td></tr>"
            "</table>"
        )

    # BESS CAPEX & payback
    if ideal_bess_mw > 0:
        capex_lo = ideal_bess_mw * 800_000
        capex_hi = ideal_bess_mw * 1_200_000
        parts.append(
            f"<b>BESS Investment ({ideal_bess_mw:.0f} MW):</b><br>"
            "<table style='font-size:10px;margin:2px 0 6px 8px;border-collapse:collapse'>"
            f"<tr><td style='padding:1px 8px'>CAPEX low ($800k/MW):</td><td>{_fmt_dollar(capex_lo)}</td></tr>"
            f"<tr><td style='padding:1px 8px'>CAPEX high ($1.2M/MW):</td><td>{_fmt_dollar(capex_hi)}</td></tr>"
        )
        if adv_real > 0:
            pb_lo = capex_lo / adv_real
            pb_hi = capex_hi / adv_real
            parts.append(
                f"<tr><td style='padding:1px 8px'>NNA-only payback:</td>"
                f"<td style='padding:1px 8px;font-weight:bold'>{pb_lo:.1f}-{pb_hi:.1f} yrs</td></tr>"
            )
        parts.append("</table><small>&nbsp;Improves further with FCAS + arbitrage stacking</small><br><br>")

    # Show workings collapsible
    parts.append(
        "<details style='margin:4px 0'>"
        "<summary style='cursor:pointer;font-weight:bold;color:#e65100'>"
        "Show workings &amp; assumptions</summary>"
        "<div style='padding:6px 4px;font-size:10px;line-height:1.5'>"
    )

    # Step 1: ADV
    parts.append("<b>Step 1 - ADV Calculation (NER cl 5.17.4):</b><br>")
    if adv_real > 0 and deferrable_real > 0:
        rate = adv_real / deferrable_real
        parts.append(
            f"&nbsp; ADV = aug_cost x (WACC + depreciation)<br>"
            f"&nbsp; = {_fmt_dollar(deferrable_real)} x ~{rate:.1%}"
            f" = <b>{_fmt_dollar(adv_real, per_yr=True)}</b><br>"
            f"&nbsp; (typical WACC 5.5% + depr 2.5% = ~8% of aug cost)<br>"
        )
    else:
        indicative = deferrable_real * 0.08
        parts.append(
            f"&nbsp; No published ADV. Indicative: {_fmt_dollar(deferrable_real)} x 8%"
            f" = <b>{_fmt_dollar(indicative, per_yr=True)}</b> (estimate)<br>"
        )

    # Step 2: Sizing
    parts.append(
        "<br><b>Step 2 - System Sizing:</b><br>"
        f"&nbsp; BESS: {ideal_bess_mw:.0f} MW to cover MW deficit at substation<br>"
        f"&nbsp; Duration: 4 hours (typical NNA dispatch window at peak)<br>"
        f"&nbsp; Solar: ~2.5x MW deficit (40% CF, BOM zone 3-4 avg)<br>"
    )

    # Step 3: CAPEX
    parts.append(
        "<br><b>Step 3 - CAPEX Benchmarks (CSIRO GenCost 2024):</b><br>"
        "&nbsp; BESS: $800k-$1.2M/MW (2-4 hr grid-scale)<br>"
        "&nbsp; Solar: $1.0-$1.4M/MW (utility, excl. land &amp; connection)<br>"
        "&nbsp; Connection costs: <b>not included</b><br>"
    )

    # Step 4: NNA contract revenue only
    parts.append("<br><b>Step 4 - NNA Contract Revenue:</b><br>")
    if adv_real > 0:
        capex_lo  = ideal_bess_mw * 800_000
        capex_hi  = ideal_bess_mw * 1_200_000
        pb_lo     = capex_lo / adv_real
        pb_hi     = capex_hi / adv_real
        parts.append(
            "<table style='font-size:10px;margin:2px 0 4px 8px;border-collapse:collapse'>"
            f"<tr><td style='padding:1px 6px'>NNA contract (ADV):</td><td><b>{_fmt_dollar(adv_real, per_yr=True)}</b></td></tr>"
            f"<tr><td style='padding:1px 6px'>NNA-only payback (BESS):</td><td>{pb_lo:.1f}–{pb_hi:.1f} yrs</td></tr>"
            "</table>"
            "&nbsp; <small>FCAS + arbitrage revenue to be modelled separately based on dispatch profile.</small><br>"
        )

    # Caveats
    parts.append(
        "<br><b>Key Requirements:</b>"
        "<ol style='margin:2px 0 4px 16px;padding:0;font-size:10px'>"
        "<li>RIT-D process must be complete and DNSP must invite NNA proposals</li>"
        "<li>Grid connection agreement required (costs not included)</li>"
        "<li>95-98% availability during constraint window (e.g. 3-8 PM summer)</li>"
        "<li>ADV is a cap — actual rate depends on competitive tender</li>"
        "</ol>"
        "<br><b>References:</b> NER cl 5.17.4 . AER RIT-D guidelines . "
        "CSIRO GenCost 2024 . BOM solar atlas . ENA DAPR/TAPR 2023"
    )
    parts.append("</div></details>")

    # ── $/MW NNA Revenue Rate ───────────────────────────────────────────────
    if adv_real > 0 and ideal_bess_mw > 0:
        adv_per_mw = adv_real / ideal_bess_mw
        parts.append(
            "<div style='background:#e8f5e9;border:1px solid #a5d6a7;"
            "border-radius:6px;padding:8px;margin:4px 0'>"
            "<b>NNA Revenue Rate</b>"
            "<hr style='margin:4px 0;border-color:#a5d6a7'>"
            "<table style='font-size:10px;border-collapse:collapse;width:100%'>"
            f"<tr><td style='padding:1px 8px'>ADV per MW/yr:</td>"
            f"<td style='padding:1px 8px;font-weight:bold'>{_fmt_dollar(adv_per_mw, per_yr=True)}</td></tr>"
            f"<tr><td style='padding:1px 8px'>Based on system size:</td>"
            f"<td style='padding:1px 8px'>{max(ideal_bess_mw, 1.0):.1f} MW BESS</td></tr>"
            "</table>"
            f"<small>Minimum viable: <b>{max(ideal_bess_mw, 1.0):.0f} MW BESS</b> / "
            f"<b>{max(ideal_bess_mw * 2.5, 2.5):.0f} MW solar</b> "
            "(1 MW BESS floor · solar at 2.5× BESS)<br>"
            "FCAS &amp; arbitrage revenue modelled separately.</small>"
            "</div>"
        )

    # ── Source Material ─────────────────────────────────────────────────────
    src = data_source_file.strip() if data_source_file else ""
    if src:
        parts.append(
            "<div style='background:#f3e5f5;border:1px solid #ce93d8;"
            "border-radius:6px;padding:8px;margin:4px 0'>"
            "<b>Source Material</b>"
            "<hr style='margin:4px 0;border-color:#ce93d8'>"
            f"<span style='font-size:10px'>&#128196; {src}</span><br>"
            "<small>Data extracted from DNSP System Limitation Report / DAPR. "
            "Values are as published; verify against the current-year report "
            "before submitting an NNA proposal.</small>"
            "</div>"
        )

    # ── DNSP Portal Link + Approach Strategy ────────────────────────────────
    if network:
        portal_url = _NETWORK_URLS.get(network, "")
        strategy   = _NETWORK_STRATEGY.get(
            network,
            "Contact the DNSP network planning team and request NNA procurement documentation."
        )
        link_html = (
            f"<a href='{portal_url}' target='_blank' style='color:#1565c0'>&#128279; "
            f"{network} NNA/Planning Portal</a>"
            if portal_url else f"<b>{network}</b>"
        )
        parts.append(
            "<div style='background:#e3f2fd;border:1px solid #90caf9;"
            "border-radius:6px;padding:8px;margin:4px 0'>"
            f"<b>DNSP: {link_html}</b>"
            "<hr style='margin:4px 0;border-color:#90caf9'>"
            f"<p style='font-size:10px;margin:4px 0'>{strategy}</p>"
            "<b style='font-size:10px'>5-Step Approach:</b>"
            "<ol style='font-size:10px;margin:2px 0 4px 16px;padding:0;line-height:1.6'>"
            "<li>Download the latest DAPR/TAPR from the portal above — confirm this asset is still listed as a system limitation</li>"
            "<li>Check <b>RIT-D status</b> — if RIT-D is commenced or NNA procurement is open, register your interest immediately</li>"
            "<li>Submit an <b>Expression of Interest (EOI)</b> to the DNSP network planning team with a one-page capability overview</li>"
            "<li>Lodge a <b>connection enquiry</b> at the constrained substation to obtain indicative costs and indicative timing</li>"
            "<li>Prepare your <b>NNA bid</b>: technical spec (MW, duration, availability SLA), commercial offer ≤ ADV, and evidence of deliverability (site control, grid connection path)</li>"
            "</ol>"
            "</div>"
        )

    parts.append("</div>")
    return "".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# Loss factor enrichment (gracefully skips if module missing)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _build_nna_leaderboard_data() -> pd.DataFrame:
    df = _build_nna_master_table()
    if df.empty:
        return df
    try:
        from loss_factor_lookup import LossFactorLookup
        lfl  = LossFactorLookup()
        mlfs = []
        dlfs = []
        for _, row in df.iterrows():
            lat     = row["latitude"]
            lon     = row["longitude"]
            region  = _safe(row.get("nem_region"), "")
            network = _safe(row.get("network"),    "")
            tni     = lfl.nearest_tni(lat, lon, region=region, max_distance_km=100)
            dlf_m   = lfl.nearest_dlf(lat, lon, region=region, dnsp=network, max_distance_km=100)
            mlfs.append(round(tni.loss_factor   if tni   else 1.0, 4))
            dlfs.append(round(dlf_m.loss_factor if dlf_m else 1.0, 4))
        df["mlf"] = mlfs
        df["dlf"] = dlfs
    except Exception:
        df["mlf"] = 1.0
        df["dlf"] = 1.0
    df["combined_lf"] = (df["mlf"] * df["dlf"]).round(4)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# Map builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_map(
    df: pd.DataFrame,
    centre_lat: Optional[float],
    centre_lon: Optional[float],
    zoom: int = 6,
    cluster: bool = True,
) -> folium.Map:

    loc  = [centre_lat, centre_lon] if (centre_lat and centre_lon) else [-33.5, 147.0]
    zoom = 10 if (centre_lat and centre_lon) else zoom

    m = folium.Map(location=loc, zoom_start=zoom, tiles=None,
                   control_scale=True, prefer_canvas=True)
    folium.TileLayer(
        tiles="CartoDB positron",
        name="",          # blank name hides it from any layer control
        show=True,
        control=False,    # exclude from layer control entirely
    ).add_to(m)
    # Override Leaflet's default popup max-height so our inner scroll div works
    folium.Element(
        "<style>"
        ".leaflet-popup-content-wrapper { max-height: none !important; overflow: visible !important; }"
        ".leaflet-popup-content { max-height: none !important; overflow: visible !important; margin: 6px 10px; }"
        "</style>"
    ).add_to(m)

    if centre_lat and centre_lon:
        folium.Marker(
            [centre_lat, centre_lon],
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
            tooltip="Your project location",
        ).add_to(m)
        folium.Circle(
            [centre_lat, centre_lon], radius=25_000,
            color="#e63946", fill=False, weight=1.5, dash_array="6",
            tooltip="25 km radius",
        ).add_to(m)

    container = MarkerCluster(disableClusteringAtZoom=11) if cluster else None

    for _, r in df.iterrows():
        lat = _safe(r.get("latitude"))
        lon = _safe(r.get("longitude"))
        if lat is None or lon is None:
            continue

        net   = _safe(r.get("network"),      "")
        name  = _safe(r.get("asset_name"),   "Unknown")
        state = _safe(r.get("state"),        "")
        colour = _colour(str(net))

        cap   = _safe(r.get("capacity_mva"))
        dem   = _safe(r.get("peak_demand_mva"))
        avail = _safe(r.get("available_mva"))
        defer = _safe(r.get("adv_real"))
        aug   = _safe(r.get("aug_cost_aud"))
        timing = _safe(r.get("proposed_timing"))
        cat   = _safe(r.get("asset_category"))
        bess  = _safe(r.get("ideal_bess_mw"))
        solar = _safe(r.get("ideal_solar_mw"))
        term  = _safe(r.get("nna_term_yrs"))
        def_m = _safe(r.get("deferrable_m"), 0.0)
        src_file = _safe(r.get("data_source_file"), "")

        rows = ""
        if cap   is not None: rows += f"<tr><td>Rating</td><td><b>{cap:.1f} MVA</b></td></tr>"
        if dem   is not None: rows += f"<tr><td>Peak demand</td><td><b>{dem:.1f} MVA</b></td></tr>"
        if avail is not None:
            clr = "green" if avail > 0 else "red"
            rows += f"<tr><td>Headroom</td><td style='color:{clr}'><b>{avail:+.1f} MVA</b></td></tr>"
        if defer is not None and defer > 0:
            rows += f"<tr><td>ADV ($/yr)</td><td><b>{_fmt_dollar(defer, per_yr=True)}</b></td></tr>"
        if aug   is not None and aug > 0:
            rows += f"<tr><td>Aug. cost</td><td><b>{_fmt_dollar(aug)}</b></td></tr>"
        if bess  is not None: rows += f"<tr><td>Ideal BESS</td><td><b>{bess:.0f} MW</b></td></tr>"
        if solar is not None: rows += f"<tr><td>Ideal Solar</td><td><b>{solar:.0f} MW</b></td></tr>"
        if term  is not None: rows += f"<tr><td>Contract term</td><td><b>{term} yrs</b></td></tr>"
        if timing is not None: rows += f"<tr><td>Invest yr</td><td>{str(timing)[:10]}</td></tr>"
        if cat   is not None: rows += f"<tr><td>Category</td><td>{cat}</td></tr>"

        workings = _nna_contract_explainer(
            float(def_m or 0),
            float(defer or 0),
            float(bess  or 5),
            aug_cost_aud=float(aug or 0),
            nna_term_yrs=int(term or 5),
            network=str(net),
            data_source_file=str(src_file or ""),
        )

        popup_html = (
            "<div style='font-family:sans-serif;width:400px;font-size:11px'>"
            "<div style='position:sticky;top:0;background:#fff;padding:4px 0 2px;z-index:1;border-bottom:1px solid #eee;margin-bottom:4px'>"
            f"<b style='font-size:12px'>{name}</b><br>"
            f"<span style='color:{colour};font-size:10px'>&#9632; {net}  ({state})</span>"
            "</div>"
            "<div style='max-height:660px;overflow-y:scroll;overflow-x:hidden;padding-right:4px;padding-bottom:120px'>"
            f"<table style='border-collapse:collapse;font-size:11px;width:100%;margin-bottom:6px'>"
            f"<colgroup><col style='width:48%'><col style='width:52%'></colgroup>"
            f"{rows}"
            f"</table>"
            f"{workings}"
            "</div>"
            "</div>"
        )

        has_defer = defer is not None and defer > 0
        tooltip_txt = f"{name} — {net}"
        if has_defer:
            tooltip_txt += f" | {_fmt_dollar(defer, per_yr=True)}"

        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=8 if has_defer else 6,
            color=colour, fill=True, fill_color=colour,
            fill_opacity=0.85 if has_defer else 0.5,
            weight=2,
            tooltip=tooltip_txt,
            popup=folium.Popup(popup_html, max_width=440, max_height=700),
        )

        if cluster and container is not None:
            marker.add_to(container)
        else:
            marker.add_to(m)

    if cluster and container is not None:
        container.add_to(m)
    return m


# ══════════════════════════════════════════════════════════════════════════════
# Leaderboard  —  10 km / state / national tiers
# ══════════════════════════════════════════════════════════════════════════════

def _format_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["Asset"]       = df["asset_name"].values
    out["Network"]     = df["network"].values
    out["State"]       = df["state"].values
    out["Dist (km)"]   = df["distance_km"].apply(lambda v: f"{v:.1f}").values
    out["Aug Cost"]    = df["deferrable_m"].apply(lambda v: _fmt_dollar(v * 1e6)).values
    out["ADV ($/yr)"]  = df["adv_real"].apply(
        lambda v: _fmt_dollar(v, per_yr=True) if v > 0 else "—"
    ).values
    out["Term (yrs)"]  = df["nna_term_yrs"].apply(
        lambda v: f"{int(v)} yr{'s' if int(v) != 1 else ''}"
    ).values
    out["BESS (MW)"]   = df["ideal_bess_mw"].apply(lambda v: f"{v:.0f}").values
    out["Solar (MW)"]  = df["ideal_solar_mw"].apply(lambda v: f"{v:.0f}").values
    out["MLF"]         = df["mlf"].apply(lambda v: f"{v:.4f}").values
    out["DLF"]         = df["dlf"].apply(lambda v: f"{v:.4f}").values
    out["Combined LF"] = df["combined_lf"].apply(lambda v: f"{v:.4f}").values
    if "constraint_season" in df.columns:
        out["Season"]  = df["constraint_season"].fillna("—").values
    return out.reset_index(drop=True)


def _leaderboard_metrics(df: pd.DataFrame, label: str) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Total Aug Cost ({label})", _fmt_dollar(df["deferrable_m"].sum() * 1e6))
    adv_sum = df["adv_real"].sum()
    c2.metric(f"Total ADV ({label})",
              _fmt_dollar(adv_sum, per_yr=True) if adv_sum > 0 else "—")
    if "combined_lf" in df.columns:
        c3.metric(f"Avg Combined LF ({label})", f"{df['combined_lf'].mean():.4f}")


def render_nna_leaderboard(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> None:
    """Render 10 km / state / national NNA leaderboard tables."""
    if lat is None:
        lat = st.session_state.get("lat_from_geocode")
    if lon is None:
        lon = st.session_state.get("lon_from_geocode")

    if lat is None or lon is None:
        st.info("Enter an address on the Site tab to see nearby NNA opportunities.")
        return

    lat, lon = float(lat), float(lon)
    user_state = _normalise_state(str(st.session_state.get("au_state", "")))

    master = _build_nna_leaderboard_data()
    if master.empty:
        st.info("No NNA opportunity data available.")
        return

    master["distance_km"] = master.apply(
        lambda r: round(_haversine_km(lat, lon, r["latitude"], r["longitude"]), 1),
        axis=1,
    )
    master = master.sort_values(["adv_real", "deferrable_m"], ascending=[False, False])

    st.markdown("---")
    st.subheader("NNA Revenue Leaderboard")
    st.caption(
        "Ranked by Annual Deferral Value (ADV) = maximum annual payment the DNSP "
        "will make to avoid network augmentation. Includes MLF x DLF per site."
    )

    # 1. Within 10 km
    nearby = master[master["distance_km"] <= 10].head(5)
    st.markdown("**Top NNA Opportunities Within 10 km**")
    if nearby.empty:
        st.info("No NNA opportunities within 10 km of your site.")
    else:
        st.dataframe(_format_leaderboard(nearby), use_container_width=True, hide_index=True)
        _leaderboard_metrics(nearby, "10 km")

    st.markdown("")

    # 2. State
    if user_state:
        state_df = master[master["state"] == user_state].head(10)
        st.markdown(f"**Top NNA Opportunities in {user_state}**")
        if state_df.empty:
            st.info(f"No NNA opportunities found in {user_state}.")
        else:
            st.dataframe(_format_leaderboard(state_df), use_container_width=True, hide_index=True)
            _leaderboard_metrics(state_df, user_state)

    st.markdown("")

    # 3. National top 5
    national = master.head(5)
    st.markdown("**Top 5 NNA Opportunities Nationally**")
    if not national.empty:
        st.dataframe(_format_leaderboard(national), use_container_width=True, hide_index=True)
        _leaderboard_metrics(national, "Top 5")

    st.markdown("")

    # 4. Top 10 by $/MW (ADV per MW of ideal BESS — best revenue density regardless of location)
    st.markdown("**Top 10 NNA Opportunities — Best $/MW Return (All Australia)**")
    st.caption(
        "Ranked by Annual Deferral Value per MW of BESS required. "
        "Higher $/MW = more revenue from a smaller battery — the most capital-efficient sites."
    )
    dollar_per_mw = master.copy()
    dollar_per_mw = dollar_per_mw[dollar_per_mw["ideal_bess_mw"] > 0]
    dollar_per_mw["adv_per_mw"] = dollar_per_mw["adv_real"] / dollar_per_mw["ideal_bess_mw"]
    dollar_per_mw = dollar_per_mw.sort_values("adv_per_mw", ascending=False).head(10)

    if dollar_per_mw.empty:
        st.info("No $/MW data available.")
    else:
        dpm_out = pd.DataFrame()
        dpm_out["#"]           = range(1, len(dollar_per_mw) + 1)
        dpm_out["Asset"]       = dollar_per_mw["asset_name"].values
        dpm_out["Network"]     = dollar_per_mw["network"].values
        dpm_out["State"]       = dollar_per_mw["state"].values
        dpm_out["BESS (MW)"]   = dollar_per_mw["ideal_bess_mw"].apply(lambda v: f"{v:.0f}").values
        dpm_out["ADV ($/yr)"]  = dollar_per_mw["adv_real"].apply(
            lambda v: _fmt_dollar(v, per_yr=True) if v > 0 else "—"
        ).values
        dpm_out["$/MW/yr"]     = dollar_per_mw["adv_per_mw"].apply(
            lambda v: f"${v:,.0f}/MW"
        ).values
        dpm_out["Aug Cost"]    = dollar_per_mw["deferrable_m"].apply(
            lambda v: _fmt_dollar(v * 1e6)
        ).values
        dpm_out["Term (yrs)"]  = dollar_per_mw["nna_term_yrs"].apply(
            lambda v: f"{int(v)} yr{'s' if int(v) != 1 else ''}"
        ).values
        dpm_out["Combined LF"] = dollar_per_mw["combined_lf"].apply(
            lambda v: f"{v:.4f}"
        ).values
        st.dataframe(dpm_out.reset_index(drop=True), use_container_width=True, hide_index=True)

        # Summary metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Best $/MW/yr", f"${dollar_per_mw['adv_per_mw'].iloc[0]:,.0f}/MW")
        c2.metric("Avg $/MW/yr (Top 10)", f"${dollar_per_mw['adv_per_mw'].mean():,.0f}/MW")
        c3.metric("Total ADV (Top 10)", _fmt_dollar(dollar_per_mw["adv_real"].sum(), per_yr=True))

    with st.expander("About the NNA Leaderboard & Methodology", expanded=False):
        st.markdown(
            """
**How this table is calculated:**

| Column | Formula / Source |
|--------|-----------------|
| **Aug Cost** | DNSP planned augmentation capex from DAPR/TAPR System Limitation Report |
| **ADV ($/yr)** | `aug_cost x (WACC + depreciation)` per NER cl 5.17.4 — typically ~8% of capex |
| **Term (yrs)** | `investment_year - current_year`, capped 1-15 years |
| **BESS (MW)** | Sized to cover MW deficit (or estimated from aug cost where no deficit data) |
| **Solar (MW)** | `BESS MW x 2.5` — accounts for ~40% capacity factor (BOM zone 3-4) |
| **MLF** | Nearest TNI marginal loss factor (AEMO FY25-26 determination) |
| **DLF** | Nearest DNSP distribution loss factor (AEMO determination) |
| **Combined LF** | `MLF x DLF` — effective wholesale price multiplier on exported energy |

**Key caveats:** ADV is a cap, not guaranteed. RIT-D process must be complete.
Connection costs not included. Refer to AER RIT-D guidelines and NER cl 5.17.4.
            """
        )


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar filters
# ══════════════════════════════════════════════════════════════════════════════

def _sidebar_filters(df: pd.DataFrame):
    networks = sorted(df["network"].dropna().unique().tolist())
    states   = sorted(df["state"].dropna().unique().tolist())

    with st.expander("🔽 Filter DNSPs & options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            sel_nets = st.multiselect("Network", networks, default=networks,
                                      key="nna_filter_networks")
        with col2:
            sel_states = st.multiselect("State", states, default=states,
                                        key="nna_filter_states")
        c1, c2 = st.columns(2)
        with c1:
            only_adv = st.checkbox("Only sites with published ADV", value=False,
                                   key="nna_filter_adv_only")
        with c2:
            cluster = st.checkbox("Cluster pins", value=True, key="nna_cluster")

    filtered = df[df["network"].isin(sel_nets) & df["state"].isin(sel_states)].copy()
    if only_adv:
        filtered = filtered[filtered["adv_real"] > 0]
    return filtered, cluster


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def render_nna_tab(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    show_leaderboard: bool = True,
    show_filters: bool = True,
) -> None:
    """
    Render the full NNA map + leaderboard.

    Coordinates: uses passed lat/lon if provided, otherwise reads
    st.session_state["lat_from_geocode"] / ["lon_from_geocode"] automatically.
    """
    check_freshness()

    if lat is None:
        lat = st.session_state.get("lat_from_geocode")
    if lon is None:
        lon = st.session_state.get("lon_from_geocode")

    try:
        df = _build_nna_master_table()
    except Exception as e:
        st.error(f"NNA data could not be loaded: {e}")
        st.info("Run `python nna_data_pipeline.py --rebuild` to regenerate.")
        return

    if df.empty:
        st.warning("NNA dataset is empty. Run `python nna_data_pipeline.py --rebuild`.")
        return

    filtered, cluster = _sidebar_filters(df) if show_filters else (df.copy(), True)

    adv_count = int((filtered["adv_real"] > 0).sum())
    st.markdown(
        f"**{len(filtered)} NNA constraint sites** across "
        f"{filtered['network'].nunique()} networks — "
        f"**{adv_count}** with published ADV. "
        f"Click any pin for investment workings and CAPEX/payback analysis."
    )

    m = _build_map(
        filtered,
        centre_lat=float(lat) if lat is not None else None,
        centre_lon=float(lon) if lon is not None else None,
        cluster=cluster,
    )
    st_folium(m, use_container_width=True, height=780, returned_objects=[])

    legend_html = " &nbsp; ".join(
        f'<span style="color:{c}">&#9679;</span> {n}'
        for n, c in _NET_COLOUR.items()
        if n in filtered["network"].values
    )
    st.caption(legend_html, unsafe_allow_html=True)

    if show_leaderboard:
        render_nna_leaderboard(lat=lat, lon=lon)

    built_at  = _safe(df["built_at"].iloc[0],  "unknown") if "built_at"  in df.columns else "unknown"
    data_year = _safe(df["data_year"].iloc[0], DATA_YEAR)  if "data_year" in df.columns else DATA_YEAR
    st.caption(
        f"Data: FY{data_year}-{int(data_year)+1} DNSP System Limitation Reports  "
        f"| Parquet built: {str(built_at)[:19]}  "
        f"| Next update: 1 July 2027"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Standalone:  streamlit run nna_map_module.py
# ══════════════════════════════════════════════════════════════════════════════

def _is_standalone() -> bool:
    import sys
    try:
        return Path(sys.argv[0]).resolve() == Path(__file__).resolve()
    except Exception:
        return False


if _is_standalone():
    st.set_page_config(page_title="NNA Opportunity Map", page_icon="", layout="wide")
    st.title("Network Non-Network Alternative (NNA) Opportunity Map")
    st.markdown(
        "Distribution network constraints where a Non-Network Alternative "
        "(battery storage, demand response, embedded generation) can be paid "
        "to defer costly network augmentation. "
        "Click any pin for full investment workings and CAPEX/payback analysis."
    )
    render_nna_tab()
