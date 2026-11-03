import { apiFetch, type DocumentUploadTicket } from '$lib/api/client';
import { ownedDocuments } from '$lib/api/owned-documents';
import type { Compliance, FleetPage } from '$lib/features/fleet/api';
import type { BaseImage, LicenseClass } from '$lib/features/fleet/catalog';
import { branch } from '$lib/stores/branch.svelte';

export type DriverStatus = 'active' | 'suspended' | 'inactive';

export const DRIVER_STATUS_META: Record<DriverStatus, { label: string; tone: string }> = {
  active: { label: 'Activo', tone: 'available' },
  suspended: { label: 'Suspendido', tone: 'maintenance' },
  inactive: { label: 'Inactivo', tone: 'muted' }
};

export interface Driver {
  id: string;
  employee: {
    id: string;
    code: string;
    name: string;
    initials: string;
    document_id: string | null;
    phone: string | null;
    photo_url: string | null;
    position: string | null;
    status: string;
  };
  branch_id: string;
  branch_name: string;
  license: {
    license_class: LicenseClass;
    number: string | null;
    expires_on: string | null;
    document_id: string | null;
  };
  status: DriverStatus;
  status_reason: string | null;
  notes: string | null;
  vehicle: {
    assignment_id: string;
    vehicle_id: string;
    code: string;
    plate: string | null;
    kind: string;
    kind_name: string;
    base_image: BaseImage | null;
    since: string;
  } | null;
  compliance: Compliance;
  created_at: string;
  updated_at: string;
}

export type CaptureSide = 'front' | 'back';
export type CaptureStatus =
  'draft' | 'pending' | 'processing' | 'ready' | 'failed' | 'confirmed' | 'cancelled' | 'expired';

export interface LicenseValues {
  license_class: string | null;
  expires: string | null;
  number: string | null;
  surnames: string | null;
  given_names: string | null;
  dui: string | null;
  issued: string | null;
  birth: string | null;
  control_number: string | null;
}

export interface LicenseIssue {
  code: string;
  severity: 'error' | 'mismatch' | 'warning';
  field: string;
  message: string;
}

export interface LicenseCapture {
  id: string;
  status: CaptureStatus;
  failure_code: string | null;
  extraction_available: boolean;
  front: { document_id: string | null; status: string | null; extracted: boolean };
  back: { document_id: string | null; status: string | null; extracted: boolean };
  values: LicenseValues;
  issues: LicenseIssue[];
}

export interface DriversSummary {
  total: number;
  active: number;
  fit: number;
  warning: number;
  blocked: number;
  assigned: number;
}

export interface DriverCandidate {
  employee_id: string;
  code: string;
  name: string;
  position: string | null;
  photo_url: string | null;
}

export interface Assignment {
  id: string;
  vehicle_id: string;
  vehicle_code: string;
  vehicle_plate: string;
  driver_id: string;
  driver_name: string;
  starts_at: string;
  ends_at: string | null;
  end_reason: string | null;
}

export interface DriverTrip {
  transfer_id: string;
  code: string;
  status: string;
  vehicle_code: string | null;
  origin_branch: string;
  destination_branch: string;
  dispatched_at: string | null;
  received_at: string | null;
}

function query(params: Record<string, string | number | null | undefined>): string {
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

export const driversApi = {
  list: (
    params: { status?: DriverStatus | ''; search?: string; page?: number; size?: number },
    signal?: AbortSignal
  ) =>
    apiFetch<FleetPage<Driver>>(`/drivers${query({ ...params, branch_id: branch.id })}`, {
      signal
    }),
  forBranch: (branchId: string) =>
    apiFetch<FleetPage<Driver>>(
      `/drivers${query({ branch_id: branchId, status: 'active', size: 100 })}`
    ),
  summary: (signal?: AbortSignal) =>
    apiFetch<DriversSummary>(`/drivers/summary${query({ branch_id: branch.id })}`, { signal }),
  get: (id: string, signal?: AbortSignal) => apiFetch<Driver>(`/drivers/${id}`, { signal }),
  candidates: (branchId: string, search?: string) =>
    apiFetch<DriverCandidate[]>(`/drivers/candidates${query({ branch_id: branchId, search })}`),
  create: (data: {
    employee_id: string;
    branch_id: string;
    license_class: LicenseClass;
    notes?: string | null;
  }) => apiFetch<Driver>('/drivers', json('POST', data)),
  update: (id: string, data: { license_class?: LicenseClass; notes?: string | null }) =>
    apiFetch<Driver>(`/drivers/${id}`, json('PATCH', data)),
  setStatus: (id: string, status: DriverStatus, reason?: string) =>
    apiFetch<Driver>(`/drivers/${id}/status`, json('POST', { status, reason })),
  changeBranch: (id: string, branchId: string, reason: string) =>
    apiFetch<Driver>(`/drivers/${id}/branch`, json('POST', { branch_id: branchId, reason })),
  assignments: (id: string) => apiFetch<Assignment[]>(`/drivers/${id}/assignments`),
  trips: (id: string) => apiFetch<DriverTrip[]>(`/drivers/${id}/trips`),
  documents: (id: string) => ownedDocuments(`/drivers/${id}`),
  captureCapabilities: () =>
    apiFetch<{ enabled: boolean; extraction_available: boolean }>(
      '/drivers/license-captures/capabilities'
    ),
  openCapture: (id: string) =>
    apiFetch<LicenseCapture>(`/drivers/${id}/license-captures`, json('POST')),
  getCapture: (id: string, captureId: string, signal?: AbortSignal) =>
    apiFetch<LicenseCapture>(`/drivers/${id}/license-captures/${captureId}`, { signal }),
  startCaptureUpload: (
    id: string,
    captureId: string,
    side: CaptureSide,
    data: { content_type: string; size_bytes: number; checksum_sha256: string }
  ) =>
    apiFetch<DocumentUploadTicket>(
      `/drivers/${id}/license-captures/${captureId}/sides/${side}/upload`,
      json('POST', data)
    ),
  completeCaptureUpload: (id: string, captureId: string, side: CaptureSide) =>
    apiFetch<LicenseCapture>(
      `/drivers/${id}/license-captures/${captureId}/sides/${side}/complete`,
      json('POST')
    ),
  capturePreview: (id: string, captureId: string, side: CaptureSide) =>
    apiFetch<{ url: string; expires_at: string }>(
      `/drivers/${id}/license-captures/${captureId}/sides/${side}/preview-url`,
      json('POST')
    ),
  checkCapture: (id: string, captureId: string, values: LicenseValues) =>
    apiFetch<LicenseIssue[]>(
      `/drivers/${id}/license-captures/${captureId}/check`,
      json('POST', values)
    ),
  confirmCapture: (
    id: string,
    captureId: string,
    data: {
      values: LicenseValues;
      acknowledged_warnings: string[];
      override_reason?: string | null;
    }
  ) => apiFetch<Driver>(`/drivers/${id}/license-captures/${captureId}/confirm`, json('POST', data)),
  cancelCapture: (id: string, captureId: string) =>
    apiFetch<void>(`/drivers/${id}/license-captures/${captureId}`, json('DELETE')),
  assign: (
    vehicleId: string,
    driverId: string,
    overrideReason?: string,
    cover?: { expected_end_on: string | null; covers_driver_id: string | null }
  ) =>
    apiFetch<Assignment>(
      `/fleet/vehicles/${vehicleId}/assignment`,
      json('POST', { driver_id: driverId, override_reason: overrideReason || undefined, ...cover })
    ),
  endAssignment: (vehicleId: string, reason: string) =>
    apiFetch<void>(`/fleet/vehicles/${vehicleId}/assignment/end`, json('POST', { reason })),
  vehicleAssignments: (vehicleId: string) =>
    apiFetch<Assignment[]>(`/fleet/vehicles/${vehicleId}/assignments`)
};
