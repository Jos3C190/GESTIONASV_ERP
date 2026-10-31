"""Persisted demonstration via authenticated HTTP; credentials arrive on stdin only."""
import sys, json, uuid
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from urllib.parse import urlsplit, parse_qsl
from decimal import Decimal
import hashlib

values = {}
for line in sys.stdin.read().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"').strip("'")

client = httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=90)
auth = client.post('/auth/login', json={'login': values.get('SUPER_ADMIN_USERNAME', 'superadmin'), 'password': values['SUPER_ADMIN_PASSWORD']})
if auth.status_code != 200:
    raise SystemExit(f'Authentication unavailable: HTTP {auth.status_code}')
client.headers['Authorization'] = 'Bearer ' + auth.json()['access_token']
del values

state_path = Path('/tmp/ers_commercial_ui_state.json')
state = json.loads(state_path.read_text()) if state_path.exists() else {'run': 'ERS-REVIEW-' + uuid.uuid4().hex[:8].upper(), 'steps': []}
def save():
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
def call(method, path, data=None, key=None):
    parsed = urlsplit(path)
    params = dict(parse_qsl(parsed.query))
    if 'company_id' in state:
        params.setdefault('company_id', state['company_id'])
    response = client.request(method, parsed.path, params=params, json=data, headers={'Idempotency-Key': key} if key else {})
    if response.status_code >= 400:
        # Response bodies on operational endpoints contain business errors only.
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text[:1000]}')
    return response.json() if response.content else None
def rows(value):
    return value['items'] if isinstance(value, dict) and 'items' in value else value


client.headers['X-Company-ID'] = state['company_id']
phase=sys.argv[1]
customer=next(row for row in rows(call('GET','/sales/customers?size=100')) if row['code']==state['run'])
quote=next(row for row in rows(call('GET','/sales/quotations?size=100')) if row['customer_id']==customer['id'])
assert Decimal(quote['total'])==80 and Decimal(quote['lines'][0]['quantity'])==4
assert quote['status']==('draft' if phase=='quote' else 'confirmed')
state['ui_customer']=customer
state['ui_quote_'+phase]=quote
if quote['sale_id']:
    sale=call('GET','/sales/'+quote['sale_id'])
    state['ui_sale_'+phase]=sale
    assert Decimal(sale['total'])==80
    assert sale['status']=='confirmed'
    deliveries=rows(call('GET','/sales/'+sale['id']+'/deliveries'))
    confirmed=[row for row in deliveries if row['status']=='confirmed']
    state['ui_deliveries_'+phase]=deliveries
    if phase=='partial':
        assert sale['delivery_progress']=='partial'
        assert Decimal(sale['lines'][0]['quantity_delivered_base'])==2
        assert len(confirmed)==1
    elif phase=='complete':
        assert sale['delivery_progress']=='complete'
        assert Decimal(sale['lines'][0]['quantity_delivered_base'])==4
        assert len(confirmed)==2
reconciliation=call('GET','/inventory/kardex/reconciliation?page_size=200')
record=next(row for row in reconciliation['items'] if row['inventory_item_id']==state['item']['id'])
expected={'quote':('4','40'),'quote_confirmed':('4','40'),'sale_confirmed':('4','40'),'delivery_draft':('4','40'),'partial':('2','20'),'complete':('0','0')}[phase]
assert Decimal(record['physical_quantity'])==Decimal(record['valued_quantity'])==Decimal(expected[0]),record
assert Decimal(record['inventory_value'])==Decimal(expected[1]),record
assert Decimal(record['quantity_difference'])==0
state['ui_reconciliation_'+phase]=record
main=json.loads(Path('/tmp/ers_review_demo_state.json').read_text())
original=next(row for row in reconciliation['items'] if row['inventory_item_id']==main['item']['id'])
assert Decimal(original['physical_quantity'])==12 and Decimal(original['inventory_value'])==160
save()
print(json.dumps({'phase':phase,'sku':state['run'],'quote':quote['code'],'quantity':record['physical_quantity'],'value':record['inventory_value']},ensure_ascii=False))
print('COMMERCIAL_UI_'+phase.upper()+'_VERIFIED')
