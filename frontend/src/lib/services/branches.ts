import { api, type BranchOut } from '$lib/api/client';
import { type Branch, BRANCHES } from '$lib/features/branches/mock-data';

/**
 * Maps a backend API branch representation to the frontend's domain Branch entity.
 */
export function mapBranchOutToBranch(b: BranchOut): Branch {
  return {
    id: b.id,
    code: b.code,
    name: b.name,
    address: b.address,
    city: b.city,
    phone: b.phone,
    email: '',
    manager: b.manager,
    managerInitials: b.manager_initials,
    lat: b.lat,
    lng: b.lng,
    status: b.status,
    employees: b.employees,
    warehouses: b.warehouses,
    salesThisMonth: b.sales_this_month,
    salesLastMonth: 0,
    salesYTD: 0,
    trend: b.trend || [],
    openedAt: b.opened_at,
    schedule: '',
    scheduleDetail: [],
    zone: '',
    services: [],
    facilities: [],
    area: 0,
    areaBuilt: 0,
    areaUnbuilt: 0,
    floors: 1,
    parking: 0,
    capacity: 0,
    propertyType: 'alquilado',
    areaAvailable: 0,
    storageCapacity: 0,
    buildingAge: 0,
    offices: 0,
    meetingRooms: 0,
    bathrooms: 0,
    accesses: 0,
    emergencyExits: 0,
    accessibility: [],
    warehousesDetail: [],
    constructionType: 'concreto',
    constructionYear: 0,
    condition: 'bueno',
    appraisedValue: 0,
    monthlyMaintenance: 0,
    lastRenovation: '',
    electricalCapacityKVA: 0,
    internetProvider: '',
    internetType: 'fibra',
    waterSource: 'red_publica',
    acSystem: 'mini_split',
    lighting: 'led',
    cctvCameras: 0,
    accessControl: 'sin_control',
    fireSystem: [],
    hasAlarm: false,
    exteriorMaterial: 'mixta',
    floorMaterial: 'porcelanato',
    roofCapacityKgM2: 0,
    hasBackupGenerator: false,
    hasUPS: false,
    cleaningProvider: '',
    cadastralCode: '',
    permitExpiry: '',
    leaseExpiry: null,
    landlord: null,
    avgTicket: 0,
    monthlyVisitors: 0,
    customerRating: 0,
    inventoryTurnover: 0,
    lastInspection: '',
    website: '',
    description: '',
    images: []
  };
}

/**
 * Fetches all branches from the API.
 * Falls back to mock data if the backend endpoint is not yet implemented or active.
 */
export async function getBranches(): Promise<Branch[]> {
  try {
    const list = await api.branches.list();
    return list.map(mapBranchOutToBranch);
  } catch (err) {
    console.warn('[Branches Service] API not ready or returned error. Using mock data.', err);
    return BRANCHES;
  }
}

/**
 * Fetches a single branch by ID.
 */
export async function getBranch(id: string): Promise<Branch> {
  try {
    const res = await api.branches.get(id);
    return mapBranchOutToBranch(res);
  } catch (err) {
    console.warn(`[Branches Service] API get failed for ${id}. Checking mock data.`, err);
    const mock = BRANCHES.find(b => b.id === id);
    if (!mock) throw err;
    return mock;
  }
}

/**
 * Creates a new branch via API.
 */
export async function createBranch(branch: Omit<Branch, 'id'>): Promise<Branch> {
  const payload = {
    code: branch.code,
    name: branch.name,
    address: branch.address,
    city: branch.city,
    phone: branch.phone,
    manager: branch.manager,
    manager_initials: branch.managerInitials,
    lat: branch.lat,
    lng: branch.lng,
    status: branch.status,
    employees: branch.employees,
    warehouses: branch.warehouses,
    sales_this_month: branch.salesThisMonth,
    trend: branch.trend,
    opened_at: branch.openedAt
  };
  const res = await api.branches.create(payload);
  return mapBranchOutToBranch(res);
}

/**
 * Updates an existing branch via API.
 */
export async function updateBranch(id: string, branch: Partial<Branch>): Promise<Branch> {
  const payload: Record<string, unknown> = {};
  if (branch.code !== undefined) payload.code = branch.code;
  if (branch.name !== undefined) payload.name = branch.name;
  if (branch.address !== undefined) payload.address = branch.address;
  if (branch.city !== undefined) payload.city = branch.city;
  if (branch.phone !== undefined) payload.phone = branch.phone;
  if (branch.manager !== undefined) payload.manager = branch.manager;
  if (branch.managerInitials !== undefined) payload.manager_initials = branch.managerInitials;
  if (branch.lat !== undefined) payload.lat = branch.lat;
  if (branch.lng !== undefined) payload.lng = branch.lng;
  if (branch.status !== undefined) payload.status = branch.status;
  if (branch.employees !== undefined) payload.employees = branch.employees;
  if (branch.warehouses !== undefined) payload.warehouses = branch.warehouses;
  if (branch.salesThisMonth !== undefined) payload.sales_this_month = branch.salesThisMonth;
  if (branch.trend !== undefined) payload.trend = branch.trend;
  if (branch.openedAt !== undefined) payload.opened_at = branch.openedAt;

  const res = await api.branches.update(id, payload);
  return mapBranchOutToBranch(res);
}

/**
 * Deletes a branch via API.
 */
export async function deleteBranch(id: string): Promise<void> {
  await api.branches.delete(id);
}
