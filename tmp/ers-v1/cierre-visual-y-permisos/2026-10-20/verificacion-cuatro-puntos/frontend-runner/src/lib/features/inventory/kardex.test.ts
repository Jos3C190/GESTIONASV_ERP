import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));

import { kardexApi } from './kardex';

describe('kardexApi', () => {
  beforeEach(() => apiFetchMock.mockReset());

  it('encodes physical filters and keeps pagination in the server query', async () => {
    apiFetchMock.mockResolvedValue({ items: [], total: 0 });

    await kardexApi.physical({
      warehouse_id: 'warehouse/1',
      inventory_item_id: 'item-1',
      period_from: '2026-10-01',
      period_to: '2026-10-14',
      movement_type: 'transfer',
      lot_code: 'LOT A/1',
      source_reference: 'adjustment:AJ-20261019-000001:2',
      page: 2,
      page_size: 25
    });

    const [path] = apiFetchMock.mock.calls[0] as [string];
    const url = new URL(path, 'http://test.local');
    expect(url.pathname).toBe('/inventory/kardex/physical');
    expect(url.searchParams.get('warehouse_id')).toBe('warehouse/1');
    expect(url.searchParams.get('inventory_item_id')).toBe('item-1');
    expect(url.searchParams.get('movement_type')).toBe('transfer');
    expect(url.searchParams.get('lot_code')).toBe('LOT A/1');
    expect(url.searchParams.get('source_reference')).toBe('adjustment:AJ-20261019-000001:2');
    expect(url.searchParams.get('page')).toBe('2');
    expect(url.searchParams.get('page_size')).toBe('25');
  });

  it('requests company-wide values and reconciliation through separate contracts', async () => {
    apiFetchMock.mockResolvedValue({ items: [], total: 0 });

    await kardexApi.valued('item-9', {
      period_from: '2026-10-01',
      period_to: '2026-10-14',
      page: 3
    });
    await kardexApi.reconciliation(2, 50);

    const valuedUrl = new URL(apiFetchMock.mock.calls[0]?.[0] as string, 'http://test.local');
    expect(valuedUrl.pathname).toBe('/inventory/kardex/valuation');
    expect(valuedUrl.searchParams.get('inventory_item_id')).toBe('item-9');
    expect(valuedUrl.searchParams.get('period_from')).toBe('2026-10-01');
    expect(valuedUrl.searchParams.get('page')).toBe('3');

    const reconciliationUrl = new URL(
      apiFetchMock.mock.calls[1]?.[0] as string,
      'http://test.local'
    );
    expect(reconciliationUrl.pathname).toBe('/inventory/kardex/reconciliation');
    expect(reconciliationUrl.searchParams.get('page')).toBe('2');
    expect(reconciliationUrl.searchParams.get('page_size')).toBe('50');
  });
});
