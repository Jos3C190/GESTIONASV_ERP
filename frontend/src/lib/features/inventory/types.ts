export type StockStatus = 'available' | 'quarantine' | 'blocked' | 'damaged' | 'in_transit';
export type MeasurementStatus = 'complete' | 'incomplete' | 'verified';
export type MeasurementSource = 'master' | 'receipt' | 'manual' | 'device' | 'split_estimate';
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
  packaging_unit_id: number | null;
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
  packaging_unit_id: number;
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
  product_name?: string | null;
  product_sku?: string | null;
  product_id?: number | null;
  base_unit_id?: number | null;
  base_unit_name?: string | null;
  base_unit_symbol?: string | null;
  packaging_name?: string | null;
  packaging_base_quantity?: number | string | null;
  id: string;
  company_id: string;
  warehouse_id: string;
  location_id: string;
  inventory_item_id: string;
  packaging_definition_id: string | null;
  origin_handling_unit_id?: string | null;
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
  receipt_lot_code?: string | null;
  receipt_lot_header_code?: string | null;
  received_at?: string | null;
  purchase_code?: string | null;
  release_requirements?: string[];
  closed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface HandlingUnitSplitPrepareResult {
  idempotency_key: string;
  source_reference: string;
  remainder_handling_unit_id: string;
  remainder_handling_unit_code: string;
  remainder_quantity_base: number | string;
  split_handling_unit_id: string;
  split_handling_unit_code: string;
  split_quantity_base: number | string;
  stock_status: 'quarantine';
  measurement_status: MeasurementStatus;
}

export interface ReceiptLotHandlingUnit extends HandlingUnit {
  location_code: string;
  pending_placement_quantity_base: string;
  placed_quantity_base: string;
}

export interface ReceiptLotLine {
  inventory_lot_detail_ids: string[];
  inventory_lot_detail_id: string;
  receipt_lot_detail_code: string;
  purchase_detail_id: string;
  inventory_item_id: string;
  product_sku: string | null;
  product_name: string;
  base_unit_id: number;
  base_unit_name: string | null;
  base_unit_symbol: string | null;
  accepted_quantity_base: string;
  placed_quantity_base: string;
  pending_placement_quantity_base: string;
  handling_units: ReceiptLotHandlingUnit[];
}

export interface InventoryReceiptLot {
  id: string;
  company_id: string;
  purchase_id: string;
  purchase_code: string;
  warehouse_id: string;
  code: string;
  received_at: string;
  placement_status: 'pending_placement' | 'partially_placed' | 'placed' | string;
  costing_status: string | null;
  lines: ReceiptLotLine[];
}

export interface LegacyInventoryStock {
  warehouse_id: string;
  location_id: string;
  location_code: string | null;
  inventory_item_id: string;
  product_sku: string | null;
  product_name: string;
  base_unit_symbol: string;
  stock_status: string;
  total_quantity_base: string;
  attributable_quantity_base: string;
  legacy_quantity_base: string;
  legacy_handling_unit_count: number;
  legacy_handling_unit_quantity_base: string;
  reconciliation_difference: string;
  reconciled: boolean;
}

export interface InventoryLabelPreview {
  inventory_lot_id: string;
  inventory_lot_detail_id: string | null;
  handling_unit_id: string | null;
  handling_unit_code: string | null;
  inventory_item_id: string;
  product_internal_code: string;
  product_name: string;
  receipt_lot_code: string;
  receipt_lot_header_code: string | null;
  manufacturer_lot_code: string | null;
  received_on: string;
  quantity_base: string;
  base_unit_symbol: string;
  expiry_date: string | null;
  stock_status: StockStatus;
  print_count: number;
  has_initial_print: boolean;
  label_revision: number | null;
  label_print_id: string | null;
  label_confirmation_required: boolean;
  label_confirmed: boolean;
  presentation_equivalence: string | null;
}

export interface InventoryLabelLayout {
  content: 'full' | 'qr' | 'barcode';
  width_mm: number;
  height_mm: number;
}

export interface InventoryLabelPrint {
  id: string;
  inventory_lot_id: string;
  inventory_lot_detail_id: string | null;
  handling_unit_id: string | null;
  inventory_item_id: string;
  quantity_printed: number;
  print_date: string;
  reason: 'initial' | 'reprint';
  printed_by: string;
  printed_at: string;
  label_snapshot: Record<string, unknown>;
}

export interface InventoryLabelConfirmation {
  id: string;
  handling_unit_id: string;
  label_print_id: string;
  handling_unit_code: string;
  label_revision: number;
  quantity_base: string;
  label_fingerprint: string;
  confirmed_by: string;
  confirmed_at: string;
}

export interface InventoryTraceCapability {
  token: string;
  created_at: string;
}

export interface PublicTraceMovement {
  movement_type: string;
  posted_at: string;
  from_warehouse_code: string | null;
  from_warehouse_name: string | null;
  from_location_code: string | null;
  from_stock_status: StockStatus | null;
  to_warehouse_code: string | null;
  to_warehouse_name: string | null;
  to_location_code: string | null;
  to_stock_status: StockStatus | null;
  quantity_base: string;
}

export interface PublicHandlingUnitTrace {
  handling_unit_code: string;
  product_sku: string | null;
  product_name: string | null;
  quantity_base: string;
  base_unit_symbol: string | null;
  lot_code: string | null;
  receipt_lot_code: string | null;
  receipt_lot_header_code: string | null;
  expiry_date: string | null;
  stock_status: StockStatus;
  warehouse_code: string | null;
  warehouse_name: string | null;
  location_code: string | null;
  origin: {
    supplier_name: string | null;
    purchase_code: string | null;
    purchase_order_code: string | null;
    received_at: string | null;
    consolidation_code: string | null;
  };
  movements: PublicTraceMovement[];
}

export interface PutawayGroupResult {
  idempotency_key: string;
  receipt_lot_id: string;
  inventory_lot_detail_id: string;
  receipt_lot_detail_code: string;
  inventory_item_id: string;
  total_quantity_base: string;
  replayed: boolean;
  allocations: Array<{
    source_handling_unit_id: string;
    handling_unit_id: string;
    handling_unit_code: string;
    movement_id: string;
    quantity_base: string;
    destination_location_id: string;
    destination_location_code: string;
    stock_status: StockStatus;
    measurement_status: MeasurementStatus;
    measurement_source: MeasurementSource;
  }>;
}

export interface TransferHandlingUnit extends HandlingUnit {
  product_id: number | null;
  product_sku: string | null;
  product_name: string | null;
  base_unit_id: number;
  base_unit_name: string | null;
  base_unit_symbol: string | null;
  warehouse_code: string | null;
  warehouse_name: string;
  branch_id: string | null;
  branch_name: string | null;
  location_code: string;
  source_reference: string | null;
  origin_handling_unit_code?: string | null;
}

export interface HandlingUnitTraceEvent {
  movement_id: string;
  movement_type: string;
  source_reference: string | null;
  posted_at: string;
  posted_by: string | null;
  operator: string | null;
  from_warehouse_code: string | null;
  from_warehouse_name: string | null;
  from_location_code: string | null;
  from_stock_status: StockStatus | null;
  to_warehouse_code: string | null;
  to_warehouse_name: string | null;
  to_location_code: string | null;
  to_stock_status: StockStatus | null;
  quantity_base: number;
}

export interface HandlingUnitTraceRequest {
  request_code: string;
  branch_name: string;
  requested_at: string;
  required_date: string | null;
}

export interface HandlingUnitTraceOrigin {
  supplier_code: string | null;
  supplier_name: string | null;
  purchase_code: string | null;
  purchase_order_code: string | null;
  received_at: string | null;
  purchase_date: string | null;
  consolidation_code: string | null;
  requests: HandlingUnitTraceRequest[];
}

export interface HandlingUnitTraceability {
  handling_unit: HandlingUnit;
  product_sku: string | null;
  product_name: string | null;
  base_unit_name: string | null;
  base_unit_symbol: string | null;
  warehouse_code: string;
  warehouse_name: string;
  location_code: string;
  origin: HandlingUnitTraceOrigin;
  movements: HandlingUnitTraceEvent[];
}

export interface WarehouseMovementFilters {
  period_from?: string;
  period_to?: string;
  q?: string;
  lot_code?: string;
  source_reference?: string;
  direction?: 'incoming' | 'outgoing' | 'internal' | '';
}

export interface InventoryMovementHistory {
  id: string;
  movement_id: string;
  line_number: number;
  company_id: string;
  movement_type: string;
  source_reference: string | null;
  purchase_code: string | null;
  purchase_order_code: string | null;
  posted_at: string;
  posted_by: string | null;
  operator: string | null;
  inventory_item_id: string;
  product_id: number | null;
  variant_id: string | null;
  base_unit_id: number;
  base_unit_name: string | null;
  base_unit_symbol: string | null;
  product_sku: string | null;
  product_name: string | null;
  handling_unit_id: string | null;
  handling_unit_code: string | null;
  from_warehouse_id: string | null;
  from_warehouse_code: string | null;
  from_warehouse_name: string | null;
  from_location_id: string | null;
  from_location_code: string | null;
  from_stock_status: StockStatus | null;
  to_warehouse_id: string | null;
  to_warehouse_code: string | null;
  to_warehouse_name: string | null;
  to_location_id: string | null;
  to_location_code: string | null;
  to_stock_status: StockStatus | null;
  quantity_base: number | string;
  occupied_weight_kg: number | string | null;
  occupied_volume_m3: number | string | null;
  measurement_status: MeasurementStatus;
  lot_code: string | null;
  receipt_lot_code: string | null;
  receipt_lot_header_code: string | null;
  expiry_date: string | null;
  packaging_snapshot: Record<string, unknown> | null;
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
