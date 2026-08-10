import { api, type BranchOut } from '$lib/api/client';
import { type Branch } from '$lib/features/branches/types';

/**
 * Maps a backend API branch representation to the frontend's domain Branch entity.
 */
export function mapBranchOutToBranch(b: BranchOut): Branch {
  return {
    id: b.id,
    companyId: b.company_id,
    departmentId: b.department_id,
    municipalityId: b.municipality_id,
    districtId: b.district_id,
    code: b.code,
    name: b.name,
    address: b.address,
    city: b.city,
    phone: b.phone,
    email: b.email ?? '',
    manager: b.manager,
    managerEmployeeId: b.manager_employee_id,
    managerInitials: b.manager_initials,
    lat: b.latitude,
    lng: b.longitude,
    status: b.operational_status,
    employees: b.employees,
    warehouses: b.warehouses,
    salesThisMonth: b.sales_this_month,
    salesLastMonth: 0,
    salesYTD: 0,
    trend: b.trend || [],
    openedAt: b.opened_at,
    schedule:
      b.schedule
        ?.map((d) => `${d.day} ${d.open ?? 'Cerrado'}${d.close ? `–${d.close}` : ''}`)
        .join(', ') ?? '',
    scheduleDetail: b.schedule ?? [],
    zone: b.zone ?? '',
    services: b.services ?? [],
    facilities: b.facilities ?? [],
    area: b.area ?? 0,
    areaBuilt: b.area_built ?? 0,
    areaUnbuilt: b.area_unbuilt ?? 0,
    floors: b.floors ?? 0,
    parking: b.parking ?? 0,
    capacity: b.people_capacity ?? 0,
    propertyType: (b.property_type ?? 'alquilado') as Branch['propertyType'],
    areaAvailable: Math.max((b.area ?? 0) - (b.area_built ?? 0), b.area_unbuilt ?? 0),
    storageCapacity: 0,
    buildingAge: b.construction_year
      ? Math.max(new Date().getFullYear() - b.construction_year, 0)
      : 0,
    offices: b.offices ?? 0,
    meetingRooms: b.meeting_rooms ?? 0,
    bathrooms: b.bathrooms ?? 0,
    accesses: b.accesses ?? 0,
    emergencyExits: b.emergency_exits ?? 0,
    accessibility: b.accessibility ?? [],
    warehousesDetail: [],
    constructionType: (b.construction_type ?? 'concreto') as Branch['constructionType'],
    constructionYear: b.construction_year ?? 0,
    condition: (b.building_condition ?? 'bueno') as Branch['condition'],
    appraisedValue: b.appraised_value ?? 0,
    monthlyMaintenance: b.monthly_maintenance ?? 0,
    lastRenovation: b.last_renovation ?? '',
    electricalCapacityKVA: b.electrical_capacity_kva ?? 0,
    internetProvider: b.internet_provider ?? '',
    internetType: (b.internet_type ?? 'fibra') as Branch['internetType'],
    waterSource: (b.water_source ?? 'red_publica') as Branch['waterSource'],
    acSystem: (b.ac_system ?? 'mini_split') as Branch['acSystem'],
    lighting: (b.lighting ?? 'led') as Branch['lighting'],
    cctvCameras: b.cctv_cameras ?? 0,
    accessControl: (b.access_control ?? 'sin_control') as Branch['accessControl'],
    fireSystem: b.fire_system ?? [],
    hasAlarm: b.has_alarm ?? false,
    exteriorMaterial: (b.exterior_material ?? 'mixta') as Branch['exteriorMaterial'],
    floorMaterial: (b.floor_material ?? 'porcelanato') as Branch['floorMaterial'],
    roofCapacityKgM2: b.roof_capacity_kg_m2 ?? 0,
    hasBackupGenerator: b.has_backup_generator ?? false,
    hasUPS: b.has_ups ?? false,
    cleaningProvider: b.cleaning_provider ?? '',
    cadastralCode: b.cadastral_code ?? '',
    permitExpiry: b.permit_expiry ?? '',
    leaseExpiry: b.lease_expiry ?? null,
    landlord: b.landlord ?? null,
    avgTicket: 0,
    monthlyVisitors: 0,
    customerRating: 0,
    inventoryTurnover: 0,
    lastInspection: b.last_inspection ?? '',
    website: b.website ?? '',
    description: b.description ?? '',
    images: b.images ?? []
  };
}

/**
 * Fetches all branches from the API.
 * All values come from the backend; transactional metrics remain empty until
 * their owning modules are implemented.
 */
export async function getBranches(signal?: AbortSignal): Promise<Branch[]> {
  const list = await api.branches.list(signal);
  return list.map(mapBranchOutToBranch);
}

/**
 * Fetches a single branch by ID.
 */
export async function getBranch(id: string): Promise<Branch> {
  return mapBranchOutToBranch(await api.branches.get(id));
}

/**
 * Creates a new branch via API.
 */
export async function createBranch(branch: Omit<Branch, 'id'>): Promise<Branch> {
  const payload = {
    code: branch.code,
    name: branch.name,
    address: branch.address,
    company_id: branch.companyId,
    department_id: branch.departmentId,
    municipality_id: branch.municipalityId,
    district_id: branch.districtId,
    phone: branch.phone,
    latitude: branch.lat,
    longitude: branch.lng,
    operational_status: branch.status,
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
  if (branch.phone !== undefined) payload.phone = branch.phone;
  if (branch.lat !== undefined) payload.latitude = branch.lat;
  if (branch.lng !== undefined) payload.longitude = branch.lng;
  if (branch.status !== undefined) payload.operational_status = branch.status;
  if (branch.openedAt !== undefined) payload.opened_at = branch.openedAt;

  const res = await api.branches.update(id, payload);
  return mapBranchOutToBranch(res);
}

/**
 * Deactivates a branch without removing it from the master data catalogue.
 */
export async function deactivateBranch(id: string): Promise<void> {
  await api.branches.deactivate(id);
}
