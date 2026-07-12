"""
NNA Opportunity Parser
Reads DNSP system limitation / NNA xlsx files and returns structured
opportunity objects for the HaimOS NNA Map tab.

Supports: Ausgrid, AusNet, Jemena, Endeavour (+ stubs for others).
"""

from __future__ import annotations
import csv, json, re
from pathlib import Path
from typing import Any

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# ── Known DNSP colors & state metadata ──────────────────────────────────────
DNSP_META = {
    "Ausgrid":          {"color": "#f59e0b", "state": "NSW", "region": "Sydney / Hunter"},
    "Endeavour":        {"color": "#10b981", "state": "NSW", "region": "Central / South Coast NSW"},
    "Essential Energy": {"color": "#6366f1", "state": "NSW", "region": "Rural NSW"},
    "AusNet":           {"color": "#3b82f6", "state": "VIC", "region": "East Melbourne / Gippsland"},
    "Jemena":           {"color": "#8b5cf6", "state": "VIC", "region": "North-West Melbourne"},
    "CitiPower":        {"color": "#ec4899", "state": "VIC", "region": "Inner Melbourne"},
    "Powercor":         {"color": "#f43f5e", "state": "VIC", "region": "West / Central VIC"},
    "United Energy":    {"color": "#14b8a6", "state": "VIC", "region": "South-East Melbourne"},
    "Energex":          {"color": "#f97316", "state": "QLD", "region": "South-East QLD"},
    "Ergon":          {"color": "#a3e635", "state": "QLD", "region": "Regional QLD"},
    "Ergon Energy":   {"color": "#a3e635", "state": "QLD", "region": "Regional QLD"},
    "Essential Energy": {"color": "#6366f1", "state": "NSW", "region": "Rural NSW"},
    "Evoenergy":      {"color": "#fb923c", "state": "ACT", "region": "ACT"},
    "CitiPower":      {"color": "#ec4899", "state": "VIC", "region": "Inner Melbourne"},
    "Powercor":       {"color": "#f43f5e", "state": "VIC", "region": "West / Central VIC"},
    "United Energy":  {"color": "#14b8a6", "state": "VIC", "region": "South-East Melbourne"},
    "SA Power":         {"color": "#e879f9", "state": "SA",  "region": "South Australia"},
    "TasNetworks":      {"color": "#2dd4bf", "state": "TAS", "region": "Tasmania"},
    "Evoenergy":        {"color": "#fb923c", "state": "ACT", "region": "ACT"},
    "Western Power":    {"color": "#a78bfa", "state": "WA",  "region": "South-West WA"},
}

# ── Data directory ───────────────────────────────────────────────────────────
_ONEDRIVE_BASES = [
    Path.home() / "Library/CloudStorage/OneDrive-Veida/solar-tool-backup-20260209_135632",
    Path.home() / "Library/CloudStorage/OneDrive-Personal/solar-tool-backup-20260206_172613",
]
_NNA_DIR: Path | None = None
for _b in _ONEDRIVE_BASES:
    if (_b / "real_data/dnsp_nna").exists():
        _NNA_DIR = _b / "real_data/dnsp_nna"
        break


def _safe_float(v) -> float | None:
    try:
        f = float(str(v).strip().replace("\t", ""))
        if -90 <= f <= 90 or -180 <= f <= 180:
            return f
        return f
    except Exception:
        return None


def _str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


# ── Ausgrid parser ───────────────────────────────────────────────────────────
def _parse_ausgrid() -> list[dict]:
    if not _NNA_DIR or not _HAS_OPENPYXL:
        return []
    fpath = _NNA_DIR / "ausgrid_system_limitations_fy25.xlsx"
    if not fpath.exists():
        return []
    results = []
    try:
        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            # Find header row (contains 'Substation/Feeder Name' or 'Connection point ID')
            hdr_idx = None
            hdr = None
            for i, row in enumerate(rows):
                if any("Substation" in _str(c) or "Connection point ID" in _str(c) for c in row if c):
                    hdr_idx = i
                    hdr = row
                    break
            if hdr_idx is None:
                continue
            for row in rows[hdr_idx + 1:]:
                if not any(c for c in row):
                    continue
                # Map by position relative to known header columns
                name_col = next((i for i, h in enumerate(hdr) if h and ("Substation" in _str(h) or "Connection point" in _str(h))), 1)
                lat_col  = next((i for i, h in enumerate(hdr) if h and "Latitude" in _str(h) and "start" in _str(h).lower()), 4)
                lng_col  = next((i for i, h in enumerate(hdr) if h and ("Longit" in _str(h) or "Longitude" in _str(h)) and "start" in _str(h).lower()), 5)
                driver_col = next((i for i, h in enumerate(hdr) if h and "Constraint primary" in _str(h)), 3)
                season_col = next((i for i, h in enumerate(hdr) if h and "Peak season" in _str(h)), 2)
                # Deferral value
                defval_col = next((i for i, h in enumerate(hdr) if h and "Deferral Value" in _str(h)), None)
                # Demand reduction
                dr_col = next((i for i, h in enumerate(hdr) if h and "Demand reduction" in _str(h) and "(MW)" in _str(h)), None)
                # Investment cost
                capex_col = next((i for i, h in enumerate(hdr) if h and "capital cost" in _str(h).lower()), None)
                # Timing
                timing_col = next((i for i, h in enumerate(hdr) if h and "Proposed timing" in _str(h)), None)
                # Network element
                elem_col = next((i for i, h in enumerate(hdr) if h and "Network Element" in _str(h)), None)

                def get(col):
                    if col is None or col >= len(row):
                        return None
                    return row[col]

                name = _str(get(name_col))
                if not name or name.startswith("'") or not re.search(r'[A-Za-z]', name):
                    continue
                lat = _safe_float(get(lat_col))
                lng = _safe_float(get(lng_col))
                if lat is None or lng is None:
                    continue
                if not (-38 < lat < -28 and 148 < lng < 155):  # Ausgrid is Sydney/Hunter
                    continue

                timing = get(timing_col)
                timing_str = timing.year if hasattr(timing, 'year') else _str(timing)

                results.append({
                    "id": f"ausgrid_{_str(get(next((i for i,h in enumerate(hdr) if h and 'Asset ID' in _str(h)), 8)))}",
                    "name": name,
                    "dnsp": "Ausgrid",
                    "state": "NSW",
                    "lat": lat,
                    "lng": lng,
                    "constraint_driver": _str(get(driver_col)),
                    "peak_season": _str(get(season_col)),
                    "network_element": _str(get(elem_col)) if elem_col else "",
                    "demand_reduction_mw": _safe_float(get(dr_col)) if dr_col else None,
                    "deferral_value_m": _safe_float(get(defval_col)) if defval_col else None,
                    "capex_m": _safe_float(get(capex_col)) if capex_col else None,
                    "proposed_timing": str(timing_str) if timing_str else "",
                    "sheet": sheet_name,
                    "favourite": False,
                })
    except Exception as e:
        print(f"[nna_parser] Ausgrid error: {e}")
    return results


# ── AusNet parser ─────────────────────────────────────────────────────────────
# AusNet data is pivot-style — asset names across columns; no lat/lng in xlsx.
# We use a known substation coordinate lookup for VIC assets.
AUSNET_COORDS: dict[str, tuple[float, float]] = {
    "Bairnsdale": (-37.8481, 147.6213), "Benalla": (-36.5512, 145.9816),
    "Bayswater": (-37.8453, 145.2652), "Clyde North": (-38.1078, 145.3343),
    "Doreen": (-37.5855, 145.1524), "Epping": (-37.6444, 145.0312),
    "Kinglake": (-37.5214, 145.3392), "Leongatha": (-38.4747, 145.9454),
    "Lilydale": (-37.7524, 145.3452), "Morwell": (-38.2342, 146.3952),
    "Pakenham": (-38.0703, 145.4892), "Ringwood": (-37.8147, 145.2270),
    "Sale": (-38.1052, 147.0685), "Seaford": (-38.1025, 145.1370),
    "Shepparton": (-36.3806, 145.3989), "Springvale": (-37.9497, 145.1512),
    "Sunbury": (-37.5810, 144.7285), "Traralgon": (-38.1953, 146.5415),
    "Wangaratta": (-36.3581, 146.3125), "Wodonga": (-36.1213, 146.8890),
    "Healesville": (-37.6552, 145.5167), "Yallourn": (-38.1760, 146.3595),
    "Warragul": (-38.1541, 145.9342), "Warrnambool": (-38.3832, 142.4840),
}

def _parse_ausnet() -> list[dict]:
    if not _NNA_DIR or not _HAS_OPENPYXL:
        return []
    fpath = _NNA_DIR / "ausnet_system_limitations_2025.xlsx"
    if not fpath.exists():
        return []
    results = []
    try:
        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        ws = wb["System Limitation Report"]
        rows = list(ws.iter_rows(values_only=True))
        # Row layout: asset names in row 1 (index 1), driver in row 4 (index ~3)
        asset_row = next((r for r in rows if r[0] == "Asset Name"), None)
        driver_row = next((r for r in rows if r[0] == "Constraint primary driver"), None)
        timing_row = next((r for r in rows if r[0] and "timing" in _str(r[0]).lower()), None)
        season_row = next((r for r in rows if r[0] and "season" in _str(r[0]).lower()), None)

        if asset_row is None:
            return []
        for col_idx in range(1, len(asset_row)):
            asset_full = _str(asset_row[col_idx])
            if not asset_full:
                continue
            # Extract short name (e.g. "Bairnsdale (BDL)" → "Bairnsdale")
            short = re.split(r'\s*\(', asset_full)[0].strip()
            coords = AUSNET_COORDS.get(short)
            if not coords:
                # Try fuzzy match
                for k in AUSNET_COORDS:
                    if k.lower() in short.lower() or short.lower() in k.lower():
                        coords = AUSNET_COORDS[k]
                        break
            if not coords:
                continue
            driver = _str(driver_row[col_idx]) if driver_row else ""
            timing = _str(timing_row[col_idx]) if timing_row else ""
            season = _str(season_row[col_idx]) if season_row else ""
            results.append({
                "id": f"ausnet_{col_idx}_{short.replace(' ','_')}",
                "name": asset_full,
                "dnsp": "AusNet",
                "state": "VIC",
                "lat": coords[0],
                "lng": coords[1],
                "constraint_driver": driver,
                "peak_season": season,
                "network_element": "Zone Substation",
                "demand_reduction_mw": None,
                "deferral_value_m": None,
                "capex_m": None,
                "proposed_timing": timing,
                "sheet": "System Limitation Report",
                "favourite": False,
            })
    except Exception as e:
        print(f"[nna_parser] AusNet error: {e}")
    return results


# ── Jemena parser ─────────────────────────────────────────────────────────────
JEMENA_COORDS: dict[str, tuple[float, float]] = {
    "Airport West": (-37.7244, 144.8797), "Broadmeadows": (-37.6891, 144.9197),
    "Broadmeadows South": (-37.7050, 144.9250), "Braybrook": (-37.7897, 144.8542),
    "Brunswick": (-37.7688, 144.9608), "Campbellfield": (-37.6717, 144.9564),
    "Coburg": (-37.7436, 144.9660), "Craigieburn": (-37.5997, 144.9347),
    "Dallas": (-37.6689, 144.9364), "Deer Park": (-37.7834, 144.7780),
    "Doncaster": (-37.7878, 145.1218), "Epping": (-37.6449, 145.0087),
    "Essendon": (-37.7450, 144.9156), "Footscray": (-37.8004, 144.8997),
    "Heidelberg": (-37.7553, 145.0614), "Keilor": (-37.7247, 144.8378),
    "Kew": (-37.8010, 145.0333), "Lalor": (-37.6600, 145.0133),
    "Laverton North": (-37.8300, 144.7950), "Meadow Heights": (-37.6617, 144.9250),
    "Melton": (-37.6850, 144.5803), "Mernda": (-37.6000, 145.0817),
    "Mickleham": (-37.5578, 144.9175), "Milleara": (-37.7556, 144.8372),
    "Moonee Ponds": (-37.7617, 144.9178), "Moreland": (-37.7558, 144.9614),
    "Northcote": (-37.7697, 145.0036), "Pascoe Vale": (-37.7292, 144.9428),
    "Preston": (-37.7461, 145.0136), "Reservoir": (-37.7169, 145.0169),
    "Rosanna": (-37.7569, 145.0644), "Roxburgh Park": (-37.6364, 144.9386),
    "Somerton": (-37.6256, 144.9578), "Sunshine": (-37.7897, 144.8297),
    "Thomastown": (-37.6878, 145.0239), "Tullamarine": (-37.7128, 144.8761),
    "Wollert": (-37.5733, 145.0303), "Woodlands": (-37.6383, 144.9033),
    "Sunbury": (-37.5810, 144.7285),
}

def _parse_jemena() -> list[dict]:
    if not _NNA_DIR or not _HAS_OPENPYXL:
        return []
    fpath = _NNA_DIR / "victoria/Jemena_system_limitations_2025.xlsx"
    if not fpath.exists():
        return []
    results = []
    try:
        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        hdr = rows[0]
        col = {_str(h): i for i, h in enumerate(hdr) if h}
        for row in rows[1:]:
            def g(key):
                idx = col.get(key)
                return row[idx] if idx is not None and idx < len(row) else None
            name = _str(g("Asset_name"))
            if not name:
                continue
            # Match to coords
            short = re.split(r'\s+Zone\s+', name, flags=re.I)[0].strip()
            coords = JEMENA_COORDS.get(short)
            if not coords:
                for k in JEMENA_COORDS:
                    if k.lower() in short.lower():
                        coords = JEMENA_COORDS[k]
                        break
            if not coords:
                continue
            results.append({
                "id": f"jemena_{_str(g('Asset_code'))}",
                "name": name,
                "dnsp": "Jemena",
                "state": "VIC",
                "lat": coords[0],
                "lng": coords[1],
                "constraint_driver": _str(g("investment_description")),
                "peak_season": "",
                "network_element": _str(g("network_element")),
                "demand_reduction_mw": None,
                "deferral_value_m": None,
                "capex_m": None,
                "proposed_timing": "",
                "sheet": "Sheet1",
                "favourite": False,
            })
    except Exception as e:
        print(f"[nna_parser] Jemena error: {e}")
    return results


# ── Endeavour parser ───────────────────────────────────────────────────────────
def _parse_endeavour() -> list[dict]:
    if not _NNA_DIR or not _HAS_OPENPYXL:
        return []
    fpath = _NNA_DIR / "endeavour_network_capacity_20260124.xlsx"
    if not fpath.exists():
        return []
    results = []
    try:
        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            hdr = None
            hdr_idx = None
            for i, row in enumerate(rows):
                if any(c and re.search(r'lat|substation|site|zone|name', _str(c), re.I) for c in row):
                    hdr = row
                    hdr_idx = i
                    break
            if hdr is None:
                continue
            col = {}
            for i, h in enumerate(hdr):
                s = _str(h).lower()
                if 'lat' in s:
                    col['lat'] = i
                elif 'lon' in s or 'lng' in s:
                    col['lng'] = i
                elif 'name' in s or 'substation' in s or 'site' in s:
                    col.setdefault('name', i)
                elif 'constraint' in s or 'driver' in s or 'reason' in s:
                    col['driver'] = i
                elif 'season' in s:
                    col['season'] = i
                elif 'deferral' in s:
                    col['deferral'] = i
                elif 'reduction' in s and 'mw' in s:
                    col['dr_mw'] = i
                elif 'timing' in s or 'year' in s:
                    col['timing'] = i

            if 'lat' not in col or 'lng' not in col:
                continue

            for row in rows[hdr_idx + 1:]:
                if not any(c for c in row):
                    continue
                def g(key):
                    idx = col.get(key)
                    return row[idx] if idx is not None and idx < len(row) else None
                name = _str(g('name'))
                lat = _safe_float(g('lat'))
                lng = _safe_float(g('lng'))
                if not name or lat is None or lng is None:
                    continue
                results.append({
                    "id": f"endeavour_{name.replace(' ','_')[:30]}",
                    "name": name,
                    "dnsp": "Endeavour",
                    "state": "NSW",
                    "lat": lat,
                    "lng": lng,
                    "constraint_driver": _str(g('driver')),
                    "peak_season": _str(g('season')),
                    "network_element": "",
                    "demand_reduction_mw": _safe_float(g('dr_mw')),
                    "deferral_value_m": _safe_float(g('deferral')),
                    "capex_m": None,
                    "proposed_timing": _str(g('timing')),
                    "sheet": sheet_name,
                    "favourite": False,
                })
    except Exception as e:
        print(f"[nna_parser] Endeavour error: {e}")
    return results


# ── Public API ────────────────────────────────────────────────────────────────
_CACHE: list[dict] | None = None

# ── ENA proposed investment CSV (covers Energex, Ergon, TasNetworks, Essential, etc.) ──
_ENA_CSV_NETWORK_MAP = {
    "Energex":          {"dnsp": "Energex",          "state": "QLD"},
    "Ergon Energy":     {"dnsp": "Ergon Energy",     "state": "QLD"},
    "TasNetworks":      {"dnsp": "TasNetworks",      "state": "TAS"},
    "Essential Energy": {"dnsp": "Essential Energy", "state": "NSW"},
    "Evoenergy":        {"dnsp": "Evoenergy",        "state": "ACT"},
    "CitiPower":        {"dnsp": "CitiPower",        "state": "VIC"},
    "Powercor":         {"dnsp": "Powercor",         "state": "VIC"},
    "United Energy":    {"dnsp": "United Energy",    "state": "VIC"},
}
# DNSPs already parsed from xlsx — skip duplicates from CSV
_ENA_CSV_SKIP_NETWORKS = {"Ausgrid", "Ausnet Services", "SA Power Networks", "Endeavour Energy", "Jemena"}

def _parse_ena_csv() -> list[dict]:
    for base in _ONEDRIVE_BASES:
        csv_path = base / "data/geospatial/ena_proposed_investment.csv"
        if csv_path.exists():
            break
    else:
        return []
    results = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                network = row.get("network", "").strip()
                if network in _ENA_CSV_SKIP_NETWORKS or network not in _ENA_CSV_NETWORK_MAP:
                    continue
                lat = _safe_float(row.get("latitude"))
                lng = _safe_float(row.get("longitude"))
                if lat is None or lng is None:
                    continue
                mapping = _ENA_CSV_NETWORK_MAP[network]
                dnsp = mapping["dnsp"]
                state = mapping["state"]
                name = row.get("asset_name", "").strip()
                if not name:
                    continue
                deferral_m = _safe_float(row.get("annual_deferral_pool"))
                capex_m = _safe_float(row.get("deferrable_invest"))
                # Estimate demand reduction from deferral pool using ADV formula
                dr_mw = None
                if deferral_m and deferral_m > 0:
                    wacc = _safe_float(row.get("wacc_rate")) or 0.0262
                    depr = _safe_float(row.get("depr_rate")) or 0.033
                    rate = wacc + depr
                    if capex_m and rate:
                        dr_mw = round(capex_m / (rate * 1000) * 10, 2) if capex_m > 0 else None
                results.append({
                    "id": f"ena_{row.get('asset_code', name).replace(' ','_')[:40]}",
                    "name": name,
                    "dnsp": dnsp,
                    "state": state,
                    "lat": lat,
                    "lng": lng,
                    "constraint_driver": row.get("investment_description", "").strip()[:120],
                    "peak_season": row.get("constraint_season", "").strip(),
                    "network_element": row.get("network_element_str", "").strip(),
                    "demand_reduction_mw": dr_mw,
                    "deferral_value_m": deferral_m,
                    "capex_m": capex_m,
                    "proposed_timing": row.get("invest_year_str", "").strip(),
                    "sheet": "",
                    "favourite": False,
                    "is_nna": False,
                })
    except Exception as e:
        print(f"[nna_parser] ENA CSV error: {e}")
    return results


def load_opportunities(force: bool = False) -> list[dict]:
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    opps = []
    opps += _parse_ausgrid()
    opps += _parse_ausnet()
    opps += _parse_jemena()
    opps += _parse_endeavour()
    opps += _parse_sapn()
    opps += _parse_ena_csv()

    # Deduplicate by id
    seen = set()
    unique = []
    for o in opps:
        if o["id"] not in seen:
            seen.add(o["id"])
            # Attach color and metadata
            meta = DNSP_META.get(o["dnsp"], {})
            o["color"] = meta.get("color", "#94a3b8")
            o["region"] = meta.get("region", "")
            # xlsx-parsed entries are confirmed NNA register items; ENA CSV are deferrable investments
            o.setdefault("is_nna", True)
            unique.append(o)

    _CACHE = unique
    return _CACHE


def get_dnsp_list() -> list[str]:
    return sorted(DNSP_META.keys())


# ── SAPN (SA Power Networks) parser ──────────────────────────────────────────
def _parse_sapn() -> list[dict]:
    if not _NNA_DIR or not _HAS_OPENPYXL:
        return []
    results = []
    sa_dir = _NNA_DIR / "south_australia"
    for fname in ["SAPN_system_limitations_2026.xlsx", "SAPN_system_limitations_2027.xlsx"]:
        fpath = sa_dir / fname
        if not fpath.exists():
            continue
        year = "2026" if "2026" in fname else "2027"
        try:
            wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                if sheet_name.lower() == "summary":
                    continue
                ws = wb[sheet_name]
                kv: dict = {}
                for row in ws.iter_rows(values_only=True):
                    if row[1] is not None and row[2] is not None:
                        kv[_str(row[1]).strip().lower()] = row[2]
                # Extract fields
                lat = _safe_float(kv.get("constraint location lattitude") or kv.get("constraint location latitude"))
                lng = _safe_float(kv.get("constraint location longitude"))
                if lat is None or lng is None:
                    continue
                if not (-38.5 < lat < -26 and 129 < lng < 141):  # SA bounds
                    continue
                name = _str(kv.get("rin asset id") or sheet_name)
                driver = _str(kv.get("constraint primary driver", ""))
                elem = _str(kv.get("network element", ""))
                # deferral / capex from summary sheet if available
                results.append({
                    "id": f"sapn_{year}_{sheet_name.replace(' ','_')[:30]}",
                    "name": name,
                    "dnsp": "SA Power",
                    "state": "SA",
                    "lat": lat,
                    "lng": lng,
                    "constraint_driver": driver,
                    "peak_season": "Summer",
                    "network_element": elem,
                    "demand_reduction_mw": _safe_float(kv.get("load at risk (mw)") or kv.get("demand reduction")),
                    "deferral_value_m": None,
                    "capex_m": None,
                    "proposed_timing": year,
                    "sheet": sheet_name,
                    "favourite": False,
                })
        except Exception as e:
            print(f"[nna_parser] SAPN {fname} error: {e}")
    # Deduplicate by name — keep 2026 entry if both years exist
    seen_names: set = set()
    unique = []
    for o in results:
        if o["name"] not in seen_names:
            seen_names.add(o["name"])
            unique.append(o)
    return unique


if __name__ == "__main__":
    opps = load_opportunities(force=True)
    print(f"Loaded {len(opps)} NNA opportunities")
    for dnsp in set(o["dnsp"] for o in opps):
        count = sum(1 for o in opps if o["dnsp"] == dnsp)
        print(f"  {dnsp}: {count}")
    if opps:
        import json
        print("\nSample:", json.dumps(opps[0], indent=2, default=str))
