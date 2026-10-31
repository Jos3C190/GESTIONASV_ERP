"""Manual comparison and allocation of consolidated purchase demand."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_consolidation import (
    PurchaseConsolidation,
    PurchaseConsolidationAward,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationStatus,
)
from app.domain.ports.purchase_consolidation_repository import PurchaseConsolidationRepository
from app.domain.ports.purchase_order_repository import PurchaseOrderRepository
from app.domain.ports.purchase_quotation_repository import PurchaseQuotationRepository

ZERO = Decimal("0")
VISIBLE_QUOTATION_STATUSES = {
    PurchaseQuotationStatus.RECEIVED,
    PurchaseQuotationStatus.UNDER_EVALUATION,
    PurchaseQuotationStatus.SELECTED,
    PurchaseQuotationStatus.REJECTED,
    PurchaseQuotationStatus.EXPIRED,
    PurchaseQuotationStatus.NOT_SELECTED,
}


@dataclass(frozen=True, slots=True)
class AwardOffer:
    quotation_id: uuid.UUID
    quotation_code: str
    quotation_version: int
    supplier_id: int
    quotation_status: PurchaseQuotationStatus
    quotation_currency: str
    quotation_valid_until: datetime | None
    quotation_delivery_days: int | None
    quotation_payment_terms: str | None
    quotation_total: Decimal
    quotation_expenses_total: Decimal
    quotation_detail_id: uuid.UUID
    requested_quantity: Decimal
    offered_quantity: Decimal | None
    available_quantity: Decimal | None
    awarded_quantity: Decimal
    remaining_offer_quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal
    delivery_days: int | None
    notes: str | None
    can_award: bool
    blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class AwardDecision:
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    quotation_code: str
    supplier_id: int
    quantity: Decimal
    reason: str
    decided_by_id: uuid.UUID
    created_at: datetime | None
    revoked_at: datetime | None
    revoked_by_id: uuid.UUID | None
    revocation_reason: str | None
    ordered_quantity: Decimal
    remaining_to_order_quantity: Decimal

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True, slots=True)
class AwardLine:
    id: uuid.UUID
    product_id: int
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    demand_quantity: Decimal
    awarded_quantity: Decimal
    remaining_quantity: Decimal
    offers: tuple[AwardOffer, ...]
    decisions: tuple[AwardDecision, ...]


@dataclass(frozen=True, slots=True)
class PurchaseConsolidationAwardBoard:
    consolidation_id: uuid.UUID
    consolidation_code: str
    lines: tuple[AwardLine, ...]
    currencies: tuple[str, ...]


class PurchaseConsolidationAdjudicationUseCases:
    def __init__(
        self,
        consolidation_repository: PurchaseConsolidationRepository,
        quotation_repository: PurchaseQuotationRepository,
        purchase_order_repository: PurchaseOrderRepository | None = None,
    ) -> None:
        self._consolidations = consolidation_repository
        self._quotations = quotation_repository
        self._purchase_orders = purchase_order_repository

    async def get_board(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> PurchaseConsolidationAwardBoard:
        consolidation = await self._get_consolidation(company_id, consolidation_id)
        quotations = await self._quotations.list_consolidation_quotations(
            company_id, consolidation_id
        )
        awards = await self._consolidations.list_awards(company_id, consolidation_id)
        ordered = (
            await self._purchase_orders.get_ordered_award_quantities(
                company_id, tuple(award.id for award in awards)
            )
            if self._purchase_orders is not None and awards
            else {}
        )
        return self._build_board(
            consolidation,
            quotations,
            awards,
            now=datetime.now(UTC),
            ordered_quantities=ordered,
        )

    async def award(
        self,
        *,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        consolidation_line_id: uuid.UUID,
        quotation_id: uuid.UUID,
        quotation_detail_id: uuid.UUID,
        quantity: Decimal,
        reason: str,
        actor_id: uuid.UUID,
        now: datetime | None = None,
    ) -> PurchaseConsolidationAward:
        reason = self._required_reason(reason)
        if not quantity.is_finite() or quantity <= ZERO:
            raise ValidationError(
                "La cantidad adjudicada debe ser mayor que cero.",
                code="purchase_award_quantity_invalid",
            )
        instant = now or datetime.now(UTC)
        consolidation = await self._get_consolidation(company_id, consolidation_id, for_update=True)
        self._ensure_awardable_consolidation(consolidation)
        quotations = await self._quotations.list_consolidation_quotations(
            company_id, consolidation_id
        )
        awards = await self._consolidations.list_awards(company_id, consolidation_id)
        board = self._build_board(consolidation, quotations, awards, now=instant)
        line = next((row for row in board.lines if row.id == consolidation_line_id), None)
        if line is None:
            raise NotFoundError(
                "El producto no pertenece a este consolidado.",
                code="purchase_award_line_not_found",
            )
        offer = next(
            (
                row
                for row in line.offers
                if row.quotation_id == quotation_id
                and row.quotation_detail_id == quotation_detail_id
            ),
            None,
        )
        if offer is None:
            raise NotFoundError(
                "La línea de oferta no pertenece a este producto y consolidado.",
                code="purchase_award_offer_not_found",
            )
        if not offer.can_award:
            raise BusinessRuleError(
                offer.blocked_reason or "Esta oferta no se puede adjudicar.",
                code="purchase_award_offer_unavailable",
            )
        if quantity > line.remaining_quantity:
            raise BusinessRuleError(
                f"Solo quedan {line.remaining_quantity} {line.unit_name} por adjudicar para este producto.",
                code="purchase_award_demand_exceeded",
            )
        if quantity > offer.remaining_offer_quantity:
            raise BusinessRuleError(
                f"Este proveedor tiene {offer.remaining_offer_quantity} {line.unit_name} disponibles para adjudicar.",
                code="purchase_award_offer_quantity_exceeded",
            )

        entity = PurchaseConsolidationAward(
            id=uuid.uuid4(),
            company_id=company_id,
            consolidation_id=consolidation_id,
            consolidation_line_id=consolidation_line_id,
            purchase_quotation_id=quotation_id,
            purchase_quotation_detail_id=quotation_detail_id,
            supplier_id=next(q.supplier_id for q in quotations if q.id == quotation_id),
            quantity=quantity,
            reason=reason,
            decided_by_id=actor_id,
        )
        saved = await self._consolidations.create_award(entity)
        if saved is None:
            raise NotFoundError(
                "El consolidado ya no está disponible.",
                code="purchase_consolidation_not_found",
            )
        return saved

    async def revoke_award(
        self,
        *,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        award_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidationAward:
        reason = self._required_reason(reason)
        consolidation = await self._get_consolidation(company_id, consolidation_id, for_update=True)
        self._ensure_awardable_consolidation(consolidation)
        if self._purchase_orders is not None:
            ordered = await self._purchase_orders.get_ordered_award_quantities(
                company_id, (award_id,)
            )
            if ordered.get(award_id, ZERO) > ZERO:
                raise BusinessRuleError(
                    "Cancela primero la orden de compra vinculada antes de revertir esta adjudicación.",
                    code="purchase_award_has_purchase_order",
                )
        saved = await self._consolidations.revoke_award(
            company_id,
            consolidation_id,
            award_id,
            actor_id=actor_id,
            reason=reason,
        )
        if saved is None:
            raise NotFoundError(
                "La adjudicación no existe o ya fue revertida.",
                code="purchase_award_not_found",
            )
        return saved

    async def _get_consolidation(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseConsolidation:
        item = await self._consolidations.get(company_id, consolidation_id, for_update=for_update)
        if item is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.",
                code="purchase_consolidation_not_found",
            )
        return item

    @staticmethod
    def _ensure_awardable_consolidation(item: PurchaseConsolidation) -> None:
        if item.status is PurchaseConsolidationStatus.CANCELLED:
            raise BusinessRuleError(
                "No se puede adjudicar un consolidado cancelado.",
                code="purchase_award_consolidation_cancelled",
            )
        if item.status is PurchaseConsolidationStatus.CLOSED:
            raise BusinessRuleError(
                "No se puede cambiar la adjudicación de un consolidado cerrado.",
                code="purchase_award_consolidation_closed",
            )

    @classmethod
    def _build_board(
        cls,
        consolidation: PurchaseConsolidation,
        quotations: tuple[PurchaseQuotation, ...],
        awards: tuple[PurchaseConsolidationAward, ...],
        *,
        now: datetime,
        ordered_quantities: dict[uuid.UUID, Decimal] | None = None,
    ) -> PurchaseConsolidationAwardBoard:
        active_awards = tuple(award for award in awards if award.is_active)
        quotation_by_id = {quotation.id: quotation for quotation in quotations}
        active_by_line: dict[uuid.UUID, list[PurchaseConsolidationAward]] = {}
        active_by_detail: dict[uuid.UUID, list[PurchaseConsolidationAward]] = {}
        for award in active_awards:
            active_by_line.setdefault(award.consolidation_line_id, []).append(award)
            active_by_detail.setdefault(award.purchase_quotation_detail_id, []).append(award)

        board_lines: list[AwardLine] = []
        currencies: set[str] = set()
        for source_line in consolidation.lines:
            line_awards = tuple(
                award for award in awards if award.consolidation_line_id == source_line.id
            )
            active_line_awards = active_by_line.get(source_line.id, [])
            awarded_quantity = sum((award.quantity for award in active_line_awards), ZERO)
            remaining_quantity = max(source_line.total_quantity - awarded_quantity, ZERO)
            offer_rows = cls._offers_for_line(
                source_line.id,
                remaining_quantity,
                quotations,
                active_line_awards,
                active_by_detail,
                now=now,
            )
            currencies.update(offer.quotation_currency for offer in offer_rows)
            board_lines.append(
                AwardLine(
                    id=source_line.id,
                    product_id=source_line.product_id,
                    product_sku=source_line.product_sku,
                    product_name=source_line.product_name,
                    unit_id=source_line.unit_id,
                    unit_name=source_line.unit_name,
                    demand_quantity=source_line.total_quantity,
                    awarded_quantity=awarded_quantity,
                    remaining_quantity=remaining_quantity,
                    offers=offer_rows,
                    decisions=cls._decisions_for_line(
                        line_awards,
                        quotation_by_id,
                        ordered_quantities or {},
                    ),
                )
            )
        return PurchaseConsolidationAwardBoard(
            consolidation_id=consolidation.id,
            consolidation_code=consolidation.code,
            lines=tuple(board_lines),
            currencies=tuple(sorted(currencies)),
        )

    @classmethod
    def _offers_for_line(
        cls,
        line_id: uuid.UUID,
        remaining_quantity: Decimal,
        quotations: tuple[PurchaseQuotation, ...],
        active_line_awards: list[PurchaseConsolidationAward],
        active_by_detail: dict[uuid.UUID, list[PurchaseConsolidationAward]],
        *,
        now: datetime,
    ) -> tuple[AwardOffer, ...]:
        offers: list[AwardOffer] = []
        for quotation in quotations:
            if quotation.status not in VISIBLE_QUOTATION_STATUSES:
                continue
            snapshots_by_detail = {
                snapshot.purchase_quotation_detail_id: snapshot for snapshot in quotation.snapshots
            }
            for detail in quotation.details:
                snapshot = snapshots_by_detail.get(detail.id)
                if snapshot is None or snapshot.consolidation_line_id != line_id:
                    continue
                offers.append(
                    cls._build_offer(
                        quotation,
                        detail,
                        remaining_quantity,
                        active_line_awards,
                        active_by_detail.get(detail.id, []),
                        now=now,
                    )
                )
        return tuple(offers)

    @classmethod
    def _build_offer(
        cls,
        quotation: PurchaseQuotation,
        detail: PurchaseQuotationDetail,
        remaining_quantity: Decimal,
        active_line_awards: list[PurchaseConsolidationAward],
        detail_awards: list[PurchaseConsolidationAward],
        *,
        now: datetime,
    ) -> AwardOffer:
        already_awarded = sum((award.quantity for award in detail_awards), ZERO)
        offered = detail.offered_quantity
        available = detail.available_quantity
        offer_cap = min(
            offered or ZERO,
            available if available is not None else (offered or ZERO),
        )
        remaining_offer = max(offer_cap - already_awarded, ZERO)
        supplier_awards = [
            award for award in active_line_awards if award.supplier_id == quotation.supplier_id
        ]
        blocked_reason = cls._offer_blocked_reason(
            quotation,
            offered,
            available,
            remaining_quantity,
            remaining_offer,
            {award.purchase_quotation_id for award in supplier_awards},
            now=now,
        )
        return AwardOffer(
            quotation_id=quotation.id,
            quotation_code=quotation.code,
            quotation_version=quotation.version_number,
            supplier_id=quotation.supplier_id,
            quotation_status=quotation.status,
            quotation_currency=quotation.currency,
            quotation_valid_until=quotation.valid_until,
            quotation_delivery_days=quotation.delivery_days,
            quotation_payment_terms=quotation.payment_terms,
            quotation_total=quotation.total,
            quotation_expenses_total=sum((expense.amount for expense in quotation.expenses), ZERO),
            quotation_detail_id=detail.id,
            requested_quantity=detail.quantity,
            offered_quantity=offered,
            available_quantity=available,
            awarded_quantity=already_awarded,
            remaining_offer_quantity=min(remaining_offer, remaining_quantity),
            unit_price=detail.unit_price,
            discount=detail.discount,
            subtotal=detail.subtotal,
            tax_rate=detail.tax_rate,
            tax_amount=detail.tax_amount,
            line_total=detail.total,
            delivery_days=detail.delivery_days,
            notes=detail.notes,
            can_award=blocked_reason is None,
            blocked_reason=blocked_reason,
        )

    @staticmethod
    def _offer_blocked_reason(
        quotation: PurchaseQuotation,
        offered: Decimal | None,
        available: Decimal | None,
        remaining_quantity: Decimal,
        remaining_offer: Decimal,
        chosen_versions: set[uuid.UUID],
        *,
        now: datetime,
    ) -> str | None:
        blocked_reason: str | None = None
        if quotation.status is PurchaseQuotationStatus.RECEIVED:
            blocked_reason = "Pasa primero la respuesta a evaluación."
        elif quotation.status is not PurchaseQuotationStatus.UNDER_EVALUATION:
            blocked_reason = "Esta cotización ya no está en evaluación."
        elif quotation.valid_until is not None and quotation.valid_until < now:
            blocked_reason = "La vigencia de esta oferta ya venció."
        elif offered is None or offered <= ZERO:
            blocked_reason = "El proveedor no ofreció cantidad para este producto."
        elif available is not None and available <= ZERO:
            blocked_reason = "El proveedor indicó que no tiene unidades disponibles."
        elif chosen_versions and quotation.id not in chosen_versions:
            blocked_reason = "Ya existe una adjudicación activa de otra versión de este proveedor para el producto."

        if remaining_quantity <= ZERO:
            blocked_reason = "La demanda de este producto ya quedó adjudicada."
        elif remaining_offer <= ZERO and blocked_reason is None:
            blocked_reason = "La cantidad ofrecida ya quedó adjudicada."
        return blocked_reason

    @staticmethod
    def _decisions_for_line(
        line_awards: tuple[PurchaseConsolidationAward, ...],
        quotation_by_id: dict[uuid.UUID, PurchaseQuotation],
        ordered_quantities: dict[uuid.UUID, Decimal],
    ) -> tuple[AwardDecision, ...]:
        return tuple(
            AwardDecision(
                id=award.id,
                purchase_quotation_id=award.purchase_quotation_id,
                quotation_code=(
                    quotation_by_id[award.purchase_quotation_id].code
                    if award.purchase_quotation_id in quotation_by_id
                    else "Cotización archivada"
                ),
                supplier_id=award.supplier_id,
                quantity=award.quantity,
                reason=award.reason,
                decided_by_id=award.decided_by_id,
                created_at=award.created_at,
                revoked_at=award.revoked_at,
                revoked_by_id=award.revoked_by_id,
                revocation_reason=award.revocation_reason,
                ordered_quantity=ordered_quantities.get(award.id, ZERO),
                remaining_to_order_quantity=(
                    max(
                        award.quantity - ordered_quantities.get(award.id, ZERO),
                        ZERO,
                    )
                    if award.is_active
                    else ZERO
                ),
            )
            for award in line_awards
        )

    @staticmethod
    def _required_reason(reason: str) -> str:
        value = reason.strip()
        if not value:
            raise ValidationError(
                "Escribe el motivo de la adjudicación o reversión.",
                code="purchase_award_reason_required",
            )
        return value
