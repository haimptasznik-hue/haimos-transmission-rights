"""
transmission_rights/api/aemo_discovery.py — Live data discovery endpoints
"""
from fastapi import APIRouter

from transmission_rights.adapters.aemo_feeds import (
    list_dispatch_irsr_files,
    list_sra_results_files,
    list_auction_units_files,
    fetch_dispatch_irsr_zip,
    fetch_sra_results_csv,
)
from transmission_rights.services.irsr_engine import IRSRReconstructor

router = APIRouter(prefix="/discovery", tags=["aemo-discovery"])


@router.get("/dispatch-irsr/files")
def list_dispatch_irsr() -> dict:
    """List available DISPATCH_IRSR zip files from NEMWeb."""
    files = list_dispatch_irsr_files(limit=20)
    return {"files": files, "count": len(files)}


@router.get("/dispatch-irsr/latest")
def get_latest_dispatch_irsr() -> dict:
    """Fetch and summarize the latest DISPATCH_IRSR data."""
    files = list_dispatch_irsr_files(limit=1)
    if not files:
        return {"error": "No DISPATCH_IRSR files found"}
    
    df = fetch_dispatch_irsr_zip(files[0])
    if df is None:
        return {"error": f"Failed to parse {files[0]}"}
    
    engine = IRSRReconstructor()
    snapshots = engine.process_dispatch_irsr_data(df)
    quarterly = engine.aggregate_by_quarter(snapshots, "C2026Q3")
    
    return {
        "file": files[0],
        "raw_records": len(df),
        "snapshots": len(snapshots),
        "quarterly_totals_by_ic": quarterly,
        "sample_quarterly_irsr": {
            ic: f"${residue:,.2f}" for ic, residue in list(quarterly.items())[:5]
        },
    }


@router.get("/sra-results/files")
def list_sra_results() -> dict:
    """List available SRA_Results CSV files from NEMWeb."""
    files = list_sra_results_files(limit=20)
    return {
        "files": [{"filename": f[0], "quarter": f[1], "tranche": f[2]} for f in files],
        "count": len(files),
    }


@router.get("/auction-units/files")
def list_auction_units() -> dict:
    """List available AUCUNITS reference files from NEMWeb."""
    files = list_auction_units_files(limit=10)
    return {"files": files, "count": len(files)}
