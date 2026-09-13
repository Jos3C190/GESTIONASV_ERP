import { apiFetch } from '$lib/api/client';
import type { PageResponse } from '$lib/api/catalog';
import type {
  PurchaseRequest,
  PurchaseRequestStatus,
  PurchaseRequestWrite
} from '$lib/types/purchase-request';

export const purchaseRequestsApi = {
  list: (params?: {
    status?: PurchaseRequestStatus;
    branch_id?: string;
    page?: number;
    size?: number;
  }) => {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.branch_id) query.set('branch_id', params.branch_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    const search = query.toString();

    return apiFetch<PageResponse<PurchaseRequest>>(
      `/purchase-requests${search ? `?${search}` : ''}`
    );
  },

  get: (id: string) => apiFetch<PurchaseRequest>(`/purchase-requests/${id}`),

  create: (data: PurchaseRequestWrite) =>
    apiFetch<PurchaseRequest>('/purchase-requests', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  update: (id: string, data: PurchaseRequestWrite) =>
    apiFetch<PurchaseRequest>(`/purchase-requests/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  submit: (id: string) =>
    apiFetch<PurchaseRequest>(`/purchase-requests/${id}/submit`, {
      method: 'POST'
    }),

  approve: (id: string) =>
    apiFetch<PurchaseRequest>(`/purchase-requests/${id}/approve`, {
      method: 'POST'
    }),

  reject: (id: string) =>
    apiFetch<PurchaseRequest>(`/purchase-requests/${id}/reject`, {
      method: 'POST'
    }),

  cancel: (id: string) =>
    apiFetch<PurchaseRequest>(`/purchase-requests/${id}/cancel`, {
      method: 'POST'
    })
};
