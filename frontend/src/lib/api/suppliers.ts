import { apiFetch } from '$lib/api/client';
import type { Supplier, SupplierContact } from '$lib/types/supplier';
import type { PageResponse } from '$lib/api/catalog';

export interface SupplierStats {
  total: number;
  active: number;
  inactive: number;
  countries: number;
}

export const suppliersApi = {
  listSuppliers: (params?: {
    country_id?: number;
    search?: string;
    active_only?: boolean;
    page?: number;
    size?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.country_id) q.append('country_id', params.country_id.toString());
    if (params?.search) q.append('search', params.search);
    if (params?.active_only !== undefined) q.append('active_only', params.active_only.toString());
    if (params?.page) q.append('page', params.page.toString());
    if (params?.size) q.append('size', params.size.toString());
    return apiFetch<PageResponse<Supplier>>(`/suppliers?${q.toString()}`);
  },

  stats: () => apiFetch<SupplierStats>('/suppliers/stats'),

  getSupplier: (id: number) =>
    apiFetch<Supplier>(`/suppliers/${id}`),

  createSupplier: (data: {
    code: string;
    name: string;
    country: number;
    address?: string;
    phone?: string;
    email?: string;
    website?: string;
  }) =>
    apiFetch<Supplier>('/suppliers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateSupplier: (id: number, data: Partial<{
    code: string;
    name: string;
    country: number;
    address: string;
    phone: string;
    email: string;
    website: string;
    is_active: boolean;
  }>) =>
    apiFetch<Supplier>(`/suppliers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Contacts
  addContact: (supplierId: number, data: { full_name: string; phone?: string; email?: string }) =>
    apiFetch<SupplierContact>(`/suppliers/${supplierId}/contacts`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateContact: (contactId: number, data: Partial<{ full_name: string; phone: string; email: string; is_active: boolean }>) =>
    apiFetch<SupplierContact>(`/suppliers/contacts/${contactId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteContact: (contactId: number) =>
    apiFetch<{ message: string }>(`/suppliers/contacts/${contactId}`, {
      method: 'DELETE',
    }),
};
