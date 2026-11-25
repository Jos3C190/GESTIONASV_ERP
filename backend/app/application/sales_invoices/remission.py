"""Nota de remisión al despachar un traslado (bloque V4d).

Si la empresa habilitó el tipo 04, despachar un traslado deja su nota de remisión en ``pending``
dentro de la misma transacción; el trabajador ``dte-worker`` la emite. Si la nota no se puede
armar (falta el establecimiento del origen, su punto de venta o datos de la empresa), el despacho
no se hace.

- Emisor: el establecimiento fiscal de la sucursal de la bodega de origen y su primer punto de
  venta activo.
- Receptor: la misma empresa, con la dirección del establecimiento de destino.
- Líneas: lo despachado, al costo promedio del kardex.

Una nota rechazada o fallida se emite de nuevo con los datos del despacho; una sellada se corrige
con invalidación tipo 1 (``prepare_replacement``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.fiscal import Establishment, PointOfSale, dte_nit, dte_nrc
from app.domain.entities.sales_fiscal_document import (
    FiscalDocumentStatus,
    ReceiverAddress,
    fiscal_mode,
)
from app.domain.entities.transfer_remission import (
    REMISSION,
    CompanyReceiver,
    RemissionLine,
    TransferTransport,
    build_receiver,
    build_request,
    remission_total,
)
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.product_fiscal_repository import ProductFiscalRepository
from app.domain.ports.sales_fiscal_repository import FiscalDocument, SalesFiscalRepository

from .use_cases import SalesInvoiceUseCases

#: Una nota en estos estados se puede volver a emitir con los datos del despacho.
REISSUABLE = (FiscalDocumentStatus.REJECTED, FiscalDocumentStatus.FAILED)


class UnitCostSource(Protocol):
    async def unit_costs(
        self, company_id: uuid.UUID, item_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]: ...


@dataclass(frozen=True, slots=True)
class DispatchedLine:
    inventory_item_id: uuid.UUID
    sku: str | None
    name: str
    quantity: Decimal
    base_unit_id: int | None


@dataclass(frozen=True, slots=True)
class DispatchedTransfer:
    """Lo que salió en el despacho, tal como lo devuelve el traslado."""

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    origin_branch_id: uuid.UUID | None
    destination_branch_id: uuid.UUID | None
    origin_name: str
    destination_name: str
    vehicle_plate: str | None
    vehicle_name: str | None
    driver_name: str | None
    lines: tuple[DispatchedLine, ...]


class DispatchedTransferSource(Protocol):
    async def dispatched(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> DispatchedTransfer | None: ...


@dataclass(frozen=True, slots=True)
class RemissionStatus:
    enabled: bool
    document: FiscalDocument | None


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class TransferRemissionUseCases:
    def __init__(
        self,
        repo: SalesFiscalRepository,
        invoices: SalesInvoiceUseCases,
        fiscal: FiscalRepository,
        products: ProductFiscalRepository,
        costs: UnitCostSource,
        transfers: DispatchedTransferSource,
    ) -> None:
        self._repo = repo
        self._transfers = transfers
        self._invoices = invoices
        self._fiscal = fiscal
        self._products = products
        self._costs = costs

    async def enabled(self, company_id: uuid.UUID) -> bool:
        return await self._invoices.enabled(company_id, REMISSION)

    async def status(self, company_id: uuid.UUID, transfer_id: uuid.UUID) -> RemissionStatus:
        document = await self._repo.active_for_transfer(
            company_id, transfer_id
        ) or await self._repo.latest_for_transfer(company_id, transfer_id)
        return RemissionStatus(enabled=await self.enabled(company_id), document=document)

    async def _transfer(self, company_id: uuid.UUID, transfer_id: uuid.UUID) -> DispatchedTransfer:
        transfer = await self._transfers.dispatched(company_id, transfer_id)
        if transfer is None:
            raise NotFoundError(
                "El traslado no existe o todavía no se despacha.",
                code="transfer_remission_transfer_not_dispatched",
            )
        return transfer

    # --- armado ---------------------------------------------------------------------------------

    async def _origin(self, transfer: DispatchedTransfer) -> tuple[Establishment, PointOfSale]:
        establishment = (
            await self._invoices.establishment_for(transfer.company_id, transfer.origin_branch_id)
            if transfer.origin_branch_id
            else None
        )
        points = sorted(
            (p for p in (establishment.points_of_sale if establishment else ()) if p.is_active),
            key=lambda point: point.code,
        )
        if establishment is None or not points:
            raise _rule(
                f"La empresa emite nota de remisión y la sucursal de {transfer.origin_name} no "
                "tiene un establecimiento fiscal activo con punto de venta. Créalo en "
                "Configuración fiscal o deshabilita la nota de remisión antes de despachar.",
                "transfer_remission_issuer_missing",
            )
        return establishment, points[0]

    async def _receiver(self, transfer: DispatchedTransfer) -> CompanyReceiver:
        destination = (
            await self._invoices.establishment_for(
                transfer.company_id, transfer.destination_branch_id
            )
            if transfer.destination_branch_id
            else None
        )
        identity = await self._fiscal.company_identity(transfer.company_id)
        profile = await self._fiscal.get_profile(transfer.company_id)
        activity = next(
            (a for a in await self._fiscal.list_activities(transfer.company_id) if a.is_primary),
            None,
        )
        address = destination.address if destination else None
        return CompanyReceiver(
            name=identity.name if identity else "",
            commercial_name=identity.commercial_name if identity else None,
            nit=dte_nit(identity.nit) if identity else None,
            nrc=dte_nrc(identity.nrc) if identity else None,
            activity_code=activity.code if activity else None,
            activity_description=activity.description if activity else None,
            address=(
                ReceiverAddress(
                    department_code=address.department_code or "",
                    municipality_code=address.municipality_code or "",
                    district_code=address.district_code or "",
                    complement=address.complement,
                )
                if address is not None and address.complete and address.complement
                else None
            ),
            phone=profile.dte_phone,
            email=profile.dte_email,
        )

    async def _lines(self, transfer: DispatchedTransfer) -> tuple[RemissionLine, ...]:
        shipped = [line for line in transfer.lines if line.quantity > 0]
        costs = await self._costs.unit_costs(
            transfer.company_id, {line.inventory_item_id for line in shipped}
        )
        codes: dict[int, str | None] = {}
        for unit_id in {line.base_unit_id for line in shipped if line.base_unit_id is not None}:
            unit = await self._products.get_unit(transfer.company_id, unit_id)
            codes[unit_id] = (unit.hacienda_unit_code or unit.suggested_code) if unit else None
        return tuple(
            RemissionLine(
                sku=line.sku or "",
                description=line.name,
                quantity=line.quantity,
                unit_code=codes.get(line.base_unit_id) if line.base_unit_id is not None else None,
                unit_cost=costs.get(line.inventory_item_id, Decimal("0")),
            )
            for line in shipped
        )

    async def _prepare(
        self,
        transfer: DispatchedTransfer,
        actor_id: uuid.UUID,
        *,
        replaces: FiscalDocument | None = None,
    ) -> FiscalDocument:
        establishment, point = await self._origin(transfer)
        issuer, establishment, point, mode = await self._invoices.issuer_at(
            transfer.company_id, establishment, point
        )
        lines = await self._lines(transfer)
        receiver = build_receiver(await self._receiver(transfer))
        transport = TransferTransport(
            transfer_code=transfer.code,
            origin=transfer.origin_name,
            destination=transfer.destination_name,
            vehicle_plate=transfer.vehicle_plate,
            vehicle_name=transfer.vehicle_name,
            driver_name=transfer.driver_name,
        )
        body = build_request(issuer, receiver, lines, transport)
        document_id = uuid.uuid4()
        assert transfer.origin_branch_id is not None  # _origin lo exige
        return FiscalDocument(
            id=document_id,
            company_id=transfer.company_id,
            branch_id=transfer.origin_branch_id,
            sale_id=None,
            transfer_id=transfer.id,
            establishment_id=establishment.id,
            point_of_sale_id=point.id,
            document_type=REMISSION,
            mode=fiscal_mode(mode).value,
            status=FiscalDocumentStatus.PENDING,
            idempotency_key=f"erp-{document_id}",
            total=remission_total(lines),
            issuer_snapshot=issuer.record(),
            request_payload=body,
            created_by_id=actor_id,
            replaces_document_id=replaces.id if replaces else None,
        )

    # --- acciones -------------------------------------------------------------------------------

    async def on_dispatch(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID, actor_id: uuid.UUID
    ) -> FiscalDocument | None:
        """Crea la nota pendiente del traslado recién despachado; ``None`` si la empresa no la usa."""

        if not await self.enabled(company_id):
            return None
        existing = await self._repo.active_for_transfer(company_id, transfer_id)
        if existing is not None:
            return existing
        transfer = await self._transfer(company_id, transfer_id)
        return await self._repo.create(await self._prepare(transfer, actor_id))

    async def reissue(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID, actor_id: uuid.UUID
    ) -> FiscalDocument:
        """Nueva nota con los datos del despacho, cuando la anterior fue rechazada o falló."""

        transfer = await self._transfer(company_id, transfer_id)
        if not await self.enabled(transfer.company_id):
            raise _rule(
                "La empresa no tiene habilitada la nota de remisión.",
                "transfer_remission_disabled",
            )
        if await self._repo.active_for_transfer(transfer.company_id, transfer.id) is not None:
            raise _rule(
                "El traslado ya tiene su nota de remisión vigente.",
                "transfer_remission_already_issued",
            )
        latest = await self._repo.latest_for_transfer(transfer.company_id, transfer.id)
        if latest is not None and latest.status not in REISSUABLE:
            raise _rule(
                "Solo se emite de nuevo una nota de remisión rechazada o fallida.",
                "transfer_remission_not_reissuable",
            )
        return await self._repo.create(await self._prepare(transfer, actor_id))

    async def prepare_replacement(
        self, original: FiscalDocument, actor_id: uuid.UUID
    ) -> FiscalDocument:
        """Nota que reemplaza a ``original`` (invalidación tipo 1). No la guarda."""

        if original.transfer_id is None:
            raise _rule(
                "El documento no es una nota de remisión de un traslado.",
                "transfer_remission_not_a_remission",
            )
        transfer = await self._transfer(original.company_id, original.transfer_id)
        if not await self.enabled(transfer.company_id):
            raise _rule(
                "La empresa no tiene habilitada la nota de remisión.",
                "transfer_remission_disabled",
            )
        return await self._prepare(transfer, actor_id, replaces=original)
