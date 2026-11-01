/**
 * Documents owned by a business entity (vehicle, driver), served by the
 * backend's owned-documents routers under `{basePath}/documents`.
 */
import {
  apiFetch,
  type DocumentCategoryOut,
  type DocumentMetadataInput,
  type DocumentRecordOut,
  type DocumentUploadInput,
  type DocumentUploadTicket
} from '$lib/api/client';

export interface OwnedDocumentsPage {
  items: DocumentRecordOut[];
  meta: { page: number; size: number; total: number; pages: number };
}

export interface OwnedDocumentsApi {
  basePath: string;
  categories: () => Promise<DocumentCategoryOut[]>;
  get: (id: string) => Promise<DocumentRecordOut>;
  list: (params?: {
    page?: number;
    size?: number;
    category_id?: string;
    search?: string;
    status?: string;
    include_versions?: boolean;
  }) => Promise<OwnedDocumentsPage>;
  initiate: (data: DocumentUploadInput) => Promise<DocumentUploadTicket>;
  complete: (id: string) => Promise<DocumentRecordOut>;
  update: (id: string, data: DocumentMetadataInput) => Promise<DocumentRecordOut>;
  replace: (id: string, data: DocumentUploadInput) => Promise<DocumentUploadTicket>;
  versions: (id: string) => Promise<DocumentRecordOut[]>;
  previewUrl: (id: string) => Promise<{ url: string; expires_at: string }>;
  downloadUrl: (id: string) => Promise<{ url: string; expires_at: string }>;
}

export function ownedDocuments(basePath: string): OwnedDocumentsApi {
  const root = `${basePath}/documents`;
  return {
    basePath,
    categories: () => apiFetch<DocumentCategoryOut[]>(`${root}/categories`),
    get: (id) => apiFetch<DocumentRecordOut>(`${root}/${id}`),
    list: (params = {}) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') query.set(key, String(value));
      }
      return apiFetch<OwnedDocumentsPage>(`${root}?${query.toString()}`);
    },
    initiate: (data) =>
      apiFetch<DocumentUploadTicket>(`${root}/uploads`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    complete: (id) => apiFetch<DocumentRecordOut>(`${root}/${id}/complete`, { method: 'POST' }),
    update: (id, data) =>
      apiFetch<DocumentRecordOut>(`${root}/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    replace: (id, data) =>
      apiFetch<DocumentUploadTicket>(`${root}/${id}/replace`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    versions: (id) => apiFetch<DocumentRecordOut[]>(`${root}/${id}/versions`),
    previewUrl: (id) =>
      apiFetch<{ url: string; expires_at: string }>(`${root}/${id}/preview-url`, {
        method: 'POST'
      }),
    downloadUrl: (id) =>
      apiFetch<{ url: string; expires_at: string }>(`${root}/${id}/download-url`, {
        method: 'POST'
      })
  };
}
