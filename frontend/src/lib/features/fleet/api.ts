import { apiFetch } from '$lib/api/client';
import { ownedDocuments } from '$lib/api/owned-documents';
import { branch } from '$lib/stores/branch.svelte';
import type {
  FuelType,
  LicenseClass,
  OperationalStatus,
  VehicleKind,
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

export interface FleetVehicle {
  id: string;
  code: string;
  plate: string;
  vin: string | null;
  kind: VehicleKind;
  brand: string;
  model: string;
  year: number;
  color: string | null;
  capacity_kg: string;
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
  plate: string;
  vin?: string | null;
  kind: VehicleKind;
  brand: string;
  model: string;
  year: number;
  color?: string | null;
  capacity_kg: string;
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
      kind?: VehicleKind | '';
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
  documents: (id: string) => ownedDocuments(`/fleet/vehicles/${id}`)
};
