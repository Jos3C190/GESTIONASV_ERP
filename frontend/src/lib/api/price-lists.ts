import { apiFetch } from '$lib/api/client';
import type {
  ListedPrice,
  PriceEntry,
  PriceInput,
  PriceList,
  PriceListInput
} from '$lib/types/price-list';

const BASE = '/price-lists';

function json(method: string, payload: unknown): RequestInit {
  return { method, body: JSON.stringify(payload) };
}

export const priceListsApi = {
  list() {
    return apiFetch<PriceList[]>(BASE);
  },
  get(id: string) {
    return apiFetch<PriceList>(`${BASE}/${id}`);
  },
  create(payload: PriceListInput) {
    return apiFetch<PriceList>(BASE, json('POST', payload));
  },
  update(id: string, payload: PriceListInput) {
    return apiFetch<PriceList>(`${BASE}/${id}`, json('PUT', payload));
  },
  prices(id: string, params: { search?: string; branch_id?: string | null; on?: string | null }) {
    const query = new URLSearchParams();
    if (params.search?.trim()) query.set('search', params.search.trim());
    if (params.branch_id) query.set('branch_id', params.branch_id);
    if (params.on) query.set('on', params.on);
    const suffix = query.toString();
    return apiFetch<ListedPrice[]>(`${BASE}/${id}/prices${suffix ? `?${suffix}` : ''}`);
  },
  history(id: string, unit: { product_id: number; variant_id: string | null; unit_id: number }) {
    const query = new URLSearchParams({
      product_id: String(unit.product_id),
      unit_id: String(unit.unit_id)
    });
    if (unit.variant_id) query.set('variant_id', unit.variant_id);
    return apiFetch<PriceEntry[]>(`${BASE}/${id}/history?${query.toString()}`);
  },
  setPrice(id: string, payload: PriceInput) {
    return apiFetch<PriceEntry>(`${BASE}/${id}/prices`, json('POST', payload));
  },
  endPrice(entryId: string, endsOn: string) {
    return apiFetch<PriceEntry>(`${BASE}/items/${entryId}/end`, json('POST', { ends_on: endsOn }));
  },
  cancelPrice(entryId: string) {
    return apiFetch<void>(`${BASE}/items/${entryId}`, { method: 'DELETE' });
  }
};
