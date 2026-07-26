from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

import pandas as pd


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


@dataclass(frozen=True)
class ArchiveFetchResult:
    archive_path: Path
    source_url: str
    cache_skipped: bool
    zip_valid: bool
    sha256: str


MMSDM_URL_TEMPLATE = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    "/{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader"
    "/DATA/{archive_name}"
)


def month_range(start_month: str, end_month: str) -> list[tuple[int, int]]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("end-month must be >= start-month")
    current = start
    months: list[tuple[int, int]] = []
    while current <= end:
        months.append((current.year, current.month))
        current += 1
    return months


def build_archive_name(dataset_token: str, year: int, month: int) -> str:
    month_token = f"{year}{month:02d}"
    return f"PUBLIC_DVD_{dataset_token}_{month_token}010000.zip"


def build_mmsdm_url(dataset_token: str, year: int, month: int) -> tuple[str, str]:
    archive_name = build_archive_name(dataset_token, year, month)
    return archive_name, MMSDM_URL_TEMPLATE.format(year=year, month=month, archive_name=archive_name)


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip(archive_path: Path) -> bool:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            return archive.testzip() is None
    except Exception:
        return False


def partitioned_cache_path(cache_dir: Path, year: int, month: int, file_name: str) -> Path:
    target_dir = cache_dir / f"year={year}" / f"month={month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / file_name


def write_manifest(manifest_path: Path, payload: dict[str, object]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fetch_archive_with_retry(
    *,
    dataset_token: str,
    year: int,
    month: int,
    raw_dir: Path,
    retries: int = 3,
    timeout_seconds: int = 90,
) -> ArchiveFetchResult:
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_name, source_url = build_mmsdm_url(dataset_token, year, month)
    archive_path = raw_dir / archive_name

    if archive_path.exists() and validate_zip(archive_path):
        return ArchiveFetchResult(
            archive_path=archive_path,
            source_url=source_url,
            cache_skipped=True,
            zip_valid=True,
            sha256=sha256_file(archive_path),
        )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(source_url, headers=REQUEST_HEADERS)
            with urlopen(request, timeout=timeout_seconds) as response:
                archive_path.write_bytes(response.read())
            if not validate_zip(archive_path):
                raise ValueError(f"invalid zip structure: {archive_path}")
            return ArchiveFetchResult(
                archive_path=archive_path,
                source_url=source_url,
                cache_skipped=False,
                zip_valid=True,
                sha256=sha256_file(archive_path),
            )
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))

    raise RuntimeError(f"failed to fetch archive after {retries} attempts: {source_url}; error={last_error}")


def progress_line(*, dataset_token: str, month_token: str, rows_normalized: int, cache_path: Path, cache_skipped: bool) -> str:
    skip_note = "cache-hit" if cache_skipped else "downloaded"
    return (
        f"[{dataset_token}] {month_token}: rows={rows_normalized} "
        f"status={skip_note} cache={cache_path}"
    )
