"""Ajuste fiscal automático al aceptar una devolución (V8a).

Cada aceptación de mercadería devuelta de un pedido facturado emite su documento: una nota de
crédito si el pedido se facturó con crédito fiscal (03), o un evento de retorno si fue factura
(01). Si no se puede emitir (pedido sin facturar, documento sin sellar, plazo vencido…) queda
registrado el motivo, sin bloquear la aceptación física. La fila es única por la llave de la
resolución: un reintento devuelve el mismo ajuste y no emite otro documento.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.audit.audit_service import AuditService
from app.application.sales_invoices.notes import SalesFiscalNoteUseCases
from app.application.sales_invoices.returns import SalesFiscalReturnUseCases
from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.entities.sales_fiscal_notes import CreditLineRequest, NoteLineKind
from app.domain.entities.sales_fiscal_returns import ReturnLineRequest
from app.domain.entities.sales_return_fiscal import fiscal_quantity
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ZERO = Decimal("0")
CCF = "03"
_SEALED = ("issued", "simulated")
MIN_MESSAGE = 5
_FAILED = "No se pudo emitir el ajuste fiscal."

_LINES = text("""
    SELECT sl.line_number_rank AS fiscal_line, sl.quantity, sl.quantity_base, rl.id AS line_id,
           sl.product_name
    FROM sales_return_lines rl
    JOIN sales_delivery_lines dl ON dl.company_id = rl.company_id AND dl.id = rl.delivery_line_id
    JOIN (
        SELECT id, company_id, quantity, quantity_base, product_name,
               row_number() OVER (PARTITION BY sale_id ORDER BY line_number) AS line_number_rank
        FROM sales_lines
        WHERE company_id = :company_id AND sale_id = :sale_id
    ) sl ON sl.company_id = dl.company_id AND sl.id = dl.sale_line_id
    WHERE rl.company_id = :company_id AND rl.return_id = :return_id AND rl.id = ANY(:ids)
""")
_DOCUMENT = text("""
    SELECT id, document_type, status, branch_id
    FROM sales_fiscal_documents
    WHERE company_id = :company_id AND sale_id = :sale_id
      AND document_type IN ('01', '03') AND superseded_by_id IS NULL
      AND status NOT IN ('failed', 'rejected', 'invalidated')
    ORDER BY created_at DESC
    LIMIT 1
""")
_RETURN = text("""
    SELECT r.sale_id, r.code, s.branch_id
    FROM sales_returns r JOIN sales s ON s.company_id = r.company_id AND s.id = r.sale_id
    WHERE r.company_id = :company_id AND r.id = :return_id
""")
_EXISTING = text("""
    SELECT id FROM sales_return_fiscal_adjustments
    WHERE company_id = :company_id AND return_id = :return_id AND resolution_key = :key
""")
_INSERT = text("""
    INSERT INTO sales_return_fiscal_adjustments (company_id, return_id, document_id, fiscal_note_id,
        fiscal_return_id, status, message, lines, resolution_key, created_by_id)
    VALUES (:company_id, :return_id, :document_id, :note_id, :event_id, :status, :message,
        CAST(:lines AS jsonb), :key, :actor_id)
    RETURNING id
""")


@dataclass(frozen=True)
class AcceptedLine:
    return_line_id: uuid.UUID
    quantity_base: Decimal


@dataclass(frozen=True)
class AdjustmentResult:
    """Documento emitido por la aceptación; el llamador lo encola tras confirmar."""

    fiscal_note_id: uuid.UUID | None = None
    fiscal_return_id: uuid.UUID | None = None


class ReturnFiscalAdjuster:
    def __init__(
        self,
        session: AsyncSession,
        notes: SalesFiscalNoteUseCases,
        returns: SalesFiscalReturnUseCases,
        audit: AuditService,
    ) -> None:
        self.session = session
        self.notes = notes
        self.returns = returns
        self.audit = audit

    async def adjust(
        self,
        *,
        company_id: uuid.UUID,
        return_id: uuid.UUID,
        actor_id: uuid.UUID,
        resolution_key: str,
        accepted: list[AcceptedLine],
        request: Any,
    ) -> AdjustmentResult:
        accepted = [line for line in accepted if line.quantity_base > ZERO]
        if not accepted:
            return AdjustmentResult()
        params = {"company_id": company_id, "return_id": return_id, "key": resolution_key}
        if (await self.session.execute(_EXISTING, params)).first() is not None:
            return AdjustmentResult()
        head = (await self.session.execute(_RETURN, params)).one()
        quantities = await self._fiscal_lines(company_id, return_id, head.sale_id, accepted)
        lines = [
            {"line_number": number, "quantity": str(quantity)}
            for number, quantity in sorted(quantities.items())
        ]
        document = (
            await self.session.execute(
                _DOCUMENT, {"company_id": company_id, "sale_id": head.sale_id}
            )
        ).first()
        document_id: uuid.UUID | None = document.id if document is not None else None
        note_id: uuid.UUID | None = None
        event_id: uuid.UUID | None = None
        message = _skip_reason(document, quantities)
        if document is not None and message is None:
            try:
                # El punto de guardado descarta lo que el emisor dejó a medias si lo rechaza.
                async with self.session.begin_nested():
                    note_id, event_id = await self._issue(
                        company_id,
                        document,
                        f"Devolución {head.code} aceptada",
                        quantities,
                        actor_id,
                    )
            except AppError as exc:
                message = exc.message[:500] if len(exc.message.strip()) >= MIN_MESSAGE else _FAILED
        status = "skipped" if message else "issued"
        row = (
            await self.session.execute(
                _INSERT,
                {
                    **params,
                    "document_id": document_id,
                    "note_id": note_id,
                    "event_id": event_id,
                    "status": status,
                    "message": message,
                    "lines": _json(lines),
                    "actor_id": actor_id,
                },
            )
        ).one()
        await self.audit.record(
            action="SALES_RETURN_FISCAL_ADJUSTMENT",
            user_id=actor_id,
            company_id=company_id,
            branch_id=head.branch_id,
            resource_type="sales_return",
            resource_id=str(return_id),
            after_state={
                "adjustment_id": str(row.id),
                "status": status,
                "document_id": str(document_id) if document_id else None,
                "fiscal_note_id": str(note_id) if note_id else None,
                "fiscal_return_id": str(event_id) if event_id else None,
                "message": message,
                "lines": lines,
            },
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            required=True,
        )
        return AdjustmentResult(fiscal_note_id=note_id, fiscal_return_id=event_id)

    async def _issue(
        self,
        company_id: uuid.UUID,
        document: Any,
        reason: str,
        quantities: dict[int, Decimal],
        actor_id: uuid.UUID,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        ordered = sorted(quantities.items())
        if document.document_type == CCF:
            note = await self.notes.credit_note(
                company_id,
                document.id,
                actor_id=actor_id,
                reason=reason,
                requests=[
                    CreditLineRequest(
                        ccf_line_number=number, kind=NoteLineKind.RETURN, quantity=qty
                    )
                    for number, qty in ordered
                ],
            )
            return note.id, None
        event = await self.returns.register(
            company_id,
            document.id,
            actor_id=actor_id,
            reason=reason,
            lines=[ReturnLineRequest(number, qty) for number, qty in ordered],
        )
        return None, event.id

    async def _fiscal_lines(
        self,
        company_id: uuid.UUID,
        return_id: uuid.UUID,
        sale_id: uuid.UUID,
        accepted: list[AcceptedLine],
    ) -> dict[int, Decimal]:
        by_line = {line.return_line_id: line.quantity_base for line in accepted}
        rows = await self.session.execute(
            _LINES,
            {
                "company_id": company_id,
                "return_id": return_id,
                "sale_id": sale_id,
                "ids": list(by_line),
            },
        )
        totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
        for row in rows:
            quantity = fiscal_quantity(by_line[row.line_id], row.quantity, row.quantity_base)
            if quantity > ZERO:
                totals[int(row.fiscal_line)] += quantity
        return dict(totals)


def _json(value: object) -> str:
    return json.dumps(value)


def _skip_reason(document: Any, quantities: dict[int, Decimal]) -> str | None:
    """Motivo por el que la aceptación no emite documento, o ``None`` si se puede emitir."""

    if document is None:
        return "El pedido no está facturado; no hay documento que ajustar."
    if document.status not in _SEALED:
        return (
            "El documento del pedido aún no tiene sello de Hacienda; emite el ajuste "
            "manualmente cuando se selle."
        )
    if not settings.DTE_SERVICE_URL:
        return "La facturación electrónica no está configurada en este servidor."
    if not quantities:
        return "Las cantidades aceptadas no alcanzan una unidad de venta."
    return None
