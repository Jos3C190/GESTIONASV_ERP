import { apiFetch } from '$lib/api/client';
import { ownedDocuments } from '$lib/api/owned-documents';
import { branch } from '$lib/stores/branch.svelte';
import type {
  FuelType,
  LicenseClass,
  OperationalStatus,
  BaseImage,
  MeterUnit,
  VehicleStatus
} from './catalog';

export type ComplianceState = 'ok' | 'warning' | 'blocked';

export interface ComplianceIssue {
  code: string;
  severity: 'blocking' | 'warning';
  message: string;
}

export interface Compliance {
  state: ComplianceState;
  issues: ComplianceIssue[];
}

export interface VehicleDriver {
  assignment_id: string;
  driver_id: string;
  name: string;
  initials: string;
  photo_url: string | null;
  license_class: LicenseClass;
  status: 'active' | 'suspended' | 'inactive';
  since: string;
}

export interface FleetVehicleTypeInfo {
  code: string;
  name: string;
  plural: string;
  license_classes: LicenseClass[];
  base_image: BaseImage | null;
  requires_plate: boolean;
  requires_capacity: boolean;
  meter_unit: MeterUnit;
  fuel_applicable: boolean;
  can_tow: boolean;
  is_towable: boolean;
  is_system: boolean;
  is_active: boolean;
}

export interface FleetVehicleType extends FleetVehicleTypeInfo {
  id: string;
  usage_count: number;
}

export type FleetVehicleTypeInput = Pick<
  FleetVehicleTypeInfo,
  | 'name'
  | 'plural'
  | 'license_classes'
  | 'base_image'
  | 'requires_plate'
  | 'requires_capacity'
  | 'meter_unit'
  | 'fuel_applicable'
  | 'can_tow'
  | 'is_towable'
> & { is_active?: boolean };

export interface VehicleCoupling {
  coupling_id: string;
  role: 'tractor' | 'trailer';
  vehicle_id: string;
  code: string;
  plate: string | null;
  since: string;
}

export interface FleetVehicle {
  id: string;
  code: string;
  plate: string | null;
  vin: string | null;
  kind: string;
  type: FleetVehicleTypeInfo;
  coupling: VehicleCoupling | null;
  brand: string;
  model: string;
  year: number;
  color: string | null;
  capacity_kg: string | null;
  fuel_type: FuelType;
  odometer_km: string;
  status: VehicleStatus;
  operational_status: OperationalStatus;
  branch_id: string;
  branch_name: string;
  driver: VehicleDriver | null;
  current_transfer: {
    id: string;
    code: string;
    status: string;
    dispatched_at: string | null;
    destination_branch: string;
  } | null;
  maintenance_in_progress: boolean;
  gps_linked: boolean;
  gps_device_unique_id: string | null;
  inventory_vehicle_id: string | null;
  notes: string | null;
  compliance: Compliance;
  created_at: string;
  updated_at: string;
}

export interface FleetSummary {
  total: number;
  available: number;
  in_route: number;
  maintenance: number;
  out_of_service: number;
  blocked: number;
  with_warnings: number;
}

export interface FleetPage<T> {
  items: T[];
  meta: { page: number; size: number; total: number; pages: number };
}

export interface VehicleInput {
  plate: string | null;
  vin?: string | null;
  kind: string;
  brand: string;
  model: string;
  year: number;
  color?: string | null;
  capacity_kg: string | null;
  fuel_type: FuelType;
  notes?: string | null;
}

export interface VehicleCreateInput extends VehicleInput {
  branch_id: string;
  code: string;
  odometer_km: string;
}

export interface VehiclePhoto {
  id: string;
  url: string;
  caption: string | null;
  position: number;
  created_at: string;
}

export interface OdometerReading {
  id: string;
  reading_km: string;
  read_at: string;
  source: 'manual' | 'fuel' | 'maintenance' | 'gps';
  notes: string | null;
  recorded_by_name: string | null;
}

export type DueState = 'ok' | 'soon' | 'overdue' | 'unknown';

export interface MaintenancePlan {
  id: string;
  name: string;
  interval_km: number | null;
  interval_days: number | null;
  last_service_km: string | null;
  last_service_on: string | null;
  due_km: string | null;
  due_on: string | null;
  state: DueState;
  is_active: boolean;
}

export interface MaintenancePlanInput {
  name: string;
  interval_km: number | null;
  interval_days: number | null;
  last_service_km: string | null;
  last_service_on: string | null;
}

export type OrderStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled';

export interface MaintenanceOrder {
  id: string;
  plan_id: string | null;
  plan_name: string | null;
  kind: 'preventive' | 'corrective';
  status: OrderStatus;
  title: string;
  description: string | null;
  workshop: string | null;
  scheduled_on: string | null;
  started_at: string | null;
  completed_at: string | null;
  odometer_km: string | null;
  cost: string | null;
  cancel_reason: string | null;
  created_at: string;
}

export interface MaintenanceOrderInput {
  kind: 'preventive' | 'corrective';
  title: string;
  description?: string | null;
  workshop?: string | null;
  scheduled_on?: string | null;
  plan_id?: string | null;
}

export interface FuelLog {
  id: string;
  filled_at: string;
  liters: string;
  total_amount: string;
  unit_price: string;
  odometer_km: string;
  full_tank: boolean;
  station: string | null;
  driver_id: string | null;
  driver_name: string | null;
  km_per_liter: string | null;
}

export interface FuelStats {
  liters: string;
  amount: string;
  average_km_per_liter: string | null;
  cost_per_km: string | null;
}

export interface FuelLogInput {
  filled_at: string;
  liters: string;
  total_amount: string;
  odometer_km: string;
  full_tank: boolean;
  station?: string | null;
  driver_id?: string | null;
}

export interface TrackerModel {
  key: string;
  brand: string;
  models: string;
  port: number;
  short_identifier: boolean;
}

export interface GpsSetup {
  configured: boolean;
  server_url: string | null;
  host: string | null;
  private_network: boolean;
  phone_config_uri: string | null;
  trackers: TrackerModel[];
}

export type GpsSignal = 'unlinked' | 'waiting' | 'reporting' | 'silent' | 'unavailable';

export interface GpsStatus {
  state: GpsSignal;
  kind: 'phone' | 'tracker' | null;
  server_configured: boolean;
  last_update: string | null;
  battery_level: number | null;
  readings?: GpsReadings;
}

export interface GpsReadings {
  ignition?: boolean;
  voltage?: number;
  satellites?: number;
  engine_hours?: number;
  temperature?: number;
}

export interface FleetAlert {
  vehicle_id: string | null;
  driver_id: string | null;
  subject: string;
  branch_name: string;
  code: string;
  severity: 'blocking' | 'warning';
  message: string;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

const json = (method: string, body?: unknown) => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) })
});

export const fleetApi = {
  list: (
    params: {
      status?: VehicleStatus | '';
      kind?: string;
      search?: string;
      include_retired?: boolean;
      page?: number;
      size?: number;
    },
    signal?: AbortSignal
  ) =>
    apiFetch<FleetPage<FleetVehicle>>(
      `/fleet/vehicles${query({ ...params, branch_id: branch.id })}`,
      { signal }
    ),
  summary: (signal?: AbortSignal) =>
    apiFetch<FleetSummary>(`/fleet/vehicles/summary${query({ branch_id: branch.id })}`, {
      signal
    }),
  get: (id: string, signal?: AbortSignal) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}`, { signal }),
  create: (data: VehicleCreateInput) =>
    apiFetch<FleetVehicle>('/fleet/vehicles', json('POST', data)),
  update: (id: string, data: Partial<VehicleInput>) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}`, json('PATCH', data)),
  setStatus: (id: string, status: Exclude<VehicleStatus, 'maintenance'>, reason?: string) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}/status`, json('POST', { status, reason })),
  changeBranch: (id: string, branchId: string, reason: string) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/branch`,
      json('POST', { branch_id: branchId, reason })
    ),
  photos: (id: string) => apiFetch<VehiclePhoto[]>(`/fleet/vehicles/${id}/photos`),
  addPhoto: (id: string, url: string, caption?: string) =>
    apiFetch<VehiclePhoto>(`/fleet/vehicles/${id}/photos`, json('POST', { url, caption })),
  deletePhoto: (id: string, photoId: string) =>
    apiFetch<void>(`/fleet/vehicles/${id}/photos/${photoId}`, { method: 'DELETE' }),
  documents: (id: string) => ownedDocuments(`/fleet/vehicles/${id}`),
  linkGps: (id: string, uniqueId: string) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/gps-device`,
      json('PUT', { unique_id: uniqueId })
    ),
  vehicleTypes: (includeInactive = false) =>
    apiFetch<FleetVehicleType[]>(
      `/fleet/vehicle-types${includeInactive ? '?include_inactive=true' : ''}`
    ),
  createVehicleType: (data: FleetVehicleTypeInput) =>
    apiFetch<FleetVehicleType>('/fleet/vehicle-types', json('POST', data)),
  updateVehicleType: (id: string, data: FleetVehicleTypeInput) =>
    apiFetch<FleetVehicleType>(`/fleet/vehicle-types/${id}`, json('PATCH', data)),
  couple: (id: string, trailerId: string) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/coupling`,
      json('PUT', { trailer_id: trailerId })
    ),
  uncouple: (id: string) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}/coupling`, { method: 'DELETE' }),
  linkPhone: (id: string, replace = false) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/gps-device`,
      json('PUT', { kind: 'phone', replace })
    ),
  gpsSetup: (id: string) => apiFetch<GpsSetup>(`/fleet/vehicles/${id}/gps-setup`),
  gpsStatus: (id: string, signal?: AbortSignal) =>
    apiFetch<GpsStatus>(`/fleet/vehicles/${id}/gps-status`, { signal }),
  unlinkGps: (id: string) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}/gps-device`, { method: 'DELETE' }),
  alerts: (signal?: AbortSignal) =>
    apiFetch<FleetAlert[]>(`/fleet/alerts${query({ branch_id: branch.id })}`, { signal }),
  odometer: (id: string) => apiFetch<OdometerReading[]>(`/fleet/vehicles/${id}/odometer`),
  addOdometer: (id: string, data: { reading_km: string; read_at?: string; notes?: string }) =>
    apiFetch<OdometerReading>(`/fleet/vehicles/${id}/odometer`, json('POST', data)),
  plans: (id: string) => apiFetch<MaintenancePlan[]>(`/fleet/vehicles/${id}/maintenance-plans`),
  createPlan: (id: string, data: MaintenancePlanInput) =>
    apiFetch<MaintenancePlan>(`/fleet/vehicles/${id}/maintenance-plans`, json('POST', data)),
  updatePlan: (id: string, planId: string, data: MaintenancePlanInput) =>
    apiFetch<MaintenancePlan>(
      `/fleet/vehicles/${id}/maintenance-plans/${planId}`,
      json('PUT', data)
    ),
  deactivatePlan: (id: string, planId: string) =>
    apiFetch<void>(`/fleet/vehicles/${id}/maintenance-plans/${planId}`, { method: 'DELETE' }),
  orders: (id: string) => apiFetch<MaintenanceOrder[]>(`/fleet/vehicles/${id}/maintenance-orders`),
  createOrder: (id: string, data: MaintenanceOrderInput) =>
    apiFetch<MaintenanceOrder>(`/fleet/vehicles/${id}/maintenance-orders`, json('POST', data)),
  startOrder: (id: string, orderId: string) =>
    apiFetch<MaintenanceOrder>(
      `/fleet/vehicles/${id}/maintenance-orders/${orderId}/start`,
      json('POST')
    ),
  completeOrder: (
    id: string,
    orderId: string,
    data: { odometer_km: string; cost: string; workshop?: string | null; notes?: string | null }
  ) =>
    apiFetch<MaintenanceOrder>(
      `/fleet/vehicles/${id}/maintenance-orders/${orderId}/complete`,
      json('POST', data)
    ),
  cancelOrder: (id: string, orderId: string, reason: string) =>
    apiFetch<MaintenanceOrder>(
      `/fleet/vehicles/${id}/maintenance-orders/${orderId}/cancel`,
      json('POST', { reason })
    ),
  fuel: (id: string) =>
    apiFetch<{ items: FuelLog[]; stats: FuelStats }>(`/fleet/vehicles/${id}/fuel-logs`),
  addFuel: (id: string, data: FuelLogInput) =>
    apiFetch<FuelLog>(`/fleet/vehicles/${id}/fuel-logs`, json('POST', data))
};
