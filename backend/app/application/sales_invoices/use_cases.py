"""Facturar el pedido confirmado (bloque V3b).

Facturar arma el emisor, el receptor, las líneas y los totales del pedido, los concilia y deja el
documento fiscal en ``pending``. El trabajador ``dte-worker`` lo emite en el servicio DTE con la
clave de idempotencia del documento; reintentar reusa esa misma clave.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.customer import CustomerType
from app.domain.entities.fiscal import (
    EconomicActivity,
    Establishment,
    OperatingMode,
    PointOfSale,
    dte_nit,
    dte_nrc,
)
from app.domain.entities.sales_fiscal_document import (
    FiscalDocumentStatus,
    FiscalLine,
    IssuerAddress,
    IssuerFacts,
    IssuerSnapshot,
    OrderFiscalTotals,
    ReceiverAddress,
    ReceiverFacts,
    build_receiver,
    build_request,
    fiscal_mode,
    issuer_snapshot,
    require_invoiceable,
    require_retryable,
)
from app.domain.entities.sales_order import PaymentTerms
from app.domain.entities.sales_renta import RentaClassification
from app.domain.ports.customer_repository import CustomerRepository
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.sales_fiscal_repository import (
    FiscalDocument,
    FiscalDocumentFilters,
    SalesFiscalRepository,
)
from app.domain.ports.sales_order_repository import Order, SalesOrderRepository

ACTIVITY_CATALOG = "CAT-019"
GEOGRAPHY_CATALOG = "CAT-012"
DEFAULT_CATALOG_VERSION = "1.1"


@dataclass(frozen=True, slots=True)
class PointOfSaleOption:
    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class InvoiceOptions:
    """Lo que la pantalla necesita para ofrecer «Facturar» en un pedido."""

    document_type: str
    mode: str
    establishment_code: str | None
    points_of_sale: tuple[PointOfSaleOption, ...]
    blockers: tuple[str, ...]
    document: FiscalDocument | None
    previous: FiscalDocument | None = None
    renta: RentaClassification | None = None
    """Clasificación de renta sugerida por la actividad del establecimiento (V4b2)."""
    """Sin documento activo: el último del pedido (rechazado, fallido o invalidado), V4b."""


@dataclass(frozen=True, slots=True)
class Issued:
    document: FiscalDocument
    created: bool
    """``False`` si el pedido ya tenía su documento y se devolvió el mismo."""


class SalesInvoiceUseCases:
    def __init__(
        self,
        repo: SalesFiscalRepository,
        orders: SalesOrderRepository,
        customers: CustomerRepository,
        fiscal: FiscalRepository,
    ) -> None:
        self._repo = repo
        self._orders = orders
        self._customers = customers
        self._fiscal = fiscal

    # --- consulta ------------------------------------------------------------------------------

    async def get(self, company_id: uuid.UUID, document_id: uuid.UUID) -> FiscalDocument:
        document = await self._repo.get(company_id, document_id)
        if document is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        return document

    async def list_documents(
        self, company_id: uuid.UUID, filters: FiscalDocumentFilters, *, page: int, size: int
    ) -> tuple[list[FiscalDocument], int]:
        return await self._repo.list_documents(company_id, filters, page=page, size=size)

    async def _order(self, company_id: uuid.UUID, order_id: uuid.UUID, *, lock: bool) -> Order:
        order = await self._orders.get(company_id, order_id, lock=lock)
        if order is None:
            raise NotFoundError("El pedido no existe.", code="sales_order_not_found")
        return order

    async def order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> Order:
        return await self._order(company_id, order_id, lock=False)

    async def _establishment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> Establishment | None:
        return next(
            (
                item
                for item in await self._fiscal.list_establishments(company_id)
                if item.branch_id == branch_id and item.is_active
            ),
            None,
        )

    async def options(self, company_id: uuid.UUID, order_id: uuid.UUID) -> InvoiceOptions:
        order = await self._order(company_id, order_id, lock=False)
        profile = await self._fiscal.get_profile(company_id)
        establishment = await self._establishment(company_id, order.branch_id)
        points = tuple(
            PointOfSaleOption(id=p.id, code=p.code, name=p.name)
            for p in (establishment.points_of_sale if establishment else ())
            if p.is_active
        )
        active = await self._repo.active_for_order(company_id, order_id)
        blockers: list[str] = []
        try:
            await self._prepare(order, points[0].id if points else None)
        except BusinessRuleError as error:
            blockers.append(error.message)
        return InvoiceOptions(
            document_type=order.document_type,
            mode=fiscal_mode(profile.operating_mode).value,
            establishment_code=establishment.code if establishment else None,
            points_of_sale=points,
            blockers=tuple(blockers),
            document=active,
            previous=None if active else await self._repo.latest_for_order(company_id, order_id),
            renta=await self._suggested_renta(order),
        )

    # --- armado ---------------------------------------------------------------------------------

    def _point_of_sale(
        self, establishment: Establishment, point_of_sale_id: uuid.UUID | None
    ) -> PointOfSale:
        active = [p for p in establishment.points_of_sale if p.is_active]
        if point_of_sale_id is None:
            if len(active) == 1:
                return active[0]
            if not active:
                raise BusinessRuleError(
                    "El establecimiento de la sucursal no tiene un punto de venta activo.",
                    code="sales_invoice_point_of_sale_missing",
                )
            raise BusinessRuleError(
                "Elige el punto de venta (caja) con el que se factura.",
                code="sales_invoice_point_of_sale_required",
            )
        chosen = next((p for p in active if p.id == point_of_sale_id), None)
        if chosen is None:
            raise BusinessRuleError(
                "El punto de venta no está activo en el establecimiento de la sucursal del pedido.",
                code="sales_invoice_point_of_sale_invalid",
            )
        return chosen

    async def _issuer(
        self, order: Order, point_of_sale_id: uuid.UUID | None
    ) -> tuple[IssuerSnapshot, Establishment, PointOfSale, OperatingMode]:
        company_id = order.company_id
        establishment = await self._establishment(company_id, order.branch_id)
        if establishment is None:
            raise BusinessRuleError(
                "La sucursal del pedido no tiene un establecimiento fiscal activo. Créalo en "
                "Configuración fiscal antes de facturar.",
                code="sales_invoice_establishment_missing",
            )
        point = self._point_of_sale(establishment, point_of_sale_id)
        identity = await self._fiscal.company_identity(company_id)
        profile = await self._fiscal.get_profile(company_id)
        activities = await self._fiscal.list_activities(company_id)
        activity = next(
            (a for a in activities if a.code == establishment.activity_code), None
        ) or next((a for a in activities if a.is_primary), None)
        address = establishment.address
        geo_version = await self._repo.catalog_version(GEOGRAPHY_CATALOG)
        facts = IssuerFacts(
            legal_name=identity.name if identity else None,
            trade_name=identity.commercial_name if identity else None,
            nit=dte_nit(identity.nit) if identity else None,
            nrc=dte_nrc(identity.nrc) if identity else None,
            activity_code=activity.code if activity else None,
            activity_description=activity.description if activity else None,
            activity_catalog_version=await self._repo.catalog_version(ACTIVITY_CATALOG)
            or DEFAULT_CATALOG_VERSION,
            address=(
                IssuerAddress(
                    department_code=address.department_code or "",
                    department_name=address.department,
                    municipality_code=address.municipality_code or "",
                    municipality_name=address.municipality,
                    district_code=address.district_code or "",
                    district_name=address.district,
                    complement=address.complement[:200],
                    geo_catalog_version=geo_version or DEFAULT_CATALOG_VERSION,
                )
                if address.complete and address.complement
                else None
            ),
            phone=profile.dte_phone or establishment.phone,
            email=profile.dte_email or establishment.email,
            establishment_type=establishment.establishment_type.value,
            establishment_code=establishment.code,
            point_of_sale_code=point.code,
        )
        return issuer_snapshot(facts), establishment, point, profile.operating_mode

    async def _receiver(self, order: Order) -> ReceiverFacts:
        customer = await self._customers.get_customer(order.company_id, order.customer_id)
        if customer is None:
            raise NotFoundError("El cliente del pedido no existe.", code="customer_not_found")
        draft = customer.draft
        address = customer.address
        return ReceiverFacts(
            name=draft.name,
            commercial_name=draft.commercial_name,
            is_generic=customer.is_generic,
            is_taxpayer=draft.customer_type == CustomerType.TAXPAYER,
            document_type=draft.document_type.value if draft.document_type else None,
            document_number=draft.document_number,
            nrc=draft.nrc,
            activity_code=draft.activity_code,
            activity_description=customer.activity_name,
            address=(
                ReceiverAddress(
                    department_code=address.department_code or "",
                    municipality_code=address.municipality_code or "",
                    district_code=address.district_code or "",
                    complement=draft.address_line,
                )
                if address.coded and draft.address_line
                else None
            ),
            phone=draft.phone,
            email=draft.email,
        )

    async def _lines(self, order: Order) -> list[FiscalLine]:
        units = await self._repo.unit_codes(
            order.company_id, {item.line.identity.unit_id for item in order.lines}
        )
        return [
            FiscalLine(
                sku=item.line.identity.product_sku,
                description=item.line.identity.product_name,
                item_type=item.line.item_type,
                unit_code=units.get(item.line.identity.unit_id),
                quantity=item.line.quantity,
                unit_price=item.line.document_unit_price,
                discount=item.line.discount_amount,
                not_subject=item.line.not_subject,
                exempt=item.line.exempt,
                taxed=item.line.taxed,
            )
            for item in order.lines
        ]

    @staticmethod
    def totals(order: Order) -> OrderFiscalTotals:
        t = order.totals
        return OrderFiscalTotals(
            document_type=order.document_type,
            global_discount_percent=order.global_discount_percent,
            total_not_subject=t.total_not_subject,
            total_exempt=t.total_exempt,
            total_taxed=t.total_taxed,
            subtotal_sales=t.subtotal_sales,
            total_discount=t.total_discount,
            subtotal=t.subtotal,
            vat=t.vat,
            vat_perceived=t.vat_perceived,
            vat_withheld=t.vat_withheld,
            total=t.total,
            on_credit=order.payment_terms == PaymentTerms.CREDIT,
            credit_days=order.credit_days,
        )

    async def _enabled(self, company_id: uuid.UUID, document_type: str) -> bool:
        return any(
            item.document_type == document_type and item.is_enabled
            for item in await self._fiscal.list_document_types(company_id)
        )

    async def _activity(self, order: Order) -> EconomicActivity | None:
        """Actividad del establecimiento de la sucursal o, si no tiene, la principal."""

        establishment = await self._establishment(order.company_id, order.branch_id)
        activities = await self._fiscal.list_activities(order.company_id)
        return next(
            (a for a in activities if establishment and a.code == establishment.activity_code),
            None,
        ) or next((a for a in activities if a.is_primary), None)

    async def _suggested_renta(self, order: Order) -> RentaClassification | None:
        activity = await self._activity(order)
        if activity is None or activity.renta_operation_type is None:
            return None
        assert activity.renta_income_type is not None
        return RentaClassification(activity.renta_operation_type, activity.renta_income_type)

    async def _renta(self, order: Order, chosen: RentaClassification | None) -> RentaClassification:
        renta = chosen or await self._suggested_renta(order)
        if renta is None:
            raise BusinessRuleError(
                "Elige el tipo de operación y el tipo de ingreso de renta del documento, o "
                "configúralos en la actividad económica (Configuración fiscal → Actividades).",
                code="sales_invoice_renta_required",
            )
        return renta

    async def _prepare(
        self,
        order: Order,
        point_of_sale_id: uuid.UUID | None,
        *,
        replaces: FiscalDocument | None = None,
    ) -> tuple[FiscalDocument, IssuerSnapshot]:
        if replaces is None:
            require_invoiceable(
                order.status.value,
                order.document_type,
                await self._enabled(order.company_id, order.document_type),
                has_active_document=False,
            )
        else:
            # El reemplazo de un documento sellado (V4b): mismo tipo, datos actuales.
            if order.document_type != replaces.document_type:
                raise BusinessRuleError(
                    "El pedido cambió de tipo de documento: anula el documento y factura de nuevo.",
                    code="sales_invoice_correction_type_changed",
                )
            if not await self._enabled(order.company_id, order.document_type):
                raise BusinessRuleError(
                    "La empresa no tiene habilitado este tipo de documento para emitir.",
                    code="sales_invoice_document_disabled",
                )
        issuer, establishment, point, mode = await self._issuer(order, point_of_sale_id)
        receiver = build_receiver(order.document_type, await self._receiver(order))
        totals = self.totals(order)
        body = build_request(issuer, receiver, await self._lines(order), totals)
        document_id = uuid.uuid4()
        document = FiscalDocument(
            id=document_id,
            company_id=order.company_id,
            branch_id=order.branch_id,
            sale_id=order.id,
            establishment_id=establishment.id,
            point_of_sale_id=point.id,
            document_type=order.document_type,
            mode=fiscal_mode(mode).value,
            status=FiscalDocumentStatus.PENDING,
            idempotency_key=f"erp-{document_id}",
            total=totals.total,
            issuer_snapshot=issuer.record(),
            request_payload=body,
            created_by_id=order.created_by_id,
            replaces_document_id=replaces.id if replaces else None,
        )
        return document, issuer

    async def prepare_replacement(
        self, original: FiscalDocument, actor_id: uuid.UUID
    ) -> FiscalDocument:
        """Documento que reemplaza a ``original`` con los datos actuales del pedido y del cliente.

        No lo guarda: quien lo pide marca primero el original y después lo crea.
        """

        order = await self._order(original.company_id, original.sale_id, lock=True)
        document, _issuer = await self._prepare(order, original.point_of_sale_id, replaces=original)
        # El reemplazo conserva la clasificación de renta del original.
        renta = await self._renta(
            order,
            RentaClassification(original.renta_operation_type, original.renta_income_type)
            if original.renta_operation_type is not None and original.renta_income_type is not None
            else None,
        )
        return replace(
            document,
            created_by_id=actor_id,
            renta_operation_type=renta.operation_type,
            renta_income_type=renta.income_type,
        )

    # --- acciones -------------------------------------------------------------------------------

    async def issue(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        point_of_sale_id: uuid.UUID | None,
        *,
        renta: RentaClassification | None = None,
    ) -> Issued:
        # Bloquear el pedido serializa «Facturar» con «Cancelar» y con otro «Facturar».
        order = await self._order(company_id, order_id, lock=True)
        existing = await self._repo.active_for_order(company_id, order_id)
        if existing is not None:
            return Issued(document=existing, created=False)
        document, _issuer = await self._prepare(order, point_of_sale_id)
        classification = await self._renta(order, renta)
        created = await self._repo.create(
            replace(
                document,
                created_by_id=actor_id,
                renta_operation_type=classification.operation_type,
                renta_income_type=classification.income_type,
            )
        )
        return Issued(document=created, created=True)

    async def retry(self, company_id: uuid.UUID, document_id: uuid.UUID) -> FiscalDocument:
        document = await self._repo.get(company_id, document_id, lock=True)
        if document is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        require_retryable(document.status)
        if document.status == FiscalDocumentStatus.FAILED:
            await self._order(company_id, document.sale_id, lock=True)
            active = await self._repo.active_for_order(company_id, document.sale_id)
            if active is not None:
                raise BusinessRuleError(
                    "El pedido ya tiene otro documento fiscal vigente.",
                    code="sales_invoice_already_issued",
                )
        document.status = FiscalDocumentStatus.PENDING
        document.attempts = 0
        document.error_code = None
        document.error_message = None
        return await self._repo.save(document)
