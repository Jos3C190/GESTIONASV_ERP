import { apiFetch } from '$lib/api/client';
import type {
  ApprovedRequestCandidatePage,
  BranchDemandLevel,
  PurchaseConsolidation,
  PurchaseConsolidationAwardBoard,
  PurchaseConsolidationInventorySnapshot,
  SelectedPurchaseRequestResolution,
  PurchaseWorkItemPage,
  PurchaseWorkItemType
} from '$lib/types/purchase-consolidation';
import type { PurchaseRequestStatus } from '$lib/types/purchase-request';

export interface PurchaseWorkItemFilters {
  type?: PurchaseWorkItemType;
  status?: PurchaseRequestStatus | 'frozen' | 'closed';
  q?: string;
  branch_id?: string;
  warehouse_id?: string;
  category_id?: number;
  date_from?: string;
  date_to?: string;
  consolidation_id?: string;
  page?: number;
  size?: number;
}

function queryString(values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && String(value).trim()) query.set(key, String(value));
  }
  return query.toString();
}

export const purchaseConsolidationsApi = {
  listWorkItems: (filters: PurchaseWorkItemFilters = {}) => {
    const search = queryString({ ...filters, type: filters.type, status: filters.status });
    return apiFetch<PurchaseWorkItemPage>(`/purchase-work-items${search ? `?${search}` : ''}`);
  },

  eligibleRequests: (params: {
    date_from: string;
    date_to: string;
    branch_id?: string;
    warehouse_id?: string;
    q?: string;
    request_ids?: string[];
    page?: number;
    size?: number;
  }) => {
    const { request_ids, ...filters } = params;
    const search = new URLSearchParams(queryString(filters));
    for (const requestId of request_ids ?? []) search.append('request_ids', requestId);
    return apiFetch<ApprovedRequestCandidatePage>(`/purchase-consolidations/eligible-requests?${search}`);
  },

  resolveSelectedRequests: (requestIds: string[]) => {
    const search = new URLSearchParams();
    for (const requestId of requestIds) search.append('request_ids', requestId);
    return apiFetch<SelectedPurchaseRequestResolution[]>(
      `/purchase-consolidations/selected-requests?${search}`
    );
  },

  create: (data: {
    request_ids: string[];
    demand_levels?: { branch_id: string; product_id: number; level: BranchDemandLevel }[];
    period_start: string;
    period_end: string;
    central_warehouse_id?: string | null;
    notes?: string | null;
  }) => apiFetch<PurchaseConsolidation>('/purchase-consolidations', {
    method: 'POST',
    body: JSON.stringify(data)
  }),

  get: (id: string) => apiFetch<PurchaseConsolidation>(`/purchase-consolidations/${id}`),

  getAwardBoard: (id: string) =>
    apiFetch<PurchaseConsolidationAwardBoard>(`/purchase-consolidations/${id}/adjudication`),

  award: (
    id: string,
    data: {
      consolidation_line_id: string;
      quotation_id: string;
      quotation_detail_id: string;
      quantity: string;
      reason: string;
    }
  ) => apiFetch<PurchaseConsolidationAwardBoard>(`/purchase-consolidations/${id}/awards`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),

  revokeAward: (id: string, awardId: string, reason: string) =>
    apiFetch<PurchaseConsolidationAwardBoard>(
      `/purchase-consolidations/${id}/awards/${awardId}/revoke`,
      { method: 'POST', body: JSON.stringify({ reason }) }
    ),

  inventorySnapshot: (id: string) =>
    apiFetch<PurchaseConsolidationInventorySnapshot>(
      `/purchase-consolidations/${id}/inventory-snapshot`
    ),

  addRequests: (id: string, data: { request_ids: string[]; reason: string }) =>
    apiFetch<PurchaseConsolidation>(`/purchase-consolidations/${id}/requests`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  update: (
    id: string,
    data: {
      change_reason: string;
      source_changes: {
        source_id: string;
        included_quantity: number;
        reason: string;
        demand_level?: BranchDemandLevel | null;
      }[];
      central_demands: { line_id?: string; product_id: number; quantity: number; reason: string }[];
      notes?: string | null;
      central_warehouse_id?: string | null;
    }
  ) => apiFetch<PurchaseConsolidation>(`/purchase-consolidations/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),

  cancel: (id: string, reason: string) =>
    apiFetch<PurchaseConsolidation>(`/purchase-consolidations/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    }),

  close: (id: string, reason: string, coveredOutsideConsolidation = false) =>
    apiFetch<PurchaseConsolidation>(`/purchase-consolidations/${id}/close`, {
      method: 'POST',
      body: JSON.stringify({
        reason,
        covered_outside_consolidation: coveredOutsideConsolidation
      })
    })
};
