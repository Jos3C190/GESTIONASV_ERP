"""Cuentas por cobrar y recibos de cobro (bloque V5a).

Ver la cartera, los estados de cuenta y los recibos pide ``sales_receivables:read``; registrar,
aplicar saldo a favor, anular recibos y registrar comprobantes de retención pide
``sales_receivables:collect``. Toda escritura queda en la bitácora.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_sales_receivable_use_cases,
    require_permission,
)
from app.api.v1.schemas.sales_receivable import (
    AccountDocumentOut,
    AccountOut,
    AnnulReceiptIn,
    ApplicationOut,
    ApplyIn,
    CertificateIn,
    CertificateOut,
    CustomerRefOut,
    CustomerSummaryOut,
    PaymentIn,
    ReceiptIn,
    ReceiptOut,
)
from app.application.audit.audit_service import AuditService
from app.application.sales_receivables.use_cases import SalesReceivableUseCases
from app.domain.entities.sales_receivables import (
    ApplicationRequest,
    PaymentLine,
    PaymentMethod,
    receipt_code,
)
from app.domain.ports.sales_receivable_repository import (
    AccountDocument,
    Certificate,
    CustomerRef,
    Receipt,
)
from app.infrastructure.sales_receipt_pdf import render_receipt_pdf

router = APIRouter(tags=["sales-receivables"])

UseCases = Annotated[SalesReceivableUseCases, Depends(get_sales_receivable_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_receivables:read"))]
_COLLECT = [Depends(require_permission("sales_receivables:collect"))]
_TZ = ZoneInfo("America/El_Salvador")


def _today() -> datetime:
    return datetime.now(_TZ)


def _customer(customer: CustomerRef) -> CustomerRefOut:
    return CustomerRefOut(
        id=customer.id,
        code=customer.code,
        name=customer.name,
        credit_days=customer.credit_days,
        credit_limit=customer.credit_limit,
    )


def document_out(item: AccountDocument) -> AccountDocumentOut:
    receivable = item.receivable
    today = _today().date()
    certificate = item.certificate
    return AccountDocumentOut(
        id=uuid.UUID(str(receivable.id)),
        document_type=receivable.document_type,
        control_number=receivable.control_number,
        issued_on=receivable.issued_on,
        due_on=receivable.due_on,
        payable=receivable.payable,
        credited=receivable.credited,
        applied=receivable.applied,
        balance=receivable.balance,
        bucket=receivable.bucket(today).value,
        overdue=receivable.overdue(today),
        invalidated=receivable.invalidated,
        sale_id=item.sale_id,
        sale_code=item.sale_code,
        customer_id=item.customer_id,
        withholding=item.withholding,
        certificate=(
            CertificateOut(
                certificate_number=certificate.certificate_number,
                issued_on=certificate.issued_on,
                amount=certificate.amount,
            )
            if certificate
            else None
        ),
    )


def receipt_out(receipt: Receipt) -> ReceiptOut:
    return ReceiptOut(
        id=receipt.id,
        code=receipt_code(receipt.number),
        number=receipt.number,
        branch_id=receipt.branch_id,
        customer_id=receipt.customer_id,
        received_on=receipt.received_on,
        total=receipt.total,
        unapplied=receipt.unapplied,
        notes=receipt.notes,
        status=receipt.status.value,
        payments=[
            PaymentIn(method=line.method.value, amount=line.amount, reference=line.reference)
            for line in receipt.payments
        ],
        applications=[ApplicationOut(**item.__dict__) for item in receipt.applications],
        annul_reason=receipt.annul_reason,
        annulled_at=receipt.annulled_at,
        created_at=receipt.created_at,
    )


def _state(receipt: Receipt) -> dict[str, object]:
    return {
        "code": receipt_code(receipt.number),
        "customer_id": str(receipt.customer_id),
        "status": receipt.status.value,
        "total": str(receipt.total),
        "unapplied": str(receipt.unapplied),
        "payments": [
            {"method": line.method.value, "amount": str(line.amount), "reference": line.reference}
            for line in receipt.payments
        ],
        "applications": [
            {"document_id": str(item.document_id), "amount": str(item.amount)}
            for item in receipt.applications
        ],
        "annul_reason": receipt.annul_reason,
    }


async def _audit(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    resource_type: str,
    resource_id: str,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        branch_id=branch_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "/sales/receivables",
    response_model=list[CustomerSummaryOut],
    summary="Cartera: clientes con saldo, vencido, saldo a favor y antigüedad",
    dependencies=_READ,
)
async def portfolio(company_id: CompanyId, cases: UseCases) -> list[CustomerSummaryOut]:
    return [
        CustomerSummaryOut(
            customer=_customer(item.customer),
            balance=item.balance,
            overdue=item.overdue,
            credit=item.credit,
            aging={bucket.value: value for bucket, value in item.aging.items()},
            oldest_due=item.oldest_due,
        )
        for item in await cases.portfolio(company_id, _today().date())
    ]


@router.get(
    "/sales/receivables/customers/{customer_id}",
    response_model=AccountOut,
    summary="Estado de cuenta de un cliente",
    dependencies=_READ,
)
async def account(customer_id: uuid.UUID, company_id: CompanyId, cases: UseCases) -> AccountOut:
    found = await cases.account(company_id, customer_id, _today().date())
    return AccountOut(
        customer=_customer(found.customer),
        balance=found.balance,
        overdue=found.overdue,
        credit=found.credit,
        aging={bucket.value: value for bucket, value in found.aging.items()},
        documents=[document_out(item) for item in found.documents],
        receipts=[receipt_out(item) for item in found.receipts],
    )


@router.get(
    "/sales/receivables/documents/{document_id}",
    response_model=AccountDocumentOut,
    summary="Saldo por cobrar de un documento fiscal",
    dependencies=_READ,
)
async def receivable_document(
    document_id: uuid.UUID, company_id: CompanyId, cases: UseCases
) -> AccountDocumentOut:
    return document_out(await cases.document(company_id, document_id))


@router.put(
    "/sales/receivables/documents/{document_id}/withholding-certificate",
    response_model=AccountDocumentOut,
    summary="Registrar el comprobante de retención que entregó el cliente",
    dependencies=_COLLECT,
)
async def record_certificate(
    document_id: uuid.UUID,
    body: CertificateIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> AccountDocumentOut:
    before = await cases.document(company_id, document_id)
    after = await cases.record_certificate(
        company_id,
        document_id,
        Certificate(body.certificate_number, body.issued_on, body.amount),
        current.id,
        _today().date(),
    )
    out = document_out(after)
    await _audit(
        audit,
        request,
        action="RECORD_WITHHOLDING_CERTIFICATE",
        actor=current.id,
        company_id=company_id,
        branch_id=after.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document_id),
        before=(
            document_out(before).certificate.model_dump(mode="json")  # type: ignore[union-attr]
            if before.certificate
            else None
        ),
        after=out.certificate.model_dump(mode="json") if out.certificate else None,
    )
    return out


@router.post(
    "/sales/receipts",
    response_model=ReceiptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un recibo de cobro (idempotente por llave)",
    dependencies=_COLLECT,
)
async def register_receipt(
    body: ReceiptIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ReceiptOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    receipt, created = await cases.register(
        company_id,
        branch_id=body.branch_id,
        customer_id=body.customer_id,
        received_on=body.received_on,
        payments=[
            PaymentLine(PaymentMethod(item.method), item.amount, item.reference)
            for item in body.payments
        ],
        applications=[
            ApplicationRequest(item.document_id, item.amount) for item in body.applications
        ],
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        actor_id=current.id,
        today=_today().date(),
    )
    if created:
        await _audit(
            audit,
            request,
            action="REGISTER_SALES_RECEIPT",
            actor=current.id,
            company_id=company_id,
            branch_id=receipt.branch_id,
            resource_type="sales_receipt",
            resource_id=str(receipt.id),
            before=None,
            after=_state(receipt),
        )
    else:
        response.status_code = status.HTTP_200_OK
    return receipt_out(receipt)


@router.get(
    "/sales/receipts/{receipt_id}",
    response_model=ReceiptOut,
    summary="Recibo de cobro",
    dependencies=_READ,
)
async def get_receipt(receipt_id: uuid.UUID, company_id: CompanyId, cases: UseCases) -> ReceiptOut:
    return receipt_out(await cases.receipt(company_id, receipt_id))


@router.get(
    "/sales/receipts/{receipt_id}/pdf",
    summary="Recibo de cobro en PDF",
    dependencies=_READ,
)
async def receipt_pdf(receipt_id: uuid.UUID, company_id: CompanyId, cases: UseCases) -> Response:
    receipt, customer, issuer = await cases.printable(company_id, receipt_id)
    return Response(
        content=render_receipt_pdf(receipt, customer, issuer),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{receipt_code(receipt.number)}.pdf"'},
    )


@router.post(
    "/sales/receipts/{receipt_id}/apply",
    response_model=ReceiptOut,
    summary="Aplicar el saldo a favor de un recibo a otros documentos",
    dependencies=_COLLECT,
)
async def apply_credit(
    receipt_id: uuid.UUID,
    body: ApplyIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ReceiptOut:
    before = await cases.receipt(company_id, receipt_id)
    after = await cases.apply_credit(
        company_id,
        receipt_id,
        [ApplicationRequest(item.document_id, item.amount) for item in body.applications],
        current.id,
        _today().date(),
    )
    await _audit(
        audit,
        request,
        action="APPLY_SALES_RECEIPT_CREDIT",
        actor=current.id,
        company_id=company_id,
        branch_id=after.branch_id,
        resource_type="sales_receipt",
        resource_id=str(receipt_id),
        before=_state(before),
        after=_state(after),
    )
    return receipt_out(after)


@router.post(
    "/sales/receipts/{receipt_id}/annul",
    response_model=ReceiptOut,
    summary="Anular un recibo de cobro con motivo; restituye los saldos",
    dependencies=_COLLECT,
)
async def annul_receipt(
    receipt_id: uuid.UUID,
    body: AnnulReceiptIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ReceiptOut:
    before, after = await cases.annul(company_id, receipt_id, body.reason, current.id)
    await _audit(
        audit,
        request,
        action="ANNUL_SALES_RECEIPT",
        actor=current.id,
        company_id=company_id,
        branch_id=after.branch_id,
        resource_type="sales_receipt",
        resource_id=str(receipt_id),
        before=_state(before),
        after=_state(after),
    )
    return receipt_out(after)
