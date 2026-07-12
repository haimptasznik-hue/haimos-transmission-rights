#!/usr/bin/env python3
"""
Download all historical AEMO data for the replication engine.

Downloads:
  1. All AUCUNITS files (weekly billing/payout records)
  2. All archived Dispatch_IRSR daily zips (historical 5-min IRSR)
  3. All current Dispatch_IRSR intraday files (current quarter)

Run from the repo root:
  python scripts/download_all_historical.py
"""

import hashlib
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# --- Config ---
BASE = Path(__file__).resolve().parents[1]
AUCUNITS_DIR     = BASE / "data/raw/aemo/auction_units"
IRSR_ARCHIVE_DIR = BASE / "data/raw/aemo/dispatch_irsr/archive"
IRSR_CURRENT_DIR = BASE / "data/raw/aemo/dispatch_irsr/current"

NEMWEB_CURRENT  = "https://nemweb.com.au/Reports/CURRENT"
NEMWEB_ARCHIVE  = "https://nemweb.com.au/Reports/ARCHIVE"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
DELAY = 0.25   # seconds between requests — be polite to NEMWEB


# ---------------------------------------------------------------------------

def fetch_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def list_files(directory_url: str, pattern: str) -> list[str]:
    html = fetch_text(directory_url)
    return sorted(set(re.findall(pattern, html)))


def download_file(url: str, dest: Path, *, skip_existing: bool = True) -> bool:
    """Download url → dest. Returns True if downloaded, False if skipped."""
    if skip_existing and dest.exists() and dest.stat().st_size > 0:
        return False
    try:
        data = fetch_bytes(url)
        dest.write_bytes(data)
        return True
    except (URLError, OSError) as exc:
        print(f"  ERROR {dest.name}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# 1. AUCUNITS
# ---------------------------------------------------------------------------

def download_aucunits() -> None:
    print("\n=== AUCUNITS (weekly billing records) ===")
    AUCUNITS_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"{NEMWEB_CURRENT}/Auction_Units_Reports"
    files = list_files(base_url + "/", r"AUCUNITS_\d+\.R\d+")
    print(f"  Found {len(files)} AUCUNITS files on NEMWEB")
    downloaded = skipped = errors = 0
    for fname in files:
        dest = AUCUNITS_DIR / fname
        ok = download_file(f"{base_url}/{fname}", dest)
        if ok:
            downloaded += 1
            print(f"  ✓ {fname}")
        else:
            skipped += 1
        time.sleep(DELAY)
    print(f"  Done: {downloaded} downloaded, {skipped} skipped (already had them), {errors} errors")


# ---------------------------------------------------------------------------
# 2. Dispatch_IRSR ARCHIVE (daily zips, one per day)
# ---------------------------------------------------------------------------

def download_dispatch_irsr_archive() -> None:
    print("\n=== Dispatch_IRSR ARCHIVE (daily historical zips) ===")
    IRSR_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"{NEMWEB_ARCHIVE}/Dispatch_IRSR"
    files = list_files(base_url + "/", r"PUBLIC_DISPATCH_IRSR_\d{8}\.zip")
    print(f"  Found {len(files)} archive daily zip files")
    downloaded = skipped = 0
    for fname in files:
        dest = IRSR_ARCHIVE_DIR / fname
        ok = download_file(f"{base_url}/{fname}", dest)
        if ok:
            downloaded += 1
            if downloaded % 20 == 0:
                print(f"  ... {downloaded}/{len(files)} downloaded so far")
        else:
            skipped += 1
        time.sleep(DELAY)
    print(f"  Done: {downloaded} downloaded, {skipped} skipped")


# ---------------------------------------------------------------------------
# 3. Dispatch_IRSR CURRENT (5-min intraday files, current quarter)
# ---------------------------------------------------------------------------

def download_dispatch_irsr_current() -> None:
    print("\n=== Dispatch_IRSR CURRENT (5-min intraday files) ===")
    IRSR_CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"{NEMWEB_CURRENT}/Dispatch_IRSR"
    files = list_files(base_url + "/", r"PUBLIC_DISPATCH_IRSR_\d{12}_\d+\.zip")
    print(f"  Found {len(files)} current intraday files")
    downloaded = skipped = 0
    for fname in files:
        dest = IRSR_CURRENT_DIR / fname
        ok = download_file(f"{base_url}/{fname}", dest)
        if ok:
            downloaded += 1
        else:
            skipped += 1
        time.sleep(DELAY)
    print(f"  Done: {downloaded} downloaded, {skipped} skipped")


# ---------------------------------------------------------------------------
# 4. SRA Results (already partially downloaded — top up)
# ---------------------------------------------------------------------------

def download_sra_results() -> None:
    print("\n=== SRA Results (auction clearing prices) ===")
    sra_dir = BASE / "data/raw/aemo/sra_results"
    sra_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"{NEMWEB_CURRENT}/SRA_Results"
    files = list_files(base_url + "/", r"PUBLIC_SRRES_[A-Z]\d{4}Q\dT\d{2}_\d+\.csv")
    print(f"  Found {len(files)} SRA result files on NEMWEB")
    downloaded = skipped = 0
    for fname in files:
        dest = sra_dir / fname
        ok = download_file(f"{base_url}/{fname}", dest)
        if ok:
            downloaded += 1
        else:
            skipped += 1
        time.sleep(DELAY)
    print(f"  Done: {downloaded} downloaded, {skipped} skipped")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("HAIMos Transmission Rights — Full Historical Data Download")
    print(f"Target directory: {BASE}/data/raw/aemo/")
    print("This will download AUCUNITS, Dispatch_IRSR archive+current, SRA Results.")
    print("Files already on disk are skipped automatically.\n")

    try:
        download_aucunits()
        download_dispatch_irsr_archive()
        download_dispatch_irsr_current()
        download_sra_results()
    except KeyboardInterrupt:
        print("\nInterrupted — partial data is usable, re-run to resume.")
        sys.exit(0)

    print("\n=== Summary ===")
    for label, d in [
        ("AUCUNITS", AUCUNITS_DIR),
        ("Dispatch_IRSR/archive", IRSR_ARCHIVE_DIR),
        ("Dispatch_IRSR/current", IRSR_CURRENT_DIR),
        ("SRA Results", BASE / "data/raw/aemo/sra_results"),
    ]:
        if d.exists():
            files = list(d.iterdir())
            total_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1_048_576
            print(f"  {label:<30} {len(files):>5} files   {total_mb:>8.1f} MB")

    print("\nDone. Run the replication engine next.")
