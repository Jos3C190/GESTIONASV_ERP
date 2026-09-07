"""SQLAlchemy implementation of the purchase-request repository port."""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
)
from app.domain.ports.purchase_request_repository import PurchaseProductReference
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)


def _to_detail(model: PurchaseRequestDetailModel) -> PurchaseRequestDetail:
    return PurchaseRequestDetail(
        id=model.id,
        purchase_request_id=model.purchase_request_id,
        product_id=model.product_id,
        unit_id=model.unit_id,
        quantity=model.quantity,
        description=model.description,
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_entity(model: PurchaseRequestModel) -> PurchaseRequest:
    return PurchaseRequest(
        id=model.id,
        company_id=model.company_id,
        code=model.code,
        branch_id=model.branch_id,
        warehouse_id=model.warehouse_id,
        requested_by_id=model.requested_by_id,
        request_date=model.request_date,
        required_date=model.required_date,
        justification=model.justification,
        status=PurchaseRequestStatus(model.status),
        notes=model.notes,
        details=tuple(_to_detail(detail) for detail in model.details),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_requests(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseRequestStatus | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseRequest], int]:
        conditions = [PurchaseRequestModel.company_id == company_id]
        if status is not None:
            conditions.append(PurchaseRequestModel.status == status.value)
        if branch_id is not None:
            conditions.append(PurchaseRequestModel.branch_id == branch_id)

        total = await self._session.scalar(
            select(func.count()).select_from(PurchaseRequestModel).where(*conditions)
        )
        result = await self._session.execute(
            select(PurchaseRequestModel)
            .options(selectinload(PurchaseRequestModel.details))
            .where(*conditions)
            .order_by(PurchaseRequestModel.request_date.desc(), PurchaseRequestModel.code.desc())
            .offset(skip)
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().all()], int(total or 0)

    async def get_request(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest | None:
        model = await self._get_model(company_id, request_id)
        return _to_entity(model) if model is not None else None

    async def get_request_for_update(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest | None:
        model = await self._get_model(company_id, request_id, for_update=True)
        return _to_entity(model) if model is not None else None

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        # The transaction-scoped advisory lock serializes allocation per tenant.
        # The UNIQUE(company_id, code) constraint remains the final DB guard.
        lock_name = f"purchase_requests:{company_id}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(lock_name)))
        )
        last_number = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(cast(func.substr(PurchaseRequestModel.code, 5), Integer)),
                    0,
                )
            ).where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.code.op("~")(r"^SCR-[0-9]+$"),
            )
        )
        return f"SCR-{int(last_number or 0) + 1:05d}"

    async def is_branch_available(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
    ) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(Branch)
            .where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
                Branch.deleted_at.is_(None),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
            )
        )
        return bool(count)

    async def is_warehouse_available(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(Warehouse)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .where(
                Warehouse.id == warehouse_id,
                Warehouse.branch_id == branch_id,
                Warehouse.deleted_at.is_(None),
                Warehouse.is_active.is_(True),
                Warehouse.operational_status == "active",
                Branch.id == branch_id,
                Branch.company_id == company_id,
                Branch.deleted_at.is_(None),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
            )
        )
        return bool(count)

    async def get_product_reference(
        self,
        company_id: uuid.UUID,
        product_id: int,
    ) -> PurchaseProductReference | None:
        result = await self._session.execute(
            select(
                ProductModel.id_product,
                ProductModel.purchase_unit,
                ProductModel.is_active,
                ProductModel.lifecycle_status,
                ProductModel.can_purchase,
                CompanyUnitModel.is_enabled,
            )
            .outerjoin(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.company_id == ProductModel.company_id,
                    CompanyUnitModel.unit_id == ProductModel.purchase_unit,
                ),
            )
            .where(
                ProductModel.company_id == company_id,
                ProductModel.id_product == product_id,
                ProductModel.deleted_at.is_(None),
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return PurchaseProductReference(
            product_id=row.id_product,
            purchase_unit_id=row.purchase_unit,
            is_active=row.is_active,
            lifecycle_status=row.lifecycle_status,
            can_purchase=row.can_purchase,
            unit_enabled=bool(row.is_enabled),
        )

    async def add_request(self, request: PurchaseRequest) -> PurchaseRequest:
        model = PurchaseRequestModel(
            id=request.id,
            company_id=request.company_id,
            code=request.code,
            branch_id=request.branch_id,
            warehouse_id=request.warehouse_id,
            requested_by_id=request.requested_by_id,
            request_date=request.request_date,
            required_date=request.required_date,
            justification=request.justification,
            status=request.status.value,
            notes=request.notes,
            details=[self._detail_model(request.company_id, detail) for detail in request.details],
        )
        self._session.add(model)
        await self._session.flush()
        persisted = await self.get_request(request.company_id, request.id)
        assert persisted is not None
        return persisted

    async def replace_draft(self, request: PurchaseRequest) -> PurchaseRequest | None:
        model = await self._get_model(request.company_id, request.id)
        if model is None:
            return None
        model.branch_id = request.branch_id
        model.warehouse_id = request.warehouse_id
        model.required_date = request.required_date
        model.justification = request.justification
        model.notes = request.notes
        model.details = [
            self._detail_model(request.company_id, detail) for detail in request.details
        ]
        await self._session.flush()
        return await self.get_request(request.company_id, request.id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        status: PurchaseRequestStatus,
    ) -> PurchaseRequest | None:
        model = await self._get_model(company_id, request_id)
        if model is None:
            return None
        model.status = status.value
        await self._session.flush()
        return await self.get_request(company_id, request_id)

    async def _get_model(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseRequestModel | None:
        statement = (
            select(PurchaseRequestModel)
            .options(selectinload(PurchaseRequestModel.details))
            .where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.id == request_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    def _detail_model(
        company_id: uuid.UUID,
        detail: PurchaseRequestDetail,
    ) -> PurchaseRequestDetailModel:
        return PurchaseRequestDetailModel(
            id=detail.id,
            purchase_request_id=detail.purchase_request_id,
            company_id=company_id,
            product_id=detail.product_id,
            unit_id=detail.unit_id,
            quantity=detail.quantity,
            description=detail.description,
            notes=detail.notes,
        )
