import {
  api,
  type PageMeta,
  type WarehouseListSummary,
  type WarehouseOut
} from '$lib/api/client';
import {
  type Warehouse,
  type WarehouseMovement,
  type WarehouseProduct,
  type WarehouseStatus,
  type WarehouseType,
  type AccessControlType,
  type CoolingType,
} from '$lib/features/warehouses/types';

/**
 * Maps a backend API warehouse representation to the frontend's domain Warehouse entity.
 */
export function mapWarehouseOutToWarehouse(w: WarehouseOut): Warehouse {
  return {
    id: w.id,
    categoryId: w.warehouse_category_id,
    code: w.code,
    name: w.name,
    description: w.description ?? '',
    type: (w.type ?? 'general') as WarehouseType,
    status: (w.status ?? 'active') as WarehouseStatus,
    location: w.location,
    branchId: w.branch_id,
    branchName: w.branch_name,
    branchAddress: w.branch_address ?? '',
    area: w.area ?? 0,
    height: w.height ?? 0,
    length: w.length ?? 0,
    width: w.width ?? 0,
    shelvesTotal: w.shelves_total ?? 0,
    shelvesOccupied: w.shelves_occupied ?? 0,
    capacity: w.capacity,
    used: w.used,
    products: w.products,
    manager: w.manager ?? '',
    managerEmployeeId: w.manager_employee_id,
    managerInitials: w.manager_initials ?? '',
    operators: w.operators ?? 0,
    shifts: w.shifts ?? [],
    totalSKUs: w.total_skus ?? 0,
    topCategories: w.top_categories ?? [],
    lowStockItems: w.low_stock_items ?? 0,
    expiringItems: w.expiring_items ?? 0,
    inventoryValue: w.inventory_value ?? 0,
    inventoryTurnover: w.inventory_turnover ?? 0,
    lastMovement: w.last_movement,
    inboundThisMonth: w.inbound_this_month ?? 0,
    outboundThisMonth: w.outbound_this_month ?? 0,
    dailyMovementsAvg: w.daily_movements_avg ?? 0,
    trend: w.trend || undefined,
    recentMovements: (w.recent_movements ?? []).map((m): WarehouseMovement => ({
      id: m.id,
      date: m.date,
      type: m.type,
      productSku: m.product_sku,
      productName: m.product_name,
      quantity: m.quantity,
      operator: m.operator,
      reference: m.reference,
    })),
    topProducts: (w.top_products ?? []).map((p): WarehouseProduct => ({
      sku: p.sku,
      name: p.name,
      category: p.category,
      quantity: p.quantity,
      unit: p.unit,
      minStock: p.min_stock,
      maxStock: p.max_stock,
      expiryDate: p.expiry_date,
    })),
    cameras: w.cameras ?? 0,
    accessControl: (w.access_control ?? 'sin_control') as AccessControlType,
    hasAlarm: w.has_alarm ?? false,
    fireSystem: w.fire_system ?? [],
    lastSecurityAudit: w.last_security_audit ?? '',
    temperatureRange: w.temperature_range ?? '',
    humidityRange: w.humidity_range ?? '',
    cooling: (w.cooling ?? 'ventilacion_natural') as CoolingType,
    hasVentilation: w.has_ventilation ?? false,
    lastMaintenance: w.last_maintenance ?? '',
    nextMaintenance: w.next_maintenance ?? '',
    maintenanceNotes: w.maintenance_notes ?? '',
    sanitaryPermit: w.sanitary_permit ?? null,
    sanitaryPermitExpiry: w.sanitary_permit_expiry ?? null,
    lastInspection: w.last_inspection ?? '',
    certifications: w.certifications ?? [],
    images: w.images ?? [],
    createdAt: w.created_at ?? '',
    updatedAt: w.updated_at ?? null,
  };
}

/**
 * Fetches all warehouses from the API, optionally filtering by branch.
 * Falls back to mock data if the backend endpoint is not yet implemented or active.
 */
export async function getWarehouses(params?: {
  branchId?: string;
  page?: number;
  size?: number;
  search?: string;
  status?: string;
  sort?: 'capacity' | 'name' | 'movement';
  signal?: AbortSignal;
}): Promise<{ items: Warehouse[]; meta: PageMeta; summary: WarehouseListSummary }> {
  const response = await api.warehouses.list({
    branch_id: params?.branchId,
    page: params?.page,
    size: params?.size,
    search: params?.search,
    status: params?.status,
    sort: params?.sort,
    signal: params?.signal
  });
  return {
    items: response.items.map(mapWarehouseOutToWarehouse),
    meta: response.meta,
    summary: response.summary
  };
}

/**
 * Fetches a single warehouse by ID.
 */
export async function getWarehouse(id: string): Promise<Warehouse> {
  return mapWarehouseOutToWarehouse(await api.warehouses.get(id));
}

/**
 * Creates a new warehouse via API.
 */
export async function createWarehouse(warehouse: Omit<Warehouse, 'id'>): Promise<Warehouse> {
  const payload = {
    code: warehouse.code,
    name: warehouse.name,
    warehouse_type: warehouse.type,
    operational_status: warehouse.status,
    physical_location: warehouse.location,
    branch_id: warehouse.branchId,
    warehouse_category_id: warehouse.categoryId,
    capacity: warehouse.capacity,
    area: warehouse.area || null,
  };
  const res = await api.warehouses.create(payload);
  return mapWarehouseOutToWarehouse(res);
}

/**
 * Updates an existing warehouse via API.
 */
export async function updateWarehouse(id: string, warehouse: Partial<Warehouse>): Promise<Warehouse> {
  const payload: Record<string, unknown> = {};
  if (warehouse.code !== undefined) payload.code = warehouse.code;
  if (warehouse.name !== undefined) payload.name = warehouse.name;
  if (warehouse.type !== undefined) payload.warehouse_type = warehouse.type;
  if (warehouse.status !== undefined) payload.operational_status = warehouse.status;
  if (warehouse.location !== undefined) payload.physical_location = warehouse.location;
  if (warehouse.capacity !== undefined) payload.capacity = warehouse.capacity;

  const res = await api.warehouses.update(id, payload);
  return mapWarehouseOutToWarehouse(res);
}

/**
 * Deactivates a warehouse without removing it from the master data catalogue.
 */
export async function deactivateWarehouse(id: string): Promise<void> {
  await api.warehouses.deactivate(id);
}
