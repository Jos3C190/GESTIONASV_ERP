"""Pure policy checks for physical Kardex scope and balances."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.v1.routers.inventory_putaway_groups import _putaway_destination_status
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_kardex import (
    mask_unauthorized_warehouse_endpoints as _mask_unauthorized_warehouse_endpoints,
)
from app.domain.entities.inventory_kardex import (
    snapshot_quantity as _snapshot_quantity,
)
from app.domain.entities.inventory_kardex import (
    valuation_opening_known as _valuation_opening_known,
)
from app.domain.entities.inventory_kardex import (
    warehouse_scope_allowed as _warehouse_scope_allowed,
)
from app.domain.entities.inventory_release import (
    ReleaseRequirement,
    handling_unit_release_requirements,
)
from app.domain.entities.operational_context import AccessibleBranch, OperationalContext
from app.infrastructure.repositories.inventory_repository import (
    _require_labelled_split_in_quarantine,
)

pytestmark = pytest.mark.unit


def test_valuation_opening_balance_is_not_invented_on_the_cut_accounting_day() -> None:
    opened_at = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)

    assert not _valuation_opening_known(opened_at, date(2026, 10, 14))
    assert _valuation_opening_known(opened_at, date(2026, 10, 15))


def test_physical_cut_sums_item_balances_by_warehouse_and_optional_lot() -> None:
    warehouse_id, other_warehouse_id, item_id = uuid4(), uuid4(), uuid4()
    snapshot = [
        {
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "lot_code": "LOT-A",
            "quantity_base": "3.25",
        },
        {
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "lot_code": "LOT-B",
            "quantity_base": "2.75",
        },
        {
            "warehouse_id": str(other_warehouse_id),
            "inventory_item_id": str(item_id),
            "lot_code": "LOT-A",
            "quantity_base": "99",
        },
    ]

    assert _snapshot_quantity(
        snapshot, warehouse_id=warehouse_id, inventory_item_id=item_id, lot_code=None
    ) == Decimal("6.00")
    assert _snapshot_quantity(
        snapshot, warehouse_id=warehouse_id, inventory_item_id=item_id, lot_code="LOT-A"
    ) == Decimal("3.25")


def test_transfer_endpoint_details_are_masked_outside_accessible_warehouses() -> None:
    allowed_id, private_id = uuid4(), uuid4()
    row = {
        "from_warehouse_id": allowed_id,
        "from_warehouse_code": "BOD-LOCAL",
        "from_location_code": "A-01",
        "from_stock_status": "available",
        "to_warehouse_id": private_id,
        "to_warehouse_name": "Sucursal confidencial",
        "to_location_id": uuid4(),
        "to_location_code": "RACK-SECRET",
        "to_stock_status": "quarantine",
    }

    result = _mask_unauthorized_warehouse_endpoints(row, {allowed_id})

    assert result["from_warehouse_id"] == allowed_id
    assert result["from_location_code"] == "A-01"
    assert result["to_warehouse_id"] is None
    assert result["to_warehouse_name"] is None
    assert result["to_location_id"] is None
    assert result["to_location_code"] is None
    assert result["to_stock_status"] is None


def test_scope_rules_require_company_wide_access_for_central_warehouse() -> None:
    branch_id = uuid4()
    company_id = uuid4()
    branch_context = OperationalContext(
        company_id=company_id,
        access_all_branches=False,
        last_branch_id=branch_id,
        branches=(AccessibleBranch(branch_id, company_id, "Sucursal", "S-01", True),),
    )
    all_context = OperationalContext(
        company_id=company_id,
        access_all_branches=True,
        last_branch_id=None,
        branches=(),
    )

    assert _warehouse_scope_allowed(branch_context, branch_id)
    assert not _warehouse_scope_allowed(branch_context, uuid4())
    assert not _warehouse_scope_allowed(branch_context, None)
    assert _warehouse_scope_allowed(all_context, None)


def test_labelled_split_must_create_quarantined_putaway_units() -> None:
    _require_labelled_split_in_quarantine(
        label_confirmation_required=True,
        from_status="quarantine",
        movement_type="putaway",
        to_status="quarantine",
    )

    for source, kind, destination in (
        ("available", "putaway", "quarantine"),
        ("quarantine", "transfer", "quarantine"),
        ("quarantine", "putaway", "available"),
    ):
        with pytest.raises(InventoryOperationError) as error:
            _require_labelled_split_in_quarantine(
                label_confirmation_required=True,
                from_status=source,
                movement_type=kind,
                to_status=destination,
            )
        assert error.value.code == "labelled_handling_unit_split_requires_quarantine_putaway"

    # A counted partial receipt is the only additional safe split: it enters
    # quarantine and leaves the unreceived remainder in transit.
    _require_labelled_split_in_quarantine(
        label_confirmation_required=True,
        from_status="in_transit",
        movement_type="transfer",
        to_status="quarantine",
    )

    # Existing historical lots without mandatory label confirmation keep the
    # previous movement behavior.
    _require_labelled_split_in_quarantine(
        label_confirmation_required=False,
        from_status="available",
        movement_type="transfer",
        to_status="available",
    )


def test_grouped_putaway_keeps_unconfirmed_units_in_quarantine() -> None:
    common = {
        "is_partial": False,
        "measurement_status": "complete",
        "measurement_source": "measured",
        "expiry_date": None,
        "today": date(2026, 10, 14),
        "label_confirmation_required": True,
    }

    assert _putaway_destination_status(**common, label_confirmed=False) == "quarantine"
    assert _putaway_destination_status(**common, label_confirmed=True) == "available"
    assert (
        _putaway_destination_status(
            **{**common, "measurement_source": "split_estimate"}, label_confirmed=True
        )
        == "quarantine"
    )


def test_release_policy_reports_all_measurement_label_and_landed_cost_requirements() -> None:
    requirements = handling_unit_release_requirements(
        is_partial=False,
        measurement_status="complete",
        measurement_source="split_estimate",
        expiry_date=date(2026, 10, 13),
        today=date(2026, 10, 14),
        label_confirmation_required=True,
        label_confirmed=False,
        retaceo_readiness_error="cost_unapplied",
    )

    assert requirements == (
        ReleaseRequirement.MEASUREMENT,
        ReleaseRequirement.EXPIRY,
        ReleaseRequirement.LABEL,
        ReleaseRequirement.RETACEO_COST,
    )


def test_release_policy_allows_historical_lot_without_a_required_label_or_retaceo() -> None:
    assert (
        handling_unit_release_requirements(
            is_partial=False,
            measurement_status="verified",
            measurement_source="manual",
            expiry_date=None,
            today=date(2026, 10, 14),
            label_confirmation_required=False,
            label_confirmed=False,
        )
        == ()
    )
