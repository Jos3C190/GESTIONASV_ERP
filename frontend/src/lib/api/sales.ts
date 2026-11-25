import { apiFetch } from '#lib/api/client.ts';
import { branch } from '#lib/stores/branch.svelte.ts';
import type {
  Sale,
  SalesCatalogItem,
  SalesDelivery,
  SalesDeliveryStockLine,
  SalesFilters,
  SalesPage,
  SalesReturn,
  SalesReturnCondition,
  SalesReturnableAllocation,
  SalesQuotation,
  QuotationDraftInput,
  QuotationSettings,
  OrderSettings,
  OrderDelivery,
  OrderDraftInput
} from '#lib/types/sales.ts';

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
  catalog() {
    return apiFetch<SalesCatalogItem[]>('/sales/catalog');
  },
  quotations(filters: SalesFilters = {}) {
    return apiFetch<SalesPage<SalesQuotation>>(scopedPath('/sales/quotations', filters));
  },
  quotation(id: string) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}`);
  },
  previewQuotation(payload: QuotationDraftInput) {
    return apiFetch<SalesQuotation>('/sales/quotations/preview', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  createQuotation(payload: QuotationDraftInput, idempotencyKey: string) {
    return apiFetch<SalesQuotation>('/sales/quotations', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  updateQuotation(id: string, payload: QuotationDraftInput & { expected_version: number }) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },
  quotationAction(
    id: string,
    action: 'issue' | 'authorize' | 'return' | 'accept' | 'reject' | 'cancel',
    payload: { expected_version: number; note?: string | null; reason?: string }
  ) {
    return apiFetch<SalesQuotation>(`/sales/quotations/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  quotationPdfPath(id: string) {
    return `/sales/quotations/${id}/pdf`;
  },
  quotationSettings() {
    return apiFetch<QuotationSettings>('/sales/settings/quotations');
  },
  saveQuotationSettings(payload: QuotationSettings) {
    return apiFetch<QuotationSettings>('/sales/settings/quotations', {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },
  orderSettings() {
    return apiFetch<OrderSettings>('/sales/settings/orders');
  },
  saveOrderSettings(payload: OrderSettings) {
    return apiFetch<OrderSettings>('/sales/settings/orders', {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },
  orderFromQuotation(
    quotationId: string,
    payload: OrderDelivery & { notes?: string | null },
    idempotencyKey: string
  ) {
    return apiFetch<Sale>(`/sales/quotations/${quotationId}/order`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  sales(filters: SalesFilters = {}) {
    return apiFetch<SalesPage<Sale>>(scopedPath('/sales', filters));
  },
  sale(id: string) {
    return apiFetch<Sale>(`/sales/${id}`);
  },
  previewOrder(payload: OrderDraftInput) {
    return apiFetch<Sale>('/sales/preview', { method: 'POST', body: JSON.stringify(payload) });
  },
  createOrder(payload: OrderDraftInput, idempotencyKey: string) {
    return apiFetch<Sale>('/sales', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  updateOrder(id: string, payload: OrderDraftInput & { expected_version: number }) {
    return apiFetch<Sale>(`/sales/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  orderAction(
    id: string,
    action: 'confirm' | 'authorize' | 'authorize-credit' | 'return' | 'cancel',
    payload: { expected_version: number; note?: string | null; reason?: string }
  ) {
    return apiFetch<Sale>(`/sales/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
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
  createDelivery(
    id: string,
    payload: {
      notes: string | null;
      assignments: Array<{ sale_line_id: string; handling_unit_id: string }>;
    },
    idempotencyKey: string
  ) {
    return apiFetch<SalesDelivery>(`/sales/${id}/deliveries`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    });
  },
  updateDelivery(
    id: string,
    payload: {
      expected_version: number;
      notes: string | null;
      assignments: Array<{ sale_line_id: string; handling_unit_id: string }>;
    }
  ) {
    return apiFetch<SalesDelivery>(`/sales/deliveries/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
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
  createReturn(
    id: string,
    payload: {
      notes: string | null;
      document_ids: string[];
      lines: Array<{
        delivery_allocation_id: string;
        quantity_base: string;
        reason: string;
        declared_condition: SalesReturnCondition;
      }>;
    },
    idempotencyKey: string
  ) {
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
  resolveReturn(
    id: string,
    payload: {
      lines: Array<{
        return_line_id: string;
        decision: 'accepted' | 'rejected';
        quantity_base: string;
        condition: SalesReturnCondition;
        reason: string;
        destination_location_id?: string | null;
      }>;
    },
    idempotencyKey: string
  ) {
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
