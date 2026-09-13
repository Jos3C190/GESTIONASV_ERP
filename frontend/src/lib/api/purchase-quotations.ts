import { apiFetch, type Page } from '$lib/api/client';
import type {
  PurchaseQuotation,
  PurchaseQuotationComparison,
  PurchaseQuotationCreateInput,
  PurchaseQuotationListParams,
  PurchaseQuotationRecordResponseInput
} from '$lib/types/purchase-quotation';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export const purchaseQuotationsApi = {
  list(params?: PurchaseQuotationListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.supplier_id) query.set('supplier_id', String(params.supplier_id));
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<PurchaseQuotation>>(queryPath('/purchase-quotations', query));
  },

  get(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}`);
  },

  compare(purchaseRequestId: string, currency?: string) {
    const query = new URLSearchParams();
    if (currency) query.set('currency', currency);

    return apiFetch<PurchaseQuotationComparison[]>(
      queryPath(`/purchase-quotations/comparison/${purchaseRequestId}`, query)
    );
  },

  create(payload: PurchaseQuotationCreateInput) {
    return apiFetch<PurchaseQuotation>('/purchase-quotations', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  recordResponse(id: string, payload: PurchaseQuotationRecordResponseInput) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/response`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  send(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/send`, {
      method: 'POST'
    });
  },

  evaluate(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/evaluate`, {
      method: 'POST'
    });
  },

  select(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/select`, {
      method: 'POST'
    });
  },

  reject(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/reject`, {
      method: 'POST'
    });
  },

  cancel(id: string) {
    return apiFetch<PurchaseQuotation>(`/purchase-quotations/${id}/cancel`, {
      method: 'POST'
    });
  }
};
