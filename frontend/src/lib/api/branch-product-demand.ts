import { apiFetch } from '$lib/api/client';

export type BranchDemandLevel = 'low' | 'medium' | 'high';

export interface BranchDemandUnitTotal {
  unit_id: number;
  unit_name: string;
  unit_symbol: string;
  quantity: number;
}

export interface BranchProductDemandItem {
  product_id: number;
  sku: string;
  product_name: string;
  request_count: number;
  last_requested_at: string;
  unit_totals: BranchDemandUnitTotal[];
  demand_level: BranchDemandLevel | null;
}

export interface BranchProductDemandResponse {
  branch_id: string;
  period_start: string;
  period_end: string;
  items: BranchProductDemandItem[];
}

export const branchProductDemandApi = {
  list: (branchId: string, dateFrom: string, dateTo: string) => {
    const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
    return apiFetch<BranchProductDemandResponse>(
      `/branches/${branchId}/product-demand?${params.toString()}`
    );
  },

  setLevel: (branchId: string, productId: number, level: BranchDemandLevel | null) =>
    apiFetch<{
      branch_id: string;
      product_id: number;
      level: BranchDemandLevel | null;
      updated_at: string | null;
    }>(`/branches/${branchId}/product-demand/${productId}`, {
      method: 'PUT',
      body: JSON.stringify({ level })
    })
};
