from decimal import Decimal

from seed.seed_catalog import (
    SOFT_FLOUR_SACK_CM,
    SOFT_FLOUR_SACK_KG,
    SOFT_FLOUR_SACK_LB,
    SoftFlourState,
    plan_soft_flour_correction,
)

EMPTY = (None, None, None)


def _state(**overrides: object) -> SoftFlourState:
    values: dict[str, object] = {
        "purchase_unit": "KILOGRAM",
        "base_unit": "UNIT",
        "has_history": False,
        "weight": None,
        "dimensions": EMPTY,
    }
    values.update(overrides)
    return SoftFlourState(**values)  # type: ignore[arg-type]


def test_the_sack_weight_is_exact_and_needs_seven_decimals() -> None:
    assert Decimal("22.6796185") == SOFT_FLOUR_SACK_KG
    # A presentation factor keeps six decimals: kilograms per sack would be rounded.
    assert SOFT_FLOUR_SACK_KG.quantize(Decimal("0.000001")) != SOFT_FLOUR_SACK_KG


def test_a_legacy_kilogram_purchase_unit_becomes_the_sack() -> None:
    changes, notes = plan_soft_flour_correction(_state())
    assert notes == []
    assert changes["purchase_unit_id"] == "UNIT"
    assert (changes["weight"], changes["weight_unit"]) == (SOFT_FLOUR_SACK_LB, "lb")
    assert (
        changes["dimension_length"],
        changes["dimension_width"],
        changes["dimension_height"],
    ) == SOFT_FLOUR_SACK_CM
    assert changes["dimension_unit"] == "cm"


def test_an_already_correct_product_is_left_alone() -> None:
    state = _state(
        purchase_unit="UNIT",
        weight=Decimal("50"),
        dimensions=(Decimal("80"), Decimal("50"), Decimal("18")),
    )
    assert plan_soft_flour_correction(state) == ({}, [])


def test_measures_typed_by_a_user_are_never_overwritten() -> None:
    state = _state(weight=Decimal("22.68"), dimensions=(Decimal("70"), None, None))
    changes, _notes = plan_soft_flour_correction(state)
    assert set(changes) == {"purchase_unit_id"}


def test_history_in_kilograms_keeps_the_purchase_unit() -> None:
    changes, notes = plan_soft_flour_correction(_state(has_history=True))
    assert "purchase_unit_id" not in changes
    assert len(notes) == 1
    assert "documentos o movimientos" in notes[0]


def test_a_purchase_unit_chosen_by_a_user_is_kept() -> None:
    changes, _notes = plan_soft_flour_correction(_state(purchase_unit="BOX"))
    assert "purchase_unit_id" not in changes


def test_another_inventory_base_unit_is_never_changed() -> None:
    changes, notes = plan_soft_flour_correction(_state(base_unit="BOX"))
    assert changes == {}
    assert "BOX" in notes[0]


def test_without_an_inventory_item_the_sack_is_still_the_purchase_unit() -> None:
    changes, _notes = plan_soft_flour_correction(_state(base_unit=None))
    assert changes["purchase_unit_id"] == "UNIT"
