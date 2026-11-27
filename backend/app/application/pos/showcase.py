"""Vitrina del punto de venta (bloque V6b).

Una vitrina por sucursal, en una ubicación ``showcase`` de una bodega de la sucursal.

- **Pasar a vitrina** mueve unidades logísticas completas y disponibles de esa bodega a la vitrina y
  las abre: desde entonces se venden y se merman por pieza (el motor lo admite solo ahí).
- **Consumo FEFO**: primero lo que vence antes; para vender se salta lo vencido; para mermar se
  empieza por lo vencido.
- **Conteo de cierre**: lo que el sistema tiene y no se contó es merma y sale como ajuste, al costo
  promedio. Contar de más no crea existencia: hay que pasar a vitrina lo que falta registrar.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.inventory import InventoryUseCases
from app.core.exceptions import AppError, BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

ZERO = Decimal("0")
QUANTUM = Decimal("0.000001")
MIN_KEY = 8
MAX_LINES = 200
HTTP_CONFLICT = 409
_TZ = ZoneInfo("America/El_Salvador")

_ITEM_NAME = """
    COALESCE(v.name_override, p.name) AS product_name,
    COALESCE(v.sku, p.sku) AS sku,
    u.symbol AS unit_symbol
"""
_ITEM_JOINS = """
    JOIN inventory_items i ON i.company_id = h.company_id AND i.id = h.inventory_item_id
    LEFT JOIN product_variants v ON v.company_id = i.company_id AND v.id = i.variant_id
    JOIN products p ON p.company_id = i.company_id AND p.id_product = COALESCE(i.product_id, v.product_id)
    JOIN units u ON u.id_unit = i.base_unit_id
"""


async def _post_movement(session: AsyncSession, **kwargs: Any) -> dict[str, Any]:
    """Registra en el motor de inventario y traduce su error a uno de la API (409 o 422)."""
    try:
        return await InventoryUseCases(SqlAlchemyInventoryRepository(session)).post_movement(
            **kwargs
        )
    except InventoryOperationError as error:
        kind: type[AppError] = (
            ConflictError if error.status_code == HTTP_CONFLICT else BusinessRuleError
        )
        raise kind(error.message, code=error.code) from error


def _today() -> date:
    return datetime.now(_TZ).date()


def _key(value: str) -> str:
    key = value.strip()
    if len(key) < MIN_KEY:
        raise BusinessRuleError("Falta la clave de idempotencia.", code="pos_idempotency_key")
    return key


@dataclass(frozen=True)
class Showcase:
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    location_id: uuid.UUID
    location_code: str
    created_at: datetime


@dataclass(frozen=True)
class WarehouseOption:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class ShowcaseUnit:
    handling_unit_id: uuid.UUID
    code: str
    quantity: Decimal
    lot_code: str | None
    expiry_date: date | None
    opened_at: datetime | None
    expired: bool


@dataclass(frozen=True)
class ShowcaseStock:
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str
    unit_symbol: str
    quantity: Decimal
    sellable: Decimal
    expired: Decimal
    next_expiry: date | None
    units: tuple[ShowcaseUnit, ...]


@dataclass(frozen=True)
class Candidate:
    handling_unit_id: uuid.UUID
    code: str
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str
    unit_symbol: str
    quantity: Decimal
    lot_code: str | None
    expiry_date: date | None
    location_code: str


@dataclass(frozen=True)
class CountLineInput:
    inventory_item_id: uuid.UUID
    counted_quantity: Decimal
    reason: str | None


@dataclass(frozen=True)
class CountLine:
    inventory_item_id: uuid.UUID
    product_name: str
    unit_symbol: str
    system_quantity: Decimal
    counted_quantity: Decimal
    waste_quantity: Decimal
    reason: str | None


@dataclass(frozen=True)
class ShowcaseCount:
    id: uuid.UUID
    number: int
    branch_id: uuid.UUID
    counted_by_name: str
    counted_at: datetime
    notes: str | None
    waste_cost: Decimal
    movement_id: uuid.UUID | None
    idempotency_key: str
    lines: tuple[CountLine, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Issue:
    """Una pieza que sale de la vitrina: de qué unidad y cuánto."""

    inventory_item_id: uuid.UUID
    handling_unit_id: uuid.UUID
    location_id: uuid.UUID
    quantity: Decimal


class PosShowcaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- vitrina ---------------------------------------------------------------------------------

    async def showcases(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Showcase]:
        rows = await self.session.execute(
            text(
                """
                SELECT s.id, s.branch_id, b.name AS branch_name, s.warehouse_id,
                       w.name AS warehouse_name, s.location_id, l.code AS location_code, s.created_at
                FROM pos_showcases s
                JOIN branches b ON b.id = s.branch_id
                JOIN warehouses w ON w.id = s.warehouse_id
                JOIN locations l ON l.id = s.location_id
                WHERE s.company_id = :company
                  AND (CAST(:branches AS uuid[]) IS NULL OR s.branch_id = ANY(CAST(:branches AS uuid[])))
                ORDER BY b.name
                """
            ),
            {"company": company_id, "branches": None if branch_ids is None else list(branch_ids)},
        )
        return [Showcase(**row._mapping) for row in rows]

    async def showcase(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, lock: bool = False
    ) -> Showcase:
        if lock:
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"pos_showcase:{company_id}:{branch_id}"},
            )
        found = await self.showcases(company_id, [branch_id])
        if not found:
            raise NotFoundError(
                "La sucursal todavía no tiene vitrina.", code="pos_showcase_not_found"
            )
        return found[0]

    async def warehouse_options(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[WarehouseOption]:
        rows = await self.session.execute(
            text(
                """
                SELECT id, name FROM warehouses
                WHERE company_id = :company AND branch_id = :branch AND is_active
                  AND NOT is_transit AND operational_status = 'active' AND deleted_at IS NULL
                ORDER BY is_central DESC, name
                """
            ),
            {"company": company_id, "branch": branch_id},
        )
        return [WarehouseOption(row.id, row.name) for row in rows]

    async def create(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Showcase:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"pos_showcase:{company_id}:{branch_id}"},
        )
        if await self.showcases(company_id, [branch_id]):
            raise ConflictError("La sucursal ya tiene vitrina.", code="pos_showcase_exists")
        if warehouse_id not in {
            option.id for option in await self.warehouse_options(company_id, branch_id)
        }:
            raise BusinessRuleError(
                "Elige una bodega activa de la sucursal.", code="pos_showcase_warehouse_invalid"
            )
        taken = {
            str(code).casefold()
            for code in (
                await self.session.scalars(
                    text(
                        "SELECT code FROM locations WHERE warehouse_id = :w AND deleted_at IS NULL "
                        "AND lower(code) LIKE 'vitrina%'"
                    ),
                    {"w": warehouse_id},
                )
            ).all()
        }
        code = next(
            candidate
            for candidate in ("VITRINA", *(f"VITRINA-{n}" for n in range(2, 100)))
            if candidate.casefold() not in taken
        )
        try:
            async with self.session.begin_nested():
                location_id = await self.session.scalar(
                    text(
                        "INSERT INTO locations (id, warehouse_id, code, area, aisle, rack, level, "
                        "position, location_type, capacity_enforcement_mode, storage_eligible, "
                        "notes, created_at, updated_at) VALUES (gen_random_uuid(), :w, :code, 'POS', "
                        ":code, '1', '1', '1', 'showcase', 'disabled', true, "
                        "'Vitrina del punto de venta', now(), now()) RETURNING id"
                    ),
                    {"w": warehouse_id, "code": code},
                )
                await self.session.execute(
                    text(
                        "INSERT INTO pos_showcases (company_id, branch_id, warehouse_id, location_id, "
                        "created_by_id) VALUES (:company, :branch, :w, :location, :actor)"
                    ),
                    {
                        "company": company_id,
                        "branch": branch_id,
                        "w": warehouse_id,
                        "location": location_id,
                        "actor": actor_id,
                    },
                )
        except IntegrityError as error:
            raise ConflictError(
                "No se pudo crear la vitrina; otra persona la creó al mismo tiempo.",
                code="pos_showcase_conflict",
            ) from error
        return await self.showcase(company_id, branch_id)

    # --- existencias -----------------------------------------------------------------------------

    async def stock(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> list[ShowcaseStock]:
        showcase = await self.showcase(company_id, branch_id)
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT h.id, h.code, h.inventory_item_id, h.quantity_base, h.lot_code,
                           h.expiry_date, h.opened_at, {_ITEM_NAME}
                    FROM inventory_handling_units h {_ITEM_JOINS}
                    WHERE h.company_id = :company AND h.location_id = :location
                      AND h.closed_at IS NULL AND h.stock_status = 'available'
                      AND h.quantity_base > 0
                    ORDER BY product_name, h.expiry_date NULLS LAST, h.opened_at, h.created_at
                    """  # noqa: S608 - fragmentos fijos del módulo, sin datos del usuario
                ),
                {"company": company_id, "location": showcase.location_id},
            )
        ).all()
        today = _today()
        grouped: dict[uuid.UUID, list[Any]] = {}
        for row in rows:
            grouped.setdefault(row.inventory_item_id, []).append(row)
        result: list[ShowcaseStock] = []
        for item_id, units in grouped.items():
            first = units[0]
            parsed = tuple(
                ShowcaseUnit(
                    handling_unit_id=row.id,
                    code=row.code,
                    quantity=Decimal(row.quantity_base),
                    lot_code=row.lot_code,
                    expiry_date=row.expiry_date,
                    opened_at=row.opened_at,
                    expired=row.expiry_date is not None and row.expiry_date < today,
                )
                for row in units
            )
            total = sum((unit.quantity for unit in parsed), ZERO)
            expired = sum((unit.quantity for unit in parsed if unit.expired), ZERO)
            future = [unit.expiry_date for unit in parsed if unit.expiry_date and not unit.expired]
            result.append(
                ShowcaseStock(
                    inventory_item_id=item_id,
                    product_name=first.product_name,
                    sku=first.sku,
                    unit_symbol=first.unit_symbol,
                    quantity=total,
                    sellable=total - expired,
                    expired=expired,
                    next_expiry=min(future) if future else None,
                    units=parsed,
                )
            )
        return result

    async def candidates(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, search: str | None = None
    ) -> list[Candidate]:
        """Unidades completas y disponibles de la bodega de la vitrina, primero lo que vence antes."""
        showcase = await self.showcase(company_id, branch_id)
        term = f"%{search.strip()}%" if search and search.strip() else None
        rows = await self.session.execute(
            text(
                f"""
                SELECT h.id, h.code, h.inventory_item_id, h.quantity_base, h.lot_code, h.expiry_date,
                       l.code AS location_code, {_ITEM_NAME}
                FROM inventory_handling_units h {_ITEM_JOINS}
                JOIN locations l ON l.id = h.location_id AND l.warehouse_id = h.warehouse_id
                WHERE h.company_id = :company AND h.warehouse_id = :warehouse
                  AND h.location_id <> :showcase AND h.closed_at IS NULL AND h.opened_at IS NULL
                  AND h.stock_status = 'available' AND h.inventory_posted_at IS NOT NULL
                  AND h.quantity_base > 0
                  AND (h.expiry_date IS NULL OR h.expiry_date >= :today)
                  AND l.is_active AND l.deleted_at IS NULL AND l.lifecycle_status = 'active'
                  AND l.location_type NOT IN ('virtual', 'showcase')
                  AND NOT EXISTS (
                      SELECT 1 FROM sales_delivery_allocations a
                      JOIN sales_delivery_lines dl ON dl.company_id = a.company_id
                           AND dl.id = a.delivery_line_id
                      JOIN sales_deliveries d ON d.company_id = dl.company_id AND d.id = dl.delivery_id
                      WHERE a.company_id = h.company_id AND a.handling_unit_id = h.id
                        AND d.status = 'draft')
                  AND (CAST(:term AS text) IS NULL OR COALESCE(v.name_override, p.name) ILIKE :term
                       OR COALESCE(v.sku, p.sku) ILIKE :term OR h.code ILIKE :term)
                ORDER BY product_name, h.expiry_date NULLS LAST, h.created_at
                LIMIT 200
                """  # noqa: S608 - fragmentos fijos del módulo, sin datos del usuario
            ),
            {
                "company": company_id,
                "warehouse": showcase.warehouse_id,
                "showcase": showcase.location_id,
                "today": _today(),
                "term": term,
            },
        )
        return [
            Candidate(
                handling_unit_id=row.id,
                code=row.code,
                inventory_item_id=row.inventory_item_id,
                product_name=row.product_name,
                sku=row.sku,
                unit_symbol=row.unit_symbol,
                quantity=Decimal(row.quantity_base),
                lot_code=row.lot_code,
                expiry_date=row.expiry_date,
                location_code=row.location_code,
            )
            for row in rows
        ]

    # --- pasar a vitrina -------------------------------------------------------------------------

    async def open_units(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        handling_unit_ids: Sequence[uuid.UUID],
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> tuple[uuid.UUID, bool]:
        """Mueve las unidades completas a la vitrina y las abre. Devuelve el movimiento y si es nuevo."""
        key = f"pos-showcase-open:{_key(idempotency_key)}"
        if not handling_unit_ids or len(set(handling_unit_ids)) != len(handling_unit_ids):
            raise BusinessRuleError(
                "Elige las unidades que pasan a vitrina, sin repetirlas.",
                code="pos_showcase_units_required",
            )
        showcase = await self.showcase(company_id, branch_id, lock=True)
        existing = await self.session.scalar(
            text(
                "SELECT id FROM inventory_movements WHERE company_id = :company "
                "AND idempotency_key = :key"
            ),
            {"company": company_id, "key": key},
        )
        if existing is not None:
            return existing, False
        allowed = {
            item.handling_unit_id: item for item in await self.candidates(company_id, branch_id)
        }
        missing = [unit_id for unit_id in handling_unit_ids if unit_id not in allowed]
        if missing:
            raise ConflictError(
                "Una de las unidades ya no está disponible en la bodega de la vitrina.",
                code="pos_showcase_unit_unavailable",
            )
        units = (
            await self.session.execute(
                text(
                    "SELECT id, inventory_item_id, location_id, quantity_base FROM "
                    "inventory_handling_units WHERE company_id = :company AND id = ANY(:ids) "
                    "ORDER BY id FOR UPDATE"
                ),
                {"company": company_id, "ids": list(handling_unit_ids)},
            )
        ).all()
        movement = await _post_movement(
            self.session,
            company_id=company_id,
            actor_id=actor_id,
            movement_type="transfer",
            idempotency_key=key,
            source_reference=f"pos_showcase:{showcase.id}",
            lines=[
                {
                    "inventory_item_id": row.inventory_item_id,
                    "handling_unit_id": row.id,
                    "from_location_id": row.location_id,
                    "from_stock_status": "available",
                    "to_location_id": showcase.location_id,
                    "to_stock_status": "available",
                    "quantity_base": Decimal(row.quantity_base),
                }
                for row in units
            ],
        )
        await self.session.execute(
            text(
                "UPDATE inventory_handling_units SET opened_at = :now, opened_by_id = :actor "
                "WHERE company_id = :company AND id = ANY(:ids)"
            ),
            {
                "now": datetime.now(UTC),
                "actor": actor_id,
                "company": company_id,
                "ids": list(handling_unit_ids),
            },
        )
        return uuid.UUID(str(movement["id"])), True

    # --- consumo FEFO ----------------------------------------------------------------------------

    async def allocate(
        self,
        company_id: uuid.UUID,
        showcase: Showcase,
        inventory_item_id: uuid.UUID,
        quantity: Decimal,
        *,
        include_expired: bool,
    ) -> list[Issue]:
        """Reparte una cantidad entre las unidades abiertas, primero lo que vence antes.

        Para vender (``include_expired=False``) lo vencido no cuenta. Bloquea las unidades.
        """
        if quantity <= ZERO:
            return []
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, quantity_base, expiry_date FROM inventory_handling_units
                    WHERE company_id = :company AND location_id = :location
                      AND inventory_item_id = :item AND closed_at IS NULL
                      AND opened_at IS NOT NULL AND stock_status = 'available'
                      AND quantity_base > 0
                      AND (:expired OR expiry_date IS NULL OR expiry_date >= :today)
                    ORDER BY expiry_date NULLS LAST, opened_at, created_at, id
                    FOR UPDATE
                    """
                ),
                {
                    "company": company_id,
                    "location": showcase.location_id,
                    "item": inventory_item_id,
                    "expired": include_expired,
                    "today": _today(),
                },
            )
        ).all()
        remaining = quantity
        issues: list[Issue] = []
        for row in rows:
            if remaining <= ZERO:
                break
            take = min(remaining, Decimal(row.quantity_base))
            issues.append(Issue(inventory_item_id, row.id, showcase.location_id, take))
            remaining -= take
        if remaining > ZERO:
            raise BusinessRuleError(
                "No hay suficiente en la vitrina; pasa más a vitrina desde la bodega.",
                code="pos_showcase_stock_insufficient",
            )
        return issues

    @staticmethod
    def movement_lines(issues: Sequence[Issue]) -> list[dict[str, Any]]:
        return [
            {
                "inventory_item_id": issue.inventory_item_id,
                "handling_unit_id": issue.handling_unit_id,
                "from_location_id": issue.location_id,
                "from_stock_status": "available",
                "to_location_id": None,
                "to_stock_status": None,
                "quantity_base": issue.quantity,
            }
            for issue in issues
        ]

    # --- conteo de cierre ------------------------------------------------------------------------

    async def counts(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, limit: int = 30
    ) -> list[ShowcaseCount]:
        return await self._counts(company_id, "c.branch_id = :branch", {"branch": branch_id}, limit)

    async def _counts(
        self, company_id: uuid.UUID, where: str, params: dict[str, Any], limit: int = 30
    ) -> list[ShowcaseCount]:
        rows = (
            await self.session.execute(
                text(
                    "SELECT c.*, pos_user_name(c.counted_by_id) AS counted_by_name "
                    "FROM pos_showcase_counts c WHERE c.company_id = :company AND "
                    + where
                    + " ORDER BY c.counted_at DESC, c.number DESC LIMIT :limit"
                ),
                {"company": company_id, "limit": limit, **params},
            )
        ).all()
        if not rows:
            return []
        lines: dict[uuid.UUID, list[CountLine]] = {}
        for line in await self.session.execute(
            text(
                """
                SELECT cl.count_id, cl.inventory_item_id, cl.system_quantity, cl.counted_quantity,
                       cl.waste_quantity, cl.reason,
                       COALESCE(v.name_override, p.name) AS product_name, u.symbol AS unit_symbol
                FROM pos_showcase_count_lines cl
                JOIN inventory_items i ON i.company_id = cl.company_id AND i.id = cl.inventory_item_id
                LEFT JOIN product_variants v ON v.company_id = i.company_id AND v.id = i.variant_id
                JOIN products p ON p.company_id = i.company_id
                     AND p.id_product = COALESCE(i.product_id, v.product_id)
                JOIN units u ON u.id_unit = i.base_unit_id
                WHERE cl.company_id = :company AND cl.count_id = ANY(:counts)
                ORDER BY product_name
                """
            ),
            {"company": company_id, "counts": [row.id for row in rows]},
        ):
            lines.setdefault(line.count_id, []).append(
                CountLine(
                    inventory_item_id=line.inventory_item_id,
                    product_name=line.product_name,
                    unit_symbol=line.unit_symbol,
                    system_quantity=Decimal(line.system_quantity),
                    counted_quantity=Decimal(line.counted_quantity),
                    waste_quantity=Decimal(line.waste_quantity),
                    reason=line.reason,
                )
            )
        return [
            ShowcaseCount(
                id=row.id,
                number=row.number,
                branch_id=row.branch_id,
                counted_by_name=row.counted_by_name,
                counted_at=row.counted_at,
                notes=row.notes,
                waste_cost=Decimal(row.waste_cost),
                movement_id=row.movement_id,
                idempotency_key=row.idempotency_key,
                lines=tuple(lines.get(row.id, ())),
            )
            for row in rows
        ]

    async def count(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        lines: Sequence[CountLineInput],
        notes: str | None,
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> tuple[ShowcaseCount, bool]:
        key = _key(idempotency_key)
        repeated = await self._counts(company_id, "c.idempotency_key = :key", {"key": key}, 1)
        if repeated:
            if repeated[0].branch_id != branch_id:
                raise ConflictError(
                    "La clave de idempotencia ya se usó en otra vitrina.",
                    code="pos_idempotency_conflict",
                )
            return repeated[0], False
        if not lines or len(lines) > MAX_LINES:
            raise BusinessRuleError(
                "Cuenta al menos un producto de la vitrina.", code="pos_showcase_count_empty"
            )
        if len({line.inventory_item_id for line in lines}) != len(lines):
            raise BusinessRuleError(
                "Un producto aparece dos veces en el conteo.", code="pos_showcase_count_repeated"
            )
        showcase = await self.showcase(company_id, branch_id, lock=True)
        prepared = await self._prepare_count(company_id, branch_id, lines)
        issues: list[Issue] = []
        for line, on_hand, counted, _reason in prepared:
            issues.extend(
                await self.allocate(
                    company_id,
                    showcase,
                    line.inventory_item_id,
                    on_hand - counted,
                    include_expired=True,
                )
            )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"pos_showcase_counts:{company_id}"},
        )
        number = int(
            await self.session.scalar(
                text(
                    "SELECT COALESCE(max(number), 0) + 1 FROM pos_showcase_counts WHERE company_id = :c"
                ),
                {"c": company_id},
            )
            or 1
        )
        count_id = uuid.uuid4()
        movement_id: uuid.UUID | None = None
        waste_cost = ZERO
        if issues:
            movement = await _post_movement(
                self.session,
                company_id=company_id,
                actor_id=actor_id,
                movement_type="adjustment_out",
                idempotency_key=f"pos-showcase-count:{key}",
                source_reference=f"pos_showcase_count:{count_id}",
                lines=self.movement_lines(issues),
            )
            movement_id = uuid.UUID(str(movement["id"]))
            waste_cost = Decimal(
                await self.session.scalar(
                    text(
                        "SELECT COALESCE(-sum(e.inventory_delta), 0) FROM inventory_valuation_entries e "
                        "JOIN inventory_movement_lines ml ON ml.id = e.movement_line_id "
                        "WHERE e.company_id = :company AND ml.movement_id = :movement"
                    ),
                    {"company": company_id, "movement": movement_id},
                )
                or ZERO
            )
        clean_notes = " ".join((notes or "").split()) or None
        await self.session.execute(
            text(
                "INSERT INTO pos_showcase_counts (id, company_id, showcase_id, branch_id, number, "
                "notes, movement_id, waste_cost, counted_by_id, idempotency_key) VALUES (:id, "
                ":company, :showcase, :branch, :number, :notes, :movement, :cost, :actor, :key)"
            ),
            {
                "id": count_id,
                "company": company_id,
                "showcase": showcase.id,
                "branch": branch_id,
                "number": number,
                "notes": clean_notes[:300] if clean_notes else None,
                "movement": movement_id,
                "cost": max(waste_cost, ZERO),
                "actor": actor_id,
                "key": key,
            },
        )
        await self.session.execute(
            text(
                "INSERT INTO pos_showcase_count_lines (company_id, count_id, inventory_item_id, "
                "system_quantity, counted_quantity, waste_quantity, reason) VALUES (:company, :count, "
                ":item, :system, :counted, :waste, :reason)"
            ),
            [
                {
                    "company": company_id,
                    "count": count_id,
                    "item": line.inventory_item_id,
                    "system": on_hand,
                    "counted": counted,
                    "waste": on_hand - counted,
                    "reason": reason,
                }
                for line, on_hand, counted, reason in prepared
            ],
        )
        [created] = await self._counts(company_id, "c.id = :id", {"id": count_id}, 1)
        return created, True

    async def _prepare_count(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, lines: Sequence[CountLineInput]
    ) -> list[tuple[CountLineInput, Decimal, Decimal, str | None]]:
        """Compara cada línea con la existencia: nada de más y toda merma con su motivo."""
        system = {item.inventory_item_id: item for item in await self.stock(company_id, branch_id)}
        prepared: list[tuple[CountLineInput, Decimal, Decimal, str | None]] = []
        for line in lines:
            counted = line.counted_quantity.quantize(QUANTUM)
            if counted < ZERO:
                raise BusinessRuleError(
                    "Una cantidad contada no puede ser negativa.", code="pos_showcase_count_invalid"
                )
            current = system.get(line.inventory_item_id)
            on_hand = current.quantity if current else ZERO
            if counted > on_hand:
                name = current.product_name if current else "un producto que no está en vitrina"
                raise BusinessRuleError(
                    f"Contaste más {name} de lo que registra la vitrina. Pasa a vitrina lo que falta "
                    "registrar antes de contar.",
                    code="pos_showcase_count_over",
                )
            waste = on_hand - counted
            reason = " ".join((line.reason or "").split()) or None
            if waste > ZERO and (reason is None or len(reason) < 3):  # noqa: PLR2004
                raise BusinessRuleError(
                    f"Indica el motivo de la merma de {current.product_name if current else ''}.",
                    code="pos_showcase_waste_reason_required",
                )
            prepared.append((line, on_hand, counted, reason))
        return prepared
