"""Piezas comunes de los documentos de venta (cotización y pedido)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LineIdentity:
    """Lo que identifica al artículo vendido y su unidad, copiado al momento de cotizar."""

    product_id: int
    variant_id: uuid.UUID | None
    inventory_item_id: uuid.UUID
    packaging_definition_id: uuid.UUID | None
    packaging_version: int | None
    unit_id: int
    base_unit_id: int
    unit_factor: Decimal
    product_sku: str
    product_name: str
    unit_name: str
    base_unit_name: str


@dataclass(slots=True)
class DocumentLine:
    identity: LineIdentity
    quantity: Decimal
    quantity_base: Decimal
    price_list_id: uuid.UUID | None
    list_price: Decimal | None
    price_overridden: bool
    unit_price: Decimal
    discount_percent: Decimal
    suggested_discount_percent: Decimal
    suggested_discount_source: str
    tax_treatment: str
    item_type: str
    document_unit_price: Decimal
    discount_amount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat_item: Decimal | None
    line_total: Decimal
    cost: Decimal | None
    margin_percent: Decimal | None
    authorization_reasons: tuple[str, ...]
    id: uuid.UUID | None = None


@dataclass(slots=True)
class DocumentTotals:
    total_not_subject: Decimal
    total_exempt: Decimal
    total_taxed: Decimal
    subtotal_sales: Decimal
    total_discount: Decimal
    subtotal: Decimal
    vat: Decimal
    vat_perceived: Decimal
    vat_withheld: Decimal
    total: Decimal
    total_in_words: str


class SalesCatalog(Protocol):
    """Lo que el cálculo de un documento necesita del catálogo y de la empresa."""

    async def line_identity(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID | None, unit_id: int
    ) -> LineIdentity: ...

    async def branch_is_active(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool: ...
