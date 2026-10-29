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


client.headers['X-Company-ID']=state['company_id']
if 'ui_return_print' not in state:
    preview=call('GET','/inventory/labels/preview?handling_unit_id='+state['ui_return_hu']['id'])
    state['ui_return_print']=call('POST','/inventory/labels/prints',{
        'handling_unit_id':state['ui_return_hu']['id'],'idempotency_key':state['run']+':return-ui-print',
        'quantity_printed':1,'print_date':datetime.now(ZoneInfo('America/El_Salvador')).date().isoformat(),
        'reason':'reprint' if preview['has_initial_print'] else 'initial'})
    save()
print('DIGITAL_LABEL_DEMONSTRATION_PRINT_RECORDED_NO_PHYSICAL_PRINTER')
