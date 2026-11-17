"""Puerto de escalas por volumen y topes de descuento por rol (bloque V2c)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.sales_margin import DiscountPolicy


@dataclass(frozen=True, slots=True)
class RolePolicy:
    role_id: uuid.UUID
    role_name: str
    policy: DiscountPolicy | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class VolumeDiscount:
    id: uuid.UUID
    price_list_id: uuid.UUID
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    min_quantity: Decimal
    discount_percent: Decimal
    valid_from: date
    valid_to: date | None


class SalesDiscountRepository(Protocol):
    async def role_policies(self, company_id: uuid.UUID) -> list[RolePolicy]: ...

    async def role_in_company(self, company_id: uuid.UUID, role_id: uuid.UUID) -> bool: ...

    async def save_policy(
        self, company_id: uuid.UUID, role_id: uuid.UUID, policy: DiscountPolicy, actor_id: uuid.UUID
    ) -> None: ...

    async def user_policies(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[bool, list[DiscountPolicy]]:
        """(es superusuario, políticas de sus roles en la empresa)."""
        ...

    async def volume_discounts(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        *,
        product_id: int | None = None,
        variant_id: uuid.UUID | None = None,
        unit_id: int | None = None,
    ) -> list[VolumeDiscount]: ...

    async def get_volume_discount(
        self, company_id: uuid.UUID, scale_id: uuid.UUID
    ) -> VolumeDiscount | None: ...

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
    ) -> uuid.UUID: ...

    async def set_volume_valid_to(self, scale_id: uuid.UUID, valid_to: date | None) -> None: ...

    async def delete_volume_discount(self, scale_id: uuid.UUID) -> None: ...

    async def customer_discount(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Decimal | None:
        """Descuento fijo del cliente, o ``None`` si el cliente no existe."""
        ...
