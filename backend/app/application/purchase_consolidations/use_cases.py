"""Application rules for editable, auditable purchase consolidations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_consolidation import (
    BranchDemandLevel,
    ConsolidationLine,
    ConsolidationQuotationStatusChange,
    ConsolidationSource,
    ConsolidationWorkItem,
    PurchaseConsolidation,
    PurchaseConsolidationAward,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_quotation import (
    PurchaseQuotationStatus,
    ensure_purchase_quotation_transition,
)
from app.domain.entities.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.domain.ports.purchase_consolidation_repository import PurchaseConsolidationRepository
from app.domain.ports.purchase_quotation_repository import PurchaseQuotationRepository
from app.domain.ports.purchase_request_repository import PurchaseRequestRepository

MAX_UNAWARDED_PREVIEW = 5


@dataclass(frozen=True, slots=True)
class SourceQuantityChange:
    source_id: uuid.UUID
    included_quantity: Decimal
    reason: str
    demand_level: BranchDemandLevel | None = None
    update_demand_level: bool = False


@dataclass(frozen=True, slots=True)
class BranchDemandAssignment:
    branch_id: uuid.UUID
    product_id: int
    level: BranchDemandLevel


@dataclass(frozen=True, slots=True)
class CentralDemandDraft:
    product_id: int
    quantity: Decimal
    reason: str
    line_id: uuid.UUID | None = None


class PurchaseConsolidationUseCases:
    def __init__(
        self,
        repository: PurchaseConsolidationRepository,
        request_repository: PurchaseRequestRepository,
        quotation_repository: PurchaseQuotationRepository | None = None,
    ) -> None:
        self._repository = repository
        self._request_repository = request_repository
        self._quotation_repository = quotation_repository

    async def list_work_items(
        self, company_id: uuid.UUID, **filters: object
    ) -> tuple[list[ConsolidationWorkItem], int]:
        return await self._repository.list_work_items(company_id, **filters)  # type: ignore[arg-type]

    async def list_approved_requests(
        self, company_id: uuid.UUID, **filters: object
    ) -> tuple[list[dict[str, object]], int]:
        return await self._repository.list_approved_requests(company_id, **filters)  # type: ignore[arg-type]

    async def resolve_selected_requests(
        self, company_id: uuid.UUID, request_ids: tuple[uuid.UUID, ...]
    ) -> list[dict[str, object]]:
        return await self._repository.resolve_selected_requests(company_id, request_ids)

    async def get(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> PurchaseConsolidation:
        item = await self._repository.get(company_id, consolidation_id)
        if item is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.", code="purchase_consolidation_not_found"
            )
        return item

    async def get_request_for_consolidation(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> PurchaseRequest | None:
        return await self._request_repository.get_request(company_id, request_id)

    async def create(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_ids: tuple[uuid.UUID, ...],
        period_start: date,
        period_end: date,
        central_warehouse_id: uuid.UUID | None,
        notes: str | None,
        demand_levels: tuple[BranchDemandAssignment, ...] = (),
    ) -> PurchaseConsolidation:
        if period_end < period_start:
            raise ValidationError(
                "El fin del período debe ser igual o posterior al inicio.",
                code="purchase_consolidation_period_invalid",
            )
        if not request_ids:
            raise ValidationError(
                "Selecciona al menos una solicitud aprobada.",
                code="purchase_consolidation_requests_required",
            )
        if len(request_ids) != len(set(request_ids)):
            raise ValidationError(
                "No repitas solicitudes en el mismo consolidado.",
                code="purchase_consolidation_duplicate_request",
            )
        if (
            central_warehouse_id is not None
            and not await self._repository.central_warehouse_available(
                company_id, central_warehouse_id
            )
        ):
            raise BusinessRuleError(
                "El destino seleccionado no está marcado como bodega madre activa.",
                code="purchase_consolidation_warehouse_not_central",
            )

        consolidation_id = uuid.uuid4()
        code = await self._repository.allocate_next_code(company_id)
        consolidation = PurchaseConsolidation(
            id=consolidation_id,
            company_id=company_id,
            code=code,
            period_start=period_start,
            period_end=period_end,
            status=PurchaseConsolidationStatus.DRAFT,
            created_by_id=actor_id,
            created_at=None,
            updated_at=None,
            central_warehouse_id=central_warehouse_id,
            central_warehouse_name=None,
            notes=notes,
            lines=(),
        )
        consolidation = await self._append_requests(
            consolidation, request_ids, enforce_period=True, demand_levels=demand_levels
        )
        return await self._repository.create(consolidation)

    async def add_requests(
        self,
        *,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_ids: tuple[uuid.UUID, ...],
        reason: str,
    ) -> PurchaseConsolidation:
        reason = self._required_reason(reason, "Indica por qué agregas estas solicitudes.")
        current = await self._get_for_update(company_id, consolidation_id)
        self._ensure_editable(current)
        await self._ensure_no_active_awards(company_id, consolidation_id)
        updated = await self._append_requests(current, request_ids, enforce_period=False)
        saved = await self._repository.save_draft(updated, actor_id=actor_id, change_reason=reason)
        if saved is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.", code="purchase_consolidation_not_found"
            )
        return saved

    async def update_draft(  # noqa: C901
        self,
        *,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        actor_id: uuid.UUID,
        change_reason: str,
        source_changes: tuple[SourceQuantityChange, ...],
        central_demands: tuple[CentralDemandDraft, ...],
        notes: str | None,
        central_warehouse_id: uuid.UUID | None = None,
        update_central_warehouse: bool = False,
    ) -> PurchaseConsolidation:
        change_reason = self._required_reason(change_reason, "Explica el motivo del cambio.")
        current = await self._get_for_update(company_id, consolidation_id)
        self._ensure_editable(current)
        warehouse_will_change = (
            update_central_warehouse and central_warehouse_id != current.central_warehouse_id
        )
        if source_changes or central_demands or warehouse_will_change:
            await self._ensure_no_active_awards(company_id, consolidation_id)
        source_map = {source.id: source for line in current.lines for source in line.sources}
        if len({change.source_id for change in source_changes}) != len(source_changes):
            raise ValidationError(
                "Una línea fuente aparece más de una vez.",
                code="purchase_consolidation_duplicate_source",
            )

        line_updates: dict[uuid.UUID, ConsolidationLine] = {}
        for change in source_changes:
            source = source_map.get(change.source_id)
            if source is None:
                raise NotFoundError(
                    "La línea fuente no pertenece a este consolidado.",
                    code="purchase_consolidation_source_not_found",
                )
            if not change.included_quantity.is_finite() or change.included_quantity < 0:
                raise ValidationError(
                    "La cantidad consolidada no puede ser negativa.",
                    code="purchase_consolidation_quantity_invalid",
                )
            if change.included_quantity > source.requested_quantity:
                raise ValidationError(
                    "La cantidad incluida no puede superar la cantidad solicitada.",
                    code="purchase_consolidation_quantity_exceeds_source",
                )
            reason = source.reason
            if change.included_quantity != source.included_quantity:
                reason = self._required_reason(
                    change.reason, "Explica la reducción o exclusión de la cantidad."
                )
            replacement_source = replace(
                source,
                included_quantity=change.included_quantity,
                reason=reason,
                demand_level=(
                    change.demand_level if change.update_demand_level else source.demand_level
                ),
            )
            for line in current.lines:
                if any(item.id == source.id for item in line.sources):
                    line_updates[line.id] = replace(
                        line,
                        sources=tuple(
                            replacement_source if item.id == source.id else item
                            for item in line.sources
                        ),
                    )
                    break

        # Keep this mutable while applying source and central-demand edits.
        # The same pass may replace an existing central line or add a new one.
        lines = [line_updates.get(line.id, line) for line in current.lines]
        effective_central_warehouse_id = (
            central_warehouse_id if update_central_warehouse else current.central_warehouse_id
        )
        if (
            any(draft.quantity.is_finite() and draft.quantity > 0 for draft in central_demands)
            and effective_central_warehouse_id is None
        ):
            raise BusinessRuleError(
                "Hay cantidades de demanda central, pero no se seleccionó una bodega de destino.",
                code="purchase_consolidation_central_warehouse_required",
            )
        for draft in central_demands:
            if draft.product_id <= 0 or not draft.quantity.is_finite() or draft.quantity < 0:
                raise ValidationError(
                    "El producto y la cantidad central deben ser válidos.",
                    code="purchase_consolidation_central_quantity_invalid",
                )
            reason = self._required_reason(draft.reason, "Explica la necesidad de bodega central.")
            if draft.line_id is not None:
                existing_index = next(
                    (i for i, line in enumerate(lines) if line.id == draft.line_id), None
                )
                if existing_index is None:
                    raise NotFoundError(
                        "La línea central no pertenece a este consolidado.",
                        code="purchase_consolidation_line_not_found",
                    )
                line = lines[existing_index]
                if line.product_id != draft.product_id:
                    raise ValidationError(
                        "No se puede cambiar el producto de una línea central existente.",
                        code="purchase_consolidation_product_immutable",
                    )
                lines[existing_index] = replace(
                    line, central_quantity=draft.quantity, central_reason=reason
                )
                continue
            if draft.quantity <= 0:
                raise ValidationError(
                    "Una nueva necesidad central debe ser mayor que cero.",
                    code="purchase_consolidation_central_quantity_invalid",
                )
            reference = await self._request_repository.get_product_reference(
                company_id, draft.product_id
            )
            if reference is None:
                raise NotFoundError(
                    f"Producto {draft.product_id} no encontrado.",
                    code="purchase_consolidation_product_not_found",
                )
            if (
                not reference.is_active
                or reference.lifecycle_status != "active"
                or not reference.can_purchase
                or not reference.unit_enabled
            ):
                raise BusinessRuleError(
                    f"El producto {draft.product_id} no está habilitado para compra.",
                    code="purchase_consolidation_product_not_purchasable",
                )
            unit_id = reference.purchase_unit_id
            existing_index = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if line.product_id == draft.product_id and line.unit_id == unit_id
                ),
                None,
            )
            if existing_index is None:
                lines.append(
                    ConsolidationLine(
                        id=uuid.uuid4(),
                        product_id=draft.product_id,
                        product_sku=f"PRD-{draft.product_id}",
                        product_name=f"Producto {draft.product_id}",
                        unit_id=unit_id,
                        unit_name=f"Unidad {unit_id}",
                        central_quantity=draft.quantity,
                        central_reason=reason,
                        sources=(),
                    )
                )
            else:
                line = lines[existing_index]
                lines[existing_index] = replace(
                    line,
                    central_quantity=line.central_quantity + draft.quantity,
                    central_reason=reason,
                )

        demand_levels_by_pair: dict[tuple[uuid.UUID, int], BranchDemandLevel | None] = {}
        for line in lines:
            for source in line.sources:
                key = (source.branch_id, line.product_id)
                existing_level = demand_levels_by_pair.get(key)
                if key in demand_levels_by_pair and existing_level != source.demand_level:
                    raise ValidationError(
                        "Usa el mismo nivel manual para todas las solicitudes del producto en la sucursal.",
                        code="purchase_consolidation_inconsistent_demand_level",
                    )
                demand_levels_by_pair[key] = source.demand_level

        if (
            effective_central_warehouse_id is not None
            and not await self._repository.central_warehouse_available(
                company_id, effective_central_warehouse_id
            )
        ):
            raise BusinessRuleError(
                "El destino seleccionado no está marcado como bodega madre activa.",
                code="purchase_consolidation_warehouse_not_central",
            )
        if effective_central_warehouse_id is None and any(
            line.central_quantity > 0 for line in lines
        ):
            raise BusinessRuleError(
                "Las líneas de demanda central necesitan una bodega destino.",
                code="purchase_consolidation_central_warehouse_required",
            )
        replacement = replace(
            current,
            lines=tuple(lines),
            notes=notes,
            central_warehouse_id=effective_central_warehouse_id,
        )
        saved = await self._repository.save_draft(
            replacement, actor_id=actor_id, change_reason=change_reason
        )
        if saved is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.", code="purchase_consolidation_not_found"
            )
        return saved

    async def cancel(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidation:
        current = await self._get_for_update(company_id, consolidation_id)
        if current.status is not PurchaseConsolidationStatus.DRAFT:
            raise BusinessRuleError(
                "Solo se pueden cancelar consolidados en borrador.",
                code="purchase_consolidation_not_cancellable",
            )
        await self._ensure_no_active_awards(company_id, consolidation_id)
        reason = self._required_reason(reason, "Indica por qué se cancela el consolidado.")
        saved = await self._repository.cancel(
            company_id, consolidation_id, actor_id=actor_id, reason=reason
        )
        if saved is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.", code="purchase_consolidation_not_found"
            )
        return saved

    async def close(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        covered_outside_consolidation: bool = False,
    ) -> PurchaseConsolidation:
        current = await self._get_for_update(company_id, consolidation_id)
        if current.status not in {
            PurchaseConsolidationStatus.DRAFT,
            PurchaseConsolidationStatus.FROZEN,
        }:
            raise BusinessRuleError(
                "Solo se pueden cerrar consolidados que aún estén en proceso.",
                code="purchase_consolidation_not_closable",
            )
        reason = self._required_reason(reason, "Indica por qué se cierra el consolidado.")
        awards = await self._repository.list_awards(company_id, consolidation_id)
        active_awards = tuple(award for award in awards if award.is_active)

        uncovered = self._unawarded_lines(current, active_awards)
        if uncovered and not covered_outside_consolidation:
            details = "; ".join(
                f"{line['product_name']}: {line['quantity']} {line['unit_name']}"
                for line in uncovered[:MAX_UNAWARDED_PREVIEW]
            )
            if len(uncovered) > MAX_UNAWARDED_PREVIEW:
                details += f"; y {len(uncovered) - MAX_UNAWARDED_PREVIEW} producto(s) más"
            raise BusinessRuleError(
                f"Aún queda demanda sin adjudicar: {details}. Si ya está cubierta por inventario o compras individuales cerradas, confirma esa opción para cerrar sin volver a solicitarla.",
                code="purchase_consolidation_awards_incomplete",
            )

        coverage_basis = (
            "covered_outside_consolidation" if uncovered else "awarded_in_consolidation"
        )
        quotation_status_changes: list[ConsolidationQuotationStatusChange] = []
        if self._quotation_repository is not None:
            quotations = await self._quotation_repository.list_consolidation_quotations(
                company_id, consolidation_id
            )
            awarded_quotation_ids = {award.purchase_quotation_id for award in active_awards}
            open_quotation_statuses = {
                PurchaseQuotationStatus.REQUESTED,
                PurchaseQuotationStatus.RECEIVED,
                PurchaseQuotationStatus.UNDER_EVALUATION,
            }
            for quotation in quotations:
                if quotation.status not in open_quotation_statuses:
                    continue
                target_status = (
                    PurchaseQuotationStatus.SELECTED
                    if quotation.id in awarded_quotation_ids
                    else PurchaseQuotationStatus.NOT_SELECTED
                )
                ensure_purchase_quotation_transition(quotation.status, target_status)
                quotation_status_changes.append(
                    ConsolidationQuotationStatusChange(
                        quotation_id=quotation.id,
                        expected_status=quotation.status,
                        target_status=target_status,
                    )
                )
        if quotation_status_changes:
            saved = await self._repository.close(
                company_id,
                consolidation_id,
                actor_id=actor_id,
                reason=reason,
                coverage_basis=coverage_basis,
                unawarded_lines=tuple(uncovered),
                quotation_status_changes=tuple(quotation_status_changes),
            )
        else:
            saved = await self._repository.close(
                company_id,
                consolidation_id,
                actor_id=actor_id,
                reason=reason,
                coverage_basis=coverage_basis,
                unawarded_lines=tuple(uncovered),
            )
        if saved is None:
            raise BusinessRuleError(
                "El consolidado cambió de estado y ya no se puede cerrar.",
                code="purchase_consolidation_not_closable",
            )
        return saved

    async def _append_requests(
        self,
        consolidation: PurchaseConsolidation,
        request_ids: tuple[uuid.UUID, ...],
        *,
        enforce_period: bool,
        demand_levels: tuple[BranchDemandAssignment, ...] = (),
    ) -> PurchaseConsolidation:
        if not request_ids or len(request_ids) != len(set(request_ids)):
            raise ValidationError(
                "Selecciona solicitudes sin repetir.",
                code="purchase_consolidation_requests_invalid",
            )
        lines = list(consolidation.lines)
        source_by_detail = {
            source.purchase_request_detail_id: source for line in lines for source in line.sources
        }
        demand_by_pair, provided_demand_pairs = self._demand_assignments(lines, demand_levels)
        matched_demand_pairs: set[tuple[uuid.UUID, int]] = set()
        seen_new: set[uuid.UUID] = set()
        for request_id in request_ids:
            request = await self._eligible_request(
                consolidation, request_id, enforce_period=enforce_period
            )
            for detail in request.details:
                if detail.id in source_by_detail or detail.id in seen_new:
                    continue
                if await self._repository.has_active_source(consolidation.company_id, detail.id):
                    raise BusinessRuleError(
                        f"La línea de {request.code} ya pertenece a otro consolidado activo.",
                        code="purchase_consolidation_request_already_linked",
                    )
                seen_new.add(detail.id)
                index = next(
                    (
                        i
                        for i, line in enumerate(lines)
                        if line.product_id == detail.product_id and line.unit_id == detail.unit_id
                    ),
                    None,
                )
                if index is None:
                    line = ConsolidationLine(
                        id=uuid.uuid4(),
                        product_id=detail.product_id,
                        product_sku=f"PRD-{detail.product_id}",
                        product_name=f"Producto {detail.product_id}",
                        unit_id=detail.unit_id,
                        unit_name=f"Unidad {detail.unit_id}",
                        central_quantity=Decimal("0"),
                        central_reason=None,
                        sources=(),
                    )
                    lines.append(line)
                    index = len(lines) - 1
                line = lines[index]
                source = ConsolidationSource(
                    id=uuid.uuid4(),
                    purchase_request_id=request.id,
                    purchase_request_detail_id=detail.id,
                    request_code=request.code,
                    branch_id=request.branch_id,
                    branch_name=request.branch_name,
                    warehouse_id=request.warehouse_id,
                    warehouse_name=request.warehouse_name,
                    requester_name=None,
                    required_date=request.required_date,
                    requested_quantity=detail.quantity,
                    included_quantity=detail.quantity,
                    demand_level=demand_by_pair.get((request.branch_id, detail.product_id)),
                )
                pair = (request.branch_id, detail.product_id)
                if pair in provided_demand_pairs:
                    matched_demand_pairs.add(pair)
                lines[index] = replace(line, sources=(*line.sources, source))
        if provided_demand_pairs != matched_demand_pairs:
            raise ValidationError(
                "Un nivel de demanda no corresponde a una sucursal y producto de las solicitudes seleccionadas.",
                code="purchase_consolidation_demand_level_out_of_scope",
            )
        return replace(consolidation, lines=tuple(lines))

    async def _get_for_update(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> PurchaseConsolidation:
        item = await self._repository.get(company_id, consolidation_id, for_update=True)
        if item is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.", code="purchase_consolidation_not_found"
            )
        return item

    async def _ensure_no_active_awards(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> None:
        awards = await self._repository.list_awards(company_id, consolidation_id)
        if any(award.is_active for award in awards):
            raise BusinessRuleError(
                "Revierte las adjudicaciones activas antes de cambiar o cancelar la demanda.",
                code="purchase_consolidation_active_awards_block_edit",
            )

    @staticmethod
    def _ensure_editable(item: PurchaseConsolidation) -> None:
        if item.status is not PurchaseConsolidationStatus.DRAFT:
            raise BusinessRuleError(
                "Solo un consolidado en borrador puede editarse.",
                code="purchase_consolidation_not_editable",
            )

    @staticmethod
    def _required_reason(value: str, message: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValidationError(message, code="purchase_consolidation_reason_required")
        return reason

    @staticmethod
    def _unawarded_lines(
        current: PurchaseConsolidation, active_awards: tuple[PurchaseConsolidationAward, ...]
    ) -> list[dict[str, object]]:
        awarded_by_line: dict[uuid.UUID, Decimal] = {}
        for award in active_awards:
            awarded_by_line[award.consolidation_line_id] = (
                awarded_by_line.get(award.consolidation_line_id, Decimal("0")) + award.quantity
            )
        uncovered: list[dict[str, object]] = []
        has_demand = False
        for line in current.lines:
            demand = line.total_quantity
            awarded = awarded_by_line.get(line.id, Decimal("0"))
            if demand > 0:
                has_demand = True
            if awarded > demand:
                raise BusinessRuleError(
                    f"La adjudicación de {line.product_name} supera la demanda consolidada.",
                    code="purchase_consolidation_award_exceeds_demand",
                )
            if awarded < demand:
                uncovered.append(
                    {
                        "product_id": line.product_id,
                        "product_name": line.product_name,
                        "quantity": str(demand - awarded),
                        "unit_name": line.unit_name,
                    }
                )
        if not has_demand:
            raise BusinessRuleError(
                "No hay cantidades de demanda para cerrar en este consolidado.",
                code="purchase_consolidation_demand_required",
            )
        return uncovered

    @staticmethod
    def _demand_assignments(
        lines: list[ConsolidationLine], demand_levels: tuple[BranchDemandAssignment, ...]
    ) -> tuple[dict[tuple[uuid.UUID, int], BranchDemandLevel], set[tuple[uuid.UUID, int]]]:
        demand_by_pair: dict[tuple[uuid.UUID, int], BranchDemandLevel] = {}
        provided_demand_pairs: set[tuple[uuid.UUID, int]] = set()
        for line in lines:
            for source in line.sources:
                if source.demand_level is None:
                    continue
                key = (source.branch_id, line.product_id)
                inherited_level = demand_by_pair.get(key)
                if inherited_level is not None and inherited_level != source.demand_level:
                    raise ValidationError(
                        "El consolidado ya tiene niveles diferentes para el mismo producto de una sucursal.",
                        code="purchase_consolidation_inconsistent_demand_level",
                    )
                demand_by_pair[key] = source.demand_level
        for assignment in demand_levels:
            key = (assignment.branch_id, assignment.product_id)
            if key in provided_demand_pairs:
                raise ValidationError(
                    "Un nivel de demanda aparece más de una vez para la misma sucursal y producto.",
                    code="purchase_consolidation_duplicate_demand_level",
                )
            demand_by_pair[key] = assignment.level
            provided_demand_pairs.add(key)
        return demand_by_pair, provided_demand_pairs

    async def _eligible_request(
        self, consolidation: PurchaseConsolidation, request_id: uuid.UUID, *, enforce_period: bool
    ) -> PurchaseRequest:
        request = await self._request_repository.get_request(consolidation.company_id, request_id)
        if request is None:
            raise NotFoundError(
                "Una solicitud seleccionada no existe.",
                code="purchase_consolidation_request_not_found",
            )
        if request.status is not PurchaseRequestStatus.APPROVED:
            raise BusinessRuleError(
                f"La solicitud {request.code} debe estar aprobada para consolidarse.",
                code="purchase_consolidation_request_not_approved",
            )
        request_timestamp = request.request_date
        if request_timestamp.tzinfo is None:
            request_timestamp = request_timestamp.replace(tzinfo=UTC)
        request_day = request_timestamp.astimezone(ZoneInfo("America/El_Salvador")).date()
        if enforce_period and not (
            consolidation.period_start <= request_day <= consolidation.period_end
        ):
            raise BusinessRuleError(
                f"La solicitud {request.code} está fuera del período elegido.",
                code="purchase_consolidation_request_outside_period",
            )
        return request
