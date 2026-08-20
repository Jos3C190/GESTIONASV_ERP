export type WarehouseStatus = 'active' | 'maintenance' | 'inactive';
export type WarehouseType =
  'general' | 'cold_storage' | 'hazmat' | 'transit' | 'bonded' | 'automated';
export type AccessControlType =
  'biometrico' | 'tarjetas' | 'teclado' | 'doble_llave' | 'sin_control';
export type CoolingType =
  'industrial_ac' | 'refrigeracion' | 'ventilacion_natural' | 'mixto' | 'sin_climatizacion';
export type CapacityProfile =
  'general_mixed' | 'rack' | 'bulk_floor' | 'cold' | 'oversize_manual' | 'transit';
export type CapacityEnforcementMode = 'disabled' | 'observe' | 'enforce';
export type CapacityStatus =
  | 'not_configured'
  | 'incomplete'
  | 'available'
  | 'warning'
  | 'critical'
  | 'full'
  | 'over_operational'
  | 'over_certified';
export interface WarehouseImage {
  url: string;
  caption: string;
  public_id?: string;
}
export interface WarehouseProduct {
  sku: string;
  name: string;
  category: string;
  quantity: number;
  unit: string;
  minStock: number;
  maxStock: number;
  expiryDate: string | null;
}
export interface WarehouseMovement {
  id: string;
  date: string;
  type: 'inbound' | 'outbound' | 'transfer' | 'adjustment';
  productSku: string;
  productName: string;
  quantity: number;
  operator: string;
  reference: string;
}
export interface Warehouse {
  id: string;
  categoryId?: string;
  code: string;
  name: string;
  description: string;
  type: WarehouseType;
  status: WarehouseStatus;
  location: string;
  branchId: string;
  branchName: string;
  branchAddress: string;
  area: number;
  height: number;
  length: number;
  width: number;
  shelvesTotal: number;
  shelvesOccupied: number | null;
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
  products: number | null;
  manager: string;
  managerEmployeeId?: string | null;
  managerInitials: string;
  operators: number;
  shifts: ('mañana' | 'tarde' | 'noche')[];
  totalSKUs: number;
  topCategories: string[];
  lowStockItems: number;
  expiringItems: number;
  inventoryValue: number;
  inventoryTurnover: number;
  lastMovement: string;
  inboundThisMonth: number;
  outboundThisMonth: number;
  dailyMovementsAvg: number;
  trend?: number[];
  recentMovements: WarehouseMovement[];
  topProducts: WarehouseProduct[];
  cameras: number;
  accessControl: AccessControlType;
  hasAlarm: boolean;
  fireSystem: string[];
  lastSecurityAudit: string;
  temperatureRange: string;
  humidityRange: string;
  cooling: CoolingType;
  hasVentilation: boolean;
  lastMaintenance: string;
  nextMaintenance: string;
  maintenanceNotes: string;
  sanitaryPermit: string | null;
  sanitaryPermitExpiry: string | null;
  lastInspection: string;
  certifications: string[];
  images: WarehouseImage[];
  createdAt: string;
  updatedAt: string | null;
}
export const STATUS_MAP: Record<
  WarehouseStatus,
  { label: string; variant: 'success' | 'neutral' | 'warning' }
> = {
  active: { label: 'Activo', variant: 'success' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
  inactive: { label: 'Inactivo', variant: 'neutral' }
};
export const TYPE_LABEL: Record<WarehouseType, string> = {
  general: 'Almacén general',
  cold_storage: 'Almacén refrigerado',
  hazmat: 'Materiales peligrosos',
  transit: 'Tránsito / cross-dock',
  bonded: 'Almacén aduanal',
  automated: 'Almacén automatizado'
};
export const CAPACITY_PROFILE_LABEL: Record<CapacityProfile, string> = {
  general_mixed: 'Mixto general',
  rack: 'Rack',
  bulk_floor: 'Piso / granel',
  cold: 'Cámara fría',
  oversize_manual: 'Sobredimensionado manual',
  transit: 'Tránsito'
};
export const CAPACITY_ENFORCEMENT_LABEL: Record<CapacityEnforcementMode, string> = {
  disabled: 'Deshabilitado',
  observe: 'Solo observar',
  enforce: 'Bloquear excesos'
};
export const CAPACITY_STATUS_LABEL: Record<CapacityStatus, string> = {
  not_configured: 'No configurada',
  incomplete: 'Configuración incompleta',
  available: 'Configurada',
  warning: 'Advertencia',
  critical: 'Crítica',
  full: 'Sin capacidad',
  over_operational: 'Sobre límite operativo',
  over_certified: 'Peligro: límite certificado excedido'
};
export function getShortWarehouseName(name: string) {
  return name.replace(/^Almacén\s+/i, '');
}
