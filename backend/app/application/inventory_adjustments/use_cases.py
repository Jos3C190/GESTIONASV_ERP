from __future__ import annotations

import builtins
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.domain.ports.inventory_adjustment_repository import InventoryAdjustmentRepository

MAX_ADJUSTMENT_LINES = 100
MAX_ADJUSTMENT_DECIMAL_PLACES = 6
MIN_ADJUSTMENT_REASON_LENGTH = 5


class InventoryAdjustmentUseCases:
    def __init__(self, repository: InventoryAdjustmentRepository) -> None:
        self._repository = repository

    @staticmethod
    def _validate_lines(lines: builtins.list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not lines or len(lines) > MAX_ADJUSTMENT_LINES:
            raise InventoryAdjustmentError(
                "Agregue de una a cien líneas válidas.", code="adjustment_lines_required"
            )
        output = []
        for index, line in enumerate(lines, start=1):
            try:
                quantity = Decimal(str(line["quantity_base"]))
            except (InvalidOperation, TypeError, ValueError, KeyError) as exc:
                raise InventoryAdjustmentError(
                    "La cantidad del ajuste no es válida.", code="adjustment_quantity_invalid"
                ) from exc
            exponent = quantity.as_tuple().exponent
            if (
                not quantity.is_finite()
                or not isinstance(exponent, int)
                or quantity <= 0
                or exponent < -MAX_ADJUSTMENT_DECIMAL_PLACES
            ):
                raise InventoryAdjustmentError(
                    "La cantidad debe ser positiva y tener hasta seis decimales.",
                    code="adjustment_quantity_invalid",
                )
            if (
                line.get("documented_unit_cost") is not None
                and line.get("documented_total_cost") is not None
            ):
                raise InventoryAdjustmentError(
                    "Indique costo unitario o costo total, no ambos.",
                    code="adjustment_cost_ambiguous",
                )
            output.append({**line, "line_number": index, "quantity_base": quantity})
        return output

    async def list(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        return await self._repository.list_adjustments(**kwargs)

    async def options(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.list_options(**kwargs)

    async def get(self, company_id: uuid.UUID, adjustment_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._repository.get_adjustment(company_id, adjustment_id)

    async def create(
        self, *, lines: builtins.list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        normalized = self._validate_lines(lines)
        if len((kwargs.get("reason") or "").strip()) < MIN_ADJUSTMENT_REASON_LENGTH:
            raise InventoryAdjustmentError(
                "Describa el motivo del ajuste.", code="adjustment_reason_required"
            )
        if not (kwargs.get("document_reference") or "").strip():
            raise InventoryAdjustmentError(
                "Indique la referencia del documento que respalda el ajuste.",
                code="adjustment_reference_required",
            )
        if kwargs["accounting_date"] < kwargs["operational_date"]:
            raise InventoryAdjustmentError(
                "La fecha contable no puede ser anterior a la fecha operativa.",
                code="adjustment_accounting_date_invalid",
            )
        return await self._repository.create_adjustment(lines=normalized, **kwargs)

    async def update(
        self, *, lines: builtins.list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        normalized = self._validate_lines(lines)
        if kwargs["accounting_date"] < kwargs["operational_date"]:
            raise InventoryAdjustmentError(
                "La fecha contable no puede ser anterior a la fecha operativa.",
                code="adjustment_accounting_date_invalid",
            )
        return await self._repository.update_adjustment(lines=normalized, **kwargs)

    async def approve(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.approve_adjustment(**kwargs)

    async def cancel(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.cancel_adjustment(**kwargs)

    async def apply(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.apply_adjustment(**kwargs)

    async def correct(self, **kwargs: Any) -> dict[str, Any]:
        return await self._repository.create_correction(**kwargs)
