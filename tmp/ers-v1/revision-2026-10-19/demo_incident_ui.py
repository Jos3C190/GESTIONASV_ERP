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
state = json.loads(state_path.read_text()) if state_path.exists() else {'run': 'ERS-INC-' + uuid.uuid4().hex[:8].upper(), 'steps': []}
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

companies = call('GET', '/companies/accessible')
selected = next((c for c in companies if 'Lorena' in c.get('commercial_name', '') or 'Lorena' in c.get('name', '')), companies[0])
client.headers['X-Company-ID'] = selected['id']
state['company_id'] = selected['id']
warehouses = rows(call('GET', '/warehouses?size=100'))
state['warehouses'] = [{k: w.get(k) for k in ['id','name','is_central','is_transit','branch_id']} for w in warehouses]
usable = []
for warehouse in warehouses:
    if warehouse.get('is_transit') or not warehouse.get('is_active', True):
        continue
    locations = rows(call('GET', '/locations?warehouse_id=' + warehouse['id']))
    location = next((l for l in locations if l.get('storage_eligible') and l.get('is_active') and l.get('location_type') != 'virtual' and l.get('lifecycle_status') == 'active'), None)
    if location:
        usable.append({'warehouse_id': warehouse['id'], 'branch_id': warehouse['branch_id'], 'name': warehouse['name'], 'location_id': location['id'], 'central': warehouse['is_central']})
state['usable'] = usable
state['valuation_active'] = bool(call('GET', '/inventory/valuation')['setting'])
state['categories'] = rows(call('GET', '/catalog/categories?size=100'))
state['units'] = rows(call('GET', '/catalog/units?size=100'))
save()
print(json.dumps({k: state[k] for k in ['run','company_id','usable','valuation_active']}, ensure_ascii=False))

if '--execute' not in sys.argv:
    sys.exit(0)

today = datetime.now(ZoneInfo('America/El_Salvador')).date().isoformat()
run = state['run']
central = next(w for w in usable if w['central'])
destination = next(w for w in usable if not w['central'] and 'Tránsito' in w['name'])
def step(name, operation):
    if name not in state:
        state[name] = operation()
        save()
        print('Completed: ' + name, flush=True)
    return state[name]
def balance(name, expected_quantity, expected_value):
    if name in state:
        return
    overview = call('GET', '/inventory/valuation')
    record = next(b for b in overview['balances'] if b['inventory_item_id'] == state['item']['id'])
    assert Decimal(record['quantity_base']) == Decimal(expected_quantity), (name, record)
    assert abs(Decimal(record['inventory_value']) - Decimal(expected_value)) <= Decimal('0.000003'), (name, record)
    state[name] = record
    save()
    print(f'Balance {name}: {record["quantity_base"]} / USD {record["inventory_value"]}', flush=True)

unit_id = next(u['id_unit'] for u in state['units'] if u.get('code') == 'UNIT')
product = step('product', lambda: call('POST', '/catalog/products', {
    'id_category': state['categories'][0]['id_category'], 'sku': run, 'internal_code': run,
    'name': 'Artículo demostración integral ' + run, 'purchase_unit': unit_id,
    'sale_unit': unit_id, 'lifecycle_status': 'active', 'can_purchase': True, 'can_sell': True}))
item = step('item', lambda: call('POST', '/inventory/items', {'product_id': product['id_product'], 'base_unit_id': unit_id}))
def adjustment(name, line, warehouse):
    doc = step(name, lambda: call('POST', '/inventory/adjustments', {
        'idempotency_key': run + ':' + name, 'warehouse_id': warehouse['warehouse_id'],
        'operational_date': today, 'accounting_date': today,
        'reason': 'Demostración académica controlada ' + run, 'document_reference': run + '-' + name,
        'lines': [line]}))
    if name + '_evidence' not in state:
        content = ('Comprobante ficticio de demostracion. ' + run + ' ' + name + '\nCantidad y costo aprobados solo para prueba.\n').encode()
        ticket = call('POST', f'/inventory/adjustments/{doc["id"]}/documents', {
            'file_name': run + '-' + name + '.txt', 'content_type': 'text/plain',
            'size_bytes': len(content), 'checksum_sha256': hashlib.sha256(content).hexdigest()})
        parsed = urlsplit(ticket['upload_url'])
        target = ticket['upload_url'].replace(parsed.netloc, 'rustfs:9000', 1)
        uploaded = httpx.put(target, headers={**ticket['required_headers'], 'Host': parsed.netloc}, content=content, timeout=90)
        assert uploaded.status_code < 300, f'Upload HTTP {uploaded.status_code}'
        step(name + '_evidence', lambda: call('POST', f'/inventory/adjustments/{doc["id"]}/documents/{ticket["document_id"]}/complete'))
    approved = step(name + '_approved', lambda: call('POST', f'/inventory/adjustments/{doc["id"]}/approve', {'expected_version': doc['version']}))
    return step(name + '_applied', lambda: call('POST', f'/inventory/adjustments/{doc["id"]}/apply', {'idempotency_key': run + ':' + name + ':apply'}))

positive = adjustment('opening_adjustment', {'inventory_item_id': item['id'], 'location_id': central['location_id'],
    'direction': 'increase', 'quantity_base': '5', 'stock_status': 'quarantine',
    'documented_total_cost': '50', 'actual_gross_weight_kg': '0.5', 'actual_volume_m3': '0.005'}, central)
balance('balance_opening', '5', '50')

def units(warehouse):
    return [h for h in rows(call('GET', '/inventory/warehouses/' + warehouse['warehouse_id'] + '/handling-units')) if h['inventory_item_id'] == item['id']]
def ready(name, hu_id, warehouse):
    if name + '_ready' in state:
        return state[name + '_ready']
    step(name + '_measured', lambda: call('PATCH', f'/inventory/handling-units/{hu_id}/measurements', {
        'source': 'manual', 'measures': {'gross_weight_kg': '0.1', 'volume_m3': '0.001'}}))
    hu = next(h for h in units(warehouse) if h['id'] == hu_id)
    if hu.get('receipt_lot_id') or hu.get('inventory_lot_id'):
        preview = call('GET', '/inventory/labels/preview?handling_unit_id=' + hu_id)
        printed = step(name + '_printed', lambda: call('POST', '/inventory/labels/prints', {
            'handling_unit_id': hu_id, 'idempotency_key': run + ':' + name + ':print',
            'quantity_printed': 1, 'print_date': today, 'reason': 'reprint' if preview['has_initial_print'] else 'initial'}))
        step(name + '_label_confirmed', lambda: call('POST', '/inventory/labels/confirmations', {
            'handling_unit_id': hu_id, 'handling_unit_code': hu['code'], 'label_print_id': printed['id'],
            'idempotency_key': run + ':' + name + ':label'}))
    if hu['stock_status'] == 'quarantine':
        step(name + '_released', lambda: call('POST', '/inventory/movements/confirm', {
            'idempotency_key': run + ':' + name + ':release', 'movement_type': 'putaway',
            'source_reference': run + ' liberar ' + name,
            'lines': [{'inventory_item_id': item['id'], 'handling_unit_id': hu_id,
                       'from_location_id': hu['location_id'], 'to_location_id': warehouse['location_id'],
                       'from_stock_status': 'quarantine', 'to_stock_status': 'available', 'quantity_base': hu['quantity_base']}]}))
    result = next(h for h in units(warehouse) if h['id'] == hu_id)
    state[name + '_ready'] = result
    save()
    return result

hu = step('source_hu', lambda: units(central)[0])
ready('source_unit', hu['id'], central)
original = json.loads(Path('/tmp/ers_review_demo_state.json').read_text())
vehicle = original['vehicle']
transfer = step('transfer', lambda: call('POST', '/inventory/transfers', {
    'idempotency_key': run + ':transfer', 'origin_warehouse_id': central['warehouse_id'],
    'destination_warehouse_id': destination['warehouse_id'], 'vehicle_id': vehicle['id'], 'notes': run + ' prueba visual de incidencia',
    'lines': [{'handling_unit_id': hu['id'], 'quantity_base': '3', 'demand_allocations': [],
               'excess_reason': 'Envío manual de demostración de incidencia, separado del caso principal'}]}))
step('dispatched', lambda: call('POST', f'/inventory/transfers/{transfer["id"]}/dispatch', {
    'idempotency_key': run + ':dispatch', 'vehicle_id': vehicle['id']}))
partial = step('received_two', lambda: call('POST', f'/inventory/transfers/{transfer["id"]}/receive', {
    'idempotency_key': run + ':receive2', 'lines': [{'transfer_detail_id': transfer['lines'][0]['id'],
      'destination_location_id': destination['location_id'], 'quantity_base': '2'}]}))
assert partial['status'] == 'in_transit'
assert Decimal(partial['lines'][0]['quantity_in_transit']) == Decimal('1')
state['current_transfer'] = call('GET', f'/inventory/transfers/{transfer["id"]}')
save()
print(json.dumps({'run': run, 'transfer_code': transfer['code'], 'transfer_id': transfer['id'], 'in_transit': '1', 'target_warehouse': destination['name']}, ensure_ascii=False))
print('INCIDENT_UI_FIXTURE_READY', flush=True)