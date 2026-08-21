export type StockStatus = 'available' | 'quarantine' | 'blocked' | 'damaged' | 'in_transit';
export type MeasurementStatus = 'complete' | 'incomplete' | 'verified';
export type MeasurementSource = 'master' | 'receipt' | 'manual' | 'device';
export type PackagingType =
  'piece' | 'box' | 'bag' | 'package' | 'roll' | 'drum' | 'container' | 'loose_other';

export type InventoryCapacityStatus =
  | 'not_configured'
  | 'incomplete'
  | 'available'
  | 'warning'
  | 'critical'
  | 'full'
  | 'over_operational'
  | 'over_certified';

export interface PhysicalMeasuresInput {
  gross_weight_kg?: number | null;
  length_m?: number | null;
  width_m?: number | null;
  height_m?: number | null;
  volume_m3?: number | null;
}

export interface InventoryItem {
  id: string;
  company_id: string;
  product_id: number | null;
  variant_id: string | null;
  base_unit_id: number;
  is_active: boolean;
}

export interface InventoryItemStatusSummary {
  stock_status: StockStatus;
  quantity_base: number;
  occupied_weight_kg: number | null;
  occupied_volume_m3: number | null;
  measurement_status: 'complete' | 'incomplete';
}

export interface InventoryItemSummary {
  inventory_item_id: string;
  company_id: string;
  product_id: number | null;
  variant_id: string | null;
  base_unit_id: number;
  is_active: boolean;
  total_quantity_base: number;
  status_totals: InventoryItemStatusSummary[];
  occupied_weight_kg: number | null;
  occupied_volume_m3: number | null;
  measurement_status: 'complete' | 'incomplete';
  handling_unit_count: number;
  unmeasured_handling_units: number;
  warehouse_count: number;
  location_count: number;
  lot_count: number;
}

export interface PackagingDefinition {
  id: string;
  company_id: string;
  inventory_item_id: string;
  code: string;
  name: string;
  packaging_type: PackagingType;
  version: number;
  base_quantity: number;
  gross_weight_kg: number | null;
  length_m: number | null;
  width_m: number | null;
  height_m: number | null;
  volume_m3: number | null;
  stackable: boolean;
  max_stack: number | null;
  is_current: boolean;
  is_active: boolean;
  created_at: string | null;
}

export interface PackagingCreateInput {
  code: string;
  name: string;
  packaging_type: PackagingType;
  base_quantity: number;
  measures: PhysicalMeasuresInput;
  stackable: boolean;
  max_stack?: number | null;
  supersedes_id?: string | null;
}

export interface CapacityMetric {
  certified: number | null;
  operational: number | null;
  occupied: number | null;
  reserved: number | null;
  projected: number | null;
  available: number | null;
  utilizationPct: number | null;
}

export interface CapacityScopeReference {
  scopeType: 'warehouse' | 'capacity_group' | 'location';
  scopeId: string;
  code: string;
  name: string;
}

export interface CapacityScopeSummary extends CapacityScopeReference {
  measurementStatus: 'complete' | 'incomplete';
  status: InventoryCapacityStatus;
  limitingMetric: 'weight' | 'volume' | null;
  weight: CapacityMetric;
  volume: CapacityMetric;
  effectiveUtilizationPct: number | null;
  unmeasuredHandlingUnits: number;
  unmeasuredReservations: number;
}

export interface CapacitySummary {
  scopeType: 'warehouse' | 'location';
  warehouseId: string;
  locationId: string | null;
  measurementStatus: 'complete' | 'incomplete';
  status: InventoryCapacityStatus;
  limitingMetric: 'weight' | 'volume' | null;
  weight: CapacityMetric;
  volume: CapacityMetric;
  effectiveUtilizationPct: number | null;
  unmeasuredHandlingUnits: number;
  unmeasuredReservations: number;
  scopePath: CapacityScopeSummary[];
  limitingScope: CapacityScopeReference | null;
}

export interface HandlingUnit {
  id: string;
  company_id: string;
  warehouse_id: string;
  location_id: string;
  inventory_item_id: string;
  packaging_definition_id: string | null;
  code: string;
  lot_code: string | null;
  expiry_date: string | null;
  quantity_base: number;
  actual_gross_weight_kg: number | null;
  actual_length_m: number | null;
  actual_width_m: number | null;
  actual_height_m: number | null;
  actual_volume_m3: number | null;
  occupied_weight_kg: number | null;
  occupied_volume_m3: number | null;
  stock_status: StockStatus;
  measurement_status: MeasurementStatus;
  measurement_source: MeasurementSource;
  closed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const PACKAGING_TYPE_LABEL: Record<PackagingType, string> = {
  piece: 'Pieza',
  box: 'Caja',
  bag: 'Saco o bolsa',
  package: 'Paquete',
  roll: 'Rollo',
  drum: 'Tambor',
  container: 'Contenedor',
  loose_other: 'Suelto u otro'
};

export const INVENTORY_CAPACITY_STATUS_LABEL: Record<InventoryCapacityStatus, string> = {
  not_configured: 'No configurada',
  incomplete: 'Medición incompleta',
  available: 'Disponible',
  warning: 'Advertencia',
  critical: 'Crítica',
  full: 'Sin capacidad operativa',
  over_operational: 'Excepción operativa activa',
  over_certified: 'Límite certificado excedido'
};
