import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  apiFetch: mocks.apiFetch
}));

import { retaceosApi } from '$lib/api/retaceos';

describe('retaceosApi', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset();
    mocks.apiFetch.mockResolvedValue({});
  });

  it('builds the list query from supported filters', async () => {
    await retaceosApi.list({
      status: 'calculated',
      purchase_id: '11111111-1111-1111-1111-111111111111',
      branch_id: '22222222-2222-2222-2222-222222222222',
      page: 2,
      size: 50
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      '/retaceos?status=calculated&purchase_id=11111111-1111-1111-1111-111111111111&branch_id=22222222-2222-2222-2222-222222222222&page=2&size=50'
    );
  });

  it('uses the backend contract for create, update and workflow transitions', async () => {
    const createPayload = {
      purchase_id: '11111111-1111-1111-1111-111111111111',
      total_freight: '10.000000',
      total_expenses: '5.000000',
      total_dai: '3.000000',
      import_vat: '2.340000',
      notes: 'Importación septiembre'
    };

    const updatePayload = {
      total_freight: '12.000000',
      total_expenses: '5.000000',
      total_dai: '3.000000',
      import_vat: '2.340000',
      notes: null
    };

    await retaceosApi.create(createPayload);
    await retaceosApi.update('ret-1', updatePayload);
    await retaceosApi.calculate('ret-1');
    await retaceosApi.verify('ret-1');
    await retaceosApi.cancel('ret-1');
    await retaceosApi.close('ret-1');

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(1, '/retaceos', {
      method: 'POST',
      body: JSON.stringify(createPayload)
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(2, '/retaceos/ret-1', {
      method: 'PUT',
      body: JSON.stringify(updatePayload)
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(3, '/retaceos/ret-1/calculate', {
      method: 'POST'
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(4, '/retaceos/ret-1/verify', {
      method: 'POST'
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(5, '/retaceos/ret-1/cancel', {
      method: 'POST'
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(6, '/retaceos/ret-1/close', {
      method: 'POST'
    });
  });
});
