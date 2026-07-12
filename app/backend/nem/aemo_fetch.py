"""
nem/aemo_fetch.py — Live AEMO wholesale price fetcher for HaimOS
================================================================
Pulled directly from SolarTool_2026-04-24_v1_Mark1 / Live Wholesale tracker
/ data_loader.py — zero synthetic data. All prices come from NEMWeb.

Sources:
  • NEMWeb DispatchIS_Reports  → live 5-min spot + FCAS prices
  • NEMWeb P5_Reports          → ~1 h ahead price forecast
  • NEMWeb PredispatchIS_Reports → rest-of-day 30-min forecast
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import requests
import pytz

logger = logging.getLogger(__name__)

AEST = pytz.timezone("Australia/Brisbane")  # UTC+10, no DST

NEM_REGIONS = ("NSW1", "VIC1", "QLD1", "SA1", "TAS1")

# NEMWeb blocks the default python-requests User-Agent — spoof a browser header.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NEMWEB_DISPATCH_URL     = "https://nemweb.com.au/Reports/Current/DispatchIS_Reports/"
NEMWEB_P5MIN_URL        = "https://nemweb.com.au/Reports/Current/P5_Reports/"
NEMWEB_PREDISPATCH_URL  = "https://nemweb.com.au/Reports/Current/PredispatchIS_Reports/"

# FCAS column positions in the D,DISPATCH,PRICE CSV row (0-indexed)
_FCAS_COL_MAP = {
    15: "fcas_raise_6sec_aud_per_mw",
    18: "fcas_raise_60sec_aud_per_mw",
    21: "fcas_raise_5min_aud_per_mw",
    24: "fcas_reg_raise_aud_per_mw",
    27: "fcas_lower_6sec_aud_per_mw",
    30: "fcas_lower_60sec_aud_per_mw",
    33: "fcas_lower_5min_aud_per_mw",
    36: "fcas_reg_lower_aud_per_mw",
    49: "fcas_raise_1sec_aud_per_mw",
    52: "fcas_lower_1sec_aud_per_mw",
}


def today_date_str() -> str:
    """Return today's date in AEST as YYYYMMDD string."""
    return datetime.now(AEST).strftime("%Y%m%d")


# ── Live spot prices ──────────────────────────────────────────────────────

def list_dispatch_zips(date_str: str) -> list[str]:
    """Scrape NEMWeb directory for dispatch ZIP filenames matching date_str."""
    try:
        resp = requests.get(NEMWEB_DISPATCH_URL, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        pattern = rf"(PUBLIC_DISPATCHIS_{date_str}\d{{4}}_\d+\.zip)"
        return sorted(set(re.findall(pattern, resp.text)))
    except Exception as e:
        logger.warning("list_dispatch_zips failed: %s", e)
        return []


def _parse_dispatch_zip(filename: str, region: str) -> list[dict]:
    """Download one dispatch ZIP, return D,DISPATCH,PRICE rows for region."""
    url = NEMWEB_DISPATCH_URL + filename
    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        records: list[dict] = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if not name.upper().endswith(".CSV"):
                    continue
                with zf.open(name) as f:
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line.startswith("D,DISPATCH,PRICE,"):
                            continue
                        parts = line.split(",")
                        if len(parts) < 12:
                            continue
                        if parts[6].strip() != region:
                            continue
                        settlement = parts[4].strip().strip('"')
                        rrp = parts[9].strip()
                        try:
                            rec = {
                                "timestamp": pd.to_datetime(settlement),
                                "price_mwh": float(rrp),
                                "region": region,
                            }
                            for idx, col in _FCAS_COL_MAP.items():
                                try:
                                    rec[col] = float(parts[idx]) if idx < len(parts) and parts[idx].strip() else 0.0
                                except (ValueError, TypeError):
                                    rec[col] = 0.0
                            records.append(rec)
                        except (ValueError, TypeError):
                            continue
        return records
    except Exception:
        return []


def fetch_todays_prices(region: str, max_workers: int = 12) -> pd.DataFrame:
    """
    Fetch all available 5-min NEM spot prices for today from NEMWeb.
    Returns DataFrame[timestamp, price_mwh, region, <10 FCAS columns>].
    Empty DataFrame on failure.
    """
    date_str = today_date_str()
    zip_files = list_dispatch_zips(date_str)
    if not zip_files:
        logger.warning("No dispatch ZIPs for %s", date_str)
        return pd.DataFrame(columns=["timestamp", "price_mwh", "region"])

    all_records: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_parse_dispatch_zip, zf, region): zf for zf in zip_files}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                all_records.extend(result)

    if not all_records:
        return pd.DataFrame(columns=["timestamp", "price_mwh", "region"])

    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    return df


# ── P5MIN forward forecast (~1 h ahead) ──────────────────────────────────

def fetch_p5min_forecast(region: str) -> pd.DataFrame:
    """
    Fetch AEMO P5MIN forecast (5-min resolution, ~1 h ahead).
    Returns DataFrame[timestamp, price_mwh, source='p5min_5min'].
    """
    try:
        resp = requests.get(NEMWEB_P5MIN_URL, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        zips = sorted(set(re.findall(r'(PUBLIC_P5MIN_[^"]*\.zip)', resp.text)))
        if not zips:
            return pd.DataFrame()

        url = NEMWEB_P5MIN_URL + zips[-1]
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()

        records: list[dict] = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if not name.upper().endswith(".CSV"):
                    continue
                with zf.open(name) as f:
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line.startswith("D,P5MIN,REGIONSOLUTION,"):
                            continue
                        parts = line.split(",")
                        if len(parts) < 10 or parts[7].strip() != region:
                            continue
                        try:
                            records.append({
                                "timestamp": pd.to_datetime(parts[6].strip().strip('"')),
                                "price_mwh": float(parts[8].strip()),
                            })
                        except (ValueError, TypeError):
                            continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df["source"] = "p5min_5min"
        return df
    except Exception as e:
        logger.warning("P5MIN fetch failed: %s", e)
        return pd.DataFrame()


# ── Pre-dispatch forecast (30 min, rest-of-day) ───────────────────────────

def fetch_predispatch_forecast(region: str) -> pd.DataFrame:
    """
    Fetch AEMO Pre-dispatch forecast (30-min resolution, rest of trading day).
    Returns DataFrame[timestamp, price_mwh, source='predispatch_30min'].
    """
    try:
        resp = requests.get(NEMWEB_PREDISPATCH_URL, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        zips = sorted(set(re.findall(r'(PUBLIC_PREDISPATCHIS_[^"]*\.zip)', resp.text)))
        if not zips:
            return pd.DataFrame()

        url = NEMWEB_PREDISPATCH_URL + zips[-1]
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()

        records: list[dict] = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if not name.upper().endswith(".CSV"):
                    continue
                with zf.open(name) as f:
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line.startswith("D,PREDISPATCH,REGION_PRICES,"):
                            continue
                        parts = line.split(",")
                        if len(parts) < 29 or parts[6].strip() != region:
                            continue
                        try:
                            records.append({
                                "timestamp": pd.to_datetime(parts[28].strip().strip('"')),
                                "price_mwh": float(parts[9].strip()),
                            })
                        except (ValueError, TypeError):
                            continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df["source"] = "predispatch_30min"
        return df
    except Exception as e:
        logger.warning("Pre-dispatch fetch failed: %s", e)
        return pd.DataFrame()


# ── Historical price fetch (AEMO MMSDM archive) ───────────────────────────────
# Monthly ZIP files from NEMWeb archive; one row per 5-min interval per region.
# URL: .../PUBLIC_DVD_DISPATCHPRICE_{year}{month:02d}010000.zip
_MMSDM_URL_TMPL = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/PUBLIC_DVD_DISPATCHPRICE_{year}{month:02d}010000.zip"
)

import pathlib as _pl, tempfile as _tmp, pickle as _pkl


def fetch_historical_prices(region: str = "VIC1", days: int = 365) -> "pd.DataFrame":
    """
    Fetch historical 5-min spot prices from AEMO MMSDM archive.

    Results are disk-cached per region/month so only the current month
    is ever re-downloaded.  Returns DataFrame[timestamp, price_mwh].
    FCAS columns are NOT included (not present in DISPATCHPRICE archive file);
    backcast simulations therefore show arb revenue only.
    """
    import pickle as _pkl

    cache_dir = _pl.Path(_tmp.gettempdir()) / "haimos_backcast"
    cache_dir.mkdir(parents=True, exist_ok=True)

    now_aest = datetime.now(AEST)
    current_ym = (now_aest.year, now_aest.month)

    # Determine which year/month combos we need
    months_needed: set = set()
    for d in range(days + 32):          # +32 to ensure full month coverage
        dt = now_aest - pd.Timedelta(days=d)
        months_needed.add((dt.year, dt.month))

    frames = []
    for (year, month) in sorted(months_needed):
        cache_file = cache_dir / f"disp_{region}_{year}{month:02d}.pkl"
        df_month: "pd.DataFrame | None" = None

        # Use cached copy unless it's the current month (prices still updating)
        if cache_file.exists() and (year, month) != current_ym:
            try:
                with open(cache_file, "rb") as fh:
                    df_month = _pkl.load(fh)
            except Exception:
                cache_file.unlink(missing_ok=True)

        if df_month is None:
            url = _MMSDM_URL_TMPL.format(year=year, month=month)
            try:
                resp = requests.get(url, timeout=90, headers=_HEADERS)
                resp.raise_for_status()
                records: list[dict] = []
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    for name in zf.namelist():
                        if not name.upper().endswith(".CSV"):
                            continue
                        with zf.open(name) as f:
                            for raw_line in f:
                                line = raw_line.decode("utf-8", errors="ignore").strip()
                                if not line.startswith("D,DISPATCH,PRICE,"):
                                    continue
                                parts = line.split(",")
                                if len(parts) < 10:
                                    continue
                                try:
                                    reg = parts[6].strip().strip('"')
                                    if reg != region:
                                        continue
                                    ts    = pd.to_datetime(parts[4].strip().strip('"'))
                                    price = float(parts[8].strip())
                                    records.append({"timestamp": ts, "price_mwh": price})
                                except (ValueError, IndexError):
                                    continue
                if records:
                    df_month = pd.DataFrame(records)
                    df_month = (df_month
                                .drop_duplicates("timestamp")
                                .sort_values("timestamp")
                                .reset_index(drop=True))
                    df_month["timestamp"] = df_month["timestamp"].dt.tz_localize(None)
                    # Cache completed months
                    if (year, month) != current_ym:
                        with open(cache_file, "wb") as fh:
                            _pkl.dump(df_month, fh)
                else:
                    df_month = pd.DataFrame()
            except Exception as exc:
                logger.warning("MMSDM fetch failed %d-%02d: %s", year, month, exc)
                df_month = pd.DataFrame()

        if df_month is not None and not df_month.empty:
            frames.append(df_month)

    # For months where MMSDM returned nothing (usually < 4 months old),
    # fall back to NEMWeb DispatchIS current archive which has ~60 days of data.
    mmsdm_timestamps = set()
    for f in frames:
        if not f.empty:
            mmsdm_timestamps.update(f["timestamp"].dt.to_period("M").unique())

    recent_days_needed = 0
    for (year, month) in sorted(months_needed):
        period = pd.Period(year=year, month=month, freq="M")
        if period not in mmsdm_timestamps:
            # Estimate how many days of recent data we're missing
            days_in_month = pd.Period(year=year, month=month, freq="M").days_in_month
            recent_days_needed = max(recent_days_needed, days_in_month + 5)

    if recent_days_needed > 0:
        logger.info("MMSDM missing recent months — fetching from DispatchIS archive (%d days)", recent_days_needed)
        recent_df = fetch_recent_dispatch_history(region=region, days=min(recent_days_needed, 60))
        if not recent_df.empty:
            frames.append(recent_df)

    if not frames:
        return pd.DataFrame(columns=["timestamp", "price_mwh"])

    combined = (pd.concat(frames, ignore_index=True)
                .drop_duplicates("timestamp")
                .sort_values("timestamp")
                .reset_index(drop=True))

    cutoff = (now_aest - pd.Timedelta(days=days)).replace(tzinfo=None)
    return combined[combined["timestamp"] >= cutoff].reset_index(drop=True)


def fetch_recent_dispatch_history(region: str, days: int = 60) -> pd.DataFrame:
    """
    Fetch recent 5-min spot prices from NEMWeb DispatchIS_Reports/Current archive.
    Used as fallback when MMSDM archive hasn't published recent months yet
    (MMSDM typically lags 2–4 months behind real-time).

    Walks back through the dispatch ZIP listing for each day and collects
    all available D,DISPATCH,PRICE rows.  Results are cached to disk by date.
    Returns DataFrame[timestamp, price_mwh].
    """
    import pathlib as _pl

    cache_dir = _pl.Path(_tmp.gettempdir()) / "haimos_recent_dispatch"
    cache_dir.mkdir(parents=True, exist_ok=True)

    now_aest = datetime.now(AEST)
    frames: list = []

    try:
        resp = requests.get(NEMWEB_DISPATCH_URL, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        # All ZIP filenames in the current directory listing
        all_zips = sorted(set(re.findall(
            r"(PUBLIC_DISPATCHIS_(\d{8})\d{4}_\d+\.zip)", resp.text
        )))
    except Exception as exc:
        logger.warning("fetch_recent_dispatch_history listing failed: %s", exc)
        return pd.DataFrame(columns=["timestamp", "price_mwh"])

    # Build a dict date_str -> list of zip filenames
    date_to_zips: dict = {}
    for fname, date_str in all_zips:
        date_to_zips.setdefault(date_str, []).append(fname)

    cutoff_date = (now_aest - pd.Timedelta(days=days)).strftime("%Y%m%d")

    for date_str in sorted(date_to_zips.keys()):
        if date_str < cutoff_date:
            continue

        cache_file = cache_dir / f"disp_{region}_{date_str}.pkl"
        # Use cache for any day that's fully completed (not today)
        is_today = date_str == now_aest.strftime("%Y%m%d")
        df_day: "pd.DataFrame | None" = None

        if cache_file.exists() and not is_today:
            try:
                with open(cache_file, "rb") as fh:
                    df_day = _pkl.load(fh)
            except Exception:
                cache_file.unlink(missing_ok=True)

        if df_day is None:
            records: list[dict] = []
            for fname in date_to_zips[date_str]:
                url = NEMWEB_DISPATCH_URL + fname
                try:
                    r = requests.get(url, timeout=10, headers=_HEADERS)
                    r.raise_for_status()
                    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                        for name in zf.namelist():
                            if not name.upper().endswith(".CSV"):
                                continue
                            with zf.open(name) as f:
                                for raw_line in f:
                                    line = raw_line.decode("utf-8", errors="ignore").strip()
                                    if not line.startswith("D,DISPATCH,PRICE,"):
                                        continue
                                    parts = line.split(",")
                                    if len(parts) < 10 or parts[6].strip() != region:
                                        continue
                                    try:
                                        records.append({
                                            "timestamp": pd.to_datetime(parts[4].strip().strip('"')),
                                            "price_mwh": float(parts[9].strip()),
                                        })
                                    except (ValueError, IndexError):
                                        continue
                except Exception as exc:
                    logger.debug("dispatch zip fetch skipped %s: %s", fname, exc)

            if records:
                df_day = (pd.DataFrame(records)
                          .drop_duplicates("timestamp")
                          .sort_values("timestamp")
                          .reset_index(drop=True))
                df_day["timestamp"] = df_day["timestamp"].dt.tz_localize(None)
                if not is_today:
                    with open(cache_file, "wb") as fh:
                        _pkl.dump(df_day, fh)

        if df_day is not None and not df_day.empty:
            frames.append(df_day)

    if not frames:
        return pd.DataFrame(columns=["timestamp", "price_mwh"])

    combined = (pd.concat(frames, ignore_index=True)
                .drop_duplicates("timestamp")
                .sort_values("timestamp")
                .reset_index(drop=True))
    cutoff_ts = (now_aest - pd.Timedelta(days=days)).replace(tzinfo=None)
    return combined[combined["timestamp"] >= cutoff_ts].reset_index(drop=True)


def merge_forward_forecasts(region: str) -> pd.DataFrame:
    """
    Merge P5MIN (near-term) and Pre-dispatch (rest-of-day) into one series.
    P5MIN takes priority where both overlap.
    Returns DataFrame[timestamp, price_mwh, source].
    """
    p5  = fetch_p5min_forecast(region)
    pd30 = fetch_predispatch_forecast(region)

    if p5.empty and pd30.empty:
        return pd.DataFrame(columns=["timestamp", "price_mwh", "source"])
    if p5.empty:
        return pd30
    if pd30.empty:
        return p5

    p5_max = p5["timestamp"].max()
    tail = pd30[pd30["timestamp"] > p5_max].copy()
    combined = pd.concat([p5, tail], ignore_index=True)
    return combined.sort_values("timestamp").reset_index(drop=True)
