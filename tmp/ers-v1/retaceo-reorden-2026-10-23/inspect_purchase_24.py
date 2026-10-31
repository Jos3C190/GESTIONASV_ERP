import asyncio
import json

from sqlalchemy import text

from app.infrastructure.db.session import async_engine


async def main():
    async with async_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            queries = {
                "schema_revision": "SELECT version_num FROM alembic_version",
                "purchase": """SELECT p.id, p.company_id, p.code, p.status,
                    p.purchase_order_id, p.warehouse_id, p.currency,
                    p.valuation_conversion, p.subtotal, p.discount, p.tax,
                    p.total, p.inventory_movement_id, p.purchase_date
                    FROM purchases p WHERE p.code = 'COM-00024'""",
                "purchase_lines": """SELECT d.id, d.purchase_id, d.product_id,
                    pr.name, pr.sku, d.unit_id, d.quantity_ordered,
                    d.quantity_received, d.quantity_accepted, d.unit_price,
                    d.discount, d.subtotal, d.tax_rate, d.tax_amount, d.total
                    FROM purchase_details d JOIN purchases p ON p.id=d.purchase_id
                    JOIN products pr ON pr.id_product=d.product_id AND pr.company_id=d.company_id
                    WHERE p.code='COM-00024' ORDER BY d.created_at, d.id""",
                "retaceos": """SELECT r.id, r.company_id, r.code, r.status,
                    r.currency, r.total_fob, r.total_freight, r.total_expenses,
                    r.total_dai, r.import_vat, r.total_cost, r.applied_at
                    FROM retaceos r JOIN purchases p ON p.id=r.purchase_id
                    WHERE p.code='COM-00024' ORDER BY r.created_at""",
                "retaceo_lines": """SELECT rd.* FROM retaceo_details rd
                    JOIN retaceos r ON r.id=rd.retaceo_id
                    JOIN purchases p ON p.id=r.purchase_id
                    WHERE p.code='COM-00024' ORDER BY rd.created_at, rd.id""",
                "retaceo_costs": """SELECT c.id, c.retaceo_id, c.classification,
                    c.title, c.amount, c.source_purchase_order_expense_id
                    FROM retaceo_costs c JOIN retaceos r ON r.id=c.retaceo_id
                    JOIN purchases p ON p.id=r.purchase_id
                    WHERE p.code='COM-00024' ORDER BY c.created_at""",
            }
            for label, query in queries.items():
                result = (await connection.execute(text(query))).mappings().all()
                print(json.dumps({label: [dict(row) for row in result]}, default=str, ensure_ascii=False))
    await async_engine.dispose()


asyncio.run(main())

