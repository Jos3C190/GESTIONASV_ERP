"""Lee los documentos sellados de un mes y los datos fiscales de las compras.

Los montos de ventas salen del JSON del DTE tal como se selló (o se simuló), nunca del pedido.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal_books import (
    ZERO,
    Party,
    Period,
    PurchaseDocument,
    PurchaseFiscalData,
    RentaPurchase,
    ReturnEvent,
    SaleDocument,
    default_purchase_renta,
    money,
    supplier_party,
)
from app.domain.ports.fiscal_book_repository import (
    Issuer,
    PendingPurchase,
    PurchaseFiscalView,
)

# Una factura se puede invalidar hasta tres meses después: el mes la resta con su fecha original.
_LOOKBACK = timedelta(days=100)

_SALES = """
    SELECT d.id, d.document_type, d.control_number, d.generation_code,
           COALESCE(d.seal, d.service_response->>'simulationMarker') AS seal,
           d.dte_json, d.renta_operation_type, d.renta_income_type,
           (d.dte_json->'identificacion'->>'fecEmi')::date AS issued_on,
           inv.resolved_on
    FROM sales_fiscal_documents d
    LEFT JOIN LATERAL (
        SELECT (i.resolved_at AT TIME ZONE 'America/El_Salvador')::date AS resolved_on
        FROM sales_fiscal_invalidations i
        WHERE i.company_id = d.company_id AND i.document_id = d.id AND i.status = 'accepted'
        ORDER BY i.resolved_at LIMIT 1
    ) inv ON true
    WHERE d.company_id = :company AND d.dte_json IS NOT NULL
      AND d.document_type IN ('01', '03', '05', '06')
      AND d.status IN ('issued', 'simulated', 'invalidated')
      AND (CAST(:mode AS text) IS NULL OR d.mode = :mode)
      AND (CAST(:start AS date) IS NULL
           OR (d.dte_json->'identificacion'->>'fecEmi')::date BETWEEN :start AND :end)
      AND (CAST(:ids AS uuid[]) IS NULL OR d.id = ANY(:ids))
"""


def _decimal(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def _party(receptor: dict[str, Any] | None) -> Party:
    rec = receptor or {}
    kind = rec.get("tipoDocumento")
    number = rec.get("numDocumento")
    return Party(
        name=str(rec.get("nombre") or "Consumidor final"),
        nit=rec.get("nit") or (number if kind == "36" else None),
        nrc=rec.get("nrc"),
        dui=number if kind == "13" else None,
    )


def _vat(summary: dict[str, Any]) -> Decimal:
    if summary.get("totalIva") is not None:
        return _decimal(summary["totalIva"])
    return sum(
        (
            _decimal(item.get("valor"))
            for item in summary.get("tributos") or []
            if item.get("codigo") == "20"
        ),
        ZERO,
    )


def _sale(row: Any) -> SaleDocument:
    dte = row.dte_json or {}
    summary = dte.get("resumen") or {}
    return SaleDocument(
        document_type=row.document_type,
        issued_on=row.issued_on,
        control_number=row.control_number or "",
        generation_code=str(row.generation_code or "").upper(),
        seal=row.seal or "",
        receiver=_party(dte.get("receptor")),
        exempt=_decimal(summary.get("totalExenta")),
        not_subject=_decimal(summary.get("totalNoSuj")),
        taxed=_decimal(summary.get("totalGravada")),
        vat=_vat(summary),
        perception=_decimal(summary.get("ivaPerci1") or summary.get("ivaPerci")),
        renta_operation=row.renta_operation_type,
        renta_income=row.renta_income_type,
        invalidated_on=row.resolved_on,
    )


class SqlAlchemyFiscalBookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def issuer(self, company_id: uuid.UUID) -> Issuer:
        row = (
            await self._session.execute(
                text("SELECT name, nit, nrc FROM companies WHERE id = :company"),
                {"company": company_id},
            )
        ).one()
        return Issuer(name=row.name, nit=row.nit, nrc=row.nrc)

    async def modes(self, company_id: uuid.UUID, period: Period) -> list[str]:
        rows = await self._session.execute(
            text(
                "SELECT DISTINCT mode FROM sales_fiscal_documents "
                "WHERE company_id = :company AND dte_json IS NOT NULL "
                "AND (dte_json->'identificacion'->>'fecEmi')::date BETWEEN :start AND :end"
            ),
            {"company": company_id, "start": period.first - _LOOKBACK, "end": period.last},
        )
        return sorted(row.mode for row in rows)

    async def sales(self, company_id: uuid.UUID, period: Period, mode: str) -> list[SaleDocument]:
        rows = await self._session.execute(
            text(_SALES),
            {
                "company": company_id,
                "mode": mode,
                "start": period.first - _LOOKBACK,
                "end": period.last,
                "ids": None,
            },
        )
        return [_sale(row) for row in rows]

    async def returns(self, company_id: uuid.UUID, period: Period, mode: str) -> list[ReturnEvent]:
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT r.id, r.document_id, r.generation_code,
                           COALESCE(r.seal, '') AS seal,
                           (r.issued_at AT TIME ZONE 'America/El_Salvador')::date AS returned_on,
                           COALESCE(SUM(l.amount) FILTER (WHERE l.nature = 'exempt'), 0) AS exempt,
                           COALESCE(SUM(l.amount) FILTER (WHERE l.nature = 'not_subject'), 0)
                               AS not_subject,
                           COALESCE(SUM(l.amount) FILTER (WHERE l.nature = 'taxed'), 0) AS taxed
                    FROM sales_fiscal_returns r
                    JOIN sales_fiscal_documents d
                      ON d.company_id = r.company_id AND d.id = r.document_id
                    LEFT JOIN sales_fiscal_return_lines l
                      ON l.company_id = r.company_id AND l.return_id = r.id
                    WHERE r.company_id = :company AND d.mode = :mode
                      AND r.status IN ('issued', 'simulated')
                      AND (r.issued_at AT TIME ZONE 'America/El_Salvador')::date BETWEEN :start AND :end
                    GROUP BY r.id
                    """
                ),
                {"company": company_id, "mode": mode, "start": period.first, "end": period.last},
            )
        ).all()
        if not rows:
            return []
        invoices = {
            row.id: _sale(row)
            for row in await self._session.execute(
                text(_SALES),
                {
                    "company": company_id,
                    "mode": None,
                    "start": None,
                    "end": None,
                    "ids": list({row.document_id for row in rows}),
                },
            )
        }
        return [
            ReturnEvent(
                invoice=invoices[row.document_id],
                returned_on=row.returned_on,
                generation_code=str(row.generation_code or "").upper(),
                seal=row.seal,
                exempt=money(_decimal(row.exempt)),
                not_subject=_decimal(row.not_subject),
                taxed=money(_decimal(row.taxed)),
            )
            for row in rows
            if row.document_id in invoices
        ]

    async def contingency_count(self, company_id: uuid.UUID, period: Period, mode: str) -> int:
        value = await self._session.scalar(
            text(
                "SELECT count(*) FROM sales_fiscal_documents WHERE company_id = :company "
                "AND mode = :mode AND status = 'contingency' AND dte_json IS NOT NULL "
                "AND (dte_json->'identificacion'->>'fecEmi')::date BETWEEN :start AND :end"
            ),
            {"company": company_id, "mode": mode, "start": period.first, "end": period.last},
        )
        return int(value or 0)

    async def _purchase_rows(
        self,
        company_id: uuid.UUID,
        *,
        purchase: uuid.UUID | None = None,
        recorded: bool | None = None,
        period: Period | None = None,
    ) -> list[Any]:
        rows = await self._session.execute(
            text(
                """
                SELECT p.id, p.company_id, p.branch_id, p.code, p.status,
                       p.supplier_invoice_number, p.supplier_invoice_date, p.total,
                       p.fiscal_document_class, p.fiscal_document_type, p.fiscal_document_number,
                       p.fiscal_control_number, p.fiscal_seal, p.fiscal_supplier_name,
                       p.fiscal_supplier_id_type, p.fiscal_supplier_id, p.renta_operation_type,
                       p.renta_classification, p.renta_sector, p.renta_cost_type,
                       p.fiscal_recorded_at,
                       COALESCE(s.legal_name, s.name) AS supplier_name,
                       (SELECT jsonb_object_agg(lower(t.identifier_type), t.normalized_value)
                        FROM supplier_tax_identifiers t WHERE t.supplier_id = p.supplier_id)
                           AS supplier_ids,
                       COALESCE(SUM(d.subtotal - d.discount) FILTER (WHERE d.tax_amount = 0), 0)
                           AS exempt,
                       COALESCE(SUM(d.subtotal - d.discount) FILTER (WHERE d.tax_amount > 0), 0)
                           AS taxed,
                       COALESCE(SUM(d.tax_amount), 0) AS vat
                FROM purchases p
                JOIN suppliers s ON s.company_id = p.company_id AND s.id_supplier = p.supplier_id
                LEFT JOIN purchase_details d ON d.purchase_id = p.id
                WHERE p.company_id = :company
                  AND (CAST(:purchase AS uuid) IS NULL OR p.id = :purchase)
                  AND (CAST(:recorded AS boolean) IS NULL
                       OR ((p.fiscal_document_class IS NOT NULL) = :recorded
                           AND p.status IN ('received', 'verified', 'closed')))
                  AND (CAST(:start AS date) IS NULL
                       OR COALESCE(p.supplier_invoice_date,
                                   (p.purchase_date AT TIME ZONE 'America/El_Salvador')::date)
                          BETWEEN :start AND :end)
                GROUP BY p.id, s.legal_name, s.name
                ORDER BY p.supplier_invoice_date NULLS LAST, p.code
                """
            ),
            {
                "company": company_id,
                "purchase": purchase,
                "recorded": recorded,
                "start": period.first if period else None,
                "end": period.last if period else None,
            },
        )
        return list(rows)

    async def purchases(self, company_id: uuid.UUID, period: Period) -> list[PurchaseDocument]:
        rows = await self._purchase_rows(company_id, recorded=True, period=period)
        return [
            PurchaseDocument(
                purchase_code=row.code,
                issued_on=row.supplier_invoice_date,
                document_class=row.fiscal_document_class,
                document_type=row.fiscal_document_type,
                number=row.fiscal_document_number,
                supplier=supplier_party(
                    row.fiscal_supplier_name, row.fiscal_supplier_id_type, row.fiscal_supplier_id
                ),
                exempt=money(_decimal(row.exempt)),
                taxed=money(_decimal(row.taxed)),
                vat=money(_decimal(row.vat)),
                renta_operation=row.renta_operation_type,
                renta_classification=row.renta_classification,
                renta_sector=row.renta_sector,
                renta_cost_type=row.renta_cost_type,
            )
            for row in rows
        ]

    async def pending_purchases(
        self, company_id: uuid.UUID, period: Period
    ) -> list[PendingPurchase]:
        rows = await self._purchase_rows(company_id, recorded=False, period=period)
        return [
            PendingPurchase(
                id=row.id,
                code=row.code,
                supplier=row.supplier_name,
                invoice_number=row.supplier_invoice_number,
                invoice_date=row.supplier_invoice_date,
                total=money(_decimal(row.total)),
            )
            for row in rows
        ]

    async def purchase(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> PurchaseFiscalView | None:
        rows = await self._purchase_rows(company_id, purchase=purchase_id)
        if not rows:
            return None
        row = rows[0]
        fiscal = None
        if row.fiscal_document_class is not None:
            fiscal = PurchaseFiscalData(
                issued_on=row.supplier_invoice_date,
                document_class=row.fiscal_document_class,
                document_type=row.fiscal_document_type,
                number=row.fiscal_document_number,
                control_number=row.fiscal_control_number,
                seal=row.fiscal_seal,
                supplier_name=row.fiscal_supplier_name,
                supplier_id_type=row.fiscal_supplier_id_type,
                supplier_id=row.fiscal_supplier_id,
                renta=RentaPurchase(
                    row.renta_operation_type,
                    row.renta_classification,
                    row.renta_sector,
                    row.renta_cost_type,
                ),
            )
        ids = {
            kind: value
            for key, value in (row.supplier_ids or {}).items()
            for kind in ("nit", "nrc", "dui")
            if kind in key
        }
        return PurchaseFiscalView(
            id=row.id,
            company_id=row.company_id,
            branch_id=row.branch_id,
            code=row.code,
            status=row.status,
            supplier_name=row.supplier_name,
            supplier_ids=ids,
            invoice_number=row.supplier_invoice_number,
            invoice_date=row.supplier_invoice_date,
            exempt=money(_decimal(row.exempt)),
            taxed=money(_decimal(row.taxed)),
            vat=money(_decimal(row.vat)),
            fiscal=fiscal,
            recorded_at=row.fiscal_recorded_at,
        )

    async def save_purchase_fiscal(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        data: PurchaseFiscalData,
        actor_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE purchases SET
                    supplier_invoice_date = :issued_on,
                    supplier_invoice_number = COALESCE(supplier_invoice_number, :invoice_number),
                    fiscal_document_class = :document_class,
                    fiscal_document_type = :document_type,
                    fiscal_document_number = :number,
                    fiscal_control_number = :control_number,
                    fiscal_seal = :seal,
                    fiscal_supplier_name = :supplier_name,
                    fiscal_supplier_id_type = :supplier_id_type,
                    fiscal_supplier_id = :supplier_id,
                    renta_operation_type = :operation,
                    renta_classification = :classification,
                    renta_sector = :sector,
                    renta_cost_type = :cost_type,
                    fiscal_recorded_by_id = :actor,
                    fiscal_recorded_at = :now,
                    updated_at = :now
                WHERE company_id = :company AND id = :purchase
                """
            ),
            {
                "company": company_id,
                "purchase": purchase_id,
                "issued_on": data.issued_on,
                "invoice_number": data.number[:80],
                "document_class": data.document_class,
                "document_type": data.document_type,
                "number": data.number,
                "control_number": data.control_number,
                "seal": data.seal,
                "supplier_name": data.supplier_name,
                "supplier_id_type": data.supplier_id_type,
                "supplier_id": data.supplier_id,
                "operation": data.renta.operation,
                "classification": data.renta.classification,
                "sector": data.renta.sector,
                "cost_type": data.renta.cost_type,
                "actor": actor_id,
                "now": datetime.now(UTC),
            },
        )

    async def renta_defaults(self, company_id: uuid.UUID) -> RentaPurchase:
        row = (
            await self._session.execute(
                text(
                    "SELECT purchase_operation_type, purchase_classification, purchase_sector, "
                    "purchase_cost_type FROM fiscal_book_settings WHERE company_id = :company"
                ),
                {"company": company_id},
            )
        ).one_or_none()
        if row is not None:
            return RentaPurchase(*row)
        activity = await self._session.scalar(
            text(
                "SELECT activity_code FROM company_economic_activities "
                "WHERE company_id = :company AND is_primary"
            ),
            {"company": company_id},
        )
        return default_purchase_renta(activity)

    async def save_renta_defaults(
        self, company_id: uuid.UUID, renta: RentaPurchase, actor_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO fiscal_book_settings (company_id, purchase_operation_type,
                    purchase_classification, purchase_sector, purchase_cost_type,
                    updated_by_id, updated_at)
                VALUES (:company, :operation, :classification, :sector, :cost_type, :actor, now())
                ON CONFLICT (company_id) DO UPDATE SET
                    purchase_operation_type = EXCLUDED.purchase_operation_type,
                    purchase_classification = EXCLUDED.purchase_classification,
                    purchase_sector = EXCLUDED.purchase_sector,
                    purchase_cost_type = EXCLUDED.purchase_cost_type,
                    updated_by_id = EXCLUDED.updated_by_id,
                    updated_at = now()
                """
            ),
            {
                "company": company_id,
                "operation": renta.operation,
                "classification": renta.classification,
                "sector": renta.sector,
                "cost_type": renta.cost_type,
                "actor": actor_id,
            },
        )
