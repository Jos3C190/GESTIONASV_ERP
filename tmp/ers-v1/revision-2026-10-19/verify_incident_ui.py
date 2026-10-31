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

state_path = Path('/tmp/ers_incident_demo_state.json')
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
transfer = call('GET', '/inventory/transfers/' + state['transfer']['id'])
assert transfer['status'] == 'closed_with_adjustment', transfer['status']
line = transfer['lines'][0]
assert Decimal(line['quantity_received']) == 2
assert Decimal(line['quantity_adjusted_out']) == 1
assert Decimal(line['quantity_in_transit']) == 0
adjustment = call('GET', '/inventory/adjustments/82c7268b-ae92-4717-832c-19c41826849c')
assert adjustment['status'] == 'applied'
assert adjustment['documents'][0]['upload_completed']
reconciliation = call('GET', '/inventory/kardex/reconciliation?page_size=200')
record = next(row for row in reconciliation['items'] if row['inventory_item_id'] == state['item']['id'])
assert Decimal(record['physical_quantity']) == Decimal(record['valued_quantity']) == 4
assert Decimal(record['inventory_value']) == 40
assert Decimal(record['quantity_difference']) == 0
main = json.loads(Path('/tmp/ers_review_demo_state.json').read_text())
original = next(row for row in reconciliation['items'] if row['inventory_item_id'] == main['item']['id'])
assert Decimal(original['physical_quantity']) == Decimal(original['valued_quantity']) == 12
assert Decimal(original['inventory_value']) == 160
state['ui_closed_transfer'] = transfer
state['ui_loss_adjustment'] = adjustment
state['final_reconciliation'] = record
state['main_reconciliation_unchanged'] = original
returns = rows(call('GET', '/sales/' + main['sale']['id'] + '/returns'))
rejected = next(row for row in returns if row['code'] == 'DEV-20261020-8A63F2BF')
assert rejected['status'] == 'rejected'
rejected_line = rejected['lines'][0]
assert Decimal(rejected_line['quantity_rejected_base']) == 1
assert Decimal(rejected_line['quantity_accepted_base']) == 0
assert Decimal(rejected_line['quantity_pending_base']) == 0
assert len(rejected_line['events']) == 1
assert rejected_line['events'][0]['movement_id'] is None
assert rejected_line['events'][0]['valuation_entry_id'] is None
available = call('GET', '/sales/' + main['sale']['id'] + '/returnable-allocations')
assert Decimal(available[0]['quantity_returnable_base']) == 2
assert Decimal(available[0]['quantity_reserved_base']) == 0
state['ui_rejected_return'] = rejected
save()
print(json.dumps({'run': state['run'], 'transfer': transfer['code'], 'status': transfer['status'], 'received': line['quantity_received'], 'adjusted_out': line['quantity_adjusted_out'], 'in_transit': line['quantity_in_transit'], 'quantity': record['physical_quantity'], 'value': record['inventory_value'], 'main_quantity': original['physical_quantity'], 'main_value': original['inventory_value']}, ensure_ascii=False))
print('INCIDENT_UI_PERSISTENCE_AND_RECONCILIATION_PASSED')
print('RETURN_UI_REJECTION_NO_STOCK_AND_RELEASED_RESERVATION_PASSED')
