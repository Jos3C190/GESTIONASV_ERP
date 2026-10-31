import { apiFetch, type Page } from '$lib/api/client';
import { branch } from '$lib/stores/branch.svelte';
import type {
  Sale,
  SalesCatalogItem,
  SalesCustomer,
  SalesDelivery,
  SalesDeliveryStockLine,
  SalesFilters,
  SalesLineInput,
  SalesPage,
  SalesReturn,
  SalesReturnCondition,
  SalesReturnableAllocation,
  SalesQuotation
} from '$lib/types/sales';

function scopedPath(path: string, filters: SalesFilters = {}): string {
  const query = new URLSearchParams();
  const branchId = filters.branch_id === undefined ? branch.id : filters.branch_id;
  if (branchId) query.set('branch_id', branchId);
  if (filters.customer_id) query.set('customer_id', filters.customer_id);
  if (filters.status) query.set('status', filters.status);
  if (filters.from_date) query.set('from_date', filters.from_date);
  if (filters.to_date) query.set('to_date', filters.to_date);
  query.set('page', String(filters.page ?? 1));
  query.set('size', String(filters.size ?? 20));
  const encoded = query.toString();
  return encoded ? `${path}?${encoded}` : path;
}

export const salesApi = {
  customers(params: { search?: string; active?: boolean | null; page?: number; size?: number } = {}) {
    const query = new URLSearchParams();
    if (params.search?.trim()) query.set('search', params.search.trim());
    if (params.active !== undefined && params.active !== null) query.set('active', String(params.active));
    query.set('page', String(params.page ?? 1));
    query.set('size', String(params.size ?? 100));
    return apiFetch<Page<SalesCustomer>>(`/sales/customers?${query.toString()}`);
  },
  createCustomer(payload: Pick<SalesCustomer, 'code' | 'name' | 'phone' | 'email'>) {
    return apiFetch<SalesCustomer>('/sales/customers', { method: 'POST', body: JSON.stringify(payload) });
  },
  updateCustomer(id: string, payload: Partial<Pick<SalesCustomer, 'name' | 'phone' | 'email' | 'is_active'>>) {
    return apiFetch<SalesCustomer>(`/sales/customers/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
  },
  catalog() {
    return apiFetch<SalesCatalogItem[]>('/sales/catalog');
  },
  quotations(filters: SalesFilters = {}) {
    return apiFetch<SalesPage<SalesQuotation>>(scopedPath('/sales/quotations', filters));
  },
  quotation(id: string) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}`);
  },
  createQuotation(payload: {
    branch_id: string;
    customer_id: string;
    valid_until: string;
    currency: 'USD';
    notes: string | null;
    lines: SalesLineInput[];
  }, idempotencyKey: string) {
    return apiFetch<SalesQuotation>('/sales/quotations', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  updateQuotation(id: string, payload: {
    expected_version: number;
    valid_until: string;
    currency: 'USD';
    notes: string | null;
    lines: SalesLineInput[];
  }) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  confirmQuotation(id: string, expected_version: number) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}/confirm`, { method: 'POST', body: JSON.stringify({ expected_version }) });
  },
  cancelQuotation(id: string, expected_version: number, reason: string) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}/cancel`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) });
  },
  convertQuotation(id: string, expected_version: number, idempotencyKey: string) {
    return apiFetch<Sale>(`/sales/quotations/${id}/convert`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ expected_version })
    });
  },
  sales(filters: SalesFilters = {}) {
    return apiFetch<SalesPage<Sale>>(scopedPath('/sales', filters));
  },
  sale(id: string) {
    return apiFetch<Sale>(`/sales/${id}`);
  },
  updateSale(id: string, payload: {
    expected_version: number;
    notes: string | null;
    lines: Array<{ source_quotation_line_id: string; quantity: string; unit_price: string }>;
  }) {
    return apiFetch<Sale>(`/sales/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  confirmSale(id: string, expected_version: number) {
    return apiFetch<Sale>(`/sales/${id}/confirm`, { method: 'POST', body: JSON.stringify({ expected_version }) });
  },
  cancelSale(id: string, expected_version: number, reason: string) {
    return apiFetch<Sale>(`/sales/${id}/cancel`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) });
  },
  deliveryStock(id: string) {
    return apiFetch<SalesDeliveryStockLine[]>(`/sales/${id}/delivery-stock`);
  },
  deliveriesForSale(id: string) {
    return apiFetch<SalesDelivery[]>(`/sales/${id}/deliveries`);
  },
  delivery(id: string) {
    return apiFetch<SalesDelivery>(`/sales/deliveries/${id}`);
  },
  createDelivery(id: string, payload: { notes: string | null; assignments: Array<{ sale_line_id: string; handling_unit_id: string }> }, idempotencyKey: string) {
    return apiFetch<SalesDelivery>(`/sales/${id}/deliveries`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  updateDelivery(id: string, payload: { expected_version: number; notes: string | null; assignments: Array<{ sale_line_id: string; handling_unit_id: string }> }) {
    return apiFetch<SalesDelivery>(`/sales/deliveries/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  confirmDelivery(id: string, expected_version: number, idempotencyKey: string) {
    return apiFetch<SalesDelivery>(`/sales/deliveries/${id}/confirm`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ expected_version })
    });
  },
  cancelDelivery(id: string, expected_version: number, reason: string) {
    return apiFetch<SalesDelivery>(`/sales/deliveries/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ expected_version, reason })
    });
  },
  returnableAllocations(id: string) {
    return apiFetch<SalesReturnableAllocation[]>(`/sales/${id}/returnable-allocations`);
  },
  returnsForSale(id: string) {
    return apiFetch<SalesReturn[]>(`/sales/${id}/returns`);
  },
  returns() {
    const query = new URLSearchParams();
    if (branch.id) query.set('branch_id', branch.id);
    const suffix = query.size ? `?${query.toString()}` : '';
    return apiFetch<SalesReturn[]>(`/sales/returns${suffix}`);
  },
  createReturn(id: string, payload: {
    notes: string | null;
    document_ids: string[];
    lines: Array<{ delivery_allocation_id: string; quantity_base: string; reason: string; declared_condition: SalesReturnCondition }>;
  }, idempotencyKey: string) {
    return apiFetch<SalesReturn>(`/sales/${id}/returns`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  receiveReturn(id: string, idempotencyKey: string) {
    return apiFetch<SalesReturn>(`/sales/returns/${id}/receive`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey }
    });
  },
  resolveReturn(id: string, payload: { lines: Array<{
    return_line_id: string;
    decision: 'accepted' | 'rejected';
    quantity_base: string;
    condition: SalesReturnCondition;
    reason: string;
    destination_location_id?: string | null;
  }> }, idempotencyKey: string) {
    return apiFetch<SalesReturn>(`/sales/returns/${id}/resolve`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  cancelReturn(id: string, reason: string, idempotencyKey: string) {
    return apiFetch<SalesReturn>(`/sales/returns/${id}/cancel`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ reason })
    });
  }
};
