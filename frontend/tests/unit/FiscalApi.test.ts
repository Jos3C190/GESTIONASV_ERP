import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));

import { fiscalApi } from '../../src/lib/api/fiscal';

function call(index = 0): [string, RequestInit | undefined] {
  return apiFetchMock.mock.calls[index] as [string, RequestInit | undefined];
}

describe('fiscalApi', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({});
  });

  it('reads a catalog by group and search', async () => {
    await fiscalApi.catalog('CAT-008', { group: '06', search: 'san', limit: 50 });
    expect(call()[0]).toBe('/fiscal/catalogs/CAT-008?group=06&search=san&limit=50');
    await fiscalApi.catalog('CAT-019');
    expect(call(1)[0]).toBe('/fiscal/catalogs/CAT-019');
  });

  it('sends the issuer profile with PUT', async () => {
    await fiscalApi.updateProfile({
      taxpayer_category: 'medium',
      person_type: '2',
      operating_mode: 'simulated',
      dte_email: 'dte@example.com',
      dte_phone: null
    });
    const [path, init] = call();
    expect(path).toBe('/fiscal/profile');
    expect(init?.method).toBe('PUT');
    expect(JSON.parse(init?.body as string)).toMatchObject({ operating_mode: 'simulated' });
  });

  it('manages activities, establishments and points of sale', async () => {
    await fiscalApi.addActivity('10712', true);
    expect(JSON.parse(call()[1]?.body as string)).toEqual({ code: '10712', is_primary: true });
    await fiscalApi.setPrimaryActivity('a1');
    expect(call(1)).toEqual(['/fiscal/activities/a1/primary', { method: 'POST' }]);
    await fiscalApi.deleteActivity('a1');
    expect(call(2)).toEqual(['/fiscal/activities/a1', { method: 'DELETE' }]);
    await fiscalApi.createEstablishment({
      branch_id: 'b1',
      establishment_type: '02',
      code: 'M001',
      activity_id: null
    });
    expect(call(3)[0]).toBe('/fiscal/establishments');
    await fiscalApi.createPointOfSale('e1', { code: 'P001', name: 'Caja 1' });
    expect(call(4)[0]).toBe('/fiscal/establishments/e1/points-of-sale');
    await fiscalApi.updatePointOfSale('p1', { code: 'P002', name: 'Caja 2', is_active: false });
    expect(call(5)[0]).toBe('/fiscal/points-of-sale/p1');
    expect(call(5)[1]?.method).toBe('PATCH');
  });

  it('updates one document type', async () => {
    await fiscalApi.updateDocumentType('03', {
      is_enabled: true,
      certification_status: 'in_progress'
    });
    expect(call()[0]).toBe('/fiscal/document-types/03');
    expect(call()[1]?.method).toBe('PUT');
  });
});
