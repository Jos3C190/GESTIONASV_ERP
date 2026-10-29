import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PurchaseQuotationCreateInput,
  PurchaseQuotationRecordResponseInput
} from '$lib/types/purchase-quotation';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  apiFetch: mocks.apiFetch
}));

import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';

describe('purchaseQuotationsApi', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset();
  });

  it('builds list and comparison query strings', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);

    await purchaseQuotationsApi.list({
      status: 'received',
      supplier_id: 25,
      page: 2,
      size: 10
    });

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      1,
      '/purchase-quotations?status=received&supplier_id=25&page=2&size=10'
    );

    await purchaseQuotationsApi.compare('11111111-1111-1111-1111-111111111111', 'USD');

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      2,
      '/purchase-quotations/comparison/11111111-1111-1111-1111-111111111111?currency=USD'
    );
  });

  it('sends create and supplier-response DTOs with the backend contract', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);

    const createPayload: PurchaseQuotationCreateInput = {
      supplier_id: 25,
      currency: 'USD',
      requests: [
        {
          purchase_request_id: '11111111-1111-1111-1111-111111111111',
          lines: [
            {
              purchase_request_detail_id: '22222222-2222-2222-2222-222222222222',
              quantity: 5
            }
          ]
        }
      ],
      notes: null
    };

    await purchaseQuotationsApi.create(createPayload);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(1, '/purchase-quotations', {
      method: 'POST',
      body: JSON.stringify(createPayload)
    });

    const responsePayload: PurchaseQuotationRecordResponseInput = {
      quotation_date: '2026-09-13T12:00:00-06:00',
      valid_until: '2026-09-30T12:00:00-06:00',
      payment_terms: '30 días',
      delivery_days: 4,
      lines: [
        {
          product_id: 10,
          unit_id: 2,
          offered_quantity: 5,
          unit_price: 12.5,
          discount: 0,
          tax_rate: 13,
          delivery_days: 4,
          available_quantity: 5,
          notes: null
        }
      ],
      expenses: [
        {
          expense_type_id: '33333333-3333-3333-3333-333333333333',
          amount: 8,
          description: 'Flete'
        }
      ],
      notes: 'Oferta recibida'
    };

    await purchaseQuotationsApi.recordResponse(
      '44444444-4444-4444-4444-444444444444',
      responsePayload
    );

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      2,
      '/purchase-quotations/44444444-4444-4444-4444-444444444444/response',
      {
        method: 'PUT',
        body: JSON.stringify(responsePayload)
      }
    );
  });

  it('creates and lists RFQs inside a consolidation scope', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);
    const consolidationId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
    const payload = {
      supplier_id: 25,
      currency: 'USD',
      consolidation_line_ids: ['bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'],
      notes: 'Entrega esta semana'
    };

    await purchaseQuotationsApi.createFromConsolidation(consolidationId, payload);
    await purchaseQuotationsApi.listForConsolidation(consolidationId);

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      1,
      `/purchase-consolidations/${consolidationId}/purchase-quotations`,
      { method: 'POST', body: JSON.stringify(payload) }
    );
    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      2,
      `/purchase-consolidations/${consolidationId}/purchase-quotations`
    );
  });

  it('keeps consolidation scope for quote details, responses, and workflow actions', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);
    const quotationId = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
    const consolidationId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

    await purchaseQuotationsApi.get(quotationId, 'ignored-branch', consolidationId);
    await purchaseQuotationsApi.send(quotationId, consolidationId);
    await purchaseQuotationsApi.recordResponse(
      quotationId,
      {
        quotation_date: '2026-10-05T12:00:00-06:00',
        valid_until: null,
        payment_terms: null,
        delivery_days: null,
        lines: [],
        expenses: [],
        notes: null
      },
      'ignored-branch',
      consolidationId
    );

    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      1,
      `/purchase-quotations/${quotationId}?consolidation_id=${consolidationId}`
    );
    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      2,
      `/purchase-quotations/${quotationId}/send?consolidation_id=${consolidationId}`,
      { method: 'POST' }
    );
    expect(mocks.apiFetch).toHaveBeenNthCalledWith(
      3,
      `/purchase-quotations/${quotationId}/response?consolidation_id=${consolidationId}`,
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('keeps consolidation scope for supplier offer document lifecycle', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);
    const quotationId = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
    const consolidationId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
    const documentId = 'dddddddd-dddd-dddd-dddd-dddddddddddd';

    await purchaseQuotationsApi.initiateDocument(
      quotationId,
      {
        file_name: 'oferta-proveedor.pdf',
        content_type: 'application/pdf',
        size_bytes: 1024,
        checksum_sha256: 'a'.repeat(64)
      },
      undefined,
      consolidationId
    );
    await purchaseQuotationsApi.completeDocument(
      quotationId,
      documentId,
      undefined,
      consolidationId
    );
    await purchaseQuotationsApi.listDocuments(quotationId, undefined, consolidationId);
    await purchaseQuotationsApi.removeDocument(quotationId, documentId, undefined, consolidationId);
    await purchaseQuotationsApi.createDocumentDownloadUrl(
      quotationId,
      documentId,
      undefined,
      consolidationId
    );

    expect(mocks.apiFetch.mock.calls).toEqual([
      [
        `/purchase-quotations/${quotationId}/documents/uploads?consolidation_id=${consolidationId}`,
        expect.objectContaining({ method: 'POST' })
      ],
      [
        `/purchase-quotations/${quotationId}/documents/${documentId}/complete?consolidation_id=${consolidationId}`,
        { method: 'POST' }
      ],
      [`/purchase-quotations/${quotationId}/documents?consolidation_id=${consolidationId}`],
      [
        `/purchase-quotations/${quotationId}/documents/${documentId}?consolidation_id=${consolidationId}`,
        { method: 'DELETE' }
      ],
      [
        `/purchase-quotations/${quotationId}/documents/${documentId}/download-url?consolidation_id=${consolidationId}`,
        { method: 'POST' }
      ]
    ]);
  });

  it('maps every workflow action to its POST endpoint', async () => {
    mocks.apiFetch.mockResolvedValue(undefined);
    const id = '55555555-5555-5555-5555-555555555555';

    await purchaseQuotationsApi.send(id);
    await purchaseQuotationsApi.evaluate(id);
    await purchaseQuotationsApi.select(id);
    await purchaseQuotationsApi.reject(id);
    await purchaseQuotationsApi.cancel(id);

    expect(mocks.apiFetch.mock.calls).toEqual([
      [`/purchase-quotations/${id}/send`, { method: 'POST' }],
      [`/purchase-quotations/${id}/evaluate`, { method: 'POST' }],
      [`/purchase-quotations/${id}/select`, { method: 'POST' }],
      [`/purchase-quotations/${id}/reject`, { method: 'POST' }],
      [`/purchase-quotations/${id}/cancel`, { method: 'POST' }]
    ]);
  });
});
