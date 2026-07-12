"""
SRA Distribution Engine

Implements settlement allocation logic per AEMO Settlement Residue Auction rules.
Handles unsold units, negative-residue rules, settlement revisions (R0/R1/R2/final),
minimum payment logic and fee treatment.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class SettlementRunEnum(Enum):
    """Settlement run versions."""
    R0 = "R0"  # Pre-settlement
    R1 = "R1"  # First revision
    R2 = "R2"  # Second revision
    FINAL = "FINAL"


@dataclass(frozen=True)
class CategoryDistribution:
    """
    Distributable IRSR for a single SRA category and relevant quarter.
    """
    category_id: str  # e.g., "NSW1-VIC1"
    relevant_quarter: str  # e.g., "C2028Q1"
    settlement_run: SettlementRunEnum
    total_irsr_dollars: Decimal  # Total directional IRSR accumulated in quarter
    settlement_costs_dollars: Decimal  # AEMO settlement costs to be deducted
    distributable_irsr_dollars: Decimal  # Total IRSR - costs
    negative_residue_treatment: str  # Description of how negative residues were handled
    units_issued: int  # Number of units issued for this category/quarter
    units_sold: int  # Number of units that cleared in auctions
    units_unsold: int  # Number of units not sold
    minimum_payment_dollars: Optional[Decimal] = None  # If applicable
    fee_treatment_description: str = ""


class SRADistributionEngine:
    """
    Implements settlement allocation logic per AEMO rules.
    
    Phase 2 deliverable:
    - Handle unsold units treatment
    - Implement negative-residue rules
    - Version by settlement run (R0/R1/R2/final)
    - Test against historical data
    
    Blueprint Section 3, 8 (distribution mechanics)
    """

    @staticmethod
    def calculate_distribution(
        total_irsr_dollars: Decimal,
        settlement_costs_dollars: Decimal,
        units_issued: int,
        units_sold: int,
        handle_negative_residue: bool = True,
        settlement_fee_dollars: Decimal = Decimal("0"),
        minimum_payment_per_unit: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate distributable IRSR per unit.
        
        Args:
            total_irsr_dollars: Total directional IRSR for the quarter
            settlement_costs_dollars: AEMO costs to deduct
            units_issued: Total units issued
            units_sold: Units that cleared
            handle_negative_residue: If True, include negative-residue logic
            settlement_fee_dollars: Additional settlement fees to deduct
            minimum_payment_per_unit: Optional floor on payout per unit
            
        Returns:
            Distributable amount per unit in AUD
            
        Note: Negative IRSR (counter-price flow) is handled per AEMO rules.
              Unsold units are typically not distributed (or treated per rule).
        """
        if units_sold <= 0:
            return Decimal("0")

        distributable = total_irsr_dollars - settlement_costs_dollars - settlement_fee_dollars

        if handle_negative_residue and distributable <= 0:
            return Decimal("0")

        # Distribute to sold units only (unsold units typically receive nothing)
        payout_per_unit = distributable / Decimal(units_sold)

        if minimum_payment_per_unit is not None:
            payout_per_unit = max(payout_per_unit, minimum_payment_per_unit)

        return payout_per_unit

    @staticmethod
    def create_distribution_record(
        category_id: str,
        relevant_quarter: str,
        settlement_run: SettlementRunEnum,
        total_irsr_dollars: Decimal,
        settlement_costs_dollars: Decimal,
        units_issued: int,
        units_sold: int,
        negative_residue_treatment: str = "Accrued per AEMO allocation rules",
        settlement_fee_dollars: Decimal = Decimal("0"),
        minimum_payment_per_unit: Optional[Decimal] = None,
    ) -> CategoryDistribution:
        """
        Create a versioned distribution record.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            settlement_run: R0, R1, R2 or FINAL
            total_irsr_dollars: Total IRSR
            settlement_costs_dollars: Costs to deduct
            units_issued: Total issued
            units_sold: Units that cleared
            negative_residue_treatment: Description
            settlement_fee_dollars: Additional fee treatment to deduct
            minimum_payment_per_unit: Optional floor on payout per unit
            
        Returns:
            CategoryDistribution record
        """
        distributable = total_irsr_dollars - settlement_costs_dollars - settlement_fee_dollars
        units_unsold = max(units_issued - units_sold, 0)

        if distributable <= 0:
            distributable = Decimal("0")

        fee_treatment_description = "Per current Auction Participation Agreement"
        if settlement_fee_dollars != 0:
            fee_treatment_description = (
                f"Includes {settlement_fee_dollars} AUD settlement fees deducted before allocation"
            )
        if minimum_payment_per_unit is not None:
            fee_treatment_description += f"; minimum payment floor {minimum_payment_per_unit} AUD/unit"

        return CategoryDistribution(
            category_id=category_id,
            relevant_quarter=relevant_quarter,
            settlement_run=settlement_run,
            total_irsr_dollars=total_irsr_dollars,
            settlement_costs_dollars=settlement_costs_dollars,
            distributable_irsr_dollars=distributable,
            negative_residue_treatment=negative_residue_treatment,
            units_issued=units_issued,
            units_sold=units_sold,
            units_unsold=units_unsold,
            minimum_payment_dollars=(minimum_payment_per_unit * Decimal(units_sold)) if minimum_payment_per_unit is not None else None,
            fee_treatment_description=fee_treatment_description,
        )

    @staticmethod
    def payout_per_unit(distribution: CategoryDistribution) -> Decimal:
        """
        Calculate payout per unit from a distribution record.
        
        Args:
            distribution: CategoryDistribution record
            
        Returns:
            Payout per unit in AUD
        """
        if distribution.units_sold <= 0:
            return Decimal("0")

        payout = distribution.distributable_irsr_dollars / Decimal(distribution.units_sold)
        if distribution.minimum_payment_dollars is not None:
            floor = distribution.minimum_payment_dollars / Decimal(distribution.units_sold)
            payout = max(payout, floor)
        return payout
