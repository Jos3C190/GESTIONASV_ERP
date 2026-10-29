import { apiFetch } from '$lib/api/client';
import { company } from '$lib/stores/company.svelte';

export type AdjustmentStatus = 'draft' | 'approved' | 'applied' | 'cancelled';
export type AdjustmentDirection = 'increase' | 'decrease';
export type AdjustmentStockStatus = 'available' | 'quarantine' | 'damaged' | 'in_transit';

export interface AdjustmentLineInput {
  inventory_item_id: string;
  location_id: string;
  direction: AdjustmentDirection;
  quantity_base: string;
  stock_status: AdjustmentStockStatus;
  inventory_lot_detail_id?: string | null;
  handling_unit_id?: string | null;
  packaging_definition_id?: string | null;
  documented_unit_cost?: string | null;
  documented_total_cost?: string | null;
  actual_gross_weight_kg?: string | null;
  actual_volume_m3?: string | null;
  transfer_detail_id?: string | null;
}

export interface AdjustmentCreateInput {
  warehouse_id: string;
  operational_date: string;
  accounting_date: string;
  reason: string;
  document_reference: string;
  notes: string | null;
  lines: AdjustmentLineInput[];
  correction_of_id?: string | null;
  transfer_id?: string | null;
  transfer_incident_id?: string | null;
}

export interface AdjustmentLine {
  id: string;
  line_number: number;
  inventory_item_id: string;
  product_name: string;
  sku: string | null;
  base_unit_id: number | null;
  base_unit_name: string;
  base_unit_symbol: string | null;
  warehouse_id: string;
  location_id: string;
  location_code: string | null;
  stock_status: AdjustmentStockStatus;
  direction: AdjustmentDirection;
  quantity_base: string;
  inventory_lot_detail_id: string | null;
  handling_unit_id: string | null;
  handling_unit_code: string | null;
  packaging_definition_id: string | null;
  documented_unit_cost: string | null;
  documented_total_cost: string | null;
  actual_gross_weight_kg: string | null;
  actual_volume_m3: string | null;
  transfer_detail_id: string | null;
  movement_id: string | null;
  movement_line_id: string | null;
}

export interface AdjustmentDocument {
  document_id: string;
  original_filename: string;
  checksum_sha256: string;
  technical_status: string;
  upload_completed: boolean;
  linked_at: string;
  detached_at: string | null;
  active: boolean;
}

export interface InventoryAdjustment {
  id: string;
  company_id: string;
  code: string;
  warehouse_id: string;
  warehouse_name: string;
  branch_id: string | null;
  operational_date: string;
  accounting_date: string;
  reason: string;
  document_reference: string;
  notes: string | null;
  status: AdjustmentStatus;
  version: number;
  approved_version: number | null;
  correction_of_id: string | null;
  transfer_id: string | null;
  transfer_incident_id: string | null;
  created_by_id: string;
  approved_by_id: string | null;
  applied_by_id: string | null;
  created_at: string;
  approved_at: string | null;
  applied_at: string | null;
  cancellation_reason: string | null;
  lines: AdjustmentLine[];
  documents: AdjustmentDocument[];
  events: Array<{
    action: string;
    actor_id: string;
    occurred_at: string;
    reason: string | null;
    version: number;
    details: Record<string, unknown>;
  }>;
}

export interface AdjustmentOptions {
  items: Array<{
    id: string;
    product_name: string;
    sku: string | null;
    base_unit_id: number;
    base_unit_name: string | null;
    base_unit_symbol: string | null;
  }>;
  locations: Array<{ id: string; code: string; location_type: string }>;
}

export interface AdjustmentList {
  items: InventoryAdjustment[];
  total: number;
}

export interface AdjustmentUploadTicket {
  document_id: string;
  upload_url: string;
  method: string;
  required_headers: Record<string, string>;
  expires_at: string;
}

function query(filters: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && String(value).trim()) params.set(key, String(value));
  }
  return params.toString();
}

function idempotencyKey(prefix: string): string {
  return `${prefix}:${crypto.randomUUID()}`;
}

function readOrCreateStoredKey(key: string): string {
  try {
    const saved = localStorage.getItem(key);
    if (saved) return saved;
    const created = idempotencyKey('adj');
    localStorage.setItem(key, created);
    return created;
  } catch {
    return idempotencyKey('adj');
  }
}

function attemptScope(action: string, identity: string): string {
  return `b05-adjustment:${company.id ?? 'no-company'}:${action}:${identity}`;
}

export const inventoryAdjustmentsApi = {
  list: (filters: {
    warehouse_id?: string;
    status?: AdjustmentStatus;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  } = {}) => apiFetch<AdjustmentList>(`/inventory/adjustments?${query(filters)}`),

  options: (warehouseId: string) =>
    apiFetch<AdjustmentOptions>(
      `/inventory/adjustments/options?${query({ warehouse_id: warehouseId })}`
    ),

  get: (adjustmentId: string) =>
    apiFetch<InventoryAdjustment>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}`),

  create: async (body: AdjustmentCreateInput) => {
    const scope = attemptScope('create', JSON.stringify(body));
    const storageKey = `${scope}:key`;
    const idempotency_key = readOrCreateStoredKey(storageKey);
    const result = await apiFetch<InventoryAdjustment>('/inventory/adjustments', {
      method: 'POST',
      body: JSON.stringify({ ...body, idempotency_key })
    });
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // The server accepted the request; keeping no local retry record is safe.
    }
    return result;
  },

  update: (adjustmentId: string, body: AdjustmentCreateInput & { approval_revocation_reason?: string | null }) =>
    apiFetch<InventoryAdjustment>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}`, {
      method: 'PUT',
      body: JSON.stringify(body)
    }),

  initiateDocument: (adjustmentId: string, body: {
    file_name: string;
    content_type: string;
    size_bytes: number;
    checksum_sha256: string;
  }) =>
    apiFetch<AdjustmentUploadTicket>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}/documents`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  completeDocument: (adjustmentId: string, documentId: string) =>
    apiFetch<InventoryAdjustment>(
      `/inventory/adjustments/${encodeURIComponent(adjustmentId)}/documents/${encodeURIComponent(documentId)}/complete`,
      { method: 'POST' }
    ),

  detachDocument: (adjustmentId: string, documentId: string) =>
    apiFetch<InventoryAdjustment>(
      `/inventory/adjustments/${encodeURIComponent(adjustmentId)}/documents/${encodeURIComponent(documentId)}`,
      { method: 'DELETE' }
    ),

  downloadDocument: (adjustmentId: string, documentId: string) =>
    apiFetch<{ url: string; expires_at: string }>(
      `/inventory/adjustments/${encodeURIComponent(adjustmentId)}/documents/${encodeURIComponent(documentId)}/download`
    ),

  approve: (adjustmentId: string, expectedVersion: number) =>
    apiFetch<InventoryAdjustment>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: expectedVersion })
    }),

  cancel: (adjustmentId: string, reason: string) =>
    apiFetch<InventoryAdjustment>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    }),

  apply: async (adjustmentId: string) => {
    const storageKey = `${attemptScope('apply', adjustmentId)}:key`;
    const idempotency_key = readOrCreateStoredKey(storageKey);
    const result = await apiFetch<InventoryAdjustment>(
      `/inventory/adjustments/${encodeURIComponent(adjustmentId)}/apply`,
      { method: 'POST', body: JSON.stringify({ idempotency_key }) }
    );
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // The server accepted the request; a repeated request is still idempotent.
    }
    return result;
  },

  correction: (adjustmentId: string, body: {
    operational_date: string;
    accounting_date: string;
    reason: string;
    document_reference: string;
  }) =>
    apiFetch<InventoryAdjustment>(`/inventory/adjustments/${encodeURIComponent(adjustmentId)}/correction`, {
      method: 'POST',
      body: JSON.stringify(body)
    })
};

export function createIdempotencyKey(): string {
  return idempotencyKey('adj');
}
