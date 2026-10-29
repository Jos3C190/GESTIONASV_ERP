"""Individual opening publishes quantity/value once and retains warehouse scope."""

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.application.inventory import InventoryUseCases
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory import InventoryHandlingUnitModel, InventoryItemModel
from app.infrastructure.models.inventory_valuation import InventoryCostAverageModel, InventoryValuationEntryModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from tests.e2e.test_inventory_preparation import _operator_headers
from tests.e2e.test_purchase_orders import _headers, _reference_ids

pytestmark = pytest.mark.e2e


async def test_opening_stock_history_idempotence_scope_and_depleted_product(e2e_client):
    client = e2e_client
    company, _, warehouse, product, _, currency = await _reference_ids()
    headers = await _headers(client, company_id=company, username="opening-admin", is_superuser=True)
    actor = uuid.UUID((await client.get('/api/v1/auth/me', headers=headers)).json()['id'])
    overview = (await client.get('/api/v1/inventory/valuation', headers=headers)).json()
    cut = await client.post('/api/v1/inventory/valuation/opening', headers=headers, json={
        'currency': currency, 'reference': 'Apertura de empresa vacía', 'approved': True,
        'snapshot_fingerprint': overview['snapshot_fingerprint'], 'lines': [],
    })
    assert cut.status_code == 200, cut.text
    async with async_session_factory() as session:
        item = await session.scalar(select(InventoryItemModel).where(InventoryItemModel.company_id == company, InventoryItemModel.product_id == product))
        location = await session.scalar(select(Location).where(Location.warehouse_id == warehouse, Location.storage_eligible.is_(True), Location.is_active.is_(True), Location.lifecycle_status == 'active'))
        assert location is not None
        item_id, location_id = item.id, location.id
        source = await session.get(Warehouse, warehouse)
        other = Warehouse(company_id=company, branch_id=source.branch_id, warehouse_category_id=source.warehouse_category_id, code='OPEN-OTHER', name='Other warehouse', is_central=False)
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()
    operator = await _operator_headers(client, company, warehouse)
    body = {
        'warehouse_id': str(warehouse), 'inventory_item_id': str(item_id), 'location_id': str(location_id),
        'quantity_base': '80', 'unit_cost': '6.80', 'gross_weight_kg': '1', 'volume_m3': '0.001',
        'operational_date': datetime.now(ZoneInfo('America/El_Salvador')).date().isoformat(),
        'document_reference': 'ACTA-INICIAL-01', 'reason': 'Conteo físico inicial autorizado',
        'idempotency_key': str(uuid.uuid4()), 'lot_code': 'APERTURA-01',
    }
    endpoint = '/api/v1/inventory/product-opening'
    assert (await client.post(endpoint, headers=operator, json=body)).status_code == 403
    invalid = await client.post(endpoint, headers=headers, json={**body, 'warehouse_id': str(other_id)})
    assert invalid.status_code == 422, invalid.text
    created = await client.post(endpoint, headers=headers, json=body)
    assert created.status_code == 200, created.text
    assert created.json()['movement_type'] == 'opening'
    repeated = await client.post(endpoint, headers=headers, json=body)
    assert repeated.status_code == 200 and repeated.json()['id'] == created.json()['id'], repeated.text
    changed = await client.post(endpoint, headers=headers, json={**body, 'unit_cost': '7'})
    assert changed.status_code == 409, changed.text
    again = await client.post(endpoint, headers=headers, json={**body, 'idempotency_key': str(uuid.uuid4())})
    assert again.status_code == 409 and 'opening_history_exists' in again.text
    stock_url = f'/api/v1/inventory/warehouses/{warehouse}/stock'
    stock = await client.get(stock_url, headers=operator, params={'q': 'APERTURA-01'})
    assert stock.status_code == 200, stock.text
    row = stock.json()['items'][0]
    assert Decimal(row['quantity_base']) == 80
    assert row['stock_status'] == 'available' and row['location_id'] == str(location_id)
    assert 'cost' not in stock.text and 'value' not in stock.text
    assert (await client.get(stock_url, headers=operator, params={'q': '%'})).json()['total'] == 0
    assert (await client.get(f'/api/v1/inventory/warehouses/{other_id}/stock', headers=operator)).status_code == 403
    async with async_session_factory() as session:
        balance = await session.get(InventoryCostAverageModel, (company,item_id))
        assert balance.quantity_base == 80 and balance.inventory_value == Decimal('544') and balance.average_unit_cost == Decimal('6.8')
        assert await session.scalar(select(func.count()).select_from(InventoryValuationEntryModel).where(InventoryValuationEntryModel.company_id == company, InventoryValuationEntryModel.inventory_item_id == item_id)) == 1
        unit = await session.scalar(select(InventoryHandlingUnitModel).where(InventoryHandlingUnitModel.company_id == company, InventoryHandlingUnitModel.inventory_item_id == item_id))
        await InventoryUseCases(SqlAlchemyInventoryRepository(session)).post_movement(
            company_id=company, actor_id=actor, movement_type='shipment', idempotency_key='opening-depletion-test', source_reference='SALIDA-PRUEBA',
            lines=[{'inventory_item_id': item_id, 'handling_unit_id': unit.id, 'from_location_id': location_id,
                    'from_stock_status':'available', 'to_location_id':None, 'quantity_base':Decimal('80')}])
        await session.commit()
    empty = await client.post(endpoint, headers=headers, json={**body, 'idempotency_key':str(uuid.uuid4())})
    assert empty.status_code == 409 and 'opening_history_exists' in empty.text
