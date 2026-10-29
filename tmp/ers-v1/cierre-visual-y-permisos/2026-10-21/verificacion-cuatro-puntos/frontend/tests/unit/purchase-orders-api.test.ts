import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PurchaseOrderCreateInput,
  PurchaseOrderExpenseDocumentInitiateInput,
  PurchaseOrderUpdateInput
} from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  apiFetch: mocks.apiFetch
}));

import { purchaseOrdersApi } from '$lib/api/purchase-orders';

describe('purchaseOrdersApi', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset();
  });

  it('builds list filters and gets an order by id', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);

    await purchaseOrdersApi.list({
      status: 'pending_approval',
      supplier_id: 25,
      page: 2,
      size: 10
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      1,
      '/purchase-orders?status=pending_approval&supplier_id=25&page=2&size=10'
    );

    const id = '11111111-1111-1111-1111-111111111111';
    await purchaseOrdersApi.get(id);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(2, `/purchase-orders/${id}`);
  });

  it('lists active expense types from the public catalogue endpoint', async () => {
    mocks.apiFetch.mockResolvedValue([]);

    await purchaseOrdersApi.listExpenseTypes();

    expect(mocks.apiFetch).toHaveBeenCalledWith('/expense-types');
  });

  it('sends create and update DTOs without computed totals', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);

    const createPayload: PurchaseOrderCreateInput = {
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      branch_id: '22222222-2222-2222-2222-222222222222',
      warehouse_id: '33333333-3333-3333-3333-333333333333',
      expected_date: '2026-09-20T12:00:00-06:00',
      lines: [
        {
          purchase_quotation_detail_id: '44444444-4444-4444-4444-444444444444',
          quantity: 5
        }
      ],
      expenses: [],
      notes: 'Entrega prioritaria'
    };

    await purchaseOrdersApi.create(createPayload);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(1, '/purchase-orders', {
      method: 'POST',
      body: JSON.stringify(createPayload)
    });

    const updatePayload: PurchaseOrderUpdateInput = {
      branch_id: createPayload.branch_id,
      warehouse_id: createPayload.warehouse_id,
      expected_date: null,
      lines: createPayload.lines,
      expenses: [],
      notes: null
    };

    const id = '55555555-5555-5555-5555-555555555555';
    await purchaseOrdersApi.update(id, updatePayload);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(2, `/purchase-orders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updatePayload)
    });
  });

  it('maps every exposed workflow action to its POST endpoint', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);
    const id = '66666666-6666-6666-6666-666666666666';

    await purchaseOrdersApi.submit(id);
    await purchaseOrdersApi.approve(id);
    await purchaseOrdersApi.send(id);
    await purchaseOrdersApi.cancel(id);

    expect(mocks.apiFetch.mock.calls).toEqual([
      [`/purchase-orders/${id}/submit`, { method: 'POST' }],
      [`/purchase-orders/${id}/approve`, { method: 'POST' }],
      [`/purchase-orders/${id}/send`, { method: 'POST' }],
      [`/purchase-orders/${id}/cancel`, { method: 'POST' }]
    ]);
  });

  it('maps expense-document initiate, complete, list and download-url endpoints', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);

    const orderId = '77777777-7777-7777-7777-777777777777';
    const expenseId = '88888888-8888-8888-8888-888888888888';
    const documentId = '99999999-9999-9999-9999-999999999999';
    const payload: PurchaseOrderExpenseDocumentInitiateInput = {
      file_name: 'flete.pdf',
      content_type: 'application/pdf',
      size_bytes: 128,
      checksum_sha256: 'a'.repeat(64)
    };
    const base = `/purchase-orders/${orderId}/expenses/${expenseId}/documents`;

    await purchaseOrdersApi.initiateExpenseDocument(orderId, expenseId, payload);
    await purchaseOrdersApi.completeExpenseDocument(orderId, expenseId, documentId);
    await purchaseOrdersApi.listExpenseDocuments(orderId, expenseId);
    await purchaseOrdersApi.createExpenseDocumentDownloadUrl(orderId, expenseId, documentId);

    expect(mocks.apiFetch.mock.calls).toEqual([
      [
        `${base}/uploads`,
        {
          method: 'POST',
          body: JSON.stringify(payload)
        }
      ],
      [`${base}/${documentId}/complete`, { method: 'POST' }],
      [base],
      [`${base}/${documentId}/download-url`, { method: 'POST' }]
    ]);
  });
});
