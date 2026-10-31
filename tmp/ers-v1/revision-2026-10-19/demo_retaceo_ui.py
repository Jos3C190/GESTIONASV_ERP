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
state = json.loads(state_path.read_text()) if state_path.exists() else {'run': 'ERS-LATE-' + uuid.uuid4().hex[:8].upper(), 'steps': []}
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

request_doc = step('purchase_request', lambda: call('POST', '/purchase-requests', {
    'branch_id': destination['branch_id'], 'warehouse_id': destination['warehouse_id'],
    'justification': run + ' demanda de demostración', 'details': [{'product_id': product['id_product'], 'quantity': '10'}]}))
step('purchase_request_submitted', lambda: call('POST', f'/purchase-requests/{request_doc["id"]}/submit'))
request_doc = step('purchase_request_approved', lambda: call('POST', f'/purchase-requests/{request_doc["id"]}/approve'))
consolidated = step('consolidation', lambda: call('POST', '/purchase-consolidations', {
    'request_ids': [request_doc['id']], 'period_start': today, 'period_end': today,
    'central_warehouse_id': central['warehouse_id'], 'notes': run}))
suppliers = rows(call('GET', '/suppliers?size=100'))
supplier = next(s for s in suppliers if s.get('is_active', True) and s.get('supplier_type', 'local') == 'local')
quote = step('purchase_quotation', lambda: call('POST', f'/purchase-consolidations/{consolidated["id"]}/purchase-quotations', {
    'supplier_id': supplier.get('id_supplier', supplier.get('id')), 'currency': 'USD',
    'consolidation_line_ids': [line['id'] for line in consolidated['lines']], 'notes': run}))
step('purchase_quotation_sent', lambda: call('POST', f'/purchase-quotations/{quote["id"]}/send'))
step('purchase_quotation_response', lambda: call('PUT', f'/purchase-quotations/{quote["id"]}/response', {
    'quotation_date': datetime.now(ZoneInfo('UTC')).isoformat(), 'payment_terms': 'Demostración sin pago',
    'lines': [{'product_id': product['id_product'], 'unit_id': unit_id, 'quantity': '10',
               'available_quantity': '10', 'unit_price': '10', 'tax_rate': '0'}]}))
quote = state['purchase_quotation_response']
step('purchase_quotation_evaluated', lambda: call('POST', f'/purchase-quotations/{quote["id"]}/evaluate'))
step('purchase_award', lambda: call('POST', f'/purchase-consolidations/{consolidated["id"]}/awards', {
    'consolidation_line_id': consolidated['lines'][0]['id'], 'quotation_id': quote['id'],
    'quotation_detail_id': quote['details'][0]['id'], 'quantity': '10', 'reason': run + ' oferta seleccionada'}))
order = step('purchase_order', lambda: call('POST', f'/purchase-orders/from-consolidation/{consolidated["id"]}/{quote["id"]}', {
    'branch_id': central['branch_id'], 'warehouse_id': central['warehouse_id'],
    'expected_date': (datetime.now(ZoneInfo('UTC')) + timedelta(days=2)).isoformat(), 'notes': run}))
for action in ['submit','approve','send']:
    step('purchase_order_' + action, lambda action=action: call('POST', f'/purchase-orders/{order["id"]}/{action}'))
purchase = step('purchase', lambda: call('POST', '/purchases', {'purchase_order_id': order['id'],
    'lines': [{'purchase_order_detail_id': order['details'][0]['id'], 'quantity_received': '10'}]}))
step('purchase_received', lambda: call('POST', f'/purchases/{purchase["id"]}/receive'))
purchase = step('purchase_verified', lambda: call('POST', f'/purchases/{purchase["id"]}/verify', {
    'lines': [{'purchase_detail_id': purchase['details'][0]['id'], 'quantity_accepted': '10',
               'inventory_location_id': central['location_id']}]}))
balance('balance_purchase', '10', '100')
save()
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


purchase_hu = step('purchase_hu', lambda: next(h for h in units(central) if h.get('purchase_code') == purchase['code']))
ready('purchase_unit', purchase_hu['id'], central)
division = step('explicit_split6', lambda: call('POST', f'/inventory/handling-units/{purchase_hu["id"]}/prepare-split', {
    'idempotency_key': run + ':split6', 'split_quantity_base': '6', 'destination_location_id': central['location_id']}))
sale_hu = ready('sale_unit6', division['split_handling_unit_id'], central)
ready('remaining_unit4', division['remainder_handling_unit_id'], central)
destination = central
customer = step('customer', lambda: call('POST', '/sales/customers', {'code': run, 'name': 'Cliente ficticio ' + run}))
sales_quote = step('sales_quote', lambda: call('POST', '/sales/quotations', {
    'branch_id': destination['branch_id'], 'customer_id': customer['id'],
    'valid_until': (datetime.now(ZoneInfo('America/El_Salvador')) + timedelta(days=2)).date().isoformat(),
    'currency': 'USD', 'notes': run, 'lines': [{'product_id': product['id_product'], 'unit_id': unit_id,
    'quantity': '6', 'unit_price': '25'}]}, key=run + ':quote'))
confirmed_quote = step('sales_quote_confirmed', lambda: call('POST', f'/sales/quotations/{sales_quote["id"]}/confirm', {'expected_version': sales_quote['version']}))
sale = step('sale', lambda: call('POST', f'/sales/quotations/{sales_quote["id"]}/convert', {'expected_version': confirmed_quote['version']}, key=run + ':convert'))
sale = step('sale_confirmed', lambda: call('POST', f'/sales/{sale["id"]}/confirm', {'expected_version': sale['version']}))
balance('balance_sale_no_issue', '10', '100')
delivery = step('delivery', lambda: call('POST', f'/sales/{sale["id"]}/deliveries', {
    'notes': run, 'assignments': [{'sale_line_id': sale['lines'][0]['id'], 'handling_unit_id': sale_hu['id']}]}, key=run + ':delivery'))
delivery = step('delivery_confirmed', lambda: call('POST', f'/sales/deliveries/{delivery["id"]}/confirm', {'expected_version': delivery['version']}, key=run + ':deliver'))
balance('balance_delivery', '4', '40')

save()
print(json.dumps({'run':run, 'purchase':purchase['code'], 'purchase_id':purchase['id'], 'sale':sale['code'], 'sale_id':sale['id'], 'quantity':'4', 'value':'40'},ensure_ascii=False))
print('LATE_RETACEO_UI_SETUP_PASSED')
