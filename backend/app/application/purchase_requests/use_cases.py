"""Application use cases for internal purchase requests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
    PurchaseRequestTransitionError,
    ensure_purchase_request_transition,
)
from app.domain.ports.purchase_request_repository import (
    PurchaseProductReference,
    PurchaseRequestRepository,
)


@dataclass(frozen=True, slots=True)
class PurchaseRequestLineDraft:
    product_id: int
    quantity: Decimal
    description: str | None = None
    notes: str | None = None


class PurchaseRequestUseCases:
    def __init__(self, repository: PurchaseRequestRepository) -> None:
        self._repository = repository

    async def list_requests(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseRequestStatus | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseRequest], int]:
        return await self._repository.list_requests(
            company_id,
            status=status,
            branch_id=branch_id,
            skip=skip,
            limit=limit,
        )

    async def get_request(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest:
        request = await self._repository.get_request(company_id, request_id)
        if request is None:
            raise NotFoundError(
                "Solicitud de compra no encontrada.",
                code="purchase_request_not_found",
            )
        return request

    async def create_request(
        self,
        *,
        company_id: uuid.UUID,
        requested_by_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        justification: str,
        lines: tuple[PurchaseRequestLineDraft, ...],
        required_date: datetime | None = None,
        notes: str | None = None,
    ) -> PurchaseRequest:
        await self._validate_operational_scope(company_id, branch_id, warehouse_id)
        request_id = uuid.uuid4()
        details = await self._build_details(company_id, request_id, lines)
        code = await self._repository.allocate_next_code(company_id)
        request_date = datetime.now(UTC)

        request = self._build_request(
            request_id=request_id,
            company_id=company_id,
            code=code,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            requested_by_id=requested_by_id,
            request_date=request_date,
            required_date=required_date,
            justification=justification,
            notes=notes,
            details=details,
        )
        return await self._repository.add_request(request)

    async def replace_draft(
        self,
        *,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        justification: str,
        lines: tuple[PurchaseRequestLineDraft, ...],
        required_date: datetime | None = None,
        notes: str | None = None,
    ) -> PurchaseRequest:
        current = await self._get_for_update(company_id, request_id)
        if current.status is not PurchaseRequestStatus.DRAFT:
            raise BusinessRuleError(
                "Solo las solicitudes en borrador pueden editarse.",
                code="purchase_request_not_editable",
            )

        await self._validate_operational_scope(company_id, branch_id, warehouse_id)
        details = await self._build_details(company_id, current.id, lines)
        replacement = self._build_request(
            request_id=current.id,
            company_id=current.company_id,
            code=current.code,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            requested_by_id=current.requested_by_id,
            request_date=current.request_date,
            required_date=required_date,
            justification=justification,
            notes=notes,
            details=details,
            status=current.status,
            created_at=current.created_at,
            updated_at=current.updated_at,
        )
        saved = await self._repository.replace_draft(replacement)
        if saved is None:
            raise NotFoundError(
                "Solicitud de compra no encontrada.",
                code="purchase_request_not_found",
            )
        return saved

    async def submit_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> PurchaseRequest:
        return await self._transition(company_id, request_id, PurchaseRequestStatus.SUBMITTED)

    async def approve_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> PurchaseRequest:
        return await self._transition(company_id, request_id, PurchaseRequestStatus.APPROVED)

    async def reject_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> PurchaseRequest:
        return await self._transition(company_id, request_id, PurchaseRequestStatus.REJECTED)

    async def cancel_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> PurchaseRequest:
        return await self._transition(company_id, request_id, PurchaseRequestStatus.CANCELLED)

    async def _get_for_update(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest:
        request = await self._repository.get_request_for_update(company_id, request_id)
        if request is None:
            raise NotFoundError(
                "Solicitud de compra no encontrada.",
                code="purchase_request_not_found",
            )
        return request

    async def _transition(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        target: PurchaseRequestStatus,
    ) -> PurchaseRequest:
        current = await self._get_for_update(company_id, request_id)
        try:
            ensure_purchase_request_transition(current.status, target)
        except PurchaseRequestTransitionError as exc:
            raise BusinessRuleError(
                "La transición solicitada no es válida para el estado actual.",
                code="purchase_request_invalid_transition",
            ) from exc

        updated = await self._repository.update_status(company_id, request_id, target)
        if updated is None:
            raise NotFoundError(
                "Solicitud de compra no encontrada.",
                code="purchase_request_not_found",
            )
        return updated

    async def _validate_operational_scope(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> None:
        if not await self._repository.is_branch_available(company_id, branch_id):
            raise NotFoundError(
                "Sucursal no encontrada o no disponible.",
                code="purchase_request_branch_not_found",
            )
        if not await self._repository.is_warehouse_available(
            company_id, branch_id, warehouse_id
        ):
            raise NotFoundError(
                "Almacén no encontrado o no disponible para la sucursal seleccionada.",
                code="purchase_request_warehouse_not_found",
            )

    async def _build_details(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        lines: tuple[PurchaseRequestLineDraft, ...],
    ) -> tuple[PurchaseRequestDetail, ...]:
        if not lines:
            raise ValidationError(
                "La solicitud de compra debe contener al menos un detalle.",
                code="purchase_request_details_required",
            )

        product_ids = [line.product_id for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise ValidationError(
                "Un producto no puede repetirse dentro de la misma solicitud.",
                code="purchase_request_duplicate_product",
            )

        details: list[PurchaseRequestDetail] = []
        for line in lines:
            reference = await self._repository.get_product_reference(company_id, line.product_id)
            self._validate_product_reference(line.product_id, reference)
            assert reference is not None
            try:
                details.append(
                    PurchaseRequestDetail(
                        id=uuid.uuid4(),
                        purchase_request_id=request_id,
                        product_id=line.product_id,
                        unit_id=reference.purchase_unit_id,
                        quantity=line.quantity,
                        description=line.description,
                        notes=line.notes,
                    )
                )
            except ValueError as exc:
                raise ValidationError(
                    str(exc),
                    code="purchase_request_quantity_invalid",
                ) from exc
        return tuple(details)

    @staticmethod
    def _validate_product_reference(
        product_id: int,
        reference: PurchaseProductReference | None,
    ) -> None:
        if reference is None:
            raise NotFoundError(
                f"Producto {product_id} no encontrado.",
                code="purchase_request_product_not_found",
            )
        if (
            not reference.is_active
            or reference.lifecycle_status != "active"
            or not reference.can_purchase
        ):
            raise BusinessRuleError(
                f"El producto {product_id} no está habilitado para compras.",
                code="purchase_request_product_not_purchasable",
            )
        if not reference.unit_enabled:
            raise BusinessRuleError(
                f"La unidad de compra del producto {product_id} no está habilitada para la empresa.",
                code="purchase_request_purchase_unit_unavailable",
            )

    @staticmethod
    def _build_request(
        *,
        request_id: uuid.UUID,
        company_id: uuid.UUID,
        code: str,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        requested_by_id: uuid.UUID,
        request_date: datetime,
        required_date: datetime | None,
        justification: str,
        notes: str | None,
        details: tuple[PurchaseRequestDetail, ...],
        status: PurchaseRequestStatus = PurchaseRequestStatus.DRAFT,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> PurchaseRequest:
        try:
            return PurchaseRequest(
                id=request_id,
                company_id=company_id,
                code=code,
                branch_id=branch_id,
                warehouse_id=warehouse_id,
                requested_by_id=requested_by_id,
                request_date=request_date,
                required_date=required_date,
                justification=justification,
                status=status,
                notes=notes,
                details=details,
                created_at=created_at,
                updated_at=updated_at,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="purchase_request_invalid",
            ) from exc
