import { apiFetch, type Page } from '$lib/api/client';
import type {
  Purchase,
  PurchaseCreateInput,
  PurchaseListParams,
  PurchaseReceivable,
  PurchaseUpdateInput
} from '$lib/types/purchase';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export const purchasesApi = {
  list(params?: PurchaseListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.supplier_id) query.set('supplier_id', String(params.supplier_id));
    if (params?.purchase_order_id) query.set('purchase_order_id', params.purchase_order_id);
    if (params?.branch_id) query.set('branch_id', params.branch_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<Purchase>>(queryPath('/purchases', query));
  },

  get(id: string) {
    return apiFetch<Purchase>(`/purchases/${id}`);
  },

  getReceivable(orderId: string) {
    return apiFetch<PurchaseReceivable>(`/purchase-orders/${orderId}/receivable`);
  },

  create(payload: PurchaseCreateInput) {
    return apiFetch<Purchase>('/purchases', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  update(id: string, payload: PurchaseUpdateInput) {
    return apiFetch<Purchase>(`/purchases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  receive(id: string) {
    return apiFetch<Purchase>(`/purchases/${id}/receive`, {
      method: 'POST'
    });
  },

  verify(id: string) {
    return apiFetch<Purchase>(`/purchases/${id}/verify`, {
      method: 'POST'
    });
  },

  cancel(id: string) {
    return apiFetch<Purchase>(`/purchases/${id}/cancel`, {
      method: 'POST'
    });
  },

  close(id: string) {
    return apiFetch<Purchase>(`/purchases/${id}/close`, {
      method: 'POST'
    });
  }
};
