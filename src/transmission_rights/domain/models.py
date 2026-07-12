from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class AllocationType(str, Enum):
    PRIMARY = "PRIMARY"
    CANCELLATION = "CANCELLATION"


class SRAProduct(BaseModel):
    interconnector_id: str = Field(description="Directional interconnector identifier")
    direction_from_region: str
    direction_to_region: str
    unit_category_id: str
    relevant_quarter: str = Field(description="AEMO relevant quarter, e.g. C2028Q1")
    tranche_no: int = Field(ge=1, le=12)
    allocation_type: AllocationType = AllocationType.PRIMARY
    max_units: int = Field(gt=0)
    unit_proportion: float = Field(gt=0, lt=1)


class PortfolioPosition(BaseModel):
    units_held: int = Field(ge=0)
    acquisition_price_per_unit: float = Field(ge=0)


class ValuationInputs(BaseModel):
    expected_irsr: float = Field(description="Expected distributable IRSR for the quarter")
    downside_irsr: float = Field(description="Low-case IRSR")
    upside_irsr: float = Field(description="High-case IRSR")
    confidence_level: float = Field(default=0.8, gt=0, lt=1)
    model_risk_discount: float = Field(default=0.05, ge=0, lt=1)
    liquidity_discount: float = Field(default=0.03, ge=0, lt=1)


class FairValueRequest(BaseModel):
    product: SRAProduct
    position: PortfolioPosition
    inputs: ValuationInputs
    methodology_version: Literal["initial-transparent-irsr-model"] = (
        "initial-transparent-irsr-model"
    )


class Sensitivities(BaseModel):
    value_per_unit_if_low_case: float
    value_per_unit_if_base_case: float
    value_per_unit_if_high_case: float


class FairValueResponse(BaseModel):
    fair_value_per_unit: float
    fair_value_total: float
    expected_distribution_per_unit: float
    expected_distribution_total: float
    confidence_band_low: float
    confidence_band_high: float
    sensitivities: Sensitivities
    notes: list[str]
