"""
AEMO AUCUNITS file parser and effective-dated registry.

Parses AEMO weekly BILLING/AUCTION_UNITS settlement records and exposes
PURCHASEDUNITS, DISTRIBUTEDSURPLUS, NETPAYMENT, NETPAYMENTPERUNIT,
ACCUMULATEDNETPAYMENT, ACCUMULATEDNETPAYMENTPERUNIT per unit category
and billing week, keyed by effective date.
"""

from __future__ import annotations

import csv as _csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class AucUnitsRow:
    source_file: str
    effective_date: date
    bill_run_type: str
    contract_year: int
    week_no: int
    bill_run_no: int
    start_date: date
    end_date: date
    residue_year: int
    quarter: int
    relevant_quarter: str
    interconnector_id: str
    from_region: str
    purchased_units: int
    total_surplus: Decimal
    distributed_surplus: Decimal
    auction_fees: Decimal
    net_payment: Decimal
    net_payment_per_unit: Decimal
    accumulated_net_payment: Decimal
    accumulated_net_payment_per_unit: Decimal
    source_hash: str


@dataclass(frozen=True)
class CategoryQuarterSummary:
    """Authoritative accumulated payout for one unit category/quarter."""
    relevant_quarter: str
    interconnector_id: str
    from_region: str
    purchased_units: int
    total_surplus: Decimal
    distributed_surplus: Decimal
    auction_fees: Decimal
    net_payment: Decimal
    accumulated_net_payment: Decimal
    accumulated_net_payment_per_unit: Decimal
    bill_run_type: str
    source_file: str
    source_hash: str
    effective_date: date


class AucUnitsLoader:
    def __init__(self) -> None:
        self._rows: List[AucUnitsRow] = []

    def load_file(self, path: Path) -> List[AucUnitsRow]:
        raw = path.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace")
        effective_date = _effective_date_from_filename(path.name)
        rows = _parse(text, path.name, effective_date, source_hash)
        self._rows.extend(rows)
        return rows

    def load_directory(self, directory: Path) -> int:
        total = 0
        for path in sorted(directory.glob("AUCUNITS_*.R*")):
            rows = self.load_file(path)
            total += len(rows)
        return total

    def all_rows(self) -> List[AucUnitsRow]:
        return list(self._rows)

    def rows_for_quarter(self, relevant_quarter: str) -> List[AucUnitsRow]:
        return [r for r in self._rows if r.relevant_quarter == relevant_quarter]

    def get_final_summary(
        self,
        relevant_quarter: str,
        interconnector_id: str,
        from_region: str,
    ) -> Optional[CategoryQuarterSummary]:
        """Return best available accumulated payout: FINAL > highest REVISION."""
        candidates = [
            r for r in self._rows
            if r.relevant_quarter == relevant_quarter
            and r.interconnector_id == interconnector_id
            and r.from_region == from_region
        ]
        if not candidates:
            return None

        def _priority(row: AucUnitsRow) -> tuple:
            if row.bill_run_type.upper() == "FINAL":
                return (2, 999, row.effective_date)
            m = re.search(r"(\d+)", row.bill_run_type)
            rev = int(m.group(1)) if m else 0
            return (1, rev, row.effective_date)

        best = max(candidates, key=_priority)
        cohort_rows = [r for r in candidates if r.bill_run_type == best.bill_run_type]

        weekly_rows: List[AucUnitsRow] = []
        for week_no in sorted({r.week_no for r in cohort_rows}):
            week_candidates = [r for r in cohort_rows if r.week_no == week_no]
            weekly_rows.append(max(week_candidates, key=lambda row: row.effective_date))

        quarter_total_surplus = sum((r.total_surplus for r in weekly_rows), Decimal("0"))
        quarter_distributed_surplus = sum((r.distributed_surplus for r in weekly_rows), Decimal("0"))
        quarter_auction_fees = sum((r.auction_fees for r in weekly_rows), Decimal("0"))
        quarter_net_payment = sum((r.net_payment for r in weekly_rows), Decimal("0"))

        return CategoryQuarterSummary(
            relevant_quarter=best.relevant_quarter,
            interconnector_id=best.interconnector_id,
            from_region=best.from_region,
            purchased_units=best.purchased_units,
            total_surplus=quarter_total_surplus,
            distributed_surplus=quarter_distributed_surplus,
            auction_fees=quarter_auction_fees,
            net_payment=quarter_net_payment,
            accumulated_net_payment=best.accumulated_net_payment,
            accumulated_net_payment_per_unit=best.accumulated_net_payment_per_unit,
            bill_run_type=best.bill_run_type,
            source_file=best.source_file,
            source_hash=best.source_hash,
            effective_date=best.effective_date,
        )

    def list_quarters(self) -> List[str]:
        return sorted({r.relevant_quarter for r in self._rows})

    def list_categories(self, relevant_quarter: Optional[str] = None) -> set:
        rows = self._rows if relevant_quarter is None else self.rows_for_quarter(relevant_quarter)
        return {(r.interconnector_id, r.from_region) for r in rows}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _effective_date_from_filename(filename: str) -> date:
    m = re.search(r"AUCUNITS_(\d{8})\.R\d+", filename, re.IGNORECASE)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    return date.today()


def _parse_csv_line(line: str) -> List[str]:
    reader = _csv.reader([line])
    parts = next(reader)
    return parts[4:]   # strip D,BILLING,AUCTION_UNITS,<n>


def _parse_dt(value: str) -> date:
    value = value.strip().strip('"')
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return date.today()


def _parse(text: str, source_file: str, effective_date: date, source_hash: str) -> List[AucUnitsRow]:
    rows: List[AucUnitsRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("D,BILLING,AUCTION_UNITS"):
            continue
        parts = _parse_csv_line(line)
        if len(parts) < 18:
            continue
        try:
            rows.append(AucUnitsRow(
                source_file=source_file,
                effective_date=effective_date,
                bill_run_type=parts[5].strip(),
                contract_year=int(parts[0]),
                week_no=int(parts[1]),
                bill_run_no=int(parts[2]),
                start_date=_parse_dt(parts[3]),
                end_date=_parse_dt(parts[4]),
                residue_year=int(parts[6]),
                quarter=int(parts[7]),
                relevant_quarter=f"C{int(parts[6])}Q{int(parts[7])}",
                interconnector_id=parts[8].strip(),
                from_region=parts[9].strip(),
                purchased_units=int(float(parts[10])),
                total_surplus=Decimal(parts[11].strip()),
                distributed_surplus=Decimal(parts[12].strip()),
                auction_fees=Decimal(parts[13].strip()),
                net_payment=Decimal(parts[14].strip()),
                net_payment_per_unit=Decimal(parts[15].strip()),
                accumulated_net_payment=Decimal(parts[16].strip()),
                accumulated_net_payment_per_unit=Decimal(parts[17].strip()),
                source_hash=source_hash,
            ))
        except (ValueError, IndexError):
            continue
    return rows
