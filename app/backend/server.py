#!/usr/bin/env python3
"""
HaimOS FastAPI backend
Serves graph data, vault chat (RAG), stats, agent runner, and VS Code launcher.
"""
import os
import re
import re as _re
import subprocess
import sys
import uuid as _uuid
import json as _json
from pathlib import Path
from typing import Optional

# ── Resolve .env ──────────────────────────────────────────────────────────────
VAULT_ROOT = Path(__file__).resolve().parent.parent.parent

def load_env():
    for candidate in [VAULT_ROOT / ".env", Path(__file__).parent / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return

load_env()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    import threading
    threading.Thread(target=_start_code_server, daemon=True).start()
    yield

app = FastAPI(title="HaimOS API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SKIP_DIRS  = {".obsidian", ".venv", "06_Raw_Data"}
INDEX_PATH = VAULT_ROOT / "06_Raw_Data" / ".chroma_index"
VENV_PY    = VAULT_ROOT / ".venv" / "bin" / "python3"

# RGB ints from Obsidian graph.json → hex
FOLDER_COLORS = {
    "00_Inbox":          "#ffff00",
    "01_Journal":        "#a8d8a8",
    "02_Projects":       "#4199e1",
    "03_Projects":       "#4199e1",
    "00_Master_Context": "#9835fa",
    "01_State":          "#33dddd",
    "05_System":         "#808000",
    "05_Personal_Admin": "#996666",
    "04_Archive":        "#808080",
}
TAG_COLORS = {
    "email":   "#ff4040",
    "trello":  "#0000ff",
    "onenote": "#7bffff",
}
DEFAULT_COLOR = "#6898d4"

_graph_cache  = None
_vscode_proc  = None
VSCODE_PORT   = 8766

_vscode2_proc = None
VSCODE2_PORT  = 8767


def _find_code_server():
    import shutil
    return (shutil.which("code-server") or
            ("/opt/homebrew/opt/code-server/bin/code-server"
             if Path("/opt/homebrew/opt/code-server/bin/code-server").exists() else None))


def _patch_copilot_bundles(ext_dir: Path):
    """Apply all Copilot Chat bundle patches — idempotent, safe to call every boot."""
    for bundle in sorted(ext_dir.glob("github.copilot-chat-*/dist/extension.js"), reverse=True):
        try:
            text = bundle.read_text(encoding="utf-8")
        except Exception:
            continue

        changed = False

        # ── Patch 1: mgt.clearMarks guard ────────────────────────────────────
        OLD_MGT = 'var mgt=globalThis.MonacoPerformanceMarks??fui(),Agt="code/chat/ext/"'
        NEW_MGT = (
            'var mgt=globalThis.MonacoPerformanceMarks??fui();'
            'typeof mgt.mark!="function"&&(mgt.mark=()=>{});'
            'typeof mgt.getMarks!="function"&&(mgt.getMarks=()=>[]);'
            'typeof mgt.clearMarks!="function"&&(mgt.clearMarks=()=>{});'
            'var Agt="code/chat/ext/"'
        )
        if OLD_MGT in text:
            text = text.replace(OLD_MGT, NEW_MGT, 1)
            changed = True

        # ── Patch 2: image dimension guard (prevents 400 "image > 8000px") ──
        OLD_E0N = (
            'function E0n(t){let e={"/9j/":"image/jpeg",iVBOR:"image/png",'
            'R0lGOD:"image/gif",UklGR:"image/webp"};'
            'for(let n of Object.keys(e))if(t.startsWith(n))'
            'return`data:${e[n]};base64,${t}`;return t}'
        )
        if OLD_E0N in text and 'MAX_IMG_DIM' not in text:
            NEW_E0N = (
                'function E0n(t){'
                'const MAX_IMG_DIM=7800;'
                'function _r32be(a,i){return(a[i]<<24|a[i+1]<<16|a[i+2]<<8|a[i+3])>>>0}'
                'function _dims(a){'
                'if(a[0]===137&&a[1]===80&&a[2]===78&&a[3]===71)return[_r32be(a,16),_r32be(a,20)];'
                'if(a[0]===0xFF&&a[1]===0xD8){'
                'let i=2;while(i+8<a.length){'
                'if(a[i]!==0xFF)break;'
                'let m=a[i+1],l=(a[i+2]<<8)|a[i+3];'
                'if((m>=0xC0&&m<=0xC3)||(m>=0xC5&&m<=0xC7)||(m>=0xC9&&m<=0xCB)||(m>=0xCD&&m<=0xCF))'
                'return[(a[i+7]<<8)|a[i+8],(a[i+5]<<8)|a[i+6]];'
                'i+=2+l;}}return null;}'
                "const STUB='R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';"
                'let e={"/9j/":"image/jpeg",iVBOR:"image/png",R0lGOD:"image/gif",UklGR:"image/webp"};'
                'for(let n of Object.keys(e)){'
                'if(t.startsWith(n)){'
                'try{'
                'const raw=typeof Buffer!=="undefined"?Buffer.from(t,"base64"):Uint8Array.from(atob(t),c=>c.charCodeAt(0));'
                'const d=_dims(raw);'
                "if(d&&(d[0]>MAX_IMG_DIM||d[1]>MAX_IMG_DIM)){"
                "console.warn('[HaimOS] Image too large ('+d[0]+'x'+d[1]+'), stripping');"
                'return`data:image/gif;base64,${STUB}`;}'
                '}catch(ex){}'
                'return`data:${e[n]};base64,${t}`;'
                '}}'
                'return t;}'
            )
            text = text.replace(OLD_E0N, NEW_E0N, 1)
            changed = True

        if changed:
            bundle.write_text(text, encoding="utf-8")
        return  # only patch the newest version


def _start_code_server():
    global _vscode_proc
    cs = _find_code_server()
    if not cs:
        return
    if _vscode_proc and _vscode_proc.poll() is None:
        return  # already running
    cs_data_dir = VAULT_ROOT / "06_Raw_Data" / ".code-server-data"
    cs_ext_dir  = VAULT_ROOT / "06_Raw_Data" / ".vscode-extensions"
    cs_data_dir.mkdir(parents=True, exist_ok=True)
    cs_ext_dir.mkdir(parents=True, exist_ok=True)
    _patch_copilot_bundles(cs_ext_dir)
    _vscode_proc = subprocess.Popen(
        [cs, "--port", str(VSCODE_PORT), "--auth", "none",
         "--disable-telemetry", "--disable-workspace-trust",
         "--disable-update-check",
         "--user-data-dir", str(cs_data_dir),
         "--extensions-dir", str(cs_ext_dir),
         str(VAULT_ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={
            **os.environ,
            "DISABLE_WORKSPACE_TRUST": "1",
            "VSCODE_GALLERY_SERVICE_URL": "https://marketplace.visualstudio.com/_apis/public/gallery",
            "VSCODE_GALLERY_CACHE_URL":   "https://vscode.blob.core.windows.net/gallery/index",
            "VSCODE_GALLERY_ITEM_URL":    "https://marketplace.visualstudio.com/items",
        }
    )




def _start_code_server2(folder: str):
    global _vscode2_proc
    cs = _find_code_server()
    if not cs:
        return
    # Kill existing instance if running
    if _vscode2_proc and _vscode2_proc.poll() is None:
        _vscode2_proc.terminate()
        _vscode2_proc.wait(timeout=5)
    cs_data_dir = VAULT_ROOT / "06_Raw_Data" / ".code-server-data-2"
    cs_ext_dir  = VAULT_ROOT / "06_Raw_Data" / ".vscode-extensions"
    cs_data_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(folder).expanduser().resolve()
    _vscode2_proc = subprocess.Popen(
        [cs, "--port", str(VSCODE2_PORT), "--auth", "none",
         "--disable-telemetry", "--disable-workspace-trust",
         "--disable-update-check",
         "--user-data-dir", str(cs_data_dir),
         "--extensions-dir", str(cs_ext_dir),
         str(workspace)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={
            **os.environ,
            "DISABLE_WORKSPACE_TRUST": "1",
            "VSCODE_GALLERY_SERVICE_URL": "https://marketplace.visualstudio.com/_apis/public/gallery",
            "VSCODE_GALLERY_CACHE_URL":   "https://vscode.blob.core.windows.net/gallery/index",
            "VSCODE_GALLERY_ITEM_URL":    "https://marketplace.visualstudio.com/items",
        }
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_node_color(rel_path: Path) -> str:
    parts = rel_path.parts
    # Tag-based
    for tag, color in TAG_COLORS.items():
        if parts and parts[-1].startswith(f"{tag}_"):
            return color
    # Folder-based
    for part in parts:
        if part in FOLDER_COLORS:
            return FOLDER_COLORS[part]
    return DEFAULT_COLOR


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/vault/graph")
async def get_graph(limit: int = 20000, folder: Optional[str] = None):
    global _graph_cache

    all_notes = {}
    for md in VAULT_ROOT.rglob("*.md"):
        try:
            rel = md.relative_to(VAULT_ROOT)
        except ValueError:
            continue
        if set(rel.parts) & SKIP_DIRS:
            continue
        if folder and not str(rel).startswith(folder):
            continue
        all_notes[md.stem] = (md, rel)

    # Build edge list
    out_deg: dict[str, int] = {}
    in_deg:  dict[str, int] = {}
    raw_edges = []

    for name, (path, rel) in all_notes.items():
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        for link in re.findall(r'\[\[([^\]|#\n]+)', text):
            link = link.strip()
            if link in all_notes and link != name:
                raw_edges.append((name, link))
                out_deg[name] = out_deg.get(name, 0) + 1
                in_deg[link]  = in_deg.get(link, 0) + 1

    degree = {n: out_deg.get(n, 0) + in_deg.get(n, 0) for n in all_notes}
    top    = sorted(degree, key=lambda x: degree[x], reverse=True)[:limit]
    top_set = set(top)

    nodes = []
    for name in top:
        _, rel = all_notes[name]
        nodes.append({
            "id":     name,
            "label":  name[:50],
            "color":  get_node_color(rel),
            "size":   min(3 + degree[name] * 0.4, 14),
            "folder": rel.parts[0] if rel.parts else "",
            "path":   str(rel),
            "orphan": degree[name] == 0,
        })

    edges = [
        {"source": s, "target": t}
        for s, t in raw_edges
        if s in top_set and t in top_set
    ]

    return {"nodes": nodes, "edges": edges, "total": len(all_notes)}


@app.get("/api/vault/stats")
async def get_stats():
    total  = 0
    counts: dict[str, int] = {}
    for md in VAULT_ROOT.rglob("*.md"):
        try:
            rel = md.relative_to(VAULT_ROOT)
        except ValueError:
            continue
        if set(rel.parts) & SKIP_DIRS:
            continue
        total += 1
        folder = rel.parts[0] if rel.parts else "root"
        counts[folder] = counts.get(folder, 0) + 1

    all_mds = sorted(
        [m for m in VAULT_ROOT.rglob("*.md")
         if not (set(m.relative_to(VAULT_ROOT).parts) & SKIP_DIRS)],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )[:10]

    recent = [
        {"name": f.stem, "path": str(f.relative_to(VAULT_ROOT)), "modified": f.stat().st_mtime}
        for f in all_mds
    ]
    return {"total": total, "by_folder": counts, "recent": recent}


@app.post("/api/chat")
async def chat(body: dict):
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "No query")

    try:
        import chromadb
        from openai import OpenAI

        client     = chromadb.PersistentClient(path=str(INDEX_PATH))
        collection = client.get_collection("haimosvault")
        oai        = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        embed   = oai.embeddings.create(model="text-embedding-3-small", input=query[:6000])
        vector  = embed.data[0].embedding

        results = collection.query(
            query_embeddings=[vector],
            n_results=8,
            include=["documents", "metadatas"]
        )

        ids      = results.get("ids", [[]])[0]
        docs     = results.get("documents", [[]])[0]
        context  = "\n\n".join(f"[{i+1}] {d[:800]}" for i, d in enumerate(docs))

        resp = oai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content":
                    f"You are HaimOS — Haim Ptasznik's personal AI. "
                    f"Answer concisely using vault context below.\n\nVAULT:\n{context}"},
                {"role": "user", "content": query}
            ]
        )
        return {"answer": resp.choices[0].message.content, "sources": ids[:8]}

    except Exception as e:
        return {"answer": f"Error: {e}", "sources": []}


@app.post("/api/agents/run")
async def run_agent(body: dict):
    ALLOWED = {
        "chatgpt_context.py", "semantic_linker.py",
        "process_inbox.py", "ingest_onenote_veida.py",
    }
    script = body.get("script", "")
    if script not in ALLOWED:
        raise HTTPException(403, f"Script not in allowed list: {ALLOWED}")

    script_path = VAULT_ROOT / "06_Raw_Data" / script
    if not script_path.exists():
        raise HTTPException(404, "Script not found")

    args = body.get("args", [])
    result = subprocess.run(
        [str(VENV_PY), str(script_path)] + args,
        capture_output=True, text=True, timeout=60, cwd=str(VAULT_ROOT)
    )
    return {
        "stdout":     result.stdout[-4000:],
        "stderr":     result.stderr[-1000:],
        "returncode": result.returncode,
    }


@app.get("/api/vscode/url")
async def vscode_url():
    """Returns the code-server URL. Server is started automatically on boot."""
    if not _find_code_server():
        return {"error": "code-server not installed"}
    return {"url": f"http://127.0.0.1:{VSCODE_PORT}"}


@app.post("/api/vscode/start")
async def start_vscode():
    """Legacy endpoint — restarts code-server if it crashed."""
    _start_code_server()
    import asyncio; await asyncio.sleep(2)
    return {"url": f"http://127.0.0.1:{VSCODE_PORT}"}


@app.post("/api/vscode2/start")
async def start_vscode2(body: dict):
    """Start a second code-server instance for a given folder path."""
    folder = body.get("folder", str(VAULT_ROOT))
    if not Path(folder).expanduser().exists():
        return {"error": f"Folder not found: {folder}"}
    _start_code_server2(folder)
    import asyncio; await asyncio.sleep(2)
    return {"url": f"http://127.0.0.1:{VSCODE2_PORT}", "folder": folder}


@app.get("/api/vscode2/status")
async def vscode2_status():
    """Return whether the second code-server is running and on which port."""
    running = _vscode2_proc is not None and _vscode2_proc.poll() is None
    return {"running": running, "port": VSCODE2_PORT}


# ── NEM / AEMO Market Data ────────────────────────────────────────────────────

@app.get("/api/nem/prices")
async def nem_prices(region: str = "VIC1"):
    """
    Live 5-min NEM wholesale spot prices for today from NEMWeb DispatchIS.
    Includes all 10 FCAS market prices in the same response.

    Query params:
      region: NEM region code — NSW1, VIC1, QLD1, SA1, TAS1 (default VIC1)
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    try:
        import sys as _sys
        _nem_dir = str(Path(__file__).parent)
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from nem.aemo_fetch import fetch_todays_prices, today_date_str
        df = fetch_todays_prices(region)
        if df.empty:
            return {"region": region, "date": today_date_str(), "intervals": [], "count": 0}
        records = df.to_dict(orient="records")
        # Convert Timestamps to ISO strings for JSON serialisation
        for r in records:
            if hasattr(r.get("timestamp"), "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()
        return {"region": region, "date": today_date_str(), "intervals": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/forecast")
async def nem_forecast(region: str = "VIC1"):
    """
    Forward price forecast: P5MIN (~1 h ahead, 5-min) merged with
    Pre-dispatch (rest-of-day, 30-min).

    Query params:
      region: NEM region code (default VIC1)
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    try:
        import sys as _sys
        _nem_dir = str(Path(__file__).parent)
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from nem.aemo_fetch import merge_forward_forecasts, today_date_str
        df = merge_forward_forecasts(region)
        if df.empty:
            return {"region": region, "forecast": [], "count": 0}
        records = df.to_dict(orient="records")
        for r in records:
            if hasattr(r.get("timestamp"), "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()
        return {"region": region, "forecast": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/snapshot")
async def nem_snapshot(region: str = "VIC1"):
    """
    Single-call snapshot: latest spot price + FCAS prices + forward forecast.
    Ideal for a dashboard widget that needs everything in one request.

    Query params:
      region: NEM region code (default VIC1)
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    try:
        import sys as _sys
        _nem_dir = str(Path(__file__).parent)
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from nem.aemo_fetch import fetch_todays_prices, merge_forward_forecasts, today_date_str
        import asyncio

        spot_df, fcast_df = await asyncio.gather(
            asyncio.get_event_loop().run_in_executor(None, fetch_todays_prices, region),
            asyncio.get_event_loop().run_in_executor(None, merge_forward_forecasts, region),
        )

        latest = {}
        if not spot_df.empty:
            row = spot_df.iloc[-1].to_dict()
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()
            latest = row

        fcast_records = []
        if not fcast_df.empty:
            fcast_records = fcast_df.to_dict(orient="records")
            for r in fcast_records:
                if hasattr(r.get("timestamp"), "isoformat"):
                    r["timestamp"] = r["timestamp"].isoformat()

        spot_records = []
        if not spot_df.empty:
            spot_records = spot_df.tail(288).to_dict(orient="records")  # last 24 h
            for r in spot_records:
                if hasattr(r.get("timestamp"), "isoformat"):
                    r["timestamp"] = r["timestamp"].isoformat()

        return {
            "region": region,
            "date": today_date_str(),
            "latest_interval": latest,
            "today_history": spot_records,
            "forward_forecast": fcast_records,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/dispatch")
async def nem_dispatch(
    region: str = "VIC1",
    bess_mw: float = 5.0,
    bess_mwh: float = 10.0,
    enable_fcas: bool = True,
    strategy: str = "co_optimised_revenue_max",
    solar_dc_mw: float = 0.0,
    solar_lat: float = -37.8136,
    solar_lon: float = 144.9631,
):
    """
    Run the BESS dispatch algorithm against today's live AEMO 5-min spot prices.

    Dispatch decisions are driven by the named strategy — charge/discharge thresholds
    are derived dynamically from forecast + backcast percentile signals, not fixed values.

    Query params:
      region:    NEM region (default VIC1)
      bess_mw:   BESS inverter power MW (default 5.0)
      bess_mwh:  BESS energy capacity MWh (default 10.0)
      enable_fcas: Override FCAS flag (strategy value preferred — use this to force-disable)
      strategy:  Dispatch strategy ID (default: co_optimised_revenue_max).
                 See /api/nem/dispatch/strategies for all available options.
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    try:
        import asyncio
        import sys as _sys
        _nem_dir = str(Path(__file__).parent / "nem")
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from dispatch_runner import BESSConfig, run_dispatch
        from aemo_fetch import fetch_todays_prices

        config = BESSConfig(
            bess_power_mw=bess_mw,
            bess_energy_mwh=bess_mwh,
            enable_fcas=enable_fcas,
            nem_region=region,
            solar_dc_mw=solar_dc_mw,
            solar_lat=solar_lat,
            solar_lon=solar_lon,
        )

        price_df = await asyncio.get_event_loop().run_in_executor(
            None, fetch_todays_prices, region
        )
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_dispatch, price_df, config, strategy
        )
        result["region"] = region
        result["bess_params"] = {
            "bess_mw": bess_mw, "bess_mwh": bess_mwh,
            "enable_fcas": enable_fcas,
            "strategy": strategy,
            "solar_dc_mw": solar_dc_mw,
        }
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/dispatch/strategies")
async def nem_dispatch_strategies():
    """
    List all available BESS dispatch strategies.

    Returns each strategy with its ID, name, description, category, and
    provider specification notes — the spec sheet for implementing the
    algorithm in an asset controller (EMS/BMS/SCADA).
    """
    try:
        import sys as _sys
        _nem_dir = str(Path(__file__).parent / "nem")
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from dispatch_strategies import list_strategies, DEFAULT_STRATEGY_ID
        return {
            "default_strategy": DEFAULT_STRATEGY_ID,
            "strategies": list_strategies(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/dispatch/compare")
async def nem_dispatch_compare(
    region: str = "VIC1",
    bess_mw: float = 5.0,
    bess_mwh: float = 10.0,
    strategies: str = "co_optimised_revenue_max,fcas_only,arb_only",
):
    """
    Run multiple dispatch strategies against today's live prices and return
    side-by-side comparison results.

    Query params:
      region:     NEM region (default VIC1)
      bess_mw:    BESS inverter power MW (default 5.0)
      bess_mwh:   BESS energy capacity MWh (default 10.0)
      strategies: Comma-separated list of strategy IDs to compare.
                  See /api/nem/dispatch/strategies for valid IDs.
                  Default: "co_optimised_revenue_max,fcas_only,arb_only"

    Returns:
      {
        "comparison": { <strategy_id>: {strategy_name, total_revenue, arb_revenue,
                                         fcas_revenue, intervals_dispatched, rank} },
        "results":    { <strategy_id>: full interval-level result }
      }
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    strategy_ids = [s.strip() for s in strategies.split(",") if s.strip()]
    if not strategy_ids:
        raise HTTPException(400, "No strategies specified")
    if len(strategy_ids) > 6:
        raise HTTPException(400, "Maximum 6 strategies per comparison")
    try:
        import asyncio
        import sys as _sys
        _nem_dir = str(Path(__file__).parent / "nem")
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from dispatch_runner import BESSConfig, run_dispatch_compare
        from aemo_fetch import fetch_todays_prices

        config = BESSConfig(
            bess_power_mw=bess_mw,
            bess_energy_mwh=bess_mwh,
            nem_region=region,
        )
        price_df = await asyncio.get_event_loop().run_in_executor(
            None, fetch_todays_prices, region
        )
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_dispatch_compare, price_df, strategy_ids, config
        )
        result["region"] = region
        result["bess_params"] = {"bess_mw": bess_mw, "bess_mwh": bess_mwh}
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nem/backcast/compare")
async def nem_backcast_compare(
    region: str = "VIC1",
    days: int = 365,
    bess_mw: float = 5.0,
    bess_mwh: float = 10.0,
    strategies: str = "all",
    solar_dc_mw: float = 0.0,
    solar_lat: float = -37.8136,
    solar_lon: float = 144.9631,
):
    """
    Run all (or selected) dispatch strategies over historical AEMO spot prices
    and return side-by-side monthly revenue + YTD totals.

    NOTE: FCAS revenue shows $0 in backcast — historical MMSDM DISPATCHPRICE
    files contain spot prices only.  The live Digital Twin endpoint includes
    full real-time FCAS co-optimisation.

    Query params:
      region:     NEM region (default VIC1)
      days:       Lookback window in days, 7–730 (default 365)
      bess_mw:    BESS inverter power MW (default 5.0)
      bess_mwh:   BESS energy capacity MWh (default 10.0)
      strategies: Comma-separated strategy IDs, or "all" (default all)

    Returns:
      { region, days, ytd_year,
        strategies: { <id>: { strategy_name, monthly, ytd_revenue_aud,
                               total_revenue_aud, arb_revenue_aud, fcas_note } } }
    """
    if region not in ("NSW1", "VIC1", "QLD1", "SA1", "TAS1"):
        raise HTTPException(400, f"Invalid region: {region}")
    if days < 7 or days > 730:
        raise HTTPException(400, "days must be between 7 and 730")
    strategy_ids = (
        ["all"] if strategies.strip() == "all"
        else [s.strip() for s in strategies.split(",") if s.strip()]
    )
    try:
        import asyncio
        import sys as _sys
        _nem_dir = str(Path(__file__).parent / "nem")
        if _nem_dir not in _sys.path:
            _sys.path.insert(0, _nem_dir)
        from dispatch_runner import BESSConfig, run_backcast

        config = BESSConfig(
            bess_power_mw=bess_mw,
            bess_energy_mwh=bess_mwh,
            nem_region=region,
            solar_dc_mw=solar_dc_mw,
            solar_lat=solar_lat,
            solar_lon=solar_lon,
        )
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_backcast, region, days, strategy_ids, config
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "vault": str(VAULT_ROOT)}


# ── To-Do routes ──────────────────────────────────────────────────────
TODO_FILE = VAULT_ROOT / "05_System" / "todos.json"

def _load_todos():
    if TODO_FILE.exists():
        return _json.loads(TODO_FILE.read_text())
    return []

def _save_todos(todos):
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODO_FILE.write_text(_json.dumps(todos, indent=2))

@app.get("/todos")
async def get_todos():
    return _load_todos()

@app.post("/todos")
async def create_todo(payload: dict):
    todos = _load_todos()
    todo = {
        "id": str(_uuid.uuid4()),
        "text": payload.get("text", ""),
        "priority": payload.get("priority", "medium"),
        "area": payload.get("area", "Other"),
        "done": False,
        "source": "manual",
    }
    todos.append(todo)
    _save_todos(todos)
    return todo

@app.patch("/todos/{todo_id}")
async def update_todo(todo_id: str, payload: dict):
    todos = _load_todos()
    for t in todos:
        if t["id"] == todo_id:
            t.update({k: v for k, v in payload.items() if k != "id"})
            _save_todos(todos)
            return t
    raise HTTPException(404, "Todo not found")

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: str):
    todos = _load_todos()
    todos = [t for t in todos if t["id"] != todo_id]
    _save_todos(todos)
    return {"ok": True}

@app.post("/todos/sync-from-md")
async def sync_todos_from_md():
    """Parse TODOS.md + TASK_CAPTURE.md and seed todos.json, preserving done state and all manually added todos."""
    import re as _re
    # Always preserve manually added todos
    all_existing = _load_todos()
    manual_todos = [t for t in all_existing if t.get("source") == "manual"]
    existing = {t["text"]: t for t in all_existing}
    area_map = {
        "SN Energy": "BDM", "AIIGP": "Grants", "Richard Feng": "BDM",
        "LPE": "BDM", "Scott Taylor": "BDM", "Wakefield": "BDM",
        "Re-Fuel": "BDM", "HaimOS": "Tech", "Investment": "Investment",
        "Finance": "Finance", "Legal": "Legal", "Personal": "Personal",
        "RMIT": "Grants", "SkySails": "Projects", "Agri": "Tech",
        "David Lee": "Operations", "COO": "Operations",
    }
    priority_map = {"🔴": "high", "🟡": "medium", "🟢": "low"}
    todos = []

    def parse_md_file(md_path, default_area="Other", default_priority="medium"):
        if not md_path.exists():
            return
        current_area = default_area
        current_priority = default_priority
        for line in md_path.read_text().splitlines():
            # Section headings
            h = _re.match(r'^#{1,3}\s+[🔴🟡🟢]?\s*(.*)', line)
            if h:
                heading = h.group(1).strip()
                current_area = next((v for k, v in area_map.items() if k in heading), default_area)
                for emoji, pri in priority_map.items():
                    if emoji in line:
                        current_priority = pri
                        break
                continue
            # Checkbox lines — support [ ], [x], [~] (parked)
            m = _re.match(r'^- \[([ x~])\]\s+(.*)', line)
            if not m:
                continue
            state = m.group(1)
            text = m.group(2).strip()
            # Strip bold markdown and anything after first — for cleaner display
            clean = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            clean = _re.split(r'\s+—\s+', clean)[0].strip()
            if not clean or len(clean) < 4:
                continue
            done = (state == 'x')
            parked = (state == '~')
            prev = existing.get(clean)
            todos.append({
                "id": prev["id"] if prev else str(_uuid.uuid4()),
                "text": clean,
                "priority": current_priority,
                "area": current_area,
                "done": prev["done"] if prev else done,
                "parked": parked,
                "source": "md",
            })

    # 1. Primary: TODOS.md
    parse_md_file(VAULT_ROOT / "01_State" / "TODOS.md")
    # 2. Secondary: TASK_CAPTURE.md (new tasks section)
    parse_md_file(VAULT_ROOT / "00_Master_Context" / "TASK_CAPTURE.md", default_area="Capture")

    # Deduplicate by text (TODOS.md takes precedence)
    seen = {}
    deduped = []
    for t in todos:
        if t["text"] not in seen:
            seen[t["text"]] = True
            deduped.append(t)

    # Re-merge manual todos not already in md sources
    md_texts = {t["text"] for t in deduped}
    for m in manual_todos:
        if m["text"] not in md_texts:
            deduped.append(m)

    _save_todos(deduped)

    # Also run seed_todos.py to pick up TASK_CAPTURE.md items
    import subprocess as _sp, sys as _sys
    seed_script = VAULT_ROOT / "05_System" / "seed_todos.py"
    if seed_script.exists():
        _sp.run([_sys.executable, str(seed_script)], cwd=str(VAULT_ROOT), capture_output=True)
    return {"synced": len(deduped)}


# ── Projects / Weekly Review routes ────────────────────────────────────
PROJECTS_FILE = VAULT_ROOT / "05_System" / "projects.json"

def _load_projects():
    if PROJECTS_FILE.exists():
        return _json.loads(PROJECTS_FILE.read_text())
    return []

def _save_projects(projects):
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(_json.dumps(projects, indent=2))

@app.get("/projects")
async def get_projects():
    return _load_projects()

@app.post("/projects")
async def create_project(payload: dict):
    projects = _load_projects()
    project = {
        "id": str(_uuid.uuid4()),
        "name": payload.get("name", "New Project"),
        "client": payload.get("client", ""),
        "contact": payload.get("contact", ""),
        "category": payload.get("category", "BDM"),
        "status": payload.get("status", "active"),
        "court": payload.get("court", "us"),
        "priority": payload.get("priority", len(projects) + 1),
        "our_actions": payload.get("our_actions", []),
        "waiting_on": payload.get("waiting_on", []),
        "stages": payload.get("stages", []),
        "documents": payload.get("documents", []),
        "payments": payload.get("payments", []),
        "notes": payload.get("notes", ""),
        "last_updated": payload.get("last_updated", ""),
    }
    projects.append(project)
    _save_projects(projects)
    return project

@app.patch("/projects/{project_id}")
async def update_project(project_id: str, payload: dict):
    projects = _load_projects()
    for p in projects:
        if p["id"] == project_id:
            p.update({k: v for k, v in payload.items() if k != "id"})
            _save_projects(projects)
            return p
    raise HTTPException(404, "Project not found")

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    projects = _load_projects()
    projects = [p for p in projects if p["id"] != project_id]
    _save_projects(projects)
    return {"ok": True}

@app.post("/projects/{project_id}/payments")
async def add_payment(project_id: str, payload: dict):
    projects = _load_projects()
    for p in projects:
        if p["id"] == project_id:
            payment = {
                "id": str(_uuid.uuid4()),
                "amount": payload.get("amount", 0),
                "date": payload.get("date", ""),
                "stage": payload.get("stage", ""),
                "note": payload.get("note", ""),
                "invoice": payload.get("invoice", ""),
            }
            if "payments" not in p:
                p["payments"] = []
            p["payments"].append(payment)
            _save_projects(projects)
            return payment
    raise HTTPException(404, "Project not found")

@app.patch("/projects/{project_id}/stages/{stage_id}")
async def update_stage(project_id: str, stage_id: str, payload: dict):
    projects = _load_projects()
    for p in projects:
        if p["id"] == project_id:
            for s in p.get("stages", []):
                if s["id"] == stage_id:
                    s.update({k: v for k, v in payload.items() if k != "id"})
                    _save_projects(projects)
                    return s
    raise HTTPException(404, "Stage not found")


# ── NNA routes ──────────────────────────────────────────────────────────
NNA_FAV_FILE = VAULT_ROOT / "05_System" / "nna_favourites.json"

def _load_favs():
    if NNA_FAV_FILE.exists():
        return set(_json.loads(NNA_FAV_FILE.read_text()))
    return set()

def _save_favs(favs):
    NNA_FAV_FILE.parent.mkdir(parents=True, exist_ok=True)
    NNA_FAV_FILE.write_text(_json.dumps(list(favs)))

@app.get("/nna/opportunities")
async def nna_opportunities():
    from nna_parser import load_opportunities
    opps = load_opportunities()
    favs = _load_favs()
    for o in opps:
        o["is_favourite"] = o.get("id") in favs
    return opps

@app.get("/nna/meta")
async def nna_meta():
    from nna_parser import load_opportunities, DNSP_META
    opps = load_opportunities()
    dnsp_list = sorted({o["dnsp"] for o in opps})
    state_list = sorted({o["state"] for o in opps if o.get("state")})
    colors = {d: DNSP_META.get(d, {}).get("color", "#4a5568") for d in dnsp_list}
    return {"dnsp_list": dnsp_list, "state_list": state_list, "dnsp_colors": colors}

@app.post("/nna/favourites/{opp_id}")
async def add_fav(opp_id: str):
    favs = _load_favs()
    favs.add(opp_id)
    _save_favs(favs)
    return {"ok": True}

@app.delete("/nna/favourites/{opp_id}")
async def remove_fav(opp_id: str):
    favs = _load_favs()
    favs.discard(opp_id)
    _save_favs(favs)
    return {"ok": True}

@app.post("/nna/chat")
async def nna_chat(payload: dict):
    msg = payload.get("message", "").lower()
    from nna_parser import load_opportunities, DNSP_META
    opps = load_opportunities()
    # Parse DNSP names
    all_dnsps = {o["dnsp"] for o in opps}
    matched_dnsp = [d for d in all_dnsps if d.lower() in msg]
    # Parse states
    state_codes = ["nsw","vic","qld","sa","wa","tas","act","nt"]
    matched_states = [s.upper() for s in state_codes if s in msg]
    # Parse season
    season = "summer" if "summer" in msg else ("winter" if "winter" in msg else None)
    # Parse MW threshold
    mw_match = _re.search(r'(\d+(?:\.\d+)?)\s*mw', msg)
    min_mw = float(mw_match.group(1)) if mw_match else None
    favs_only = "fav" in msg or "favour" in msg
    parts = []
    if matched_dnsp: parts.append(", ".join(matched_dnsp))
    if matched_states: parts.append("/".join(matched_states))
    if season: parts.append(season)
    if min_mw: parts.append(f">{min_mw}MW")
    if favs_only: parts.append("favourites only")
    summary = "Filtered by: " + ", ".join(parts) if parts else "No filters detected"
    return {"dnsp": matched_dnsp, "state": matched_states, "season": season,
            "min_mw": min_mw, "favs_only": favs_only, "summary": summary}


# ── Social / LinkedIn ─────────────────────────────────────────────────────────

@app.get("/api/social/drafts")
async def social_get_drafts():
    """Return all saved post drafts."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import get_all_drafts
        return {"drafts": get_all_drafts()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/social/generate")
async def social_generate():
    """Fetch today's news + generate fresh post drafts with AI images."""
    try:
        import asyncio
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.news_fetcher import fetch_news
        from social.post_drafter import draft_posts_from_articles

        articles = await asyncio.get_event_loop().run_in_executor(None, fetch_news)
        new_drafts = await asyncio.get_event_loop().run_in_executor(
            None, draft_posts_from_articles, articles, 6
        )
        return {"generated": len(new_drafts), "drafts": new_drafts}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/social/generate-custom")
async def social_generate_custom(body: dict):
    """Generate a single LinkedIn post draft from a user-supplied subject + vault context."""
    subject = (body.get("subject") or "").strip()
    if not subject:
        raise HTTPException(400, "subject is required")
    try:
        import asyncio
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import draft_post_from_subject
        draft = await asyncio.get_event_loop().run_in_executor(
            None, draft_post_from_subject, subject
        )
        return {"draft": draft}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/social/drafts/{draft_id}")
async def social_update_draft(draft_id: str, body: dict):
    """Update a draft (edit text, change status, etc.)."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import update_draft
        updated = update_draft(draft_id, body)
        if not updated:
            raise HTTPException(404, "Draft not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/social/drafts/{draft_id}")
async def social_delete_draft(draft_id: str):
    """Permanently delete a draft."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import delete_draft
        ok = delete_draft(draft_id)
        if not ok:
            raise HTTPException(404, "Draft not found")
        return {"deleted": draft_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/social/linkedin/auth")
async def social_linkedin_auth():
    """Return the LinkedIn OAuth URL to redirect user to."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.linkedin_client import get_auth_url
        return get_auth_url()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/social/linkedin/callback")
async def social_linkedin_callback(code: str = "", state: str = "", error: str = ""):
    """LinkedIn OAuth callback — exchanges code for token."""
    if error:
        return {"error": error}
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.linkedin_client import handle_callback
        result = handle_callback(code, state)
        # Return a simple HTML page that closes the popup/window
        if result.get("success"):
            html = "<html><body><script>window.close();opener&&opener.postMessage('linkedin_auth_ok','*');</script><p>LinkedIn connected! You can close this tab.</p></body></html>"
        else:
            html = f"<html><body><p>Error: {result.get('error')}</p></body></html>"
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/social/linkedin/status")
async def social_linkedin_status():
    """Check if LinkedIn OAuth token is valid."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.linkedin_client import get_token_status
        return get_token_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/social/linkedin/post/{draft_id}")
async def social_post_to_linkedin(draft_id: str):
    """Post an approved draft to LinkedIn."""
    try:
        import asyncio
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import get_all_drafts, update_draft
        from social.linkedin_client import post_to_linkedin
        from datetime import datetime, timezone

        drafts = get_all_drafts()
        draft  = next((d for d in drafts if d["id"] == draft_id), None)
        if not draft:
            raise HTTPException(404, "Draft not found")
        if draft["status"] == "posted":
            raise HTTPException(400, "Already posted")

        result = await asyncio.get_event_loop().run_in_executor(
            None, post_to_linkedin, draft["post_text"], draft.get("image_path")
        )
        if result.get("success"):
            update_draft(draft_id, {
                "status":      "posted",
                "posted_at":   datetime.now(timezone.utc).isoformat(),
                "linkedin_id": result.get("id"),
            })
            return {"success": True, "linkedin_id": result.get("id")}
        else:
            raise HTTPException(502, result.get("error", "Unknown LinkedIn error"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/social/image/{draft_id}")
async def social_get_image(draft_id: str):
    """Serve a draft's generated image."""
    try:
        import sys as _sys
        _social_dir = str(Path(__file__).parent)
        if _social_dir not in _sys.path:
            _sys.path.insert(0, _social_dir)
        from social.post_drafter import get_all_drafts
        from fastapi.responses import FileResponse

        drafts = get_all_drafts()
        draft  = next((d for d in drafts if d["id"] == draft_id), None)
        if not draft or not draft.get("image_path"):
            raise HTTPException(404, "No image for this draft")
        img_path = Path(draft["image_path"])
        if not img_path.exists():
            raise HTTPException(404, "Image file not found")
        return FileResponse(str(img_path), media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
