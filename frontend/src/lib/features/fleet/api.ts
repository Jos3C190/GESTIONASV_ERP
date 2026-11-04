import { apiFetch, type DocumentUploadTicket } from '$lib/api/client';
import { ownedDocuments } from '$lib/api/owned-documents';
import type {
  CaptureCheck,
  CaptureSide,
  CaptureState,
  CaptureValues
} from '$lib/features/document-capture/types';
import { branch } from '$lib/stores/branch.svelte';
import type {
  CostCategory,
  FuelType,
  IncidentKind,
  IncidentResponsible,
  IncidentSeverity,
  IncidentStatus,
  LicenseClass,
  OperationalStatus,
  Ownership,
  BaseImage,
  MeterUnit,
  VehicleStatus
} from './catalog';

export type {
  CostCategory,
  IncidentKind,
  IncidentResponsible,
  IncidentSeverity,
  IncidentStatus,
  Ownership
};

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
  expected_end_on?: string | null;
  covers_driver_id?: string | null;
  covers_driver_name?: string | null;
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
  chassis_number: string | null;
  engine_number: string | null;
  kind: string;
  type: FleetVehicleTypeInfo;
  coupling: VehicleCoupling | null;
  brand: string;
  model: string;
  year: number;
  color: string | null;
  capacity_kg: string | null;
  tank_liters: string | null;
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
  ownership: Ownership;
  owner_supplier_id: number | null;
  owner_supplier_name: string | null;
  contract_reference: string | null;
  contract_ends_on: string | null;
  monthly_fee: string | null;
  loan?: {
    id: string;
    to_branch_id: string;
    to_branch_name: string;
    expected_return_on: string;
  } | null;
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

export interface CirculationConfirmed {
  vehicle: FleetVehicle;
  filled_fields: string[];
  skipped_fields: string[];
}

export interface VehicleInput {
  plate: string | null;
  vin?: string | null;
  chassis_number?: string | null;
  engine_number?: string | null;
  kind: string;
  brand: string;
  model: string;
  year: number;
  color?: string | null;
  capacity_kg: string | null;
  tank_liters?: string | null;
  fuel_type: FuelType;
  notes?: string | null;
  ownership?: Ownership;
  owner_supplier_id?: number | null;
  contract_reference?: string | null;
  contract_ends_on?: string | null;
  monthly_fee?: string | null;
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
  source: 'manual' | 'fuel' | 'maintenance' | 'gps' | 'meter_replacement';
  notes: string | null;
  recorded_by_name: string | null;
  voided_at?: string | null;
  voided_by_name?: string | null;
  void_reason?: string | null;
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
  supplier_id?: number | null;
  receipt_document_id?: string | null;
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
  supplier_id?: number | null;
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
  supplier_id?: number | null;
  receipt_document_id?: string | null;
  driver_id: string | null;
  driver_name: string | null;
  km_per_liter: string | null;
  voided_at?: string | null;
  voided_by_name?: string | null;
  void_reason?: string | null;
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
  supplier_id?: number | null;
  receipt_document_id?: string | null;
  driver_id?: string | null;
}

export interface FleetSupplier {
  id: number;
  code: string;
  name: string;
}

export interface FleetCost {
  id: string;
  category: CostCategory;
  incurred_on: string;
  amount: string;
  description: string | null;
  supplier_id: number | null;
  supplier_name: string | null;
  document_id: string | null;
  recorded_by_name: string | null;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
}

export interface FleetCostInput {
  category: CostCategory;
  incurred_on: string;
  amount: string;
  description?: string | null;
  supplier_id?: number | null;
  document_id?: string | null;
}

export interface CostReportRow {
  vehicle_id: string;
  code: string;
  plate: string | null;
  kind_name: string;
  branch_name: string;
  meter_unit: MeterUnit;
  fuel: string;
  maintenance: string;
  other: string;
  incidents: string;
  total: string;
  distance: string;
  cost_per_unit: string | null;
}

export interface FleetIncident {
  id: string;
  vehicle_id: string;
  vehicle_code: string;
  driver_id: string | null;
  driver_name: string | null;
  kind: IncidentKind;
  severity: IncidentSeverity;
  responsible: IncidentResponsible;
  status: IncidentStatus;
  occurred_at: string;
  location: string | null;
  description: string;
  cost: string | null;
  insurance_claim: string | null;
  document_id: string | null;
  resolution: string | null;
  reported_by_name: string | null;
  closed_at: string | null;
  closed_by_name: string | null;
  vehicle_taken_out?: boolean;
}

export interface FleetIncidentInput {
  kind: IncidentKind;
  severity: IncidentSeverity;
  responsible: IncidentResponsible;
  occurred_at: string;
  location?: string | null;
  description: string;
  driver_id?: string | null;
  cost?: string | null;
  insurance_claim?: string | null;
  document_id?: string | null;
  take_out_of_service?: boolean;
}

export interface FleetIncidentUpdate {
  status?: IncidentStatus;
  responsible?: IncidentResponsible;
  resolution?: string | null;
  cost?: string | null;
  insurance_claim?: string | null;
  document_id?: string | null;
}

export interface InspectionItem {
  id: string;
  name: string;
  is_critical: boolean;
  is_active: boolean;
}

export interface InspectionResult {
  id: string;
  item_name: string;
  is_critical: boolean;
  passed: boolean;
  notes: string | null;
  photo_url: string | null;
  resolved_at: string | null;
  resolved_by_name: string | null;
  resolution: string | null;
}

export interface FleetInspection {
  id: string;
  inspected_at: string;
  passed: boolean;
  notes: string | null;
  inspected_by_name: string | null;
  results: InspectionResult[];
}

export interface FleetInspectionInput {
  driver_id?: string | null;
  notes?: string | null;
  results: { item_id: string; passed: boolean; notes?: string | null; photo_url?: string | null }[];
}

export interface FleetSettings {
  block_overdue_maintenance: boolean;
  require_inspection: boolean;
  block_overweight: boolean;
  inspection_valid_hours: number;
  document_warning_days: number;
  maintenance_warning_km: number;
  maintenance_warning_days: number;
}

export interface FleetLoan {
  id: string;
  from_branch_id: string;
  from_branch_name: string;
  to_branch_id: string;
  to_branch_name: string;
  starts_on: string;
  expected_return_on: string;
  reason: string;
  returned_at: string | null;
  created_by_name: string | null;
}

export interface FleetReservation {
  id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  status: 'active' | 'cancelled';
  reserved_by_name: string | null;
  cancel_reason: string | null;
}

export interface CostReport {
  date_from: string;
  date_to: string;
  rows: CostReportRow[];
  totals: { fuel: string; maintenance: string; other: string; incidents: string; total: string };
  other_by_category: Partial<Record<CostCategory, string>>;
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
  circulationCaptureCapabilities: () =>
    apiFetch<{ enabled: boolean; extraction_available: boolean }>(
      '/fleet/circulation-captures/capabilities'
    ),
  circulationCaptures: (id: string) => {
    const base = `/fleet/vehicles/${id}/circulation-captures`;
    return {
      open: () => apiFetch<CaptureState>(base, json('POST')),
      get: (captureId: string) => apiFetch<CaptureState>(`${base}/${captureId}`),
      startUpload: (
        captureId: string,
        side: CaptureSide,
        data: { content_type: string; size_bytes: number; checksum_sha256: string }
      ) =>
        apiFetch<DocumentUploadTicket>(
          `${base}/${captureId}/sides/${side}/upload`,
          json('POST', data)
        ),
      completeUpload: (captureId: string, side: CaptureSide) =>
        apiFetch<CaptureState>(`${base}/${captureId}/sides/${side}/complete`, json('POST')),
      preview: (captureId: string, side: CaptureSide) =>
        apiFetch<{ url: string; expires_at: string }>(
          `${base}/${captureId}/sides/${side}/preview-url`,
          json('POST')
        ),
      check: (captureId: string, values: CaptureValues) =>
        apiFetch<CaptureCheck>(`${base}/${captureId}/check`, json('POST', values)),
      confirm: (
        captureId: string,
        data: { values: CaptureValues; acknowledged_warnings: string[] }
      ) => apiFetch<CirculationConfirmed>(`${base}/${captureId}/confirm`, json('POST', data)),
      cancel: (captureId: string) => apiFetch<void>(`${base}/${captureId}`, json('DELETE'))
    };
  },
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
  voidReading: (id: string, readingId: string, reason: string) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/odometer/${readingId}/void`,
      json('POST', { reason })
    ),
  replaceMeter: (id: string, data: { reading_km: string; reason: string }) =>
    apiFetch<FleetVehicle>(`/fleet/vehicles/${id}/odometer/replace-meter`, json('POST', data)),
  odometerTotal: (id: string) =>
    apiFetch<{ total: string; replacements: number }>(`/fleet/vehicles/${id}/odometer/total`),
  voidFuel: (id: string, logId: string, reason: string) =>
    apiFetch<FleetVehicle>(
      `/fleet/vehicles/${id}/fuel-logs/${logId}/void`,
      json('POST', { reason })
    ),
  correctFuel: (id: string, logId: string, data: FuelLogInput & { reason: string }) =>
    apiFetch<FuelLog>(`/fleet/vehicles/${id}/fuel-logs/${logId}`, json('PUT', data)),
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
    data: {
      odometer_km: string;
      cost: string;
      workshop?: string | null;
      supplier_id?: number | null;
      receipt_document_id?: string | null;
      notes?: string | null;
    }
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
    apiFetch<FuelLog>(`/fleet/vehicles/${id}/fuel-logs`, json('POST', data)),
  suppliers: () => apiFetch<FleetSupplier[]>('/fleet/suppliers'),
  settings: () => apiFetch<FleetSettings>('/fleet/settings'),
  saveSettings: (data: FleetSettings) =>
    apiFetch<FleetSettings>('/fleet/settings', json('PUT', data)),
  loans: (id: string) => apiFetch<FleetLoan[]>(`/fleet/vehicles/${id}/loans`),
  lend: (id: string, data: { to_branch_id: string; expected_return_on: string; reason: string }) =>
    apiFetch<FleetLoan>(`/fleet/vehicles/${id}/loans`, json('POST', data)),
  returnLoan: (id: string, loanId: string) =>
    apiFetch<FleetLoan>(`/fleet/vehicles/${id}/loans/${loanId}/return`, json('POST')),
  reservations: (id: string) => apiFetch<FleetReservation[]>(`/fleet/vehicles/${id}/reservations`),
  addReservation: (id: string, data: { starts_at: string; ends_at: string; reason: string }) =>
    apiFetch<FleetReservation>(`/fleet/vehicles/${id}/reservations`, json('POST', data)),
  cancelReservation: (id: string, reservationId: string, reason: string) =>
    apiFetch<FleetReservation>(
      `/fleet/vehicles/${id}/reservations/${reservationId}/cancel`,
      json('POST', { reason })
    ),
  incidents: (id: string) => apiFetch<FleetIncident[]>(`/fleet/vehicles/${id}/incidents`),
  driverIncidents: (driverId: string) =>
    apiFetch<FleetIncident[]>(`/fleet/drivers/${driverId}/incidents`),
  addIncident: (id: string, data: FleetIncidentInput) =>
    apiFetch<FleetIncident>(`/fleet/vehicles/${id}/incidents`, json('POST', data)),
  updateIncident: (id: string, incidentId: string, data: FleetIncidentUpdate) =>
    apiFetch<FleetIncident>(`/fleet/vehicles/${id}/incidents/${incidentId}`, json('PATCH', data)),
  inspectionItems: (includeInactive = false) =>
    apiFetch<InspectionItem[]>(
      `/fleet/inspection-items${includeInactive ? '?include_inactive=true' : ''}`
    ),
  createInspectionItem: (data: { name: string; is_critical: boolean }) =>
    apiFetch<InspectionItem>('/fleet/inspection-items', json('POST', data)),
  updateInspectionItem: (
    id: string,
    data: { name: string; is_critical: boolean; is_active: boolean }
  ) => apiFetch<InspectionItem>(`/fleet/inspection-items/${id}`, json('PATCH', data)),
  inspections: (id: string) => apiFetch<FleetInspection[]>(`/fleet/vehicles/${id}/inspections`),
  addInspection: (id: string, data: FleetInspectionInput) =>
    apiFetch<FleetInspection>(`/fleet/vehicles/${id}/inspections`, json('POST', data)),
  resolveInspectionResult: (id: string, resultId: string, reason: string) =>
    apiFetch<InspectionResult>(
      `/fleet/vehicles/${id}/inspection-results/${resultId}/resolve`,
      json('POST', { reason })
    ),
  costs: (id: string) => apiFetch<FleetCost[]>(`/fleet/vehicles/${id}/costs`),
  addCost: (id: string, data: FleetCostInput) =>
    apiFetch<FleetCost>(`/fleet/vehicles/${id}/costs`, json('POST', data)),
  voidCost: (id: string, costId: string, reason: string) =>
    apiFetch<FleetCost>(`/fleet/vehicles/${id}/costs/${costId}/void`, json('POST', { reason })),
  costReport: (
    params: { date_from: string; date_to: string; vehicle_id?: string },
    signal?: AbortSignal
  ) =>
    apiFetch<CostReport>(
      `/fleet/cost-report${query({ ...params, branch_id: params.vehicle_id ? null : branch.id })}`,
      { signal }
    )
};
