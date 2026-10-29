import os
from sqlalchemy import create_engine, text

source = os.environ["DATABASE_URL_SYNC"]
base = source.rsplit("/", 1)[0]
databases = ["erp_db", "erp_db_b08_rehearsal_20261019"]
tables = [
    "companies", "branches", "warehouses", "locations", "inventory_items",
    "inventory_lots", "inventory_lot_details", "inventory_packaging_definitions",
    "inventory_handling_units", "inventory_balances", "inventory_movements",
    "inventory_movement_lines", "inventory_cost_averages", "inventory_valuation_entries",
    "inventory_valuation_settings", "inventory_transfer_details", "inventory_transfers",
    "sales_customers", "sales_quotations", "sales_quotation_lines", "sales", "sales_lines",
    "sales_deliveries", "sales_delivery_lines", "sales_delivery_allocations", "sales_returns",
    "sales_return_lines", "sales_return_events", "sales_return_commands", "sales_return_documents",
]
print("database;table;rows;md5")
for database in databases:
    engine = create_engine(f"{base}/{database}")
    try:
        with engine.connect() as connection:
            available = set(connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
            for table in tables:
                if table not in available:
                    print(f"{database};{table};MISSING;")
                    continue
                query = text(f'''SELECT count(*), md5(coalesce(string_agg(to_jsonb(t)::text, chr(10) ORDER BY to_jsonb(t)::text), '')) FROM "{table}" AS t''')
                count, digest = connection.execute(query).one()
                print(f"{database};{table};{count};{digest}")
    finally:
        engine.dispose()
