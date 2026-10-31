"""SQLAlchemy implementation of the retaceo repository."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast as type_cast

from sqlalchemy import Integer, Select, and_, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.retaceo import (
    Retaceo,
    RetaceoCost,
    RetaceoCostAllocation,
    RetaceoCostClass,
    RetaceoCostDocument,
    RetaceoDetail,
    RetaceoStatus,
)
from app.domain.entities.retaceo_calculation import CalculationMode
from app.domain.ports.retaceo_repository import RetaceoCostDocumentReference, RetaceoCostReference
from app.infrastructure.models.retaceo import (
    RetaceoCostAllocationModel,
    RetaceoCostDocumentModel,
    RetaceoCostModel,
    RetaceoDetailModel,
    RetaceoModel,
)


def _to_detail(model: RetaceoDetailModel) -> RetaceoDetail:
    return RetaceoDetail(
        id=model.id,
        retaceo_id=model.retaceo_id,
        purchase_detail_id=model.purchase_detail_id,
        product_id=model.product_id,
        unit_id=model.unit_id,
        quantity=model.quantity,
        cost_fob=model.cost_fob,
        freight=model.freight,
        expenses=model.expenses,
        dai=model.dai,
        total_cost=model.total_cost,
        unit_cost=model.unit_cost,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_cost_document(model: RetaceoCostDocumentModel) -> RetaceoCostDocument:
    return RetaceoCostDocument(
        id=model.id,
        retaceo_cost_id=model.retaceo_cost_id,
        document_id=model.document_id,
        file_name=model.file_name,
        file_type=model.file_type,
        uploaded_at=model.uploaded_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _to_cost(model: RetaceoCostModel) -> RetaceoCost:
    return RetaceoCost(
        id=model.id,
        retaceo_id=model.retaceo_id,
        classification=RetaceoCostClass(model.classification),
        title=model.title,
        amount=model.amount,
        allocations=tuple(
            RetaceoCostAllocation(
                purchase_detail_id=allocation.purchase_detail_id,
                amount=allocation.amount,
            )
            for allocation in model.allocations
        ),
        documents=tuple(
            _to_cost_document(document)
            for document in model.documents
            if document.deleted_at is None
        ),
        source_purchase_order_expense_id=model.source_purchase_order_expense_id,
        expense_type_id=model.expense_type_id,
        incurred_on=model.incurred_on,
        description=model.description,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_entity(model: RetaceoModel) -> Retaceo:
    return Retaceo(
        id=model.id,
        company_id=model.company_id,
        code=model.code,
        purchase_id=model.purchase_id,
        branch_id=model.branch_id,
        created_by_id=model.created_by_id,
        currency=model.currency,
        details=tuple(_to_detail(detail) for detail in model.details),
        costs=tuple(_to_cost(cost) for cost in model.costs),
        total_fob=model.total_fob,
        total_freight=model.total_freight,
        total_expenses=model.total_expenses,
        total_dai=model.total_dai,
        import_vat=model.import_vat,
        total_cost=model.total_cost,
        status=RetaceoStatus(model.status),
        applied_at=model.applied_at,
        applied_by=model.applied_by,
        notes=model.notes,
        origin_country=model.origin_country,
        import_invoice_number=model.import_invoice_number,
        import_invoice_date=model.import_invoice_date,
        import_policy_number=model.import_policy_number,
        import_policy_date=model.import_policy_date,
        manual_entry=bool(model.manual_entry),
        calculation_mode=type_cast(CalculationMode, model.calculation_mode),
        dai_rate=model.dai_rate,
        vat_rate=model.vat_rate,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyRetaceoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_retaceos(
        self,
        company_id: uuid.UUID,
        *,
        status: RetaceoStatus | None = None,
        purchase_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Retaceo], int]:
        conditions = [RetaceoModel.company_id == company_id]
        if status is not None:
            conditions.append(RetaceoModel.status == status.value)
        if purchase_id is not None:
            conditions.append(RetaceoModel.purchase_id == purchase_id)
        if branch_id is not None:
            conditions.append(RetaceoModel.branch_id == branch_id)

        total = await self._session.scalar(
            select(func.count()).select_from(RetaceoModel).where(*conditions)
        )
        result = await self._session.execute(
            self._base_statement()
            .where(*conditions)
            .order_by(RetaceoModel.created_at.desc(), RetaceoModel.code.desc())
            .offset(skip)
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().unique().all()], int(total or 0)

    async def get_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None:
        model = await self._get_model(company_id, retaceo_id)
        return _to_entity(model) if model is not None else None

    async def get_retaceo_for_update(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None:
        model = await self._get_model(company_id, retaceo_id, for_update=True)
        return _to_entity(model) if model is not None else None

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        lock_name = f"retaceos:{company_id}"
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_name))))
        last_number = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(sa_cast(func.substr(RetaceoModel.code, 5), Integer)),
                    0,
                )
            ).where(
                RetaceoModel.company_id == company_id,
                RetaceoModel.code.op("~")(r"^RET-[0-9]+$"),
            )
        )
        return f"RET-{int(last_number or 0) + 1:05d}"

    async def add_retaceo(self, retaceo: Retaceo) -> Retaceo:
        self._session.add(self._retaceo_model(retaceo))
        await self._session.flush()
        persisted = await self.get_retaceo(retaceo.company_id, retaceo.id)
        assert persisted is not None
        return persisted

    @staticmethod
    def _replace_draft_details(model: RetaceoModel, retaceo: Retaceo) -> None:
        existing = {detail.purchase_detail_id: detail for detail in model.details}
        replacements = {detail.purchase_detail_id: detail for detail in retaceo.details}
        if existing.keys() != replacements.keys():
            raise RuntimeError("Los detalles fuente de un retaceo en borrador no pueden cambiar.")
        for purchase_detail_id, replacement in replacements.items():
            persisted = existing[purchase_detail_id]
            persisted.product_id = replacement.product_id
            persisted.unit_id = replacement.unit_id
            persisted.quantity = replacement.quantity
            persisted.cost_fob = replacement.cost_fob
            persisted.freight = replacement.freight
            persisted.expenses = replacement.expenses
            persisted.dai = replacement.dai
            persisted.total_cost = replacement.total_cost
            persisted.unit_cost = replacement.unit_cost

    @staticmethod
    def _replace_cost_allocations(
        persisted_cost: RetaceoCostModel,
        replacement_cost: RetaceoCost,
        *,
        company_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> None:
        allocation_by_detail = {
            allocation.purchase_detail_id: allocation for allocation in persisted_cost.allocations
        }
        replacement_allocation_ids = {
            allocation.purchase_detail_id for allocation in replacement_cost.allocations
        }
        for purchase_detail_id, allocation in allocation_by_detail.items():
            if purchase_detail_id not in replacement_allocation_ids:
                persisted_cost.allocations.remove(allocation)
        current_allocation_by_detail = {
            allocation.purchase_detail_id: allocation for allocation in persisted_cost.allocations
        }
        for replacement_allocation in replacement_cost.allocations:
            current_allocation = current_allocation_by_detail.get(
                replacement_allocation.purchase_detail_id
            )
            if current_allocation is None:
                persisted_cost.allocations.append(
                    RetaceoCostAllocationModel(
                        id=uuid.uuid4(),
                        company_id=company_id,
                        retaceo_cost_id=cost_id,
                        purchase_detail_id=replacement_allocation.purchase_detail_id,
                        amount=replacement_allocation.amount,
                    )
                )
            else:
                current_allocation.amount = replacement_allocation.amount

    def _replace_existing_draft_costs(
        self,
        *,
        model: RetaceoModel,
        retaceo: Retaceo,
        existing_costs: dict[uuid.UUID, RetaceoCostModel],
        replacement_costs: dict[uuid.UUID, RetaceoCost],
    ) -> None:
        for cost_id, persisted_cost in existing_costs.items():
            replacement_cost = replacement_costs.get(cost_id)
            if replacement_cost is None:
                if persisted_cost.source_purchase_order_expense_id is not None:
                    raise RuntimeError("Los gastos heredados de la orden deben conservarse.")
                persisted_cost.is_active = False
                continue
            persisted_cost.classification = replacement_cost.classification.value
            persisted_cost.title = replacement_cost.title
            persisted_cost.description = replacement_cost.description
            persisted_cost.expense_type_id = replacement_cost.expense_type_id
            persisted_cost.incurred_on = replacement_cost.incurred_on
            persisted_cost.amount = replacement_cost.amount
            persisted_cost.is_active = replacement_cost.is_active
            self._replace_cost_allocations(
                persisted_cost,
                replacement_cost,
                company_id=retaceo.company_id,
                cost_id=cost_id,
            )

    def _append_new_draft_costs(
        self,
        *,
        model: RetaceoModel,
        retaceo: Retaceo,
        existing_costs: dict[uuid.UUID, RetaceoCostModel],
        replacement_costs: dict[uuid.UUID, RetaceoCost],
    ) -> None:
        for cost_id, replacement_cost in replacement_costs.items():
            if cost_id not in existing_costs:
                model.costs.append(self._cost_model(retaceo.company_id, replacement_cost))

    async def replace_draft(self, retaceo: Retaceo) -> Retaceo | None:
        model = await self._get_model(retaceo.company_id, retaceo.id)
        if model is None:
            return None
        model.total_fob = retaceo.total_fob
        model.total_freight = retaceo.total_freight
        model.total_expenses = retaceo.total_expenses
        model.total_dai = retaceo.total_dai
        model.import_vat = retaceo.import_vat
        model.total_cost = retaceo.total_cost
        model.notes = retaceo.notes
        model.origin_country = retaceo.origin_country
        model.import_invoice_number = retaceo.import_invoice_number
        model.import_invoice_date = retaceo.import_invoice_date
        model.import_policy_number = retaceo.import_policy_number
        model.import_policy_date = retaceo.import_policy_date
        model.manual_entry = retaceo.manual_entry
        model.calculation_mode = retaceo.calculation_mode
        model.dai_rate = retaceo.dai_rate
        model.vat_rate = retaceo.vat_rate
        self._replace_draft_details(model, retaceo)
        existing_costs = {cost.id: cost for cost in model.costs}
        replacement_costs = {cost.id: cost for cost in retaceo.costs}
        self._replace_existing_draft_costs(
            model=model,
            retaceo=retaceo,
            existing_costs=existing_costs,
            replacement_costs=replacement_costs,
        )
        self._append_new_draft_costs(
            model=model,
            retaceo=retaceo,
            existing_costs=existing_costs,
            replacement_costs=replacement_costs,
        )

        await self._session.flush()
        return await self.get_retaceo(retaceo.company_id, retaceo.id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        status: RetaceoStatus,
    ) -> Retaceo | None:
        model = await self._get_model(company_id, retaceo_id)
        if model is None:
            return None
        model.status = status.value
        await self._session.flush()
        return await self.get_retaceo(company_id, retaceo_id)

    async def get_cost_reference(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> RetaceoCostReference | None:
        row = (
            await self._session.execute(
                select(RetaceoModel.status, RetaceoCostModel.is_active)
                .join(
                    RetaceoCostModel,
                    and_(
                        RetaceoCostModel.retaceo_id == RetaceoModel.id,
                        RetaceoCostModel.company_id == RetaceoModel.company_id,
                    ),
                )
                .where(
                    RetaceoModel.company_id == company_id,
                    RetaceoModel.id == retaceo_id,
                    RetaceoCostModel.id == cost_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        status, is_active = row
        return RetaceoCostReference(
            retaceo_id=retaceo_id,
            cost_id=cost_id,
            status=RetaceoStatus(status),
            is_active=is_active,
        )

    async def add_cost_document(
        self,
        attachment: RetaceoCostDocument,
        company_id: uuid.UUID,
    ) -> RetaceoCostDocument:
        model = RetaceoCostDocumentModel(
            id=attachment.id,
            company_id=company_id,
            retaceo_cost_id=attachment.retaceo_cost_id,
            document_id=attachment.document_id,
            file_name=attachment.file_name,
            file_type=attachment.file_type,
            uploaded_at=attachment.uploaded_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_cost_document(model)

    async def get_cost_document(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> RetaceoCostDocumentReference | None:
        row = await self._session.execute(
            select(RetaceoCostDocumentModel, RetaceoModel.status)
            .join(
                RetaceoCostModel,
                and_(
                    RetaceoCostModel.id == RetaceoCostDocumentModel.retaceo_cost_id,
                    RetaceoCostModel.company_id == RetaceoCostDocumentModel.company_id,
                ),
            )
            .join(
                RetaceoModel,
                and_(
                    RetaceoModel.id == RetaceoCostModel.retaceo_id,
                    RetaceoModel.company_id == RetaceoCostModel.company_id,
                ),
            )
            .where(
                RetaceoModel.company_id == company_id,
                RetaceoModel.id == retaceo_id,
                RetaceoCostModel.id == cost_id,
                RetaceoCostDocumentModel.document_id == document_id,
                RetaceoCostDocumentModel.deleted_at.is_(None),
            )
        )
        result = row.one_or_none()
        if result is None:
            return None
        document_model, status = result
        return RetaceoCostDocumentReference(
            retaceo_id=retaceo_id,
            cost_id=cost_id,
            status=RetaceoStatus(status),
            document=_to_cost_document(document_model),
        )

    async def list_cost_documents(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> tuple[RetaceoCostDocument, ...]:
        result = await self._session.execute(
            select(RetaceoCostDocumentModel)
            .join(
                RetaceoCostModel,
                and_(
                    RetaceoCostModel.id == RetaceoCostDocumentModel.retaceo_cost_id,
                    RetaceoCostModel.company_id == RetaceoCostDocumentModel.company_id,
                ),
            )
            .where(
                RetaceoCostDocumentModel.company_id == company_id,
                RetaceoCostModel.retaceo_id == retaceo_id,
                RetaceoCostModel.id == cost_id,
                RetaceoCostDocumentModel.deleted_at.is_(None),
            )
            .order_by(RetaceoCostDocumentModel.created_at, RetaceoCostDocumentModel.id)
        )
        return tuple(_to_cost_document(item) for item in result.scalars().all())

    async def mark_cost_document_uploaded(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> RetaceoCostDocument | None:
        result = await self._session.execute(
            select(RetaceoCostDocumentModel)
            .join(
                RetaceoCostModel,
                and_(
                    RetaceoCostModel.id == RetaceoCostDocumentModel.retaceo_cost_id,
                    RetaceoCostModel.company_id == RetaceoCostDocumentModel.company_id,
                ),
            )
            .where(
                RetaceoCostDocumentModel.company_id == company_id,
                RetaceoCostModel.retaceo_id == retaceo_id,
                RetaceoCostModel.id == cost_id,
                RetaceoCostDocumentModel.document_id == document_id,
                RetaceoCostDocumentModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.file_type = file_type
        model.uploaded_at = uploaded_at
        await self._session.flush()
        return _to_cost_document(model)

    async def soft_delete_cost_document(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        deleted_at: datetime,
    ) -> RetaceoCostDocument | None:
        result = await self._session.execute(
            select(RetaceoCostDocumentModel)
            .join(
                RetaceoCostModel,
                and_(
                    RetaceoCostModel.id == RetaceoCostDocumentModel.retaceo_cost_id,
                    RetaceoCostModel.company_id == RetaceoCostDocumentModel.company_id,
                ),
            )
            .where(
                RetaceoCostDocumentModel.company_id == company_id,
                RetaceoCostModel.retaceo_id == retaceo_id,
                RetaceoCostModel.id == cost_id,
                RetaceoCostDocumentModel.document_id == document_id,
                RetaceoCostDocumentModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.deleted_at = deleted_at
        await self._session.flush()
        return _to_cost_document(model)

    async def _get_model(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> RetaceoModel | None:
        statement = self._base_statement().where(
            RetaceoModel.company_id == company_id,
            RetaceoModel.id == retaceo_id,
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        result = await self._session.execute(statement)
        return result.scalars().unique().one_or_none()

    @staticmethod
    def _base_statement() -> Select[tuple[RetaceoModel]]:
        return select(RetaceoModel).options(
            selectinload(RetaceoModel.details),
            selectinload(RetaceoModel.costs).selectinload(RetaceoCostModel.allocations),
            selectinload(RetaceoModel.costs).selectinload(RetaceoCostModel.documents),
        )

    @classmethod
    def _retaceo_model(cls, retaceo: Retaceo) -> RetaceoModel:
        return RetaceoModel(
            id=retaceo.id,
            company_id=retaceo.company_id,
            code=retaceo.code,
            purchase_id=retaceo.purchase_id,
            branch_id=retaceo.branch_id,
            created_by_id=retaceo.created_by_id,
            currency=retaceo.currency,
            total_fob=retaceo.total_fob,
            total_freight=retaceo.total_freight,
            total_expenses=retaceo.total_expenses,
            total_dai=retaceo.total_dai,
            import_vat=retaceo.import_vat,
            total_cost=retaceo.total_cost,
            status=retaceo.status.value,
            notes=retaceo.notes,
            origin_country=retaceo.origin_country,
            import_invoice_number=retaceo.import_invoice_number,
            import_invoice_date=retaceo.import_invoice_date,
            import_policy_number=retaceo.import_policy_number,
            import_policy_date=retaceo.import_policy_date,
            manual_entry=retaceo.manual_entry,
            calculation_mode=retaceo.calculation_mode,
            dai_rate=retaceo.dai_rate,
            vat_rate=retaceo.vat_rate,
            details=[cls._detail_model(retaceo.company_id, detail) for detail in retaceo.details],
            costs=[cls._cost_model(retaceo.company_id, cost) for cost in retaceo.costs],
        )

    @staticmethod
    def _cost_model(company_id: uuid.UUID, cost: RetaceoCost) -> RetaceoCostModel:
        return RetaceoCostModel(
            id=cost.id,
            company_id=company_id,
            retaceo_id=cost.retaceo_id,
            source_purchase_order_expense_id=cost.source_purchase_order_expense_id,
            expense_type_id=cost.expense_type_id,
            incurred_on=cost.incurred_on,
            classification=cost.classification.value,
            title=cost.title,
            description=cost.description,
            amount=cost.amount,
            is_active=cost.is_active,
            allocations=[
                RetaceoCostAllocationModel(
                    id=uuid.uuid4(),
                    company_id=company_id,
                    retaceo_cost_id=cost.id,
                    purchase_detail_id=allocation.purchase_detail_id,
                    amount=allocation.amount,
                )
                for allocation in cost.allocations
            ],
            documents=[
                RetaceoCostDocumentModel(
                    id=document.id,
                    company_id=company_id,
                    retaceo_cost_id=cost.id,
                    document_id=document.document_id,
                    file_name=document.file_name,
                    file_type=document.file_type,
                    uploaded_at=document.uploaded_at,
                )
                for document in cost.documents
            ],
        )

    @staticmethod
    def _detail_model(
        company_id: uuid.UUID,
        detail: RetaceoDetail,
    ) -> RetaceoDetailModel:
        return RetaceoDetailModel(
            id=detail.id,
            company_id=company_id,
            retaceo_id=detail.retaceo_id,
            purchase_detail_id=detail.purchase_detail_id,
            product_id=detail.product_id,
            unit_id=detail.unit_id,
            quantity=detail.quantity,
            cost_fob=detail.cost_fob,
            freight=detail.freight,
            expenses=detail.expenses,
            dai=detail.dai,
            total_cost=detail.total_cost,
            unit_cost=detail.unit_cost,
        )
