"""Cotización de venta rediseñada (bloque V2d).

Cada vez que se guarda un borrador, el servidor:
1. resuelve la lista y el precio de cada línea (V2b), el descuento sugerido y el costo (V2c);
2. aplica el precio manual si quien guarda tiene permiso;
3. calcula impuestos y totales con el motor fiscal (V2a) y evalúa el tope del usuario.

Todo queda guardado en la cotización: un cambio posterior de lista o de costo no la altera.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
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
from app.domain.entities.sales_margin import DiscountPolicy
from app.domain.entities.sales_quotation import (
    QuotationStatus,
    QuoteCalculation,
    is_expired,
    issue_target,
    require_acceptable,
    require_answerable,
    require_authority,
    require_cancellable,
    require_editable,
    require_pending_authorization,
    require_rejection_reason,
    require_valid_until,
    require_validity_days,
)
from app.domain.ports.customer_repository import CustomerRepository
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.price_list_repository import PriceListRepository
from app.domain.ports.sales_quotation_repository import (
    LinkedSale,
    PeopleNames,
    Quotation,
    QuotationFilters,
    SalesQuotationRepository,
)

IDEMPOTENCY_KEY_MAX_LENGTH = 120
MIN_NOTE_LENGTH = 3


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Draft:
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    lines: tuple[DraftLine, ...]
    document_type: str | None = None
    """``01`` o ``03``; si falta, se propone según el cliente."""
    valid_until: date | None = None
    """Si falta, la fecha más los días de vigencia de la empresa."""
    global_discount_percent: Decimal = Decimal("0")
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class QuotationView:
    """La cotización con los nombres que necesita la pantalla o el PDF."""

    quotation: Quotation
    customer: Customer
    price_list_name: str | None
    people: PeopleNames
    sale: LinkedSale | None

    @property
    def expired(self) -> bool:
        return is_expired(self.quotation.status, self.quotation.valid_until, today_in_el_salvador())


@dataclass(frozen=True, slots=True)
class DocumentHeader:
    company_name: str
    commercial_name: str
    nit: str
    nrc: str
    email: str | None
    phone: str | None
    branch_name: str | None


@dataclass(slots=True)
class Change:
    """Resultado de una acción: la cotización y su estado antes, para la bitácora."""

    quotation: Quotation
    before: Quotation | None = None
    replayed: bool = False
    details: dict[str, object] = field(default_factory=dict)


class SalesQuotationUseCases:
    def __init__(
        self,
        repository: SalesQuotationRepository,
        pricing: SalesDocumentPricing,
        prices: PriceListRepository,
        fiscal: FiscalRepository,
        customers: CustomerRepository,
    ) -> None:
        self._repo = repository
        self._pricing = pricing
        self._prices = prices
        self._fiscal = fiscal
        self._customers = customers

    # --- consultas ---------------------------------------------------------------------------

    async def get(self, company_id: uuid.UUID, quotation_id: uuid.UUID) -> Quotation:
        found = await self._repo.get(company_id, quotation_id)
        if found is None:
            raise NotFoundError("Cotización no encontrada.", code="sales_quotation_not_found")
        return found

    async def page(
        self, company_id: uuid.UUID, filters: QuotationFilters, page: int, size: int
    ) -> tuple[list[Quotation], int]:
        return await self._repo.page(company_id, filters, page, size)

    async def view(self, quotation: Quotation) -> QuotationView:
        customer = await self._customers.get_customer(quotation.company_id, quotation.customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        price_list = (
            await self._prices.get_list(quotation.company_id, quotation.price_list_id)
            if quotation.price_list_id
            else None
        )
        people = await self._repo.user_names(
            {
                user
                for user in (
                    quotation.created_by_id,
                    quotation.issued_by_id,
                    quotation.authorized_by_id,
                    quotation.customer_response_by_id,
                    quotation.cancelled_by_id,
                )
                if user
            }
        )
        return QuotationView(
            quotation=quotation,
            customer=customer,
            price_list_name=price_list.name if price_list else None,
            people=people,
            sale=await self._repo.linked_sale(quotation.company_id, quotation.id),
        )

    async def document_header(self, view: QuotationView) -> DocumentHeader:
        """Datos del emisor y de la sucursal para la versión imprimible."""

        company_id = view.quotation.company_id
        identity = await self._fiscal.company_identity(company_id)
        profile = await self._fiscal.get_profile(company_id)
        return DocumentHeader(
            company_name=identity.name if identity else "",
            commercial_name=identity.commercial_name if identity else "",
            nit=identity.nit if identity else "",
            nrc=identity.nrc if identity else "",
            email=profile.dte_email,
            phone=profile.dte_phone,
            branch_name=await self._fiscal.branch_name(company_id, view.quotation.branch_id),
        )

    async def validity_days(self, company_id: uuid.UUID) -> int:
        return await self._repo.validity_days(company_id)

    async def save_validity_days(
        self, company_id: uuid.UUID, days: int, actor_id: uuid.UUID
    ) -> tuple[int, int]:
        require_validity_days(days)
        before = await self._repo.validity_days(company_id)
        await self._repo.save_validity_days(company_id, days, actor_id)
        return before, days

    # --- cálculo -----------------------------------------------------------------------------

    async def _build(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        draft: Draft,
        today: date,
        *,
        kept_prices: dict[PriceKey, Decimal] | None = None,
    ) -> Quotation:
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
        valid_until = draft.valid_until or today + timedelta(
            days=await self._repo.validity_days(company_id)
        )
        require_valid_until(today, valid_until)
        return Quotation(
            id=uuid.uuid4(),
            company_id=company_id,
            branch_id=draft.branch_id,
            customer_id=priced.customer.id,
            code="",
            quotation_date=today,
            valid_until=valid_until,
            document_type=priced.document.value,
            price_list_id=priced.price_list_id,
            prices_include_vat=priced.prices_include_vat,
            global_discount_percent=draft.global_discount_percent,
            status=QuotationStatus.DRAFT,
            version=1,
            notes=(draft.notes or "").strip() or None,
            totals=priced.totals,
            requires_authorization=priced.calculation.requires_authorization,
            authorization_reasons=priced.reasons,
            created_by_id=actor.user_id,
            lines=priced.lines,
        )

    async def preview(self, company_id: uuid.UUID, actor: Actor, draft: Draft) -> Quotation:
        """Calcula sin guardar, para ver precios, impuestos y avisos mientras se edita."""

        return await self._build(company_id, actor, draft, today_in_el_salvador())

    async def _recalculate(self, quotation: Quotation, policy: DiscountPolicy) -> QuoteCalculation:
        """Vuelve a evaluar lo guardado con el tope de otro usuario, sin tocar los precios."""

        return await self._pricing.reevaluate(
            quotation.company_id,
            quotation.customer_id,
            quotation.document_type,
            quotation.prices_include_vat,
            quotation.global_discount_percent,
            quotation.lines,
            policy,
        )

    # --- borrador ----------------------------------------------------------------------------

    async def create(
        self, company_id: uuid.UUID, actor: Actor, draft: Draft, idempotency_key: str
    ) -> Change:
        if not idempotency_key or len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise ValidationError(
                "La clave de idempotencia es obligatoria y admite hasta 120 caracteres.",
                code="sales_idempotency_key_required",
            )
        fingerprint = _fingerprint(draft)
        await self._repo.lock_key(company_id, "create_quote", idempotency_key)
        remembered = await self._repo.remembered(company_id, "create_quote", idempotency_key)
        if remembered is not None:
            if remembered[0] != fingerprint:
                raise ConflictError(
                    "La clave de idempotencia ya se usó con otro contenido.",
                    code="sales_idempotency_payload_conflict",
                )
            return Change(await self.get(company_id, remembered[1]), replayed=True)
        today = today_in_el_salvador()
        quotation = await self._build(company_id, actor, draft, today)
        quotation.code = f"COT-{today:%Y%m%d}-{quotation.id.hex[:8].upper()}"
        await self._repo.add(quotation)
        await self._repo.remember(
            company_id, "create_quote", idempotency_key, fingerprint, quotation.id, actor.user_id
        )
        return Change(quotation)

    async def _locked(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID, expected_version: int
    ) -> Quotation:
        found = await self._repo.get(company_id, quotation_id, lock=True)
        if found is None:
            raise NotFoundError("Cotización no encontrada.", code="sales_quotation_not_found")
        if found.version != expected_version:
            raise ConflictError(
                "La cotización cambió. Recárgala antes de continuar.",
                code="sales_quote_version_conflict",
            )
        return found

    async def update(
        self,
        company_id: uuid.UUID,
        actor: Actor,
        quotation_id: uuid.UUID,
        expected_version: int,
        draft: Draft,
    ) -> Change:
        current = await self._locked(company_id, quotation_id, expected_version)
        require_editable(current.status)
        # Quien no puede cambiar precios sí puede conservar, sin tocarlos, los precios
        # manuales que alguien con permiso ya dejó en la cotización.
        kept = {
            (line.identity.product_id, line.identity.variant_id, line.identity.unit_id): (
                line.unit_price
            )
            for line in current.lines
            if line.price_overridden
        }
        before = _copy(current)
        rebuilt = await self._build(
            company_id, actor, draft, today_in_el_salvador(), kept_prices=kept
        )
        rebuilt.id = current.id
        rebuilt.code = current.code
        rebuilt.created_by_id = current.created_by_id
        rebuilt.version = current.version + 1
        await self._repo.save(rebuilt, replace_lines=True)
        rebuilt.created_at = current.created_at
        return Change(rebuilt, before)

    # --- emisión y autorización ----------------------------------------------------------------

    async def issue(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
    ) -> Change:
        current = await self._locked(company_id, quotation_id, expected_version)
        today = today_in_el_salvador()
        if current.valid_until < today:
            raise BusinessRuleError(
                "La vigencia ya pasó. Edita la cotización para actualizarla.",
                code="sales_quote_expired",
            )
        before = _copy(current)
        policy = await self._pricing.policy(company_id, actor_id)
        calculation = await self._recalculate(current, policy)
        current.status = issue_target(current.status, calculation.requires_authorization)
        current.requires_authorization = calculation.requires_authorization
        current.authorization_reasons = tuple(r.value for r in calculation.reasons)
        current.totals = totals_of(calculation)
        now = datetime.now(UTC)
        if current.status is QuotationStatus.ISSUED:
            current.issued_by_id, current.issued_at = actor_id, now
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def authorize(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
        note: str | None,
    ) -> Change:
        current = await self._locked(company_id, quotation_id, expected_version)
        require_pending_authorization(current.status)
        if current.valid_until < today_in_el_salvador():
            raise BusinessRuleError(
                "La vigencia ya pasó. Devuélvela a borrador para actualizarla.",
                code="sales_quote_expired",
            )
        policy = await self._pricing.policy(company_id, actor_id)
        require_authority(await self._recalculate(current, policy), policy)
        before = _copy(current)
        now = datetime.now(UTC)
        current.status = QuotationStatus.ISSUED
        current.authorized_by_id, current.authorized_at = actor_id, now
        current.authorization_note = (note or "").strip() or None
        current.issued_by_id, current.issued_at = actor_id, now
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def return_to_draft(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
        note: str,
    ) -> Change:
        text = note.strip()
        if len(text) < MIN_NOTE_LENGTH:
            raise ValidationError(
                "Indica qué debe corregirse antes de volver a enviarla.",
                code="sales_quote_reason_required",
            )
        current = await self._locked(company_id, quotation_id, expected_version)
        require_pending_authorization(current.status)
        before = _copy(current)
        current.status = QuotationStatus.DRAFT
        current.authorization_note = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before, details={"returned_by": str(actor_id)})

    # --- respuesta del cliente y cancelación ---------------------------------------------------

    async def accept(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
    ) -> Change:
        current = await self._locked(company_id, quotation_id, expected_version)
        require_acceptable(current.status, current.valid_until, today_in_el_salvador())
        await self._pricing.active_customer(company_id, current.customer_id)
        before = _copy(current)
        current.status = QuotationStatus.ACCEPTED
        current.customer_response_by_id = actor_id
        current.customer_response_at = datetime.now(UTC)
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def reject(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
        reason: str,
    ) -> Change:
        text = require_rejection_reason(reason)
        current = await self._locked(company_id, quotation_id, expected_version)
        require_answerable(current.status)
        before = _copy(current)
        current.status = QuotationStatus.REJECTED
        current.customer_response_by_id = actor_id
        current.customer_response_at = datetime.now(UTC)
        current.rejection_reason = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)

    async def cancel(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expected_version: int,
        reason: str,
    ) -> Change:
        text = reason.strip()
        if len(text) < MIN_NOTE_LENGTH:
            raise ValidationError(
                "Indica el motivo de la cancelación.", code="sales_cancellation_reason_required"
            )
        current = await self._locked(company_id, quotation_id, expected_version)
        require_cancellable(current.status)
        if await self._repo.linked_sale(company_id, quotation_id):
            raise BusinessRuleError(
                "La cotización ya originó una venta. Gestiona la venta vinculada.",
                code="sales_quote_converted",
            )
        before = _copy(current)
        current.status = QuotationStatus.CANCELLED
        current.cancelled_by_id = actor_id
        current.cancelled_at = datetime.now(UTC)
        current.cancellation_reason = text
        current.version += 1
        await self._repo.save(current, replace_lines=False)
        return Change(current, before)


def _copy(quotation: Quotation) -> Quotation:
    return replace(quotation, lines=list(quotation.lines))
