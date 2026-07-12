"""
SRA Auction Parser

Parses AEMO auction results, bid/offer schemas, clearing and cancellation prices.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import csv
import io
import re
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class AuctionResult:
    """Result of a single SRA auction."""
    auction_id: str  # e.g., "SRA_2026_Q3_T01"
    category_id: str  # e.g., "NSW1-VIC1"
    relevant_quarter: str  # e.g., "C2028Q1"
    tranche_no: int
    units_offered: int
    units_cleared: int
    clearing_price: Optional[Decimal]  # $/unit, None if no clearing
    total_revenue: Optional[Decimal]  # $/unit * units_cleared
    auction_datetime: str  # ISO 8601
    status: str  # "cleared", "no_clearance", "partial_clearance"


@dataclass(frozen=True)
class CancellationResult:
    """Result of a cancellation (secondary) auction for units offered by existing holders."""
    cancellation_auction_id: str
    category_id: str
    relevant_quarter: str
    tranche_no: int
    units_offered: int
    units_cleared: int
    cancellation_price: Optional[Decimal]  # $/unit
    participant_id: Optional[str]  # Participant offering the cancellation


class SRAAuctionParser:
    """
    Parses AEMO auction results and pricing data.
    
    Phase 1 deliverable:
    - Ingest SRA_Results clearing prices and Units for all completed tranches
    - Link to product registry
    - Compute realized distributions
    
    Blueprint Section 7, 12 (auction and secondary trading)
    """

    def __init__(self):
        """Initialize empty parser."""
        self.auction_results: List[AuctionResult] = []
        self.cancellation_results: List[CancellationResult] = []
        self._auction_result_ids: set[str] = set()
        self._cancellation_result_ids: set[str] = set()

    def add_auction_result(self, result: AuctionResult) -> None:
        """Register a primary auction result."""
        if result.auction_id in self._auction_result_ids:
            return
        self._auction_result_ids.add(result.auction_id)
        self.auction_results.append(result)

    def add_cancellation_result(self, result: CancellationResult) -> None:
        """Register a cancellation (secondary) auction result."""
        if result.cancellation_auction_id in self._cancellation_result_ids:
            return
        self._cancellation_result_ids.add(result.cancellation_auction_id)
        self.cancellation_results.append(result)

    @staticmethod
    def _parse_report_datetime(csv_text: str) -> datetime:
        first_line = csv_text.splitlines()[0] if csv_text else ""
        match = re.search(r'PUBLIC,"([^"]+)"', first_line)
        if not match:
            return datetime.utcnow()
        return datetime.strptime(match.group(1), "%Y/%m/%d %H:%M:%S")

    @staticmethod
    def _result_status(units_offered: int, units_sold: int) -> str:
        if units_sold <= 0:
            return "no_clearance"
        if units_sold < units_offered:
            return "partial_clearance"
        return "cleared"

    def ingest_sra_results_csv_text(self, csv_text: str) -> int:
        """
        Ingest a single SRA_Results CSV payload into the parser.

        The AEMO report contains one data row per interconnector/from-region pair,
        so the parser stores each row as a distinct AuctionResult keyed by report
        version and from-region.

        Returns:
            Number of AuctionResult rows ingested.
        """
        report_datetime = self._parse_report_datetime(csv_text)
        row_count = 0
        reader = csv.reader(io.StringIO(csv_text))
        for row in reader:
            if len(row) < 12 or row[0] != "D" or row[1] != "RESIDUE_PUBLIC_DATA":
                continue
            contract_id = row[4]
            version_no = int(row[5]) if row[5].strip() else 0
            quarter_match = re.fullmatch(r"C(\d{4})Q([1-4])T(\d{2})", contract_id)
            if not quarter_match:
                continue
            relevant_quarter = f"C{quarter_match.group(1)}Q{quarter_match.group(2)}"
            tranche_no = int(quarter_match.group(3))
            units_offered = int(row[8]) if row[8].strip() else 0
            units_sold = int(row[9]) if row[9].strip() else 0
            clearing_price = Decimal(row[10].strip()) if row[10].strip() else None
            total_revenue = (
                clearing_price * Decimal(units_sold)
                if clearing_price is not None
                else None
            )
            auction_result = AuctionResult(
                auction_id=f"{contract_id}_v{version_no:02d}_{row[7]}",
                category_id=row[6],
                relevant_quarter=relevant_quarter,
                tranche_no=tranche_no,
                units_offered=units_offered,
                units_cleared=units_sold,
                clearing_price=clearing_price,
                total_revenue=total_revenue,
                auction_datetime=report_datetime.isoformat(),
                status=self._result_status(units_offered, units_sold),
            )
            self.add_auction_result(auction_result)
            row_count += 1
        return row_count

    def ingest_sra_results_files(self, csv_texts: Iterable[str]) -> int:
        """Ingest multiple SRA_Results CSV payloads."""
        total = 0
        for csv_text in csv_texts:
            total += self.ingest_sra_results_csv_text(csv_text)
        return total

    def get_clearing_price(
        self,
        category_id: str,
        relevant_quarter: str,
        tranche_no: int,
    ) -> Optional[Decimal]:
        """
        Get primary clearing price for a specific product.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            tranche_no: 1-12
            
        Returns:
            Clearing price in $/unit, or None if not cleared
        """
        matching: Optional[AuctionResult] = None
        for result in self.auction_results:
            if (result.category_id == category_id
                and result.relevant_quarter == relevant_quarter
                and result.tranche_no == tranche_no):
                matching = result
        return matching.clearing_price if matching is not None else None

    def get_cancellation_prices(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> List[Decimal]:
        """
        Get all cancellation prices for a category/quarter.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            List of cancellation prices ($/unit)
        """
        prices = []
        for result in self.cancellation_results:
            if (result.category_id == category_id
                and result.relevant_quarter == relevant_quarter
                and result.cancellation_price):
                prices.append(result.cancellation_price)
        return prices

    def get_units_sold(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> int:
        """
        Get total units sold in primary auctions for a category/quarter.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            Total units cleared across all tranches
        """
        total = 0
        for result in self.auction_results:
            if result.category_id == category_id and result.relevant_quarter == relevant_quarter:
                total += result.units_cleared
        return total

    def get_units_offered(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> int:
        """
        Get total units offered in primary auctions for a category/quarter.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            Total units offered across all tranches
        """
        total = 0
        for result in self.auction_results:
            if result.category_id == category_id and result.relevant_quarter == relevant_quarter:
                total += result.units_offered
        return total
