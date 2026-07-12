"""
SRA Product Registry

Manages canonical SRA product definitions, metadata, and effective-date versioning.
Responsible for directional interconnectors, categories, quarters, tranches, max units and proportions.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional
from enum import Enum


class AllocationTypeEnum(Enum):
    """Allocation type for SRA units."""
    PRIMARY = "PRIMARY"
    CANCELLATION = "CANCELLATION"


@dataclass(frozen=True)
class SRAProduct:
    """
    Canonical SRA product identifier and metadata.
    Intersection of: directional interconnector, unit category, relevant quarter, tranche, allocation type.
    """
    product_id: str  # e.g., "NSW1-VIC1_C2028Q1"
    unit_category_id: str  # e.g., "NSW1-VIC1"
    relevant_quarter: str  # e.g., "C2028Q1"
    tranche_no: int  # 1-12
    allocation_type: AllocationTypeEnum
    directional_interconnector: str  # e.g., "NSW1-VIC1"
    from_region: str  # e.g., "NSW1"
    to_region: str  # e.g., "VIC1"
    max_units: int  # Max units available for this category (effective date dependent)
    unit_proportion: float  # 1 / max_units
    effective_date: date  # When this definition became/becomes effective
    description: str = ""


class SRAProductRegistry:
    """
    Registry for all SRA products with historical versioning support.
    
    Phase 1 deliverable:
    - Ingest AEMO's current/historical max-units and proportions table
    - Store historical snapshots (product definitions change on effective dates)
    - Support point-in-time product queries (e.g., "what was product definition on 2027-Q3-01?")
    """

    def __init__(self):
        """Initialize empty registry."""
        self.products: Dict[str, List[SRAProduct]] = {}  # product_id -> [versions]
        self.effective_dates: List[date] = []

    def register_product(self, product: SRAProduct) -> None:
        """Register a versioned product definition."""
        if product.product_id not in self.products:
            self.products[product.product_id] = []
        self.products[product.product_id].append(product)
        if product.effective_date not in self.effective_dates:
            self.effective_dates.append(product.effective_date)
        self.effective_dates.sort()

    def get_product(
        self,
        product_id: str,
        as_of_date: Optional[date] = None,
    ) -> Optional[SRAProduct]:
        """
        Retrieve product definition, optionally as of a specific effective date.
        
        Args:
            product_id: e.g., "NSW1-VIC1_C2028Q1"
            as_of_date: If None, returns latest version
            
        Returns:
            SRAProduct if found, else None
        """
        if product_id not in self.products:
            return None

        versions = self.products[product_id]
        if not versions:
            return None

        if as_of_date is None:
            return versions[-1]  # Latest version

        # Return product effective as of the given date
        matching = [p for p in versions if p.effective_date <= as_of_date]
        return matching[-1] if matching else None

    def list_products(self, as_of_date: Optional[date] = None) -> List[SRAProduct]:
        """
        List all registered products, optionally as of a specific effective date.
        
        Args:
            as_of_date: If None, returns latest versions
            
        Returns:
            List of SRAProduct objects
        """
        result = []
        for versions in self.products.values():
            if as_of_date is None:
                result.append(versions[-1])
            else:
                matching = [p for p in versions if p.effective_date <= as_of_date]
                if matching:
                    result.append(matching[-1])
        return result

    def list_by_quarter(self, relevant_quarter: str, as_of_date: Optional[date] = None) -> List[SRAProduct]:
        """
        List all products for a specific relevant quarter.
        
        Args:
            relevant_quarter: e.g., "C2028Q1"
            as_of_date: If None, returns latest versions
            
        Returns:
            List of SRAProduct objects
        """
        return [p for p in self.list_products(as_of_date) if p.relevant_quarter == relevant_quarter]

    def list_by_interconnector(self, interconnector: str, as_of_date: Optional[date] = None) -> List[SRAProduct]:
        """
        List all products for a specific directional interconnector.
        
        Args:
            interconnector: e.g., "NSW1-VIC1"
            as_of_date: If None, returns latest versions
            
        Returns:
            List of SRAProduct objects
        """
        return [p for p in self.list_products(as_of_date) if p.directional_interconnector == interconnector]
