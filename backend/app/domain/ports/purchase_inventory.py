"""Inventory boundary used when a supplier receipt is verified."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.purchase import Purchase, PurchaseVerificationLine


@dataclass(frozen=True, slots=True)
class PurchaseReceiptReadiness:
    required: bool
    ready: bool
    retaceo_id: uuid.UUID | None = None
    retaceo_code: str | None = None
    retaceo_status: str | None = None


class PurchaseInventoryGateway(Protocol):
    async def receipt_readiness(self, purchase: Purchase) -> PurchaseReceiptReadiness: ...
    async def valuation_currency(self, company_id: uuid.UUID) -> str | None: ...

    async def post_verified_receipt(
        self,
        *,
        purchase: Purchase,
        lines: tuple[PurchaseVerificationLine, ...],
        actor_id: uuid.UUID,
    ) -> uuid.UUID | None: ...
