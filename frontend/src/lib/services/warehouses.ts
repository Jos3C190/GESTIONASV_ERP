import { api, type WarehouseOut } from '$lib/api/client';
import { type Warehouse, WAREHOUSES } from '$lib/features/warehouses/mock-data';

/**
 * Maps a backend API warehouse representation to the frontend's domain Warehouse entity.
 */
export function mapWarehouseOutToWarehouse(w: WarehouseOut): Warehouse {
  return {
    id: w.id,
    code: w.code,
    name: w.name,
    branchId: w.branch_id,
    branchName: w.branch_name,
    location: w.location,
    capacity: w.capacity,
    used: w.used,
    status: w.status,
    products: w.products,
    lastMovement: w.last_movement,
    trend: w.trend || undefined
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
    branch_id: warehouse.branchId,
    branch_name: warehouse.branchName,
    location: warehouse.location,
    capacity: warehouse.capacity,
    used: warehouse.used,
    status: warehouse.status,
    products: warehouse.products,
    last_movement: warehouse.lastMovement,
    trend: warehouse.trend || null
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
  if (warehouse.branchId !== undefined) payload.branch_id = warehouse.branchId;
  if (warehouse.branchName !== undefined) payload.branch_name = warehouse.branchName;
  if (warehouse.location !== undefined) payload.location = warehouse.location;
  if (warehouse.capacity !== undefined) payload.capacity = warehouse.capacity;
  if (warehouse.used !== undefined) payload.used = warehouse.used;
  if (warehouse.status !== undefined) payload.status = warehouse.status;
  if (warehouse.products !== undefined) payload.products = warehouse.products;
  if (warehouse.lastMovement !== undefined) payload.last_movement = warehouse.lastMovement;
  if (warehouse.trend !== undefined) payload.trend = warehouse.trend;

  const res = await api.warehouses.update(id, payload);
  return mapWarehouseOutToWarehouse(res);
}

/**
 * Deletes a warehouse via API.
 */
export async function deleteWarehouse(id: string): Promise<void> {
  await api.warehouses.delete(id);
}
