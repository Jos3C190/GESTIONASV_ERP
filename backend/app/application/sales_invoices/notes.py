"""Notas de crédito y de débito sobre un crédito fiscal sellado (bloque V4c).

La nota pertenece al mismo pedido y al mismo punto de venta que el CCF, lleva el emisor actual y
hereda la clasificación de renta del CCF. Queda en ``pending`` y el trabajador DTE la emite como
cualquier documento; al emitirse se envía por correo al cliente.

Las notas son solo fiscales: no mueven inventario ni reintegran dinero (eso llega con las
devoluciones de V8).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.application.sales_invoices.use_cases import SalesInvoiceUseCases
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus, fiscal_mode
from app.domain.entities.sales_fiscal_notes import (
    CREDIT_NOTE,
    DEBIT_NOTE,
    NOTE_NAMES,
    VIGENT_STATUSES,
    CreditLineRequest,
    DebitChargeRequest,
    LineBalance,
    NoteLine,
    NoteLineKind,
    PriorNoteLine,
    build_note_request,
    ccf_adjustments,
    ccf_lines,
    line_balances,
    note_deadline,
    note_totals,
    plan_credit_note,
    plan_debit_note,
    require_note_in_time,
    require_noteable,
    require_reason,
)
from app.domain.ports.sales_fiscal_invalidation_repository import (
    SalesFiscalInvalidationRepository,
)
from app.domain.ports.sales_fiscal_repository import (
    FiscalDocument,
    FiscalNoteLine,
    SalesFiscalRepository,
)

_ZONE = ZoneInfo("America/El_Salvador")


def today_sv() -> date:
    return datetime.now(_ZONE).date()


def ccf_date(ccf: FiscalDocument) -> date | None:
    """Fecha de emisión del CCF tal como la tiene Hacienda (``identificacion.fecEmi``)."""

    issued = ((ccf.dte_json or {}).get("identificacion") or {}).get("fecEmi")
    try:
        return date.fromisoformat(str(issued)) if issued else None
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class NotesOverview:
    ccf: FiscalDocument
    balances: tuple[LineBalance, ...]
    deadline: date | None
    """Último día para emitir notas: tres meses desde la fecha del CCF."""
    withholding: bool
    perception: bool
    credit_blocker: str | None
    debit_blocker: str | None
    notes: list[FiscalDocument]
    lines: dict[uuid.UUID, list[FiscalNoteLine]]


class SalesFiscalNoteUseCases:
    def __init__(
        self,
        documents: SalesFiscalRepository,
        invalidations: SalesFiscalInvalidationRepository,
        invoices: SalesInvoiceUseCases,
    ) -> None:
        self._documents = documents
        self._invalidations = invalidations
        self._invoices = invoices

    async def _ccf(self, company_id: uuid.UUID, ccf_id: uuid.UUID, *, lock: bool) -> FiscalDocument:
        ccf = await self._documents.get(company_id, ccf_id, lock=lock)
        if ccf is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        return ccf

    async def ccf(self, company_id: uuid.UUID, ccf_id: uuid.UUID) -> FiscalDocument:
        return await self._ccf(company_id, ccf_id, lock=False)

    async def _require_noteable(self, ccf: FiscalDocument) -> date:
        pending = await self._invalidations.pending_for_document(ccf.company_id, ccf.id)
        require_noteable(
            ccf.document_type,
            ccf.status,
            superseded=ccf.superseded_by_id is not None,
            invalidation_pending=pending is not None,
        )
        issued = ccf_date(ccf)
        if issued is None:
            raise BusinessRuleError(
                "El crédito fiscal no tiene su JSON sellado; espera a que termine de emitirse.",
                code="sales_note_ccf_not_sealed",
            )
        return issued

    async def _require_enabled(self, company_id: uuid.UUID, note_type: str) -> None:
        if not await self._invoices.enabled(company_id, note_type):
            raise BusinessRuleError(
                f"La empresa no tiene habilitada la {NOTE_NAMES[note_type]} para emitir "
                "(Configuración fiscal → Documentos).",
                code="sales_note_document_disabled",
            )

    async def _prior(self, ccf: FiscalDocument) -> list[PriorNoteLine]:
        """Las líneas de las notas de crédito vigentes del CCF: lo que ya se acreditó."""

        notes = [
            n
            for n in await self._documents.notes_for(ccf.company_id, ccf.id)
            if n.document_type == CREDIT_NOTE and n.status in VIGENT_STATUSES
        ]
        lines = await self._documents.note_lines(ccf.company_id, [n.id for n in notes])
        return [
            PriorNoteLine(
                ccf_line_number=line.ccf_line_number,
                kind=NoteLineKind(line.kind),
                quantity=line.quantity,
                amount=line.amount,
            )
            for note_lines in lines.values()
            for line in note_lines
            if line.ccf_line_number is not None
        ]

    async def overview(
        self, company_id: uuid.UUID, ccf_id: uuid.UUID, *, today: date | None = None
    ) -> NotesOverview:
        ccf = await self._ccf(company_id, ccf_id, lock=False)
        notes = await self._documents.notes_for(company_id, ccf_id)
        lines = await self._documents.note_lines(company_id, [n.id for n in notes])
        issued = ccf_date(ccf)
        credit_blocker: str | None = None
        debit_blocker: str | None = None
        try:
            await self._require_noteable(ccf)
        except BusinessRuleError as error:
            credit_blocker = debit_blocker = error.message
        if credit_blocker is None and issued is not None:
            try:
                require_note_in_time(issued, today or today_sv())
            except BusinessRuleError as error:
                credit_blocker = debit_blocker = error.message
        for note_type in (CREDIT_NOTE, DEBIT_NOTE):
            if (credit_blocker if note_type == CREDIT_NOTE else debit_blocker) is not None:
                continue
            try:
                await self._require_enabled(company_id, note_type)
            except BusinessRuleError as error:
                if note_type == CREDIT_NOTE:
                    credit_blocker = error.message
                else:
                    debit_blocker = error.message
        withholding, perception = ccf_adjustments(ccf.dte_json or {})
        return NotesOverview(
            ccf=ccf,
            balances=line_balances(ccf_lines(ccf.dte_json or {}), await self._prior(ccf)),
            deadline=note_deadline(issued) if issued else None,
            withholding=withholding,
            perception=perception,
            credit_blocker=credit_blocker,
            debit_blocker=debit_blocker,
            notes=notes,
            lines=lines,
        )

    async def _create(
        self,
        ccf: FiscalDocument,
        issued: date,
        note_type: str,
        planned: tuple[NoteLine, ...],
        reason: str,
        actor_id: uuid.UUID,
    ) -> FiscalDocument:
        order = await self._invoices.order(ccf.company_id, ccf.sale_id)
        issuer, establishment, point, mode = await self._invoices.issuer_for(
            order, ccf.point_of_sale_id
        )
        withholding, perception = ccf_adjustments(ccf.dte_json or {})
        totals = note_totals(planned, withholding=withholding, perception=perception)
        assert ccf.generation_code is not None
        body = build_note_request(
            issuer.to_service(),
            ccf.dte_json or {},
            str(ccf.generation_code),
            issued,
            planned,
            reason,
        )
        note_id = uuid.uuid4()
        note = FiscalDocument(
            id=note_id,
            company_id=ccf.company_id,
            branch_id=ccf.branch_id,
            sale_id=ccf.sale_id,
            establishment_id=establishment.id,
            point_of_sale_id=point.id,
            document_type=note_type,
            mode=fiscal_mode(mode).value,
            status=FiscalDocumentStatus.PENDING,
            idempotency_key=f"erp-{note_id}",
            total=totals.total,
            issuer_snapshot=issuer.record(),
            request_payload=body,
            created_by_id=actor_id,
            renta_operation_type=ccf.renta_operation_type,
            renta_income_type=ccf.renta_income_type,
            related_document_id=ccf.id,
            note_reason=reason,
        )
        return await self._documents.create_note(
            note,
            [
                FiscalNoteLine(
                    line_number=line.line_number,
                    ccf_line_number=line.ccf_line_number,
                    kind=line.kind.value,
                    nature=line.nature.value,
                    description=line.description,
                    # Una rebaja no devuelve unidades: su cantidad 1 es solo la del DTE.
                    quantity=None if line.kind == NoteLineKind.DISCOUNT else line.quantity,
                    amount=line.amount,
                )
                for line in planned
            ],
        )

    async def credit_note(
        self,
        company_id: uuid.UUID,
        ccf_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        requests: list[CreditLineRequest],
        today: date | None = None,
    ) -> FiscalDocument:
        # Bloquear el CCF serializa las notas del mismo CCF y su invalidación.
        ccf = await self._ccf(company_id, ccf_id, lock=True)
        issued = await self._require_noteable(ccf)
        require_note_in_time(issued, today or today_sv())
        await self._require_enabled(company_id, CREDIT_NOTE)
        text = require_reason(reason)
        balances = line_balances(ccf_lines(ccf.dte_json or {}), await self._prior(ccf))
        planned = plan_credit_note(balances, requests)
        return await self._create(ccf, issued, CREDIT_NOTE, planned, text, actor_id)

    async def debit_note(
        self,
        company_id: uuid.UUID,
        ccf_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        requests: list[DebitChargeRequest],
        today: date | None = None,
    ) -> FiscalDocument:
        ccf = await self._ccf(company_id, ccf_id, lock=True)
        issued = await self._require_noteable(ccf)
        require_note_in_time(issued, today or today_sv())
        await self._require_enabled(company_id, DEBIT_NOTE)
        text = require_reason(reason)
        planned = plan_debit_note(ccf_lines(ccf.dte_json or {}), requests)
        return await self._create(ccf, issued, DEBIT_NOTE, planned, text, actor_id)
