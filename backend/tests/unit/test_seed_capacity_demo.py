from seed.seed_capacity_demo import CAPACITY_DEMOS


def test_capacity_demo_scenarios_are_safe_and_distinct() -> None:
    assert len(CAPACITY_DEMOS) == 3
    assert len({scenario.code for scenario in CAPACITY_DEMOS}) == len(CAPACITY_DEMOS)
    assert len({scenario.stock.handling_unit_code for scenario in CAPACITY_DEMOS}) == len(
        CAPACITY_DEMOS
    )
    for scenario in CAPACITY_DEMOS:
        assert scenario.limits.operational_weight <= scenario.limits.certified_weight
        assert scenario.limits.operational_volume <= scenario.limits.certified_volume
        assert scenario.stock.location_code in {
            location.code for location in scenario.locations if location.storage_eligible
        }
        structure_codes = {structure.code for structure in scenario.structures}
        assert all(
            location.group_code is None or location.group_code in structure_codes
            for location in scenario.locations
        )


def test_capacity_demo_contains_available_warning_and_critical_examples() -> None:
    projected = {}
    for scenario in CAPACITY_DEMOS:
        target = next(
            location
            for location in scenario.locations
            if location.code == scenario.stock.location_code
        )
        assert target.limits is not None
        weight = scenario.stock.measures.gross_weight_kg
        assert weight is not None
        projected[scenario.code] = (
            (weight * scenario.stock.quantity_base / scenario.stock.base_quantity)
            / target.limits.operational_weight
            * 100
        )

    assert projected["BOD-ET-01"] < 80
    assert 80 <= projected["BOD-SM-01"] < 90
    assert 90 <= projected["BOD-JIQ-01"] < 100
