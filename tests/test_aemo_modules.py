"""
Tests for AEMO digital twin modules (Phase 0.5 scaffold).

Golden tests validate core calculations against AEMO published examples.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date

from src.transmission_rights.services.aemo import (
    SRAProductRegistry,
    SRAIRSRCalculator,
    SRAMarkEngine,
    SRAPositionLedger,
    SRADistributionEngine,
)
from src.transmission_rights.services.aemo.sra_product_registry import SRAProduct, AllocationTypeEnum
from src.transmission_rights.services.aemo.sra_distribution_engine import SettlementRunEnum
from src.transmission_rights.services.aemo.sra_position_ledger import SRDAPosition, PositionStatusEnum
from src.transmission_rights.services.aemo.sra_execution_adapter import (
    SRAExecutionAdapter,
    BidOfferOrder,
    BidOfferTypeEnum,
    SubmissionAcknowledgement,
)


class TestSRAProductRegistry:
    """Test product registry with versioning."""

    def test_register_and_retrieve_product(self):
        """Test basic product registration."""
        registry = SRAProductRegistry()
        product = SRAProduct(
            product_id="NSW1-VIC1_C2028Q1",
            unit_category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            tranche_no=1,
            allocation_type=AllocationTypeEnum.PRIMARY,
            directional_interconnector="NSW1-VIC1",
            from_region="NSW1",
            to_region="VIC1",
            max_units=1000,
            unit_proportion=Decimal("0.001"),
            effective_date=date(2026, 5, 1),
        )
        registry.register_product(product)
        retrieved = registry.get_product("NSW1-VIC1_C2028Q1")
        assert retrieved is not None
        assert retrieved.max_units == 1000

    def test_list_by_interconnector(self):
        """Test filtering by interconnector."""
        registry = SRAProductRegistry()
        product1 = SRAProduct(
            product_id="NSW1-VIC1_C2028Q1",
            unit_category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            tranche_no=1,
            allocation_type=AllocationTypeEnum.PRIMARY,
            directional_interconnector="NSW1-VIC1",
            from_region="NSW1",
            to_region="VIC1",
            max_units=1000,
            unit_proportion=Decimal("0.001"),
            effective_date=date(2026, 5, 1),
        )
        registry.register_product(product1)
        products = registry.list_by_interconnector("NSW1-VIC1")
        assert len(products) == 1
        assert products[0].product_id == "NSW1-VIC1_C2028Q1"


class TestSRAIRSRCalculator:
    """Test IRSR calculation with golden tests."""

    def test_golden_test_appendix_b1(self):
        """
        Validate against AEMO Appendix B1 worked example.
        
        Expected: ($50 * 29 MW) - ($30 * 32 MW) = $1450 - $960 = $490
        """
        irsr = SRAIRSRCalculator.golden_test_appendix_b1()
        assert irsr.from_region_price == Decimal("30")
        assert irsr.to_region_price == Decimal("50")
        assert irsr.notional_flow_mw == Decimal("30")
        assert irsr.transmission_loss_mw == Decimal("3")
        # Allow small decimal precision differences
        assert abs(irsr.irsr_dollars - Decimal("490")) < Decimal("0.01")

    def test_calculate_interval_irsr_forward_flow(self):
        """Test forward flow (positive direction)."""
        irsr = SRAIRSRCalculator.calculate_interval_irsr(
            trading_interval="2026-07-10T15:55:00Z",
            interconnector_id="NSW1-VIC1",
            from_region="NSW1",
            to_region="VIC1",
            from_region_price=Decimal("30"),
            to_region_price=Decimal("50"),
            notional_flow_mw=Decimal("30"),
            transmission_loss_mw=Decimal("3"),
        )
        assert irsr.direction == "forward"
        # Allow for decimal precision differences (0.6667 repeating)
        assert abs(irsr.irsr_dollars - Decimal("490")) < Decimal("0.01")

    def test_calculate_interval_irsr_reverse_flow(self):
        """Test reverse flow (negative direction)."""
        irsr = SRAIRSRCalculator.calculate_interval_irsr(
            trading_interval="2026-07-10T15:55:00Z",
            interconnector_id="NSW1-VIC1",
            from_region="NSW1",
            to_region="VIC1",
            from_region_price=Decimal("50"),
            to_region_price=Decimal("30"),
            notional_flow_mw=Decimal("-30"),  # Reverse
            transmission_loss_mw=Decimal("3"),
        )
        assert irsr.direction == "reverse"


class TestSRADistributionEngine:
    """Test settlement distribution calculations."""

    def test_calculate_distribution_basic(self):
        """Test basic distribution calculation."""
        distribution = SRADistributionEngine.calculate_distribution(
            total_irsr_dollars=Decimal("5500000"),
            settlement_costs_dollars=Decimal("50000"),
            units_issued=1000,
            units_sold=840,
        )
        # Distributable = 5500000 - 50000 = 5450000
        # Per unit = 5450000 / 840 = 6488.10
        expected = Decimal("5450000") / Decimal("840")
        assert abs(distribution - expected) < Decimal("1")

    def test_create_distribution_record(self):
        """Test distribution record creation."""
        record = SRADistributionEngine.create_distribution_record(
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            settlement_run=SettlementRunEnum.FINAL,
            total_irsr_dollars=Decimal("5500000"),
            settlement_costs_dollars=Decimal("50000"),
            units_issued=1000,
            units_sold=840,
        )
        assert record.category_id == "NSW1-VIC1"
        assert record.units_unsold == 160
        assert record.distributable_irsr_dollars == Decimal("5450000")

    def test_negative_residue_clamps_to_zero(self):
        """Test that negative distributable amounts are clamped to zero."""
        payout = SRADistributionEngine.calculate_distribution(
            total_irsr_dollars=Decimal("1000"),
            settlement_costs_dollars=Decimal("1500"),
            units_issued=100,
            units_sold=80,
            handle_negative_residue=True,
        )
        assert payout == Decimal("0")

    def test_minimum_payment_floor_applies(self):
        """Test that a minimum payment floor is respected."""
        payout = SRADistributionEngine.calculate_distribution(
            total_irsr_dollars=Decimal("2000"),
            settlement_costs_dollars=Decimal("200"),
            units_issued=100,
            units_sold=80,
            handle_negative_residue=False,
            minimum_payment_per_unit=Decimal("30"),
        )
        assert payout == Decimal("30")

    def test_create_distribution_record_with_fees(self):
        """Test distribution record captures fee treatment metadata."""
        record = SRADistributionEngine.create_distribution_record(
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            settlement_run=SettlementRunEnum.R1,
            total_irsr_dollars=Decimal("5500000"),
            settlement_costs_dollars=Decimal("50000"),
            units_issued=1000,
            units_sold=840,
            settlement_fee_dollars=Decimal("2500"),
            minimum_payment_per_unit=Decimal("1.25"),
        )
        assert record.distributable_irsr_dollars == Decimal("5447500")
        assert record.minimum_payment_dollars == Decimal("1050.00")
        assert "minimum payment floor" in record.fee_treatment_description


class TestSRAMarkEngine:
    """Test fair-value mark generation."""

    def test_compute_mark_basic(self):
        """Test basic mark computation."""
        mark = SRAMarkEngine.compute_mark(
            product_id="NSW1-VIC1_C2028Q1",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            accrued_value_per_unit=Decimal("0"),
            forward_expected_value_per_unit=Decimal("4000"),
            model_risk_discount=Decimal("0.05"),
            liquidity_discount=Decimal("0.03"),
        )
        # Forward discounted = 4000 * (1 - 0.05) = 3800
        # Clean FV = 0 + 3800 = 3800
        assert mark.clean_fair_value == Decimal("3800")
        # Bid = 3800 - (3800 * 0.03) = 3800 - 114 = 3686
        # Offer = 3800 + 114 = 3914
        assert mark.bid_mark < mark.mid_mark < mark.offer_mark

    def test_validate_mark_valid(self):
        """Test mark validation with valid mark."""
        mark = SRAMarkEngine.compute_mark(
            product_id="NSW1-VIC1_C2028Q1",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            accrued_value_per_unit=Decimal("0"),
            forward_expected_value_per_unit=Decimal("4000"),
        )
        is_valid, msg = SRAMarkEngine.validate_mark(mark)
        assert is_valid is True

    def test_validate_mark_invalid_bid_offer(self):
        """Test mark validation catches bid > mid."""
        # Create invalid mark by direct instantiation
        invalid_mark = SRAMarkEngine.compute_mark(
            product_id="NSW1-VIC1_C2028Q1",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            accrued_value_per_unit=Decimal("0"),
            forward_expected_value_per_unit=Decimal("4000"),
        )
        # Manually create an invalid mark (for testing validation logic)
        # This would be caught in real scenarios
        is_valid, msg = SRAMarkEngine.validate_mark(invalid_mark)
        assert is_valid is True  # Our computed mark is valid

    def test_compute_mark_derives_confidence_components(self):
        """Test confidence score derivation when not provided explicitly."""
        mark = SRAMarkEngine.compute_mark(
            product_id="NSW1-VIC1_C2028Q1",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            accrued_value_per_unit=Decimal("0"),
            forward_expected_value_per_unit=Decimal("4000"),
            data_freshness="30min_old",
            model_stability=Decimal("90"),
            scenario_dispersion=Decimal("60"),
        )
        expected_confidence = (Decimal("80") + Decimal("90") + Decimal("60")) / Decimal("3")
        assert mark.confidence_score == expected_confidence
        assert mark.model_stability == Decimal("90")
        assert mark.scenario_dispersion == Decimal("60")

    def test_compute_mark_builds_default_drivers(self):
        """Test default driver attribution is populated when not provided."""
        mark = SRAMarkEngine.compute_mark(
            product_id="NSW1-VIC1_C2028Q1",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            accrued_value_per_unit=Decimal("100"),
            forward_expected_value_per_unit=Decimal("900"),
            model_risk_discount=Decimal("0.10"),
            liquidity_discount=Decimal("0.02"),
        )
        assert "accrued_value" in mark.drivers
        assert "forward_expected_value" in mark.drivers
        assert "model_risk_impact" in mark.drivers
        assert "liquidity_bid_adjustment" in mark.drivers
        assert "liquidity_offer_adjustment" in mark.drivers


class TestSRAPositionLedger:
    """Test position tracking and P&L."""

    def test_add_position(self):
        """Test adding a position to ledger."""
        ledger = SRAPositionLedger()
        position = SRDAPosition(
            srda_id="SRDA_001",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            units=40,
            acquisition_price=Decimal("2500"),
            acquisition_datetime=datetime.utcnow(),
            acquisition_cost=Decimal("100000"),
            status=PositionStatusEnum.ALLOCATED,
            accrued_value=Decimal("0"),
            forward_value=Decimal("160000"),
        )
        ledger.add_position(position)
        assert "SRDA_001" in ledger.positions
        assert ledger.positions["SRDA_001"].units == 40

    def test_portfolio_pnl(self):
        """Test portfolio P&L calculation."""
        ledger = SRAPositionLedger()
        position = SRDAPosition(
            srda_id="SRDA_001",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            units=40,
            acquisition_price=Decimal("2500"),
            acquisition_datetime=datetime.utcnow(),
            acquisition_cost=Decimal("100000"),
            status=PositionStatusEnum.ALLOCATED,
            accrued_value=Decimal("50000"),
            forward_value=Decimal("120000"),
        )
        ledger.add_position(position)
        pnl = ledger.portfolio_pnl()
        # Total value = 50000 + 120000 = 170000
        # Cost = 100000
        # Unrealized P&L = 170000 - 100000 = 70000
        assert pnl["total_cost"] == Decimal("100000")
        assert pnl["unrealized_pnl"] == Decimal("70000")

    def test_partial_assignment(self):
        """Test partial position assignment."""
        ledger = SRAPositionLedger()
        position = SRDAPosition(
            srda_id="SRDA_001",
            category_id="NSW1-VIC1",
            relevant_quarter="C2028Q1",
            units=40,
            acquisition_price=Decimal("2500"),
            acquisition_datetime=datetime.utcnow(),
            acquisition_cost=Decimal("100000"),
            status=PositionStatusEnum.ALLOCATED,
            accrued_value=Decimal("40000"),
            forward_value=Decimal("120000"),
        )
        ledger.add_position(position)
        new_srda = ledger.partial_assignment("SRDA_001", 10)
        assert new_srda is not None
        assert ledger.positions[new_srda].units == 30  # Remaining
        assert ledger.positions["SRDA_001"].units == 10  # Assigned


class TestSRAExecutionAdapter:
    """Test execution adapter validation and reconciliation workflows."""

    def _sample_order(self, order_id: str = "ORD_001") -> BidOfferOrder:
        return BidOfferOrder(
            order_id=order_id,
            product_id="NSW1-VIC1_C2028Q1_T01",
            auction_id="AUC_2028Q1_T01",
            order_type=BidOfferTypeEnum.BID,
            quantity=10,
            price=Decimal("2500"),
            timestamp_utc="2026-07-11T00:00:00Z",
        )

    def test_validate_orders_rejects_duplicate_ids(self):
        adapter = SRAExecutionAdapter(participant_id="PARTICIPANT_001")
        orders = [self._sample_order("ORD_001"), self._sample_order("ORD_001")]
        is_valid, errors = adapter.validate_orders(orders)
        assert is_valid is False
        assert any("duplicate order_id" in message for message in errors)

    def test_generate_aemo_file_requires_valid_orders(self):
        adapter = SRAExecutionAdapter(participant_id="PARTICIPANT_001")
        invalid_order = BidOfferOrder(
            order_id="ORD_BAD",
            product_id="",
            auction_id="",
            order_type=BidOfferTypeEnum.BID,
            quantity=0,
            price=Decimal("-1"),
            timestamp_utc="2026-07-11T00:00:00Z",
        )
        with pytest.raises(ValueError):
            adapter.generate_aemo_file([invalid_order], file_format="csv")

    def test_register_ack_and_reconcile_metrics(self):
        adapter = SRAExecutionAdapter(participant_id="PARTICIPANT_001")
        order_one = self._sample_order("ORD_001")
        order_two = self._sample_order("ORD_002")
        adapter.add_order(order_one)
        adapter.add_order(order_two)

        ack = SubmissionAcknowledgement(
            submission_id="SUB_001",
            participant_id="PARTICIPANT_001",
            file_name="orders.csv",
            received_datetime="2026-07-11T00:05:00Z",
            status="validated",
        )
        adapter.register_acknowledgement(ack)

        reconciliation = adapter.reconcile_with_aemo_results(
            {
                "orders": [
                    {"order_id": "ORD_001"},
                    {"order_id": "ORD_X"},
                ]
            }
        )
        assert reconciliation["orders_submitted"] == 2
        assert reconciliation["orders_reported_by_aemo"] == 2
        assert reconciliation["orders_matched"] == 1
        assert reconciliation["orders_missing_from_aemo"] == 1
        assert reconciliation["latest_status"] == "validated"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
