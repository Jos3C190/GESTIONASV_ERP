"""Pedido de venta (bloque V2e).

El pedido nace de una cotización aceptada (copia sus condiciones tal como se aceptaron) o se
arma directamente con el mismo cálculo de la cotización. Al confirmarlo aparta existencias de
la sucursal: si no alcanzan, no se confirma. Cancelar libera lo apartado.

Las condiciones de una cotización aceptada ya fueron autorizadas: el pedido que nace de ella y
no se edita conserva esa autorización. Si se edita, se recalcula y se vuelve a evaluar.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.price_lists import today_in_el_salvador
from app.application.sales_documents.pricing import (
    Actor,
    DraftLine,
    PriceKey,
    PricingRequest,
    SalesDocumentPricing,
    totals_of,
)
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.customer import Customer
from app.domain.entities.sales_credit import (
    credit_reasons,
    evaluate_credit,
    has_credit_authorization,
    require_credit_note,
)
from app.domain.entities.sales_margin import DiscountPolicy
from app.domain.entities.sales_order import (
    DeliveryMode,
    OrderStatus,
    PaymentTerms,
    available_to_sell,
    confirm_target,
    payment_condition,
    require_cancellable,
    require_delivery_place,
    require_editable,
    require_exchange,
    require_pending_authorization,
    require_promised_date,
    shortages,
)
from app.domain.entities.sales_quotation import (
    QuotationStatus,
    QuoteCalculation,
    require_authority,
    require_not_below_cost,
)
from app.domain.ports.customer_repository import CustomerRepository
from app.domain.ports.price_list_repository import PriceListRepository
from app.domain.ports.sales_credit_repository import SalesCreditRepository
from app.domain.ports.sales_order_repository import (
    Order,
    OrderFilters,
    OrderLine,
    SalesOrderRepository,
)
from app.domain.ports.sales_quotation_repository import (
    PeopleNames,
    Quotation,
    SalesQuotationRepository,
)

IDEMPOTENCY_KEY_MAX_LENGTH = 120
MIN_NOTE_LENGTH = 3


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_key(key: str) -> None:
    if not key or len(key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        raise ValidationError(
            "La clave de idempotencia es obligatoria y admite hasta 120 caracteres.",
            code="sales_idempotency_key_required",
        )


def _require_note(text: str, message: str, code: str) -> str:
    clean = text.strip()
    if len(clean) < MIN_NOTE_LENGTH:
        raise ValidationError(message, code=code)
    return clean


@dataclass(frozen=True, slots=True)
class Delivery:
    promised_date: date
    mode: DeliveryMode
    address_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class OrderDraft:
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    lines: tuple[DraftLine, ...]
    delivery: Delivery
    document_type: str | None = None
    global_discount_percent: Decimal = Decimal("0")
    notes: str | None = None
    exchange_return_id: uuid.UUID | None = None
    """V8b1: la devolución que este pedido cambia por otro producto."""


@dataclass(frozen=True, slots=True)
class Availability:
    """Disponible para vender por artículo en la sucursal, sin contar este pedido."""

    on_hand: dict[uuid.UUID, Decimal]
    reserved: dict[uuid.UUID, Decimal]

    def free(self, item: uuid.UUID) -> Decimal:
        return available_to_sell(
            self.on_hand.get(item, Decimal("0")), self.reserved.get(item, Decimal("0"))
        )


@dataclass(frozen=True, slots=True)
class OrderView:
    order: Order
    customer: Customer
    price_list_name: str | None
    quotation_code: str | None
    people: PeopleNames
    exchange_return_code: str | None = None
    availability: Availability | None = None


@dataclass(slots=True)
class Change:
    order: Order
    before: Order | None = None
    replayed: bool = False
    details: dict[str, object] = field(default_factory=dict)


class SalesOrderUseCases:
    def __init__(
        self,
        repository: SalesOrderRepository,
        quotations: SalesQuotationRepository,
        pricing: SalesDocumentPricing,
        prices: PriceListRepository,
        customers: CustomerRepository,
        credit: SalesCreditRepository | None = None,
    ) -> None:
        self._repo = repository
        self._quotations = quotations
        self._pricing = pricing
        self._prices = prices
        self._customers = customers
        self._credit = credit

    async def _credit_reasons(self, order: Order) -> list[str]:
        """Motivos de crédito del pedido (V5b): cupo, mora y bloqueo; el contado no se evalúa."""

        if self._credit is None or order.payment_terms is not PaymentTerms.CREDIT:
            return []
        snapshot = await self._credit.snapshot(
            order.company_id,
            order.customer_id,
            exclude_sale_id=order.id,
            today=today_in_el_salvador(),
        )
        return [
            reason.value
            for reason in evaluate_credit(snapshot, order.payment_terms, order.totals.total)
        ]

    # --- consultas ---------------------------------------------------------------------------

    async def get(self, company_id: uuid.UUID, order_id: uuid.UUID) -> Order:
        found = await self._repo.get(company_id, order_id)
        if found is None:
            raise NotFoundError("Pedido no encontrado.", code="sales_order_not_found")
        return found

    async def page(
        self, company_id: uuid.UUID, filters: OrderFilters, page: int, size: int
    ) -> tuple[list[Order], int]:
        return await self._repo.page(company_id, filters, page, size)

    async def availability(self, order: Order) -> Availability:
        items = {item.line.identity.inventory_item_id for item in order.lines}
        return Availability(
            on_hand=await self._repo.on_hand(order.company_id, order.branch_id, items),
            reserved=await self._repo.reserved(
                order.company_id, order.branch_id, items, exclude_order=order.id
            ),
        )

    async def view(self, order: Order, *, with_availability: bool = False) -> OrderView:
        customer = await self._customers.get_customer(order.company_id, order.customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        price_list = (
            await self._prices.get_list(order.company_id, order.price_list_id)
            if order.price_list_id
            else None
        )
        quotation = (
            await self._quotations.get(order.company_id, order.quotation_id)
            if order.quotation_id
            else None
        )
        people = await self._repo.user_names(
            {
                user
                for user in (
                    order.created_by_id,
                    order.confirmed_by_id,
                    order.authorized_by_id,
                    order.cancelled_by_id,
                )
                if user
            }
        )
        exchange = (
            await self._repo.exchange_source(
                order.company_id, order.exchange_return_id, exclude_order=order.id
            )
            if order.exchange_return_id
            else None
        )
        return OrderView(
            order=order,
            customer=customer,
            price_list_name=price_list.name if price_list else None,
            quotation_code=quotation.code if quotation else None,
            exchange_return_code=exchange.code if exchange else None,
            people=people,
            availability=await self.availability(order) if with_availability else None,
        )

    # --- borrador ----------------------------------------------------------------------------

    async def _delivery_text(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, delivery: Delivery, today: date
    ) -> str | None:
        require_promised_date(delivery.promised_date, today)
        require_delivery_place(delivery.mode, delivery.address_id is not None)
        if delivery.address_id is None:
            return None
        address = await self._repo.delivery_address(company_id, customer_id, delivery.address_id)
        if address is None:
            raise BusinessRuleError(
                "La dirección de entrega no existe o no es de este cliente.",
                code="sales_order_address_invalid",
            )
        return address.text

    async def _build(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        draft: OrderDraft,
        today: date,
        *,
        kept_prices: dict[PriceKey, Decimal] | None = None,
        enforce_cost: bool = True,
        order_id: uuid.UUID | None = None,
    ) -> Order:
        if draft.exchange_return_id is not None:
            await self._require_exchange(company_id, draft, order_id)
        priced = await self._pricing.price(
            company_id,
            actor,
            PricingRequest(
                branch_id=draft.branch_id,
                customer_id=draft.customer_id,
                lines=draft.lines,
                document_type=draft.document_type,
                global_discount_percent=draft.global_discount_percent,
            ),
            today,
            kept_prices=kept_prices,
        )
        if enforce_cost:
            require_not_below_cost(priced.calculation)
        address_text = await self._delivery_text(
            company_id, draft.customer_id, draft.delivery, today
        )
        condition = payment_condition(priced.customer.draft.credit_days)
        return Order(
            id=uuid.uuid4(),
            company_id=company_id,
            branch_id=draft.branch_id,
            customer_id=priced.customer.id,
            code="",
            document_type=priced.document.value,
            price_list_id=priced.price_list_id,
            prices_include_vat=priced.prices_include_vat,
            global_discount_percent=draft.global_discount_percent,
            status=OrderStatus.DRAFT,
            version=1,
            notes=(draft.notes or "").strip() or None,
            totals=priced.totals,
            requires_authorization=priced.calculation.requires_authorization,
            authorization_reasons=priced.reasons,
            promised_date=draft.delivery.promised_date,
            delivery_mode=draft.delivery.mode,
            delivery_address_id=draft.delivery.address_id,
            delivery_address_text=address_text,
            payment_terms=condition.terms,
            credit_days=condition.credit_days,
            created_by_id=actor.user_id,
            exchange_return_id=draft.exchange_return_id,
            lines=[OrderLine(line=line) for line in priced.lines],
        )

    async def _require_exchange(
        self, company_id: uuid.UUID, draft: OrderDraft, order_id: uuid.UUID | None
    ) -> None:
        assert draft.exchange_return_id is not None
        source = await self._repo.exchange_source(
            company_id, draft.exchange_return_id, exclude_order=order_id
        )
        if source is None:
            raise NotFoundError(
                "La devolución del cambio no existe.", code="sales_exchange_return_not_found"
            )
        require_exchange(source, draft.customer_id)

    async def preview(self, company_id: uuid.UUID, actor: Actor, draft: OrderDraft) -> Order:
        # La vista previa solo calcula: el vínculo del cambio se valida al guardar.
        return await self._build(
            company_id,
            actor,
            replace(draft, exchange_return_id=None),
            today_in_el_salvador(),
            enforce_cost=False,
        )

    async def _current(self, order: Order, policy: DiscountPolicy) -> QuoteCalculation:
        """Lo guardado con el tope de ``policy`` y el costo vigente del kardex; nunca bajo costo."""

        calculation = await self._pricing.reevaluate(
            order.company_id,
            order.customer_id,
            order.document_type,
            order.prices_include_vat,
            order.global_discount_percent,
            [item.line for item in order.lines],
            policy,
            current_costs=True,
        )
        require_not_below_cost(calculation)
        return calculation

    async def _replay(
        self, company_id: uuid.UUID, action: str, key: str, fingerprint: str
    ) -> Change | None:
        await self._repo.lock_key(company_id, action, key)
        remembered = await self._repo.remembered(company_id, action, key)
        if remembered is None:
            return None
        if remembered[0] != fingerprint:
            raise ConflictError(
                "La clave de idempotencia ya se usó con otro contenido.",
                code="sales_idempotency_payload_conflict",
            )
        return Change(await self.get(company_id, remembered[1]), replayed=True)

    async def _store_new(
        self, order: Order, today: date, action: str, key: str, fingerprint: str
    ) -> Change:
        order.code = f"PED-{today:%Y%m%d}-{order.id.hex[:8].upper()}"
        await self._repo.add(order)
        await self._repo.remember(
            order.company_id, action, key, fingerprint, order.id, order.created_by_id
        )
        return Change(order)

    async def create(
        self, company_id: uuid.UUID, actor: Actor, draft: OrderDraft, idempotency_key: str
    ) -> Change:
        _require_key(idempotency_key)
        fingerprint = _fingerprint(draft)
        replayed = await self._replay(company_id, "create_order", idempotency_key, fingerprint)
        if replayed:
            return replayed
        today = today_in_el_salvador()
        order = await self._build(company_id, actor, draft, today)
        return await self._store_new(order, today, "create_order", idempotency_key, fingerprint)

    async def create_from_quotation(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        quotation_id: uuid.UUID,
        delivery: Delivery,
        idempotency_key: str,
        notes: str | None = None,
    ) -> Change:
        """Copia la cotización aceptada tal como el cliente la aceptó, sin recalcular."""

        _require_key(idempotency_key)
        fingerprint = _fingerprint({"quotation": quotation_id, "delivery": delivery})
        replayed = await self._replay(company_id, "order_from_quote", idempotency_key, fingerprint)
        if replayed:
            return replayed
        existing = await self._repo.for_quotation(company_id, quotation_id)
        if existing is not None:
            return Change(existing, replayed=True)
        quotation = await self._quotations.get(company_id, quotation_id, lock=True)
        if quotation is None:
            raise NotFoundError("Cotización no encontrada.", code="sales_quotation_not_found")
        if quotation.status is not QuotationStatus.ACCEPTED:
            raise BusinessRuleError(
                "Solo una cotización aceptada por el cliente se convierte en pedido.",
                code="sales_quote_not_convertible",
            )
        customer = await self._pricing.active_customer(company_id, quotation.customer_id)
        today = today_in_el_salvador()
        address_text = await self._delivery_text(company_id, customer.id, delivery, today)
        condition = payment_condition(customer.draft.credit_days)
        order = _from_quotation(quotation, actor.user_id, delivery, address_text, notes)
        order.payment_terms, order.credit_days = condition.terms, condition.credit_days
        return await self._store_new(order, today, "order_from_quote", idempotency_key, fingerprint)

    async def _locked(
        self, company_id: uuid.UUID, order_id: uuid.UUID, expected_version: int
    ) -> Order:
        found = await self._repo.get(company_id, order_id, lock=True)
        if found is None:
            raise NotFoundError("Pedido no encontrado.", code="sales_order_not_found")
        if found.version != expected_version:
            raise ConflictError(
                "El pedido cambió. Recárgalo antes de continuar.",
                code="sales_order_version_conflict",
            )
        return found

    async def update(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        order_id: uuid.UUID,
        expected_version: int,
        draft: OrderDraft,
    ) -> Change:
        current = await self._locked(company_id, order_id, expected_version)
        require_editable(current.status)
        kept = {
            (
                item.line.identity.product_id,
                item.line.identity.variant_id,
                item.line.identity.unit_id,
            ): item.line.unit_price
            for item in current.lines
            if item.line.price_overridden
        }
        before = _copy(current)
        rebuilt = await self._build(
            company_id, actor, draft, today_in_el_salvador(), kept_prices=kept, order_id=current.id
        )
        # Editar invalida la autorización heredada de la cotización: se vuelve a evaluar.
        rebuilt.id, rebuilt.code = current.id, current.code
        rebuilt.created_by_id, rebuilt.quotation_id = current.created_by_id, current.quotation_id
        rebuilt.version = current.version + 1
        await self._repo.save(rebuilt, replace_lines=True)
        rebuilt.created_at = current.created_at
        return Change(rebuilt, before)

    # --- confirmación y reserva ------------------------------------------------------------------

    async def _reserve(self, order: Order) -> None:
        """Valida que el disponible de la sucursal alcance para lo que el pedido aparta."""

        required: dict[uuid.UUID, Decimal] = {}
        names: dict[uuid.UUID, str] = {}
        for item in order.lines:
            identity = item.line.identity
            required[identity.inventory_item_id] = (
                required.get(identity.inventory_item_id, Decimal("0")) + item.line.quantity_base
            )
            names[identity.inventory_item_id] = (
                f"{identity.product_name} ({identity.base_unit_name})"
            )
        await self._repo.lock_reservations(order.company_id, order.branch_id, set(required))
        availability = await self.availability(order)
        missing = shortages(required, {item: availability.free(item) for item in required})
        if missing:
            detail = "; ".join(
                f"{names[m.inventory_item_id]}: pides {m.required.normalize():f}, "
                f"hay {m.available.normalize():f} disponibles"
                for m in missing
            )
            raise BusinessRuleError(
                f"No hay existencias suficientes en la sucursal para apartar el pedido. {detail}.",
                code="sales_order_stock_insufficient",
            )

    def _confirm(self, order: Order, actor_id: uuid.UUID) -> None:
        order.status = OrderStatus.CONFIRMED
        order.confirmed_by_id, order.confirmed_at = actor_id, datetime.now(UTC)

    async def confirm(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        order_id: uuid.UUID,
        expected_version: int,
    ) -> Change:
        current = await self._locked(company_id, order_id, expected_version)
        before = _copy(current)
        policy = await self._pricing.policy(company_id, actor_id)
        calculation = await self._current(current, policy)
        if current.authorized_by_id is None:
            current.totals = totals_of(calculation)
            credit = await self._credit_reasons(current)
            requires = calculation.requires_authorization or bool(credit)
            current.status = confirm_target(current.status, requires)
            current.requires_authorization = requires
            current.authorization_reasons = tuple(r.value for r in calculation.reasons) + tuple(
                credit
            )
        else:
            confirm_target(current.status, requires_authorization=False)
            current.status = OrderStatus.CONFIRMED
        if current.status is OrderStatus.CONFIRMED:
            await self._reserve(current)
            self._confirm(current, actor_id)
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def authorize(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        order_id: uuid.UUID,
        expected_version: int,
        note: str | None,
        *,
        can_authorize_discounts: bool = True,
        can_authorize_credit: bool = False,
    ) -> Change:
        current = await self._locked(company_id, order_id, expected_version)
        require_pending_authorization(current.status)
        credit = credit_reasons(current.authorization_reasons)
        if credit:
            if not can_authorize_credit:
                raise BusinessRuleError(
                    "Este pedido necesita una autorización de crédito: pídela a quien controla "
                    "el crédito de los clientes.",
                    code="sales_credit_authority_required",
                )
            note = require_credit_note(note)
        if len(credit) < len(current.authorization_reasons):
            if not can_authorize_discounts:
                raise BusinessRuleError(
                    "Este pedido también tiene descuentos que pasan el tope: debe autorizarlo "
                    "alguien con permiso de autorizar descuentos.",
                    code="sales_discount_authority_required",
                )
            policy = await self._pricing.policy(company_id, actor_id)
            require_authority(await self._current(current, policy), policy)
        before = _copy(current)
        await self._reserve(current)
        now = datetime.now(UTC)
        current.authorized_by_id, current.authorized_at = actor_id, now
        current.authorization_note = (note or "").strip() or None
        self._confirm(current, actor_id)
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def authorize_credit(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        order_id: uuid.UUID,
        expected_version: int,
        note: str | None,
    ) -> Change:
        """Autoriza el crédito de un pedido ya confirmado que al facturar pasó el cupo (V5b).

        Entre confirmar y facturar el cliente puede agotar su cupo, caer en mora o bloquearse; el
        pedido confirmado no vuelve a borrador, así que la autorización de crédito se registra
        sobre él y vale para facturarlo.
        """

        current = await self._locked(company_id, order_id, expected_version)
        if current.status is not OrderStatus.CONFIRMED:
            raise BusinessRuleError(
                "Solo un pedido confirmado se autoriza para facturar a crédito.",
                code="sales_credit_not_applicable",
            )
        if has_credit_authorization(
            current.authorization_reasons, current.authorized_by_id is not None
        ):
            raise BusinessRuleError(
                "El crédito de este pedido ya está autorizado.",
                code="sales_credit_already_authorized",
            )
        reasons = await self._credit_reasons(current)
        if not reasons:
            raise BusinessRuleError(
                "El pedido no necesita autorización de crédito para facturarse.",
                code="sales_credit_not_required",
            )
        text = require_credit_note(note)
        before = _copy(current)
        current.authorization_reasons = tuple(
            dict.fromkeys((*current.authorization_reasons, *reasons))
        )
        current.requires_authorization = True
        current.authorized_by_id, current.authorized_at = actor_id, datetime.now(UTC)
        current.authorization_note = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def return_to_draft(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        order_id: uuid.UUID,
        expected_version: int,
        note: str,
    ) -> Change:
        text = _require_note(
            note,
            "Indica qué debe corregirse antes de volver a enviarlo.",
            "sales_order_reason_required",
        )
        current = await self._locked(company_id, order_id, expected_version)
        require_pending_authorization(current.status)
        before = _copy(current)
        current.status = OrderStatus.DRAFT
        current.authorization_note = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before, details={"returned_by": str(actor_id)})

    async def cancel(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        order_id: uuid.UUID,
        expected_version: int,
        reason: str,
    ) -> Change:
        text = _require_note(
            reason, "Indica el motivo de la cancelación.", "sales_cancellation_reason_required"
        )
        current = await self._locked(company_id, order_id, expected_version)
        require_cancellable(current.status, current.delivered_any)
        if await self._repo.invoiced(company_id, order_id):
            raise BusinessRuleError(
                "El pedido ya está facturado y no se puede cancelar. Se corrige con la "
                "invalidación del documento o una nota de crédito.",
                code="sales_order_invoiced",
            )
        before = _copy(current)
        current.status = OrderStatus.CANCELLED
        current.cancelled_by_id, current.cancelled_at = actor_id, datetime.now(UTC)
        current.cancellation_reason = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before, details={"released_reservation": True})


def _from_quotation(
    quotation: Quotation,
    actor_id: uuid.UUID,
    delivery: Delivery,
    address_text: str | None,
    notes: str | None,
) -> Order:
    authorizer = quotation.authorized_by_id or quotation.issued_by_id
    authorized_at = quotation.authorized_at or quotation.issued_at
    return Order(
        id=uuid.uuid4(),
        company_id=quotation.company_id,
        branch_id=quotation.branch_id,
        customer_id=quotation.customer_id,
        quotation_id=quotation.id,
        code="",
        document_type=quotation.document_type,
        price_list_id=quotation.price_list_id,
        prices_include_vat=quotation.prices_include_vat,
        global_discount_percent=quotation.global_discount_percent,
        status=OrderStatus.DRAFT,
        version=1,
        notes=(notes or "").strip() or quotation.notes,
        totals=replace(quotation.totals),
        requires_authorization=quotation.requires_authorization,
        authorization_reasons=quotation.authorization_reasons,
        promised_date=delivery.promised_date,
        delivery_mode=delivery.mode,
        delivery_address_id=delivery.address_id,
        delivery_address_text=address_text,
        payment_terms=payment_condition(0).terms,
        credit_days=0,
        created_by_id=actor_id,
        authorized_by_id=authorizer,
        authorized_at=authorized_at,
        authorization_note=f"Condiciones aceptadas en la cotización {quotation.code}.",
        lines=[
            OrderLine(line=replace(line, id=None), source_quotation_line_id=line.id)
            for line in quotation.lines
        ],
    )


def _copy(order: Order) -> Order:
    return replace(order, lines=list(order.lines))
