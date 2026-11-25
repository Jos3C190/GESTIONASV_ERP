"""Emisión y anulación de eventos de retorno en el trabajador DTE (bloque V4d2).

- ``process_fiscal_return``: transmite el retorno pendiente al servicio DTE, guarda su JSON y su PDF,
  concilia sus totales con lo que guardó el ERP y crea el envío al cliente.
- ``process_return_annulment``: transmite la anulación (invalidación tipo 2 del evento) y, al
  aceptarse, deja el retorno anulado, con lo que su saldo vuelve a la factura.

Lanzan ``DteServiceError`` reintentable cuando el servicio no respondió: la tarea arq reintenta con
la misma clave de idempotencia.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.application.audit.audit_service import AuditService
from app.core.config import settings
from app.domain.entities.sales_fiscal_returns import (
    AnnulStatus,
    ReturnStatus,
    ReturnTotals,
    invoice_withholding,
    return_dte_differences,
    return_totals,
)
from app.domain.ports.dte_service import DteService, DteServiceError, InvalidationRequest
from app.domain.ports.object_storage import ObjectStorage
from app.domain.ports.sales_fiscal_repository import FiscalDocument
from app.domain.ports.sales_fiscal_return_repository import FiscalReturn
from app.infrastructure.db.session import session_scope
from app.infrastructure.dte_email import SessionScope, queue_return_email
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.sales_fiscal_repository import SqlAlchemySalesFiscalRepository
from app.infrastructure.repositories.sales_fiscal_return_repository import (
    SqlAlchemySalesFiscalReturnRepository,
)

_MAX_ERROR = 2000
EmailQueued = Callable[[uuid.UUID], Awaitable[None]]


async def _save(scope: SessionScope, item: FiscalReturn, action: str | None = None) -> FiscalReturn:
    async with scope() as session:
        saved = await SqlAlchemySalesFiscalReturnRepository(session).save(item)
        if action:
            await AuditService(SqlAlchemyAuditRepository(session)).record(
                action=action,
                company_id=item.company_id,
                resource_type="sales_fiscal_document",
                resource_id=str(item.document_id),
                after_state={
                    "return_id": str(item.id),
                    "status": item.status.value,
                    "annul_status": item.annul_status.value if item.annul_status else None,
                    "generation_code": str(item.generation_code) if item.generation_code else None,
                    "total": str(item.total),
                    "error_code": item.annul_error_code or item.error_code,
                },
                metadata={"actor": "dte-worker"},
            )
    return saved


async def _invoice(scope: SessionScope, item: FiscalReturn) -> FiscalDocument:
    async with scope() as session:
        invoice = await SqlAlchemySalesFiscalRepository(session).get(
            item.company_id, item.document_id
        )
    assert invoice is not None
    return invoice


async def _register(
    scope: SessionScope, client: DteService, invoice: FiscalDocument, item: FiscalReturn
) -> str:
    # Import tardío: dte_worker importa este módulo para sus tareas.
    from app.infrastructure.dte_worker import _credentials, _enabled_types

    nit = str(invoice.issuer_snapshot["nit"])
    await client.register_issuer(
        nit,
        name=str(invoice.issuer_snapshot["legalName"]),
        mode=invoice.mode,
        document_types=await _enabled_types(scope, invoice.company_id),
        credentials=await _credentials(scope, invoice),
        responsible=item.annul_responsible,
    )
    return nit


async def _store(
    storage: ObjectStorage | None, item: FiscalReturn, event: dict[str, Any], pdf: bytes
) -> tuple[str | None, str | None]:
    if storage is None:
        return None, None
    base = f"companies/{item.company_id}/sales-fiscal/{item.document_id}/returns/{item.id}"
    metadata = {"fiscal-return-id": str(item.id), "document-type": "18"}
    with tempfile.TemporaryDirectory() as folder:
        json_path = Path(folder) / "evento.json"
        json_path.write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
        pdf_path = Path(folder) / "evento.pdf"
        pdf_path.write_bytes(pdf)
        await storage.upload_from(
            f"{base}.json", json_path, content_type="application/json", metadata=metadata
        )
        await storage.upload_from(
            f"{base}.pdf", pdf_path, content_type="application/pdf", metadata=metadata
        )
    return f"{base}.json", f"{base}.pdf"


def _totals(item: FiscalReturn, invoice: FiscalDocument) -> ReturnTotals:
    return return_totals(item.lines, withholding=invoice_withholding(invoice.dte_json or {}))


async def process_fiscal_return(
    return_id: uuid.UUID,
    *,
    client: DteService,
    storage: ObjectStorage | None,
    scope: SessionScope = session_scope,
    max_attempts: int | None = None,
    on_email: EmailQueued | None = None,
) -> FiscalReturn | None:
    """Emite un retorno pendiente. Devuelve el retorno guardado, o ``None`` si no le tocaba."""

    limit = max_attempts or settings.DTE_MAX_ATTEMPTS
    async with scope() as session:
        item = await SqlAlchemySalesFiscalReturnRepository(session).claim(return_id)
    if item is None:
        return None
    if item.attempts > limit:
        item.status = ReturnStatus.FAILED
        item.error_code = item.error_code or "dte_attempts_exhausted"
        item.error_message = f"Se agotaron los {limit} intentos. {item.error_message or ''}".strip()
        return await _save(scope, item, "FISCAL_RETURN_FAILED")
    invoice = await _invoice(scope, item)
    try:
        nit = await _register(scope, client, invoice, item)
        result = await client.issue_return(
            nit,
            str(invoice.generation_code).upper(),
            idempotency_key=item.idempotency_key,
            body=item.request_payload,
        )
        if result.generation_code:
            item.generation_code = uuid.UUID(result.generation_code)
        if not result.accepted:
            item.status = ReturnStatus.REJECTED
            item.error_code = "dte_return_rejected"
            item.error_message = (result.message or "Hacienda rechazó el evento de retorno.")[
                :_MAX_ERROR
            ]
            return await _save(scope, item, "FISCAL_RETURN_REJECTED")
        code = str(item.generation_code).upper()
        event = await client.event_json(nit, code)
        pdf = await client.invalidation_pdf(nit, code)
    except DteServiceError as error:
        item.error_code = error.code[:80]
        item.error_message = error.message[:_MAX_ERROR]
        if error.transient:
            await _save(scope, item)
            raise
        item.status = ReturnStatus.FAILED
        return await _save(scope, item, "FISCAL_RETURN_FAILED")
    item.json_object_key, item.pdf_object_key = await _store(storage, item, event, pdf)
    item.dte_json = event
    item.seal = result.seal
    item.status = ReturnStatus.SIMULATED if result.simulated else ReturnStatus.ISSUED
    item.issued_at = datetime.now(UTC)
    item.error_code = None
    item.error_message = None
    differences = return_dte_differences(event, _totals(item, invoice))
    if differences:
        item.error_code = "dte_totals_mismatch"
        item.error_message = "; ".join(differences)[:_MAX_ERROR]
    saved = await _save(scope, item, "FISCAL_RETURN_ISSUED")
    email_id = await queue_return_email(scope, invoice, saved.id)
    if email_id is not None and on_email is not None:
        await on_email(email_id)
    return saved


async def process_return_annulment(
    return_id: uuid.UUID,
    *,
    client: DteService,
    scope: SessionScope = session_scope,
    max_attempts: int | None = None,
) -> FiscalReturn | None:
    """Anula un retorno (invalidación tipo 2 del evento). ``None`` si no le tocaba."""

    limit = max_attempts or settings.DTE_MAX_ATTEMPTS
    async with scope() as session:
        item = await SqlAlchemySalesFiscalReturnRepository(session).claim_annulment(return_id)
    if item is None:
        return None
    if item.annul_attempts > limit or item.generation_code is None:
        item.annul_status = AnnulStatus.FAILED
        item.annul_error_code = item.annul_error_code or "dte_attempts_exhausted"
        item.annul_error_message = (
            f"No se pudo anular el retorno. {item.annul_error_message or ''}".strip()
        )
        return await _save(scope, item, "FISCAL_RETURN_ANNUL_FAILED")
    assert item.annul_responsible is not None
    assert item.annul_requester is not None
    invoice = await _invoice(scope, item)
    try:
        nit = await _register(scope, client, invoice, item)
        result = await client.annul_return(
            nit,
            str(item.generation_code).upper(),
            idempotency_key=str(item.annul_idempotency_key),
            request=InvalidationRequest(
                kind=2,
                reason=item.reason[:200],
                responsible=item.annul_responsible,
                requester=item.annul_requester,
            ),
        )
    except DteServiceError as error:
        item.annul_error_code = error.code[:80]
        item.annul_error_message = error.message[:_MAX_ERROR]
        if error.transient:
            await _save(scope, item)
            raise
        item.annul_status = AnnulStatus.FAILED
        return await _save(scope, item, "FISCAL_RETURN_ANNUL_FAILED")
    if result.generation_code:
        item.annul_generation_code = uuid.UUID(result.generation_code)
    if not result.accepted:
        item.annul_status = AnnulStatus.REJECTED
        item.annul_error_code = "dte_return_invalidation_rejected"
        item.annul_error_message = (result.message or "Hacienda rechazó la anulación.")[:_MAX_ERROR]
        return await _save(scope, item, "FISCAL_RETURN_ANNUL_REJECTED")
    item.annul_status = AnnulStatus.ACCEPTED
    item.annul_seal = result.seal
    item.annul_error_code = None
    item.annul_error_message = None
    item.annulled_at = datetime.now(UTC)
    item.status = ReturnStatus.INVALIDATED
    return await _save(scope, item, "FISCAL_RETURN_ANNULLED")
