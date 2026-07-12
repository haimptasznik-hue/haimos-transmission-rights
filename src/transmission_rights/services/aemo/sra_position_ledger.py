"""
SRA Position Ledger

Manages SRDAs, units, acquisition costs, cancellations, assignments, accrued/settled values.
Tracks full position lifecycle with P&L calculations.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class PositionStatusEnum(Enum):
    """Position status through lifecycle."""
    BID = "BID"  # Pending auction result
    ALLOCATED = "ALLOCATED"  # Auction cleared
    OFFERED = "OFFERED"  # Offered for cancellation
    CANCELLED = "CANCELLED"  # Cancelled by holder
    ASSIGNED = "ASSIGNED"  # Assigned to another party
    SETTLED = "SETTLED"  # Final settlement completed
    EXPIRED = "EXPIRED"  # Position expired without settlement


@dataclass(frozen=True)
class SRDAPosition:
    """
    Single Settlement Residue Distribution Agreement position.
    Represents ownership of units for a specific category and quarter.
    """
    srda_id: str  # Unique AEMO SRDA identifier
    category_id: str  # e.g., "NSW1-VIC1"
    relevant_quarter: str  # e.g., "C2028Q1"
    units: int  # Number of units held
    acquisition_price: Decimal  # $/unit purchase price
    acquisition_datetime: datetime
    acquisition_cost: Decimal  # total = units * acquisition_price
    status: PositionStatusEnum
    accrued_value: Decimal = Decimal("0")  # Already-realized entitlement
    forward_value: Decimal = Decimal("0")  # Expected future entitlement
    notes: str = ""


class SRAPositionLedger:
    """
    Manages all SRA positions and tracks P&L.
    
    Phase 4 deliverable:
    - Ingest SRDAs from AEMO
    - Track acquisition cost, cancellations, assignments
    - Compute accrued/settled/forward values
    - Support partial assignments
    - Calculate real-time P&L per position and portfolio
    
    Blueprint Section 8 (P&L example)
    """

    def __init__(self):
        """Initialize empty ledger."""
        self.positions: Dict[str, SRDAPosition] = {}  # srda_id -> position
        self.historical_trades: List[Dict] = []  # Audit trail

    def add_position(self, position: SRDAPosition) -> None:
        """Add a new position (e.g., from auction clearance)."""
        self.positions[position.srda_id] = position
        self.historical_trades.append({
            "action": "add_position",
            "srda_id": position.srda_id,
            "datetime": datetime.utcnow(),
            "details": f"Added {position.units} units at ${position.acquisition_price}/unit",
        })

    def update_position_status(self, srda_id: str, new_status: PositionStatusEnum) -> None:
        """Update position status."""
        if srda_id in self.positions:
            old_pos = self.positions[srda_id]
            self.positions[srda_id] = SRDAPosition(
                srda_id=old_pos.srda_id,
                category_id=old_pos.category_id,
                relevant_quarter=old_pos.relevant_quarter,
                units=old_pos.units,
                acquisition_price=old_pos.acquisition_price,
                acquisition_datetime=old_pos.acquisition_datetime,
                acquisition_cost=old_pos.acquisition_cost,
                status=new_status,
                accrued_value=old_pos.accrued_value,
                forward_value=old_pos.forward_value,
                notes=old_pos.notes,
            )
            self.historical_trades.append({
                "action": "update_status",
                "srda_id": srda_id,
                "datetime": datetime.utcnow(),
                "details": f"Status changed to {new_status.value}",
            })

    def update_valuations(self, srda_id: str, accrued: Decimal, forward: Decimal) -> None:
        """Update accrued and forward valuations for a position."""
        if srda_id in self.positions:
            old_pos = self.positions[srda_id]
            self.positions[srda_id] = SRDAPosition(
                srda_id=old_pos.srda_id,
                category_id=old_pos.category_id,
                relevant_quarter=old_pos.relevant_quarter,
                units=old_pos.units,
                acquisition_price=old_pos.acquisition_price,
                acquisition_datetime=old_pos.acquisition_datetime,
                acquisition_cost=old_pos.acquisition_cost,
                status=old_pos.status,
                accrued_value=accrued,
                forward_value=forward,
                notes=old_pos.notes,
            )

    def partial_assignment(self, srda_id: str, units_assigned: int) -> Optional[str]:
        """
        Assign part of a position to another party.
        Returns new SRDA ID for remaining position, or None if fully assigned.
        
        Args:
            srda_id: Original SRDA ID
            units_assigned: Units being assigned away
            
        Returns:
            New SRDA ID for remaining position, or None if fully assigned
        """
        if srda_id not in self.positions:
            return None

        old_pos = self.positions[srda_id]
        if units_assigned > old_pos.units:
            return None  # Cannot assign more than held

        if units_assigned == old_pos.units:
            # Full assignment
            self.update_position_status(srda_id, PositionStatusEnum.ASSIGNED)
            return None

        # Partial assignment: original position reduced, new SRDA created for remainder
        assigned_pos = SRDAPosition(
            srda_id=srda_id,
            category_id=old_pos.category_id,
            relevant_quarter=old_pos.relevant_quarter,
            units=units_assigned,
            acquisition_price=old_pos.acquisition_price,
            acquisition_datetime=old_pos.acquisition_datetime,
            acquisition_cost=old_pos.acquisition_price * Decimal(units_assigned),
            status=PositionStatusEnum.ASSIGNED,
            accrued_value=old_pos.accrued_value * Decimal(units_assigned) / Decimal(old_pos.units),
            forward_value=old_pos.forward_value * Decimal(units_assigned) / Decimal(old_pos.units),
        )

        remaining_units = old_pos.units - units_assigned
        new_srda_id = f"{srda_id}_remainder"
        remaining_pos = SRDAPosition(
            srda_id=new_srda_id,
            category_id=old_pos.category_id,
            relevant_quarter=old_pos.relevant_quarter,
            units=remaining_units,
            acquisition_price=old_pos.acquisition_price,
            acquisition_datetime=old_pos.acquisition_datetime,
            acquisition_cost=old_pos.acquisition_price * Decimal(remaining_units),
            status=old_pos.status,
            accrued_value=old_pos.accrued_value * Decimal(remaining_units) / Decimal(old_pos.units),
            forward_value=old_pos.forward_value * Decimal(remaining_units) / Decimal(old_pos.units),
        )

        self.positions[srda_id] = assigned_pos
        self.positions[new_srda_id] = remaining_pos
        self.historical_trades.append({
            "action": "partial_assignment",
            "srda_id": srda_id,
            "units_assigned": units_assigned,
            "new_srda_id": new_srda_id,
            "datetime": datetime.utcnow(),
        })

        return new_srda_id

    def portfolio_pnl(self) -> Dict:
        """
        Calculate portfolio P&L summary.
        
        Returns:
            Dict with: total_cost, total_accrued, total_forward, unrealized_pnl, total_pnl
        """
        total_cost = Decimal("0")
        total_accrued = Decimal("0")
        total_forward = Decimal("0")

        for pos in self.positions.values():
            if pos.status not in [PositionStatusEnum.EXPIRED, PositionStatusEnum.CANCELLED]:
                total_cost += pos.acquisition_cost
                total_accrued += pos.accrued_value
                total_forward += pos.forward_value

        unrealized = (total_accrued + total_forward) - total_cost
        return {
            "total_cost": total_cost,
            "total_accrued": total_accrued,
            "total_forward": total_forward,
            "unrealized_pnl": unrealized,
            "total_pnl": unrealized,
        }
