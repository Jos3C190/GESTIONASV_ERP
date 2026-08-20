import type { CapacityEnforcementMode, CapacityProfile, CapacityStatus } from './types';

export type CapacityGroupType =
  'structural' | 'rack' | 'bay' | 'level' | 'floor_zone' | 'cold_chamber' | 'transit_zone';

export interface WarehouseCapacityGroup {
  id: string;
  warehouseId: string;
  parentId: string | null;
  code: string;
  name: string;
  groupType: CapacityGroupType;
  certifiedMaxWeightKg: number | null;
  operationalMaxWeightKg: number | null;
  certifiedUsableVolumeM3: number | null;
  operationalUsableVolumeM3: number | null;
  capacityProfile: CapacityProfile;
  capacityEnforcementMode: CapacityEnforcementMode;
  capacityStatus: CapacityStatus;
  storageEligible: boolean;
  usableLengthM: number | null;
  usableWidthM: number | null;
  usableHeightM: number | null;
  isActive: boolean;
  directLocationCount: number;
  subtreeLocationCount: number;
  createdAt: string;
  updatedAt: string | null;
}

export interface WarehouseCapacityGroupInput {
  parent_id: string | null;
  code: string;
  name: string;
  group_type: CapacityGroupType;
  certified_max_weight_kg: number | null;
  operational_max_weight_kg: number | null;
  certified_usable_volume_m3: number | null;
  operational_usable_volume_m3: number | null;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  storage_eligible: boolean;
  usable_length_m: number | null;
  usable_width_m: number | null;
  usable_height_m: number | null;
  is_active: boolean;
}

export interface WarehouseCapacityGroupDraft {
  parent_id: string;
  code: string;
  name: string;
  group_type: CapacityGroupType;
  certified_max_weight_kg: string;
  operational_max_weight_kg: string;
  certified_usable_volume_m3: string;
  operational_usable_volume_m3: string;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  storage_eligible: boolean;
  usable_length_m: string;
  usable_width_m: string;
  usable_height_m: string;
  is_active: boolean;
}

export type CapacityGroupFieldErrors = Partial<
  Record<keyof WarehouseCapacityGroupDraft | 'form', string>
>;

export interface CapacityGroupTreeRow {
  group: WarehouseCapacityGroup;
  depth: number;
  childCount: number;
  orphaned: boolean;
}

export interface CapacityConfigurationIssue {
  severity: 'error' | 'warning';
  code:
    | 'capacity_child_limit_exceeds_parent'
    | 'parent_limit_not_configured'
    | 'nominal_capacity_overallocated';
  scopeType: 'warehouse' | 'capacity_group' | 'location';
  scopeId: string;
  parentScopeType: 'warehouse' | 'capacity_group' | null;
  parentScopeId: string | null;
  metric: 'weight' | 'volume';
  limitKind: 'certified' | 'operational';
  childLimit: number | null;
  parentLimit: number | null;
  allocatedChildrenTotal: number | null;
  allocationRatioPct: number | null;
}

export interface CapacityConfigurationDiagnostics {
  warehouseId: string;
  issues: CapacityConfigurationIssue[];
}

export const CAPACITY_GROUP_TYPE_OPTIONS: Array<{
  value: CapacityGroupType;
  label: string;
  description: string;
}> = [
  {
    value: 'structural',
    label: 'Estructural',
    description: 'Agrupación general para organizar otros espacios.'
  },
  { value: 'rack', label: 'Rack', description: 'Estructura completa de almacenamiento.' },
  { value: 'bay', label: 'Bahía', description: 'Sección vertical dentro de un rack.' },
  { value: 'level', label: 'Nivel', description: 'Nivel de carga dentro de una estructura.' },
  {
    value: 'floor_zone',
    label: 'Zona de piso',
    description: 'Superficie útil para granel, sacos o carga no estibada.'
  },
  {
    value: 'cold_chamber',
    label: 'Cámara fría',
    description: 'Recinto con condiciones térmicas controladas.'
  },
  {
    value: 'transit_zone',
    label: 'Zona de tránsito',
    description: 'Área temporal de recepción, despacho o transferencia.'
  }
];

export const CAPACITY_GROUP_TYPE_LABEL: Record<CapacityGroupType, string> = Object.fromEntries(
  CAPACITY_GROUP_TYPE_OPTIONS.map((option) => [option.value, option.label])
) as Record<CapacityGroupType, string>;
