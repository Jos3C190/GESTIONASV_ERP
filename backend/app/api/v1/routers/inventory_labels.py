"""Inventory label preview and append-only print registration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    authorize_handling_unit_branch_scope,
    authorize_warehouse_assignment,
    effective_company_id,
    resolve_branch_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.inventory_labels import (
    InventoryLabelConfirmationIn,
    InventoryLabelConfirmationOut,
    InventoryLabelPreviewIn,
    InventoryLabelPreviewOut,
    InventoryLabelPrintIn,
    InventoryLabelPrintOut,
)
from app.application.audit.audit_service import AuditService
from app.core.exceptions import ConflictError
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Warehouse
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.repositories.inventory_label_repository import (
    SqlAlchemyInventoryLabelRepository,
)
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)

router = APIRouter(
    prefix="/inventory/labels",
    tags=["inventory labels"],
    dependencies=[Depends(require_permission("inventory:receive"))],
)


async def _authorize_target(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    *,
    inventory_lot_detail_id: uuid.UUID | None = None,
    handling_unit_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    if (inventory_lot_detail_id is None) == (handling_unit_id is None):
        raise HTTPException(422, "Seleccione un detalle de lote o una unidad logística.")
    company_id = effective_company_id(request)
    # Use the same company-wide mutex as valuation and stock mutations before
    # reading ownership, then scope the operation to the target's real warehouse.
    await SqlAlchemyInventoryValuationRepository(session).lock(company_id)
    if handling_unit_id is not None:
        _, branch_id = await authorize_handling_unit_branch_scope(
            session, current, company_id, handling_unit_id
        )
        return company_id, branch_id

    row = await session.execute(
        select(Warehouse.branch_id, Warehouse.id.label("warehouse_id"))
        .select_from(InventoryLotDetailModel)
        .join(
            InventoryLotModel,
            (InventoryLotModel.company_id == InventoryLotDetailModel.company_id)
            & (InventoryLotModel.id == InventoryLotDetailModel.inventory_lot_id),
        )
        .join(
            PurchaseModel,
            (PurchaseModel.company_id == InventoryLotModel.company_id)
            & (PurchaseModel.id == InventoryLotModel.purchase_id),
        )
        .join(
            Warehouse,
            (Warehouse.company_id == PurchaseModel.company_id)
            & (Warehouse.id == PurchaseModel.warehouse_id),
        )
        .where(
            InventoryLotDetailModel.company_id == company_id,
            InventoryLotDetailModel.id == inventory_lot_detail_id,
        )
    )
    persisted = row.one_or_none()
    if persisted is None:
        raise HTTPException(404, "El detalle de recepción no existe en esta empresa.")
    branch_id = persisted.branch_id
    if branch_id is None:
        raise HTTPException(409, "La bodega aún no está asociada a una sucursal matriz.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    await authorize_warehouse_assignment(session, current, company_id, persisted.warehouse_id)
    return company_id, branch_id


@router.get("/preview", response_model=InventoryLabelPreviewOut)
async def preview_label(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    inventory_lot_detail_id: uuid.UUID | None = None,
    handling_unit_id: uuid.UUID | None = None,
) -> InventoryLabelPreviewOut:
    company_id, _ = await _authorize_target(
        request,
        session,
        current,
        inventory_lot_detail_id=inventory_lot_detail_id,
        handling_unit_id=handling_unit_id,
    )
    target = InventoryLabelPreviewIn(
        inventory_lot_detail_id=inventory_lot_detail_id,
        handling_unit_id=handling_unit_id,
    )
    preview = await SqlAlchemyInventoryLabelRepository(session).preview(
        company_id=company_id,
        inventory_lot_detail_id=target.inventory_lot_detail_id,
        handling_unit_id=target.handling_unit_id,
    )
    return InventoryLabelPreviewOut.model_validate(preview)


@router.post("/prints", response_model=InventoryLabelPrintOut)
async def register_label_print(
    body: InventoryLabelPrintIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> InventoryLabelPrintOut:
    company_id, branch_id = await _authorize_target(
        request,
        session,
        current,
        inventory_lot_detail_id=body.inventory_lot_detail_id,
        handling_unit_id=body.handling_unit_id,
    )
    repository = SqlAlchemyInventoryLabelRepository(session)
    try:
        async with session.begin_nested():
            entry, created = await repository.register_print(
                company_id=company_id,
                inventory_lot_detail_id=body.inventory_lot_detail_id,
                handling_unit_id=body.handling_unit_id,
                idempotency_key=body.idempotency_key,
                quantity_printed=body.quantity_printed,
                print_date=body.print_date,
                reason=body.reason,
                actor_id=current.id,
                layout=body.layout.to_domain() if body.layout else None,
                notes=body.notes,
            )
            if created:
                await audit.record(
                    action="PRINT_LABELS" if body.reason == "initial" else "REPRINT_LABELS",
                    user_id=current.id,
                    company_id=company_id,
                    branch_id=branch_id,
                    resource_type="inventory_label_prints",
                    resource_id=str(entry.id),
                    after_state={
                        "inventory_lot_id": str(entry.inventory_lot_id),
                        "inventory_lot_detail_id": str(entry.inventory_lot_detail_id)
                        if entry.inventory_lot_detail_id
                        else None,
                        "handling_unit_id": str(entry.handling_unit_id)
                        if entry.handling_unit_id
                        else None,
                        "quantity_printed": entry.quantity_printed,
                        "print_date": entry.print_date.isoformat(),
                        "reason": entry.reason,
                        "label_snapshot": entry.label_snapshot,
                    },
                    required=True,
                )
            response = InventoryLabelPrintOut.model_validate(entry)
    except IntegrityError as exc:
        # A duplicate request can arrive under a different target lock when a
        # client accidentally reuses its key. Fail closed without leaking SQL.
        existing = await repository.get_by_key(company_id, body.idempotency_key)
        if existing is not None:
            response = InventoryLabelPrintOut.model_validate(existing)
            if (
                existing.quantity_printed != body.quantity_printed
                or existing.print_date != body.print_date
                or existing.reason != body.reason
                or existing.inventory_lot_detail_id != body.inventory_lot_detail_id
                or existing.handling_unit_id != body.handling_unit_id
                or existing.label_snapshot.get("print_layout")
                != (body.layout.model_dump() if body.layout else None)
                or existing.label_snapshot.get("notes") != ((body.notes or "").strip() or None)
            ):
                raise ConflictError(
                    "La clave de impresión ya se usó con otros datos.",
                    code="inventory_label_idempotency_conflict",
                ) from exc
            return response
        raise ConflictError(
            "La etiqueta cambió durante el registro; recarga la vista previa e inténtalo de nuevo.",
            code="inventory_label_print_conflict",
        ) from exc
    return response


@router.post("/confirmations", response_model=InventoryLabelConfirmationOut)
async def confirm_label_placement(
    body: InventoryLabelConfirmationIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> InventoryLabelConfirmationOut:
    company_id, branch_id = await _authorize_target(
        request, session, current, handling_unit_id=body.handling_unit_id
    )
    repository = SqlAlchemyInventoryLabelRepository(session)
    async with session.begin_nested():
        confirmation, created = await repository.confirm_handling_unit_label(
            company_id=company_id,
            handling_unit_id=body.handling_unit_id,
            handling_unit_code=body.handling_unit_code,
            label_print_id=body.label_print_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        )
        if created:
            await audit.record(
                action="CONFIRM_INVENTORY_LABEL_PLACEMENT",
                user_id=current.id,
                company_id=company_id,
                branch_id=branch_id,
                resource_type="inventory_handling_units",
                resource_id=str(confirmation.handling_unit_id),
                after_state={
                    "confirmation_id": str(confirmation.id),
                    "label_print_id": str(confirmation.label_print_id),
                    "handling_unit_code": confirmation.handling_unit_code,
                    "label_revision": confirmation.label_revision,
                    "quantity_base": str(confirmation.quantity_base),
                    "label_fingerprint": confirmation.label_fingerprint,
                    "confirmed_at": confirmation.confirmed_at.isoformat(),
                },
                required=True,
            )
        return InventoryLabelConfirmationOut.model_validate(confirmation)


__all__ = ["router"]
