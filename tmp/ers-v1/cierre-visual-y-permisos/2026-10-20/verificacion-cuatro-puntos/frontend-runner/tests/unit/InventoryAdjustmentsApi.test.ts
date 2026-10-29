import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));

import { inventoryAdjustmentsApi, type AdjustmentCreateInput } from '../../src/lib/features/inventory/adjustments';

const draft: AdjustmentCreateInput = {
  warehouse_id: 'warehouse-1',
  operational_date: '2026-10-19',
  accounting_date: '2026-10-19',
  reason: 'Conteo de verificación',
  document_reference: 'ACTA-001',
  notes: null,
  lines: [{
    inventory_item_id: 'item-1',
    location_id: 'location-1',
    direction: 'increase',
    quantity_base: '2',
    stock_status: 'quarantine',
    documented_unit_cost: '3',
    actual_gross_weight_kg: '1',
    actual_volume_m3: '0.5'
  }]
};

describe('inventoryAdjustmentsApi', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    localStorage.clear();
  });

  it('reuses the create idempotency key after an uncertain response for the same body', async () => {
    apiFetchMock.mockRejectedValueOnce(new Error('Respuesta interrumpida')).mockResolvedValue({ id: 'adjustment-1' });

    await expect(inventoryAdjustmentsApi.create(draft)).rejects.toThrow('Respuesta interrumpida');
    await inventoryAdjustmentsApi.create(draft);

    const firstBody = JSON.parse((apiFetchMock.mock.calls[0]?.[1] as RequestInit).body as string);
    const retryBody = JSON.parse((apiFetchMock.mock.calls[1]?.[1] as RequestInit).body as string);
    expect(firstBody.idempotency_key).toMatch(/^adj:/);
    expect(retryBody.idempotency_key).toBe(firstBody.idempotency_key);
    expect(localStorage.length).toBe(0);
  });

  it('encodes warehouse, status and date filters for the adjustment list', async () => {
    apiFetchMock.mockResolvedValue({ items: [], total: 0 });
    await inventoryAdjustmentsApi.list({ warehouse_id: 'warehouse-1', status: 'applied', date_from: '2026-10-01' });

    const url = new URL(apiFetchMock.mock.calls[0]?.[0] as string, 'http://test.local');
    expect(url.pathname).toBe('/inventory/adjustments');
    expect(url.searchParams.get('warehouse_id')).toBe('warehouse-1');
    expect(url.searchParams.get('status')).toBe('applied');
    expect(url.searchParams.get('date_from')).toBe('2026-10-01');
  });
});
