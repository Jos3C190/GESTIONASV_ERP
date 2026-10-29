import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL_SYNC'])
assert url.database == 'erp_db'
with create_engine(url).connect() as c:
    c.exec_driver_sql('SET TRANSACTION READ ONLY')
    row = c.execute(text('''
      SELECT p.id, p.code, p.status, p.currency AS receipt_currency,
             p.inventory_movement_id, p.subtotal, p.total,
             o.code AS order_code, o.status AS order_status, o.currency AS order_currency,
             q.code AS quotation_code, q.currency AS quotation_currency,
             v.currency AS valuation_currency, v.opened_at
      FROM purchases p
      JOIN purchase_orders o ON o.id = p.purchase_order_id AND o.company_id = p.company_id
      JOIN purchase_quotations q ON q.id = o.purchase_quotation_id AND q.company_id = p.company_id
      LEFT JOIN inventory_valuation_settings v ON v.company_id = p.company_id
      WHERE p.id = :receipt AND p.company_id = :company
    '''), {'receipt': '3efec936-fd3f-46d9-9e41-a09181fe9425',
           'company': '0a7303f6-64a5-428c-a829-c2b09966fefd'}).mappings().one()
    print('CURRENCY_DIAGNOSTIC', json.dumps(dict(row), default=str))
    print('TRANSACTION_READ_ONLY', c.exec_driver_sql('SHOW transaction_read_only').scalar())
