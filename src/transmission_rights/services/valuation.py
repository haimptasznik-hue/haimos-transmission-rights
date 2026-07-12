from __future__ import annotations

from transmission_rights.domain.models import FairValueRequest, FairValueResponse, Sensitivities


class FairValueEngine:
    def value(self, request: FairValueRequest) -> FairValueResponse:
        product = request.product
        position = request.position
        inputs = request.inputs

        gross_base_per_unit = product.unit_proportion * inputs.expected_irsr
        gross_low_per_unit = product.unit_proportion * inputs.downside_irsr
        gross_high_per_unit = product.unit_proportion * inputs.upside_irsr

        total_discount = inputs.model_risk_discount + inputs.liquidity_discount
        discounted_base_per_unit = gross_base_per_unit * (1 - total_discount)
        discounted_low_per_unit = gross_low_per_unit * (1 - total_discount)
        discounted_high_per_unit = gross_high_per_unit * (1 - total_discount)

        fair_value_total = discounted_base_per_unit * position.units_held
        expected_distribution_total = gross_base_per_unit * position.units_held

        return FairValueResponse(
            fair_value_per_unit=round(discounted_base_per_unit, 2),
            fair_value_total=round(fair_value_total, 2),
            expected_distribution_per_unit=round(gross_base_per_unit, 2),
            expected_distribution_total=round(expected_distribution_total, 2),
            confidence_band_low=round(discounted_low_per_unit, 2),
            confidence_band_high=round(discounted_high_per_unit, 2),
            sensitivities=Sensitivities(
                value_per_unit_if_low_case=round(discounted_low_per_unit, 2),
                value_per_unit_if_base_case=round(discounted_base_per_unit, 2),
                value_per_unit_if_high_case=round(discounted_high_per_unit, 2),
            ),
            notes=[
                "Initial scaffold uses proportional IRSR share only.",
                "Future versions should add exact AEMO settlement adjustments, fees, revisions, and scenario weighting.",
                "Auction marks and historical clears should calibrate liquidity and model-risk discounts.",
            ],
        )
