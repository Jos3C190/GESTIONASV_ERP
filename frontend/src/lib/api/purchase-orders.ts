import { apiFetch, type Page } from '$lib/api/client';
import type {
  PurchaseOrder,
  PurchaseOrderCreateInput,
  PurchaseOrderExpenseDocument,
  PurchaseOrderExpenseDocumentDownloadUrl,
  PurchaseOrderExpenseDocumentInitiateInput,
  PurchaseOrderExpenseDocumentUpload,
  PurchaseOrderExpenseType,
  PurchaseOrderListParams,
  PurchaseOrderUpdateInput
} from '$lib/types/purchase-order';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function expenseDocumentsPath(orderId: string, expenseId: string): string {
  return `/purchase-orders/${orderId}/expenses/${expenseId}/documents`;
}

export const purchaseOrdersApi = {
  list(params?: PurchaseOrderListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.supplier_id) query.set('supplier_id', String(params.supplier_id));
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<PurchaseOrder>>(queryPath('/purchase-orders', query));
  },

  get(id: string) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}`);
  },

  listExpenseTypes() {
    return apiFetch<PurchaseOrderExpenseType[]>('/expense-types');
  },

  create(payload: PurchaseOrderCreateInput) {
    return apiFetch<PurchaseOrder>('/purchase-orders', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  update(id: string, payload: PurchaseOrderUpdateInput) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  submit(id: string) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/submit`, {
      method: 'POST'
    });
  },

  approve(id: string) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/approve`, {
      method: 'POST'
    });
  },

  send(id: string) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/send`, {
      method: 'POST'
    });
  },

  cancel(id: string) {
    return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/cancel`, {
      method: 'POST'
    });
  },

  initiateExpenseDocument(
    orderId: string,
    expenseId: string,
    payload: PurchaseOrderExpenseDocumentInitiateInput
  ) {
    return apiFetch<PurchaseOrderExpenseDocumentUpload>(
      `${expenseDocumentsPath(orderId, expenseId)}/uploads`,
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );
  },

  completeExpenseDocument(orderId: string, expenseId: string, documentId: string) {
    return apiFetch<PurchaseOrderExpenseDocument>(
      `${expenseDocumentsPath(orderId, expenseId)}/${documentId}/complete`,
      { method: 'POST' }
    );
  },

  listExpenseDocuments(orderId: string, expenseId: string) {
    return apiFetch<PurchaseOrderExpenseDocument[]>(expenseDocumentsPath(orderId, expenseId));
  },

  createExpenseDocumentDownloadUrl(orderId: string, expenseId: string, documentId: string) {
    return apiFetch<PurchaseOrderExpenseDocumentDownloadUrl>(
      `${expenseDocumentsPath(orderId, expenseId)}/${documentId}/download-url`,
      { method: 'POST' }
    );
  }
};
