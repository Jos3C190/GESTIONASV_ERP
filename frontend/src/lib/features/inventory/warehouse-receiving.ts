import { apiFetch, type Page } from '$lib/api/client';

export interface WarehouseReceipt {
  id: string;
  code: string;
  warehouse_id: string;
  purchase_date: string;
  status: string;
  ready: boolean;
  retaceo_code: string | null;
  lines: Array<{
    id: string;
    product_name: string;
    product_sku: string;
    unit_symbol: string;
    quantity_received: string;
    quantity_accepted: string | null;
  }>;
}

export const warehouseReceivingApi = {
  list(warehouseId: string, page: number) {
    return apiFetch<Page<WarehouseReceipt>>(
      `/warehouse-receipts?${new URLSearchParams({ warehouse_id: warehouseId, page: String(page), size: '10' })}`
    );
  },
  verify(
    id: string,
    lines: Array<{
      purchase_detail_id: string;
      quantity_accepted: string;
      inventory_location_id: string | null;
    }>
  ) {
    return apiFetch<WarehouseReceipt>(`/warehouse-receipts/${id}/verify`, {
      method: 'POST',
      body: JSON.stringify({ lines })
    });
  }
};
