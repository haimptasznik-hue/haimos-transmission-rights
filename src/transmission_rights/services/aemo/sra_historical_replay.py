"""
SRA Historical Replay

Point-in-time reconstruction of IRSR and distributions with settlement revisions.
Supports queries at specific effective dates (R0, R1, R2, final runs).
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional
from .sra_distribution_engine import SettlementRunEnum, CategoryDistribution


@dataclass(frozen=True)
class HistoricalSnapshot:
    """
    Point-in-time historical snapshot of a category's IRSR and distribution.
    """
    effective_date: date
    category_id: str
    relevant_quarter: str
    settlement_run: SettlementRunEnum
    total_irsr_dollars: Decimal
    distributable_irsr_dollars: Decimal
    payout_per_unit: Decimal
    data_source: str  # e.g., "AEMO_SETTLEMENT_RUN_R0"


class SRAHistoricalReplay:
    """
    Reconstructs historical IRSR and distributions at specific effective dates.
    
    Phase 2 deliverable:
    - Use effective-date product registry snapshots
    - Support R0/R1/R2/final settlement runs
    - Output: accrued and final distributions per unit per quarter
    - Reconcile to AEMO settlement and auction records
    
    Blueprint Section 2, 8 (historical mechanics)
    """

    def __init__(self):
        """Initialize empty replay engine."""
        self.snapshots: Dict[str, List[HistoricalSnapshot]] = {}  # (category, quarter) -> [snapshots]

    def add_snapshot(self, snapshot: HistoricalSnapshot) -> None:
        """Add a historical snapshot."""
        key = (snapshot.category_id, snapshot.relevant_quarter)
        if key not in self.snapshots:
            self.snapshots[key] = []
        self.snapshots[key].append(snapshot)
        # Sort by effective date and settlement run
        self.snapshots[key].sort(key=lambda s: (s.effective_date, s.settlement_run.value))

    def get_snapshot(
        self,
        category_id: str,
        relevant_quarter: str,
        as_of_date: Optional[date] = None,
        settlement_run: Optional[SettlementRunEnum] = None,
    ) -> Optional[HistoricalSnapshot]:
        """
        Retrieve historical snapshot at a specific date and settlement run.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            as_of_date: If None, returns latest snapshot
            settlement_run: If None, returns latest settlement run for the date
            
        Returns:
            HistoricalSnapshot if found, else None
        """
        key = (category_id, relevant_quarter)
        if key not in self.snapshots:
            return None

        snaps = self.snapshots[key]
        if not snaps:
            return None

        # Filter by date if specified
        if as_of_date is not None:
            snaps = [s for s in snaps if s.effective_date <= as_of_date]
        if not snaps:
            return None

        # Filter by settlement run if specified
        if settlement_run is not None:
            snaps = [s for s in snaps if s.settlement_run == settlement_run]
        if not snaps:
            return None

        return snaps[-1]  # Latest matching snapshot

    def get_all_runs(
        self,
        category_id: str,
        relevant_quarter: str,
        as_of_date: Optional[date] = None,
    ) -> List[HistoricalSnapshot]:
        """
        Get all settlement runs (R0, R1, R2, final) for a category/quarter.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            as_of_date: If None, returns latest versions
            
        Returns:
            List of HistoricalSnapshot objects, one per settlement run
        """
        key = (category_id, relevant_quarter)
        if key not in self.snapshots:
            return []

        snaps = self.snapshots[key]
        if as_of_date is not None:
            snaps = [s for s in snaps if s.effective_date <= as_of_date]

        # Return one per settlement run (latest version of each)
        result_by_run = {}
        for snap in snaps:
            result_by_run[snap.settlement_run] = snap

        return sorted(result_by_run.values(), key=lambda s: s.settlement_run.value)

    def reconciliation_delta(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> Optional[Dict]:
        """
        Calculate reconciliation deltas between settlement runs.
        Useful for back-testing against AEMO published data.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            Dict showing payout_per_unit changes across R0 -> R1 -> R2 -> final
        """
        runs = self.get_all_runs(category_id, relevant_quarter)
        if not runs:
            return None

        deltas = []
        prev_payout = None
        for run in runs:
            if prev_payout is not None:
                delta = run.payout_per_unit - prev_payout
                deltas.append({
                    "from_run": runs[len(deltas) - 1].settlement_run.value,
                    "to_run": run.settlement_run.value,
                    "payout_per_unit": run.payout_per_unit,
                    "delta": delta,
                    "delta_percentage": (delta / prev_payout * 100) if prev_payout != 0 else Decimal("0"),
                })
            prev_payout = run.payout_per_unit

        return {
            "category_id": category_id,
            "relevant_quarter": relevant_quarter,
            "deltas": deltas,
            "final_payout": runs[-1].payout_per_unit if runs else None,
        }
