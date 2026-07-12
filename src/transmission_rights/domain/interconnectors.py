"""
transmission_rights/domain/interconnectors.py — Reference data for NEM interconnectors
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Interconnector:
    """Static reference data for a directional interconnector."""
    interconnector_id: str
    direction_from_region: str
    direction_to_region: str
    category_id: str
    max_units: int = 1000
    unit_proportion: float = 0.001

    @classmethod
    def registry(cls) -> dict[str, "Interconnector"]:
        """Return all known interconnector categories (as of 1 May 2026)."""
        return {
            "NSW1-QLD1": cls(
                interconnector_id="NSW1-QLD1",
                direction_from_region="NSW1",
                direction_to_region="QLD1",
                category_id="NSW1-QLD1/NSW1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "QLD1-NSW1": cls(
                interconnector_id="QLD1-NSW1",
                direction_from_region="QLD1",
                direction_to_region="NSW1",
                category_id="QLD1-NSW1/QLD1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "NSW1-VIC1": cls(
                interconnector_id="NSW1-VIC1",
                direction_from_region="NSW1",
                direction_to_region="VIC1",
                category_id="NSW1-VIC1/NSW1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "VIC1-NSW1": cls(
                interconnector_id="VIC1-NSW1",
                direction_from_region="VIC1",
                direction_to_region="NSW1",
                category_id="VIC1-NSW1/VIC1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "VIC1-SA1": cls(
                interconnector_id="VIC1-SA1",
                direction_from_region="VIC1",
                direction_to_region="SA1",
                category_id="VIC1-SA1/VIC1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "SA1-VIC1": cls(
                interconnector_id="SA1-VIC1",
                direction_from_region="SA1",
                direction_to_region="VIC1",
                category_id="SA1-VIC1/SA1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "VIC1-TAS1": cls(
                interconnector_id="VIC1-TAS1",
                direction_from_region="VIC1",
                direction_to_region="TAS1",
                category_id="VIC1-TAS1/VIC1",
                max_units=1000,
                unit_proportion=0.001,
            ),
            "TAS1-VIC1": cls(
                interconnector_id="TAS1-VIC1",
                direction_from_region="TAS1",
                direction_to_region="VIC1",
                category_id="TAS1-VIC1/TAS1",
                max_units=1000,
                unit_proportion=0.001,
            ),
        }

    @classmethod
    def get(cls, interconnector_id: str) -> "Interconnector | None":
        return cls.registry().get(interconnector_id)
