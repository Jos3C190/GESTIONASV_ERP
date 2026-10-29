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

state_path = Path('/tmp/ers_retaceo_demo_state.json')
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
phase = sys.argv[1]
retaceo = call('GET', '/retaceos/dc211308-7a44-472c-8da4-9cd67c7cbc47')
ledger = call('GET', '/inventory/valuation/items/' + state['item']['id'] + '/ledger')
reconciliation = call('GET', '/inventory/kardex/reconciliation?page_size=200')
record = next(row for row in reconciliation['items'] if row['inventory_item_id'] == state['item']['id'])
expected = {'calculated': ('4','40'), 'verified': ('4','40'), 'applied': ('4','48'), 'closed': ('4','48'), 'returned': ('5','60'), 'released': ('5','60')}[phase]
assert Decimal(record['physical_quantity']) == Decimal(record['valued_quantity']) == Decimal(expected[0]), record
assert Decimal(record['inventory_value']) == Decimal(expected[1]), record
assert Decimal(record['quantity_difference']) == 0
if phase in {'applied','closed','returned','released'}:
    events = [row for row in ledger if row['kind'] == 'cost_adjustment']
    assert len(events) == 1
    cost = events[0]
    assert Decimal(cost['quantity_base']) == 0
    assert Decimal(cost['source_value']) == 20
    assert Decimal(cost['inventory_delta']) == 8
    assert Decimal(cost['source_value']) - Decimal(cost['inventory_delta']) == 12
    assert retaceo['applied_at']
else:
    assert retaceo['status'] == phase and not retaceo['applied_at']
    assert not any(row['kind'] == 'cost_adjustment' for row in ledger)
if phase in {'returned','released'}:
    events = [row for row in ledger if row['kind'] == 'customer_return']
    assert len(events) == 1 and Decimal(events[0]['inventory_delta']) == 12
    assert events[0]['original_entry_id']
    hus = rows(call('GET', '/inventory/warehouses/' + state['usable'][0]['warehouse_id'] + '/handling-units'))
    returned_hu = next(row for row in hus if row['inventory_item_id'] == state['item']['id'] and row['code'].startswith('HU-RET-'))
    assert returned_hu['stock_status'] == ('available' if phase == 'released' else 'quarantine')
    assert Decimal(returned_hu['quantity_base']) == 1
    state['ui_return_released_hu' if phase == 'released' else 'ui_return_hu'] = returned_hu
main = json.loads(Path('/tmp/ers_review_demo_state.json').read_text())
original = next(row for row in reconciliation['items'] if row['inventory_item_id'] == main['item']['id'])
assert Decimal(original['physical_quantity']) == 12 and Decimal(original['inventory_value']) == 160
state['ui_retaceo_' + phase] = retaceo
state['reconciliation_' + phase] = record
state['ledger_' + phase] = ledger
save()
print(json.dumps({'phase':phase,'retaceo':retaceo['code'],'status':retaceo['status'],'quantity':record['physical_quantity'],'value':record['inventory_value'],'main_quantity':original['physical_quantity'],'main_value':original['inventory_value']},ensure_ascii=False))
print('LATE_RETACEO_UI_' + phase.upper() + '_VERIFIED')
if '--cancelled-confirmation' in sys.argv:
    delivery = call('GET', '/sales/deliveries/' + state['confirmation_delivery']['id'])
    sale = call('GET', '/sales/' + state['confirmation_sale']['id'])
    assert delivery['status'] == 'cancelled'
    assert sale['status'] == 'cancelled'
    assert all(allocation['movement_id'] is None for line in delivery['lines'] for allocation in line['allocations'])
    state['ui_confirmation_cancelled_delivery'] = delivery
    state['ui_confirmation_cancelled_sale'] = sale
    save()
    print('DELIVERY_CONFIRMATION_CANCELLED_WITHOUT_STOCK_EFFECT_VERIFIED')
