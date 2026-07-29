import { api, type WarehouseOut } from '$lib/api/client';
import {
  type Warehouse,
  type WarehouseMovement,
  type WarehouseProduct,
  type WarehouseStatus,
  type WarehouseType,
  type AccessControlType,
  type CoolingType,
  WAREHOUSES
} from '$lib/features/warehouses/mock-data';

/**
 * Maps a backend API warehouse representation to the frontend's domain Warehouse entity.
 */
export function mapWarehouseOutToWarehouse(w: WarehouseOut): Warehouse {
  return {
    id: w.id,
    code: w.code,
    name: w.name,
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
    createdAt: w.created_at ?? '',
    updatedAt: w.updated_at ?? null,
  };
}

/**
 * Fetches all warehouses from the API, optionally filtering by branch.
 * Falls back to mock data if the backend endpoint is not yet implemented or active.
 */
export async function getWarehouses(params?: { branchId?: string }): Promise<Warehouse[]> {
  try {
    const list = await api.warehouses.list({
      branch_id: params?.branchId
    });
    return list.map(mapWarehouseOutToWarehouse);
  } catch (err) {
    console.warn('[Warehouses Service] API not ready or returned error. Using mock data.', err);
    if (params?.branchId) {
      return WAREHOUSES.filter(w => w.branchId === params.branchId);
    }
    return WAREHOUSES;
  }
}

/**
 * Fetches a single warehouse by ID.
 */
export async function getWarehouse(id: string): Promise<Warehouse> {
  try {
    const res = await api.warehouses.get(id);
    return mapWarehouseOutToWarehouse(res);
  } catch (err) {
    console.warn(`[Warehouses Service] API get failed for ${id}. Checking mock data.`, err);
    const mock = WAREHOUSES.find(w => w.id === id);
    if (!mock) throw err;
    return mock;
  }
}

/**
 * Creates a new warehouse via API.
 */
export async function createWarehouse(warehouse: Omit<Warehouse, 'id'>): Promise<Warehouse> {
  const payload = {
    code: warehouse.code,
    name: warehouse.name,
    type: warehouse.type,
    status: warehouse.status,
    location: warehouse.location,
    branch_id: warehouse.branchId,
    branch_name: warehouse.branchName,
    branch_address: warehouse.branchAddress,
    capacity: warehouse.capacity,
    used: warehouse.used,
    products: warehouse.products,
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
  if (warehouse.type !== undefined) payload.type = warehouse.type;
  if (warehouse.status !== undefined) payload.status = warehouse.status;
  if (warehouse.location !== undefined) payload.location = warehouse.location;
  if (warehouse.capacity !== undefined) payload.capacity = warehouse.capacity;
  if (warehouse.used !== undefined) payload.used = warehouse.used;
  if (warehouse.products !== undefined) payload.products = warehouse.products;

  const res = await api.warehouses.update(id, payload);
  return mapWarehouseOutToWarehouse(res);
}

/**
 * Deletes a warehouse via API.
 */
export async function deleteWarehouse(id: string): Promise<void> {
  await api.warehouses.delete(id);
}