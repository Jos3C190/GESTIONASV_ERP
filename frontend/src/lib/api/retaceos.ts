import { apiFetch, type Page } from '$lib/api/client';
import type {
  Retaceo,
  RetaceoAverageComparison,
  RetaceoCostDocument,
  RetaceoCostDocumentDownloadUrl,
  RetaceoCostDocumentUpload,
  RetaceoCreateInput,
  RetaceoListParams,
  RetaceoUpdateInput
} from '$lib/types/retaceo';

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export const retaceosApi = {
  list(params?: RetaceoListParams) {
    const query = new URLSearchParams();

    if (params?.status) query.set('status', params.status);
    if (params?.purchase_id) query.set('purchase_id', params.purchase_id);
    if (params?.branch_id) query.set('branch_id', params.branch_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.size) query.set('size', String(params.size));

    return apiFetch<Page<Retaceo>>(queryPath('/retaceos', query));
  },

  get(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}`);
  },

  create(payload: RetaceoCreateInput) {
    return apiFetch<Retaceo>('/retaceos', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  update(id: string, payload: RetaceoUpdateInput) {
    return apiFetch<Retaceo>(`/retaceos/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  calculate(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}/calculate`, {
      method: 'POST'
    });
  },

  verify(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}/verify`, {
      method: 'POST'
    });
  },

  cancel(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}/cancel`, {
      method: 'POST'
    });
  },

  close(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}/close`, {
      method: 'POST'
    });
  },

  valuationStatus(id: string) {
    return apiFetch<{ enabled: boolean; inventory_after_retaceo: boolean }>(
      `/retaceos/${id}/valuation-status`
    );
  },

  averageComparison(id: string) {
    return apiFetch<RetaceoAverageComparison>(`/retaceos/${id}/average-comparison`);
  },

  apply(id: string) {
    return apiFetch<Retaceo>(`/retaceos/${id}/apply`, { method: 'POST' });
  },

  initiateCostDocument(
    retaceoId: string,
    costId: string,
    payload: {
      file_name: string;
      content_type: string;
      size_bytes: number;
      checksum_sha256: string;
    }
  ) {
    return apiFetch<RetaceoCostDocumentUpload>(
      `/retaceos/${retaceoId}/costs/${costId}/documents/uploads`,
      { method: 'POST', body: JSON.stringify(payload) }
    );
  },

  completeCostDocument(retaceoId: string, costId: string, documentId: string) {
    return apiFetch<RetaceoCostDocument>(
      `/retaceos/${retaceoId}/costs/${costId}/documents/${documentId}/complete`,
      { method: 'POST' }
    );
  },

  removeCostDocument(retaceoId: string, costId: string, documentId: string) {
    return apiFetch<void>(`/retaceos/${retaceoId}/costs/${costId}/documents/${documentId}`, {
      method: 'DELETE'
    });
  },

  listCostDocuments(retaceoId: string, costId: string) {
    return apiFetch<RetaceoCostDocument[]>(`/retaceos/${retaceoId}/costs/${costId}/documents`);
  },

  createCostDocumentDownloadUrl(retaceoId: string, costId: string, documentId: string) {
    return apiFetch<RetaceoCostDocumentDownloadUrl>(
      `/retaceos/${retaceoId}/costs/${costId}/documents/${documentId}/download-url`,
      { method: 'POST' }
    );
  }
};
