import { apiFetch } from '$lib/api/client';
import type {
  BranchOption,
  CatalogItem,
  CatalogSummary,
  DocumentTypeInput,
  DocumentTypeSetting,
  EconomicActivity,
  Establishment,
  EstablishmentInput,
  EstablishmentUpdateInput,
  FiscalProfile,
  FiscalProfileInput,
  PointOfSale,
  PointOfSaleInput,
  PointOfSaleUpdateInput
} from '$lib/types/fiscal';

const BASE = '/fiscal';

function json(method: string, payload: unknown): RequestInit {
  return { method, body: JSON.stringify(payload) };
}

export const fiscalApi = {
  listCatalogs() {
    return apiFetch<CatalogSummary[]>(`${BASE}/catalogs`);
  },

  catalog(code: string, params: { group?: string; search?: string; limit?: number } = {}) {
    const query = new URLSearchParams();
    if (params.group !== undefined) query.set('group', params.group);
    if (params.search) query.set('search', params.search);
    if (params.limit) query.set('limit', String(params.limit));
    const suffix = query.toString();
    return apiFetch<CatalogItem[]>(
      `${BASE}/catalogs/${encodeURIComponent(code)}${suffix ? `?${suffix}` : ''}`
    );
  },

  getProfile() {
    return apiFetch<FiscalProfile>(`${BASE}/profile`);
  },

  updateProfile(payload: FiscalProfileInput) {
    return apiFetch<FiscalProfile>(`${BASE}/profile`, json('PUT', payload));
  },

  listActivities() {
    return apiFetch<EconomicActivity[]>(`${BASE}/activities`);
  },

  addActivity(code: string, isPrimary = false) {
    return apiFetch<EconomicActivity>(
      `${BASE}/activities`,
      json('POST', { code, is_primary: isPrimary })
    );
  },

  setPrimaryActivity(id: string) {
    return apiFetch<EconomicActivity>(`${BASE}/activities/${id}/primary`, { method: 'POST' });
  },

  deleteActivity(id: string) {
    return apiFetch<void>(`${BASE}/activities/${id}`, { method: 'DELETE' });
  },

  listBranchOptions() {
    return apiFetch<BranchOption[]>(`${BASE}/branch-options`);
  },

  listEstablishments() {
    return apiFetch<Establishment[]>(`${BASE}/establishments`);
  },

  createEstablishment(payload: EstablishmentInput) {
    return apiFetch<Establishment>(`${BASE}/establishments`, json('POST', payload));
  },

  updateEstablishment(id: string, payload: EstablishmentUpdateInput) {
    return apiFetch<Establishment>(`${BASE}/establishments/${id}`, json('PATCH', payload));
  },

  createPointOfSale(establishmentId: string, payload: PointOfSaleInput) {
    return apiFetch<PointOfSale>(
      `${BASE}/establishments/${establishmentId}/points-of-sale`,
      json('POST', payload)
    );
  },

  updatePointOfSale(id: string, payload: PointOfSaleUpdateInput) {
    return apiFetch<PointOfSale>(`${BASE}/points-of-sale/${id}`, json('PATCH', payload));
  },

  listDocumentTypes() {
    return apiFetch<DocumentTypeSetting[]>(`${BASE}/document-types`);
  },

  updateDocumentType(documentType: string, payload: DocumentTypeInput) {
    return apiFetch<DocumentTypeSetting>(
      `${BASE}/document-types/${documentType}`,
      json('PUT', payload)
    );
  }
};
