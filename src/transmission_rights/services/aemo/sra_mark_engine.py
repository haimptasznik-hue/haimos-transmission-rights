"""
SRA Mark Engine

Computes clean fair value, confidence scores, bid/mid/offer marks and probability distributions.
Separates physical value from liquidity adjustment.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional, Dict, List


@dataclass(frozen=True)
class SRAMark:
    """
    Complete valuation mark for an SRA product, updated every 5 minutes.
    """
    product_id: str  # e.g., "NSW1-VIC1_C2028Q1"
    category_id: str
    relevant_quarter: str
    timestamp_utc: str  # ISO 8601
    accrued_value_per_unit: Decimal  # Already-realized entitlement
    forward_value_per_unit: Decimal  # Expected remaining quarter entitlement
    clean_fair_value: Decimal  # Accrued + discounted forward
    model_risk_discount: Decimal  # E.g., 0.05 (5%)
    liquidity_discount: Decimal  # E.g., 0.03 (3%)
    bid_mark: Decimal  # Fair value less liquidity adjustment
    mid_mark: Decimal  # Fair value
    offer_mark: Decimal  # Fair value plus liquidity adjustment
    confidence_score: Decimal  # 0-100, composite measure
    data_freshness: str  # "live", "30min_old", "stale"
    model_stability: Decimal  # 0-100, how confident in model
    scenario_dispersion: Decimal  # 0-100, how tight are scenarios
    probability_distribution: Dict[str, Decimal] = None  # {"P5": x, "P25": y, ..., "P95": z}
    drivers: Dict[str, Decimal] = None  # Attribution by driver
    lineage_id: str = ""  # Reference to audit/lineage trail


class SRAMarkEngine:
    """
    Computes continuous fair-value marks every 5 minutes.
    
    Phase 3 deliverable:
    - Compute accrued value, forward value, clean fair value
    - Bid/mid/offer marks (liquidity-adjusted executable bands)
    - Confidence score (data freshness, model stability, scenario dispersion)
    - Probability distribution (P5, P25, P50, mean, P75, P95)
    - Separate physical value from liquidity discount
    - Publish via API
    
    Blueprint Section 9, 12 (marks and outputs)
    """

    @staticmethod
    def compute_mark(
        product_id: str,
        category_id: str,
        relevant_quarter: str,
        accrued_value_per_unit: Decimal,
        forward_expected_value_per_unit: Decimal,
        model_risk_discount: Decimal = Decimal("0.05"),
        liquidity_discount: Decimal = Decimal("0.03"),
        confidence_score: Optional[Decimal] = None,
        data_freshness: str = "live",
        model_stability: Optional[Decimal] = None,
        scenario_dispersion: Optional[Decimal] = None,
        probability_distribution: Optional[Dict[str, Decimal]] = None,
        drivers: Optional[Dict[str, Decimal]] = None,
    ) -> SRAMark:
        """
        Compute complete mark for a product.
        
        Args:
            product_id: e.g., "NSW1-VIC1_C2028Q1"
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            accrued_value_per_unit: Value already realized
            forward_expected_value_per_unit: Expected remaining value
            model_risk_discount: Discount for model error risk
            liquidity_discount: Discount for execution friction
            confidence_score: 0-100 composite confidence
            data_freshness: "live", "30min_old", or "stale"
            probability_distribution: Dict of percentile names to values
            drivers: Dict of driver name to contribution
            
        Returns:
            SRAMark object
        """
        # Clean fair value = accrued + (discounted forward)
        # Note: accrued value is not discounted (already realized)
        forward_discounted = forward_expected_value_per_unit * (1 - model_risk_discount)
        clean_fair_value = accrued_value_per_unit + forward_discounted

        # Executable marks: bid/mid/offer
        # Bid = fair value - liquidity cost (buyer conservative)
        # Offer = fair value + liquidity cost (seller conservative)
        liquidity_adjustment = clean_fair_value * liquidity_discount
        bid_mark = clean_fair_value - liquidity_adjustment
        mid_mark = clean_fair_value
        offer_mark = clean_fair_value + liquidity_adjustment

        # Model confidence components
        freshness_score = {
            "live": Decimal("100"),
            "30min_old": Decimal("80"),
            "stale": Decimal("50"),
        }.get(data_freshness, Decimal("50"))

        stability_score = model_stability if model_stability is not None else Decimal("75")
        dispersion_score = scenario_dispersion if scenario_dispersion is not None else Decimal("70")

        if confidence_score is None:
            confidence_score = (freshness_score + stability_score + dispersion_score) / Decimal("3")

        if drivers is None:
            drivers = {
                "accrued_value": accrued_value_per_unit,
                "forward_expected_value": forward_expected_value_per_unit,
                "model_risk_impact": forward_expected_value_per_unit - forward_discounted,
                "liquidity_bid_adjustment": -liquidity_adjustment,
                "liquidity_offer_adjustment": liquidity_adjustment,
            }

        return SRAMark(
            product_id=product_id,
            category_id=category_id,
            relevant_quarter=relevant_quarter,
            timestamp_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            accrued_value_per_unit=accrued_value_per_unit,
            forward_value_per_unit=forward_expected_value_per_unit,
            clean_fair_value=clean_fair_value,
            model_risk_discount=model_risk_discount,
            liquidity_discount=liquidity_discount,
            bid_mark=bid_mark,
            mid_mark=mid_mark,
            offer_mark=offer_mark,
            confidence_score=confidence_score,
            data_freshness=data_freshness,
            model_stability=stability_score,
            scenario_dispersion=dispersion_score,
            probability_distribution=probability_distribution or {},
            drivers=drivers,
        )

    @staticmethod
    def validate_mark(mark: SRAMark) -> tuple[bool, str]:
        """
        Validate a mark for consistency and sanity checks.
        
        Args:
            mark: SRAMark to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if mark.bid_mark > mark.mid_mark:
            return False, "Bid mark cannot exceed mid mark"
        if mark.mid_mark > mark.offer_mark:
            return False, "Mid mark cannot exceed offer mark"
        if mark.confidence_score < 0 or mark.confidence_score > 100:
            return False, "Confidence score must be 0-100"
        if mark.model_risk_discount < 0 or mark.model_risk_discount > 1:
            return False, "Model risk discount must be 0-1"
        if mark.liquidity_discount < 0 or mark.liquidity_discount > 1:
            return False, "Liquidity discount must be 0-1"

        return True, "Valid"
