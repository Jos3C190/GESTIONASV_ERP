"""Evento de retorno sobre una factura sellada (bloque V4d2).

El retorno documenta los bienes que el cliente devuelve de una factura: reduce la venta y el
débito fiscal del emisor (Normativa DTE 2.0, regla 13.3). Se registra en ``pending`` y el
trabajador DTE lo transmite; al aceptarse se envía al cliente con su JSON y su PDF.

Es solo fiscal, como las notas: no mueve inventario ni reintegra dinero (eso llega con las
devoluciones de V8). Una factura con retornos vigentes no se anula ni se corrige; el retorno se
anula con el evento de invalidación tipo 2, que pide el responsable fiscal y quién lo solicita.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.application.period_guard import local_day, require_open
from app.application.sales_invoices.notes import ccf_date, today_sv
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_invalidation import validate_requester
from app.domain.entities.sales_fiscal_notes import LineBalance
from app.domain.entities.sales_fiscal_returns import (
    AnnulStatus,
    ReturnLineRequest,
    ReturnStatus,
    build_return_request,
    invoice_lines,
    invoice_withholding,
    plan_return,
    require_reason,
    require_return_in_time,
    require_returnable,
    return_balances,
    return_deadline,
    return_totals,
)
from app.domain.ports.contingency_repository import ContingencyResponsibleRepository
from app.domain.ports.fiscal_period_repository import ClosedPeriods
from app.domain.ports.sales_fiscal_invalidation_repository import (
    SalesFiscalInvalidationRepository,
)
from app.domain.ports.sales_fiscal_repository import FiscalDocument, SalesFiscalRepository
from app.domain.ports.sales_fiscal_return_repository import (
    FiscalReturn,
    ReturnLineRecord,
    SalesFiscalReturnRepository,
)

#: Los retornos que se pueden anular: vigentes, sin una anulación en curso o aceptada.
_ANNULLABLE = (ReturnStatus.ISSUED, ReturnStatus.SIMULATED)


@dataclass(frozen=True, slots=True)
class ReturnsOverview:
    invoice: FiscalDocument
    balances: tuple[LineBalance, ...]
    deadline: date | None
    """Último día para registrar retornos (3 meses, o 2 años con medicamentos)."""
    withholding: bool
    blocker: str | None
    """Por qué no se puede registrar un retorno ahora (o ``None``)."""
    returns: list[FiscalReturn]


def invoice_activity(invoice: FiscalDocument) -> str | None:
    """Actividad económica del emisor tal como quedó en la factura sellada."""

    issuer = (invoice.dte_json or {}).get("emisor") or {}
    code = issuer.get("codActividad")
    return str(code) if code else None


class SalesFiscalReturnUseCases:
    def __init__(
        self,
        documents: SalesFiscalRepository,
        returns: SalesFiscalReturnRepository,
        invalidations: SalesFiscalInvalidationRepository,
        responsibles: ContingencyResponsibleRepository,
        periods: ClosedPeriods | None = None,
    ) -> None:
        self._documents = documents
        self._returns = returns
        self._periods = periods
        self._invalidations = invalidations
        self._responsibles = responsibles

    async def invoice(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, lock: bool = False
    ) -> FiscalDocument:
        document = await self._documents.get(company_id, document_id, lock=lock)
        if document is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        return document

    async def get(self, company_id: uuid.UUID, return_id: uuid.UUID) -> FiscalReturn:
        item = await self._returns.get(company_id, return_id)
        if item is None:
            raise NotFoundError("El evento de retorno no existe.", code="sales_return_not_found")
        return item

    async def _require_returnable(self, invoice: FiscalDocument) -> date:
        require_returnable(
            invoice.document_type, invoice.status, superseded=invoice.superseded_by_id is not None
        )
        if await self._invalidations.pending_for_document(invoice.company_id, invoice.id):
            raise BusinessRuleError(
                "La factura tiene una anulación en curso: espera su resultado.",
                code="sales_return_invalidation_pending",
            )
        issued = ccf_date(invoice)
        if issued is None:
            raise BusinessRuleError(
                "La factura no tiene su JSON sellado; espera a que termine de emitirse.",
                code="sales_return_invoice_not_sealed",
            )
        return issued

    async def _balances(self, invoice: FiscalDocument) -> tuple[LineBalance, ...]:
        prior = await self._returns.prior_lines(invoice.company_id, invoice.id)
        return return_balances(invoice_lines(invoice.dte_json or {}), prior)

    async def overview(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, today: date | None = None
    ) -> ReturnsOverview:
        invoice = await self.invoice(company_id, document_id)
        issued = ccf_date(invoice)
        blocker: str | None = None
        try:
            issued = await self._require_returnable(invoice)
            require_return_in_time(issued, invoice_activity(invoice), today or today_sv())
        except BusinessRuleError as error:
            blocker = error.message
        return ReturnsOverview(
            invoice=invoice,
            balances=await self._balances(invoice) if invoice.dte_json else (),
            deadline=return_deadline(issued, invoice_activity(invoice)) if issued else None,
            withholding=invoice_withholding(invoice.dte_json or {}),
            blocker=blocker,
            returns=await self._returns.for_document(company_id, document_id),
        )

    async def register(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        lines: list[ReturnLineRequest],
        today: date | None = None,
    ) -> FiscalReturn:
        # Bloquear la factura serializa dos retornos sobre el mismo saldo y su anulación.
        invoice = await self.invoice(company_id, document_id, lock=True)
        issued = await self._require_returnable(invoice)
        require_return_in_time(issued, invoice_activity(invoice), today or today_sv())
        text = require_reason(reason)
        planned = plan_return(await self._balances(invoice), lines)
        totals = return_totals(planned, withholding=invoice_withholding(invoice.dte_json or {}))
        return_id = uuid.uuid4()
        return await self._returns.create(
            FiscalReturn(
                id=return_id,
                company_id=company_id,
                document_id=invoice.id,
                reason=text,
                status=ReturnStatus.PENDING,
                idempotency_key=f"erp-ret-{return_id}",
                request_payload=build_return_request(planned),
                total=totals.total,
                created_by_id=actor_id,
                lines=tuple(
                    ReturnLineRecord(
                        line_number=line.line_number,
                        invoice_line_number=line.invoice_line_number,
                        nature=line.nature,
                        description=line.description,
                        quantity=line.quantity,
                        amount=line.amount,
                        vat=line.vat,
                    )
                    for line in planned
                ),
            )
        )

    async def annul(
        self,
        company_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        requester: ContingencyResponsible,
    ) -> FiscalReturn:
        item = await self._returns.get(company_id, return_id, lock=True)
        if item is None:
            raise NotFoundError("El evento de retorno no existe.", code="sales_return_not_found")
        await require_open(self._periods, company_id, local_day(item.issued_at))
        if item.status not in _ANNULLABLE or item.annul_status in (
            AnnulStatus.PENDING,
            AnnulStatus.ACCEPTED,
        ):
            raise BusinessRuleError(
                "Solo se anula un retorno vigente sin una anulación en curso.",
                code="sales_return_not_annullable",
            )
        person = validate_requester(
            requester.name, requester.document_type, requester.document_number
        )
        responsible = await self._responsibles.get(company_id)
        if responsible is None:
            raise BusinessRuleError(
                "Registra al responsable fiscal de la empresa (Ventas → Contingencia) antes de "
                "anular un retorno.",
                code="sales_invoice_responsible_missing",
            )
        item.annul_status = AnnulStatus.PENDING
        item.annul_idempotency_key = f"erp-ret-anul-{uuid.uuid4()}"
        item.annul_requester = person
        item.annul_responsible = responsible
        item.annul_requested_by_id = actor_id
        item.annul_requested_at = datetime.now(UTC)
        item.annul_attempts = 0
        item.annul_error_code = None
        item.annul_error_message = None
        return await self._returns.save(item)
