"""Punto de venta: cajas, turnos, efectivo, arqueo ciego, depósitos y PIN (bloque V6a).

Permisos:

- ``pos:registers_manage`` configura las cajas.
- ``pos:shift_open`` / ``pos:shift_close`` / ``pos:cash_movements``: el cajero opera **su** turno.
- ``pos:supervise``: ver los turnos de la sucursal, pedir recuento, aprobar el cierre y autorizar con
  su PIN. Nunca su propio turno.
- ``pos:reports``: informes del turno; ``pos:deposits``: depósitos bancarios.

Toda escritura queda en la bitácora. Mientras un turno no se cierra, el esperado y la diferencia
solo los ve un supervisor que no es el cajero (cierre ciego).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_pos_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.pos import (
    ApproveIn,
    CountIn,
    CountOut,
    DenominationIn,
    DenominationOut,
    DepositIn,
    DepositOut,
    DepositShiftOut,
    MeOut,
    MovementIn,
    MovementOut,
    OpenShiftIn,
    PersonOut,
    PinIn,
    PointOfSaleOptionOut,
    RecountIn,
    RegisterCreateIn,
    RegisterOut,
    RegisterUpdateIn,
    ShiftDetailOut,
    ShiftOut,
    ShiftPage,
    ShiftTotalsOut,
)
from app.application.audit.audit_service import AuditService
from app.application.organization import GetOperationalContext
from app.application.pos.use_cases import PosUseCases, ShiftDetail, SupervisorApproval
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.pos import (
    CashMovementKind,
    DenominationCount,
    DenominationForm,
    ShiftStatus,
    deposit_code,
    shift_code,
)
from app.domain.ports.pos_repository import (
    CashMovement,
    Deposit,
    DepositShift,
    PointOfSaleOption,
    Register,
    RegisterData,
    Shift,
    ShiftCount,
    ShiftFilter,
)
from app.infrastructure.repositories import SqlAlchemyOperationalContextRepository

router = APIRouter(prefix="/pos", tags=["pos"])
_TZ = ZoneInfo("America/El_Salvador")
UseCases = Annotated[PosUseCases, Depends(get_pos_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]

_ANY_POS = [
    Depends(
        require_any_permission(
            "pos:sell",
            "pos:shift_open",
            "pos:shift_close",
            "pos:cash_movements",
            "pos:supervise",
            "pos:registers_manage",
            "pos:reports",
            "pos:deposits",
        )
    )
]
_MANAGE = [Depends(require_permission("pos:registers_manage"))]
_REGISTERS_READ = [
    Depends(require_any_permission("pos:registers_manage", "pos:shift_open", "pos:supervise"))
]
_OPEN = [Depends(require_permission("pos:shift_open"))]
_CLOSE = [Depends(require_permission("pos:shift_close"))]
_MOVE = [Depends(require_permission("pos:cash_movements"))]
_SUPERVISE = [Depends(require_permission("pos:supervise"))]
_SHIFTS_READ = [Depends(require_any_permission("pos:supervise", "pos:reports"))]
_DEPOSITS = [Depends(require_permission("pos:deposits"))]


# --- utilidades --------------------------------------------------------------------------------


async def _allowed(
    checker: CheckPermissionUseCase, user: uuid.UUID, company: uuid.UUID, code: str
) -> bool:
    return (await checker.execute(user, company, code)).allowed


async def _branch_ids(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID, branch_id: uuid.UUID | None
) -> list[uuid.UUID] | None:
    """Sucursales que el usuario puede ver: la pedida o, si no pide, todas las suyas."""
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
        return [branch_id]
    await require_company_access(session, current, company_id)
    context = await GetOperationalContext(SqlAlchemyOperationalContextRepository(session)).execute(
        user_id=current.id, company_id=company_id, is_superuser=current.is_superuser
    )
    return None if context.access_all_branches else [branch.id for branch in context.branches]


def _person(person_id: uuid.UUID | None, name: str | None) -> PersonOut | None:
    return None if person_id is None or name is None else PersonOut(id=person_id, name=name)


def _register(item: Register) -> RegisterOut:
    return RegisterOut(
        id=item.id,
        branch_id=item.branch_id,
        branch_name=item.branch_name,
        establishment_code=item.establishment_code,
        point_of_sale_id=item.point_of_sale_id,
        point_of_sale_code=item.point_of_sale_code,
        code=item.code,
        name=item.name,
        opening_float=item.opening_float,
        cash_out_approval_threshold=item.cash_out_approval_threshold,
        cash_drawer_limit=item.cash_drawer_limit,
        is_active=item.is_active,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        unclosed_shift_id=item.unclosed_shift_id,
        unclosed_shift_cashier=item.unclosed_shift_cashier,
        has_shifts=item.has_shifts,
    )


def _point(item: PointOfSaleOption) -> PointOfSaleOptionOut:
    reason = None
    if item.register_id is not None:
        reason = "Ya tiene una caja."
    elif not item.is_active or not item.establishment_active:
        reason = "Está inactivo en la configuración fiscal."
    return PointOfSaleOptionOut(
        id=item.id,
        code=item.code,
        name=item.name,
        establishment_code=item.establishment_code,
        branch_id=item.branch_id,
        branch_name=item.branch_name,
        available=reason is None,
        unavailable_reason=reason,
    )


def _shift(item: Shift, *, amounts_visible: bool) -> ShiftOut:
    """``amounts_visible`` decide si se muestran el esperado y la diferencia (cierre ciego)."""
    visible = amounts_visible or item.status is ShiftStatus.CLOSED
    return ShiftOut(
        id=item.id,
        number=item.number,
        code=shift_code(item.number),
        branch_id=item.branch_id,
        branch_name=item.branch_name,
        register_id=item.register_id,
        register_code=item.register_code,
        register_name=item.register_name,
        cashier=PersonOut(id=item.cashier_id, name=item.cashier_name),
        status=item.status.value,
        opening_float=item.opening_float,
        opened_at=item.opened_at,
        counted_at=item.counted_at,
        recount_reason=item.recount_reason,
        closed_at=item.closed_at,
        approved_by=_person(item.approved_by_id, item.approved_by_name),
        approval_notes=item.approval_notes,
        counted_cash=item.counted_cash,
        declared_card=item.declared_card,
        declared_transfer=item.declared_transfer,
        expected_cash=item.expected_cash if visible else None,
        cash_difference=item.cash_difference if visible else None,
        expected_card=item.expected_card if visible else None,
        expected_transfer=item.expected_transfer if visible else None,
        retained_float=item.retained_float,
        cash_to_deposit=item.cash_to_deposit,
        deposit_id=item.deposit_id,
        deposit_number=item.deposit_number,
        version=item.version,
        amounts_visible=visible,
    )


def _movement(item: CashMovement) -> MovementOut:
    return MovementOut(
        id=item.id,
        kind=item.kind.value,
        amount=item.amount,
        reason=item.reason,
        reference=item.reference,
        authorized_by=_person(item.authorized_by_id, item.authorized_by_name),
        created_by=PersonOut(id=item.created_by_id, name=item.created_by_name),
        created_at=item.created_at,
    )


def _count(item: ShiftCount) -> CountOut:
    return CountOut(
        id=item.id,
        kind=item.kind.value,
        sequence=item.sequence,
        cash_total=item.cash_total,
        card_total=item.card_total,
        transfer_total=item.transfer_total,
        notes=item.notes,
        counted_by=PersonOut(id=item.counted_by_id, name=item.counted_by_name),
        counted_at=item.counted_at,
        denominations=[
            DenominationOut(
                form=line.form.value,
                denomination=line.denomination,
                quantity=line.quantity,
                amount=line.amount,
            )
            for line in item.lines
        ],
    )


def _detail(detail: ShiftDetail, *, amounts_visible: bool) -> ShiftDetailOut:
    totals = detail.totals
    visible = amounts_visible or detail.shift.status is ShiftStatus.CLOSED
    return ShiftDetailOut(
        shift=_shift(detail.shift, amounts_visible=amounts_visible),
        register_detail=_register(detail.register),
        movements=[_movement(item) for item in detail.movements],
        counts=[_count(item) for item in detail.counts],
        totals=(
            ShiftTotalsOut(
                opening_float=totals.opening_float,
                cash_in=totals.cash_in,
                cash_out=totals.cash_out,
                safe_drops=totals.safe_drops,
                cash_sales=totals.cash_sales,
                cash_refunds=totals.cash_refunds,
                card_sales=totals.card_sales,
                card_refunds=totals.card_refunds,
                transfer_sales=totals.transfer_sales,
                transfer_refunds=totals.transfer_refunds,
                expected_cash=totals.expected_cash,
                expected_card=totals.expected_card,
                expected_transfer=totals.expected_transfer,
            )
            if visible
            else None
        ),
        drawer_limit_reached=detail.drawer_limit_reached,
    )


def _deposit_shift(item: DepositShift) -> DepositShiftOut:
    return DepositShiftOut(
        shift_id=item.shift_id,
        shift_number=item.shift_number,
        shift_code=shift_code(item.shift_number),
        register_code=item.register_code,
        cashier_name=item.cashier_name,
        closed_at=item.closed_at,
        amount=item.amount,
    )


def _deposit(item: Deposit) -> DepositOut:
    return DepositOut(
        id=item.id,
        number=item.number,
        code=deposit_code(item.number),
        branch_id=item.branch_id,
        branch_name=item.branch_name,
        deposited_on=item.deposited_on,
        bank_name=item.bank_name,
        account_reference=item.account_reference,
        slip_number=item.slip_number,
        expected_amount=item.expected_amount,
        deposited_amount=item.deposited_amount,
        difference=item.difference,
        notes=item.notes,
        created_by_name=item.created_by_name,
        created_at=item.created_at,
        shifts=[_deposit_shift(shift) for shift in item.shifts],
    )


def _lines(items: list[DenominationIn]) -> list[DenominationCount]:
    return [
        DenominationCount(DenominationForm(item.form), item.denomination, item.quantity)
        for item in items
    ]


def _approval(item: Any) -> SupervisorApproval | None:
    return None if item is None else SupervisorApproval(item.supervisor_id, item.pin)


async def _audit(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        branch_id=branch_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _shift_state(item: Shift) -> dict[str, Any]:
    return _shift(item, amounts_visible=True).model_dump(mode="json")


async def _readable_shift(
    cases: PosUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    checker: CheckPermissionUseCase,
    shift_id: uuid.UUID,
) -> tuple[Shift, bool]:
    """Un turno lo ve su cajero o quien supervisa o revisa informes en su sucursal.

    Devuelve si quien lo ve puede ver el esperado: nunca el propio cajero mientras no se cierre.
    """
    shift = await cases.shift(company_id, shift_id)
    await resolve_branch_scope(session, current, company_id, shift.branch_id)
    if shift.cashier_id == current.id:
        return shift, False
    for code in ("pos:supervise", "pos:reports"):
        if await _allowed(checker, current.id, company_id, code):
            return shift, True
    raise AuthorizationError("No puedes ver ese turno.", code="pos_shift_forbidden")


# --- yo (la caja de quien está conectado) ------------------------------------------------------


@router.get("/me", response_model=MeOut, summary="Mi turno y mi PIN", dependencies=_ANY_POS)
async def me(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    checker: Checker,
) -> MeOut:
    await require_company_access(session, current, company_id)
    shift = await cases.current_shift(company_id, current.id)
    person = await cases.person(current.id)
    return MeOut(
        user=PersonOut(id=current.id, name=person),
        shift=None if shift is None else _shift(shift, amounts_visible=False),
        has_pin=await cases.has_pin(current.id),
        can_supervise=await _allowed(checker, current.id, company_id, "pos:supervise"),
    )


@router.put(
    "/me/pin",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Definir o cambiar mi PIN de autorización",
    dependencies=_SUPERVISE,
)
async def set_pin(
    body: PinIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> Response:
    await require_company_access(session, current, company_id)
    await cases.set_pin(current.id, body.password, body.pin)
    await audit.record(
        action="SET_POS_SUPERVISOR_PIN",
        user_id=current.id,
        company_id=company_id,
        resource_type="pos_supervisor_pin",
        resource_id=str(current.id),
        before_state=None,
        after_state={"configured": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/branches/{branch_id:uuid}/supervisors",
    response_model=list[PersonOut],
    summary="Quiénes pueden autorizar en la caja de esta sucursal",
    dependencies=_ANY_POS,
)
async def supervisors(
    branch_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> list[PersonOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [
        PersonOut(id=item.id, name=item.name)
        for item in await cases.supervisors(company_id, branch_id)
        if item.id != current.id
    ]


# --- cajas -------------------------------------------------------------------------------------


@router.get(
    "/point-of-sale-options",
    response_model=list[PointOfSaleOptionOut],
    summary="Puntos de venta fiscales para crear cajas",
    dependencies=_MANAGE,
)
async def point_of_sale_options(
    session: SessionDep, current: CurrentUser, company_id: CompanyId, cases: UseCases
) -> list[PointOfSaleOptionOut]:
    branches = await _branch_ids(session, current, company_id, None)
    return [
        _point(item)
        for item in await cases.point_of_sale_options(company_id)
        if branches is None or item.branch_id in branches
    ]


@router.get(
    "/registers",
    response_model=list[RegisterOut],
    summary="Cajas de las sucursales del usuario",
    dependencies=_REGISTERS_READ,
)
async def list_registers(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[RegisterOut]:
    branches = await _branch_ids(session, current, company_id, branch_id)
    return [_register(item) for item in await cases.registers(company_id, branches)]


@router.get(
    "/registers/{register_id:uuid}",
    response_model=RegisterOut,
    summary="Detalle de una caja",
    dependencies=_REGISTERS_READ,
)
async def get_register(
    register_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> RegisterOut:
    register = await cases.register(company_id, register_id)
    await resolve_branch_scope(session, current, company_id, register.branch_id)
    return _register(register)


def _register_data(body: RegisterCreateIn | RegisterUpdateIn) -> RegisterData:
    return RegisterData(
        code=body.code,
        name=body.name,
        opening_float=body.opening_float,
        cash_out_approval_threshold=body.cash_out_approval_threshold,
        cash_drawer_limit=body.cash_drawer_limit,
        is_active=body.is_active,
    )


@router.post(
    "/registers",
    response_model=RegisterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una caja sobre un punto de venta fiscal",
    dependencies=_MANAGE,
)
async def create_register(
    body: RegisterCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> RegisterOut:
    point = await cases.point_of_sale(company_id, body.point_of_sale_id)
    await resolve_branch_scope(session, current, company_id, point.branch_id)
    register = await cases.create_register(
        company_id, current.id, body.point_of_sale_id, _register_data(body)
    )
    out = _register(register)
    await _audit(
        audit,
        request,
        action="CREATE_POS_REGISTER",
        actor=current.id,
        company_id=company_id,
        branch_id=register.branch_id,
        resource_type="pos_register",
        resource_id=register.id,
        before=None,
        after=out.model_dump(mode="json"),
    )
    return out


@router.put(
    "/registers/{register_id:uuid}",
    response_model=RegisterOut,
    summary="Editar una caja",
    dependencies=_MANAGE,
)
async def update_register(
    register_id: uuid.UUID,
    body: RegisterUpdateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> RegisterOut:
    before = await cases.register(company_id, register_id)
    await resolve_branch_scope(session, current, company_id, before.branch_id)
    register = await cases.update_register(
        company_id, current.id, register_id, body.expected_version, _register_data(body)
    )
    out = _register(register)
    await _audit(
        audit,
        request,
        action="UPDATE_POS_REGISTER",
        actor=current.id,
        company_id=company_id,
        branch_id=register.branch_id,
        resource_type="pos_register",
        resource_id=register.id,
        before=_register(before).model_dump(mode="json"),
        after=out.model_dump(mode="json"),
    )
    return out


# --- turnos ------------------------------------------------------------------------------------


@router.post(
    "/shifts",
    response_model=ShiftOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir mi turno con el conteo del fondo (idempotente por llave)",
    dependencies=_OPEN,
)
async def open_shift(
    body: OpenShiftIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ShiftOut:
    register = await cases.register(company_id, body.register_id)
    await resolve_branch_scope(session, current, company_id, register.branch_id)
    existing = await cases.shift_by_key(company_id, body.idempotency_key)
    shift = await cases.open_shift(
        company_id,
        current.id,
        body.register_id,
        _lines(body.denominations),
        body.notes,
        body.idempotency_key,
    )
    if existing is None:
        await _audit(
            audit,
            request,
            action="OPEN_POS_SHIFT",
            actor=current.id,
            company_id=company_id,
            branch_id=shift.branch_id,
            resource_type="pos_shift",
            resource_id=shift.id,
            before=None,
            after=_shift_state(shift),
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _shift(shift, amounts_visible=False)


@router.get(
    "/shifts",
    response_model=ShiftPage,
    summary="Turnos de las sucursales del usuario",
    dependencies=_SHIFTS_READ,
)
async def list_shifts(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[list[ShiftStatus] | None, Query(alias="status")] = None,
    register_id: Annotated[uuid.UUID | None, Query()] = None,
    cashier_id: Annotated[uuid.UUID | None, Query()] = None,
    opened_from: Annotated[date | None, Query(alias="from")] = None,
    opened_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ShiftPage:
    branches = await _branch_ids(session, current, company_id, branch_id)
    items, total = await cases.shifts(
        company_id,
        ShiftFilter(
            branch_ids=branches,
            statuses=status_filter,
            register_id=register_id,
            cashier_id=cashier_id,
            opened_from=opened_from,
            opened_to=opened_to,
            limit=limit,
            offset=offset,
        ),
    )
    return ShiftPage(
        items=[_shift(item, amounts_visible=item.cashier_id != current.id) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/shifts/{shift_id:uuid}",
    response_model=ShiftDetailOut,
    summary="Detalle del turno: movimientos, conteos y, para el supervisor, el esperado",
    dependencies=_ANY_POS,
)
async def get_shift(
    shift_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    checker: Checker,
) -> ShiftDetailOut:
    _, visible = await _readable_shift(cases, session, current, company_id, checker, shift_id)
    return _detail(await cases.detail(company_id, shift_id), amounts_visible=visible)


@router.post(
    "/shifts/{shift_id:uuid}/movements",
    response_model=MovementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Entrada, salida o retiro de efectivo de mi turno (idempotente por llave)",
    dependencies=_MOVE,
)
async def add_movement(
    shift_id: uuid.UUID,
    body: MovementIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> MovementOut:
    shift = await cases.shift(company_id, shift_id)
    await resolve_branch_scope(session, current, company_id, shift.branch_id)
    existing = await cases.movement_by_key(company_id, body.idempotency_key)
    movement = await cases.add_movement(
        company_id,
        current.id,
        shift_id,
        kind=CashMovementKind(body.kind),
        amount=body.amount,
        reason=body.reason,
        reference=body.reference,
        approval=_approval(body.approval),
        idempotency_key=body.idempotency_key,
    )
    out = _movement(movement)
    if existing is None:
        await _audit(
            audit,
            request,
            action="POS_CASH_MOVEMENT",
            actor=current.id,
            company_id=company_id,
            branch_id=shift.branch_id,
            resource_type="pos_shift",
            resource_id=shift.id,
            before=None,
            after=out.model_dump(mode="json"),
        )
    else:
        response.status_code = status.HTTP_200_OK
    return out


@router.post(
    "/shifts/{shift_id:uuid}/count",
    response_model=ShiftOut,
    summary="Contar y entregar mi turno (cierre ciego)",
    dependencies=_CLOSE,
)
async def count_shift(
    shift_id: uuid.UUID,
    body: CountIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ShiftOut:
    before = await cases.shift(company_id, shift_id)
    await resolve_branch_scope(session, current, company_id, before.branch_id)
    shift = await cases.count(
        company_id,
        current.id,
        shift_id,
        expected_version=body.expected_version,
        lines=_lines(body.denominations),
        declared_card=body.declared_card,
        declared_transfer=body.declared_transfer,
        notes=body.notes,
    )
    await _audit(
        audit,
        request,
        action="COUNT_POS_SHIFT",
        actor=current.id,
        company_id=company_id,
        branch_id=shift.branch_id,
        resource_type="pos_shift",
        resource_id=shift.id,
        before=_shift_state(before),
        after=_shift_state(shift),
    )
    return _shift(shift, amounts_visible=False)


@router.post(
    "/shifts/{shift_id:uuid}/recount",
    response_model=ShiftOut,
    summary="Pedir al cajero que vuelva a contar",
    dependencies=_SUPERVISE,
)
async def request_recount(
    shift_id: uuid.UUID,
    body: RecountIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ShiftOut:
    before = await cases.shift(company_id, shift_id)
    await resolve_branch_scope(session, current, company_id, before.branch_id)
    shift = await cases.request_recount(
        company_id, current.id, shift_id, expected_version=body.expected_version, reason=body.reason
    )
    await _audit(
        audit,
        request,
        action="REQUEST_POS_SHIFT_RECOUNT",
        actor=current.id,
        company_id=company_id,
        branch_id=shift.branch_id,
        resource_type="pos_shift",
        resource_id=shift.id,
        before=_shift_state(before),
        after=_shift_state(shift),
    )
    return _shift(shift, amounts_visible=True)


@router.post(
    "/shifts/{shift_id:uuid}/approve",
    response_model=ShiftOut,
    summary="Aprobar el cierre del turno; un cierre aprobado no se modifica",
    dependencies=_SUPERVISE,
)
async def approve_shift(
    shift_id: uuid.UUID,
    body: ApproveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ShiftOut:
    before = await cases.shift(company_id, shift_id)
    await resolve_branch_scope(session, current, company_id, before.branch_id)
    shift = await cases.approve(
        company_id,
        current.id,
        shift_id,
        expected_version=body.expected_version,
        retained_float=body.retained_float,
        notes=body.notes,
    )
    await _audit(
        audit,
        request,
        action="APPROVE_POS_SHIFT",
        actor=current.id,
        company_id=company_id,
        branch_id=shift.branch_id,
        resource_type="pos_shift",
        resource_id=shift.id,
        before=_shift_state(before),
        after=_shift_state(shift),
    )
    return _shift(shift, amounts_visible=True)


# --- depósitos ---------------------------------------------------------------------------------


@router.get(
    "/deposits/candidates",
    response_model=list[DepositShiftOut],
    summary="Turnos cerrados de la sucursal con efectivo por depositar",
    dependencies=_DEPOSITS,
)
async def deposit_candidates(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: Annotated[uuid.UUID, Query()],
) -> list[DepositShiftOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [_deposit_shift(item) for item in await cases.deposit_candidates(company_id, branch_id)]


@router.get(
    "/deposits",
    response_model=list[DepositOut],
    summary="Depósitos bancarios de las sucursales del usuario",
    dependencies=_DEPOSITS,
)
async def list_deposits(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[DepositOut]:
    branches = await _branch_ids(session, current, company_id, branch_id)
    return [_deposit(item) for item in await cases.deposits(company_id, branches)]


@router.get(
    "/deposits/{deposit_id:uuid}",
    response_model=DepositOut,
    summary="Detalle de un depósito",
    dependencies=_DEPOSITS,
)
async def get_deposit(
    deposit_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> DepositOut:
    deposit = await cases.deposit(company_id, deposit_id)
    await resolve_branch_scope(session, current, company_id, deposit.branch_id)
    return _deposit(deposit)


@router.post(
    "/deposits",
    response_model=DepositOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar el depósito bancario de turnos cerrados (idempotente por llave)",
    dependencies=_DEPOSITS,
)
async def create_deposit(
    body: DepositIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> DepositOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    existing = await cases.deposit_by_key(company_id, body.idempotency_key)
    deposit = await cases.create_deposit(
        company_id,
        current.id,
        branch_id=body.branch_id,
        shift_ids=body.shift_ids,
        deposited_on=body.deposited_on,
        bank_name=body.bank_name,
        account_reference=body.account_reference,
        slip_number=body.slip_number,
        deposited_amount=body.deposited_amount,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        today=datetime.now(_TZ).date(),
    )
    out = _deposit(deposit)
    if existing is None:
        await _audit(
            audit,
            request,
            action="CREATE_POS_DEPOSIT",
            actor=current.id,
            company_id=company_id,
            branch_id=deposit.branch_id,
            resource_type="pos_deposit",
            resource_id=deposit.id,
            before=None,
            after=out.model_dump(mode="json"),
        )
    else:
        response.status_code = status.HTTP_200_OK
    return out
