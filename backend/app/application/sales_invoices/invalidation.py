"""Invalidar o corregir un documento fiscal (bloque V4b).

- ``invalidate``: rescinde la operación (tipo 2). Si se pide desde el pedido, éste se cancela al
  aceptarse la invalidación.
- ``correct``: crea el documento de reemplazo con los datos actuales y deja pendiente la
  invalidación del original (tipo 1); el trabajador la envía cuando el reemplazo queda sellado.

Las solicitudes quedan en ``sales_fiscal_invalidations`` y el trabajador DTE las procesa con su
clave de idempotencia. Firma el responsable fiscal de la empresa (el mismo de la contingencia).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.sales_invoices.use_cases import SalesInvoiceUseCases
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_invalidation import (
    FiscalInvalidation,
    InvalidationKind,
    require_correctable,
    require_invalidatable,
    validate_reason,
    validate_requester,
)
from app.domain.entities.sales_fiscal_notes import (
    NOTE_TYPES,
    VIGENT_STATUSES,
    require_without_vigent_notes,
)
from app.domain.entities.sales_order import require_cancellable
from app.domain.ports.contingency_repository import ContingencyResponsibleRepository
from app.domain.ports.dte_service import DteService, DteServiceError, InvalidationWindow
from app.domain.ports.sales_fiscal_invalidation_repository import (
    SalesFiscalInvalidationRepository,
)
from app.domain.ports.sales_fiscal_repository import FiscalDocument, SalesFiscalRepository
from app.domain.ports.sales_order_repository import SalesOrderRepository

CORRECTION_REASON = "Error en la información del documento; se reemplaza por uno corregido."


@dataclass(frozen=True, slots=True)
class Requester:
    name: str
    document_type: str
    document_number: str


@dataclass(frozen=True, slots=True)
class Correction:
    replacement: FiscalDocument
    invalidation: FiscalInvalidation


class FiscalInvalidationUseCases:
    def __init__(
        self,
        documents: SalesFiscalRepository,
        invalidations: SalesFiscalInvalidationRepository,
        invoices: SalesInvoiceUseCases,
        responsibles: ContingencyResponsibleRepository,
        orders: SalesOrderRepository,
        dte: DteService | None,
    ) -> None:
        self._documents = documents
        self._invalidations = invalidations
        self._invoices = invoices
        self._responsibles = responsibles
        self._orders = orders
        self._dte = dte

    async def _document(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, lock: bool
    ) -> FiscalDocument:
        document = await self._documents.get(company_id, document_id, lock=lock)
        if document is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        return document

    async def _responsible(self, company_id: uuid.UUID) -> ContingencyResponsible:
        responsible = await self._responsibles.get(company_id)
        if responsible is None:
            raise BusinessRuleError(
                "Registra al responsable fiscal de la empresa (Ventas → Contingencia) antes de "
                "invalidar.",
                code="sales_invoice_responsible_missing",
            )
        return responsible

    async def window(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> InvalidationWindow | None:
        """Plazo para invalidar según el servicio; ``None`` si no aplica o no responde."""

        document = await self._document(company_id, document_id, lock=False)
        if self._dte is None or document.generation_code is None:
            return None
        try:
            return await self._dte.invalidation_window(
                str(document.issuer_snapshot["nit"]), str(document.generation_code).upper()
            )
        except DteServiceError:
            return None

    async def _require_without_notes(self, document: FiscalDocument) -> None:
        notes = await self._documents.notes_for(document.company_id, document.id)
        require_without_vigent_notes(sum(1 for n in notes if n.status in VIGENT_STATUSES))

    async def _require_in_time(self, document: FiscalDocument) -> None:
        window = await self.window(document.company_id, document.id)
        if window is not None and window.expired:
            raise BusinessRuleError(
                f"El plazo para invalidar este documento venció el "
                f"{window.deadline.strftime('%d/%m/%Y')}. Hacienda ya no lo acepta.",
                code="sales_invoice_invalidation_expired",
            )

    async def history(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalInvalidation]:
        await self._document(company_id, document_id, lock=False)
        return await self._invalidations.for_document(company_id, document_id)

    async def invalidate(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        requester: Requester,
        cancel_order: bool,
    ) -> FiscalInvalidation:
        document = await self._document(company_id, document_id, lock=True)
        pending = await self._invalidations.pending_for_document(company_id, document_id)
        require_invalidatable(
            document.status,
            superseded=document.superseded_by_id is not None,
            pending_invalidation=pending is not None,
        )
        await self._require_without_notes(document)
        if cancel_order and document.document_type in NOTE_TYPES:
            raise BusinessRuleError(
                "Anular una nota no cancela el pedido: el pedido sigue con su crédito fiscal.",
                code="sales_note_cancel_order_invalid",
            )
        text = validate_reason(reason)
        person = validate_requester(
            requester.name, requester.document_type, requester.document_number
        )
        responsible = await self._responsible(company_id)
        if cancel_order:
            order = await self._orders.get(company_id, document.sale_id, lock=True)
            if order is None:
                raise NotFoundError("El pedido no existe.", code="sales_order_not_found")
            require_cancellable(order.status, order.delivered_any)
        await self._require_in_time(document)
        invalidation_id = uuid.uuid4()
        return await self._invalidations.create(
            FiscalInvalidation(
                id=invalidation_id,
                company_id=company_id,
                document_id=document_id,
                kind=InvalidationKind.RESCISSION,
                reason=text,
                requester=person,
                requested_by_id=actor_id,
                idempotency_key=f"erp-inv-{invalidation_id}",
                responsible=responsible,
                cancel_order=cancel_order,
            )
        )

    async def correct(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        requester: Requester,
    ) -> Correction:
        original = await self._document(company_id, document_id, lock=True)
        pending = await self._invalidations.pending_for_document(company_id, document_id)
        require_correctable(
            original.status,
            original.document_type,
            superseded=original.superseded_by_id is not None,
            pending_invalidation=pending is not None,
        )
        await self._require_without_notes(original)
        person = validate_requester(
            requester.name, requester.document_type, requester.document_number
        )
        responsible = await self._responsible(company_id)
        await self._require_in_time(original)
        replacement = await self._invoices.prepare_replacement(original, actor_id)
        # El original deja de ser el documento activo del pedido antes de crear el reemplazo.
        original.superseded_by_id = replacement.id
        await self._documents.save(original)
        created = await self._documents.create(replacement)
        invalidation_id = uuid.uuid4()
        invalidation = await self._invalidations.create(
            FiscalInvalidation(
                id=invalidation_id,
                company_id=company_id,
                document_id=document_id,
                kind=InvalidationKind.CORRECTION,
                reason=CORRECTION_REASON,
                requester=person,
                requested_by_id=actor_id,
                idempotency_key=f"erp-inv-{invalidation_id}",
                responsible=responsible,
                replacement_document_id=created.id,
            )
        )
        return Correction(replacement=created, invalidation=invalidation)
