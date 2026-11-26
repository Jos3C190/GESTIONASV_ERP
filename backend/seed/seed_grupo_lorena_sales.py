"""Un mes de ventas de demostración de Grupo Lorena (bloque V9b).

Genera el mes anterior completo con las reglas reales del ERP, llamando a la API en proceso:

* Prepara cajas en la bodega central: fracciona pallets en unidades de una caja (medir, etiquetar
  y liberar, como en bodega) para que cada venta salga entregada del kardex al confirmar.
* Cada día hábil (lunes a sábado) crea unas seis ventas a clientes de mostrador y mayoreo,
  las confirma (salida automática), las autoriza si pasan el crédito, las factura en modo
  simulado y cobra las de contado el mismo día; las de crédito se cobran al vencer si el vencimiento
  cae dentro del mes.
* Registra algunas devoluciones aceptadas (con su nota de crédito o evento de retorno), un cambio
  de producto con su saldo a favor aplicado y la meta del mes de la sucursal.

El reloj del proceso se mueve a cada día con ``time-machine`` y el servicio DTE recibe la misma
fecha por ``X-DTE-Demo-Clock`` (solo emisores simulados y con ``DTE_DEMO_CLOCK_ENABLED=true``),
así que facturas, entregas, kardex, cobros y libros quedan con fechas coherentes. Los documentos se
procesan aquí mismo, dentro del reloj movido, en lugar de encolarlos para el trabajador.

Los precios sembrados rigen desde noviembre de 2026 y el ERP no admite precios con fecha pasada;
como dato maestro de demostración, la siembra agrega el tramo anterior (desde el primer día del
mes) con el mismo precio inicial.

Cada documento lleva ``Ref. GLVTA-…`` en sus notas; una nueva corrida lo encuentra y continúa sin
duplicar. Nunca corre en producción. Ejecutar dentro del contenedor del backend:
``uv run --no-sync python -m seed.seed_grupo_lorena_sales``.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from unittest import mock
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text

from seed.grupo_lorena_media import COMPANY_ID
from seed.grupo_lorena_operations_data import CENTRAL_WAREHOUSE, PRODUCTS, pallet_measures
from seed.seed_grupo_lorena import SUPER_ADMIN_USERNAME, _session_factory

TZ = ZoneInfo("America/El_Salvador")
API = "/api/v1"
REF = "GLVTA"
SEED = 20261001
D = Decimal

#: Base units of one sale box per product (one purchase unit).
PACKS: dict[str, Decimal] = {
    "PRD-AZU-004": D("10"),
    "PRD-CAF-011": D("1"),
    "PRD-CHO-006": D("5"),
    "PRD-EMP-009": D("25"),
    "PRD-EMP-010": D("100"),
    "PRD-HAR-001": D("1"),
    "PRD-HAR-003": D("25"),
    "PRD-LAC-002": D("1"),
    "PRD-MAR-008": D("15"),
    "PRD-REL-007": D("4"),
}
#: Share of the boxes available in the central warehouse that the month may use.
STOCK_SHARE = D("0.6")
#: Cajas a preparar por producto como máximo (cada una es una unidad logística).
MAX_BOXES = 45
#: Customer codes (prefix) and their weight in the daily mix.
#: Panadería Centroamericana (CLI-00004) es extranjera: solo recibe factura de exportación (11),
#: que no está en el alcance de la demostración.
CUSTOMER_MIX: tuple[tuple[str, int], ...] = (
    ("CF-HQ", 50),
    ("CLI-00001", 22),
    ("CLI-00002", 16),
    ("CLI-00003", 12),
)
ORDERS_PER_DAY = (5, 6, 6, 7)
RETURNS = 5


def production() -> bool:
    return os.environ.get("ENVIRONMENT", "development").strip().casefold() == "production"


def demo_month(today: date | None = None) -> tuple[date, date]:
    """Primer y último día del mes a generar (el anterior, o ``SEED_DEMO_SALES_MONTH``)."""

    override = os.environ.get("SEED_DEMO_SALES_MONTH", "").strip()
    if override:
        year, month = (int(part) for part in override.split("-"))
        first = date(year, month, 1)
    else:
        current = (today or datetime.now(TZ).date()).replace(day=1)
        first = (current - timedelta(days=1)).replace(day=1)
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return first, last


def business_days(first: date, last: date) -> list[date]:
    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    return [day for day in days if day.weekday() != 6]


# =========================================================================== plan


@dataclass(frozen=True, slots=True)
class LinePlan:
    sku: str
    boxes: int


@dataclass(frozen=True, slots=True)
class OrderPlan:
    ref: str
    day: date
    at: time
    customer: str
    lines: tuple[LinePlan, ...]


@dataclass(frozen=True, slots=True)
class ReturnPlan:
    ref: str
    order_ref: str
    day: date
    exchange_sku: str | None = None


def build_plan(
    days: list[date], boxes: dict[str, int], rng: random.Random
) -> tuple[list[OrderPlan], list[ReturnPlan]]:
    """Ventas por día y devoluciones, deterministas, sin pasar de las cajas disponibles."""

    budget = dict(boxes)
    codes = [code for code, _ in CUSTOMER_MIX]
    weights = [weight for _, weight in CUSTOMER_MIX]
    orders: list[OrderPlan] = []
    for day in days:
        hours = sorted(rng.sample(range(8 * 60, 17 * 60), rng.choice(ORDERS_PER_DAY)))
        for number, minute in enumerate(hours, start=1):
            available = [sku for sku, left in budget.items() if left > 0]
            if not available:
                break
            products = rng.sample(available, min(len(available), 1 if rng.random() < 0.7 else 2))
            lines = []
            for sku in products:
                boxes_wanted = rng.choices((1, 2, 3), weights=(6, 3, 1))[0]
                take = min(boxes_wanted, budget[sku])
                budget[sku] -= take
                lines.append(LinePlan(sku, take))
            orders.append(
                OrderPlan(
                    ref=f"{REF}-{day:%Y%m%d}-{number:02d}",
                    day=day,
                    at=time(minute // 60, minute % 60),
                    customer=rng.choices(codes, weights=weights)[0],
                    lines=tuple(lines),
                )
            )
    returns: list[ReturnPlan] = []
    candidates = [order for order in orders if order.day <= days[-1] - timedelta(days=3)]
    for number, order in enumerate(rng.sample(candidates, min(RETURNS, len(candidates))), start=1):
        later = [day for day in days if order.day < day <= order.day + timedelta(days=4)]
        exchange = None
        if number == 1:
            others = [sku for sku, left in budget.items() if left > 0 and sku != order.lines[0].sku]
            exchange = others[0] if others else None
            if exchange:
                budget[exchange] -= 1
        returns.append(
            ReturnPlan(
                ref=f"{REF}-DEV-{number:02d}",
                order_ref=order.ref,
                day=later[0] if later else order.day,
                exchange_sku=exchange,
            )
        )
    return orders, sorted(returns, key=lambda item: item.day)


# =========================================================================== runtime


class ApiError(RuntimeError):
    pass


@dataclass
class Report:
    created: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def add(self, key: str, amount: int = 1) -> None:
        self.created[key] += amount


@dataclass
class Runtime:
    client: Any
    session_factory: Any
    actor_id: UUID
    report: Report
    queued_documents: list[UUID] = field(default_factory=list)
    queued_returns: list[UUID] = field(default_factory=list)

    async def call(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        ok: tuple[int, ...] = (200, 201, 202),
    ) -> Any:
        from app.infrastructure.repositories.token_service import JwtTokenService

        token = JwtTokenService().issue_access_token(
            user_id=self.actor_id, username=SUPER_ADMIN_USERNAME, is_superuser=True
        )
        response = await self.client.request(
            method,
            f"{API}{path}",
            json=json,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Company-ID": str(COMPANY_ID),
                **(headers or {}),
            },
        )
        if response.status_code not in ok:
            raise ApiError(f"{method} {path}: {response.status_code} {response.text[:400]}")
        return response.json() if response.content else None

    async def rows(self, sql: str, **params: Any) -> list[Any]:
        async with self.session_factory() as session:
            return list((await session.execute(text(sql), params)).all())

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.session_factory() as session:
            await session.execute(text(sql), params)
            await session.commit()

    async def process_queue(self) -> None:
        """Procesa aquí, con el reloj movido, lo que la API habría encolado."""

        from app.infrastructure.dte_returns_worker import process_fiscal_return
        from app.infrastructure.dte_worker import (
            dte_client,
            object_storage,
            process_fiscal_document,
        )

        client = dte_client()
        if client is None:
            raise RuntimeError("El servicio DTE no está configurado (DTE_SERVICE_URL).")
        inner = object_storage()
        storage = RealTimeStorage(inner) if inner is not None else None
        while self.queued_documents:
            document_id = self.queued_documents.pop(0)
            await process_fiscal_document(document_id, client=client, storage=storage)
        while self.queued_returns:
            return_id = self.queued_returns.pop(0)
            await process_fiscal_return(return_id, client=client, storage=storage)


@contextmanager
def capture_queues(runtime: Runtime) -> Iterator[None]:
    """La API encola documentos para el trabajador; aquí se guardan para procesarlos en el día."""

    async def document(document_id: UUID) -> None:
        runtime.queued_documents.append(document_id)

    async def fiscal_return(return_id: UUID) -> None:
        runtime.queued_returns.append(return_id)

    async def ignore(*_: Any) -> None:
        return None

    targets = {
        "app.api.v1.routers.sales_invoices.enqueue_fiscal_document": document,
        "app.api.v1.routers.sales_invoices.enqueue_fiscal_email": ignore,
        "app.api.v1.routers.sales_notes.enqueue_fiscal_document": document,
        "app.api.v1.routers.sales.enqueue_fiscal_document": document,
        "app.api.v1.routers.sales.enqueue_fiscal_return": fiscal_return,
        "app.api.v1.routers.sales_fiscal_returns.enqueue_fiscal_return": fiscal_return,
    }
    with ExitStack() as stack:
        for target, replacement in targets.items():
            stack.enter_context(mock.patch(target, replacement))
        yield


#: Viaje en el tiempo activo (uno a la vez): ``real_time`` lo pausa y lo retoma.
_TRAVEL: list[Any] = []


@contextmanager
def on_day(day: date, at: time) -> Iterator[None]:
    """Reloj del proceso y del servicio DTE en ``day`` a la hora ``at`` (El Salvador)."""

    import time_machine
    from app.infrastructure.dte_demo_clock import demo_clock

    moment = datetime.combine(day, at, tzinfo=TZ).astimezone(UTC)
    traveller = time_machine.travel(moment, tick=True)
    traveller.start()
    _TRAVEL.append(traveller)
    try:
        with demo_clock():
            yield
    finally:
        _TRAVEL.pop().stop()


async def real_time(call: Any) -> Any:
    """Corre ``call`` con la hora real y retoma el día en el instante en que iba.

    El almacenamiento de objetos (S3/MinIO) rechaza firmas con la hora movida
    (``RequestTimeTooSkewed``); solo esas llamadas salen del reloj de demostración.
    """

    import time_machine

    if not _TRAVEL:
        return await call()
    now = datetime.now(UTC)
    _TRAVEL.pop().stop()
    try:
        return await call()
    finally:
        traveller = time_machine.travel(now, tick=True)
        traveller.start()
        _TRAVEL.append(traveller)


class RealTimeStorage:
    """El almacenamiento del trabajador, con cada operación hecha a la hora real."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if not asyncio.iscoroutinefunction(attribute):
            return attribute

        async def call(*args: Any, **kwargs: Any) -> Any:
            return await real_time(lambda: attribute(*args, **kwargs))

        return call


# =========================================================================== master data


async def ensure_month_prices(runtime: Runtime, first: date) -> None:
    """Tramo de precio desde ``first`` para cada precio que empieza después (dato de demostración)."""

    # El tramo anterior lleva el precio vigente: el primero que se sembró puede quedar bajo el
    # costo de hoy y el ERP nunca vende bajo costo.
    rows = await runtime.rows(
        """
        SELECT first_item.company_id, first_item.price_list_id, first_item.product_id,
               first_item.variant_id, first_item.unit_id, first_item.branch_id,
               first_item.valid_from, current_item.price
        FROM (
            SELECT DISTINCT ON (price_list_id, product_id, variant_id, unit_id, branch_id) *
            FROM sales_price_list_items WHERE company_id = :company
            ORDER BY price_list_id, product_id, variant_id, unit_id, branch_id, valid_from
        ) first_item
        JOIN LATERAL (
            SELECT price FROM sales_price_list_items i
            WHERE i.price_list_id = first_item.price_list_id
              AND i.product_id = first_item.product_id
              AND i.variant_id IS NOT DISTINCT FROM first_item.variant_id
              AND i.unit_id = first_item.unit_id
              AND i.branch_id IS NOT DISTINCT FROM first_item.branch_id
            ORDER BY i.valid_from DESC LIMIT 1
        ) current_item ON TRUE
        """,
        company=COMPANY_ID,
    )
    for row in rows:
        if row.valid_from <= first:
            continue
        await runtime.execute(
            """
            INSERT INTO sales_price_list_items (company_id, price_list_id, product_id, variant_id,
                unit_id, branch_id, price, valid_from, valid_to, created_by)
            VALUES (:company, :list, :product, :variant, :unit, :branch, :price, :start, :end,
                :actor)
            """,
            company=row.company_id,
            list=row.price_list_id,
            product=row.product_id,
            variant=row.variant_id,
            unit=row.unit_id,
            branch=row.branch_id,
            price=row.price,
            start=first,
            end=row.valid_from - timedelta(days=1),
            actor=runtime.actor_id,
        )
        runtime.report.add("price_ranges")
    # Tramos que una corrida anterior creó con el primer precio: se alinean con el vigente.
    await runtime.execute(
        """
        UPDATE sales_price_list_items seeded SET price = (
            SELECT i.price FROM sales_price_list_items i
            WHERE i.price_list_id = seeded.price_list_id AND i.product_id = seeded.product_id
              AND i.variant_id IS NOT DISTINCT FROM seeded.variant_id
              AND i.unit_id = seeded.unit_id
              AND i.branch_id IS NOT DISTINCT FROM seeded.branch_id
            ORDER BY i.valid_from DESC LIMIT 1
        )
        WHERE seeded.company_id = :company AND seeded.valid_from = :start
          AND seeded.created_by = :actor AND seeded.valid_to IS NOT NULL
        """,
        company=COMPANY_ID,
        start=first,
        actor=runtime.actor_id,
    )


@dataclass(frozen=True, slots=True)
class Catalog:
    headquarters: UUID
    warehouse: UUID
    customers: dict[str, Any]
    products: dict[str, Any]
    #: (price_list_id, product_id) -> (unit_id, factor)
    units: dict[tuple[UUID, int], tuple[int, Decimal]]
    default_list: UUID


async def load_catalog(runtime: Runtime) -> Catalog:
    [hq] = await runtime.rows(
        "SELECT id FROM branches WHERE company_id = :c AND is_headquarters", c=COMPANY_ID
    )
    [warehouse] = await runtime.rows(
        "SELECT id FROM warehouses WHERE company_id = :c AND code = :code",
        c=COMPANY_ID,
        code=CENTRAL_WAREHOUSE,
    )
    customers = {
        row.code: row
        for row in await runtime.rows(
            "SELECT id, code, name, credit_days, price_list_id FROM sales_customers "
            "WHERE company_id = :c AND is_active",
            c=COMPANY_ID,
        )
    }
    products = {
        row.sku: row
        for row in await runtime.rows(
            "SELECT p.id_product, p.sku, i.id AS item_id FROM products p "
            "JOIN inventory_items i ON i.company_id = p.company_id AND i.product_id = p.id_product "
            "AND i.variant_id IS NULL WHERE p.company_id = :c AND p.sku = ANY(:skus)",
            c=COMPANY_ID,
            skus=list(PACKS),
        )
    }
    [default] = await runtime.rows(
        "SELECT id FROM sales_price_lists WHERE company_id = :c AND is_default", c=COMPANY_ID
    )
    catalog = await runtime.call("GET", "/sales/catalog")
    factors = {
        (item["product_id"], unit["unit_id"]): D(str(unit["factor"]))
        for item in catalog
        for unit in item["units"]
    }
    units: dict[tuple[UUID, int], tuple[int, Decimal]] = {}
    for row in await runtime.rows(
        "SELECT DISTINCT price_list_id, product_id, unit_id FROM sales_price_list_items "
        "WHERE company_id = :c AND branch_id IS NULL AND valid_to IS NULL",
        c=COMPANY_ID,
    ):
        factor = factors.get((row.product_id, row.unit_id))
        if factor is None:
            continue
        current = units.get((row.price_list_id, row.product_id))
        if current is None or factor < current[1]:
            units[(row.price_list_id, row.product_id)] = (row.unit_id, factor)
    return Catalog(hq.id, warehouse.id, customers, products, units, default.id)


def customer_by_id(catalog: Catalog, customer_id: Any) -> Any:
    return next(row for row in catalog.customers.values() if row.id == customer_id)


def customer_for(catalog: Catalog, code: str) -> Any:
    for key, row in catalog.customers.items():
        if key.startswith(code):
            return row
    raise RuntimeError(f"Falta el cliente {code}.")


# =========================================================================== boxes


def box_measures(sku: str, base: Decimal) -> tuple[Decimal, Decimal]:
    setup = PRODUCTS[sku]
    units = base / setup.per_purchase_unit
    weight = (setup.unit_weight_kg * units).quantize(D("0.001"))
    volume = max((setup.unit_volume_m3 * units).quantize(D("0.0001")), D("0.0001"))
    return weight, volume


async def available_boxes(runtime: Runtime, catalog: Catalog, sku: str) -> list[Any]:
    return await runtime.rows(
        "SELECT id, code, location_id, quantity_base FROM inventory_handling_units "
        "WHERE company_id = :c AND warehouse_id = :w AND inventory_item_id = :item "
        "AND stock_status = 'available' AND closed_at IS NULL AND quantity_base > 0 "
        "ORDER BY quantity_base DESC",
        c=COMPANY_ID,
        w=catalog.warehouse,
        item=catalog.products[sku].item_id,
    )


async def finish_unit(runtime: Runtime, sku: str, unit_id: UUID, *, pallet: bool) -> None:
    """Medir, etiquetar y liberar a disponible una unidad recién fraccionada."""

    [unit] = await runtime.rows(
        "SELECT id, code, location_id, quantity_base, inventory_item_id, measurement_status, "
        "stock_status FROM inventory_handling_units WHERE id = :id",
        id=unit_id,
    )
    if unit.stock_status == "available":
        return
    if unit.measurement_status != "verified":
        if pallet:
            weight, volume = pallet_measures(
                sku, unit.quantity_base / PRODUCTS[sku].per_purchase_unit
            )
        else:
            weight, volume = box_measures(sku, unit.quantity_base)
        await runtime.call(
            "PATCH",
            f"/inventory/handling-units/{unit.id}/measurements",
            json={
                "measures": {"gross_weight_kg": str(weight), "volume_m3": str(volume)},
                "source": "manual",
            },
        )
    [unit] = await runtime.rows(
        "SELECT id, code, location_id, quantity_base, inventory_item_id, label_revision "
        "FROM inventory_handling_units WHERE id = :id",
        id=unit_id,
    )
    printed = None
    for reason in ("initial", "reprint"):
        try:
            printed = await runtime.call(
                "POST",
                "/inventory/labels/prints",
                json={
                    "idempotency_key": f"glvta-{reason}-{unit.id}-{unit.label_revision}",
                    "handling_unit_id": str(unit.id),
                    "quantity_printed": 1,
                    "print_date": datetime.now(TZ).date().isoformat(),
                    "reason": reason,
                    **({"notes": "Etiqueta nueva tras fraccionar"} if reason == "reprint" else {}),
                },
            )
            break
        except ApiError as error:
            # La parte que queda del pallet ya tuvo su impresión inicial.
            if reason == "reprint" or "initial_already_printed" not in str(error):
                raise
    assert printed is not None
    await runtime.call(
        "POST",
        "/inventory/labels/confirmations",
        json={
            "idempotency_key": f"glvta-label-{unit.id}-{unit.label_revision}",
            "handling_unit_id": str(unit.id),
            "handling_unit_code": unit.code,
            "label_print_id": printed["id"],
        },
    )
    key = f"glvta-release-{unit.id}-{unit.quantity_base}"
    await runtime.call(
        "POST",
        "/inventory/movements/confirm",
        json={
            "idempotency_key": key,
            "source_reference": f"quarantine-release:{unit.id}:{key}",
            "movement_type": "putaway",
            "lines": [
                {
                    "inventory_item_id": str(unit.inventory_item_id),
                    "handling_unit_id": str(unit.id),
                    "from_location_id": str(unit.location_id),
                    "to_location_id": str(unit.location_id),
                    "from_stock_status": "quarantine",
                    "to_stock_status": "available",
                    "quantity_base": str(unit.quantity_base),
                }
            ],
        },
    )


async def storage_locations(runtime: Runtime, catalog: Catalog) -> list[UUID]:
    """Ubicaciones de almacenamiento de la bodega central, primero las menos ocupadas."""

    rows = await runtime.rows(
        "SELECT l.id FROM locations l LEFT JOIN inventory_handling_units hu "
        "ON hu.location_id = l.id AND hu.closed_at IS NULL AND hu.quantity_base > 0 "
        "WHERE l.warehouse_id = :w AND l.storage_eligible AND l.is_active "
        "AND l.lifecycle_status = 'active' AND l.deleted_at IS NULL "
        "GROUP BY l.id, l.code ORDER BY count(hu.id), l.code",
        w=catalog.warehouse,
    )
    return [row.id for row in rows]


async def split_into_free_location(
    runtime: Runtime, catalog: Catalog, source: Any, pack: Decimal
) -> Any:
    """Fracciona una caja hacia la primera ubicación con capacidad para recibirla."""

    candidates = [source.location_id, *await storage_locations(runtime, catalog)]
    last = ""
    for location in dict.fromkeys(candidates):
        try:
            return await runtime.call(
                "POST",
                f"/inventory/handling-units/{source.id}/prepare-split",
                json={
                    "idempotency_key": f"glvta-split-{source.id}-{source.quantity_base}-{location}",
                    "split_quantity_base": str(pack),
                    "destination_location_id": str(location),
                },
            )
        except ApiError as error:
            if "capacity" not in str(error):
                raise
            last = str(error)
    raise ApiError(f"No hay ubicación con capacidad para una caja de {source.code}: {last}")


async def prepare_boxes(
    runtime: Runtime, catalog: Catalog, target: dict[str, int]
) -> dict[str, int]:
    """Fracciona pallets hasta ``target`` cajas por producto; devuelve las cajas listas.

    Un pallet que no se deja fraccionar (capacidad de su ubicación) deja el producto con las
    cajas que ya tenía.
    """

    ready: dict[str, int] = {}
    for sku, count in target.items():
        pack = PACKS[sku]
        # Una corrida interrumpida pudo dejar partes de un fraccionamiento en cuarentena; las
        # devoluciones (HU-RET-…) se revisan en bodega y no se tocan.
        for unit in await runtime.rows(
            "SELECT id, quantity_base FROM inventory_handling_units WHERE company_id = :c "
            "AND warehouse_id = :w AND inventory_item_id = :item AND stock_status = 'quarantine' "
            "AND closed_at IS NULL AND code NOT LIKE 'HU-RET-%'",
            c=COMPANY_ID,
            w=catalog.warehouse,
            item=catalog.products[sku].item_id,
        ):
            await finish_unit(runtime, sku, unit.id, pallet=unit.quantity_base > pack)
        units = await available_boxes(runtime, catalog, sku)
        boxes = sum(1 for unit in units if unit.quantity_base == pack)
        while boxes < count:
            source = next((unit for unit in units if unit.quantity_base > pack), None)
            if source is None:
                break
            try:
                split = await split_into_free_location(runtime, catalog, source, pack)
            except ApiError as error:
                runtime.report.errors.append(f"{sku}: no se pudo fraccionar ({error})")
                break
            await finish_unit(runtime, sku, UUID(split["split_handling_unit_id"]), pallet=False)
            remainder = UUID(split["remainder_handling_unit_id"])
            await finish_unit(
                runtime, sku, remainder, pallet=D(split["remainder_quantity_base"]) > pack
            )
            runtime.report.add("boxes_prepared")
            boxes += 1
            units = await available_boxes(runtime, catalog, sku)
        ready[sku] = boxes
    return ready


# =========================================================================== sales


async def existing_order(runtime: Runtime, ref: str) -> Any | None:
    rows = await runtime.rows(
        "SELECT id, status, version, customer_id FROM sales WHERE company_id = :c "
        "AND notes LIKE :ref",
        c=COMPANY_ID,
        ref=f"%Ref. {ref}%",
    )
    return rows[0] if rows else None


async def active_document(runtime: Runtime, sale_id: UUID) -> Any | None:
    rows = await runtime.rows(
        "SELECT id, status FROM sales_fiscal_documents WHERE sale_id = :s "
        "AND document_type IN ('01', '03') AND superseded_by_id IS NULL "
        "AND status NOT IN ('failed', 'rejected', 'invalidated')",
        s=sale_id,
    )
    return rows[0] if rows else None


def order_body(catalog: Catalog, plan: OrderPlan, customer: Any, notes: str) -> dict[str, Any]:
    price_list = customer.price_list_id or catalog.default_list
    lines = []
    for line in plan.lines:
        product = catalog.products[line.sku]
        unit_id, factor = (
            catalog.units.get((price_list, product.id_product))
            or catalog.units[(catalog.default_list, product.id_product)]
        )
        quantity = (PACKS[line.sku] * line.boxes / factor).normalize()
        lines.append(
            {
                "product_id": product.id_product,
                "variant_id": None,
                "unit_id": unit_id,
                "quantity": str(quantity),
            }
        )
    return {
        "branch_id": str(catalog.headquarters),
        "customer_id": str(customer.id),
        "document_type": None,
        "promised_date": plan.day.isoformat(),
        "delivery_mode": "pickup",
        "notes": notes,
        "lines": lines,
    }


async def run_order(runtime: Runtime, catalog: Catalog, plan: OrderPlan) -> UUID | None:
    customer = customer_for(catalog, plan.customer)
    found = await existing_order(runtime, plan.ref)
    if found is None:
        order = await runtime.call(
            "POST",
            "/sales",
            json=order_body(catalog, plan, customer, f"Venta de demostración. Ref. {plan.ref}"),
            headers={"Idempotency-Key": f"glvta-order-{plan.ref}"},
        )
        runtime.report.add("orders")
    else:
        # Una corrida anterior pudo planear otro cliente para esta referencia: manda el pedido.
        order = await runtime.call("GET", f"/sales/{found.id}")
        customer = customer_by_id(catalog, found.customer_id)
    if order["status"] == "draft":
        order = await runtime.call(
            "POST", f"/sales/{order['id']}/confirm", json={"expected_version": order["version"]}
        )
    if order["status"] == "pending_authorization":
        order = await runtime.call(
            "POST",
            f"/sales/{order['id']}/authorize",
            json={
                "expected_version": order["version"],
                "note": "Cliente con buen historial de pago (demostración)",
            },
        )
        runtime.report.add("credit_authorizations")
    if order["status"] != "confirmed":
        raise ApiError(f"{plan.ref}: el pedido quedó en {order['status']}.")
    if (order.get("auto_delivery") or {}).get("pending_products"):
        runtime.report.add("orders_pending_delivery")
    if await active_document(runtime, UUID(order["id"])) is None:
        await runtime.call("POST", f"/sales/{order['id']}/invoice", json={})
        runtime.report.add("invoices")
    await runtime.process_queue()
    document = await active_document(runtime, UUID(order["id"]))
    if document is not None and document.status == "pending":
        # Una corrida anterior se cortó antes de procesarlo.
        runtime.queued_documents.append(document.id)
        await runtime.process_queue()
        document = await active_document(runtime, UUID(order["id"]))
    if document is None:
        raise ApiError(f"{plan.ref}: no quedó documento vigente.")
    if customer.credit_days == 0:
        await collect(runtime, catalog, customer, document.id, plan.day, f"{plan.ref}-RC")
    return document.id


async def collect(
    runtime: Runtime, catalog: Catalog, customer: Any, document_id: UUID, day: date, key: str
) -> None:
    receivable = await runtime.call("GET", f"/sales/receivables/documents/{document_id}")
    balance = D(str(receivable["balance"]))
    if balance <= 0:
        return
    method = random.Random(key).choice(("cash", "cash", "card", "transfer"))
    payment: dict[str, Any] = {"method": method, "amount": str(balance)}
    if method != "cash":
        payment["reference"] = f"{'AUT' if method == 'card' else 'TRF'}-{key[-11:]}"
    await runtime.call(
        "POST",
        "/sales/receipts",
        json={
            "branch_id": str(catalog.headquarters),
            "customer_id": str(customer.id),
            "received_on": day.isoformat(),
            "payments": [payment],
            "applications": [{"document_id": str(document_id), "amount": str(balance)}],
            "notes": f"Ref. {key}",
            "idempotency_key": f"glvta-{key}",
        },
    )
    runtime.report.add("receipts")


async def run_return(
    runtime: Runtime, catalog: Catalog, plan: ReturnPlan, orders: dict[str, OrderPlan]
) -> None:
    order_plan = orders[plan.order_ref]
    order = await existing_order(runtime, plan.order_ref)
    if order is None:
        return
    done = await runtime.rows(
        "SELECT id, status FROM sales_returns WHERE company_id = :c AND notes LIKE :ref",
        c=COMPANY_ID,
        ref=f"%Ref. {plan.ref}%",
    )
    if not done:
        sources = await runtime.call("GET", f"/sales/{order.id}/returnable-allocations")
        if not sources:
            return
        source = sources[0]
        pack = PACKS[order_plan.lines[0].sku]
        quantity = min(pack, D(str(source["quantity_returnable_base"])))
        created = await runtime.call(
            "POST",
            f"/sales/{order.id}/returns",
            json={
                "notes": f"Devolución de demostración. Ref. {plan.ref}",
                "lines": [
                    {
                        "delivery_allocation_id": source["delivery_allocation_id"],
                        "quantity_base": str(quantity),
                        "reason": "Empaque dañado al recibir",
                        "declared_condition": "resalable",
                    }
                ],
            },
            headers={"Idempotency-Key": f"glvta-return-{plan.ref}"},
        )
        return_id = created["id"]
        runtime.report.add("returns")
    else:
        return_id = str(done[0].id)
    current = await runtime.call("GET", f"/sales/returns/{return_id}")
    if current["status"] == "draft":
        current = await runtime.call(
            "POST",
            f"/sales/returns/{return_id}/receive",
            headers={"Idempotency-Key": f"glvta-receive-{plan.ref}"},
        )
    pending = [line for line in current["lines"] if D(str(line["quantity_pending_base"])) > 0]
    if pending:
        await runtime.call(
            "POST",
            f"/sales/returns/{return_id}/resolve",
            json={
                "lines": [
                    {
                        "return_line_id": line["id"],
                        "decision": "accepted",
                        "quantity_base": str(line["quantity_pending_base"]),
                        "condition": "resalable",
                        "reason": "Revisado en bodega: apto para reventa",
                    }
                    for line in pending
                ]
            },
            headers={"Idempotency-Key": f"glvta-resolve-{plan.ref}"},
        )
        runtime.report.add("returns_accepted")
    await runtime.process_queue()
    if plan.exchange_sku:
        await run_exchange(runtime, catalog, plan, order, UUID(return_id))


async def run_exchange(
    runtime: Runtime, catalog: Catalog, plan: ReturnPlan, order: Any, return_id: UUID
) -> None:
    assert plan.exchange_sku is not None
    exchange_ref = f"{plan.ref}-CAMBIO"
    [customer] = [row for row in catalog.customers.values() if row.id == order.customer_id]
    found = await existing_order(runtime, exchange_ref)
    if found is None:
        body = order_body(
            catalog,
            OrderPlan(
                exchange_ref, plan.day, time(12), customer.code, (LinePlan(plan.exchange_sku, 1),)
            ),
            customer,
            f"Cambio de producto de demostración. Ref. {exchange_ref}",
        )
        body["exchange_return_id"] = str(return_id)
        exchange = await runtime.call(
            "POST", "/sales", json=body, headers={"Idempotency-Key": f"glvta-order-{exchange_ref}"}
        )
        runtime.report.add("exchanges")
    else:
        exchange = await runtime.call("GET", f"/sales/{found.id}")
    if exchange["status"] == "draft":
        exchange = await runtime.call(
            "POST",
            f"/sales/{exchange['id']}/confirm",
            json={"expected_version": exchange["version"]},
        )
    if exchange["status"] == "pending_authorization":
        exchange = await runtime.call(
            "POST",
            f"/sales/{exchange['id']}/authorize",
            json={"expected_version": exchange["version"], "note": "Cambio de producto"},
        )
    if await active_document(runtime, UUID(exchange["id"])) is None:
        await runtime.call("POST", f"/sales/{exchange['id']}/invoice", json={})
    await runtime.process_queue()
    document = await active_document(runtime, UUID(exchange["id"]))
    if document is None:
        return
    receivable = await runtime.call("GET", f"/sales/receivables/documents/{document.id}")
    balance = D(str(receivable["balance"]))
    account = await runtime.call("GET", f"/sales/receivables/customers/{customer.id}")
    for receipt in account["receipts"]:
        unapplied = D(str(receipt["unapplied"]))
        if balance <= 0 or receipt["status"] != "issued" or unapplied <= 0:
            continue
        amount = min(balance, unapplied)
        await runtime.call(
            "POST",
            f"/sales/receipts/{receipt['id']}/apply",
            json={"applications": [{"document_id": str(document.id), "amount": str(amount)}]},
        )
        balance -= amount
        runtime.report.add("credit_applied")
    if customer.credit_days == 0:
        await collect(runtime, catalog, customer, document.id, plan.day, f"{exchange_ref}-RC")


async def collect_credit(
    runtime: Runtime, catalog: Catalog, plans: list[OrderPlan], day: date
) -> None:
    """Cobra las ventas a crédito que vencen ``day`` (si el cliente paga a tiempo)."""

    for plan in plans:
        order = await existing_order(runtime, plan.ref)
        if order is None:
            continue
        customer = customer_by_id(catalog, order.customer_id)
        if customer.credit_days == 0 or plan.day + timedelta(days=customer.credit_days) != day:
            continue
        document = await active_document(runtime, order.id)
        if document is not None:
            await collect(runtime, catalog, customer, document.id, day, f"{plan.ref}-RC")


async def set_goal(runtime: Runtime, catalog: Catalog, first: date, last: date) -> None:
    analysis = await runtime.call(
        "GET",
        "/sales/analytics",
        params={
            "from": first.isoformat(),
            "to": last.isoformat(),
            "branch_id": str(catalog.headquarters),
        },
    )
    sold = D(str(analysis["totals"]["net_sales"]))
    if sold <= 0:
        return
    goal = (sold * D("1.08")).quantize(D("100"))
    await runtime.call(
        "PUT",
        f"/sales/goals/{first:%Y-%m}",
        json={"goals": [{"branch_id": str(catalog.headquarters), "amount": str(goal)}]},
        params={"branch_id": str(catalog.headquarters)},
    )
    runtime.report.add("goals")


# =========================================================================== main


async def _guarded(report: Report, step: Any) -> None:
    """Corre un paso del día; un rechazo de la API queda en el reporte y el mes sigue."""

    from app.core.exceptions import AppError

    try:
        await step
    except (ApiError, AppError) as error:
        report.errors.append(f"{type(error).__name__}: {error}")


async def _box_targets(runtime: Runtime, catalog: Catalog) -> dict[str, int]:
    target = {}
    for sku, pack in PACKS.items():
        if sku not in catalog.products:
            continue
        units = await available_boxes(runtime, catalog, sku)
        total = sum((unit.quantity_base for unit in units), D("0"))
        target[sku] = min(MAX_BOXES, int(total / pack * STOCK_SHARE))
    return target


async def _month_boxes(runtime: Runtime, catalog: Catalog, first: date) -> dict[str, int] | None:
    """Si el mes ya empezó, las cajas con que se planeó: las disponibles más las ya entregadas.

    Así una nueva corrida reconstruye el mismo presupuesto y no fracciona más pallets.
    """

    prefix = f"%Ref. {REF}-{first:%Y%m}%"
    started = await runtime.rows(
        "SELECT 1 FROM sales WHERE company_id = :c AND notes LIKE :ref LIMIT 1",
        c=COMPANY_ID,
        ref=prefix,
    )
    if not started:
        return None
    boxes: dict[str, int] = {}
    for sku, pack in PACKS.items():
        if sku not in catalog.products:
            continue
        units = await available_boxes(runtime, catalog, sku)
        [delivered] = await runtime.rows(
            "SELECT coalesce(sum(a.quantity_base), 0) AS quantity "
            "FROM sales_delivery_allocations a "
            "JOIN sales_delivery_lines dl ON dl.company_id = a.company_id AND dl.id = a.delivery_line_id "
            "JOIN sales_deliveries dv ON dv.company_id = dl.company_id AND dv.id = dl.delivery_id "
            "JOIN sales s ON s.company_id = dl.company_id AND s.id = dl.sale_id "
            "WHERE s.company_id = :c AND s.notes LIKE :ref AND dv.status = 'confirmed' "
            "AND dl.inventory_item_id = :item",
            c=COMPANY_ID,
            ref=prefix,
            item=catalog.products[sku].item_id,
        )
        on_hand = sum(1 for unit in units if unit.quantity_base == pack)
        boxes[sku] = on_hand + int(D(delivered.quantity) / pack)
    return boxes


async def _run_month(
    runtime: Runtime,
    catalog: Catalog,
    days: list[date],
    plan: tuple[list[OrderPlan], list[ReturnPlan]],
) -> None:
    orders, returns = plan
    by_ref = {order.ref: order for order in orders}
    for day in days:
        for order in [item for item in orders if item.day == day]:
            with on_day(day, order.at):
                await _guarded(runtime.report, run_order(runtime, catalog, order))
        with on_day(day, time(17, 30)):
            for item in [ret for ret in returns if ret.day == day]:
                await _guarded(runtime.report, run_return(runtime, catalog, item, by_ref))
            await _guarded(runtime.report, collect_credit(runtime, catalog, orders, day))


async def _super_admin(factory: Any) -> UUID:
    async with factory() as session:
        actor = (
            await session.execute(
                text("SELECT id FROM users WHERE username = :u AND deleted_at IS NULL"),
                {"u": SUPER_ADMIN_USERNAME},
            )
        ).first()
    if actor is None:
        raise RuntimeError("Ejecute primero seed_grupo_lorena (falta el superadmin).")
    return actor.id


async def seed() -> Report:
    if production():
        raise RuntimeError("Los datos de demostración nunca se generan en producción.")
    from app.infrastructure.db.session import dispose_engine
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    factory = _session_factory()
    report = Report()
    actor_id = await _super_admin(factory)
    first, last = demo_month()
    days = business_days(first, last)
    limit = os.environ.get("SEED_DEMO_SALES_DAYS", "").strip()
    if limit:
        days = days[: int(limit)]
    app = create_app()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://seed.internal"
        ) as client:
            runtime = Runtime(client, factory, actor_id, report)
            await ensure_month_prices(runtime, first)
            with on_day(first, time(7)):
                catalog = await load_catalog(runtime)
                boxes = await _month_boxes(runtime, catalog, first)
                target = await _box_targets(runtime, catalog) if boxes is None else {}
            with capture_queues(runtime):
                if boxes is None:
                    with on_day(first, time(7, 15)):
                        boxes = await prepare_boxes(runtime, catalog, target)
                plan = build_plan(days, boxes, random.Random(SEED))
                await _run_month(runtime, catalog, days, plan)
                with on_day(days[-1], time(18)):
                    await _guarded(report, set_goal(runtime, catalog, first, last))
    finally:
        await dispose_engine()
    return report


def main() -> None:
    report = asyncio.run(seed())
    for key, count in sorted(report.created.items()):
        print(f"[seed-ventas] {key}: {count}")
    for error in report.errors:
        print(f"[seed-ventas] ERROR {error}")


if __name__ == "__main__":
    main()
