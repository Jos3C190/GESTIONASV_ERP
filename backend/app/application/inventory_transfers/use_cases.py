"""Transfer lifecycle orchestration and value-independent validation."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.entities.inventory_transfer import (
    TransferDomainError,
    validate_positive_quantity,
)
from app.domain.ports.inventory_transfer_repository import InventoryTransferRepository

MIN_INCIDENT_REASON_LENGTH = 5


class InventoryTransferUseCases:
    def __init__(self, repository: InventoryTransferRepository) -> None:
        self._repository = repository

    @staticmethod
    def _validated_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not lines:
            raise TransferDomainError(
                "Agregue al menos una línea al traslado.",
                code="transfer_lines_required",
                status_code=422,
            )
        seen_units: set[uuid.UUID] = set()
        normalized: list[dict[str, Any]] = []
        for index, line in enumerate(lines, start=1):
            unit_id = line.get("handling_unit_id")
            if unit_id in seen_units:
                raise TransferDomainError(
                    "Una unidad logística solo puede asignarse una vez al mismo traslado.",
                    code="transfer_duplicate_handling_unit",
                    status_code=422,
                )
            seen_units.add(unit_id)
            try:
                quantity = Decimal(str(line.get("quantity_base")))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise TransferDomainError(
                    "La cantidad de la línea no es válida.",
                    code="transfer_quantity_invalid",
                    status_code=422,
                ) from exc
            validate_positive_quantity(quantity)
            allocations = []
            allocated_total = Decimal("0")
            seen_request_details: set[uuid.UUID] = set()
            for allocation in line.get("demand_allocations", []):
                request_detail_id = allocation["purchase_request_detail_id"]
                if request_detail_id in seen_request_details:
                    raise TransferDomainError(
                        "La misma línea de solicitud aparece más de una vez en una línea del traslado.",
                        code="transfer_duplicate_demand_allocation",
                        status_code=422,
                    )
                seen_request_details.add(request_detail_id)
                try:
                    allocated = Decimal(str(allocation.get("allocated_quantity")))
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise TransferDomainError(
                        "La cantidad asignada a la solicitud no es válida.",
                        code="transfer_demand_allocation_invalid",
                        status_code=422,
                    ) from exc
                validate_positive_quantity(allocated)
                allocated_total += allocated
                allocations.append(
                    {
                        "purchase_request_detail_id": request_detail_id,
                        "allocated_quantity": allocated,
                    }
                )
            if allocated_total > quantity:
                raise TransferDomainError(
                    "La demanda vinculada supera la cantidad planeada de esta línea.",
                    code="transfer_demand_allocation_exceeds_line",
                    status_code=422,
                )
            normalized.append(
                {
                    **line,
                    "line_number": index,
                    "quantity_base": quantity,
                    "demand_allocations": allocations,
                }
            )
        return normalized

    async def create_transfer(self, *, lines: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        return await self._repository.create_transfer(
            lines=self._validated_lines(lines), **kwargs
        )

    async def update_transfer(self, *, lines: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        return await self._repository.update_transfer(
            lines=self._validated_lines(lines), **kwargs
        )

    async def dispatch_transfer(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.dispatch_transfer(**kwargs)

    async def receive_transfer(self, *, lines: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        if not lines:
            raise TransferDomainError(
                "Indique las unidades recibidas.",
                code="transfer_receipt_lines_required",
                status_code=422,
            )
        seen_details: set[uuid.UUID] = set()
        for line in lines:
            if line["transfer_detail_id"] in seen_details:
                raise TransferDomainError(
                    "Cada detalle de traslado debe aparecer una sola vez por recepción.",
                    code="transfer_duplicate_receipt_detail",
                    status_code=422,
                )
            seen_details.add(line["transfer_detail_id"])
            validate_positive_quantity(Decimal(str(line["quantity_base"])))
        return await self._repository.receive_transfer(lines=lines, **kwargs)

    async def open_incident(self, *, reason: str, **kwargs: Any) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if len(normalized_reason) < MIN_INCIDENT_REASON_LENGTH:
            raise TransferDomainError(
                "Describa la incidencia con al menos cinco caracteres.",
                code="transfer_incident_reason_required",
                status_code=422,
            )
        return await self._repository.open_incident(reason=normalized_reason, **kwargs)

    async def resolve_incident(self, *, resolution: str, **kwargs: Any) -> dict[str, Any]:
        if resolution not in {"resume_transit", "close_received"}:
            raise TransferDomainError(
                "La resolución indicada no está habilitada.",
                code="transfer_incident_resolution_invalid",
                status_code=422,
            )
        return await self._repository.resolve_incident(resolution=resolution, **kwargs)

    async def cancel_transfer(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.cancel_transfer(**kwargs)

    async def get_transfer(self, company_id: uuid.UUID, transfer_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._repository.get_transfer(company_id, transfer_id)

    async def list_transfers(self, **kwargs: Any) -> list[dict[str, Any]]:
        return await self._repository.list_transfers(**kwargs)

    async def list_demand(self, **kwargs: Any) -> list[dict[str, Any]]:
        return await self._repository.list_demand(**kwargs)

    async def create_vehicle(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.create_vehicle(**kwargs)

    async def list_vehicles(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self._repository.list_vehicles(company_id)

    async def set_vehicle_status(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.set_vehicle_status(**kwargs)

