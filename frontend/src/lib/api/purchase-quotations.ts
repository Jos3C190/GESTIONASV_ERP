import { apiFetch, type Page } from '$lib/api/client';
import { branch } from '$lib/stores/branch.svelte';
import type {
  PurchaseQuotation,
  PurchaseQuotationComparison,
  PurchaseQuotationCreateInput,
  PurchaseQuotationListParams,
  PurchaseQuotationRecordResponseInput,
  PurchaseQuotationFromConsolidationInput,
  PurchaseQuotationDocument,
  PurchaseQuotationDocumentDownloadUrl,
  PurchaseQuotationDocumentInitiateInput,
  PurchaseQuotationDocumentUpload
} from '$lib/types/purchase-quotation';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function scopedPath(
  path: string,
  branchId: string | null = branch.id,
  consolidationId: string | null = null
): string {
  const query = new URLSearchParams();
  if (consolidationId) query.set('consolidation_id', consolidationId);
  else if (branchId) query.set('branch_id', branchId);
  return queryPath(path, query);
}

export const purchaseQuotationsApi = {
  list(params?: PurchaseQuotationListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.supplier_id) query.set('supplier_id', String(params.supplier_id));
    const selectedBranchId = params?.branch_id !== undefined ? params.branch_id : branch.id;
    if (selectedBranchId) query.set('branch_id', selectedBranchId);
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<PurchaseQuotation>>(queryPath('/purchase-quotations', query));
  },

  get(id: string, branchId: string | null = branch.id, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(`/purchase-quotations/${id}`, branchId, consolidationId)
    );
  },

  compare(purchaseRequestId: string, currency?: string, branchId: string | null = branch.id) {
    const query = new URLSearchParams();
    if (currency) query.set('currency', currency);
    if (branchId) query.set('branch_id', branchId);

    return apiFetch<PurchaseQuotationComparison[]>(
      queryPath(`/purchase-quotations/comparison/${purchaseRequestId}`, query)
    );
  },

  create(payload: PurchaseQuotationCreateInput) {
    return apiFetch<PurchaseQuotation>(scopedPath('/purchase-quotations'), {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createFromConsolidation(
    consolidationId: string,
    payload: PurchaseQuotationFromConsolidationInput
  ) {
    return apiFetch<PurchaseQuotation>(
      `/purchase-consolidations/${consolidationId}/purchase-quotations`,
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );
  },

  listForConsolidation(consolidationId: string) {
    return apiFetch<PurchaseQuotation[]>(
      `/purchase-consolidations/${consolidationId}/purchase-quotations`
    );
  },

  initiateDocument(
    id: string,
    payload: PurchaseQuotationDocumentInitiateInput,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<PurchaseQuotationDocumentUpload>(
      scopedPath(`/purchase-quotations/${id}/documents/uploads`, branchId, consolidationId),
      { method: 'POST', body: JSON.stringify(payload) }
    );
  },

  completeDocument(
    id: string,
    documentId: string,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<PurchaseQuotationDocument>(
      scopedPath(
        `/purchase-quotations/${id}/documents/${documentId}/complete`,
        branchId,
        consolidationId
      ),
      { method: 'POST' }
    );
  },

  listDocuments(
    id: string,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<PurchaseQuotationDocument[]>(
      scopedPath(`/purchase-quotations/${id}/documents`, branchId, consolidationId)
    );
  },

  removeDocument(
    id: string,
    documentId: string,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<void>(
      scopedPath(`/purchase-quotations/${id}/documents/${documentId}`, branchId, consolidationId),
      { method: 'DELETE' }
    );
  },

  createDocumentDownloadUrl(
    id: string,
    documentId: string,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<PurchaseQuotationDocumentDownloadUrl>(
      scopedPath(
        `/purchase-quotations/${id}/documents/${documentId}/download-url`,
        branchId,
        consolidationId
      ),
      { method: 'POST' }
    );
  },

  recordResponse(
    id: string,
    payload: PurchaseQuotationRecordResponseInput,
    branchId: string | null = branch.id,
    consolidationId: string | null = null
  ) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(`/purchase-quotations/${id}/response`, branchId, consolidationId),
      {
        method: 'PUT',
        body: JSON.stringify(payload)
      }
    );
  },

  send(id: string, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(
        `/purchase-quotations/${id}/send`,
        consolidationId ? null : branch.id,
        consolidationId
      ),
      {
        method: 'POST'
      }
    );
  },

  evaluate(id: string, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(
        `/purchase-quotations/${id}/evaluate`,
        consolidationId ? null : branch.id,
        consolidationId
      ),
      {
        method: 'POST'
      }
    );
  },

  select(id: string, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(
        `/purchase-quotations/${id}/select`,
        consolidationId ? null : branch.id,
        consolidationId
      ),
      {
        method: 'POST'
      }
    );
  },

  reject(id: string, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(
        `/purchase-quotations/${id}/reject`,
        consolidationId ? null : branch.id,
        consolidationId
      ),
      {
        method: 'POST'
      }
    );
  },

  cancel(id: string, consolidationId: string | null = null) {
    return apiFetch<PurchaseQuotation>(
      scopedPath(
        `/purchase-quotations/${id}/cancel`,
        consolidationId ? null : branch.id,
        consolidationId
      ),
      {
        method: 'POST'
      }
    );
  }
};
