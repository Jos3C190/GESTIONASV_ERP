"""Libros de IVA y anexos del F-07 por empresa y mes.

Ver y descargar pide ``fiscal_books:read``. Registrar el documento del proveedor de una compra y la
renta de compras por defecto pide ``fiscal_books:manage`` y queda en la bitácora.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_fiscal_book_use_cases,
    require_permission,
)
from app.api.v1.schemas.fiscal_book import (
    AnnexOut,
    ConsumerLineOut,
    ContributorLineOut,
    FiscalMonthOut,
    IssuerOut,
    PendingPurchaseOut,
    PurchaseFiscalIn,
    PurchaseFiscalOut,
    PurchaseLineOut,
    RentaPurchaseIn,
    RentaPurchaseOut,
    SummaryOut,
)
from app.application.audit.audit_service import AuditService
from app.application.fiscal_books.use_cases import FiscalBookUseCases, MonthView
from app.domain.entities.fiscal_books import (
    ANNEX_FILES,
    PurchaseFiscalData,
    RentaPurchase,
    annex_file_name,
)
from app.domain.ports.fiscal_book_repository import PurchaseFiscalView

router = APIRouter(prefix="/fiscal-books", tags=["fiscal-books"])

UseCases = Annotated[FiscalBookUseCases, Depends(get_fiscal_book_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("fiscal_books:read"))]
_MANAGE = [Depends(require_permission("fiscal_books:manage"))]
_TZ = ZoneInfo("America/El_Salvador")


def _renta_out(renta: RentaPurchase) -> RentaPurchaseOut:
    return RentaPurchaseOut(
        operation=renta.operation,
        classification=renta.classification,
        sector=renta.sector,
        cost_type=renta.cost_type,
    )


def month_out(view: MonthView) -> FiscalMonthOut:
    month = view.month
    summary = view.summary
    return FiscalMonthOut(
        period=month.period.key,
        label=month.period.label,
        mode=month.mode,
        modes=view.modes,
        issuer=IssuerOut(name=view.issuer.name, nit=view.issuer.nit, nrc=view.issuer.nrc),
        warnings=month.warnings,
        summary=SummaryOut(**summary.__dict__),
        contributor_book=[ContributorLineOut(**line.__dict__) for line in month.contributor_book],
        consumer_book=[ConsumerLineOut(**line.__dict__) for line in month.consumer_book],
        purchase_book=[PurchaseLineOut(**line.__dict__) for line in month.purchase_book],
        annexes=[
            AnnexOut(
                key=key,
                title=title,
                file_name=annex_file_name(key, month.period, month.mode),
                rows=[row.cells() for row in getattr(month, attribute)],
            )
            for key, (title, attribute) in ANNEX_FILES.items()
        ],
        pending_purchases=[PendingPurchaseOut(**item.__dict__) for item in view.pending_purchases],
    )


def _purchase_out(view: PurchaseFiscalView, defaults: RentaPurchase) -> PurchaseFiscalOut:
    fiscal = view.fiscal
    return PurchaseFiscalOut(
        id=view.id,
        code=view.code,
        status=view.status,
        supplier_name=view.supplier_name,
        supplier_ids=view.supplier_ids,
        invoice_number=view.invoice_number,
        invoice_date=view.invoice_date,
        exempt=view.exempt,
        taxed=view.taxed,
        vat=view.vat,
        recorded=(
            PurchaseFiscalIn(
                issued_on=fiscal.issued_on,
                document_class=fiscal.document_class,  # type: ignore[arg-type]
                document_type=fiscal.document_type,  # type: ignore[arg-type]
                number=fiscal.number,
                control_number=fiscal.control_number,
                seal=fiscal.seal,
                supplier_name=fiscal.supplier_name,
                supplier_id_type=fiscal.supplier_id_type,  # type: ignore[arg-type]
                supplier_id=fiscal.supplier_id,
                renta=RentaPurchaseIn(**_renta_out(fiscal.renta).model_dump()),
            )
            if fiscal
            else None
        ),
        recorded_at=view.recorded_at,
        renta_defaults=_renta_out(defaults),
    )


@router.get(
    "/settings",
    response_model=RentaPurchaseOut,
    summary="Renta de compras que se propone al registrar el documento del proveedor",
    dependencies=_READ,
)
async def get_settings(company_id: CompanyId, cases: UseCases) -> RentaPurchaseOut:
    return _renta_out(await cases.renta_defaults(company_id))


@router.put(
    "/settings",
    response_model=RentaPurchaseOut,
    summary="Cambiar la renta de compras por defecto",
    dependencies=_MANAGE,
)
async def save_settings(
    body: RentaPurchaseIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> RentaPurchaseOut:
    before = await cases.renta_defaults(company_id)
    saved = await cases.save_renta_defaults(
        company_id,
        RentaPurchase(body.operation, body.classification, body.sector, body.cost_type),
        current.id,
    )
    await audit.record(
        action="UPDATE_FISCAL_BOOK_SETTINGS",
        user_id=current.id,
        company_id=company_id,
        resource_type="fiscal_book_settings",
        resource_id=str(company_id),
        before_state=before.__dict__,
        after_state=saved.__dict__,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return _renta_out(saved)


@router.get(
    "/purchases/{purchase_id}",
    response_model=PurchaseFiscalOut,
    summary="Documento del proveedor registrado en una compra",
    dependencies=_READ,
)
async def get_purchase(
    purchase_id: uuid.UUID, company_id: CompanyId, cases: UseCases
) -> PurchaseFiscalOut:
    view = await cases.purchase(company_id, purchase_id)
    return _purchase_out(view, await cases.renta_defaults(company_id))


@router.put(
    "/purchases/{purchase_id}",
    response_model=PurchaseFiscalOut,
    summary="Registrar o corregir el documento del proveedor de una compra",
    dependencies=_MANAGE,
)
async def record_purchase(
    purchase_id: uuid.UUID,
    body: PurchaseFiscalIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> PurchaseFiscalOut:
    defaults = await cases.renta_defaults(company_id)
    previous = _purchase_out(await cases.purchase(company_id, purchase_id), defaults).recorded
    view = await cases.record_purchase(
        company_id,
        purchase_id,
        PurchaseFiscalData(
            issued_on=body.issued_on,
            document_class=body.document_class,
            document_type=body.document_type,
            number=body.number,
            control_number=body.control_number,
            seal=body.seal,
            supplier_name=body.supplier_name,
            supplier_id_type=body.supplier_id_type,
            supplier_id=body.supplier_id,
            renta=RentaPurchase(
                body.renta.operation,
                body.renta.classification,
                body.renta.sector,
                body.renta.cost_type,
            ),
        ),
        current.id,
        datetime.now(_TZ).date(),
    )
    out = _purchase_out(view, defaults)
    await audit.record(
        action="RECORD_PURCHASE_FISCAL_DOCUMENT",
        user_id=current.id,
        company_id=company_id,
        branch_id=view.branch_id,
        resource_type="purchase",
        resource_id=str(purchase_id),
        before_state=previous.model_dump(mode="json") if previous else None,
        after_state=out.recorded.model_dump(mode="json") if out.recorded else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return out


@router.get(
    "/{period}",
    response_model=FiscalMonthOut,
    summary="Libros de IVA, anexos del F-07 y resumen de un mes",
    dependencies=_READ,
)
async def get_month(
    period: str,
    company_id: CompanyId,
    cases: UseCases,
    mode: Annotated[str | None, Query(pattern="^(production|test|simulated)$")] = None,
) -> FiscalMonthOut:
    return month_out(await cases.month(company_id, period, mode))
