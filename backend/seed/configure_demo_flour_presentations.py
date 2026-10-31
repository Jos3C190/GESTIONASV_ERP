"""Configure the two explicitly requested fictional flour purchase conversions.

Dry run by default; --apply commits master data plus required audit entries.
This maintenance command never receives purchases or posts inventory movements.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from decimal import Decimal

import app.infrastructure.models  # noqa: F401 -- register model relationships
from app.api.v1.routers.inventory import _packaging_out
from app.api.v1.schemas.inventory import PackagingCreate
from app.application.audit.audit_service import AuditService
from app.application.inventory.use_cases import InventoryUseCases
from app.infrastructure.db.session import async_engine, async_session_factory
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.purchase_inventory_gateway import (
    SqlAlchemyPurchaseInventoryGateway,
)
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text

COMPANY_ID = uuid.UUID("0a7303f6-64a5-428c-a829-c2b09966fefd")
RECEIPT_ID = uuid.UUID("b803ed0c-bfd7-400a-b291-918b3628f45c")
DEFINITIONS = (
    (3, "PRD-HAR-003", "KG-HAR-003", "Kilogramo integral · caja base de 25 kg", "0.040000"),
    (1, "PRD-HAR-001", "KG-HAR-001", "Kilogramo suave · caja base de 50 lb (demo)", "0.044092"),
)
STOCK_TABLES = (
    "inventory_items",
    "inventory_balances",
    "inventory_handling_units",
    "inventory_movements",
    "inventory_movement_lines",
    "inventory_cost_averages",
    "inventory_valuation_entries",
    "inventory_lots",
    "inventory_lot_details",
    "purchases",
    "purchase_details",
    "purchase_orders",
    "purchase_order_details",
)


async def stock_fingerprint(session) -> dict[str, str]:
    """Snapshot complete company rows, including the protected products."""
    result = {}
    for table in STOCK_TABLES:
        # Only fixed table names from the allowlist above enter SQL text.
        result[table] = await session.scalar(
            text(
                f"SELECT md5(COALESCE(string_agg(to_jsonb(t)::text, '' "
                f"ORDER BY to_jsonb(t)::text), '')) FROM {table} t WHERE company_id = :company"
            ),
            {"company": COMPANY_ID},
        )
    return result


async def configure_product(session, repository, use_cases, audit, kilogram_id, spec) -> None:
    product_id, sku, code, name, factor = spec
    product = await session.scalar(
        select(ProductModel).where(
            ProductModel.company_id == COMPANY_ID,
            ProductModel.id_product == product_id,
            ProductModel.sku == sku,
        )
    )
    if product is None:
        raise RuntimeError(f"Expected demonstration product {sku} not found.")
    item = await repository.get_item_by_target(
        company_id=COMPANY_ID,
        product_id=product_id,
        variant_id=None,
    )
    if item is None or not item.is_active:
        raise RuntimeError(f"Active inventory configuration missing for {sku}.")
    base_code = await session.scalar(
        select(UnitModel.code).where(
            UnitModel.id_unit == item.base_unit_id,
        )
    )
    if base_code != "BOX":
        raise RuntimeError(f"Base unit changed for {sku}; review rather than overwrite.")
    existing = [
        p
        for p in await repository.list_packaging(COMPANY_ID, item.id)
        if p.packaging_unit_id == kilogram_id and p.is_current and p.is_active
    ]
    body = PackagingCreate(
        code=code,
        name=name,
        packaging_type="loose_other",
        packaging_unit_id=kilogram_id,
        base_quantity=Decimal(factor),
        measures={"gross_weight_kg": "1.000000", "volume_m3": "0.002000"},
        stackable=False,
    )
    if existing:
        if (
            len(existing) != 1
            or existing[0].code != code
            or (
                existing[0].base_quantity != body.base_quantity
                or existing[0].measures != body.measures.to_domain()
            )
        ):
            raise RuntimeError(f"An existing kilogram presentation conflicts for {sku}.")
        definition = existing[0]
        action = "UNCHANGED"
    else:
        definition = await use_cases.create_packaging(
            company_id=COMPANY_ID,
            item_id=item.id,
            code=body.code,
            name=body.name,
            packaging_type=body.packaging_type,
            packaging_unit_id=body.packaging_unit_id,
            base_quantity=body.base_quantity,
            measures=body.measures.to_domain(),
            stackable=body.stackable,
            max_stack=body.max_stack,
        )
        await audit.record(
            action="CREATE",
            company_id=COMPANY_ID,
            resource_type="inventory_packaging_definitions",
            resource_id=str(definition.id),
            after_state=jsonable_encoder(_packaging_out(definition)),
            metadata={
                "source": "user_authorized_demo_maintenance",
                "receipt": str(RECEIPT_ID),
                "assumption": "One historical BOX represents the sack weight in the product name.",
                "precision": "Six decimals; 50 lb factor rounded to 0.044092 BOX per kg.",
                "physical_measures": "Fictional: each purchased kg occupies 0.002 cubic metres.",
            },
            required=True,
        )
        action = "CREATE"
    quantity, packaging_id = await SqlAlchemyPurchaseInventoryGateway(
        session
    )._quantity_in_base_unit(
        company_id=COMPANY_ID,
        product_id=product_id,
        received_unit_id=kilogram_id,
        item=item,
        accepted_quantity=Decimal("100"),
    )
    print(
        json.dumps(
            {
                "sku": sku,
                "action": action,
                "presentation_id": str(packaging_id),
                "factor_boxes_per_kg": str(definition.base_quantity),
                "accepted_kg": "100",
                "quantity_base_boxes": str(quantity),
            }
        )
    )


async def main(apply: bool) -> None:
    if async_engine.url.database != "erp_db":
        raise RuntimeError("This command is scoped to the local fictional demonstration database.")
    async with async_session_factory() as session:
        async with session.begin():
            receipt = await session.scalar(
                select(PurchaseModel)
                .where(
                    PurchaseModel.company_id == COMPANY_ID,
                    PurchaseModel.id == RECEIPT_ID,
                )
                .with_for_update()
            )
            if receipt is None or receipt.code != "COM-00021":
                raise RuntimeError("Expected demonstration receipt not found.")
            before = await stock_fingerprint(session)
            repository = SqlAlchemyInventoryRepository(session)
            use_cases = InventoryUseCases(repository)
            audit = AuditService(SqlAlchemyAuditRepository(session))
            kilogram_id = await session.scalar(
                select(UnitModel.id_unit).where(
                    UnitModel.code == "KILOGRAM",
                    UnitModel.owner_company_id.is_(None),
                    UnitModel.is_active.is_(True),
                )
            )
            if kilogram_id is None:
                raise RuntimeError("The standard kilogram unit is unavailable.")
            for spec in DEFINITIONS:
                await configure_product(session, repository, use_cases, audit, kilogram_id, spec)
            await session.flush()
            after = await stock_fingerprint(session)
            if before != after:
                raise RuntimeError("Stock or purchase history changed unexpectedly; rolling back.")
            print(json.dumps({"stock_and_purchases_unchanged": True, "fingerprints": after}))
            if not apply:
                await session.rollback()
        print("COMMITTED_PRESENTATIONS_AND_AUDIT_ONLY" if apply else "DRY_RUN_ROLLED_BACK")
    await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
