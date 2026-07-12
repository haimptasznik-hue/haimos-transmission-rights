"""
SRA Market Calendar

Manages auction opening/closing dates, notices and product availability.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class AuctionEvent:
    """Calendar entry for an SRA auction."""
    auction_id: str  # e.g., "SRA_2026_Q3_T01"
    relevant_quarter: str  # e.g., "C2028Q1"
    tranche_no: int  # 1-12
    auction_open_datetime: datetime
    auction_close_datetime: datetime
    notice_published_datetime: Optional[datetime] = None
    description: str = ""


class SRAMarketCalendar:
    """
    Manages SRA auction calendar and product availability.
    
    Phase 1 deliverable:
    - Fetch and store SRA auction dates 2025-2026
    - Support queries for upcoming, active and completed auctions
    - Track tranche release schedule
    """

    def __init__(self):
        """Initialize empty calendar."""
        self.events: List[AuctionEvent] = []

    def add_event(self, event: AuctionEvent) -> None:
        """Add an auction event."""
        self.events.append(event)
        self.events.sort(key=lambda e: e.auction_open_datetime)

    def get_active_auctions(self, as_of_datetime: Optional[datetime] = None) -> List[AuctionEvent]:
        """
        Get currently active auctions (between open and close datetime).
        
        Args:
            as_of_datetime: If None, uses current time
            
        Returns:
            List of active AuctionEvent objects
        """
        now = as_of_datetime or datetime.utcnow()
        return [e for e in self.events if e.auction_open_datetime <= now <= e.auction_close_datetime]

    def get_upcoming_auctions(self, as_of_datetime: Optional[datetime] = None, limit: int = 5) -> List[AuctionEvent]:
        """
        Get upcoming auctions.
        
        Args:
            as_of_datetime: If None, uses current time
            limit: Max number to return
            
        Returns:
            List of upcoming AuctionEvent objects
        """
        now = as_of_datetime or datetime.utcnow()
        upcoming = [e for e in self.events if e.auction_open_datetime > now]
        return upcoming[:limit]

    def get_by_quarter(self, relevant_quarter: str) -> List[AuctionEvent]:
        """
        Get all auctions for a specific relevant quarter.
        
        Args:
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            List of AuctionEvent objects
        """
        return [e for e in self.events if e.relevant_quarter == relevant_quarter]

    def get_tranche_schedule(self, relevant_quarter: str) -> List[AuctionEvent]:
        """
        Get all 12 tranches for a specific relevant quarter in order.
        
        Args:
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            List of AuctionEvent objects sorted by tranche_no
        """
        events = self.get_by_quarter(relevant_quarter)
        return sorted(events, key=lambda e: e.tranche_no)
