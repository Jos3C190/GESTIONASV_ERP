import { apiFetch, type Page } from '$lib/api/client';
import type {
  Customer,
  CustomerCreateInput,
  CustomerInput,
  CustomerListParams,
  DeliveryAddress,
  DeliveryAddressInput
} from '$lib/types/customer';

const BASE = '/customers';

function json(method: string, payload: unknown): RequestInit {
  return { method, body: JSON.stringify(payload) };
}

export const customersApi = {
  list(params: CustomerListParams = {}) {
    const query = new URLSearchParams();
    if (params.search?.trim()) query.set('search', params.search.trim());
    if (params.customer_type) query.set('customer_type', params.customer_type);
    if (params.active !== undefined && params.active !== null) {
      query.set('active', String(params.active));
    }
    if (params.include_generic) query.set('include_generic', 'true');
    query.set('page', String(params.page ?? 1));
    query.set('size', String(params.size ?? 20));
    return apiFetch<Page<Customer>>(`${BASE}?${query.toString()}`);
  },

  get(id: string) {
    return apiFetch<Customer>(`${BASE}/${id}`);
  },

  create(payload: CustomerCreateInput) {
    return apiFetch<Customer>(BASE, json('POST', payload));
  },

  update(id: string, payload: CustomerInput) {
    return apiFetch<Customer>(`${BASE}/${id}`, json('PUT', payload));
  },

  setActive(id: string, isActive: boolean) {
    return apiFetch<Customer>(`${BASE}/${id}/status`, json('PATCH', { is_active: isActive }));
  },

  generic(branchId: string) {
    return apiFetch<Customer>(`${BASE}/generic?branch_id=${encodeURIComponent(branchId)}`);
  },

  addDeliveryAddress(customerId: string, payload: DeliveryAddressInput) {
    return apiFetch<DeliveryAddress>(
      `${BASE}/${customerId}/delivery-addresses`,
      json('POST', payload)
    );
  },

  updateDeliveryAddress(customerId: string, addressId: string, payload: DeliveryAddressInput) {
    return apiFetch<DeliveryAddress>(
      `${BASE}/${customerId}/delivery-addresses/${addressId}`,
      json('PUT', payload)
    );
  },

  deleteDeliveryAddress(customerId: string, addressId: string) {
    return apiFetch<void>(`${BASE}/${customerId}/delivery-addresses/${addressId}`, {
      method: 'DELETE'
    });
  }
};
