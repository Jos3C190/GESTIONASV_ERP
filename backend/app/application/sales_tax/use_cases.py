"""Cálculo fiscal de un documento de venta con los datos de la empresa (bloque V2a).

Arma la entrada del motor con lo que ya está configurado: la categoría del emisor, los
datos fiscales del cliente y la clasificación de cada producto. Nada de eso lo decide
quien llama.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.customer import Customer, CustomerType
from app.domain.entities.sales_tax import (
    GlobalDiscounts,
    SalesDocumentKind,
    TaxCalculation,
    TaxLineInput,
    TaxParties,
    calculate,
)
from app.domain.ports.customer_repository import CustomerRepository
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.product_fiscal_repository import ProductFiscalRepository


@dataclass(frozen=True, slots=True)
class CalculationLine:
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    price_includes_vat: bool
    discount: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class CalculationRequest:
    document: SalesDocumentKind
    customer_id: uuid.UUID | None
    lines: tuple[CalculationLine, ...]
    discounts: GlobalDiscounts = field(default_factory=GlobalDiscounts)


@dataclass(frozen=True, slots=True)
class CalculatedLine:
    product_id: int
    sku: str
    name: str
    unit_code: str | None
    """Código de Hacienda (CAT-014) de la unidad de venta."""


@dataclass(frozen=True, slots=True)
class CalculationResult:
    calculation: TaxCalculation
    products: tuple[CalculatedLine, ...]
    customer_id: uuid.UUID | None
    customer_name: str | None


class SalesTaxUseCases:
    def __init__(
        self,
        fiscal: FiscalRepository,
        customers: CustomerRepository,
        products: ProductFiscalRepository,
    ) -> None:
        self._fiscal = fiscal
        self._customers = customers
        self._products = products

    async def _require_document_enabled(
        self, company_id: uuid.UUID, document: SalesDocumentKind
    ) -> None:
        settings = await self._fiscal.list_document_types(company_id)
        if not any(s.document_type == document.value and s.is_enabled for s in settings):
            raise BusinessRuleError(
                "La empresa no tiene habilitado este tipo de documento. Habilítalo en "
                "Configuración fiscal → Documentos.",
                code="sales_tax_document_disabled",
            )

    async def _customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID | None, document: SalesDocumentKind
    ) -> Customer | None:
        if customer_id is None:
            if document is SalesDocumentKind.TAX_CREDIT:
                raise BusinessRuleError(
                    "Elige el cliente contribuyente para el comprobante de crédito fiscal.",
                    code="sales_tax_customer_required",
                )
            return None
        customer = await self._customers.get_customer(company_id, customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        if not customer.is_active:
            raise BusinessRuleError(
                "El cliente está inactivo y no admite nuevas ventas.",
                code="sales_tax_customer_inactive",
            )
        if document.value not in customer.receivable_documents:
            missing = customer.tax_credit_missing
            detail = f" Falta: {' '.join(missing)}" if missing else ""
            raise BusinessRuleError(
                f"A este cliente no se le puede emitir ese documento.{detail}",
                code="sales_tax_document_not_receivable",
            )
        return customer

    async def calculate(
        self, company_id: uuid.UUID, request: CalculationRequest
    ) -> CalculationResult:
        await self._require_document_enabled(company_id, request.document)
        customer = await self._customer(company_id, request.customer_id, request.document)
        profile = await self._fiscal.get_profile(company_id)

        inputs: list[TaxLineInput] = []
        products: list[CalculatedLine] = []
        for position, line in enumerate(request.lines, start=1):
            product = await self._products.get_product(company_id, line.product_id)
            if product is None:
                raise NotFoundError(
                    f"El producto de la línea {position} no existe.", code="product_not_found"
                )
            if not product.can_sell:
                raise BusinessRuleError(
                    f"«{product.name}» no está marcado como vendible.",
                    code="sales_tax_product_not_sellable",
                )
            inputs.append(
                TaxLineInput(
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    price_includes_vat=line.price_includes_vat,
                    tax_treatment=product.tax_treatment,
                    item_type=product.effective_item_type,
                    discount=line.discount,
                    additional_taxes=tuple(tax.code for tax in product.additional_taxes),
                )
            )
            products.append(
                CalculatedLine(
                    product_id=product.product_id,
                    sku=product.sku,
                    name=product.name,
                    unit_code=product.sale_unit.effective_code if product.sale_unit else None,
                )
            )

        draft = customer.draft if customer else None
        parties = TaxParties(
            issuer_category=profile.taxpayer_category,
            customer_is_taxpayer=draft is not None and draft.customer_type == CustomerType.TAXPAYER,
            customer_category=draft.taxpayer_category if draft else None,
            customer_is_withholding_agent=draft.is_withholding_agent if draft else False,
        )
        calculation = calculate(request.document, inputs, parties, request.discounts)
        return CalculationResult(
            calculation=calculation,
            products=tuple(products),
            customer_id=customer.id if customer else None,
            customer_name=customer.draft.name if customer else None,
        )
