import asyncio
import json
from sqlalchemy import text
from app.infrastructure.db.session import async_engine


async def main():
    async with async_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text('SET TRANSACTION READ ONLY'))
            query = """SELECT po.code order_code, po.purchase_quotation_id,
                od.id order_detail_id, od.purchase_quotation_detail_id,
                od.quantity order_quantity, od.unit_price order_unit_price,
                od.subtotal order_subtotal, od.discount order_discount,
                od.tax_amount order_tax, od.total order_total,
                q.code quotation_code, q.status quotation_status,
                qd.quantity quotation_quantity, qd.offered_quantity,
                qd.unit_price quotation_unit_price, qd.discount quotation_discount,
                qd.subtotal quotation_subtotal, qd.tax_amount quotation_tax,
                qd.total quotation_total
                FROM purchases p
                JOIN purchase_details pd ON pd.purchase_id=p.id AND pd.company_id=p.company_id
                JOIN purchase_orders po ON po.id=p.purchase_order_id AND po.company_id=p.company_id
                JOIN purchase_order_details od ON od.id=pd.purchase_order_detail_id AND od.company_id=p.company_id
                JOIN purchase_quotations q ON q.id=po.purchase_quotation_id AND q.company_id=p.company_id
                JOIN purchase_quotation_details qd ON qd.id=od.purchase_quotation_detail_id AND qd.company_id=p.company_id
                WHERE p.id='16fe2c34-9beb-4274-a4bc-c3d234a34a52'
                AND p.company_id='0a7303f6-64a5-428c-a829-c2b09966fefd'"""
            rows = (await connection.execute(text(query))).mappings().all()
            print(json.dumps([dict(row) for row in rows], default=str, ensure_ascii=False))
    await async_engine.dispose()


asyncio.run(main())
