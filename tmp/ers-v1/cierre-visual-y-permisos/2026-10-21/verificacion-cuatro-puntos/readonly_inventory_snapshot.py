"""Read-only lookup helper; refuses any database other than isolated ERS-FINAL-4P."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel as HU, InventoryItemModel
from app.infrastructure.models.organization import Warehouse

EXPECTED = "erp_db_ers_final4p_20261020"
url = os.environ["DATABASE_URL_SYNC"]
actual = urlparse(url).path.rsplit("/", 1)[-1]
if actual != EXPECTED:
    raise SystemExit(f"Refusing database {actual!r}; expected isolated clone.")

protected = {"ERS-REVIEW-DD6BBF85", "ERS-INC-EE8FE228", "ERS-LATE-B1B55D6D", "ERS-UI-F767BABC"}
engine = create_engine(url)
with Session(engine) as session:
    rows = session.execute(
        select(ProductModel.sku, ProductModel.name, Warehouse.code,
               func.sum(HU.quantity_base), func.count(HU.id))
        .join(InventoryItemModel, InventoryItemModel.product_id == ProductModel.id_product)
        .join(HU, HU.inventory_item_id == InventoryItemModel.id)
        .join(Warehouse, Warehouse.id == HU.warehouse_id)
        .where(
            HU.closed_at.is_(None), HU.stock_status == "available",
            ProductModel.sku.notin_(protected),
        )
        .group_by(ProductModel.sku, ProductModel.name, Warehouse.code)
        .having(func.sum(HU.quantity_base) >= 10)
        .order_by(Warehouse.code, ProductModel.sku)
        .limit(50)
    ).all()
    print(f"database={actual}")
    for row in rows:
        print("\t".join(str(value) for value in row))
engine.dispose()
