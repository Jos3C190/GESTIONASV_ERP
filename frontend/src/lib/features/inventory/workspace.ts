import { apiFetch } from '$lib/api/client';
import type { AdjustmentOptions } from './adjustments';

export const workspaceField = 'min-h-11 w-full rounded-lg border border-border-control bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
export interface StockRow {
  inventory_item_id: string; product_name: string; sku: string | null; base_unit_symbol: string;
  location_id: string; location_code: string; stock_status: string; lot_code: string | null;
  expiry_date: string | null; quantity_base: string;
}
export interface StockPage { items: StockRow[]; total: number; page: number; size: number }
export const workspaceApi = {
  stock(warehouseId: string, filters: { q?: string; location_id?: string; stock_status?: string; page?: number }, signal?: AbortSignal) {
    const query = new URLSearchParams({ size: '25' });
    for (const [key, value] of Object.entries(filters)) if (value) query.set(key, String(value));
    return apiFetch<StockPage>(`/inventory/warehouses/${warehouseId}/stock?${query}`, { signal });
  },
  searchItems(warehouseId: string, q: string, offset: number) {
    return apiFetch<AdjustmentOptions>(`/inventory/warehouses/${warehouseId}/workspace-items?${new URLSearchParams({ q, offset: String(offset) })}`);
  },
  opening(body: Record<string, unknown>) {
    return apiFetch<{ id: string; source_reference: string }>('/inventory/product-opening', { method: 'POST', body: JSON.stringify(body) });
  }
};
