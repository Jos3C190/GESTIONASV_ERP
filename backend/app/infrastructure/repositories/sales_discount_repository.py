"""Escalas por volumen y topes de descuento por rol en PostgreSQL (bloque V2c)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_margin import DiscountPolicy
from app.domain.ports.sales_discount_repository import RolePolicy, VolumeDiscount
from app.infrastructure.models.rbac import Role, UserRole
from app.infrastructure.models.sales import SalesCustomerModel
from app.infrastructure.models.sales_pricing import (
    SalesDiscountPolicyModel,
    SalesVolumeDiscountModel,
)
from app.infrastructure.models.user import User

SUPER_ADMIN = "SUPER_ADMIN"


def _policy(row: SalesDiscountPolicyModel) -> DiscountPolicy:
    return DiscountPolicy(
        max_line_percent=row.max_line_discount_percent,
        max_global_percent=row.max_global_discount_percent,
        can_sell_below_cost=row.can_sell_below_cost,
    )


def _scale(row: SalesVolumeDiscountModel) -> VolumeDiscount:
    return VolumeDiscount(
        id=row.id,
        price_list_id=row.price_list_id,
        product_id=row.product_id,
        variant_id=row.variant_id,
        unit_id=row.unit_id,
        min_quantity=row.min_quantity,
        discount_percent=row.discount_percent,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
    )


class SqlAlchemySalesDiscountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _company_roles(self, company_id: uuid.UUID) -> Select[tuple[Role]]:
        return select(Role).where(
            Role.deleted_at.is_(None),
            Role.name != SUPER_ADMIN,
            or_(Role.company_id == company_id, Role.company_id.is_(None)),
        )

    async def role_policies(self, company_id: uuid.UUID) -> list[RolePolicy]:
        roles = (
            await self._session.scalars(self._company_roles(company_id).order_by(Role.name))
        ).all()
        policies = {
            row.role_id: row
            for row in (
                await self._session.scalars(
                    select(SalesDiscountPolicyModel).where(
                        SalesDiscountPolicyModel.company_id == company_id
                    )
                )
            ).all()
        }
        return [
            RolePolicy(
                role_id=role.id,
                role_name=role.name,
                policy=_policy(policies[role.id]) if role.id in policies else None,
                updated_at=policies[role.id].updated_at if role.id in policies else None,
            )
            for role in roles
        ]

    async def role_in_company(self, company_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            self._company_roles(company_id).where(Role.id == role_id)
        )
        return found is not None

    async def save_policy(
        self, company_id: uuid.UUID, role_id: uuid.UUID, policy: DiscountPolicy, actor_id: uuid.UUID
    ) -> None:
        row = await self._session.scalar(
            select(SalesDiscountPolicyModel).where(
                SalesDiscountPolicyModel.company_id == company_id,
                SalesDiscountPolicyModel.role_id == role_id,
            )
        )
        if row is None:
            row = SalesDiscountPolicyModel(company_id=company_id, role_id=role_id)
            self._session.add(row)
        row.max_line_discount_percent = policy.max_line_percent
        row.max_global_discount_percent = policy.max_global_percent
        row.can_sell_below_cost = policy.can_sell_below_cost
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def user_policies(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[bool, list[DiscountPolicy]]:
        is_superuser = bool(
            await self._session.scalar(select(User.is_superuser).where(User.id == user_id))
        )
        rows = (
            await self._session.scalars(
                select(SalesDiscountPolicyModel)
                .join(UserRole, UserRole.role_id == SalesDiscountPolicyModel.role_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    SalesDiscountPolicyModel.company_id == company_id,
                    UserRole.company_id == company_id,
                    UserRole.user_id == user_id,
                    Role.deleted_at.is_(None),
                )
            )
        ).all()
        return is_superuser, [_policy(r) for r in rows]

    async def volume_discounts(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        *,
        product_id: int | None = None,
        variant_id: uuid.UUID | None = None,
        unit_id: int | None = None,
    ) -> list[VolumeDiscount]:
        query = select(SalesVolumeDiscountModel).where(
            SalesVolumeDiscountModel.company_id == company_id,
            SalesVolumeDiscountModel.price_list_id == list_id,
        )
        if product_id is not None:
            variant = SalesVolumeDiscountModel.variant_id
            query = query.where(
                SalesVolumeDiscountModel.product_id == product_id,
                variant.is_(None) if variant_id is None else variant == variant_id,
            )
        if unit_id is not None:
            query = query.where(SalesVolumeDiscountModel.unit_id == unit_id)
        rows = (
            await self._session.scalars(
                query.order_by(
                    SalesVolumeDiscountModel.product_id,
                    SalesVolumeDiscountModel.unit_id,
                    SalesVolumeDiscountModel.min_quantity,
                    SalesVolumeDiscountModel.valid_from.desc(),
                )
            )
        ).all()
        return [_scale(r) for r in rows]

    async def get_volume_discount(
        self, company_id: uuid.UUID, scale_id: uuid.UUID
    ) -> VolumeDiscount | None:
        row = await self._session.scalar(
            select(SalesVolumeDiscountModel).where(
                SalesVolumeDiscountModel.company_id == company_id,
                SalesVolumeDiscountModel.id == scale_id,
            )
        )
        return _scale(row) if row else None

    async def insert_volume_discount(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        product_id: int,
        variant_id: uuid.UUID | None,
        unit_id: int,
        min_quantity: Decimal,
        discount_percent: Decimal,
        valid_from: date,
        actor_id: uuid.UUID,
    ) -> uuid.UUID:
        row = SalesVolumeDiscountModel(
            company_id=company_id,
            price_list_id=list_id,
            product_id=product_id,
            variant_id=variant_id,
            unit_id=unit_id,
            min_quantity=min_quantity,
            discount_percent=discount_percent,
            valid_from=valid_from,
            created_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def set_volume_valid_to(self, scale_id: uuid.UUID, valid_to: date | None) -> None:
        await self._session.execute(
            update(SalesVolumeDiscountModel)
            .where(SalesVolumeDiscountModel.id == scale_id)
            .values(valid_to=valid_to)
        )
        await self._session.flush()

    async def delete_volume_discount(self, scale_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(SalesVolumeDiscountModel).where(SalesVolumeDiscountModel.id == scale_id)
        )
        await self._session.flush()

    async def customer_discount(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Decimal | None:
        value = await self._session.scalar(
            select(SalesCustomerModel.discount_percent).where(
                SalesCustomerModel.company_id == company_id,
                SalesCustomerModel.id == customer_id,
            )
        )
        return Decimal(value) if value is not None else None
