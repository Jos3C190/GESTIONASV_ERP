"""PostgreSQL checks for transfers between branches, returns to headquarters and approval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.domain.entities.inventory_transfer import TransferDomainError, TransferPolicy
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryTransferSettingsModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from tests.integration.test_inventory_transfer_repository import (
    TransferFixture,
    _create_context,
)

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class BranchRouteFixture:
    base: TransferFixture
    branch_a: Warehouse
    location_a: Location
    unit_a: uuid.UUID
    branch_b: Warehouse
    location_b: Location
    sibling_a: Warehouse
    central: Warehouse
    central_location: Location
    creator_id: uuid.UUID
    approver_id: uuid.UUID
    driver_id: uuid.UUID
    use_cases: InventoryTransferUseCases
    suffix: str

    @property
    def company_id(self) -> uuid.UUID:
        return self.base.company_id

    @property
    def central_unit(self) -> uuid.UUID:
        return self.base.handling_unit_id


async def _write_policy(session: Any, company_id: uuid.UUID, **flags: bool) -> None:
    row = await session.get(InventoryTransferSettingsModel, company_id)
    if row is None:
        row = InventoryTransferSettingsModel(company_id=company_id)
        session.add(row)
    for name, value in flags.items():
        setattr(row, name, value)
    await session.flush()


async def _new_user(session: Any, label: str, suffix: str) -> uuid.UUID:
    user = User(
        username=f"{label}-{suffix[:12]}",
        email=f"{label}-{suffix[:12]}@example.test",
        password_hash="not-used-by-this-repository-test",
    )
    session.add(user)
    await session.flush()
    return user.id


async def _new_driver(
    session: Any, company_id: uuid.UUID, branch_id: uuid.UUID, tag: str
) -> uuid.UUID:
    """An active driver of ``branch_id`` (the transport a branch transfer must name)."""
    employee = Employee(
        company_id=company_id,
        employee_code=f"RT-{tag[:12].upper()}",
        first_name=f"conductor-{tag[:8]}",
        last_name="Prueba",
        status="activo",
    )
    session.add(employee)
    await session.flush()
    driver = DriverModel(
        company_id=company_id,
        employee_id=employee.id,
        branch_id=branch_id,
        license_class="liviana",
    )
    session.add(driver)
    await session.flush()
    return driver.id


async def _create_branch_route_context(
    session: Any, suffix: str, **policy_flags: bool
) -> BranchRouteFixture:
    """Stock in a branch warehouse, a second branch, and the rules written in this session."""
    base = await _create_context(session, suffix)
    company_id = base.company_id
    second_branch_id = await session.scalar(
        select(Branch.id)
        .where(
            Branch.company_id == company_id,
            Branch.is_headquarters.is_(False),
            Branch.is_active.is_(True),
            Branch.operational_status == "active",
            Branch.deleted_at.is_(None),
            Branch.id != base.destination.branch_id,
        )
        .order_by(Branch.created_at, Branch.id)
        .limit(1)
    )
    assert second_branch_id is not None
    category_id = base.destination.warehouse_category_id

    def warehouse(branch_id: uuid.UUID, tag: str) -> Warehouse:
        return Warehouse(
            company_id=company_id,
            branch_id=branch_id,
            warehouse_category_id=category_id,
            name=f"Ruta {tag} {suffix[:8]}",
            code=f"R{tag}-{suffix[:8]}",
            is_central=False,
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )

    branch_b = warehouse(second_branch_id, "B")
    sibling_a = warehouse(base.destination.branch_id, "S")
    session.add_all([branch_b, sibling_a])
    await session.flush()
    location_b = Location(
        warehouse_id=branch_b.id,
        code=f"RB-L-{suffix[:8]}",
        aisle="01",
        rack="01",
        level="01",
        position="01",
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    session.add(location_b)
    await session.flush()
    receipt = await SqlAlchemyInventoryRepository(session).post_movement(
        company_id=company_id,
        idempotency_key=f"route-seed-{suffix}",
        movement_type="receipt",
        source_reference=f"route-integration-receipt:{suffix}",
        lines=[
            {
                "inventory_item_id": base.item.id,
                "to_location_id": base.destination_location.id,
                "to_stock_status": "available",
                "quantity_base": Decimal("10"),
                "valuation_value": Decimal("25"),
                "valuation_currency": "USD",
                "handling_unit_code": f"RT-HU-{suffix}",
                "actual_measures": {
                    "gross_weight_kg": Decimal("10"),
                    "length_m": Decimal("0.5"),
                    "width_m": Decimal("0.5"),
                    "height_m": Decimal("0.4"),
                },
            }
        ],
        actor_id=base.actor_id,
    )
    await _write_policy(session, company_id, **policy_flags)
    return BranchRouteFixture(
        base=base,
        branch_a=base.destination,
        location_a=base.destination_location,
        unit_a=receipt["lines"][0]["handling_unit_id"],
        branch_b=branch_b,
        location_b=location_b,
        sibling_a=sibling_a,
        central=base.origin,
        central_location=base.source_location,
        creator_id=base.actor_id,
        approver_id=await _new_user(session, "route-approver", suffix),
        driver_id=await _new_driver(session, company_id, base.destination.branch_id, suffix),
        use_cases=InventoryTransferUseCases(SqlAlchemyInventoryTransferRepository(session)),
        suffix=suffix,
    )


def _lines(unit_id: uuid.UUID, quantity: str = "10") -> list[dict[str, Any]]:
    return [
        {
            "handling_unit_id": unit_id,
            "quantity_base": Decimal(quantity),
            "demand_allocations": [],
            "excess_reason": "Reubicación por quiebre de existencias",
        }
    ]


async def _create(
    ctx: BranchRouteFixture,
    destination: Warehouse,
    key: str,
    *,
    origin: Warehouse | None = None,
    unit_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return await ctx.use_cases.create_transfer(
        company_id=ctx.company_id,
        origin_warehouse_id=(origin or ctx.branch_a).id,
        destination_warehouse_id=destination.id,
        vehicle_id=ctx.base.vehicle_id,
        driver_id=ctx.driver_id,
        lines=_lines(unit_id or ctx.unit_a),
        idempotency_key=f"{key}-{ctx.suffix}",
        actor_id=actor_id or ctx.creator_id,
    )


async def _command(ctx: BranchRouteFixture, name: str, transfer_id: Any, key: str, **kw: Any):
    return await getattr(ctx.use_cases, f"{name}_transfer")(
        company_id=ctx.company_id,
        transfer_id=transfer_id,
        idempotency_key=f"{key}-{ctx.suffix}",
        **kw,
    )


async def _submit(ctx: BranchRouteFixture, transfer_id: Any, key: str = "submit"):
    return await _command(ctx, "submit", transfer_id, key, actor_id=ctx.creator_id)


async def _approve(
    ctx: BranchRouteFixture,
    transfer_id: Any,
    round_: int,
    key: str = "approve",
    *,
    actor_id: uuid.UUID | None = None,
    allow_self: bool = False,
):
    return await _command(
        ctx,
        "approve",
        transfer_id,
        key,
        actor_id=actor_id or ctx.approver_id,
        expected_round=round_,
        allow_self_approval=allow_self,
    )


async def _expect(awaitable: Any, code: str, status: int | None = None) -> TransferDomainError:
    with pytest.raises(TransferDomainError) as raised:
        await awaitable
    assert raised.value.code == code, raised.value.message
    if status is not None:
        assert raised.value.status_code == status
    return raised.value


async def _run(body: Any, **policy_flags: bool) -> None:
    suffix = uuid.uuid4().hex
    try:
        async with async_session_factory() as session:
            transaction = await session.begin()
            try:
                ctx = await _create_branch_route_context(session, suffix, **policy_flags)
                await body(session, ctx)
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await dispose_engine()


async def _flush_in_savepoint(session: Any, row: Any, **changes: Any) -> None:
    async with session.begin_nested():
        for name, value in changes.items():
            setattr(row, name, value)
        await session.flush()


ALL_ROUTES = {"allow_branch_to_branch": True, "allow_branch_to_central": True}


@pytest.mark.asyncio
async def test_default_policy_only_allows_distribution_from_the_central_warehouse() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        assert await ctx.use_cases.get_policy(ctx.company_id) == TransferPolicy(
            allow_branch_to_branch=False, allow_branch_to_central=False, require_approval=True
        )
        for destination in (ctx.branch_b, ctx.central):
            error = await _expect(
                _create(ctx, destination, "default-policy"), "transfer_origin_not_central", 422
            )
            assert error.message == "El traslado a sucursal debe salir de la bodega central."
        central = await ctx.use_cases.create_transfer(
            company_id=ctx.company_id,
            origin_warehouse_id=ctx.central.id,
            destination_warehouse_id=ctx.branch_a.id,
            vehicle_id=ctx.base.vehicle_id,
            lines=_lines(ctx.central_unit),
            idempotency_key=f"central-default-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert central["route_type"] == "central_distribution"
        assert central["requires_approval"] is False
        assert central["approval_round"] == 0
        assert central["origin_is_central"] is True
        assert central["destination_is_central"] is False
        assert central["origin_branch_name"] is not None
        assert central["destination_branch_name"] is not None
        await _expect(
            _command(ctx, "submit", central["id"], "central-submit", actor_id=ctx.creator_id),
            "transfer_approval_not_applicable",
            422,
        )

    await _run(body, allow_branch_to_branch=False, allow_branch_to_central=False)


@pytest.mark.asyncio
async def test_each_route_follows_its_own_switch_and_same_branch_is_refused() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        await _write_policy(session, ctx.company_id, allow_branch_to_branch=True)
        disabled = await _expect(
            _create(ctx, ctx.central, "to-central-off"), "transfer_route_disabled", 409
        )
        assert (
            disabled.message
            == "Los retornos a la bodega central no están habilitados en esta empresa."
        )
        between = await _create(ctx, ctx.branch_b, "to-branch-on")
        assert between["route_type"] == "branch_to_branch"
        assert between["requires_approval"] is True
        assert between["origin_branch_id"] != between["destination_branch_id"]
        await _expect(_create(ctx, ctx.sibling_a, "same-branch"), "transfer_same_branch", 422)

        await _write_policy(
            session, ctx.company_id, allow_branch_to_branch=False, allow_branch_to_central=True
        )
        disabled = await _expect(
            _create(ctx, ctx.branch_b, "to-branch-off"), "transfer_route_disabled", 409
        )
        assert (
            disabled.message
            == "Los traslados entre sucursales no están habilitados en esta empresa."
        )
        returning = await _create(ctx, ctx.central, "to-central-on")
        assert returning["route_type"] == "branch_to_central"
        assert returning["destination_is_central"] is True

    await _run(body)


@pytest.mark.asyncio
async def test_branch_transfer_rejects_purchase_demand_and_asks_for_a_reason() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        with_demand = _lines(ctx.unit_a)
        with_demand[0]["demand_allocations"] = [
            {"purchase_request_detail_id": uuid.uuid4(), "allocated_quantity": Decimal("5")}
        ]
        error = await _expect(
            ctx.use_cases.create_transfer(
                company_id=ctx.company_id,
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.branch_b.id,
                lines=with_demand,
                idempotency_key=f"branch-demand-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_demand_not_allowed_for_route",
            422,
        )
        assert error.message == (
            "Los traslados entre sucursales o de retorno no se vinculan a solicitudes de compra."
        )
        no_reason = _lines(ctx.unit_a)
        no_reason[0]["excess_reason"] = None
        reason_error = await _expect(
            ctx.use_cases.create_transfer(
                company_id=ctx.company_id,
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.branch_b.id,
                lines=no_reason,
                idempotency_key=f"branch-reason-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_excess_reason_required",
            422,
        )
        assert reason_error.message == "Indica el motivo del traslado en cada línea."
        await _expect(
            ctx.use_cases.create_transfer(
                company_id=ctx.company_id,
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.branch_b.id,
                lines=_lines(ctx.central_unit),
                idempotency_key=f"branch-wrong-unit-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_handling_unit_unavailable",
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_branch_to_branch_goes_through_approval_dispatch_and_receipt() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "happy")
        assert draft["status"] == "preparation"
        assert draft["requires_approval"] is True
        await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                vehicle_id=ctx.base.vehicle_id,
                idempotency_key=f"happy-early-dispatch-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_approval_required",
            409,
        )
        pending = await _submit(ctx, draft["id"])
        assert pending["status"] == "pending_approval"
        assert pending["approval_round"] == 1
        assert pending["submitted_by_id"] == ctx.creator_id
        assert pending["submitted_by_name"] == f"transfer-{ctx.suffix[:16]}"
        assert pending["submitted_at"] is not None
        await _expect(
            ctx.use_cases.update_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.branch_b.id,
                vehicle_id=None,
                notes="Cambio durante la espera",
                lines=_lines(ctx.unit_a),
                idempotency_key=f"happy-edit-pending-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_not_in_preparation",
            409,
        )
        await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                vehicle_id=ctx.base.vehicle_id,
                idempotency_key=f"happy-pending-dispatch-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_approval_required",
            409,
        )
        approved = await _approve(ctx, draft["id"], 1)
        assert approved["status"] == "approved"
        assert approved["approved_by_id"] == ctx.approver_id
        assert approved["approved_by_name"] == f"route-approver-{ctx.suffix[:12]}"
        assert approved["approved_at"] is not None

        before = await session.scalar(
            select(func.count(InventoryMovementModel.id)).where(
                InventoryMovementModel.company_id == ctx.company_id
            )
        )
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"happy-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert dispatched["status"] == "in_transit"
        assert dispatched["approved_by_id"] == ctx.approver_id
        vehicle = await session.get(InventoryVehicleModel, ctx.base.vehicle_id)
        assert vehicle is not None
        in_transit = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == ctx.company_id,
                InventoryBalanceModel.inventory_item_id == ctx.base.item.id,
                InventoryBalanceModel.location_id == vehicle.transit_location_id,
                InventoryBalanceModel.stock_status == "in_transit",
            )
        )
        assert in_transit == Decimal("10")
        origin_stock = await session.scalar(
            select(func.coalesce(func.sum(InventoryBalanceModel.quantity_base), 0)).where(
                InventoryBalanceModel.company_id == ctx.company_id,
                InventoryBalanceModel.location_id == ctx.location_a.id,
            )
        )
        assert origin_stock == Decimal("0")

        received = await ctx.use_cases.receive_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            lines=[
                {
                    "transfer_detail_id": dispatched["lines"][0]["id"],
                    "destination_location_id": ctx.location_b.id,
                    "quantity_base": Decimal("10"),
                }
            ],
            idempotency_key=f"happy-receive-{ctx.suffix}",
            actor_id=ctx.approver_id,
        )
        assert received["status"] == "received"
        arrived = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == ctx.company_id,
                InventoryBalanceModel.location_id == ctx.location_b.id,
                InventoryBalanceModel.stock_status == "quarantine",
            )
        )
        assert arrived == Decimal("10")
        movements = await session.scalar(
            select(func.count(InventoryMovementModel.id)).where(
                InventoryMovementModel.company_id == ctx.company_id,
                InventoryMovementModel.source_reference.like(
                    f"inventory_transfer:{draft['code']}:%"
                ),
            )
        )
        assert movements == 2
        assert before is not None

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_branch_to_central_return_reaches_the_central_warehouse() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.central, "return")
        assert draft["route_type"] == "branch_to_central"
        pending = await _submit(ctx, draft["id"])
        await _approve(ctx, draft["id"], pending["approval_round"])
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"return-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        received = await ctx.use_cases.receive_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            lines=[
                {
                    "transfer_detail_id": dispatched["lines"][0]["id"],
                    "destination_location_id": ctx.central_location.id,
                    "quantity_base": Decimal("10"),
                }
            ],
            idempotency_key=f"return-receive-{ctx.suffix}",
            actor_id=ctx.approver_id,
        )
        assert received["status"] == "received"
        returned = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == ctx.company_id,
                InventoryBalanceModel.location_id == ctx.central_location.id,
                InventoryBalanceModel.inventory_item_id == ctx.base.item.id,
                InventoryBalanceModel.stock_status == "quarantine",
            )
        )
        assert returned == Decimal("10")

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_rejection_returns_to_preparation_and_a_stale_round_cannot_decide() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "reject")
        first = await _submit(ctx, draft["id"], "reject-submit-1")
        assert first["approval_round"] == 1
        await _expect(
            _approve(ctx, draft["id"], 2, "reject-future"), "transfer_approval_stale", 409
        )
        await _expect(
            _command(
                ctx,
                "reject",
                draft["id"],
                "reject-short",
                actor_id=ctx.approver_id,
                expected_round=1,
                reason="no",
            ),
            "transfer_rejection_reason_required",
            422,
        )
        rejected = await _command(
            ctx,
            "reject",
            draft["id"],
            "reject-ok",
            actor_id=ctx.approver_id,
            expected_round=1,
            reason="  Falta documentar el motivo del traslado  ",
        )
        assert rejected["status"] == "preparation"
        assert rejected["rejected_by_id"] == ctx.approver_id
        assert rejected["rejected_by_name"] == f"route-approver-{ctx.suffix[:12]}"
        assert rejected["rejection_reason"] == "Falta documentar el motivo del traslado"
        assert rejected["rejected_at"] is not None
        assert rejected["submitted_by_id"] is None
        assert rejected["submitted_at"] is None
        assert rejected["approval_round"] == 1
        await _expect(
            _command(
                ctx,
                "reject",
                draft["id"],
                "reject-twice",
                actor_id=ctx.approver_id,
                expected_round=1,
                reason="Otra vez rechazado",
            ),
            "transfer_not_pending_approval",
            409,
        )

        second = await _submit(ctx, draft["id"], "reject-submit-2")
        assert second["approval_round"] == 2
        assert second["rejected_by_id"] is None
        assert second["rejection_reason"] is None
        assert second["rejected_at"] is None
        await _expect(
            _approve(ctx, draft["id"], 1, "reject-old-round"), "transfer_approval_stale", 409
        )
        approved = await _approve(ctx, draft["id"], 2, "reject-new-round")
        assert approved["status"] == "approved"
        assert approved["approval_round"] == 2

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_nobody_approves_their_own_transfer_unless_allowed() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        sender_id = await _new_user(session, "route-sender", ctx.suffix)
        draft = await _create(ctx, ctx.branch_b, "self")
        pending = await _command(ctx, "submit", draft["id"], "self-submit", actor_id=sender_id)
        round_ = pending["approval_round"]
        for actor in (ctx.creator_id, sender_id):
            error = await _expect(
                _approve(ctx, draft["id"], round_, f"self-approve-{actor}", actor_id=actor),
                "transfer_approval_self_forbidden",
                403,
            )
            assert (
                error.message
                == "No puedes aprobar un traslado que tú preparaste, editaste o enviaste."
            )
            await _expect(
                _command(
                    ctx,
                    "reject",
                    draft["id"],
                    f"self-reject-{actor}",
                    actor_id=actor,
                    expected_round=round_,
                    reason="Intento de rechazo propio",
                ),
                "transfer_approval_self_forbidden",
                403,
            )
        approved = await _approve(
            ctx, draft["id"], round_, "self-superuser", actor_id=ctx.creator_id, allow_self=True
        )
        assert approved["status"] == "approved"
        assert approved["approved_by_id"] == ctx.creator_id

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_without_required_approval_a_branch_transfer_dispatches_directly() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "direct")
        assert draft["requires_approval"] is False
        error = await _expect(
            _submit(ctx, draft["id"], "direct-submit"), "transfer_approval_not_applicable", 422
        )
        assert error.message == (
            "Esta empresa no exige aprobación para esta ruta; puedes despachar directamente."
        )
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"direct-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert dispatched["status"] == "in_transit"
        assert dispatched["approved_by_id"] is None

    await _run(body, require_approval=False, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_a_draft_follows_the_rules_in_force_when_they_change() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "live")
        assert draft["requires_approval"] is True
        await _write_policy(session, ctx.company_id, require_approval=False)
        relaxed = await ctx.use_cases.get_transfer(ctx.company_id, draft["id"])
        assert relaxed is not None
        assert relaxed["requires_approval"] is False
        listed = await ctx.use_cases.list_transfers(
            company_id=ctx.company_id, branch_id=ctx.branch_a.branch_id
        )
        assert [row["requires_approval"] for row in listed if row["id"] == draft["id"]] == [False]
        await _write_policy(session, ctx.company_id, require_approval=True)
        await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                vehicle_id=ctx.base.vehicle_id,
                idempotency_key=f"live-dispatch-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_approval_required",
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_turning_a_route_off_blocks_everything_except_undoing_the_request() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        first = await _create(ctx, ctx.branch_b, "off-first")
        pending = await _submit(ctx, first["id"], "off-submit")
        approved = await _approve(ctx, first["id"], pending["approval_round"], "off-approve")
        assert approved["status"] == "approved"
        await _write_policy(session, ctx.company_id, allow_branch_to_branch=False)
        await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=first["id"],
                vehicle_id=ctx.base.vehicle_id,
                idempotency_key=f"off-dispatch-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_route_disabled",
            409,
        )
        await _expect(_create(ctx, ctx.branch_b, "off-create"), "transfer_route_disabled", 409)
        cancelled = await _command(
            ctx, "cancel", first["id"], "off-cancel", actor_id=ctx.creator_id
        )
        assert cancelled["status"] == "cancelled"

        await _write_policy(session, ctx.company_id, allow_branch_to_branch=True)
        second = await _create(ctx, ctx.branch_b, "off-second")
        waiting = await _submit(ctx, second["id"], "off-second-submit")
        await _write_policy(session, ctx.company_id, allow_branch_to_branch=False)
        await _expect(
            _approve(ctx, second["id"], waiting["approval_round"], "off-second-approve"),
            "transfer_route_disabled",
            409,
        )
        await _expect(
            _command(ctx, "submit", second["id"], "off-resubmit", actor_id=ctx.creator_id),
            "transfer_route_disabled",
        )
        withdrawn = await _command(
            ctx, "withdraw", second["id"], "off-withdraw", actor_id=ctx.creator_id
        )
        assert withdrawn["status"] == "preparation"
        await _expect(
            _command(ctx, "submit", second["id"], "off-resubmit-2", actor_id=ctx.creator_id),
            "transfer_route_disabled",
            409,
        )
        await _write_policy(session, ctx.company_id, allow_branch_to_branch=True)
        third_round = await _submit(ctx, second["id"], "off-resubmit-3")
        assert third_round["approval_round"] == 2
        await _write_policy(session, ctx.company_id, allow_branch_to_branch=False)
        rejected = await _command(
            ctx,
            "reject",
            second["id"],
            "off-reject",
            actor_id=ctx.approver_id,
            expected_round=2,
            reason="Ruta suspendida por la empresa",
        )
        assert rejected["status"] == "preparation"

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_pending_and_approved_transfers_can_be_cancelled_but_not_after_leaving() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        first = await _create(ctx, ctx.branch_b, "cancel-first")
        await _submit(ctx, first["id"], "cancel-first-submit")
        cancelled_pending = await _command(
            ctx, "cancel", first["id"], "cancel-pending", actor_id=ctx.creator_id
        )
        assert cancelled_pending["status"] == "cancelled"

        second = await _create(ctx, ctx.branch_b, "cancel-second")
        waiting = await _submit(ctx, second["id"], "cancel-second-submit")
        await _approve(ctx, second["id"], waiting["approval_round"], "cancel-second-approve")
        cancelled_approved = await _command(
            ctx, "cancel", second["id"], "cancel-approved", actor_id=ctx.creator_id
        )
        assert cancelled_approved["status"] == "cancelled"

        third = await _create(ctx, ctx.branch_b, "cancel-third")
        waiting = await _submit(ctx, third["id"], "cancel-third-submit")
        await _approve(ctx, third["id"], waiting["approval_round"], "cancel-third-approve")
        await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=third["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"cancel-third-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        error = await _expect(
            _command(ctx, "cancel", third["id"], "cancel-third", actor_id=ctx.creator_id),
            "transfer_not_cancellable",
            409,
        )
        assert error.message == "Solo se cancelan traslados que aún no se despachan."

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_a_unit_promised_to_a_waiting_transfer_cannot_be_promised_again() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        first = await _create(ctx, ctx.branch_b, "commit-first")
        # Drafts promise nothing: a second draft with the same unit is allowed.
        second = await _create(ctx, ctx.branch_b, "commit-second")
        waiting = await _submit(ctx, first["id"], "commit-first-submit")
        error = await _expect(
            _submit(ctx, second["id"], "commit-second-submit"),
            "transfer_handling_unit_committed",
            409,
        )
        unit_code = await session.scalar(
            select(InventoryHandlingUnitModel.code).where(
                InventoryHandlingUnitModel.id == ctx.unit_a
            )
        )
        assert error.message == (
            f"La unidad {unit_code} ya está comprometida en el traslado {first['code']} "
            "pendiente de despacho."
        )
        # An approved transfer keeps holding its unit.
        await _approve(ctx, first["id"], waiting["approval_round"], "commit-first-approve")
        await _expect(
            _submit(ctx, second["id"], "commit-second-submit-2"),
            "transfer_handling_unit_committed",
        )
        await _command(ctx, "cancel", first["id"], "commit-first-cancel", actor_id=ctx.creator_id)
        released = await _submit(ctx, second["id"], "commit-second-submit-3")
        assert released["status"] == "pending_approval"

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_approval_notices_when_the_stock_is_gone() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "gone")
        waiting = await _submit(ctx, draft["id"], "gone-submit")
        unit = await session.get(InventoryHandlingUnitModel, ctx.unit_a)
        assert unit is not None
        unit.stock_status = "damaged"
        await session.flush()
        await _expect(
            _approve(ctx, draft["id"], waiting["approval_round"], "gone-approve"),
            "transfer_handling_unit_unavailable",
            409,
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_new_commands_are_idempotent_and_reject_a_changed_replay() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "idem")

        submitted = await _submit(ctx, draft["id"], "idem-submit")
        replay = await _submit(ctx, draft["id"], "idem-submit")
        assert replay["status"] == "pending_approval"
        assert replay["approval_round"] == submitted["approval_round"] == 1
        await _expect(
            _command(ctx, "submit", uuid.uuid4(), "idem-submit", actor_id=ctx.creator_id),
            "transfer_idempotency_conflict",
        )

        withdrawn = await _command(
            ctx, "withdraw", draft["id"], "idem-withdraw", actor_id=ctx.creator_id
        )
        replay_withdraw = await _command(
            ctx, "withdraw", draft["id"], "idem-withdraw", actor_id=ctx.creator_id
        )
        assert withdrawn["status"] == replay_withdraw["status"] == "preparation"
        await _expect(
            _command(ctx, "withdraw", uuid.uuid4(), "idem-withdraw", actor_id=ctx.creator_id),
            "transfer_idempotency_conflict",
        )

        resubmitted = await _submit(ctx, draft["id"], "idem-submit-2")
        round_ = resubmitted["approval_round"]
        assert round_ == 2
        approved = await _approve(ctx, draft["id"], round_, "idem-approve")
        replay_approve = await _approve(ctx, draft["id"], round_, "idem-approve")
        assert approved["status"] == replay_approve["status"] == "approved"
        await _expect(
            _approve(ctx, draft["id"], round_ + 1, "idem-approve"), "transfer_idempotency_conflict"
        )

        second = await _create(ctx, ctx.branch_b, "idem-reject", unit_id=ctx.unit_a)
        await _command(ctx, "cancel", draft["id"], "idem-cancel", actor_id=ctx.creator_id)
        waiting = await _submit(ctx, second["id"], "idem-reject-submit")
        arguments = {
            "actor_id": ctx.approver_id,
            "expected_round": waiting["approval_round"],
        }
        rejected = await _command(
            ctx, "reject", second["id"], "idem-reject-key", reason="Motivo de prueba", **arguments
        )
        replay_reject = await _command(
            ctx, "reject", second["id"], "idem-reject-key", reason="Motivo de prueba", **arguments
        )
        assert rejected["status"] == replay_reject["status"] == "preparation"
        await _expect(
            _command(
                ctx, "reject", second["id"], "idem-reject-key", reason="Otro motivo", **arguments
            ),
            "transfer_idempotency_conflict",
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_listing_matches_either_side_and_filters_by_route_side_and_approver() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "list")
        waiting = await _submit(ctx, draft["id"], "list-submit")
        branch_a, branch_b = ctx.branch_a.branch_id, ctx.branch_b.branch_id

        async def ids(**filters: Any) -> set[uuid.UUID]:
            rows = await ctx.use_cases.list_transfers(company_id=ctx.company_id, **filters)
            return {row["id"] for row in rows}

        assert draft["id"] in await ids(branch_id=branch_a)
        assert draft["id"] in await ids(branch_id=branch_b)
        assert draft["id"] in await ids(branch_id=branch_a, side="origin")
        assert draft["id"] not in await ids(branch_id=branch_a, side="destination")
        assert draft["id"] in await ids(branch_id=branch_b, side="destination")
        assert draft["id"] not in await ids(branch_id=branch_b, side="origin")
        assert draft["id"] in await ids(branch_ids=[branch_b])
        assert draft["id"] not in await ids(branch_ids=[])
        assert draft["id"] in await ids(route_type="branch_to_branch")
        assert draft["id"] not in await ids(route_type="branch_to_central")
        assert draft["id"] not in await ids(route_type="central_distribution")
        assert draft["id"] in await ids(status_filter="pending_approval")
        assert draft["id"] not in await ids(status_filter="approved")

        decide = {"company_id": ctx.company_id, "actor_id": ctx.approver_id}
        awaiting = {"awaiting_approval_by": ctx.approver_id}
        assert draft["id"] in await ids(**awaiting)
        assert draft["id"] in await ids(**awaiting, approver_branch_ids=[branch_a])
        assert draft["id"] not in await ids(**awaiting, approver_branch_ids=[branch_b])
        assert await ids(**awaiting, approver_branch_ids=[]) == set()
        assert await ctx.use_cases.pending_approval_count(**decide) >= 1
        assert (
            await ctx.use_cases.pending_approval_count(**decide, approver_branch_ids=[branch_a])
            >= 1
        )
        assert (
            await ctx.use_cases.pending_approval_count(**decide, approver_branch_ids=[branch_b])
            == 0
        )
        assert await ctx.use_cases.pending_approval_count(**decide, approver_branch_ids=[]) == 0

        # The people who prepared or sent it do not see it as theirs to decide.
        creator_view = {"awaiting_approval_by": ctx.creator_id}
        assert draft["id"] not in await ids(**creator_view)
        assert draft["id"] in await ids(**creator_view, allow_self_approval=True)
        mine = {"company_id": ctx.company_id, "actor_id": ctx.creator_id}
        count_without = await ctx.use_cases.pending_approval_count(**mine)
        count_with = await ctx.use_cases.pending_approval_count(**mine, allow_self_approval=True)
        assert count_with == count_without + 1

        await _approve(ctx, draft["id"], waiting["approval_round"], "list-approve")
        assert draft["id"] not in await ids(**awaiting)
        assert draft["id"] in await ids(status_filter="approved")

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_route_options_respect_scope_permission_and_the_rules_in_force() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        company = ctx.company_id
        everything = await ctx.use_cases.route_options(company_id=company, can_move=True)
        origin_ids = {origin["id"] for origin in everything["origins"]}
        assert {ctx.central.id, ctx.branch_a.id, ctx.branch_b.id} <= origin_ids
        assert everything["policy"] == {
            "allow_branch_to_branch": True,
            "allow_branch_to_central": True,
            "require_approval": True,
        }
        assert set(everything["origins"][0]) == {
            "id",
            "code",
            "name",
            "branch_id",
            "branch_name",
            "is_central",
        }
        assert everything["destinations"] == []
        nobody = await ctx.use_cases.route_options(company_id=company, can_move=False)
        assert nobody["origins"] == []
        assert nobody["policy"]["allow_branch_to_branch"] is True

        scoped = await ctx.use_cases.route_options(
            company_id=company, can_move=True, branch_ids=[ctx.branch_a.branch_id]
        )
        scoped_ids = {origin["id"] for origin in scoped["origins"]}
        assert {ctx.branch_a.id, ctx.sibling_a.id} <= scoped_ids
        assert not {ctx.branch_b.id, ctx.central.id} & scoped_ids
        assigned = await ctx.use_cases.route_options(
            company_id=company,
            can_move=True,
            branch_ids=[ctx.branch_a.branch_id],
            warehouse_ids=[ctx.branch_a.id],
        )
        assert {origin["id"] for origin in assigned["origins"]} == {ctx.branch_a.id}

        with_destinations = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.branch_a.id
        )
        routes = {row["id"]: row["route_type"] for row in with_destinations["destinations"]}
        assert routes[ctx.branch_b.id] == "branch_to_branch"
        assert routes[ctx.central.id] == "branch_to_central"
        assert ctx.sibling_a.id not in routes
        assert ctx.branch_a.id not in routes
        from_central = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.central.id
        )
        central_routes = {row["id"]: row["route_type"] for row in from_central["destinations"]}
        assert central_routes[ctx.branch_a.id] == "central_distribution"
        assert ctx.central.id not in central_routes

        forbidden = await _expect(
            ctx.use_cases.route_options(
                company_id=company,
                can_move=True,
                branch_ids=[ctx.branch_a.branch_id],
                origin_warehouse_id=ctx.branch_b.id,
            ),
            "transfer_origin_forbidden",
            403,
        )
        assert forbidden.message == "No tienes acceso a esta bodega de origen."
        await _expect(
            ctx.use_cases.route_options(
                company_id=company, can_move=False, origin_warehouse_id=ctx.branch_a.id
            ),
            "transfer_origin_forbidden",
            403,
        )

        await _write_policy(
            session, company, allow_branch_to_branch=False, allow_branch_to_central=False
        )
        closed = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.central.id
        )
        closed_ids = {origin["id"] for origin in closed["origins"]}
        assert ctx.central.id in closed_ids
        assert not {ctx.branch_a.id, ctx.branch_b.id} & closed_ids
        assert ctx.branch_a.id in {row["id"] for row in closed["destinations"]}

        await _write_policy(session, company, allow_branch_to_central=True)
        only_return = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.branch_a.id
        )
        only_return_routes = {row["id"]: row["route_type"] for row in only_return["destinations"]}
        assert only_return_routes == {ctx.central.id: "branch_to_central"}

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_update_reclassifies_the_route_and_keeps_validating_it() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "update")
        updated = await ctx.use_cases.update_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            origin_warehouse_id=ctx.branch_a.id,
            destination_warehouse_id=ctx.central.id,
            vehicle_id=ctx.base.vehicle_id,
            notes="Ahora es un retorno",
            lines=_lines(ctx.unit_a),
            idempotency_key=f"update-return-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert updated["route_type"] == "branch_to_central"
        await _expect(
            ctx.use_cases.update_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.sibling_a.id,
                vehicle_id=None,
                notes=None,
                lines=_lines(ctx.unit_a),
                idempotency_key=f"update-same-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_same_branch",
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_database_refuses_an_inconsistent_approval_state() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "constraint")
        row = await session.get(InventoryTransferModel, draft["id"])
        assert row is not None
        created_at = row.created_at
        with pytest.raises(IntegrityError, match="ck_inventory_transfers_approval_state"):
            await _flush_in_savepoint(session, row, status="pending_approval")
        with pytest.raises(IntegrityError, match="ck_inventory_transfers_rejection_reason"):
            await _flush_in_savepoint(
                session,
                row,
                rejection_reason="abcd",
                rejected_by_id=ctx.approver_id,
                rejected_at=created_at,
            )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_the_last_editor_cannot_decide_and_is_exposed() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        editor_id = await _new_user(session, "route-editor", ctx.suffix)
        draft = await _create(ctx, ctx.branch_b, "editor")
        assert draft["last_edited_by_id"] is None
        assert draft["last_edited_by_name"] is None
        edited = await ctx.use_cases.update_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            origin_warehouse_id=ctx.branch_a.id,
            destination_warehouse_id=ctx.branch_b.id,
            vehicle_id=ctx.base.vehicle_id,
            driver_id=ctx.driver_id,
            notes="Corregido por otra persona",
            lines=_lines(ctx.unit_a),
            idempotency_key=f"editor-update-{ctx.suffix}",
            actor_id=editor_id,
        )
        assert edited["last_edited_by_id"] == editor_id
        assert edited["last_edited_by_name"] == f"route-editor-{ctx.suffix[:12]}"
        pending = await _submit(ctx, draft["id"], "editor-submit")
        round_ = pending["approval_round"]
        assert pending["last_edited_by_id"] == editor_id
        error = await _expect(
            _approve(ctx, draft["id"], round_, "editor-approve", actor_id=editor_id),
            "transfer_approval_self_forbidden",
            403,
        )
        assert (
            error.message == "No puedes aprobar un traslado que tú preparaste, editaste o enviaste."
        )
        await _expect(
            _command(
                ctx,
                "reject",
                draft["id"],
                "editor-reject",
                actor_id=editor_id,
                expected_round=round_,
                reason="Intento de rechazo del editor",
            ),
            "transfer_approval_self_forbidden",
            403,
        )

        async def awaiting_ids(actor_id: uuid.UUID, **extra: Any) -> set[uuid.UUID]:
            rows = await ctx.use_cases.list_transfers(
                company_id=ctx.company_id, awaiting_approval_by=actor_id, **extra
            )
            return {row["id"] for row in rows}

        assert draft["id"] not in await awaiting_ids(editor_id)
        assert draft["id"] in await awaiting_ids(editor_id, allow_self_approval=True)
        assert draft["id"] in await awaiting_ids(ctx.approver_id)
        mine = {"company_id": ctx.company_id, "actor_id": editor_id}
        without = await ctx.use_cases.pending_approval_count(**mine)
        with_self = await ctx.use_cases.pending_approval_count(**mine, allow_self_approval=True)
        assert with_self == without + 1
        approved = await _approve(
            ctx,
            draft["id"],
            round_,
            "editor-approve-superuser",
            actor_id=editor_id,
            allow_self=True,
        )
        assert approved["status"] == "approved"

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_route_options_only_offer_warehouses_that_can_store_stock() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        company = ctx.company_id
        await _flush_in_savepoint(session, ctx.branch_b, storage_eligible=False)
        origins = await ctx.use_cases.route_options(company_id=company, can_move=True)
        assert ctx.branch_b.id not in {origin["id"] for origin in origins["origins"]}
        from_a = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.branch_a.id
        )
        assert ctx.branch_b.id not in {row["id"] for row in from_a["destinations"]}
        assert ctx.central.id in {row["id"] for row in from_a["destinations"]}

        await _flush_in_savepoint(session, ctx.central, storage_eligible=False)
        origins = await ctx.use_cases.route_options(company_id=company, can_move=True)
        assert ctx.central.id not in {origin["id"] for origin in origins["origins"]}
        from_a = await ctx.use_cases.route_options(
            company_id=company, can_move=True, origin_warehouse_id=ctx.branch_a.id
        )
        assert ctx.central.id not in {row["id"] for row in from_a["destinations"]}
        # The server refuses the same warehouses on the central route.
        await _expect(
            _create(
                ctx, ctx.branch_a, "central-origin", origin=ctx.central, unit_id=ctx.central_unit
            ),
            "transfer_origin_invalid",
            409,
        )
        await _flush_in_savepoint(session, ctx.central, storage_eligible=True)
        await _flush_in_savepoint(session, ctx.branch_a, storage_eligible=False)
        await _expect(
            _create(
                ctx,
                ctx.branch_a,
                "central-destination",
                origin=ctx.central,
                unit_id=ctx.central_unit,
            ),
            "transfer_destination_invalid",
            422,
        )

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_dispatching_a_draft_refuses_a_unit_promised_to_a_waiting_transfer() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        first = await _create(ctx, ctx.branch_b, "dispatch-commit-first")
        second = await _create(ctx, ctx.branch_b, "dispatch-commit-second")
        await _submit(ctx, first["id"], "dispatch-commit-submit")
        await _write_policy(session, ctx.company_id, require_approval=False)
        error = await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=second["id"],
                vehicle_id=ctx.base.vehicle_id,
                idempotency_key=f"dispatch-commit-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_handling_unit_committed",
            409,
        )
        assert first["code"] in error.message

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_a_draft_dispatched_after_approval_was_turned_off_does_not_claim_approval() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "no-claim")
        assert draft["requires_approval"] is True
        await _write_policy(session, ctx.company_id, require_approval=False)
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"no-claim-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert dispatched["status"] == "in_transit"
        assert dispatched["requires_approval"] is False
        assert dispatched["approved_by_id"] is None

    await _run(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_editing_a_saved_branch_transfer_with_its_routes_off_reports_the_route() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "edit-off")
        await _write_policy(
            session, ctx.company_id, allow_branch_to_branch=False, allow_branch_to_central=False
        )
        await _expect(
            ctx.use_cases.update_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                vehicle_id=ctx.base.vehicle_id,
                notes="Sigue en preparación",
                lines=_lines(ctx.unit_a),
                idempotency_key=f"edit-off-update-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_route_disabled",
            409,
        )

    await _run(body, **ALL_ROUTES)
