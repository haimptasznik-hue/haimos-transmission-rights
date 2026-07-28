"""
AEMO Deterministic Payout Reconstruction and Reconciliation Engine.

Takes:
  - AUCUNITS parsed records (via AucUnitsLoader)
  - Dispatch_IRSR quarterly totals CSV (data/derived/irsr/dispatch_quarterly_*.csv)

Produces per unit category per quarter:
  - reconstructed_net_payment_per_unit = quarterly_residue / purchased_units
  - aemo_net_payment_per_unit          = ACCUMULATEDNETPAYMENTPERUNIT from AUCUNITS
  - absolute and percentage variance
  - calculation status and warnings

Governing rule (AEMO methodology):
  gross_value_per_unit = distributable_category_IRSR / maximum_units
  The AUCUNITS ACCUMULATEDNETPAYMENT is AEMO's published quarterly payout.
  PURCHASEDUNITS is units sold (cleared at auction), not maximum_units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Optional

import pandas as pd

from transmission_rights.replication.aucunits_loader import AucUnitsLoader, CategoryQuarterSummary

VARIANCE_THRESHOLD_PCT = Decimal("0.01")   # 1% acceptance target


@dataclass
class PayoutReconRow:
    relevant_quarter: str
    interconnector_id: str
    from_region: str
    purchased_units: int
    quarterly_residue_aud: Decimal
    aemo_accumulated_net_payment: Decimal
    aemo_net_payment_per_unit: Decimal
    reconstructed_net_payment_per_unit: Decimal
    absolute_variance_aud: Decimal
    percentage_variance: Decimal
    aemo_bill_run_type: str
    aemo_source_file: str
    warnings: List[str] = field(default_factory=list)
    calculation_status: str = "unknown"


@dataclass
class PayoutReconReport:
    relevant_quarter: str
    rows: List[PayoutReconRow]
    total_aemo_payment_aud: Decimal
    total_reconstructed_residue_aud: Decimal
    total_absolute_variance_aud: Decimal
    categories_reconciled: int
    categories_with_variance: int
    categories_missing_aucunits: int
    categories_missing_irsr: int


class PayoutReconEngine:
    """
    Deterministic payout reconstruction and AEMO reconciliation engine.

    Usage
    -----
    engine = PayoutReconEngine()
    engine.load_aucunits_directory(Path("data/raw/aemo/auction_units"))
    engine.load_dispatch_quarterly(Path("data/derived/irsr/dispatch_quarterly_C2025Q3_C2026Q2.csv"))
    report = engine.reconcile("C2025Q2")
    print_report(report)
    """

    def __init__(self) -> None:
        self._loader = AucUnitsLoader()
        self._dispatch_df: Optional[pd.DataFrame] = None

    def load_aucunits_directory(self, directory: Path) -> int:
        return self._loader.load_directory(directory)

    def load_aucunits_file(self, path: Path) -> int:
        return len(self._loader.load_file(path))

    def load_dispatch_quarterly(self, path: Path) -> None:
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        df["residue_aud"] = pd.to_numeric(df["residue_aud"], errors="coerce").fillna(0.0)
        if self._dispatch_df is None:
            self._dispatch_df = df
        else:
            self._dispatch_df = (
                pd.concat([self._dispatch_df, df], ignore_index=True)
                .drop_duplicates(subset=["quarter", "interconnector_id", "from_region"], keep="last")
                .reset_index(drop=True)
            )

    def reconcile(self, relevant_quarter: str) -> PayoutReconReport:
        aucunits_cats = self._loader.list_categories(relevant_quarter)
        irsr_cats: set = set()
        if self._dispatch_df is not None:
            q_df = self._dispatch_df[self._dispatch_df["quarter"] == relevant_quarter]
            irsr_cats = {(r["interconnector_id"], r["from_region"]) for _, r in q_df.iterrows()}

        all_cats = sorted(aucunits_cats | irsr_cats)
        rows = [self._reconcile_category(relevant_quarter, ic, reg) for ic, reg in all_cats]

        return PayoutReconReport(
            relevant_quarter=relevant_quarter,
            rows=rows,
            total_aemo_payment_aud=sum((r.aemo_accumulated_net_payment for r in rows), Decimal("0")),
            total_reconstructed_residue_aud=sum((r.quarterly_residue_aud for r in rows), Decimal("0")),
            total_absolute_variance_aud=sum((r.absolute_variance_aud for r in rows), Decimal("0")),
            categories_reconciled=sum(1 for r in rows if r.calculation_status == "reconciled"),
            categories_with_variance=sum(1 for r in rows if "variance" in r.calculation_status),
            categories_missing_aucunits=sum(1 for r in rows if "no_aucunits" in r.warnings),
            categories_missing_irsr=sum(1 for r in rows if "no_dispatch_irsr" in r.warnings),
        )

    def _reconcile_category(self, relevant_quarter: str, ic_id: str, from_region: str) -> PayoutReconRow:
        warnings: List[str] = []

        summary: Optional[CategoryQuarterSummary] = self._loader.get_final_summary(
            relevant_quarter, ic_id, from_region
        )
        if summary is None:
            warnings.append("no_aucunits")
            aemo_acc = aemo_ppu = Decimal("0")
            purchased_units = 0
            bill_run = source_file = "N/A"
        else:
            aemo_acc = summary.accumulated_net_payment
            aemo_ppu = summary.accumulated_net_payment_per_unit
            purchased_units = summary.purchased_units
            bill_run = summary.bill_run_type
            source_file = summary.source_file

        quarterly_residue = Decimal("0")
        if self._dispatch_df is not None:
            mask = (
                (self._dispatch_df["quarter"] == relevant_quarter)
                & (self._dispatch_df["interconnector_id"] == ic_id)
                & (self._dispatch_df["from_region"] == from_region)
            )
            matches = self._dispatch_df[mask]
            if matches.empty:
                warnings.append("no_dispatch_irsr")
            else:
                quarterly_residue = Decimal(str(matches.iloc[0]["residue_aud"]))
        else:
            warnings.append("no_dispatch_irsr")

        if purchased_units > 0:
            recon_ppu = (quarterly_residue / Decimal(purchased_units)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        else:
            recon_ppu = Decimal("0")
            warnings.append("zero_purchased_units")

        abs_var = (quarterly_residue - aemo_acc).copy_abs()
        if aemo_acc != Decimal("0"):
            pct_var = abs_var / aemo_acc.copy_abs()
        elif quarterly_residue == Decimal("0"):
            pct_var = Decimal("0")
        else:
            pct_var = Decimal("1")
            warnings.append("zero_aemo_baseline")

        if "no_aucunits" in warnings or "no_dispatch_irsr" in warnings:
            status = "incomplete_data"
        elif pct_var <= VARIANCE_THRESHOLD_PCT:
            status = "reconciled"
        elif pct_var <= Decimal("0.05"):
            status = "small_variance"
            cause = "likely:settlement_revision_or_fees" if quarterly_residue > aemo_acc else "likely:negative_residue_or_completeness"
            warnings.append(cause)
        else:
            status = "unexplained_variance"
            warnings.append(f"variance={float(pct_var):.2%}")

        return PayoutReconRow(
            relevant_quarter=relevant_quarter,
            interconnector_id=ic_id,
            from_region=from_region,
            purchased_units=purchased_units,
            quarterly_residue_aud=quarterly_residue,
            aemo_accumulated_net_payment=aemo_acc,
            aemo_net_payment_per_unit=aemo_ppu,
            reconstructed_net_payment_per_unit=recon_ppu,
            absolute_variance_aud=abs_var,
            percentage_variance=pct_var,
            aemo_bill_run_type=bill_run,
            aemo_source_file=source_file,
            warnings=warnings,
            calculation_status=status,
        )


def print_report(report: PayoutReconReport) -> None:
    print(f"\n{'='*110}")
    print(f"  AEMO REPLICATION — PAYOUT RECONCILIATION   Quarter: {report.relevant_quarter}")
    print(f"{'='*110}")
    print(f"  {'Interconnector':<18} {'Dir':<8} {'Units':>6}  {'Dispatch IRSR':>18}  {'AEMO AccPmt':>18}  {'Recon PPU':>12}  {'AEMO PPU':>12}  {'Var%':>7}  Status")
    print(f"  {'-'*105}")
    for r in report.rows:
        warn_str = f"  [{', '.join(r.warnings)}]" if r.warnings else ""
        print(
            f"  {r.interconnector_id:<18} {r.from_region:<8} {r.purchased_units:>6}  "
            f"{float(r.quarterly_residue_aud):>18,.2f}  {float(r.aemo_accumulated_net_payment):>18,.2f}  "
            f"{float(r.reconstructed_net_payment_per_unit):>12,.4f}  {float(r.aemo_net_payment_per_unit):>12,.4f}  "
            f"{float(r.percentage_variance):>6.2%}  {r.calculation_status}{warn_str}"
        )
    print(f"  {'-'*105}")
    print(f"  Total AEMO accumulated payments:     AUD {float(report.total_aemo_payment_aud):>18,.2f}")
    print(f"  Total dispatch IRSR (reconstructed): AUD {float(report.total_reconstructed_residue_aud):>18,.2f}")
    print(f"  Total absolute variance:             AUD {float(report.total_absolute_variance_aud):>18,.2f}")
    print(f"\n  Reconciled (<1%): {report.categories_reconciled}  |  With variance: {report.categories_with_variance}  |  Missing AUCUNITS: {report.categories_missing_aucunits}  |  Missing IRSR: {report.categories_missing_irsr}")
    print(f"{'='*110}\n")
