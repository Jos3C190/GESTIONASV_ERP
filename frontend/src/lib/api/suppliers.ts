import { apiFetch } from '$lib/api/client';
import type {
  Currency,
  PaymentTerms,
  Supplier,
  SupplierAddress,
  SupplierBankAccount,
  SupplierContact,
  SupplierGroup,
  SupplierImageDraft,
  SupplierTaxIdentifier,
} from '$lib/types/supplier';
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
    legal_name?: string;
    supplier_group_id?: string | null;
    supplier_status?: Supplier['supplier_status'];
    hold_reason?: string | null;
    hold_from?: string | null;
    hold_until?: string | null;
    default_currency_code?: string | null;
    payment_terms_id?: string | null;
    default_payment_method?: string | null;
    external_reference?: string | null;
    image?: SupplierImageDraft | null;
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
    legal_name?: string | null;
    supplier_group_id?: string | null;
    supplier_status?: Supplier['supplier_status'];
    hold_reason?: string | null;
    hold_from?: string | null;
    hold_until?: string | null;
    default_currency_code?: string | null;
    payment_terms_id?: string | null;
    default_payment_method?: string | null;
    external_reference?: string | null;
    image?: SupplierImageDraft | null;
  }>) =>
    apiFetch<Supplier>(`/suppliers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Contacts
  addContact: (
    supplierId: number,
    data: { full_name: string; phone?: string; email?: string; image?: SupplierImageDraft | null }
  ) =>
    apiFetch<SupplierContact>(`/suppliers/${supplierId}/contacts`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateContact: (
    contactId: number,
    data: Partial<{
      full_name: string;
      phone: string;
      email: string;
      is_active: boolean;
      image: SupplierImageDraft | null;
    }>
  ) =>
    apiFetch<SupplierContact>(`/suppliers/contacts/${contactId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deactivateContact: (contactId: number) =>
    apiFetch<SupplierContact>(`/suppliers/contacts/${contactId}/deactivate`, {
      method: 'POST',
    }),

  currencies: () => apiFetch<Currency[]>('/currencies'),
  groups: () => apiFetch<SupplierGroup[]>('/supplier-groups'),
  paymentTerms: () => apiFetch<PaymentTerms[]>('/payment-terms'),
  taxIdentifiers: (supplierId: number) => apiFetch<SupplierTaxIdentifier[]>(`/suppliers/${supplierId}/tax-identifiers`),
  addTaxIdentifier: (supplierId: number, data: Omit<SupplierTaxIdentifier, 'id' | 'supplier_id' | 'normalized_value'>) =>
    apiFetch<SupplierTaxIdentifier>(`/suppliers/${supplierId}/tax-identifiers`, { method: 'POST', body: JSON.stringify(data) }),
  updateTaxIdentifier: (supplierId: number, id: string, data: Partial<Omit<SupplierTaxIdentifier, 'id' | 'supplier_id' | 'normalized_value'>>) =>
    apiFetch<SupplierTaxIdentifier>(`/suppliers/${supplierId}/tax-identifiers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeTaxIdentifier: (supplierId: number, id: string) =>
    apiFetch<void>(`/suppliers/${supplierId}/tax-identifiers/${id}`, { method: 'DELETE' }),
  addresses: (supplierId: number) => apiFetch<SupplierAddress[]>(`/suppliers/${supplierId}/addresses`),
  addAddress: (supplierId: number, data: Omit<SupplierAddress, 'id' | 'supplier_id'>) =>
    apiFetch<SupplierAddress>(`/suppliers/${supplierId}/addresses`, { method: 'POST', body: JSON.stringify(data) }),
  updateAddress: (supplierId: number, id: string, data: Partial<Omit<SupplierAddress, 'id' | 'supplier_id'>>) =>
    apiFetch<SupplierAddress>(`/suppliers/${supplierId}/addresses/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeAddress: (supplierId: number, id: string) =>
    apiFetch<void>(`/suppliers/${supplierId}/addresses/${id}`, { method: 'DELETE' }),
  bankAccounts: (supplierId: number) => apiFetch<SupplierBankAccount[]>(`/suppliers/${supplierId}/bank-accounts`),
  addBankAccount: (supplierId: number, data: { bank_name: string; account_holder: string; account_number: string; iban?: string | null; country_id?: number | null; currency_code?: string | null; account_type?: string | null; is_primary?: boolean; is_verified?: boolean; status?: 'active' | 'blocked' | 'closed' }) =>
    apiFetch<SupplierBankAccount>(`/suppliers/${supplierId}/bank-accounts`, { method: 'POST', body: JSON.stringify(data) }),
  updateBankAccount: (supplierId: number, id: string, data: Partial<{ bank_name: string; account_holder: string; account_number: string; iban?: string | null; country_id?: number | null; currency_code?: string | null; account_type?: string | null; is_primary?: boolean; is_verified?: boolean; status?: 'active' | 'blocked' | 'closed' }>) =>
    apiFetch<SupplierBankAccount>(`/suppliers/${supplierId}/bank-accounts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
};
