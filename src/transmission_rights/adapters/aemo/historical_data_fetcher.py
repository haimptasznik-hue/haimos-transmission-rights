"""AEMO historical and reference data fetcher for Phase 1 ingestion."""

from __future__ import annotations

import csv
import io
import re
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
import requests

from ...services.aemo.sra_market_calendar import AuctionEvent, SRAMarketCalendar
from ...services.aemo.sra_product_registry import (
    AllocationTypeEnum,
    SRAProduct,
    SRAProductRegistry,
)

NEMWEB_CURRENT_BASE = "https://nemweb.com.au/Reports/CURRENT"
NEMWEB_ARCHIVE_BASE = "https://nemweb.com.au/Reports/ARCHIVE"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class AuctionProductSnapshot:
    auction_id: str
    contract_id: str
    quarter: str
    tranche_no: int
    directional_interconnector: str
    from_region: str
    units_offered: int
    units_sold: int
    clearing_price: Decimal
    reserve_price: Decimal


@dataclass(frozen=True)
class DispatchIRSRRecord:
    trading_interval: str
    interconnector_id: str
    from_region: str
    residue_aud: Decimal


class HistoricalDataFetcher:
    """
    Fetches and manages historical AEMO data for replay and calibration.
    
    Phase 1 deliverable:
    - Download archived Dispatch_IRSR files
    - Download archived SRA_Results
    - Download product definitions (max units, proportions) snapshots
    - Organize by effective date and settlement run
    - Support queries: "give me all data for C2027Q3", "reconcile Q2028Q1"
    
    Blueprint Section 2, 12 (data sources and historical replay)
    """

    def __init__(self):
        """Initialize data fetcher."""
        self.cached_files: Dict[str, bytes] = {}  # Filename -> raw file contents
        self.metadata: Dict[str, Dict] = {}  # Filename -> metadata
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _USER_AGENT})

    @staticmethod
    def _parse_quarter(quarter: str) -> tuple[int, int]:
        match = re.fullmatch(r"C(\d{4})Q([1-4])", quarter)
        if not match:
            raise ValueError(f"Invalid quarter format: {quarter}")
        return int(match.group(1)), int(match.group(2))

    @classmethod
    def _quarter_in_range(cls, quarter: str, start_quarter: str, end_quarter: str) -> bool:
        return cls._parse_quarter(start_quarter) <= cls._parse_quarter(quarter) <= cls._parse_quarter(
            end_quarter
        )

    @staticmethod
    def _quarter_from_datetime(value: datetime) -> str:
        quarter = ((value.month - 1) // 3) + 1
        return f"C{value.year}Q{quarter}"

    @classmethod
    def _quarter_from_dispatch_filename(cls, filename: str) -> Optional[str]:
        current_match = re.search(r"PUBLIC_DISPATCH_IRSR_(\d{12})_\d+\.zip", filename)
        if current_match:
            file_time = datetime.strptime(current_match.group(1), "%Y%m%d%H%M")
            return cls._quarter_from_datetime(file_time)
        archive_match = re.search(r"PUBLIC_DISPATCH_IRSR_(\d{8})\.zip", filename)
        if archive_match:
            file_date = datetime.strptime(archive_match.group(1), "%Y%m%d")
            return cls._quarter_from_datetime(file_date)
        return None

    def _download_text(self, url: str, timeout: int = 30) -> str:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            proc = subprocess.run(
                ["/usr/bin/curl", "-sL", url],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                raise
            return proc.stdout

    def _download_bytes(self, url: str, timeout: int = 30) -> bytes:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            proc = subprocess.run(
                ["/usr/bin/curl", "-sL", url],
                check=False,
                capture_output=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                raise
            return proc.stdout

    def _list_files_from_directory(self, directory_url: str, pattern: str) -> List[str]:
        html = self._download_text(directory_url, timeout=20)
        return sorted(set(re.findall(pattern, html)))

    @staticmethod
    def _parse_contract_id(contract_id: str) -> tuple[str, int]:
        match = re.fullmatch(r"C\d{4}Q[1-4]T(\d{2})", contract_id)
        if not match:
            raise ValueError(f"Invalid contract id: {contract_id}")
        quarter = contract_id[:7]
        tranche = int(match.group(1))
        return quarter, tranche

    @staticmethod
    def _safe_int(value: str) -> int:
        return int(value.strip()) if value.strip() else 0

    @staticmethod
    def _safe_decimal(value: str) -> Decimal:
        cleaned = value.strip().replace(",", "")
        return Decimal(cleaned) if cleaned else Decimal("0")

    @staticmethod
    def _auction_units_sort_key(filename: str) -> tuple[date, int, str]:
        effective = HistoricalDataFetcher._effective_date_from_filename(filename)
        revision_match = re.search(r"\.R(\d+)$", filename)
        revision = int(revision_match.group(1)) if revision_match else 0
        return effective, revision, filename

    @staticmethod
    def _effective_date_from_filename(filename: str) -> date:
        auc_match = re.search(r"AUCUNITS_(\d{8})\.R\d+", filename)
        if auc_match:
            return datetime.strptime(auc_match.group(1), "%Y%m%d").date()
        srres_match = re.search(r"PUBLIC_SRRES_[A-Z]\d{4}Q\dT\d{2}_(\d{14})\.csv", filename)
        if srres_match:
            return datetime.strptime(srres_match.group(1), "%Y%m%d%H%M%S").date()
        return datetime.utcnow().date()

    def list_sra_results_files(self) -> List[tuple[str, str, int]]:
        pattern = r"PUBLIC_SRRES_([A-Z]\d{4}Q\d)T(\d{2})_\d+\.csv"
        html = self._download_text(f"{NEMWEB_CURRENT_BASE}/SRA_Results/", timeout=20)
        results: List[tuple[str, str, int]] = []
        for match in re.finditer(pattern, html):
            quarter = match.group(1)
            tranche = int(match.group(2))
            filename = match.group(0)
            results.append((filename, quarter, tranche))
        return sorted(set(results), key=lambda item: (item[1], item[2], item[0]))

    def list_dispatch_irsr_files(self) -> List[str]:
        current_files = self._list_files_from_directory(
            f"{NEMWEB_CURRENT_BASE}/Dispatch_IRSR/",
            r"PUBLIC_DISPATCH_IRSR_\d{12}_\d+\.zip",
        )
        archive_files = self._list_files_from_directory(
            f"{NEMWEB_ARCHIVE_BASE}/Dispatch_IRSR/",
            r"PUBLIC_DISPATCH_IRSR_\d{8}\.zip",
        )
        return sorted(set(current_files + archive_files))

    def list_auction_units_files(self) -> List[str]:
        return self._list_files_from_directory(
            f"{NEMWEB_CURRENT_BASE}/Auction_Units_Reports/",
            r"AUCUNITS_\d{8}\.R\d+",
        )

    def list_sra_offer_files(self) -> List[str]:
        return self._list_files_from_directory(
            f"{NEMWEB_CURRENT_BASE}/SRA_Offers/",
            r"PUBLIC_SROFFER_A\d{6}_\d{14}\.CSV",
        )

    def list_sra_bid_files(self) -> List[str]:
        return self._list_files_from_directory(
            f"{NEMWEB_CURRENT_BASE}/SRA_Bids/",
            r"PUBLIC_SRBID_A\d{6}_\d{14}\.CSV",
        )

    def fetch_sra_results_file(self, filename: str) -> str:
        url = f"{NEMWEB_CURRENT_BASE}/SRA_Results/{filename}"
        text = self._download_text(url)
        self.cached_files[filename] = text.encode("utf-8")
        self.metadata[filename] = {
            "source": "SRA_Results",
            "fetched_at": datetime.utcnow().isoformat(),
            "effective_date": self._effective_date_from_filename(filename).isoformat(),
        }
        return text

    def fetch_auction_units_file(self, filename: str) -> str:
        url = f"{NEMWEB_CURRENT_BASE}/Auction_Units_Reports/{filename}"
        text = self._download_text(url)
        self.cached_files[filename] = text.encode("utf-8")
        self.metadata[filename] = {
            "source": "Auction_Units_Reports",
            "fetched_at": datetime.utcnow().isoformat(),
            "effective_date": self._effective_date_from_filename(filename).isoformat(),
        }
        return text

    def fetch_sra_offer_file(self, filename: str) -> str:
        url = f"{NEMWEB_CURRENT_BASE}/SRA_Offers/{filename}"
        text = self._download_text(url)
        self.cached_files[filename] = text.encode("utf-8")
        self.metadata[filename] = {
            "source": "SRA_Offers",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        return text

    def fetch_sra_bid_file(self, filename: str) -> str:
        url = f"{NEMWEB_CURRENT_BASE}/SRA_Bids/{filename}"
        text = self._download_text(url)
        self.cached_files[filename] = text.encode("utf-8")
        self.metadata[filename] = {
            "source": "SRA_Bids",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        return text

    @staticmethod
    def parse_dispatch_irsr_zip_bytes(content: bytes) -> List[DispatchIRSRRecord]:
        records: List[DispatchIRSRRecord] = []

        def _parse_zip(zip_bytes: bytes) -> None:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    with zf.open(name) as handle:
                        payload = handle.read()
                    lower_name = name.lower()
                    # Archive daily zips wrap per-interval zips — recurse into them
                    if lower_name.endswith(".zip") and payload.startswith(b"PK"):
                        _parse_zip(payload)
                        continue
                    if not lower_name.endswith(".csv"):
                        continue
                    for raw_line in payload.decode("utf-8", errors="ignore").splitlines():
                        line = raw_line.strip()
                        if not line.startswith("D,DISPATCH,IRSR,2,"):
                            continue
                        row = next(csv.reader([line]))
                        if len(row) < 8:
                            continue
                        try:
                            residue = Decimal(row[7])
                        except Exception:
                            continue
                        records.append(
                            DispatchIRSRRecord(
                                trading_interval=row[4],
                                interconnector_id=row[5],
                                from_region=row[6],
                                residue_aud=residue,
                            )
                        )

        _parse_zip(content)
        return records

    @classmethod
    def _quarter_from_interval_string(cls, trading_interval: str) -> str:
        dt = datetime.strptime(trading_interval.strip('"'), "%Y/%m/%d %H:%M:%S")
        return cls._quarter_from_datetime(dt)

    def reconstruct_irsr_quarterly(self, dispatch_filenames: List[str]) -> pd.DataFrame:
        rows: List[Dict[str, str | Decimal]] = []
        for filename in dispatch_filenames:
            content = self.cached_files.get(filename)
            if not content:
                continue
            for record in self.parse_dispatch_irsr_zip_bytes(content):
                quarter = self._quarter_from_interval_string(record.trading_interval)
                rows.append(
                    {
                        "quarter": quarter,
                        "interconnector_id": record.interconnector_id,
                        "from_region": record.from_region,
                        "residue_aud": record.residue_aud,
                    }
                )

        if not rows:
            return pd.DataFrame(columns=["quarter", "interconnector_id", "from_region", "residue_aud"])

        df = pd.DataFrame(rows)
        grouped = (
            df.groupby(["quarter", "interconnector_id", "from_region"], as_index=False)["residue_aud"]
            .sum()
            .sort_values(["quarter", "interconnector_id", "from_region"])
        )
        return grouped

    def load_auction_units_from_file(self, filename: str) -> pd.DataFrame:
        content = self.fetch_auction_units_file(filename)
        return self.parse_auction_units_text(content)

    @staticmethod
    def parse_auction_units_text(content: str) -> pd.DataFrame:
        reader = csv.reader(io.StringIO(content))
        header: List[str] = []
        rows: List[Dict[str, str]] = []
        for row in reader:
            if row and row[0] == "I" and len(row) > 5 and row[1] == "BILLING":
                header = row[5:]
                continue
            if row and row[0] == "D" and row[1] == "BILLING" and header:
                values = row[5 : 5 + len(header)]
                rows.append(dict(zip(header, values)))
        return pd.DataFrame(rows)

    def reconcile_dispatch_vs_auction_units(
        self,
        dispatch_quarterly_df: pd.DataFrame,
        auction_units_df: pd.DataFrame,
        relevant_quarter: str,
    ) -> pd.DataFrame:
        if dispatch_quarterly_df.empty or auction_units_df.empty:
            return pd.DataFrame(
                columns=[
                    "interconnector_id",
                    "from_region",
                    "dispatch_residue_aud",
                    "auction_netpayment_aud",
                    "delta_aud",
                ]
            )

        quarter_no = int(relevant_quarter[-1])
        dispatch_slice = dispatch_quarterly_df[dispatch_quarterly_df["quarter"] == relevant_quarter].copy()

        auction_slice = auction_units_df[auction_units_df["QUARTER"].astype(str) == str(quarter_no)].copy()
        auction_slice = auction_slice.rename(
            columns={
                "INTERCONNECTORID": "interconnector_id",
                "FROMREGIONID": "from_region",
                "NETPAYMENT": "auction_netpayment_aud",
            }
        )
        auction_slice["auction_netpayment_aud"] = pd.to_numeric(
            auction_slice["auction_netpayment_aud"], errors="coerce"
        ).fillna(0)
        auction_agg = (
            auction_slice.groupby(["interconnector_id", "from_region"], as_index=False)["auction_netpayment_aud"]
            .sum()
            .sort_values(["interconnector_id", "from_region"])
        )

        dispatch_slice["dispatch_residue_aud"] = pd.to_numeric(
            dispatch_slice["residue_aud"], errors="coerce"
        ).fillna(0)
        dispatch_agg = dispatch_slice[["interconnector_id", "from_region", "dispatch_residue_aud"]]

        merged = dispatch_agg.merge(
            auction_agg,
            on=["interconnector_id", "from_region"],
            how="outer",
        ).fillna(0)
        merged["delta_aud"] = merged["dispatch_residue_aud"] - merged["auction_netpayment_aud"]
        return merged.sort_values(["interconnector_id", "from_region"])

    def parse_sra_results(self, csv_text: str) -> List[AuctionProductSnapshot]:
        snapshots: List[AuctionProductSnapshot] = []
        reader = csv.reader(io.StringIO(csv_text))
        for row in reader:
            if len(row) < 12 or row[0] != "D" or row[1] != "RESIDUE_PUBLIC_DATA":
                continue
            contract_id = row[4]
            quarter, tranche_no = self._parse_contract_id(contract_id)
            snapshots.append(
                AuctionProductSnapshot(
                    auction_id=f"A{quarter[1:5]}{int(quarter[-1]) * 3:02d}",
                    contract_id=contract_id,
                    quarter=quarter,
                    tranche_no=tranche_no,
                    directional_interconnector=row[6],
                    from_region=row[7],
                    units_offered=self._safe_int(row[8]),
                    units_sold=self._safe_int(row[9]),
                    clearing_price=self._safe_decimal(row[10]),
                    reserve_price=self._safe_decimal(row[11]),
                )
            )
        return snapshots

    def load_products_from_sra_results(
        self,
        registry: SRAProductRegistry,
        snapshots: List[AuctionProductSnapshot],
        effective_date: date,
    ) -> int:
        count = 0
        for record in snapshots:
            from_region = record.from_region
            to_region = ""
            if "-" in record.directional_interconnector:
                region_a, region_b = record.directional_interconnector.split("-", 1)
                to_region = region_b if from_region == region_a else region_a
            product = SRAProduct(
                product_id=f"{record.directional_interconnector}_{record.contract_id}_{from_region}",
                unit_category_id=f"{record.directional_interconnector}_{from_region}",
                relevant_quarter=record.quarter,
                tranche_no=record.tranche_no,
                allocation_type=AllocationTypeEnum.PRIMARY,
                directional_interconnector=record.directional_interconnector,
                from_region=from_region,
                to_region=to_region,
                max_units=record.units_offered,
                unit_proportion=(1 / record.units_offered) if record.units_offered else 0,
                effective_date=effective_date,
                description=f"Loaded from SRA_Results {record.contract_id}",
            )
            registry.register_product(product)
            count += 1
        return count

    def load_calendar_from_sra_results(
        self,
        calendar: SRAMarketCalendar,
        snapshots: List[AuctionProductSnapshot],
        auction_timestamp: datetime,
    ) -> int:
        seen: set[str] = set()
        added = 0
        for record in snapshots:
            if record.contract_id in seen:
                continue
            seen.add(record.contract_id)
            auction_id = f"{record.contract_id}_v1"
            event = AuctionEvent(
                auction_id=auction_id,
                relevant_quarter=record.quarter,
                tranche_no=record.tranche_no,
                auction_open_datetime=auction_timestamp,
                auction_close_datetime=auction_timestamp,
                notice_published_datetime=auction_timestamp,
                description="Derived from SRA_Results publication",
            )
            calendar.add_event(event)
            added += 1
        return added

    def fetch_dispatch_irsr_range(
        self,
        start_quarter: str,  # e.g., "C2027Q3"
        end_quarter: str,  # e.g., "C2028Q2"
    ) -> List[str]:
        """
        Fetch all DISPATCH_IRSR files for a range of quarters.
        
        Args:
            start_quarter: Starting relevant quarter
            end_quarter: Ending relevant quarter
            
        Returns:
            List of successfully fetched filenames
        """
        current_url = f"{NEMWEB_CURRENT_BASE}/Dispatch_IRSR/"
        archive_url = f"{NEMWEB_ARCHIVE_BASE}/Dispatch_IRSR/"
        current_files = self._list_files_from_directory(
            current_url, r"PUBLIC_DISPATCH_IRSR_\d{12}_\d+\.zip"
        )
        archive_files = self._list_files_from_directory(
            archive_url, r"PUBLIC_DISPATCH_IRSR_\d{8}\.zip"
        )
        files = sorted(set(current_files + archive_files))
        fetched: List[str] = []
        for filename in files:
            file_quarter = self._quarter_from_dispatch_filename(filename)
            if file_quarter is None:
                continue
            if not self._quarter_in_range(file_quarter, start_quarter, end_quarter):
                continue
            if re.search(r"PUBLIC_DISPATCH_IRSR_\d{12}_\d+\.zip$", filename):
                file_url = f"{current_url}{filename}"
            else:
                file_url = f"{archive_url}{filename}"
            try:
                content = self._download_bytes(file_url, timeout=30)
            except Exception:
                continue
            if not content.startswith(b"PK"):
                continue
            self.cached_files[filename] = content
            self.metadata[filename] = {
                "source": "Dispatch_IRSR",
                "fetched_at": datetime.utcnow().isoformat(),
                "quarter": file_quarter,
            }
            fetched.append(filename)
        return fetched

    def fetch_sra_results_range(
        self,
        start_quarter: str,
        end_quarter: str,
    ) -> List[str]:
        """
        Fetch all SRA_Results files for a range of quarters.
        
        Args:
            start_quarter: Starting relevant quarter
            end_quarter: Ending relevant quarter
            
        Returns:
            List of successfully fetched filenames
        """
        fetched: List[str] = []
        for filename, quarter, tranche in self.list_sra_results_files():
            if not self._quarter_in_range(quarter, start_quarter, end_quarter):
                continue
            try:
                self.fetch_sra_results_file(filename)
            except Exception:
                continue
            self.metadata[filename].update({
                "quarter": quarter,
                "tranche_no": tranche,
            })
            fetched.append(filename)
        return fetched

    def fetch_product_definitions_snapshot(
        self,
        effective_date: str,  # ISO 8601 date
    ) -> Optional[Dict]:
        """
        Fetch product definitions (max units, proportions) as of an effective date.
        
        Args:
            effective_date: Date for which to fetch definitions
            
        Returns:
            Dict of product definitions, or None if not available
        """
        requested = datetime.strptime(effective_date, "%Y-%m-%d").date()
        files = self.list_auction_units_files()
        eligible = [f for f in files if self._effective_date_from_filename(f) <= requested]
        if not eligible:
            return None
        filename = max(eligible, key=self._auction_units_sort_key)
        content = self.fetch_auction_units_file(filename)
        rows = self.parse_auction_units_text(content).to_dict(orient="records")
        return {
            "effective_date": self._effective_date_from_filename(filename).isoformat(),
            "source_file": filename,
            "rows": rows,
            "count": len(rows),
        }

    def get_cached_file(self, filename: str) -> Optional[bytes]:
        """
        Retrieve a previously fetched file from cache.
        
        Args:
            filename: Name of file to retrieve
            
        Returns:
            File contents (bytes), or None if not cached
        """
        return self.cached_files.get(filename)

    def reconciliation_report(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> Dict:
        """
        Generate reconciliation report for a category/quarter.
        Compares calculated vs. published AEMO data.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            Reconciliation report dict
        """
        return {
            "category_id": category_id,
            "relevant_quarter": relevant_quarter,
            "status": "not_reconciled",  # Placeholder
            "message": "Reconciliation requires full data ingestion (Phase 1)",
        }
