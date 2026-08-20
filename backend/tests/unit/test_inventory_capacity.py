"""Focused rules and contracts for physical inventory capacity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from app.api.v1.routers.inventory import InventoryBoundaryError, _execute, router
from app.api.v1.schemas.inventory import (
    CapacityDecisionOut,
    CapacitySummaryOut,
    MovementConfirmIn,
)
from app.application.inventory import InventoryApplicationError, InventoryUseCases
from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.domain.entities.inventory import (
    CapacityLimit,
    CapacityUsage,
    Consumption,
    InventoryOperationError,
    MeasurementStatus,
    PackagingType,
    PhysicalMeasures,
    ReservationStatus,
    StockStatus,
    calculate_consumption,
    calculate_measured_consumption,
    evaluate_capacity,
    require_quarantine_for_incomplete_measures,
)
from app.infrastructure.models.inventory import (
    CapacityOperationalOverrideModel,
    CapacityReservationModel,
    InventoryHandlingUnitModel,
    InventoryMovementModel,
)
from app.infrastructure.repositories.inventory_repository import (
    SqlAlchemyInventoryRepository,
    _advisory_lock_key,
    _capacity_metric_payload,
    _capacity_summary_status,
    _physical_from_handling_unit,
)
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.unit


def test_consumption_scales_requested_quantity_not_one_packaging() -> None:
    consumption = calculate_consumption(
        quantity_base=Decimal("25"),
        base_quantity=Decimal("5"),
        measures=PhysicalMeasures(
            gross_weight_kg=Decimal("2"),
            length_m=Decimal("0.5"),
            width_m=Decimal("0.4"),
            height_m=Decimal("0.3"),
        ),
    )

    assert consumption == Consumption(
        weight_kg=Decimal("10"),
        volume_m3=Decimal("0.300"),
    )


def test_real_handling_unit_measurement_is_total_and_is_not_scaled_again() -> None:
    measures = PhysicalMeasures(
        gross_weight_kg=Decimal("20"),
        length_m=Decimal("1"),
        width_m=Decimal("0.5"),
        height_m=Decimal("0.4"),
    )

    actual = calculate_measured_consumption(measures)
    master_scaled = calculate_consumption(
        quantity_base=Decimal("50"),
        base_quantity=Decimal("5"),
        measures=measures,
    )

    assert actual == Consumption(Decimal("20"), Decimal("0.2"))
    assert master_scaled == Consumption(Decimal("200"), Decimal("2"))


def test_fractional_packaging_consumption_rounds_up_to_ledger_precision() -> None:
    consumption = calculate_consumption(
        quantity_base=Decimal("1"),
        base_quantity=Decimal("3"),
        measures=PhysicalMeasures(
            gross_weight_kg=Decimal("1"),
            length_m=Decimal("1"),
            width_m=Decimal("1"),
            height_m=Decimal("1"),
        ),
    )

    assert consumption == Consumption(Decimal("0.333334"), Decimal("0.333334"))


class _ScalarQueueSession:
    def __init__(self, *values: object) -> None:
        self.values = list(values)

    async def scalar(self, _statement: object) -> object:
        return self.values.pop(0)


@pytest.mark.asyncio
async def test_repository_resolves_multiple_packaging_units_from_requested_quantity() -> None:
    company_id = uuid.uuid4()
    item_id = uuid.uuid4()
    packaging_id = uuid.uuid4()
    item = SimpleNamespace(
        id=item_id,
        company_id=company_id,
        product_id=1,
        variant_id=None,
        base_unit_id=1,
        is_active=True,
    )
    packaging = SimpleNamespace(
        id=packaging_id,
        company_id=company_id,
        inventory_item_id=item_id,
        code="BOX5",
        name="Caja de cinco",
        packaging_type=PackagingType.BOX.value,
        version=1,
        base_quantity=Decimal("5"),
        gross_weight_kg=Decimal("2"),
        length_m=Decimal("0.5"),
        width_m=Decimal("0.4"),
        height_m=Decimal("0.3"),
        volume_m3=Decimal("0.06"),
        stackable=True,
        max_stack=4,
        is_current=True,
        is_active=True,
    )
    session = _ScalarQueueSession(item, packaging)
    repository = SqlAlchemyInventoryRepository(cast(Any, session))

    resolved = await repository._resolve_physical(
        company_id=company_id,
        item_id=item_id,
        packaging_id=packaging_id,
        quantity_base=Decimal("25"),
        actual_measures=None,
    )

    assert resolved.consumption == Consumption(
        weight_kg=Decimal("10"),
        volume_m3=Decimal("0.30"),
    )


@pytest.mark.asyncio
async def test_repository_treats_receipt_measurement_as_whole_hu_total() -> None:
    company_id = uuid.uuid4()
    item_id = uuid.uuid4()
    packaging_id = uuid.uuid4()
    item = SimpleNamespace(
        id=item_id,
        company_id=company_id,
        product_id=1,
        variant_id=None,
        base_unit_id=1,
        is_active=True,
    )
    packaging = SimpleNamespace(
        id=packaging_id,
        company_id=company_id,
        inventory_item_id=item_id,
        code="BOX5",
        name="Caja de cinco",
        packaging_type=PackagingType.BOX.value,
        version=1,
        base_quantity=Decimal("5"),
        gross_weight_kg=Decimal("2"),
        length_m=Decimal("0.5"),
        width_m=Decimal("0.4"),
        height_m=Decimal("0.3"),
        volume_m3=Decimal("0.06"),
        stackable=True,
        max_stack=4,
        is_current=True,
        is_active=True,
    )
    repository = SqlAlchemyInventoryRepository(cast(Any, _ScalarQueueSession(item, packaging)))

    resolved = await repository._resolve_physical(
        company_id=company_id,
        item_id=item_id,
        packaging_id=packaging_id,
        quantity_base=Decimal("25"),
        actual_measures=PhysicalMeasures(
            gross_weight_kg=Decimal("11"),
            length_m=Decimal("1"),
            width_m=Decimal("0.8"),
            height_m=Decimal("0.5"),
        ),
    )

    assert resolved.consumption == Consumption(Decimal("11"), Decimal("0.4"))


def test_incomplete_hu_can_move_between_quarantines_but_not_to_available() -> None:
    row = SimpleNamespace(
        actual_gross_weight_kg=None,
        actual_length_m=None,
        actual_width_m=None,
        actual_height_m=None,
        actual_volume_m3=None,
        occupied_weight_kg=Decimal("0"),
        occupied_volume_m3=Decimal("0"),
        measurement_status=MeasurementStatus.INCOMPLETE.value,
        measurement_source="master",
        packaging_snapshot=None,
    )

    resolved = _physical_from_handling_unit(cast(Any, row))

    assert resolved.consumption is None
    require_quarantine_for_incomplete_measures(resolved.measures, StockStatus.QUARANTINE)
    with pytest.raises(ValueError, match="cuarentena"):
        require_quarantine_for_incomplete_measures(resolved.measures, StockStatus.AVAILABLE)


def test_incomplete_measurements_are_only_accepted_in_quarantine() -> None:
    incomplete = PhysicalMeasures(Decimal("2"), None, None, None, None)

    require_quarantine_for_incomplete_measures(incomplete, StockStatus.QUARANTINE)
    with pytest.raises(ValueError, match="cuarentena"):
        require_quarantine_for_incomplete_measures(incomplete, StockStatus.AVAILABLE)


def test_projected_capacity_includes_occupied_reserved_and_incoming() -> None:
    decision = evaluate_capacity(
        limit=CapacityLimit(
            certified_weight_kg=Decimal("120"),
            operational_weight_kg=Decimal("100"),
            certified_volume_m3=Decimal("60"),
            operational_volume_m3=Decimal("50"),
        ),
        usage=CapacityUsage(
            occupied_weight_kg=Decimal("80"),
            occupied_volume_m3=Decimal("30"),
            reserved_weight_kg=Decimal("10"),
            reserved_volume_m3=Decimal("5"),
        ),
        incoming=Consumption(Decimal("15"), Decimal("10")),
    )

    assert decision.projected_weight_kg == Decimal("105")
    assert decision.projected_volume_m3 == Decimal("45")
    assert not decision.allowed
    assert decision.code == "capacity_weight_exceeded"


def test_operational_override_never_overrides_certified_limit() -> None:
    limit = CapacityLimit(
        certified_weight_kg=Decimal("120"),
        operational_weight_kg=Decimal("100"),
        certified_volume_m3=Decimal("80"),
        operational_volume_m3=Decimal("70"),
    )
    usage = CapacityUsage(occupied_weight_kg=Decimal("95"))

    operational = evaluate_capacity(
        limit=limit,
        usage=usage,
        incoming=Consumption(Decimal("10"), Decimal("1")),
        has_operational_override=True,
    )
    certified = evaluate_capacity(
        limit=limit,
        usage=usage,
        incoming=Consumption(Decimal("30"), Decimal("1")),
        has_operational_override=True,
    )

    assert operational.allowed
    assert not certified.allowed
    assert certified.code == "certified_capacity_exceeded"


def test_observe_mode_reports_utilization_without_blocking_operational_limit() -> None:
    decision = evaluate_capacity(
        limit=CapacityLimit(
            certified_weight_kg=Decimal("200"),
            operational_weight_kg=Decimal("100"),
            certified_volume_m3=Decimal("200"),
            operational_volume_m3=Decimal("100"),
            enforcement_mode="observe",
        ),
        usage=CapacityUsage(occupied_weight_kg=Decimal("90")),
        incoming=Consumption(Decimal("20"), Decimal("1")),
    )

    assert decision.allowed
    assert decision.weight_utilization_pct == Decimal("110.0")


def test_unknown_occupancy_is_serialized_as_none_not_zero() -> None:
    payload = _capacity_metric_payload(
        certified=Decimal("120"),
        operational=Decimal("100"),
        occupied=Decimal("0"),
        reserved=Decimal("10"),
        projected=Decimal("10"),
        utilization_pct=Decimal("10"),
        occupied_known=False,
        reserved_known=True,
    )

    assert payload["occupied"] is None
    assert payload["reserved"] == Decimal("10")
    assert payload["projected"] is None
    assert payload["available"] is None
    assert payload["utilization_pct"] is None

    preview = CapacityDecisionOut.model_validate(
        {
            "allowed": True,
            "code": None,
            "projected_weight_kg": None,
            "projected_volume_m3": None,
            "weight_utilization_pct": None,
            "volume_utilization_pct": None,
            "limiting_metric": None,
            "measurement_status": "incomplete",
        }
    )
    assert preview.projected_weight_kg is None


def test_available_capacity_preserves_negative_overage() -> None:
    payload = _capacity_metric_payload(
        certified=Decimal("120"),
        operational=Decimal("100"),
        occupied=Decimal("105"),
        reserved=Decimal("0"),
        projected=Decimal("105"),
        utilization_pct=Decimal("105"),
        occupied_known=True,
        reserved_known=True,
    )

    assert payload["available"] == Decimal("-5")


class _MeasurementRepository:
    def __init__(self) -> None:
        self.called = False

    async def verify_handling_unit_measurements(self, **kwargs: Any) -> dict[str, Any]:
        self.called = True
        return kwargs


@pytest.mark.asyncio
async def test_quarantine_measurement_flow_requires_complete_verified_measures() -> None:
    repository = _MeasurementRepository()
    use_cases = InventoryUseCases(cast(Any, repository))

    with pytest.raises(InventoryApplicationError) as error:
        await use_cases.verify_handling_unit_measurements(
            company_id=uuid.uuid4(),
            handling_unit_id=uuid.uuid4(),
            measures=PhysicalMeasures(Decimal("1"), None, None, None, None),
            source="manual",
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "verified_measurements_required"
    assert not repository.called


class _VerifySession:
    def __init__(self, row: object) -> None:
        self.values = [row, row]
        self.flush_count = 0

    async def scalar(self, _statement: object) -> object:
        return self.values.pop(0)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_verifying_multi_pack_hu_uses_measured_total_without_multiplication() -> None:
    now = datetime.now(UTC)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        inventory_item_id=uuid.uuid4(),
        packaging_definition_id=uuid.uuid4(),
        code="HU-MULTI-001",
        lot_code=None,
        expiry_date=None,
        quantity_base=Decimal("50"),
        packaging_snapshot={"base_quantity": "5"},
        actual_gross_weight_kg=None,
        actual_length_m=None,
        actual_width_m=None,
        actual_height_m=None,
        actual_volume_m3=None,
        occupied_weight_kg=Decimal("0"),
        occupied_volume_m3=Decimal("0"),
        stock_status="quarantine",
        measurement_status="incomplete",
        measurement_source="master",
        closed_at=None,
        created_at=now,
        updated_at=now,
    )
    balance = SimpleNamespace(
        occupied_weight_kg=Decimal("0"),
        occupied_volume_m3=Decimal("0"),
    )
    session = _VerifySession(row)
    repository = SqlAlchemyInventoryRepository(cast(Any, session))
    repository._location_context = AsyncMock()  # type: ignore[method-assign]
    repository._balance = AsyncMock(return_value=balance)  # type: ignore[method-assign]

    result = await repository.verify_handling_unit_measurements(
        company_id=row.company_id,
        handling_unit_id=row.id,
        measures=PhysicalMeasures(
            gross_weight_kg=Decimal("20"),
            length_m=Decimal("1"),
            width_m=Decimal("0.5"),
            height_m=Decimal("0.4"),
        ),
        source="manual",
        actor_id=uuid.uuid4(),
    )

    assert result["occupied_weight_kg"] == Decimal("20")
    assert result["occupied_volume_m3"] == Decimal("0.2")
    assert balance.occupied_weight_kg == Decimal("20")
    assert balance.occupied_volume_m3 == Decimal("0.2")


def test_movement_confirmation_requires_existing_hu_for_physical_pick() -> None:
    with pytest.raises(ValidationError, match="unidad logística"):
        MovementConfirmIn.model_validate(
            {
                "idempotency_key": "physical-pick-001",
                "movement_type": "pick",
                "lines": [
                    {
                        "inventory_item_id": str(uuid.uuid4()),
                        "from_location_id": str(uuid.uuid4()),
                        "from_stock_status": "available",
                        "quantity_base": "1",
                    }
                ],
            }
        )


class _RollbackSession:
    def __init__(self) -> None:
        self.rollback_count = 0

    async def rollback(self) -> None:
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_inventory_boundary_rolls_back_failed_multi_line_command() -> None:
    session = _RollbackSession()

    async def failing_command() -> None:
        raise InventoryOperationError(
            "El segundo renglón no cabe.",
            code="capacity_volume_exceeded",
            status_code=409,
        )

    with pytest.raises(InventoryBoundaryError) as error:
        await _execute(cast(Any, session), failing_command())

    assert error.value.status_code == 409
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_inventory_boundary_translates_integrity_race_without_leaking_db() -> None:
    session = _RollbackSession()

    async def conflicting_command() -> None:
        raise IntegrityError("INSERT sensitive", {}, Exception("duplicate key detail"))

    with pytest.raises(InventoryBoundaryError) as error:
        await _execute(cast(Any, session), conflicting_command())

    assert error.value.code == "inventory_integrity_conflict"
    assert "duplicate key" not in str(error.value)
    assert session.rollback_count == 1


class _ReservationSession:
    def __init__(self, row: CapacityReservationModel) -> None:
        self.row = row
        self.flush_count = 0

    async def scalar(self, _statement: object) -> CapacityReservationModel:
        return self.row

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_expired_reservation_transition_returns_terminal_state_for_audit() -> None:
    row = CapacityReservationModel(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        inventory_item_id=uuid.uuid4(),
        packaging_definition_id=None,
        quantity_base=Decimal("1"),
        reserved_weight_kg=Decimal("1"),
        reserved_volume_m3=Decimal("1"),
        measurement_status="complete",
        stock_status="available",
        status="active",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        created_by=uuid.uuid4(),
        operational_override_id=None,
    )
    session = _ReservationSession(row)
    repository = SqlAlchemyInventoryRepository(cast(Any, session))

    result = await repository.change_reservation_status(
        company_id=row.company_id,
        reservation_id=row.id,
        action="confirm",
        actor_id=uuid.uuid4(),
    )

    assert result.status is ReservationStatus.EXPIRED
    assert row.status == "expired"
    assert session.flush_count == 1


class _OverrideSession:
    def __init__(self, row: CapacityOperationalOverrideModel) -> None:
        self.row = row
        self.flush_count = 0

    async def scalar(self, _statement: object) -> CapacityOperationalOverrideModel:
        return self.row

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_expired_override_transition_returns_terminal_state_for_audit() -> None:
    row = CapacityOperationalOverrideModel(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        reason="Sobrecupo temporal documentado",
        valid_until=datetime.now(UTC) - timedelta(seconds=1),
        status="active",
        granted_by=uuid.uuid4(),
    )
    session = _OverrideSession(row)
    repository = SqlAlchemyInventoryRepository(cast(Any, session))
    repository._location_context = AsyncMock()  # type: ignore[method-assign]

    result = await repository.revoke_operational_override(
        company_id=row.company_id,
        override_id=row.id,
        actor_id=uuid.uuid4(),
    )

    assert result["status"] == "expired"
    assert row.status == "expired"
    assert session.flush_count == 1


def test_capacity_summary_status_preserves_configuration_and_safety_semantics() -> None:
    assert (
        _capacity_summary_status(
            measurements_complete=True,
            configuration_status="incomplete",
            effective_utilization_pct=Decimal("25"),
            active_override=False,
        )
        == "incomplete"
    )
    assert (
        _capacity_summary_status(
            measurements_complete=True,
            configuration_status="available",
            effective_utilization_pct=Decimal("100"),
            active_override=True,
        )
        == "full"
    )
    assert (
        _capacity_summary_status(
            measurements_complete=True,
            configuration_status="available",
            effective_utilization_pct=Decimal("130"),
            active_override=True,
            certified_exceeded=True,
        )
        == "over_certified"
    )
    assert (
        _capacity_summary_status(
            measurements_complete=False,
            configuration_status="incomplete",
            effective_utilization_pct=Decimal("130"),
            active_override=True,
            certified_exceeded=True,
        )
        == "over_certified"
    )


def test_idempotency_advisory_lock_is_scoped_by_company_and_key() -> None:
    company_id = uuid.uuid4()

    first = _advisory_lock_key("inventory-movement", company_id, "retry-0001")

    assert first == _advisory_lock_key("inventory-movement", company_id, "retry-0001")
    assert first != _advisory_lock_key("inventory-movement", uuid.uuid4(), "retry-0001")


def test_capacity_summary_contract_accepts_unknown_physical_totals() -> None:
    summary = CapacitySummaryOut.model_validate(
        {
            "scope_type": "location",
            "warehouse_id": uuid.uuid4(),
            "location_id": uuid.uuid4(),
            "measurement_status": "incomplete",
            "status": "incomplete",
            "limiting_metric": None,
            "weight": {
                "certified": "100",
                "operational": "90",
                "occupied": None,
                "reserved": "10",
                "projected": None,
                "available": None,
                "utilization_pct": None,
            },
            "volume": {
                "certified": "50",
                "operational": "45",
                "occupied": None,
                "reserved": "2",
                "projected": None,
                "available": None,
                "utilization_pct": None,
            },
            "effective_utilization_pct": None,
            "unmeasured_handling_units": 1,
            "unmeasured_reservations": 0,
        }
    )

    assert summary.weight.occupied is None
    assert summary.effective_utilization_pct is None


def test_capacity_summary_contract_exposes_certified_safety_breach() -> None:
    summary = CapacitySummaryOut.model_validate(
        {
            "scope_type": "warehouse",
            "warehouse_id": uuid.uuid4(),
            "location_id": None,
            "measurement_status": "complete",
            "status": "over_certified",
            "limiting_metric": "weight",
            "weight": {
                "certified": "100",
                "operational": "90",
                "occupied": "110",
                "reserved": "0",
                "projected": "110",
                "available": "-20",
                "utilization_pct": "122.222222",
            },
            "volume": {
                "certified": "50",
                "operational": "45",
                "occupied": "20",
                "reserved": "0",
                "projected": "20",
                "available": "25",
                "utilization_pct": "44.444444",
            },
            "effective_utilization_pct": "122.222222",
            "unmeasured_handling_units": 0,
            "unmeasured_reservations": 0,
        }
    )

    assert summary.status == "over_certified"


def test_api_exposes_target_lookup_capacity_summary_and_measurement_release_flow() -> None:
    paths = {route.path for route in router.routes}

    assert "/inventory/items/by-target" in paths
    assert "/inventory/warehouses/{warehouse_id}/capacity-summary" in paths
    assert "/inventory/handling-units/{handling_unit_id}/measurements" in paths
    assert "/inventory/movements/confirm" in paths
    assert all("open-pick" not in path for path in paths)


def test_inventory_model_is_lightweight_and_reservation_is_tenant_bound() -> None:
    assert "parent_id" not in InventoryHandlingUnitModel.__table__.columns
    assert "pallet" not in {item.value for item in PackagingType}
    reservation_foreign_keys = {
        constraint.name for constraint in InventoryMovementModel.__table__.foreign_key_constraints
    }
    assert "fk_inventory_movements_reservation_company" in reservation_foreign_keys


def test_inventory_permissions_are_in_the_runtime_catalogue() -> None:
    assert {
        "inventory:read",
        "inventory:manage_packaging",
        "inventory:receive",
        "inventory:move",
        "inventory:capacity",
        "inventory:reserve",
        "capacity:override_operational",
    } <= ALL_PERMISSION_CODES
