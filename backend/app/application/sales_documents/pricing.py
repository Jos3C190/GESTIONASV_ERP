"""Cálculo común de los documentos de venta: cotización (V2d) y pedido (V2e).

Para cada línea:
1. resuelve la lista y el precio (V2b), el descuento sugerido y el costo (V2c);
2. aplica el precio manual si quien guarda tiene permiso;
3. calcula impuestos y totales con el motor fiscal (V2a) y evalúa el tope del usuario;
4. marca las líneas que quedan bajo el costo: no se pueden guardar ni confirmar así.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.sales_discounts import LineRequest, SalesDiscountUseCases
from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.customer import Customer, CustomerType
from app.domain.entities.product_fiscal import DteItemType, TaxTreatment
from app.domain.entities.sales import normalize_quantity, quantity_in_base
from app.domain.entities.sales_margin import DiscountPolicy, DiscountSource
from app.domain.entities.sales_quotation import (
    QuoteCalculation,
    QuoteLineInput,
    calculate_quote,
    require_price_override_allowed,
)
from app.domain.entities.sales_tax import SalesDocumentKind, TaxParties, line_round
from app.domain.ports.customer_repository import CustomerRepository
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.product_fiscal_repository import ProductFiscalRepository
from app.domain.ports.sales_document import DocumentLine, DocumentTotals, SalesCatalog

PriceKey = tuple[int, uuid.UUID | None, int]


@dataclass(frozen=True, slots=True)
class DraftLine:
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    quantity: Decimal
    discount_percent: Decimal | None = None
    """Si falta, se aplica el descuento sugerido (cliente o volumen)."""
    manual_price: Decimal | None = None
    """Precio escrito a mano, en la forma de la lista; exige ``sales_prices:override``."""


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: uuid.UUID
    can_override_price: bool = False


@dataclass(frozen=True, slots=True)
class PricingRequest:
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    lines: tuple[DraftLine, ...]
    document_type: str | None = None
    """``01`` o ``03``; si falta, se propone según el cliente."""
    global_discount_percent: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PricedDocument:
    customer: Customer
    document: SalesDocumentKind
    prices_include_vat: bool
    price_list_id: uuid.UUID | None
    lines: list[DocumentLine]
    calculation: QuoteCalculation

    @property
    def totals(self) -> DocumentTotals:
        return totals_of(self.calculation)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(r.value for r in self.calculation.reasons)


def totals_of(calculation: QuoteCalculation) -> DocumentTotals:
    summary = calculation.tax.summary
    return DocumentTotals(
        total_not_subject=summary.total_not_subject,
        total_exempt=summary.total_exempt,
        total_taxed=summary.total_taxed,
        subtotal_sales=summary.subtotal_sales,
        total_discount=summary.total_discount,
        subtotal=summary.subtotal,
        vat=summary.vat,
        vat_perceived=summary.vat_perceived,
        vat_withheld=summary.vat_withheld,
        total=summary.total_to_pay,
        total_in_words=summary.total_in_words,
    )


class SalesDocumentPricing:
    def __init__(
        self,
        catalog: SalesCatalog,
        discounts: SalesDiscountUseCases,
        fiscal: FiscalRepository,
        customers: CustomerRepository,
        products: ProductFiscalRepository,
    ) -> None:
        self._catalog = catalog
        self._discounts = discounts
        self._fiscal = fiscal
        self._customers = customers
        self._products = products

    async def policy(self, company_id: uuid.UUID, user_id: uuid.UUID) -> DiscountPolicy:
        return await self._discounts.user_policy(company_id, user_id)

    async def active_customer(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        customer = await self._customers.get_customer(company_id, customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        if not customer.is_active:
            raise BusinessRuleError(
                "El cliente está inactivo y no admite nuevos documentos de venta.",
                code="sales_customer_inactive",
            )
        return customer

    async def _document(
        self, company_id: uuid.UUID, customer: Customer, requested: str | None
    ) -> SalesDocumentKind:
        enabled = {
            s.document_type
            for s in await self._fiscal.list_document_types(company_id)
            if s.is_enabled
        }
        receivable = set(customer.receivable_documents)
        if requested is None:
            for candidate in (SalesDocumentKind.TAX_CREDIT, SalesDocumentKind.INVOICE):
                if candidate.value in enabled and candidate.value in receivable:
                    return candidate
            raise BusinessRuleError(
                "La empresa no tiene habilitada la factura ni el crédito fiscal. Habilítalos en "
                "Configuración fiscal → Documentos.",
                code="sales_tax_document_disabled",
            )
        if requested not in {k.value for k in SalesDocumentKind}:
            raise ValidationError("El documento debe ser 01 o 03.", code="sales_document_invalid")
        if requested not in enabled:
            raise BusinessRuleError(
                "La empresa no tiene habilitado este tipo de documento.",
                code="sales_tax_document_disabled",
            )
        if requested not in receivable:
            missing = customer.tax_credit_missing
            detail = f" Falta: {' '.join(missing)}" if missing else ""
            raise BusinessRuleError(
                f"A este cliente no se le puede emitir ese documento.{detail}",
                code="sales_tax_document_not_receivable",
            )
        return SalesDocumentKind(requested)

    async def _parties(self, company_id: uuid.UUID, customer: Customer) -> TaxParties:
        profile = await self._fiscal.get_profile(company_id)
        return TaxParties(
            issuer_category=profile.taxpayer_category,
            customer_is_taxpayer=customer.draft.customer_type == CustomerType.TAXPAYER,
            customer_category=customer.draft.taxpayer_category,
            customer_is_withholding_agent=customer.draft.is_withholding_agent,
        )

    async def _fiscal_class(
        self, company_id: uuid.UUID, product_id: int, position: int
    ) -> tuple[TaxTreatment, DteItemType]:
        product = await self._products.get_product(company_id, product_id)
        if product is None:
            raise NotFoundError(
                f"El producto de la línea {position} no existe.", code="product_not_found"
            )
        if not product.can_sell:
            raise BusinessRuleError(
                f"«{product.name}» no está marcado como vendible.",
                code="sales_tax_product_not_sellable",
            )
        return product.tax_treatment, product.effective_item_type

    @staticmethod
    def _quantities(lines: tuple[DraftLine, ...]) -> list[Decimal]:
        quantities = []
        for position, line in enumerate(lines, start=1):
            try:
                quantities.append(normalize_quantity(line.quantity))
            except ValueError as error:
                raise ValidationError(
                    f"Línea {position}: {error}", code="sales_quantity_invalid"
                ) from error
        return quantities

    async def price(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        request: PricingRequest,
        today: date,
        *,
        kept_prices: dict[PriceKey, Decimal] | None = None,
    ) -> PricedDocument:
        """Precios, descuentos, impuestos y motivos de autorización de un borrador."""

        if not request.lines:
            raise ValidationError("Agrega al menos un producto.", code="sales_lines_required")
        if not await self._catalog.branch_is_active(company_id, request.branch_id):
            raise BusinessRuleError(
                "La sucursal no está activa para vender.", code="sales_branch_inactive"
            )
        customer = await self.active_customer(company_id, request.customer_id)
        document = await self._document(company_id, customer, request.document_type)
        parties = await self._parties(company_id, customer)
        quantities = self._quantities(request.lines)
        evaluation = await self._discounts.evaluate(
            company_id,
            actor.user_id,
            customer_id=customer.id,
            branch_id=request.branch_id,
            on=today,
            lines=[
                LineRequest(
                    line.product_id, line.variant_id, line.unit_id, quantity, line.discount_percent
                )
                for line, quantity in zip(request.lines, quantities, strict=True)
            ],
            global_discount_percent=request.global_discount_percent,
        )
        price_list = next((e.price_list for e in evaluation.lines if e.price_list), None)
        include_vat = (
            price_list.prices_include_vat
            if price_list is not None
            else document is SalesDocumentKind.INVOICE
        )

        inputs: list[QuoteLineInput] = []
        identities = []
        for position, (line, quantity, evaluated) in enumerate(
            zip(request.lines, quantities, evaluation.lines, strict=True), start=1
        ):
            treatment, item_type = await self._fiscal_class(company_id, line.product_id, position)
            suggested = evaluated.suggested
            if evaluated.promotion is not None:
                # En promoción el descuento es el de la promoción; el del vendedor no cuenta.
                discount = evaluated.promotion.discount_percent
            elif line.discount_percent is not None:
                discount = line.discount_percent
            else:
                discount = suggested.percent if suggested else Decimal("0")
            item = QuoteLineInput(
                quantity=quantity,
                list_price=evaluated.evaluation.list_price if evaluated.evaluation else None,
                manual_price=line.manual_price,
                discount_percent=discount,
                tax_treatment=treatment,
                item_type=item_type,
                cost=evaluated.cost,
                suggested_discount_percent=suggested.percent if suggested else Decimal("0"),
                suggested_discount_source=suggested.source if suggested else DiscountSource.NONE,
            )
            kept = (kept_prices or {}).get((line.product_id, line.variant_id, line.unit_id))
            require_price_override_allowed(
                item, actor.can_override_price or kept == line.manual_price
            )
            inputs.append(item)
            identities.append(
                await self._catalog.line_identity(
                    company_id, line.product_id, line.variant_id, line.unit_id
                )
            )

        calculation = calculate_quote(
            document,
            include_vat,
            inputs,
            parties,
            request.global_discount_percent,
            evaluation.policy,
        )
        lines = []
        for identity, item, result, evaluated in zip(
            identities, inputs, calculation.lines, evaluation.lines, strict=True
        ):
            try:
                quantity_base = quantity_in_base(item.quantity, identity.unit_factor)
            except ValueError as error:
                raise ValidationError(str(error), code="sales_quantity_invalid") from error
            lines.append(
                DocumentLine(
                    identity=identity,
                    quantity=item.quantity,
                    quantity_base=quantity_base,
                    price_list_id=evaluated.price_list.id if evaluated.price_list else None,
                    list_price=item.list_price,
                    price_overridden=result.price_overridden,
                    unit_price=result.unit_price,
                    discount_percent=item.discount_percent,
                    suggested_discount_percent=item.suggested_discount_percent,
                    suggested_discount_source=item.suggested_discount_source.value,
                    tax_treatment=item.tax_treatment.value,
                    item_type=item.item_type.value,
                    document_unit_price=result.document_unit_price,
                    discount_amount=result.discount_amount,
                    not_subject=result.not_subject,
                    exempt=result.exempt,
                    taxed=result.taxed,
                    vat_item=result.vat_item,
                    line_total=result.line_total,
                    cost=item.cost,
                    margin_percent=result.margin_percent,
                    authorization_reasons=tuple(r.value for r in result.reasons)
                    + (("below_cost",) if result.below_cost else ()),
                )
            )
        return PricedDocument(
            customer=customer,
            document=document,
            prices_include_vat=include_vat,
            price_list_id=price_list.id if price_list else None,
            lines=lines,
            calculation=calculation,
        )

    async def reevaluate(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        document_type: str,
        prices_include_vat: bool,
        global_discount_percent: Decimal,
        lines: list[DocumentLine],
        policy: DiscountPolicy,
        *,
        current_costs: bool = False,
    ) -> QuoteCalculation:
        """Vuelve a evaluar lo guardado con el tope de otro usuario, sin tocar los precios.

        Con ``current_costs`` compara contra el costo vigente del kardex y no contra el guardado,
        para que confirmar nunca venda bajo un costo que subió después de cotizar.
        """

        customer = await self.active_customer(company_id, customer_id)
        parties = await self._parties(company_id, customer)
        costs = [line.cost for line in lines]
        if current_costs:
            unit_costs = await self._discounts.unit_costs(
                company_id, {line.identity.inventory_item_id for line in lines}
            )
            costs = [
                line_round(unit_costs[line.identity.inventory_item_id] * line.identity.unit_factor)
                if line.identity.inventory_item_id in unit_costs
                else line.cost
                for line in lines
            ]
        inputs = [
            QuoteLineInput(
                quantity=line.quantity,
                list_price=line.list_price,
                manual_price=line.unit_price if line.price_overridden else None,
                discount_percent=line.discount_percent,
                tax_treatment=TaxTreatment(line.tax_treatment),
                item_type=DteItemType(line.item_type),
                cost=cost,
                suggested_discount_percent=line.suggested_discount_percent,
                suggested_discount_source=DiscountSource(line.suggested_discount_source),
            )
            for line, cost in zip(lines, costs, strict=True)
        ]
        return calculate_quote(
            SalesDocumentKind(document_type),
            prices_include_vat,
            inputs,
            parties,
            global_discount_percent,
            policy,
        )
