"""
SRA Execution Adapter

Generates AEMO-compliant bid/offer files, validates payloads, submits to AEMO systems,
and parses acknowledgements and results.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict


class BidOfferTypeEnum(Enum):
    """Bid or offer for auction."""
    BID = "BID"  # Want to buy units
    OFFER = "OFFER"  # Want to sell units (cancellation)


@dataclass(frozen=True)
class BidOfferOrder:
    """Single bid or offer order for AEMO submission."""
    order_id: str  # Unique internal order ID
    product_id: str  # e.g., "NSW1-VIC1_C2028Q1_T01"
    auction_id: str  # AEMO auction ID
    order_type: BidOfferTypeEnum
    quantity: int  # Units
    price: Decimal  # $/unit
    timestamp_utc: str  # ISO 8601


@dataclass(frozen=True)
class SubmissionAcknowledgement:
    """Acknowledgement from AEMO that file was received."""
    submission_id: str  # AEMO-assigned file ID
    participant_id: str
    file_name: str
    received_datetime: str  # ISO 8601
    status: str  # "received", "processing", "validated", "error"
    message: Optional[str] = None


class SRAExecutionAdapter:
    """
    Adapter for AEMO submission, validation and reconciliation workflows.
    
    Phase 4 deliverable:
    - Generate AEMO bid/offer file formats (per Section 6 technical spec)
    - Pre-submission validator: check product, quarter, units, prices, file limits
    - Support Participant File Server or Data Interchange upload
    - Parse acknowledgement from AEMO
    - Reconciliation service confirms AEMO receipt and latest-file status
    
    Blueprint Section 6, 12 (execution mechanics)
    """

    def __init__(self, participant_id: str, participant_password: Optional[str] = None):
        """
        Initialize adapter with participant credentials.
        
        Args:
            participant_id: AEMO participant ID
            participant_password: Optional password (for FTP/API auth)
        """
        self.participant_id = participant_id
        self.participant_password = participant_password
        self.submitted_orders: List[BidOfferOrder] = []
        self.acknowledgements: List[SubmissionAcknowledgement] = []

    def add_order(self, order: BidOfferOrder) -> None:
        """
        Queue an order for submission.
        
        Args:
            order: BidOfferOrder to submit
        """
        self.submitted_orders.append(order)

    def validate_orders(self, orders: List[BidOfferOrder]) -> tuple[bool, List[str]]:
        """
        Pre-submission validation of orders.
        
        Args:
            orders: List of BidOfferOrder objects
            
        Returns:
            (is_valid, [error_messages]) tuple
        """
        errors = []

        if not orders:
            errors.append("No orders to submit")
            return False, errors

        seen_order_ids = set()
        for order in orders:
            if order.quantity <= 0:
                errors.append(f"Order {order.order_id}: quantity must be > 0")
            if order.price < 0:
                errors.append(f"Order {order.order_id}: price cannot be negative")
            if not order.product_id:
                errors.append(f"Order {order.order_id}: product_id required")
            if not order.auction_id:
                errors.append(f"Order {order.order_id}: auction_id required")
            if order.order_id in seen_order_ids:
                errors.append(f"Order {order.order_id}: duplicate order_id in submission")
            seen_order_ids.add(order.order_id)

        return len(errors) == 0, errors

    def generate_aemo_file(self, orders: List[BidOfferOrder], file_format: str = "csv") -> str:
        """
        Generate AEMO-compliant submission file (CSV or XML).
        
        Args:
            orders: List of orders to include
            file_format: "csv" or "xml" (default: csv)
            
        Returns:
            File contents as string
        """
        is_valid, errors = self.validate_orders(orders)
        if not is_valid:
            raise ValueError("Invalid orders: " + "; ".join(errors))

        if file_format == "csv":
            lines = [
                "Participant_ID,Auction_ID,Order_Type,Quantity_Units,Price_AUD_per_Unit",
            ]
            for order in orders:
                lines.append(
                    f"{self.participant_id},{order.auction_id},"
                    f"{order.order_type.value},{order.quantity},{order.price}"
                )
            return "\n".join(lines)

        elif file_format == "xml":
            lines = ['<?xml version="1.0" encoding="UTF-8"?>']
            lines.append("<SRA_Submission>")
            lines.append(f"  <Participant_ID>{self.participant_id}</Participant_ID>")
            lines.append("  <Orders>")
            for order in orders:
                lines.append("    <Order>")
                lines.append(f"      <Auction_ID>{order.auction_id}</Auction_ID>")
                lines.append(f"      <Order_Type>{order.order_type.value}</Order_Type>")
                lines.append(f"      <Quantity_Units>{order.quantity}</Quantity_Units>")
                lines.append(f"      <Price_AUD_per_Unit>{order.price}</Price_AUD_per_Unit>")
                lines.append("    </Order>")
            lines.append("  </Orders>")
            lines.append("</SRA_Submission>")
            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported file format: {file_format}")

    def register_acknowledgement(self, ack: SubmissionAcknowledgement) -> None:
        """
        Register acknowledgement from AEMO.
        
        Args:
            ack: SubmissionAcknowledgement from AEMO
        """
        self.acknowledgements.append(ack)

    def get_latest_acknowledgement(self) -> Optional[SubmissionAcknowledgement]:
        """Get most recent acknowledgement from AEMO."""
        return self.acknowledgements[-1] if self.acknowledgements else None

    def reconcile_with_aemo_results(
        self,
        aemo_results: Dict,  # e.g., {"orders": [...], "clearing_prices": {...}}
    ) -> Dict:
        """
        Reconcile submitted orders with AEMO's official results.
        
        Args:
            aemo_results: Results from AEMO (auction results, clears, allocations)
            
        Returns:
            Reconciliation summary dict
        """
        result_order_ids = {
            str(order.get("order_id"))
            for order in aemo_results.get("orders", [])
            if isinstance(order, dict) and order.get("order_id") is not None
        }
        submitted_order_ids = {order.order_id for order in self.submitted_orders}
        matched_order_ids = submitted_order_ids.intersection(result_order_ids)

        return {
            "participant_id": self.participant_id,
            "orders_submitted": len(self.submitted_orders),
            "orders_reported_by_aemo": len(result_order_ids),
            "orders_matched": len(matched_order_ids),
            "orders_missing_from_aemo": len(submitted_order_ids - result_order_ids),
            "acknowledgements_received": len(self.acknowledgements),
            "latest_status": self.get_latest_acknowledgement().status if self.acknowledgements else None,
            "ready_for_next_auction": len(self.acknowledgements) > 0,
        }
