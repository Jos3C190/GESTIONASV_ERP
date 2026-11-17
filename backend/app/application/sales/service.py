"""Application service for the base sales workflow (no stock movements)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.application.audit.audit_service import AuditService
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.sales import (
    PRICE_QUANTUM,
    line_amount,
    normalize_price,
    normalize_quantity,
    quantity_in_base,
)
from app.domain.entities.sales_quotation import QuotationStatus
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryItemModel, InventoryPackagingModel
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.sales import (
    SaleLineModel,
    SaleModel,
    SalesCustomerModel,
    SalesIdempotencyModel,
    SalesQuotationLineModel,
    SalesQuotationModel,
)
from app.infrastructure.models.sales_delivery import SalesDeliveryLineModel, SalesDeliveryModel
from app.infrastructure.repositories.sales_line_identity import unit_label, unit_name, unit_symbol
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

SV_TZ = ZoneInfo("America/El_Salvador")
ZERO_MONEY = Decimal("0.00")
IDEMPOTENCY_KEY_MAX_LENGTH = 120


def local_today() -> date:
    return datetime.now(SV_TZ).date()


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _decimal_string(value: Decimal | int | None) -> str | None:
    return str(value) if value is not None else None


class SalesService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    async def _audit(
        self,
        *,
        action: str,
        actor_id: uuid.UUID,
        company_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        request: Any,
        branch_id: uuid.UUID | None = None,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
    ) -> None:
        await self.audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type=resource_type,
            resource_id=str(resource_id),
            before_state=before,
            after_state=after,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            required=True,
        )

    @staticmethod
    def _quote_state(row: SalesQuotationModel) -> dict[str, object]:
        return {
            "id": str(row.id),
            "code": row.code,
            "company_id": str(row.company_id),
            "branch_id": str(row.branch_id),
            "customer_id": str(row.customer_id),
            "valid_until": row.valid_until.isoformat(),
            "currency": row.currency,
            "subtotal": str(row.subtotal),
            "total": str(row.total),
            "status": row.status,
            "version": row.version,
        }

    @staticmethod
    def _sale_state(row: SaleModel) -> dict[str, object]:
        return {
            "id": str(row.id),
            "code": row.code,
            "company_id": str(row.company_id),
            "branch_id": str(row.branch_id),
            "customer_id": str(row.customer_id),
            "quotation_id": str(row.quotation_id) if row.quotation_id else None,
            "currency": row.currency,
            "subtotal": str(row.subtotal),
            "total": str(row.total),
            "status": row.status,
            "version": row.version,
        }

    async def get_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> SalesCustomerModel:
        row = await self.session.scalar(
            select(SalesCustomerModel).where(
                SalesCustomerModel.company_id == company_id, SalesCustomerModel.id == customer_id
            )
        )
        if row is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        return row

    async def catalog(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        products = list(
            (
                await self.session.scalars(
                    select(ProductModel)
                    .where(
                        ProductModel.company_id == company_id,
                        ProductModel.is_active.is_(True),
                        ProductModel.can_sell.is_(True),
                        ProductModel.product_kind == "goods",
                        ProductModel.lifecycle_status == "active",
                        ProductModel.deleted_at.is_(None),
                    )
                    .order_by(ProductModel.name)
                )
            ).all()
        )
        result: list[dict[str, Any]] = []
        for product in products:
            if product.variant_mode == "standalone":
                item = await self.session.scalar(
                    select(InventoryItemModel).where(
                        InventoryItemModel.company_id == company_id,
                        InventoryItemModel.product_id == product.id_product,
                        InventoryItemModel.is_active.is_(True),
                    )
                )
                if item:
                    result.append(await self._catalog_option(product, None, item))
                continue
            variants = list(
                (
                    await self.session.scalars(
                        select(ProductVariantModel)
                        .where(
                            ProductVariantModel.company_id == company_id,
                            ProductVariantModel.product_id == product.id_product,
                            ProductVariantModel.is_active.is_(True),
                            ProductVariantModel.lifecycle_status == "active",
                        )
                        .order_by(ProductVariantModel.sku)
                    )
                ).all()
            )
            for variant in variants:
                item = await self.session.scalar(
                    select(InventoryItemModel).where(
                        InventoryItemModel.company_id == company_id,
                        InventoryItemModel.variant_id == variant.id,
                        InventoryItemModel.is_active.is_(True),
                    )
                )
                if item:
                    result.append(await self._catalog_option(product, variant, item))
        return result

    async def _catalog_option(
        self, product: ProductModel, variant: ProductVariantModel | None, item: InventoryItemModel
    ) -> dict[str, Any]:
        units: list[dict[str, Any]] = []
        package_rows = list(
            (
                await self.session.scalars(
                    select(InventoryPackagingModel)
                    .where(
                        InventoryPackagingModel.company_id == item.company_id,
                        InventoryPackagingModel.inventory_item_id == item.id,
                        InventoryPackagingModel.is_current.is_(True),
                        InventoryPackagingModel.is_active.is_(True),
                    )
                    .order_by(InventoryPackagingModel.name)
                )
            ).all()
        )
        base_unit = await unit_name(self.session, item.company_id, item.base_unit_id)
        units.append(
            {
                "unit_id": item.base_unit_id,
                "name": base_unit,
                "factor": "1",
                "packaging_definition_id": None,
                "packaging_version": None,
            }
        )
        for package in package_rows:
            if package.packaging_unit_id is None:
                continue
            symbol = await unit_symbol(self.session, item.company_id, package.packaging_unit_id)
            units.append(
                {
                    "unit_id": package.packaging_unit_id,
                    "name": unit_label(package.name, symbol),
                    "factor": str(package.base_quantity),
                    "packaging_definition_id": str(package.id),
                    "packaging_version": package.version,
                }
            )
        display_name = (
            (variant.name_override if variant and variant.name_override else None)
            or product.sales_name
            or product.name
        )
        return {
            "product_id": product.id_product,
            "variant_id": str(variant.id) if variant else None,
            "inventory_item_id": str(item.id),
            "sku": variant.sku if variant else product.sku,
            "name": display_name,
            "base_unit_id": item.base_unit_id,
            "base_unit_name": base_unit,
            "units": units,
        }

    async def _idempotency(
        self, company_id: uuid.UUID, action: str, key: str, fingerprint: str
    ) -> SalesIdempotencyModel | None:
        row = await self.session.scalar(
            select(SalesIdempotencyModel)
            .where(
                SalesIdempotencyModel.company_id == company_id,
                SalesIdempotencyModel.action == action,
                SalesIdempotencyModel.idempotency_key == key,
            )
            .with_for_update()
        )
        if row is not None and row.fingerprint != fingerprint:
            raise ConflictError(
                "La clave de idempotencia ya se usó con otro contenido.",
                code="sales_idempotency_payload_conflict",
            )
        return row

    async def _lock_idempotency(self, company_id: uuid.UUID, action: str, key: str) -> None:
        lock_value = f"{company_id}:{action}:{key}"
        await self.session.scalar(select(func.pg_advisory_xact_lock(func.hashtext(lock_value))))

    async def get_quotation(
        self, company_id: uuid.UUID, quote_id: uuid.UUID, *, lock: bool = False
    ) -> SalesQuotationModel:
        statement = select(SalesQuotationModel).where(
            SalesQuotationModel.company_id == company_id, SalesQuotationModel.id == quote_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError(
                "Cotización de venta no encontrada.", code="sales_quotation_not_found"
            )
        return row

    @staticmethod
    def _line_out(
        line: SalesQuotationLineModel | SaleLineModel,
        quantity_delivered_base: Decimal = ZERO_MONEY,
    ) -> dict[str, Any]:
        quantity_quantum = Decimal("0.000001")
        delivered = min(
            max(Decimal(quantity_delivered_base), ZERO_MONEY), Decimal(line.quantity_base)
        )
        pending = max(ZERO_MONEY, Decimal(line.quantity_base) - delivered)
        return {
            "id": str(line.id),
            "source_quotation_line_id": str(getattr(line, "source_quotation_line_id", line.id)),
            "product_id": line.product_id,
            "variant_id": str(line.variant_id) if line.variant_id else None,
            "inventory_item_id": str(line.inventory_item_id),
            "product_sku": line.product_sku,
            "product_name": line.product_name,
            "unit_id": line.unit_id,
            "unit_name": line.unit_name,
            "base_unit_id": line.base_unit_id,
            "base_unit_name": line.base_unit_name,
            "unit_factor": str(line.unit_factor),
            "quantity": str(line.quantity),
            "quantity_base": str(line.quantity_base),
            "unit_price": str(line.unit_price),
            "line_total": str(line.line_total),
            "quantity_delivered_base": str(delivered.quantize(quantity_quantum)),
            "quantity_pending_base": str(pending.quantize(quantity_quantum)),
        }

    async def convert_quotation(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quote_id: uuid.UUID,
        expected_version: int,
        idempotency_key: str,
        request: Any,
    ) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise ValidationError(
                "La clave de idempotencia es obligatoria y admite hasta 120 caracteres.",
                code="sales_idempotency_key_required",
            )
        fingerprint = _fingerprint(
            {"quotation_id": str(quote_id), "expected_version": expected_version}
        )
        async with self.session.begin_nested():
            row = await self.get_quotation(company_id, quote_id, lock=True)
            await self._lock_idempotency(company_id, "convert_quote", idempotency_key)
            replay = await self._idempotency(
                company_id, "convert_quote", idempotency_key, fingerprint
            )
            if replay:
                sale = await self.get_sale(company_id, replay.resource_id)
                return await self.sale_out(sale)
            existing = await self.session.scalar(
                select(SaleModel)
                .where(SaleModel.company_id == company_id, SaleModel.quotation_id == quote_id)
                .with_for_update()
            )
            if existing:
                # A conversion is unique by origin, even when the client retries with a new key.
                self.session.add(
                    SalesIdempotencyModel(
                        company_id=company_id,
                        action="convert_quote",
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="sale",
                        resource_id=existing.id,
                        actor_id=actor_id,
                    )
                )
                await self.session.flush()
                return await self.sale_out(existing)
            if row.version != expected_version:
                raise ConflictError(
                    "La cotización cambió. Recárguela antes de convertir.",
                    code="sales_quote_version_conflict",
                )
            if row.status != QuotationStatus.ACCEPTED.value:
                raise BusinessRuleError(
                    "Solo una cotización aceptada por el cliente puede convertirse en venta.",
                    code="sales_quote_not_convertible",
                )
            customer = await self.get_customer(company_id, row.customer_id)
            if not customer.is_active:
                raise BusinessRuleError(
                    "El cliente está inactivo y no se puede convertir la cotización.",
                    code="sales_customer_inactive",
                )
            quote_lines = list(
                (
                    await self.session.scalars(
                        select(SalesQuotationLineModel)
                        .where(
                            SalesQuotationLineModel.company_id == company_id,
                            SalesQuotationLineModel.quotation_id == quote_id,
                        )
                        .order_by(SalesQuotationLineModel.line_number)
                    )
                ).all()
            )
            if not quote_lines:
                raise BusinessRuleError(
                    "La cotización no contiene líneas.", code="sales_quote_lines_required"
                )
            # La venta B06 no lleva impuestos ni descuento global: copia el neto de cada línea
            # (precio con descuento en la forma del documento). V2e la reemplaza por el pedido.
            net_lines = [(line, line_amount(Decimal("1"), line.line_total)) for line in quote_lines]
            sale_total = sum((amount for _, amount in net_lines), ZERO_MONEY)
            sale = SaleModel(
                company_id=company_id,
                branch_id=row.branch_id,
                customer_id=row.customer_id,
                quotation_id=row.id,
                code=f"VTA-{local_today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
                currency=row.currency,
                subtotal=sale_total,
                total=sale_total,
                status="draft",
                version=1,
                notes=row.notes,
                created_by_id=actor_id,
            )
            self.session.add(sale)
            await self.session.flush()
            for line, net_total in net_lines:
                self.session.add(
                    SaleLineModel(
                        company_id=company_id,
                        sale_id=sale.id,
                        source_quotation_line_id=line.id,
                        line_number=line.line_number,
                        product_id=line.product_id,
                        variant_id=line.variant_id,
                        inventory_item_id=line.inventory_item_id,
                        packaging_definition_id=line.packaging_definition_id,
                        packaging_version=line.packaging_version,
                        unit_id=line.unit_id,
                        base_unit_id=line.base_unit_id,
                        unit_factor=line.unit_factor,
                        quantity=line.quantity,
                        quantity_base=line.quantity_base,
                        product_sku=line.product_sku,
                        product_name=line.product_name,
                        unit_name=line.unit_name,
                        base_unit_name=line.base_unit_name,
                        unit_price=(line.line_total / line.quantity).quantize(PRICE_QUANTUM),
                        line_total=net_total,
                    )
                )
            self.session.add(
                SalesIdempotencyModel(
                    company_id=company_id,
                    action="convert_quote",
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="sale",
                    resource_id=sale.id,
                    actor_id=actor_id,
                )
            )
            await self.session.flush()
            await self._audit(
                action="SALES_QUOTATION_CONVERTED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=row.branch_id,
                resource_type="sales_quotation",
                resource_id=row.id,
                request=request,
                before=self._quote_state(row),
                after={**self._quote_state(row), "sale_id": str(sale.id), "sale_code": sale.code},
            )
            await self._audit(
                action="SALES_DRAFT_CREATED_FROM_QUOTATION",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                resource_type="sale",
                resource_id=sale.id,
                request=request,
                after=self._sale_state(sale),
            )
        return await self.sale_out(sale)

    async def list_sales(
        self,
        company_id: uuid.UUID,
        *,
        branch_ids: tuple[uuid.UUID, ...] | None,
        branch_id: uuid.UUID | None,
        customer_id: uuid.UUID | None,
        status: str | None,
        from_date: date | None,
        to_date: date | None,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        conditions: list[Any] = [SaleModel.company_id == company_id]
        if branch_id:
            conditions.append(SaleModel.branch_id == branch_id)
        elif branch_ids is not None:
            conditions.append(
                SaleModel.branch_id.in_(branch_ids) if branch_ids else SaleModel.id.is_(None)
            )
        if customer_id:
            conditions.append(SaleModel.customer_id == customer_id)
        if status:
            conditions.append(SaleModel.status == status)
        if from_date:
            conditions.append(func.date(SaleModel.created_at) >= from_date)
        if to_date:
            conditions.append(func.date(SaleModel.created_at) <= to_date)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(SaleModel).where(*conditions)
            )
            or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    select(SaleModel)
                    .where(*conditions)
                    .order_by(SaleModel.created_at.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )
        return {
            "items": [await self.sale_out(row) for row in rows],
            "meta": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size,
            },
        }

    async def get_sale(
        self, company_id: uuid.UUID, sale_id: uuid.UUID, *, lock: bool = False
    ) -> SaleModel:
        statement = select(SaleModel).where(
            SaleModel.company_id == company_id, SaleModel.id == sale_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError("Venta no encontrada.", code="sales_sale_not_found")
        return row

    async def sale_out(self, row: SaleModel) -> dict[str, Any]:
        lines = list(
            (
                await self.session.scalars(
                    select(SaleLineModel)
                    .where(
                        SaleLineModel.company_id == row.company_id, SaleLineModel.sale_id == row.id
                    )
                    .order_by(SaleLineModel.line_number)
                )
            ).all()
        )
        customer = await self.get_customer(row.company_id, row.customer_id)
        quote = (
            await self.get_quotation(row.company_id, row.quotation_id) if row.quotation_id else None
        )
        delivered_rows = (
            await self.session.execute(
                select(
                    SalesDeliveryLineModel.sale_line_id,
                    func.sum(SalesDeliveryLineModel.quantity_base),
                )
                .join(
                    SalesDeliveryModel,
                    (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                    & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                )
                .where(
                    SalesDeliveryModel.company_id == row.company_id,
                    SalesDeliveryModel.sale_id == row.id,
                    SalesDeliveryModel.status == "confirmed",
                )
                .group_by(SalesDeliveryLineModel.sale_line_id)
            )
        ).all()
        delivered_by_line = {
            line_id: Decimal(quantity or ZERO_MONEY) for line_id, quantity in delivered_rows
        }
        delivered_total = sum(delivered_by_line.values(), ZERO_MONEY)
        sold_total = sum((Decimal(line.quantity_base) for line in lines), ZERO_MONEY)
        delivery_progress = (
            "pending"
            if delivered_total <= ZERO_MONEY
            else "complete"
            if delivered_total >= sold_total
            else "partial"
        )
        return {
            "id": str(row.id),
            "company_id": str(row.company_id),
            "branch_id": str(row.branch_id),
            "customer_id": str(row.customer_id),
            "customer_code": customer.code,
            "customer_name": customer.name,
            "quotation_id": str(row.quotation_id) if row.quotation_id else None,
            "quotation_code": quote.code if quote else None,
            "code": row.code,
            "currency": row.currency,
            "subtotal": str(row.subtotal),
            "total": str(row.total),
            "status": row.status,
            "version": row.version,
            "notes": row.notes,
            "delivery_progress": delivery_progress,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "lines": [
                self._line_out(line, delivered_by_line.get(line.id, ZERO_MONEY)) for line in lines
            ],
        }

    async def confirm_sale(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale_id: uuid.UUID,
        expected_version: int,
        request: Any,
    ) -> dict[str, Any]:
        async with self.session.begin_nested():
            row = await self.get_sale(company_id, sale_id, lock=True)
            if row.status == "confirmed":
                return await self.sale_out(row)
            if row.status != "draft":
                raise BusinessRuleError(
                    "Solo se puede confirmar una venta en borrador.",
                    code="sales_sale_state_invalid",
                )
            if row.version != expected_version:
                raise ConflictError(
                    "La venta cambió. Recárguela antes de confirmar.",
                    code="sales_sale_version_conflict",
                )
            customer = await self.get_customer(company_id, row.customer_id)
            if not customer.is_active:
                raise BusinessRuleError(
                    "El cliente está inactivo y no se puede confirmar la venta.",
                    code="sales_customer_inactive",
                )
            lines = int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(SaleLineModel)
                    .where(SaleLineModel.company_id == company_id, SaleLineModel.sale_id == sale_id)
                )
                or 0
            )
            if not lines:
                raise BusinessRuleError(
                    "La venta no contiene líneas.", code="sales_sale_lines_required"
                )
            before = self._sale_state(row)
            row.status = "confirmed"
            row.confirmed_by_id = actor_id
            row.confirmed_at = datetime.now(UTC)
            row.version += 1
            await self.session.flush()
            await self._audit(
                action="SALE_CONFIRMED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=row.branch_id,
                resource_type="sale",
                resource_id=row.id,
                request=request,
                before=before,
                after=self._sale_state(row),
            )
        return await self.sale_out(row)

    async def update_sale(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale_id: uuid.UUID,
        data: dict[str, Any],
        request: Any,
    ) -> dict[str, Any]:
        async with self.session.begin_nested():
            row = await self.get_sale(company_id, sale_id, lock=True)
            if row.status != "draft":
                raise BusinessRuleError(
                    "Solo se puede editar una venta en borrador.", code="sales_sale_state_invalid"
                )
            if row.version != int(data["expected_version"]):
                raise ConflictError(
                    "La venta cambió. Recárguela antes de editar.",
                    code="sales_sale_version_conflict",
                )
            customer = await self.get_customer(company_id, row.customer_id)
            if not customer.is_active:
                raise BusinessRuleError(
                    "El cliente está inactivo y no se puede editar la venta.",
                    code="sales_customer_inactive",
                )
            lines = list(
                (
                    await self.session.scalars(
                        select(SaleLineModel)
                        .where(
                            SaleLineModel.company_id == company_id, SaleLineModel.sale_id == sale_id
                        )
                        .order_by(SaleLineModel.line_number)
                        .with_for_update()
                    )
                ).all()
            )
            updates = data.get("lines") or []
            by_source = {line.source_quotation_line_id: line for line in lines}
            received_ids = [uuid.UUID(str(item["source_quotation_line_id"])) for item in updates]
            if len(set(received_ids)) != len(received_ids) or set(received_ids) != set(by_source):
                raise ValidationError(
                    "Conserve todas las líneas de origen de la cotización y envíe cada una una sola vez.",
                    code="sales_source_lines_mismatch",
                )
            before = self._sale_state(row)
            for item in updates:
                source_id = uuid.UUID(str(item["source_quotation_line_id"]))
                line = by_source[source_id]
                quantity = normalize_quantity(Decimal(str(item["quantity"])))
                price = normalize_price(Decimal(str(item["unit_price"])))
                quantity_base = quantity_in_base(quantity, line.unit_factor)
                line.quantity = quantity
                line.quantity_base = quantity_base
                line.unit_price = price
                line.line_total = line_amount(quantity, price)
            row.subtotal = sum((line.line_total for line in lines), ZERO_MONEY)
            row.total = row.subtotal
            row.notes = str(data.get("notes") or "").strip() or None
            row.version += 1
            await self.session.flush()
            await self._audit(
                action="SALE_DRAFT_UPDATED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=row.branch_id,
                resource_type="sale",
                resource_id=row.id,
                request=request,
                before=before,
                after=self._sale_state(row),
            )
        return await self.sale_out(row)

    async def cancel_sale(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale_id: uuid.UUID,
        expected_version: int,
        reason: str,
        request: Any,
    ) -> dict[str, Any]:
        reason = reason.strip()
        if not reason:
            raise ValidationError(
                "Indique el motivo de cancelación.", code="sales_cancellation_reason_required"
            )
        async with self.session.begin_nested():
            row = await self.get_sale(company_id, sale_id, lock=True)
            if row.status == "cancelled":
                if row.cancellation_reason == reason:
                    return await self.sale_out(row)
                raise ConflictError(
                    "La venta ya se canceló con otro motivo.", code="sales_sale_already_cancelled"
                )
            if row.version != expected_version:
                raise ConflictError(
                    "La venta cambió. Recárguela antes de cancelar.",
                    code="sales_sale_version_conflict",
                )
            if row.status not in {"draft", "confirmed"}:
                raise BusinessRuleError(
                    "El estado actual no permite cancelar la venta.",
                    code="sales_sale_state_invalid",
                )
            has_confirmed_delivery = await self.session.scalar(
                select(SalesDeliveryModel.id)
                .where(
                    SalesDeliveryModel.company_id == company_id,
                    SalesDeliveryModel.sale_id == sale_id,
                    SalesDeliveryModel.status == "confirmed",
                )
                .limit(1)
            )
            if has_confirmed_delivery is not None:
                raise BusinessRuleError(
                    "La venta ya tiene una entrega confirmada y no se puede cancelar. Registre la devolución desde el flujo correspondiente.",
                    code="sales_sale_has_confirmed_delivery",
                )
            before = self._sale_state(row)
            row.status = "cancelled"
            row.cancelled_by_id = actor_id
            row.cancelled_at = datetime.now(UTC)
            row.cancellation_reason = reason
            row.version += 1
            await self.session.flush()
            await self._audit(
                action="SALE_CANCELLED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=row.branch_id,
                resource_type="sale",
                resource_id=row.id,
                request=request,
                before=before,
                after={**self._sale_state(row), "cancellation_reason": reason, "delivery_count": 0},
            )
        return await self.sale_out(row)
