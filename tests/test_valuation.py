from transmission_rights.data.contracts import build_example_product
from transmission_rights.domain.models import FairValueRequest, PortfolioPosition, ValuationInputs
from transmission_rights.services.valuation import FairValueEngine


def test_fair_value_engine_uses_unit_proportion_and_discounts() -> None:
    engine = FairValueEngine()
    request = FairValueRequest(
        product=build_example_product(),
        position=PortfolioPosition(units_held=40, acquisition_price_per_unit=2500),
        inputs=ValuationInputs(
            expected_irsr=4_000_000,
            downside_irsr=2_800_000,
            upside_irsr=5_200_000,
            model_risk_discount=0.05,
            liquidity_discount=0.03,
        ),
    )

    response = engine.value(request)

    assert response.expected_distribution_per_unit == 4000.0
    assert response.fair_value_per_unit == 3680.0
    assert response.fair_value_total == 147200.0
    assert response.confidence_band_low == 2576.0
    assert response.confidence_band_high == 4784.0
