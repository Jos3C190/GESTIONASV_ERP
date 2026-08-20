import { apiFetch } from '$lib/api/client';
import type {
  CapacityConfigurationDiagnostics,
  CapacityConfigurationIssue,
  CapacityGroupType,
  WarehouseCapacityGroup,
  WarehouseCapacityGroupInput
} from './capacity-groups.types';
import type { CapacityEnforcementMode, CapacityProfile, CapacityStatus } from './types';

interface WarehouseCapacityGroupResponse {
  id: string;
  warehouse_id: string;
  parent_id: string | null;
  code: string;
  name: string;
  group_type: CapacityGroupType;
  certified_max_weight_kg: number | string | null;
  operational_max_weight_kg: number | string | null;
  certified_usable_volume_m3: number | string | null;
  operational_usable_volume_m3: number | string | null;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  capacity_status: CapacityStatus;
  storage_eligible: boolean;
  usable_length_m: number | string | null;
  usable_width_m: number | string | null;
  usable_height_m: number | string | null;
  is_active: boolean;
  direct_location_count?: number;
  subtree_location_count?: number;
  created_at: string;
  updated_at: string | null;
}

interface CapacityConfigurationIssueResponse {
  severity: CapacityConfigurationIssue['severity'];
  code: CapacityConfigurationIssue['code'];
  scope_type: CapacityConfigurationIssue['scopeType'];
  scope_id: string;
  parent_scope_type: CapacityConfigurationIssue['parentScopeType'];
  parent_scope_id: string | null;
  metric: CapacityConfigurationIssue['metric'];
  limit_kind: CapacityConfigurationIssue['limitKind'];
  child_limit: number | string | null;
  parent_limit: number | string | null;
  allocated_children_total: number | string | null;
  allocation_ratio_pct: number | string | null;
}

interface CapacityConfigurationDiagnosticsResponse {
  warehouse_id: string;
  issues: CapacityConfigurationIssueResponse[];
}

const nullableNumber = (value: number | string | null): number | null => {
  if (value === null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

function mapCapacityGroup(response: WarehouseCapacityGroupResponse): WarehouseCapacityGroup {
  return {
    id: response.id,
    warehouseId: response.warehouse_id,
    parentId: response.parent_id,
    code: response.code,
    name: response.name,
    groupType: response.group_type,
    certifiedMaxWeightKg: nullableNumber(response.certified_max_weight_kg),
    operationalMaxWeightKg: nullableNumber(response.operational_max_weight_kg),
    certifiedUsableVolumeM3: nullableNumber(response.certified_usable_volume_m3),
    operationalUsableVolumeM3: nullableNumber(response.operational_usable_volume_m3),
    capacityProfile: response.capacity_profile,
    capacityEnforcementMode: response.capacity_enforcement_mode,
    capacityStatus: response.capacity_status,
    storageEligible: response.storage_eligible,
    usableLengthM: nullableNumber(response.usable_length_m),
    usableWidthM: nullableNumber(response.usable_width_m),
    usableHeightM: nullableNumber(response.usable_height_m),
    isActive: response.is_active,
    directLocationCount: Number(response.direct_location_count ?? 0),
    subtreeLocationCount: Number(response.subtree_location_count ?? 0),
    createdAt: response.created_at,
    updatedAt: response.updated_at
  };
}

/** Lists active and inactive structural groups for one warehouse. */
export async function listCapacityGroups(
  warehouseId: string,
  signal?: AbortSignal
): Promise<WarehouseCapacityGroup[]> {
  const response = await apiFetch<WarehouseCapacityGroupResponse[]>(
    `/warehouses/${encodeURIComponent(warehouseId)}/capacity-groups`,
    { signal }
  );
  return response.map(mapCapacityGroup);
}

export async function getCapacityConfigurationDiagnostics(
  warehouseId: string,
  signal?: AbortSignal
): Promise<CapacityConfigurationDiagnostics> {
  const response = await apiFetch<CapacityConfigurationDiagnosticsResponse>(
    `/warehouses/${encodeURIComponent(warehouseId)}/capacity-configuration-diagnostics`,
    { signal }
  );
  return {
    warehouseId: response.warehouse_id,
    issues: response.issues.map((issue) => ({
      severity: issue.severity,
      code: issue.code,
      scopeType: issue.scope_type,
      scopeId: issue.scope_id,
      parentScopeType: issue.parent_scope_type,
      parentScopeId: issue.parent_scope_id,
      metric: issue.metric,
      limitKind: issue.limit_kind,
      childLimit: nullableNumber(issue.child_limit),
      parentLimit: nullableNumber(issue.parent_limit),
      allocatedChildrenTotal: nullableNumber(issue.allocated_children_total),
      allocationRatioPct: nullableNumber(issue.allocation_ratio_pct)
    }))
  };
}

export async function createCapacityGroup(
  warehouseId: string,
  input: WarehouseCapacityGroupInput
): Promise<WarehouseCapacityGroup> {
  const response = await apiFetch<WarehouseCapacityGroupResponse>(
    `/warehouses/${encodeURIComponent(warehouseId)}/capacity-groups`,
    { method: 'POST', body: JSON.stringify(input) }
  );
  return mapCapacityGroup(response);
}

export async function updateCapacityGroup(
  warehouseId: string,
  groupId: string,
  input: WarehouseCapacityGroupInput
): Promise<WarehouseCapacityGroup> {
  const response = await apiFetch<WarehouseCapacityGroupResponse>(
    `/warehouses/${encodeURIComponent(warehouseId)}/capacity-groups/${encodeURIComponent(groupId)}`,
    { method: 'PATCH', body: JSON.stringify(input) }
  );
  return mapCapacityGroup(response);
}
