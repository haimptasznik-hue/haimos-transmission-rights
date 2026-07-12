"""
SRA IRSR Calculator

Implements AEMO's interval inter-regional settlement residue (IRSR) calculation.
Core formula: IRSR = (import_price * import_flow) - (export_price * export_flow)
with transmission loss apportionment and directional flow handling.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple, Optional


class IRSRInterval(NamedTuple):
    """Calculated IRSR for a single 5-minute interval."""
    trading_interval: str  # ISO 8601 datetime, e.g., "2026-07-10T15:55:00Z"
    interconnector_id: str  # e.g., "NSW1-VIC1"
    from_region: str  # e.g., "NSW1"
    to_region: str  # e.g., "VIC1"
    from_region_price: Decimal  # $/MWh
    to_region_price: Decimal  # $/MWh
    notional_flow_mw: Decimal  # MW (positive = flow from_region to to_region)
    transmission_loss_mw: Decimal  # MW
    from_region_loss_apportionment: Decimal  # Fraction (0-1)
    to_region_loss_apportionment: Decimal  # Fraction (0-1)
    irsr_dollars: Decimal  # Calculated IRSR in AUD
    direction: str  # "forward" or "reverse" (whether notional flow is in declared direction)


class SRAIRSRCalculator:
    """
    Calculates AEMO's inter-regional settlement residue per 5-minute interval.
    
    Blueprint Section 10, Appendix B1:
    IRSR = (import_price * import_flow) - (export_price * export_flow)
    with loss apportionment per AEMO settlement rules.
    
    Phase 2 deliverable:
    - Reproduce AEMO's published worked example exactly
    - Validate golden tests
    - Reconcile historical quarterly totals
    """

    @staticmethod
    def calculate_interval_irsr(
        trading_interval: str,
        interconnector_id: str,
        from_region: str,
        to_region: str,
        from_region_price: Decimal,
        to_region_price: Decimal,
        notional_flow_mw: Decimal,
        transmission_loss_mw: Decimal,
        from_region_loss_apportionment: Decimal = Decimal("0.6667"),
        to_region_loss_apportionment: Decimal = Decimal("0.3333"),
    ) -> IRSRInterval:
        """
        Calculate IRSR for a single 5-minute interval.
        
        Args:
            trading_interval: ISO 8601 datetime
            interconnector_id: e.g., "NSW1-VIC1"
            from_region: e.g., "NSW1" (nominal export region)
            to_region: e.g., "VIC1" (nominal import region)
            from_region_price: Regional reference price in $/MWh
            to_region_price: Regional reference price in $/MWh
            notional_flow_mw: Notional MW flow from region (positive = forward)
            transmission_loss_mw: Transmission losses in MW
            from_region_loss_apportionment: Fraction of loss to allocate to from_region
            to_region_loss_apportionment: Fraction of loss to allocate to to_region
            
        Returns:
            IRSRInterval with calculated IRSR
            
        Reference: AEMO Guide to Settlements Residue Auction, Appendix B1 worked example
        """
        # Determine flow direction
        direction = "forward" if notional_flow_mw >= 0 else "reverse"

        # Absolute flow values
        abs_flow = abs(notional_flow_mw)

        # Adjusted flows after loss apportionment
        if direction == "forward":
            # Forward flow: from_region exports, to_region imports
            export_flow = abs_flow + (transmission_loss_mw * from_region_loss_apportionment)
            import_flow = abs_flow - (transmission_loss_mw * to_region_loss_apportionment)
            export_price = from_region_price
            import_price = to_region_price
        else:
            # Reverse flow: to_region exports, from_region imports
            export_flow = abs_flow + (transmission_loss_mw * to_region_loss_apportionment)
            import_flow = abs_flow - (transmission_loss_mw * from_region_loss_apportionment)
            export_price = to_region_price
            import_price = from_region_price

        # IRSR = (import_price * import_flow) - (export_price * export_flow)
        irsr = (import_price * import_flow) - (export_price * export_flow)

        return IRSRInterval(
            trading_interval=trading_interval,
            interconnector_id=interconnector_id,
            from_region=from_region,
            to_region=to_region,
            from_region_price=from_region_price,
            to_region_price=to_region_price,
            notional_flow_mw=notional_flow_mw,
            transmission_loss_mw=transmission_loss_mw,
            from_region_loss_apportionment=from_region_loss_apportionment,
            to_region_loss_apportionment=to_region_loss_apportionment,
            irsr_dollars=irsr,
            direction=direction,
        )

    @staticmethod
    def golden_test_appendix_b1() -> IRSRInterval:
        """
        AEMO published worked example from Appendix B1.
        
        Assumptions:
        - Measured flow: 30 MW
        - Transmission losses: 3 MW
        - Loss apportionment: 0.6667 to exporting region, 0.3333 to importing region
        - Export flow: 32 MW (30 + 3*0.6667)
        - Import flow: 29 MW (30 - 3*0.3333)
        - Export price: $30/MWh
        - Import price: $50/MWh
        - Duration: 1 hour
        
        Expected IRSR = (29 * 50) - (32 * 30) = 1450 - 960 = $490
        
        Returns:
            IRSRInterval for validation
        """
        return SRAIRSRCalculator.calculate_interval_irsr(
            trading_interval="2026-01-01T10:00:00Z",
            interconnector_id="NSW1-VIC1",
            from_region="NSW1",
            to_region="VIC1",
            from_region_price=Decimal("30"),
            to_region_price=Decimal("50"),
            notional_flow_mw=Decimal("30"),
            transmission_loss_mw=Decimal("3"),
            from_region_loss_apportionment=Decimal("0.6667"),
            to_region_loss_apportionment=Decimal("0.3333"),
        )
