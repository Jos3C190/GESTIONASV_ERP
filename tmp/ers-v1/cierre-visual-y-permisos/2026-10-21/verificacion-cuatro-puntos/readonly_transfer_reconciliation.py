from __future__ import annotations
import os
from sqlalchemy import select, func, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryItemModel, InventoryHandlingUnitModel as HU
from app.infrastructure.models.inventory_transfer import InventoryTransferModel as Transfer, InventoryTransferDetailModel as Detail
from app.infrastructure.models.inventory_valuation import InventoryCostAverageModel as Average
from app.infrastructure.models.organization import Warehouse, Location

expected = "erp_db_ers_final4p_20261020"
sync_url = os.environ["DATABASE_URL_SYNC"]
source_url = make_url(sync_url)
if source_url.database != expected:
    raise SystemExit(f"Refusing primary DSN {source_url.database!r}; expected isolated clone.")
engine = create_engine(sync_url)
def snapshot(db_name: str, include_transfer: bool) -> None:
    url = source_url.set(database=db_name)
    read_engine = create_engine(url)
    with read_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        with Session(bind=conn) as session:
            print(f"\nDATABASE={db_name}")
            products = session.execute(
                select(ProductModel.sku, ProductModel.name, InventoryItemModel.id,
                       Average.quantity_base, Average.inventory_value, Average.average_unit_cost,
                       Average.updated_at)
                .join(InventoryItemModel, InventoryItemModel.product_id == ProductModel.id_product)
                .outerjoin(Average, (Average.company_id == InventoryItemModel.company_id) &
                           (Average.inventory_item_id == InventoryItemModel.id))
                .where(ProductModel.sku == "PRD-EMP-009")
            ).all()
            for row in products:
                print("PRODUCT_AVERAGE", *row, sep="|")
            hus = session.execute(
                select(HU.code, HU.quantity_base, HU.stock_status, Warehouse.code,
                       Location.code, HU.closed_at)
                .join(InventoryItemModel, InventoryItemModel.id == HU.inventory_item_id)
                .join(ProductModel, ProductModel.id_product == InventoryItemModel.product_id)
                .join(Warehouse, Warehouse.id == HU.warehouse_id)
                .join(Location, Location.id == HU.location_id)
                .where(ProductModel.sku == "PRD-EMP-009")
                .order_by(HU.created_at, HU.code)
            ).all()
            for row in hus:
                print("PRODUCT_HU", *row, sep="|")
            protected = {"ERS-REVIEW-DD6BBF85", "ERS-INC-EE8FE228", "ERS-LATE-B1B55D6D", "ERS-UI-F767BABC"}
            rows = session.execute(
                select(ProductModel.sku, func.coalesce(func.sum(HU.quantity_base), 0),
                       func.count(HU.id))
                .join(InventoryItemModel, InventoryItemModel.product_id == ProductModel.id_product)
                .join(HU, HU.inventory_item_id == InventoryItemModel.id)
                .where(ProductModel.sku.in_(protected), HU.closed_at.is_(None))
                .group_by(ProductModel.sku)
                .order_by(ProductModel.sku)
            ).all()
            for row in rows:
                print("PROTECTED_HU", *row, sep="|")
            if include_transfer:
                t = session.scalar(select(Transfer).where(Transfer.code == "TR-20261021-60344005"))
                if t:
                    print("TRANSFER", t.id, t.code, t.status, t.origin_warehouse_id,
                          t.destination_warehouse_id, t.vehicle_id, t.dispatched_at, t.received_at,
                          t.notes, sep="|")
                    for d in session.scalars(select(Detail).where(
                        Detail.company_id == t.company_id, Detail.transfer_id == t.id
                    ).order_by(Detail.line_number)):
                        print("TRANSFER_DETAIL", d.id, d.line_number, d.inventory_item_id,
                              d.source_handling_unit_id, d.transit_handling_unit_id,
                              d.quantity_planned, d.quantity_dispatched, d.quantity_received,
                              d.quantity_returned, d.quantity_adjusted_out, sep="|")
    read_engine.dispose()
snapshot(expected, True)
snapshot("erp_db", False)
engine.dispose()
