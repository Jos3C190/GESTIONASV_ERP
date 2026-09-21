"""SQLAlchemy implementation of the retaceo repository."""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, Select, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.retaceo import Retaceo, RetaceoDetail, RetaceoStatus
from app.infrastructure.models.retaceo import RetaceoDetailModel, RetaceoModel


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
        total_fob=model.total_fob,
        total_freight=model.total_freight,
        total_expenses=model.total_expenses,
        total_dai=model.total_dai,
        import_vat=model.import_vat,
        total_cost=model.total_cost,
        status=RetaceoStatus(model.status),
        notes=model.notes,
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
        existing_by_purchase_detail = {
            detail.purchase_detail_id: detail for detail in model.details
        }
        replacement_by_purchase_detail = {
            detail.purchase_detail_id: detail for detail in retaceo.details
        }

        if existing_by_purchase_detail.keys() != replacement_by_purchase_detail.keys():
            raise RuntimeError("Los detalles fuente de un retaceo en borrador no pueden cambiar.")

        for purchase_detail_id, replacement in replacement_by_purchase_detail.items():
            persisted = existing_by_purchase_detail[purchase_detail_id]
            persisted.product_id = replacement.product_id
            persisted.unit_id = replacement.unit_id
            persisted.quantity = replacement.quantity
            persisted.cost_fob = replacement.cost_fob
            persisted.freight = replacement.freight
            persisted.expenses = replacement.expenses
            persisted.dai = replacement.dai
            persisted.total_cost = replacement.total_cost
            persisted.unit_cost = replacement.unit_cost

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
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalars().unique().one_or_none()

    @staticmethod
    def _base_statement() -> Select[tuple[RetaceoModel]]:
        return select(RetaceoModel).options(selectinload(RetaceoModel.details))

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
            details=[cls._detail_model(retaceo.company_id, detail) for detail in retaceo.details],
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
