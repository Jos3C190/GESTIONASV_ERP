import { apiFetch, type Page } from '$lib/api/client';
import type {
  Retaceo,
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
  }
};
