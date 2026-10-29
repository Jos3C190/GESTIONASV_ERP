import type { PageMeta } from '$lib/api/client';
import type {
  CapacityEnforcementMode,
  CapacityProfile,
  CapacityStatus
} from '$lib/features/warehouses/types';

export type LocationType =
  | 'standard'
  | 'bulk'
  | 'receiving'
  | 'reserve'
  | 'picking'
  | 'staging'
  | 'quality'
  | 'packing'
  | 'shipping'
  | 'returns'
  | 'virtual'
  | string;

export type LocationLifecycleStatus =
  | 'draft'
  | 'active'
  | 'blocked'
  | 'blocked_in'
  | 'blocked_out'
  | 'maintenance'
  | 'retired'
  | string;

export interface LocationOut {
  id: string;
  warehouse_id: string;
  capacity_group_id: string | null;
  code: string;
  area: string | null;
  aisle: string;
  rack: string;
  level: string;
  position: string;
  certified_max_weight_kg: number | null;
  operational_max_weight_kg: number | null;
  certified_usable_volume_m3: number | null;
  operational_usable_volume_m3: number | null;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  capacity_status: CapacityStatus;
  storage_eligible: boolean;
  usable_length_m: number | null;
  usable_width_m: number | null;
  usable_height_m: number | null;
  notes: string | null;
  location_type: LocationType;
  lifecycle_status: LocationLifecycleStatus;
  barcode: string | null;
  verification_code: string | null;
  pick_sequence: number | null;
  putaway_sequence: number | null;
  external_id: string | null;
  scheme_id: string | null;
  scheme_version: number | null;
  code_source: 'generated' | 'legacy' | string;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface LocationPage {
  items: LocationOut[];
  meta: PageMeta;
}

export interface LocationSummary {
  total: number;
  storage_eligible: number;
  capacity_configured: number;
  capacity_incomplete: number;
  active: number;
  inactive: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  areas: Record<string, number>;
}

export interface LocationListParams {
  page?: number;
  size?: number;
  search?: string;
  area?: string;
  location_type?: string;
  lifecycle_status?: string;
  is_active?: boolean;
  capacity_group_id?: string;
  include_descendants?: boolean;
  unassigned?: boolean;
  signal?: AbortSignal;
}

export interface LocationDraft {
  capacity_group_id: string;
  area: string;
  aisle: string;
  rack: string;
  level: string;
  position: string;
  certified_max_weight_kg: string | number;
  operational_max_weight_kg: string | number;
  certified_usable_volume_m3: string | number;
  operational_usable_volume_m3: string | number;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  storage_eligible: boolean;
  usable_length_m: string | number;
  usable_width_m: string | number;
  usable_height_m: string | number;
  notes: string;
  location_type: string;
  lifecycle_status: string;
  pick_sequence: string | number;
  putaway_sequence: string | number;
  external_id: string;
  barcode: string;
  verification_code: string;
}

export interface LocationMutationInput {
  capacity_group_id: string | null;
  area: string | null;
  aisle: string;
  rack: string;
  level: string;
  position: string;
  certified_max_weight_kg: number | null;
  operational_max_weight_kg: number | null;
  certified_usable_volume_m3: number | null;
  operational_usable_volume_m3: number | null;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  storage_eligible: boolean;
  usable_length_m: number | null;
  usable_width_m: number | null;
  usable_height_m: number | null;
  notes: string | null;
  location_type: string;
  lifecycle_status: string;
  pick_sequence: number | null;
  putaway_sequence: number | null;
  external_id: string | null;
  barcode: string | null;
  verification_code: string | null;
  /** Fija la versión previsualizada para evitar un código distinto al guardar. */
  scheme_version?: number;
}

export interface LocationUpdateInput extends LocationMutationInput {
  /** Versión leída al abrir la edición; evita sobrescribir cambios concurrentes. */
  expected_updated_at: string | null;
}

export type LocationCodePreviewInput = Pick<
  LocationMutationInput,
  'area' | 'aisle' | 'rack' | 'level' | 'position'
> & {
  /** Excluye la propia ubicación al previsualizar una edición. */
  exclude_location_id?: string;
};

export interface LocationCodePreview {
  code: string;
  normalized_components: Record<string, string>;
  scheme_id: string;
  scheme_version: number;
  code_exists: boolean;
  coordinates_exist: boolean;
}

export interface LocationCodeSegment {
  key: string;
  label: string;
  prefix: string;
  width: number;
  pad_char: string;
  required: boolean;
}

export interface LocationCodeScheme {
  id: string;
  warehouse_id: string;
  name: string;
  version: number;
  separator: string;
  segments: LocationCodeSegment[];
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface LocationCodeSchemeInput {
  name: string;
  separator: string;
  segments: LocationCodeSegment[];
}

export interface LocationBatchAxis {
  key: 'aisle' | 'rack' | 'level' | 'position' | string;
  start?: string;
  end?: string;
  step?: number;
  values?: string[];
}

export interface LocationBatchDefaults {
  area?: string | null;
  capacity_group_id?: string | null;
  certified_max_weight_kg?: number | null;
  operational_max_weight_kg?: number | null;
  certified_usable_volume_m3?: number | null;
  operational_usable_volume_m3?: number | null;
  capacity_profile: CapacityProfile;
  capacity_enforcement_mode: CapacityEnforcementMode;
  storage_eligible: boolean;
  usable_length_m?: number | null;
  usable_width_m?: number | null;
  usable_height_m?: number | null;
  location_type: string;
  lifecycle_status?: string;
  notes?: string | null;
}

export interface LocationBatchPreviewInput {
  idempotency_key: string;
  scheme_version?: number;
  axes: LocationBatchAxis[];
  defaults: LocationBatchDefaults;
}

export type LocationBatchOperation = 'create' | 'update' | 'unchanged' | 'conflict' | 'error';

export interface LocationBatchRow {
  id: string;
  row_number: number;
  operation: LocationBatchOperation | string;
  code: string | null;
  normalized_data: Record<string, unknown>;
  diff: Record<string, unknown>;
  errors: string[];
}

export interface LocationBatchJob {
  id: string;
  warehouse_id: string;
  kind: 'generate' | 'import' | string;
  status: 'preview' | 'ready' | 'publishing' | 'published' | 'failed' | string;
  idempotency_key: string;
  input_checksum: string;
  scheme_id: string | null;
  scheme_version: number | null;
  total_rows: number;
  create_count: number;
  update_count: number;
  unchanged_count: number;
  conflict_count: number;
  error_count: number;
  summary: Record<string, unknown>;
  /** Permisos calculados por el servidor según el impacto real del lote. */
  required_permissions?: string[];
  /** Metadatos de la página de filas. `rows_meta` es el contrato canónico. */
  rows_meta?: PageMeta;
  /** Compatibilidad temporal con respuestas que expongan la meta en la raíz. */
  meta?: PageMeta;
  created_by: string;
  published_by: string | null;
  created_at: string;
  published_at: string | null;
  rows: LocationBatchRow[];
}

export function locationBatchRequiredPermissions(job: LocationBatchJob): string[] {
  const summaryPermissions = job.summary.required_permissions;
  const candidates = Array.isArray(job.required_permissions)
    ? job.required_permissions
    : Array.isArray(summaryPermissions)
      ? summaryPermissions
      : [];
  return [...new Set(candidates.filter((value): value is string => typeof value === 'string'))];
}

const LOCATION_PERMISSION_LABELS: Record<string, string> = {
  'locations.create': 'Crear ubicaciones',
  'locations.update': 'Editar ubicaciones',
  'locations.recode': 'Recodificar rutas',
  'locations.activate': 'Activar ubicaciones retiradas',
  'locations.deactivate': 'Retirar ubicaciones',
  'locations.commission': 'Cambiar estados operativos',
  'locations.bulk': 'Generar ubicaciones por lotes',
  'locations.import': 'Importar ubicaciones'
};

export function locationPermissionLabel(permission: string): string {
  return LOCATION_PERMISSION_LABELS[permission] ?? permission;
}

export interface LocationImportPreviewInput {
  file: File;
  idempotency_key: string;
  scheme_version?: number;
}

export const LOCATION_TYPE_OPTIONS = [
  {
    value: 'standard',
    label: 'Almacenamiento general',
    description: 'Ubicación física de uso general.'
  },
  { value: 'bulk', label: 'Piso / granel', description: 'Cajas, sacos o materiales sin rack.' },
  { value: 'receiving', label: 'Recepción', description: 'Ingreso y verificación de mercancía.' },
  { value: 'reserve', label: 'Reserva', description: 'Existencias de reposición y largo plazo.' },
  { value: 'picking', label: 'Picking', description: 'Preparación eficiente de pedidos.' },
  { value: 'staging', label: 'Consolidación', description: 'Permanencia temporal entre procesos.' },
  {
    value: 'quality',
    label: 'Control de calidad',
    description: 'Inspección y liberación de mercancía.'
  },
  { value: 'packing', label: 'Empaque', description: 'Embalaje y verificación final del pedido.' },
  { value: 'shipping', label: 'Despacho', description: 'Salida y carga de mercancía.' },
  {
    value: 'returns',
    label: 'Devoluciones',
    description: 'Recepción y clasificación de retornos.'
  },
  { value: 'virtual', label: 'Virtual', description: 'Estado lógico sin espacio físico.' }
] as const;

export const LOCATION_STATUS_OPTIONS = [
  { value: 'draft', label: 'Borrador' },
  { value: 'active', label: 'Activa' },
  { value: 'blocked', label: 'Bloqueada para toda operación' },
  { value: 'blocked_in', label: 'Bloqueada para entradas' },
  { value: 'blocked_out', label: 'Bloqueada para salidas' },
  { value: 'maintenance', label: 'Mantenimiento' },
  { value: 'retired', label: 'Retirada' }
] as const;

export function locationTypeLabel(value: string): string {
  return LOCATION_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function locationStatusLabel(value: string): string {
  return LOCATION_STATUS_OPTIONS.find((option) => option.value === value)?.label ?? value;
}
