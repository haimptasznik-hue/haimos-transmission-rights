from transmission_rights.domain.models import AllocationType, SRAProduct


def build_example_product() -> SRAProduct:
    return SRAProduct(
        interconnector_id="NSW1-VIC1",
        direction_from_region="NSW1",
        direction_to_region="VIC1",
        unit_category_id="NSW1-VIC1/NSW1",
        relevant_quarter="C2028Q1",
        tranche_no=5,
        allocation_type=AllocationType.PRIMARY,
        max_units=1000,
        unit_proportion=0.001,
    )
