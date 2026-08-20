"""Orchestration boundary for inventory commands and queries."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain.entities.inventory import (
    CapacityDecision,
    CapacityReservation,
    InventoryItem,
    PackagingDefinition,
    PackagingType,
    PhysicalMeasures,
)
from app.domain.ports.inventory_repository import InventoryRepository

MAX_RESERVATION_MINUTES = 120
MIN_OVERRIDE_REASON_LENGTH = 10


class InventoryApplicationError(Exception):
    """Expected inventory failure translated by the HTTP adapter."""

    def __init__(self, message: str, *, code: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InventoryUseCases:
    def __init__(self, repository: InventoryRepository) -> None:
        self._repository = repository

    async def create_item(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
        base_unit_id: int,
    ) -> InventoryItem:
        if (product_id is None) == (variant_id is None):
            raise InventoryApplicationError(
                "Seleccione exactamente un producto independiente o una variante.",
                code="inventory_item_exact_target_required",
            )
        if base_unit_id <= 0:
            raise InventoryApplicationError(
                "La unidad base no es válida.", code="invalid_base_unit"
            )
        return await self._repository.create_item(
            company_id=company_id,
            product_id=product_id,
            variant_id=variant_id,
            base_unit_id=base_unit_id,
        )

    async def list_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> Sequence[PackagingDefinition]:
        if await self._repository.get_item(company_id, item_id) is None:
            raise InventoryApplicationError(
                "Identidad inventariable no encontrada.", code="inventory_item_not_found", status_code=404
            )
        return await self._repository.list_packaging(company_id, item_id)

    async def get_item(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> InventoryItem:
        item = await self._repository.get_item(company_id, item_id)
        if item is None:
            raise InventoryApplicationError(
                "Identidad inventariable no encontrada.",
                code="inventory_item_not_found",
                status_code=404,
            )
        return item

    async def get_item_by_target(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
    ) -> InventoryItem:
        if (product_id is None) == (variant_id is None):
            raise InventoryApplicationError(
                "Seleccione exactamente un producto independiente o una variante.",
                code="inventory_item_exact_target_required",
            )
        item = await self._repository.get_item_by_target(
            company_id=company_id,
            product_id=product_id,
            variant_id=variant_id,
        )
        if item is None:
            raise InventoryApplicationError(
                "El producto o variante todavía no tiene identidad inventariable.",
                code="inventory_item_not_found",
                status_code=404,
            )
        return item

    async def create_packaging(
        self,
        *,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        code: str,
        name: str,
        packaging_type: PackagingType,
        base_quantity: Decimal,
        measures: PhysicalMeasures,
        stackable: bool,
        max_stack: int | None,
        supersedes_id: uuid.UUID | None = None,
    ) -> PackagingDefinition:
        try:
            measures.validate()
        except ValueError as exc:
            raise InventoryApplicationError(str(exc), code="invalid_physical_measures") from exc
        if not code.strip() or not name.strip() or base_quantity <= 0:
            raise InventoryApplicationError(
                "Código, nombre y cantidad base son obligatorios.",
                code="invalid_packaging_definition",
            )
        if not stackable and max_stack is not None:
            raise InventoryApplicationError(
                "Una presentación no apilable no puede indicar altura de apilado.",
                code="invalid_stack_configuration",
            )
        return await self._repository.create_packaging(
            company_id=company_id,
            item_id=item_id,
            code=code.strip().upper(),
            name=name.strip(),
            packaging_type=packaging_type,
            base_quantity=base_quantity,
            measures=measures,
            stackable=stackable,
            max_stack=max_stack,
            supersedes_id=supersedes_id,
        )

    async def deactivate_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID, packaging_id: uuid.UUID
    ) -> None:
        await self._repository.deactivate_packaging(company_id, item_id, packaging_id)

    async def preview_capacity(self, **kwargs: Any) -> CapacityDecision:
        return await self._repository.preview_capacity(**kwargs)

    async def reserve_capacity(
        self,
        *,
        duration_minutes: int = 30,
        **kwargs: Any,
    ) -> tuple[CapacityReservation, CapacityDecision]:
        if duration_minutes < 1 or duration_minutes > MAX_RESERVATION_MINUTES:
            raise InventoryApplicationError(
                "La reserva debe durar entre 1 y 120 minutos.", code="invalid_reservation_duration"
            )
        return await self._repository.reserve_capacity(
            expires_at=datetime.now(UTC) + timedelta(minutes=duration_minutes), **kwargs
        )

    async def change_reservation_status(self, **kwargs: Any) -> CapacityReservation:
        return await self._repository.change_reservation_status(**kwargs)

    async def verify_handling_unit_measurements(
        self, *, measures: PhysicalMeasures, source: str, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            measures.validate()
        except ValueError as exc:
            raise InventoryApplicationError(
                str(exc), code="invalid_physical_measures"
            ) from exc
        if not measures.is_complete:
            raise InventoryApplicationError(
                "La verificación requiere peso y volumen completos.",
                code="verified_measurements_required",
            )
        return await self._repository.verify_handling_unit_measurements(
            measures=measures, source=source, **kwargs
        )

    async def list_handling_units(self, **kwargs: Any) -> Sequence[dict[str, Any]]:
        return await self._repository.list_handling_units(**kwargs)

    async def list_balances(self, **kwargs: Any) -> Sequence[dict[str, Any]]:
        return await self._repository.list_balances(**kwargs)

    async def post_movement(
        self,
        *,
        movement_type: str,
        lines: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not lines:
            raise InventoryApplicationError(
                "El movimiento debe contener al menos una línea.", code="movement_lines_required"
            )
        if movement_type == "reversal":
            raise InventoryApplicationError(
                "Las reversiones deben originarse desde un movimiento publicado.",
                code="direct_reversal_not_allowed",
            )
        allowed_types = {
            "receipt",
            "putaway",
            "transfer",
            "pick",
            "shipment",
            "adjustment_in",
            "adjustment_out",
        }
        if movement_type not in allowed_types:
            raise InventoryApplicationError(
                "El tipo de movimiento no está habilitado.", code="invalid_movement_type"
            )
        for line in lines:
            source = line.get("from_location_id")
            destination = line.get("to_location_id")
            if movement_type in {"receipt", "adjustment_in"} and (source or not destination):
                raise InventoryApplicationError(
                    "Una entrada requiere destino y no admite ubicación de origen.",
                    code="invalid_movement_endpoints",
                )
            if movement_type in {"pick", "shipment", "adjustment_out"} and (
                not source or destination
            ):
                raise InventoryApplicationError(
                    "Una salida requiere origen y no admite ubicación de destino.",
                    code="invalid_movement_endpoints",
                )
            if movement_type in {"putaway", "transfer"} and (
                not source or not destination
            ):
                raise InventoryApplicationError(
                    "El traslado requiere ubicaciones de origen y destino.",
                    code="invalid_movement_endpoints",
                )
        return await self._repository.post_movement(
            movement_type=movement_type, lines=lines, **kwargs
        )

    async def capacity_summary(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.capacity_summary(**kwargs)

    async def create_operational_override(
        self, *, reason: str, valid_until: datetime, **kwargs: Any
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        if valid_until.tzinfo is None or valid_until.utcoffset() is None:
            raise InventoryApplicationError(
                "La vigencia debe incluir zona horaria.", code="invalid_override_expiry"
            )
        if valid_until <= now or valid_until > now + timedelta(hours=24):
            raise InventoryApplicationError(
                "La excepción debe vencer dentro de las próximas 24 horas.",
                code="invalid_override_expiry",
            )
        if len(reason.strip()) < MIN_OVERRIDE_REASON_LENGTH:
            raise InventoryApplicationError(
                "Documente una razón operativa de al menos 10 caracteres.",
                code="override_reason_required",
            )
        return await self._repository.create_operational_override(
            reason=reason.strip(), valid_until=valid_until, **kwargs
        )

    async def revoke_operational_override(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.revoke_operational_override(**kwargs)
