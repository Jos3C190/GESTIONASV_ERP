import asyncio
import json
from sqlalchemy import text
from app.infrastructure.db.session import async_engine


async def main():
    async with async_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text('SET TRANSACTION READ ONLY'))
            queries = {
                'revision': 'SELECT version_num FROM alembic_version',
                'purchase25': "SELECT code,status,inventory_workflow,subtotal,discount,total,inventory_movement_id FROM purchases WHERE id='e20cd14f-a90b-4b1d-b2cc-6e565b37b006'",
                'retaceo19': "SELECT code,status,total_fob,total_expenses,total_cost,applied_at FROM retaceos WHERE id='97fd48cf-39de-498c-bd37-0b2c75cba3ae'",
                'operator': "SELECT u.username,u.is_active,u.is_superuser,c.warehouse_restricted,c.access_all_branches,w.code warehouse_code,r.name role FROM users u JOIN user_companies c ON c.user_id=u.id JOIN user_warehouse_access a ON a.user_id=u.id AND a.company_id=c.company_id JOIN warehouses w ON w.id=a.warehouse_id JOIN user_roles ur ON ur.user_id=u.id AND ur.company_id=c.company_id JOIN roles r ON r.id=ur.role_id WHERE u.id='919acf00-6918-4963-a73d-45ac9c7cd801'",
                'operator_permissions': "SELECT DISTINCT p.code FROM user_roles ur JOIN role_permissions rp ON rp.role_id=ur.role_id JOIN permissions p ON p.id=rp.permission_id WHERE ur.user_id='919acf00-6918-4963-a73d-45ac9c7cd801' ORDER BY p.code",
                'sugar_balance': "SELECT pr.sku,a.quantity_base,a.inventory_value,a.average_unit_cost FROM inventory_cost_averages a JOIN inventory_items i ON i.id=a.inventory_item_id AND i.company_id=a.company_id JOIN products pr ON pr.id_product=i.product_id AND pr.company_id=i.company_id WHERE pr.sku='PRD-AZU-004' AND a.company_id='0a7303f6-64a5-428c-a829-c2b09966fefd'",
                'sugar_recent_history': "SELECT e.sequence,e.kind,e.quantity_base,e.inventory_delta,e.balance_quantity,e.source_reference FROM inventory_valuation_entries e JOIN inventory_items i ON i.id=e.inventory_item_id AND i.company_id=e.company_id JOIN products pr ON pr.id_product=i.product_id AND pr.company_id=i.company_id WHERE pr.sku='PRD-AZU-004' AND e.company_id='0a7303f6-64a5-428c-a829-c2b09966fefd' ORDER BY e.sequence DESC LIMIT 3",
            }
            for name, query in queries.items():
                rows = (await connection.execute(text(query))).mappings().all()
                print(json.dumps({name: [dict(row) for row in rows]}, default=str, ensure_ascii=False))
    await async_engine.dispose()


asyncio.run(main())
