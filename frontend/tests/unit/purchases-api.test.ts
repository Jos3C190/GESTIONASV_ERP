import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PurchaseCreateInput, PurchaseUpdateInput } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  apiFetch: mocks.apiFetch
}));

import { purchasesApi } from '$lib/api/purchases';

describe('purchasesApi', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset();
    mocks.apiFetch.mockResolvedValue(undefined);
  });

  it('builds list filters, gets a purchase and reads receivable quantities', async () => {
    await purchasesApi.list({
      status: 'received',
      supplier_id: 25,
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      branch_id: '22222222-2222-2222-2222-222222222222',
      page: 2,
      size: 10
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      1,
      '/purchases?status=received&supplier_id=25&purchase_order_id=11111111-1111-1111-1111-111111111111&branch_id=22222222-2222-2222-2222-222222222222&page=2&size=10'
    );

    const purchaseId = '33333333-3333-3333-3333-333333333333';
    await purchasesApi.get(purchaseId);
    expect(mocks.apiFetch).toHaveBeenNthCalledWith(2, `/purchases/${purchaseId}`);

    const orderId = '44444444-4444-4444-4444-444444444444';
    await purchasesApi.getReceivable(orderId);
    expect(mocks.apiFetch).toHaveBeenNthCalledWith(3, `/purchase-orders/${orderId}/receivable`);
  });

  it('sends create and update DTOs without client-computed totals', async () => {
    const createPayload: PurchaseCreateInput = {
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      supplier_invoice_number: 'FAC-001',
      supplier_invoice_date: '2026-09-20',
      lines: [
        {
          purchase_order_detail_id: '22222222-2222-2222-2222-222222222222',
          quantity_received: 2
        }
      ],
      notes: 'Recepción parcial'
    };

    await purchasesApi.create(createPayload);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(1, '/purchases', {
      method: 'POST',
      body: JSON.stringify(createPayload)
    });

    const updatePayload: PurchaseUpdateInput = {
      supplier_invoice_number: 'FAC-001-A',
      supplier_invoice_date: null,
      lines: createPayload.lines,
      notes: null
    };

    const purchaseId = '33333333-3333-3333-3333-333333333333';
    await purchasesApi.update(purchaseId, updatePayload);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(2, `/purchases/${purchaseId}`, {
      method: 'PUT',
      body: JSON.stringify(updatePayload)
    });
  });

  it('maps every purchase lifecycle action to its POST endpoint', async () => {
    const id = '55555555-5555-5555-5555-555555555555';

    await purchasesApi.receive(id);
    await purchasesApi.verify(id);
    await purchasesApi.cancel(id);
    await purchasesApi.close(id);

    expect(mocks.apiFetch.mock.calls).toEqual([
      [`/purchases/${id}/receive`, { method: 'POST' }],
      [`/purchases/${id}/verify`, { method: 'POST' }],
      [`/purchases/${id}/cancel`, { method: 'POST' }],
      [`/purchases/${id}/close`, { method: 'POST' }]
    ]);
  });
});
