"""Idempotent physical-capacity demonstration for selected Grupo Lorena warehouses.

The demo uses real inventory commands so handling units, ledger movements and
capacity summaries stay consistent. It never deletes existing business data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal

from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory import PackagingType, PhysicalMeasures
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import (
    InventoryItemModel,
    InventoryMovementModel,
    InventoryPackagingModel,
)
from app.infrastructure.models.organization import (
    Location,
    Warehouse,
    WarehouseCapacityGroup,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import (
    SqlAlchemyInventoryRepository,
)
from sqlalchemy import func, select

from seed.grupo_lorena_media import COMPANY_ID
from seed.seed_grupo_lorena import _session_factory


def d(value: str) -> Decimal:
    return Decimal(value)


@dataclass(frozen=True, slots=True)
class CapacityLimits:
    certified_weight: Decimal
    operational_weight: Decimal
    certified_volume: Decimal
    operational_volume: Decimal
    length: Decimal
    width: Decimal
    height: Decimal


@dataclass(frozen=True, slots=True)
class StructureDemo:
    code: str
    name: str
    group_type: str
    profile: str
    limits: CapacityLimits
    parent_code: str | None = None


@dataclass(frozen=True, slots=True)
class LocationDemo:
    code: str
    location_type: str
    group_code: str | None
    profile: str
    limits: CapacityLimits | None
    storage_eligible: bool = True


@dataclass(frozen=True, slots=True)
class StockDemo:
    product_sku: str
    packaging_code: str
    packaging_name: str
    packaging_type: PackagingType
    base_quantity: Decimal
    measures: PhysicalMeasures
    stackable: bool
    max_stack: int | None
    quantity_base: Decimal
    location_code: str
    handling_unit_code: str
    lot_code: str


@dataclass(frozen=True, slots=True)
class WarehouseDemo:
    code: str
    profile: str
    limits: CapacityLimits
    structures: tuple[StructureDemo, ...]
    locations: tuple[LocationDemo, ...]
    stock: StockDemo


TRANSIT_LOCATION = lambda code, location_type: LocationDemo(  # noqa: E731
    code=code,
    location_type=location_type,
    group_code=None,
    profile="transit",
    limits=None,
    storage_eligible=False,
)


CAPACITY_DEMOS: tuple[WarehouseDemo, ...] = (
    WarehouseDemo(
        code="BOD-ET-01",
        profile="rack",
        limits=CapacityLimits(d("3600"), d("3000"), d("28"), d("22"), d("12"), d("8"), d("3.2")),
        structures=(
            StructureDemo(
                "RACK-A",
                "Rack A · almacenamiento seco",
                "rack",
                "rack",
                CapacityLimits(d("2200"), d("1900"), d("18"), d("14"), d("8"), d("2"), d("2.4")),
            ),
            StructureDemo(
                "RACK-A-N1",
                "Nivel 1 del Rack A",
                "level",
                "rack",
                CapacityLimits(d("1700"), d("1400"), d("10"), d("8"), d("2"), d("1.2"), d("1.8")),
                parent_code="RACK-A",
            ),
        ),
        locations=(
            LocationDemo(
                "A01-R01-N01-P01",
                "standard",
                "RACK-A-N1",
                "rack",
                CapacityLimits(d("1700"), d("1400"), d("10"), d("8"), d("0.9"), d("1.2"), d("1.8")),
            ),
            LocationDemo(
                "A01-R01-N01-P02",
                "standard",
                "RACK-A-N1",
                "rack",
                CapacityLimits(d("1700"), d("1400"), d("10"), d("8"), d("0.9"), d("1.2"), d("1.8")),
            ),
            LocationDemo(
                "A01-R03-N02-P04",
                "reserve",
                None,
                "rack",
                CapacityLimits(d("1200"), d("950"), d("8"), d("6"), d("0.9"), d("1.2"), d("1.8")),
            ),
            LocationDemo(
                "A02-R01-N01-P03",
                "picking",
                None,
                "rack",
                CapacityLimits(d("900"), d("700"), d("6"), d("4.5"), d("0.9"), d("1.2"), d("1.8")),
            ),
        ),
        stock=StockDemo(
            "PRD-HAR-001",
            "SACK-50LB",
            "Saco de harina 50 lb",
            PackagingType.BAG,
            d("1"),
            PhysicalMeasures(d("22.68"), d("0.80"), d("0.50"), d("0.18"), d("0.072")),
            True,
            8,
            d("40"),
            "A01-R01-N01-P01",
            "HU-DEMO-ET-HARINA-001",
            "HAR-ET-2026-01",
        ),
    ),
    WarehouseDemo(
        code="BOD-SM-01",
        profile="bulk_floor",
        limits=CapacityLimits(d("4800"), d("4000"), d("35"), d("28"), d("10"), d("7"), d("3")),
        structures=(
            StructureDemo(
                "PISO-SECO",
                "Zona de piso para sacos",
                "floor_zone",
                "bulk_floor",
                CapacityLimits(d("2600"), d("2200"), d("16"), d("12"), d("6"), d("4"), d("2.5")),
            ),
        ),
        locations=(
            TRANSIT_LOCATION("REC-01", "receiving"),
            LocationDemo(
                "SEC-02",
                "bulk",
                "PISO-SECO",
                "bulk_floor",
                CapacityLimits(d("2600"), d("2200"), d("16"), d("12"), d("6"), d("4"), d("2.5")),
            ),
            TRANSIT_LOCATION("EMP-03", "packing"),
        ),
        stock=StockDemo(
            "PRD-HAR-001",
            "SACK-50LB",
            "Saco de harina 50 lb",
            PackagingType.BAG,
            d("1"),
            PhysicalMeasures(d("22.68"), d("0.80"), d("0.50"), d("0.18"), d("0.072")),
            True,
            8,
            d("80"),
            "SEC-02",
            "HU-DEMO-SM-HARINA-001",
            "HAR-SM-2026-01",
        ),
    ),
    WarehouseDemo(
        code="BOD-JIQ-01",
        profile="cold",
        limits=CapacityLimits(d("3600"), d("3000"), d("26"), d("20"), d("8"), d("6"), d("2.8")),
        structures=(
            StructureDemo(
                "CAM-FRIA-01",
                "Cámara fría principal",
                "cold_chamber",
                "cold",
                CapacityLimits(d("1900"), d("1600"), d("9"), d("6.5"), d("4"), d("3"), d("2.4")),
            ),
        ),
        locations=(
            TRANSIT_LOCATION("REC-01", "receiving"),
            LocationDemo(
                "SEC-02",
                "reserve",
                "CAM-FRIA-01",
                "cold",
                CapacityLimits(d("1900"), d("1600"), d("9"), d("6.5"), d("4"), d("3"), d("2.4")),
            ),
            TRANSIT_LOCATION("EMP-03", "packing"),
        ),
        stock=StockDemo(
            "PRD-LAC-002",
            "BOX-10KG",
            "Caja de mantequilla 10 kg",
            PackagingType.BOX,
            d("1"),
            PhysicalMeasures(d("10.5"), d("0.40"), d("0.30"), d("0.25"), d("0.03")),
            True,
            6,
            d("140"),
            "SEC-02",
            "HU-DEMO-JIQ-MANTEQUILLA-001",
            "LAC-JIQ-2026-01",
        ),
    ),
)


def apply_limits(resource: object, limits: CapacityLimits | None, *, profile: str) -> None:
    resource.capacity_profile = profile
    if limits is None:
        resource.certified_max_weight_kg = None
        resource.operational_max_weight_kg = None
        resource.certified_usable_volume_m3 = None
        resource.operational_usable_volume_m3 = None
        resource.usable_length_m = None
        resource.usable_width_m = None
        resource.usable_height_m = None
        return
    resource.certified_max_weight_kg = limits.certified_weight
    resource.operational_max_weight_kg = limits.operational_weight
    resource.certified_usable_volume_m3 = limits.certified_volume
    resource.operational_usable_volume_m3 = limits.operational_volume
    resource.usable_length_m = limits.length
    resource.usable_width_m = limits.width
    resource.usable_height_m = limits.height


async def ensure_structure(session, warehouse: Warehouse, specification: StructureDemo, parents):
    row = await session.scalar(
        select(WarehouseCapacityGroup)
        .where(
            WarehouseCapacityGroup.warehouse_id == warehouse.id,
            func.lower(WarehouseCapacityGroup.code) == specification.code.casefold(),
        )
        .execution_options(include_deleted=True)
    )
    if row is None:
        row = WarehouseCapacityGroup(warehouse_id=warehouse.id, code=specification.code)
        session.add(row)
    row.deleted_at = None
    row.deleted_by = None
    row.deletion_reason = None
    row.code = specification.code
    row.name = specification.name
    row.group_type = specification.group_type
    row.parent_id = parents.get(specification.parent_code)
    row.capacity_enforcement_mode = "enforce"
    row.storage_eligible = True
    row.is_active = True
    apply_limits(row, specification.limits, profile=specification.profile)
    await session.flush()
    return row


async def ensure_item_and_packaging(session, use_cases: InventoryUseCases, stock: StockDemo):
    product = await session.scalar(
        select(ProductModel).where(
            ProductModel.company_id == COMPANY_ID,
            ProductModel.sku == stock.product_sku,
            ProductModel.deleted_at.is_(None),
        )
    )
    if product is None:
        raise RuntimeError(f"Producto de demostración no encontrado: {stock.product_sku}")
    item_row = await session.scalar(
        select(InventoryItemModel).where(
            InventoryItemModel.company_id == COMPANY_ID,
            InventoryItemModel.product_id == product.id_product,
        )
    )
    item_created = item_row is None
    if item_row is None:
        item = await use_cases.create_item(
            company_id=COMPANY_ID,
            product_id=product.id_product,
            variant_id=None,
            base_unit_id=1,
        )
        item_id = item.id
    else:
        item_id = item_row.id

    packaging_row = await session.scalar(
        select(InventoryPackagingModel).where(
            InventoryPackagingModel.company_id == COMPANY_ID,
            InventoryPackagingModel.inventory_item_id == item_id,
            InventoryPackagingModel.code == stock.packaging_code,
            InventoryPackagingModel.is_current.is_(True),
            InventoryPackagingModel.is_active.is_(True),
        )
    )
    packaging_created = packaging_row is None
    if packaging_row is None:
        packaging = await use_cases.create_packaging(
            company_id=COMPANY_ID,
            item_id=item_id,
            code=stock.packaging_code,
            name=stock.packaging_name,
            packaging_type=stock.packaging_type,
            base_quantity=stock.base_quantity,
            measures=stock.measures,
            stackable=stock.stackable,
            max_stack=stock.max_stack,
        )
        packaging_id = packaging.id
    else:
        packaging_id = packaging_row.id
    return item_id, packaging_id, item_created, packaging_created


async def seed() -> None:  # noqa: C901 - orchestration is intentionally kept transactional
    factory = _session_factory()
    async with factory() as session, session.begin():
        actor = await session.scalar(
            select(User).where(User.username == "superadmin", User.deleted_at.is_(None))
        )
        if actor is None:
            raise RuntimeError("El usuario superadmin es requerido para auditar la demostración.")
        use_cases = InventoryUseCases(SqlAlchemyInventoryRepository(session))

        for scenario in CAPACITY_DEMOS:
            warehouse = await session.scalar(
                select(Warehouse).where(
                    Warehouse.code == scenario.code,
                    Warehouse.deleted_at.is_(None),
                )
            )
            if warehouse is None:
                raise RuntimeError(f"Almacén de demostración no encontrado: {scenario.code}")
            warehouse.capacity_enforcement_mode = "enforce"
            warehouse.storage_eligible = True
            warehouse.operational_status = "active"
            warehouse.is_active = True
            apply_limits(warehouse, scenario.limits, profile=scenario.profile)
            await session.flush()

            structures: dict[str, WarehouseCapacityGroup] = {}
            parent_ids: dict[str | None, object] = {None: None}
            for specification in scenario.structures:
                structure = await ensure_structure(session, warehouse, specification, parent_ids)
                structures[specification.code] = structure
                parent_ids[specification.code] = structure.id

            locations: dict[str, Location] = {}
            for specification in scenario.locations:
                location = await session.scalar(
                    select(Location).where(
                        Location.warehouse_id == warehouse.id,
                        func.lower(Location.code) == specification.code.casefold(),
                        Location.deleted_at.is_(None),
                    )
                )
                if location is None:
                    raise RuntimeError(
                        f"Ubicación {specification.code} no encontrada en {scenario.code}."
                    )
                location.location_type = specification.location_type
                location.capacity_group_id = (
                    structures[specification.group_code].id
                    if specification.group_code is not None
                    else None
                )
                location.storage_eligible = specification.storage_eligible
                location.capacity_enforcement_mode = (
                    "enforce" if specification.storage_eligible else "disabled"
                )
                location.lifecycle_status = "active"
                location.is_active = True
                apply_limits(location, specification.limits, profile=specification.profile)
                locations[specification.code] = location
            await session.flush()

            (
                item_id,
                packaging_id,
                item_created,
                packaging_created,
            ) = await ensure_item_and_packaging(session, use_cases, scenario.stock)
            movement_key = f"capacity-demo-{scenario.code.lower()}-v1"
            movement_existed = await session.scalar(
                select(InventoryMovementModel.id).where(
                    InventoryMovementModel.company_id == COMPANY_ID,
                    InventoryMovementModel.idempotency_key == movement_key,
                )
            )
            movement = await use_cases.post_movement(
                company_id=COMPANY_ID,
                idempotency_key=movement_key,
                movement_type="receipt",
                source_reference="Demostración de capacidad física",
                lines=[
                    {
                        "inventory_item_id": item_id,
                        "packaging_definition_id": packaging_id,
                        "handling_unit_code": scenario.stock.handling_unit_code,
                        "lot_code": scenario.stock.lot_code,
                        "expiry_date": None,
                        "from_location_id": None,
                        "to_location_id": locations[scenario.stock.location_code].id,
                        "from_stock_status": None,
                        "to_stock_status": "available",
                        "quantity_base": scenario.stock.quantity_base,
                        "actual_measures": None,
                        "capacity_override_id": None,
                    }
                ],
                actor_id=actor.id,
            )

            audit_exists = await session.scalar(
                select(AuditLog.id).where(
                    AuditLog.action == "SEED_DEMO",
                    AuditLog.resource_type == "warehouse_capacity_demo",
                    AuditLog.resource_id == str(warehouse.id),
                )
            )
            if audit_exists is None:
                session.add(
                    AuditLog(
                        user_id=actor.id,
                        company_id=COMPANY_ID,
                        branch_id=warehouse.branch_id,
                        action="SEED_DEMO",
                        resource_type="warehouse_capacity_demo",
                        resource_id=str(warehouse.id),
                        after_state={
                            "warehouse_code": scenario.code,
                            "profile": scenario.profile,
                            "structures": [item.code for item in structures.values()],
                            "locations": list(locations),
                            "movement_id": str(movement["id"]),
                        },
                        status="success",
                        metadata_={"source": "seed_capacity_demo", "version": 1},
                    )
                )
            if item_created:
                session.add(
                    AuditLog(
                        user_id=actor.id,
                        company_id=COMPANY_ID,
                        action="CREATE",
                        resource_type="inventory_items",
                        resource_id=str(item_id),
                        metadata_={"source": "seed_capacity_demo"},
                    )
                )
            if packaging_created:
                session.add(
                    AuditLog(
                        user_id=actor.id,
                        company_id=COMPANY_ID,
                        action="CREATE",
                        resource_type="inventory_packaging_definitions",
                        resource_id=str(packaging_id),
                        metadata_={"source": "seed_capacity_demo"},
                    )
                )
            if movement_existed is None:
                session.add(
                    AuditLog(
                        user_id=actor.id,
                        company_id=COMPANY_ID,
                        branch_id=warehouse.branch_id,
                        action="CONFIRM",
                        resource_type="inventory_movements",
                        resource_id=str(movement["id"]),
                        after_state={"movement_type": "receipt", "line_count": 1},
                        metadata_={"source": "seed_capacity_demo"},
                    )
                )

    print("Demostración de capacidad lista: 3 almacenes, 4 estructuras y 3 recepciones.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
