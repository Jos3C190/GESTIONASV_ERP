"""Documento fiscal del pedido en PostgreSQL (bloque V3b)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus
from app.domain.ports.sales_fiscal_repository import FiscalDocument, FiscalDocumentFilters
from app.infrastructure.models.catalog import CompanyUnitModel
from app.infrastructure.models.fiscal import (
    FiscalEstablishmentModel,
    FiscalPointOfSaleModel,
    HaciendaCatalogItemModel,
)
from app.infrastructure.models.sales import SaleModel, SalesCustomerModel
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentModel

_FIELDS = (
    "branch_id",
    "sale_id",
    "establishment_id",
    "point_of_sale_id",
    "document_type",
    "mode",
    "idempotency_key",
    "total",
    "issuer_snapshot",
    "request_payload",
    "created_by_id",
    "attempts",
    "generation_code",
    "control_number",
    "dte_json",
    "seal",
    "service_response",
    "json_object_key",
    "pdf_object_key",
    "error_code",
    "error_message",
    "issued_at",
    "contingency_type",
    "contingency_reason",
    "contingency_at",
)
#: Lo que cambia después de crear el documento.
_MUTABLE = (
    "attempts",
    "generation_code",
    "control_number",
    "dte_json",
    "seal",
    "service_response",
    "json_object_key",
    "pdf_object_key",
    "error_code",
    "error_message",
    "issued_at",
    "contingency_type",
    "contingency_reason",
    "contingency_at",
)


def _query() -> Select[Any]:
    return (
        select(
            SalesFiscalDocumentModel,
            SaleModel.code,
            SalesCustomerModel.name,
            FiscalPointOfSaleModel.code,
            FiscalEstablishmentModel.code,
            SalesCustomerModel.email,
        )
        .join(
            SaleModel,
            (SaleModel.company_id == SalesFiscalDocumentModel.company_id)
            & (SaleModel.id == SalesFiscalDocumentModel.sale_id),
        )
        .join(
            SalesCustomerModel,
            (SalesCustomerModel.company_id == SaleModel.company_id)
            & (SalesCustomerModel.id == SaleModel.customer_id),
        )
        .join(
            FiscalPointOfSaleModel,
            FiscalPointOfSaleModel.id == SalesFiscalDocumentModel.point_of_sale_id,
        )
        .join(
            FiscalEstablishmentModel,
            FiscalEstablishmentModel.id == SalesFiscalDocumentModel.establishment_id,
        )
    )


def _entity(row: Any) -> FiscalDocument:
    model, sale_code, customer_name, pos_code, establishment_code, customer_email = row
    return FiscalDocument(
        id=model.id,
        company_id=model.company_id,
        status=FiscalDocumentStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
        sale_code=sale_code,
        customer_name=customer_name,
        point_of_sale_code=pos_code,
        establishment_code=establishment_code,
        customer_email=customer_email,
        **{name: getattr(model, name) for name in _FIELDS},
    )


class SqlAlchemySalesFiscalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _one(self, statement: Select[Any]) -> FiscalDocument | None:
        row = (await self._session.execute(statement)).first()
        return _entity(row) if row is not None else None

    async def create(self, document: FiscalDocument) -> FiscalDocument:
        model = SalesFiscalDocumentModel(
            id=document.id,
            company_id=document.company_id,
            status=document.status.value,
            **{name: getattr(document, name) for name in _FIELDS},
        )
        self._session.add(model)
        await self._session.flush()
        created = await self.get(document.company_id, document.id)
        assert created is not None
        return created

    async def get(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, lock: bool = False
    ) -> FiscalDocument | None:
        statement = _query().where(
            SalesFiscalDocumentModel.company_id == company_id,
            SalesFiscalDocumentModel.id == document_id,
        )
        if lock:
            statement = statement.with_for_update(of=SalesFiscalDocumentModel)
        return await self._one(statement)

    async def active_for_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> FiscalDocument | None:
        return await self._one(
            _query().where(
                SalesFiscalDocumentModel.company_id == company_id,
                SalesFiscalDocumentModel.sale_id == order_id,
                SalesFiscalDocumentModel.status != FiscalDocumentStatus.FAILED.value,
            )
        )

    async def list_documents(
        self, company_id: uuid.UUID, filters: FiscalDocumentFilters, *, page: int, size: int
    ) -> tuple[list[FiscalDocument], int]:
        statement = _query().where(SalesFiscalDocumentModel.company_id == company_id)
        if filters.branch_ids is not None:
            statement = statement.where(SalesFiscalDocumentModel.branch_id.in_(filters.branch_ids))
        if filters.branch_id is not None:
            statement = statement.where(SalesFiscalDocumentModel.branch_id == filters.branch_id)
        if filters.sale_id is not None:
            statement = statement.where(SalesFiscalDocumentModel.sale_id == filters.sale_id)
        if filters.status is not None:
            statement = statement.where(SalesFiscalDocumentModel.status == filters.status)
        if filters.document_type is not None:
            statement = statement.where(
                SalesFiscalDocumentModel.document_type == filters.document_type
            )
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            statement = statement.where(
                or_(
                    SalesFiscalDocumentModel.control_number.ilike(pattern),
                    SaleModel.code.ilike(pattern),
                    SalesCustomerModel.name.ilike(pattern),
                )
            )
        total = await self._session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = (
            await self._session.execute(
                statement.order_by(
                    SalesFiscalDocumentModel.created_at.desc(), SalesFiscalDocumentModel.id
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return [_entity(row) for row in rows], int(total or 0)

    async def save(self, document: FiscalDocument) -> FiscalDocument:
        await self._session.execute(
            update(SalesFiscalDocumentModel)
            .where(
                SalesFiscalDocumentModel.company_id == document.company_id,
                SalesFiscalDocumentModel.id == document.id,
            )
            .values(
                status=document.status.value,
                updated_at=func.now(),
                **{name: getattr(document, name) for name in _MUTABLE},
            )
        )
        saved = await self.get(document.company_id, document.id)
        assert saved is not None
        return saved

    async def claim(self, document_id: uuid.UUID, max_attempts: int) -> FiscalDocument | None:
        model = await self._session.scalar(
            select(SalesFiscalDocumentModel)
            .where(
                SalesFiscalDocumentModel.id == document_id,
                SalesFiscalDocumentModel.status == FiscalDocumentStatus.PENDING.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        model.attempts += 1
        await self._session.flush()
        return await self.get(model.company_id, model.id)

    async def lock_contingency(self, document_id: uuid.UUID) -> FiscalDocument | None:
        model = await self._session.scalar(
            select(SalesFiscalDocumentModel)
            .where(
                SalesFiscalDocumentModel.id == document_id,
                SalesFiscalDocumentModel.status == FiscalDocumentStatus.CONTINGENCY.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        return await self.get(model.company_id, model.id)

    async def contingency_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]:
        """Documentos en contingencia que no se revisan desde ``updated_before``."""

        rows = await self._session.scalars(
            select(SalesFiscalDocumentModel.id)
            .where(
                SalesFiscalDocumentModel.status == FiscalDocumentStatus.CONTINGENCY.value,
                SalesFiscalDocumentModel.updated_at < updated_before,
            )
            .order_by(SalesFiscalDocumentModel.updated_at)
            .limit(limit)
        )
        return list(rows)

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]:
        rows = await self._session.scalars(
            select(SalesFiscalDocumentModel.id)
            .where(
                SalesFiscalDocumentModel.status == FiscalDocumentStatus.PENDING.value,
                SalesFiscalDocumentModel.updated_at < updated_before,
            )
            .order_by(SalesFiscalDocumentModel.updated_at)
            .limit(limit)
        )
        return list(rows)

    async def unit_codes(self, company_id: uuid.UUID, unit_ids: set[int]) -> dict[int, str]:
        if not unit_ids:
            return {}
        rows = await self._session.execute(
            select(CompanyUnitModel.unit_id, CompanyUnitModel.hacienda_unit_code).where(
                CompanyUnitModel.company_id == company_id,
                CompanyUnitModel.unit_id.in_(unit_ids),
                CompanyUnitModel.hacienda_unit_code.is_not(None),
            )
        )
        return {unit_id: code for unit_id, code in rows if code}

    async def catalog_version(self, catalog_code: str) -> str | None:
        version = await self._session.scalar(
            select(func.max(HaciendaCatalogItemModel.catalog_version)).where(
                HaciendaCatalogItemModel.catalog_code == catalog_code
            )
        )
        return str(version) if version else None
