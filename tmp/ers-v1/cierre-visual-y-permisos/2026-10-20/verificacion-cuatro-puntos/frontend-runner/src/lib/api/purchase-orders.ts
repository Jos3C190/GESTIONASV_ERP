import { apiFetch, type Page } from '$lib/api/client';
import { branch } from '$lib/stores/branch.svelte';
import type {
  PurchaseOrder,
  PurchaseOrderCreateInput,
  PurchaseOrderExpenseDocument,
  PurchaseOrderExpenseDocumentDownloadUrl,
  PurchaseOrderExpenseDocumentInitiateInput,
  PurchaseOrderExpenseDocumentUpload,
  PurchaseOrderExpenseType,
  PurchaseOrderFromConsolidationInput,
  PurchaseOrderExpenseTypeCatalog,
  PurchaseOrderListParams,
  PurchaseOrderUpdateInput
} from '$lib/types/purchase-order';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function scopedPath(path: string, branchId: string | null = branch.id): string {
  const query = new URLSearchParams();
  if (branchId) query.set('branch_id', branchId);
  return queryPath(path, query);
}

function expenseDocumentsPath(orderId: string, expenseId: string): string {
  return scopedPath(`/purchase-orders/${orderId}/expenses/${expenseId}/documents`);
}

export const purchaseOrdersApi = {
  list(params?: PurchaseOrderListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.supplier_id) query.set('supplier_id', String(params.supplier_id));
    const selectedBranchId = params?.branch_id !== undefined ? params.branch_id : branch.id;
    if (selectedBranchId) query.set('branch_id', selectedBranchId);
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<PurchaseOrder>>(queryPath('/purchase-orders', query));
  },

  get(id: string, branchId: string | null = branch.id) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}`, branchId));
  },

  listExpenseTypes() {
    return apiFetch<PurchaseOrderExpenseType[]>('/expense-types');
  },

  listExpenseTypeCatalog() {
    return apiFetch<PurchaseOrderExpenseTypeCatalog[]>('/expense-types/catalog');
  },

  createExpenseType(payload: { name: string; description?: string }) {
    return apiFetch<PurchaseOrderExpenseTypeCatalog>('/expense-types', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  updateExpenseType(
    id: string,
    payload: { name: string; description?: string | null; is_active: boolean }
  ) {
    return apiFetch<PurchaseOrderExpenseTypeCatalog>(`/expense-types/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },

  create(payload: PurchaseOrderCreateInput) {
    return apiFetch<PurchaseOrder>(scopedPath('/purchase-orders'), {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createFromConsolidation(
    consolidationId: string,
    quotationId: string,
    payload: PurchaseOrderFromConsolidationInput
  ) {
    return apiFetch<PurchaseOrder>(
      scopedPath(`/purchase-orders/from-consolidation/${consolidationId}/${quotationId}`),
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );
  },

  update(id: string, payload: PurchaseOrderUpdateInput) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}`), {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  submit(id: string) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}/submit`), {
      method: 'POST'
    });
  },

  approve(id: string) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}/approve`), {
      method: 'POST'
    });
  },

  send(id: string) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}/send`), {
      method: 'POST'
    });
  },

  cancel(id: string) {
    return apiFetch<PurchaseOrder>(scopedPath(`/purchase-orders/${id}/cancel`), {
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
