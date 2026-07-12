"""
HaimOS Streamlit frontend.
Runs as a separate process alongside the Electron / FastAPI backend.

Start:  streamlit run app.py
"""
import streamlit as st
import requests

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HaimOS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Import NNA map module (self-contained, no mutations) ───────────────────────
from nna_map_module import render_nna_tab

# ── Sidebar: project address + geocoding ──────────────────────────────────────
with st.sidebar:
    st.title("⚡ HaimOS")
    st.markdown("---")
    st.subheader("Project Location")

    address_input = st.text_input(
        "Address",
        value=st.session_state.get("address_input", ""),
        placeholder="e.g. 123 Collins St, Melbourne VIC",
        key="address_input",
    )

    if st.button("Geocode Address", use_container_width=True):
        if address_input.strip():
            with st.spinner("Geocoding…"):
                try:
                    resp = requests.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": address_input, "format": "json", "limit": 1},
                        headers={"User-Agent": "HaimOS/1.0"},
                        timeout=10,
                    )
                    results = resp.json()
                    if results:
                        lat = float(results[0]["lat"])
                        lon = float(results[0]["lon"])
                        st.session_state["lat_from_geocode"] = lat
                        st.session_state["lon_from_geocode"] = lon
                        st.success(f"📍 {lat:.5f}, {lon:.5f}")
                    else:
                        st.warning("Address not found — try a more specific query.")
                except Exception as exc:
                    st.error(f"Geocode failed: {exc}")
        else:
            st.warning("Enter an address first.")

    # Show current coords if resolved
    if "lat_from_geocode" in st.session_state:
        lat_disp = st.session_state["lat_from_geocode"]
        lon_disp = st.session_state["lon_from_geocode"]
        st.caption(f"Lat {lat_disp:.5f} · Lon {lon_disp:.5f}")

    st.markdown("---")
    st.caption("HaimOS · Two-process architecture\nFastAPI backend + Streamlit frontend")


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_dashboard, tab_nna = st.tabs(["📊 NEM Dashboard", "🗺️ NNA Map"])

# ── TAB 1: NEM Dashboard ──────────────────────────────────────────────────────
with tab_dashboard:
    st.header("NEM Dashboard")

    BACKEND = "http://localhost:8000"

    col1, col2 = st.columns([1, 1])
    with col1:
        region = st.selectbox("Region", ["NSW1", "VIC1", "QLD1", "SA1", "TAS1"], index=1)
    with col2:
        if st.button("Refresh snapshot", use_container_width=True):
            st.session_state.pop("nem_snapshot", None)

    if "nem_snapshot" not in st.session_state:
        with st.spinner("Fetching NEM snapshot…"):
            try:
                r = requests.get(f"{BACKEND}/api/nem/snapshot", params={"region": region}, timeout=15)
                r.raise_for_status()
                st.session_state["nem_snapshot"] = r.json()
            except Exception as exc:
                st.session_state["nem_snapshot"] = {"error": str(exc)}

    snap = st.session_state.get("nem_snapshot", {})
    if "error" in snap:
        st.warning(f"Backend unavailable: {snap['error']}\n\nStart the FastAPI server with `python backend/server.py`")
    else:
        latest = snap.get("latest_interval", {})
        if latest:
            st.metric("Spot Price ($/MWh)", f"${latest.get('spot_price', 0):,.2f}")
        forecast = snap.get("forecast", [])
        if forecast:
            import pandas as pd
            df = pd.DataFrame(forecast)
            st.subheader("Price Forecast")
            st.line_chart(df.set_index(df.columns[0])[["spot_price"]] if "spot_price" in df.columns else df)
        else:
            st.info("No forecast data returned from backend.")

# ── TAB 2: NNA Map ────────────────────────────────────────────────────────────
with tab_nna:
    render_nna_tab(show_leaderboard=True)
