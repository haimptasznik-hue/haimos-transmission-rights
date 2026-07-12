"""
transmission_rights/data/aemo_feeds.py — Live AEMO SRA data ingestion
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# NEMWeb requires a realistic User-Agent
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

NEMWEB_BASE = "https://nemweb.com.au/Reports/CURRENT"


def list_dispatch_irsr_files(limit: int = 20) -> list[str]:
    """List most recent DISPATCH_IRSR zip files from NEMWeb."""
    try:
        url = f"{NEMWEB_BASE}/Dispatch_IRSR/"
        resp = requests.get(url, timeout=15, headers={"User-Agent": _UA})
        resp.raise_for_status()
        pattern = r'PUBLIC_DISPATCH_IRSR_(\d{12})_(\d+)\.zip'
        matches = re.findall(pattern, resp.text)
        # Sort descending by timestamp
        files = [f"PUBLIC_DISPATCH_IRSR_{ts}_{fnum}.zip" for ts, fnum in sorted(matches, reverse=True)]
        return files[:limit]
    except Exception as e:
        logger.error("Failed to list dispatch_irsr files: %s", e)
        return []


def fetch_dispatch_irsr_zip(filename: str) -> pd.DataFrame | None:
    """Download and parse one DISPATCH_IRSR zip file into a DataFrame."""
    try:
        url = f"{NEMWEB_BASE}/Dispatch_IRSR/{filename}"
        resp = requests.get(url, timeout=30, headers={"User-Agent": _UA})
        resp.raise_for_status()

        records = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if not name.upper().endswith(".CSV"):
                    continue
                with zf.open(name) as f:
                    for line in f:
                        text = line.decode("utf-8", errors="ignore").strip()
                        if not text.startswith("D,DISPATCH,IRSR,2,"):
                            continue
                        parts = text.split(",", 4)
                        if len(parts) < 5:
                            continue
                        try:
                            timestamp = parts[3].strip('"')
                            interconnector_id = parts[4].split(",")[0].strip('"') if "," in parts[4] else ""
                            rest = parts[4].split(",")
                            if len(rest) < 3:
                                continue
                            interconnector_id = rest[0].strip('"')
                            from_region = rest[1].strip('"')
                            residue_str = rest[2].strip('"')
                            residue = float(residue_str) if residue_str else 0.0
                            records.append({
                                "timestamp": timestamp,
                                "interconnector_id": interconnector_id,
                                "from_region": from_region,
                                "residue_aud": residue,
                            })
                        except (IndexError, ValueError):
                            continue
        if not records:
            logger.warning(f"No records parsed from {filename}")
            return None
        return pd.DataFrame(records)
    except Exception as e:
        logger.error(f"Failed to fetch/parse {filename}: {e}")
        return None


def list_sra_results_files(limit: int = 30) -> list[tuple[str, str, int]]:
    """List SRA_Results CSV files, returning (filename, quarter, tranche_no)."""
    try:
        url = f"{NEMWEB_BASE}/SRA_Results/"
        resp = requests.get(url, timeout=15, headers={"User-Agent": _UA})
        resp.raise_for_status()
        pattern = r'PUBLIC_SRRES_([A-Z]\d{4}[Q]\d)T(\d{2})_'
        matches = re.findall(pattern, resp.text)
        # Extract all files with quarter and tranche
        files = []
        for match in re.finditer(r'PUBLIC_SRRES_([A-Z]\d{4}[Q]\d)T(\d{2})_\d+\.csv', resp.text):
            quarter = match.group(1)
            tranche = int(match.group(2))
            filename = match.group(0)
            files.append((filename, quarter, tranche))
        return sorted(files, key=lambda x: (x[1], x[2]), reverse=True)[:limit]
    except Exception as e:
        logger.error("Failed to list sra_results files: %s", e)
        return []


def fetch_sra_results_csv(filename: str) -> pd.DataFrame | None:
    """Download and parse one SRA_Results CSV into a DataFrame."""
    try:
        url = f"{NEMWEB_BASE}/SRA_Results/{filename}"
        resp = requests.get(url, timeout=30, headers={"User-Agent": _UA})
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        return df
    except Exception as e:
        logger.error(f"Failed to fetch/parse SRA_Results {filename}: {e}")
        return None


def list_auction_units_files(limit: int = 10) -> list[str]:
    """List AUCUNITS reference files from NEMWeb."""
    try:
        url = f"{NEMWEB_BASE}/Auction_Units_Reports/"
        resp = requests.get(url, timeout=15, headers={"User-Agent": _UA})
        resp.raise_for_status()
        pattern = r'AUCUNITS_(\d{8})\.R(\d+)'
        matches = re.findall(pattern, resp.text)
        # Return most recent
        files = [f"AUCUNITS_{d}.R{r}" for d, r in sorted(matches, reverse=True)]
        return files[:limit]
    except Exception as e:
        logger.error("Failed to list auction_units files: %s", e)
        return []


def fetch_auction_units_file(filename: str) -> str | None:
    """Download AUCUNITS reference file (raw text format)."""
    try:
        url = f"{NEMWEB_BASE}/Auction_Units_Reports/{filename}"
        resp = requests.get(url, timeout=30, headers={"User-Agent": _UA})
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"Failed to fetch AUCUNITS {filename}: {e}")
        return None
