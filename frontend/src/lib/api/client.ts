/**
 * Centralised API client with:
 * - Authorization header injection from the session store.
 * - Transparent refresh-token rotation on 401 (calls /auth/refresh, retries).
 * - Uniform error typing (HttpError with code + message + status).
 *
 * The refresh token is sent as an httpOnly cookie automatically by the browser
 * for same-origin requests. For cross-origin (dev), the backend's CORS allows
 * credentials and the cookie is set on the /api/v1/auth path.
 */
import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { session } from '$lib/stores/session.svelte';
import { company } from '$lib/stores/company.svelte';
import { branch, type OperationalContext } from '$lib/stores/branch.svelte';
import { buildUserListQuery, type UserStatusFilter } from '$lib/features/users/list-query';

export const API_BASE_URL = env.PUBLIC_API_URL ?? 'http://localhost:8000';
const API_PREFIX = '/api/v1';
const REFRESH_ENDPOINT = `${API_PREFIX}/auth/refresh`;

export class HttpError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
    this.name = 'HttpError';
  }
}

async function parseError(res: Response): Promise<HttpError> {
  let code = 'http_error';
  let message = friendlyStatusMessage(res.status);
  try {
    const body = (await res.json()) as {
      code?: string;
      message?: string;
      detail?: string | unknown[];
    };
    if (body?.code) code = body.code;
    if (typeof body?.message === 'string' && body.message.trim()) message = body.message;
    else if (typeof body?.detail === 'string' && body.detail.trim()) message = body.detail;
    else if (Array.isArray(body?.detail))
      message = 'Revise los datos ingresados e intente nuevamente.';
  } catch {
    // keep defaults
  }
  return new HttpError(code, message, res.status);
}

function friendlyStatusMessage(status: number): string {
  if (status === 400) return 'La solicitud contiene información inválida.';
  if (status === 401) return 'Su sesión expiró. Inicie sesión nuevamente.';
  if (status === 403) return 'No tiene permisos para realizar esta acción.';
  if (status === 404) return 'No se encontró la información solicitada.';
  if (status === 409) return 'La operación no puede realizarse por el estado actual del registro.';
  if (status === 422) return 'Revise los datos ingresados e intente nuevamente.';
  if (status >= 500) return 'Ocurrió un problema en el servidor. Intente nuevamente más tarde.';
  return 'No se pudo completar la operación. Intente nuevamente.';
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!browser) return false;
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}${REFRESH_ENDPOINT}`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' }
      });
      if (!res.ok) return false;
      const body = (await res.json()) as { access_token: string };
      session.setToken(body.access_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export interface ApiFetchOptions extends RequestInit {
  /** Skip auth header (e.g. for login). */
  noAuth?: boolean;
  /** Skip the 401-refresh-retry flow (e.g. for the refresh endpoint itself). */
  noRefresh?: boolean;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  if (!browser && !path.startsWith('http')) {
    throw new Error('apiFetch must receive an absolute URL when called on the server.');
  }
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${API_PREFIX}${path}`;
  const { noAuth, noRefresh, headers: initHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(rest.body ? { 'Content-Type': 'application/json' } : {}),
    ...((initHeaders ?? {}) as Record<string, string>)
  };
  if (!noAuth && browser && session.token) {
    headers['Authorization'] = `Bearer ${session.token}`;
    if (company.id) headers['X-Company-ID'] = company.id;
    if (branch.id) headers['X-Branch-ID'] = branch.id;
  }

  let res: Response;
  try {
    res = await fetch(url, { ...rest, headers, credentials: 'include' });
  } catch {
    // If initial fetch fails due to network/cold start on Render, wait 2.5s and retry once
    await new Promise((resolve) => setTimeout(resolve, 2500));
    try {
      res = await fetch(url, { ...rest, headers, credentials: 'include' });
    } catch {
      throw new HttpError(
        'network_error',
        'No se pudo conectar con el servidor. Si el servicio estaba inactivo en Render, intente nuevamente en unos segundos.',
        0
      );
    }
  }

  // 401 -> try refresh -> retry once
  if (res.status === 401 && browser && !noRefresh && !noAuth) {
    const ok = await tryRefresh();
    if (ok && session.token) {
      headers['Authorization'] = `Bearer ${session.token}`;
      const retryRes = await fetch(url, { ...rest, headers, credentials: 'include' });
      if (!retryRes.ok) {
        if (retryRes.status === 401) session.clear();
        throw await parseError(retryRes);
      }
      if (retryRes.status === 204) return undefined as T;
      return (await retryRes.json()) as T;
    }
    session.clear();
  }

  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function apiDownload(path: string): Promise<Blob> {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${API_PREFIX}${path}`;
  const headers: Record<string, string> = { Accept: 'text/csv' };
  if (browser && session.token) headers.Authorization = `Bearer ${session.token}`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw await parseError(res);
  return await res.blob();
}

export interface HealthReport {
  status: string;
  version: string;
  environment: string;
  timestamp: string;
  components: { name: string; status: string; detail?: string }[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
}

export interface UserOut {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  failed_login_attempts: number;
  locked_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface PageMeta {
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface DeletedRecordOut {
  resource: string;
  record_id: string;
  label: string;
  company_id: string | null;
  deleted_at: string | null;
  deleted_by: string | null;
  deletion_reason: string | null;
}

export interface PermissionOut {
  id: string;
  code: string;
  description: string | null;
  module: string | null;
  is_protected: boolean;
}

export interface RoleOut {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface RoleWithPermissions extends RoleOut {
  permissions: PermissionOut[];
}

export interface EffectivePermissions {
  permissions: string[];
  is_superuser: boolean;
}

export interface DepartmentOut {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  parent_department_id: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface EmployeeOut {
  id: string;
  company_id: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  user_id: string | null;
  document_id: string | null;
  birth_date: string | null;
  phone: string | null;
  address: string | null;
  department_id: string | null;
  position: string | null;
  hire_date: string | null;
  termination_date: string | null;
  status: string;
  photo_url: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface EmployeeBranchAssignmentOut {
  id: string;
  employee_id: string;
  branch_id: string;
  is_primary: boolean;
  assigned_from: string;
  assigned_until: string | null;
  position: string | null;
  shift: string | null;
  is_active: boolean;
}

export interface DepartmentBranchAssignmentOut {
  id: string;
  department_id: string;
  branch_id: string;
  manager_employee_id: string | null;
  opened_at: string;
  closed_at: string | null;
  is_active: boolean;
}

export interface AuditLogOut {
  id: string;
  user_id: string | null;
  company_id: string | null;
  branch_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  status: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogOut[];
  meta: PageMeta;
}

export interface CompanyOut {
  id: string;
  name: string;
  commercial_name: string;
  nit: string;
  nrc: string;
  commercial_line_1: string | null;
  commercial_line_2: string | null;
  commercial_line_3: string | null;
  address: string;
  department_id: string;
  municipality_id: string;
  district_id: string;
  phone: string | null;
  email: string | null;
  web_site: string | null;
  logo: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type MediaPurpose = 'company_logo' | 'employee_avatar' | 'branch_image' | 'warehouse_image';

export interface UploadedImage {
  url: string;
  publicId: string;
  width: number;
  height: number;
  bytes: number;
  format: string;
}

export interface BranchOut {
  id: string;
  company_id: string;
  department_id: string;
  municipality_id: string;
  district_id: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  manager: string;
  manager_employee_id: string | null;
  manager_initials: string;
  latitude: number;
  longitude: number;
  operational_status: 'active' | 'inactive' | 'maintenance';
  employees: number;
  warehouses: number;
  sales_this_month: number;
  trend: number[];
  opened_at: string;
  email?: string | null;
  description?: string | null;
  schedule?: { day: string; open: string | null; close: string | null }[];
  zone?: string | null;
  services?: string[];
  facilities?: string[];
  images?: { url: string; caption: string; public_id?: string }[];
  area?: number | null;
  area_built?: number | null;
  area_unbuilt?: number | null;
  floors?: number | null;
  parking?: number | null;
  people_capacity?: number | null;
  property_type?: string | null;
  offices?: number | null;
  meeting_rooms?: number | null;
  bathrooms?: number | null;
  accesses?: number | null;
  emergency_exits?: number | null;
  accessibility?: string[];
  construction_type?: string | null;
  construction_year?: number | null;
  building_condition?: string | null;
  cadastral_code?: string | null;
  permit_expiry?: string | null;
  lease_expiry?: string | null;
  landlord?: string | null;
  website?: string | null;
  cctv_cameras?: number | null;
  access_control?: string | null;
  has_alarm?: boolean;
  fire_system?: string[];
  has_backup_generator?: boolean;
  has_ups?: boolean;
  appraised_value?: number | null;
  monthly_maintenance?: number | null;
  last_renovation?: string | null;
  electrical_capacity_kva?: number | null;
  internet_provider?: string | null;
  internet_type?: string | null;
  water_source?: string | null;
  ac_system?: string | null;
  lighting?: string | null;
  exterior_material?: string | null;
  floor_material?: string | null;
  roof_capacity_kg_m2?: number | null;
  cleaning_provider?: string | null;
  last_inspection?: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface WarehouseOut {
  id: string;
  warehouse_category_id: string;
  code: string;
  name: string;
  description?: string | null;
  type: 'general' | 'cold_storage' | 'hazmat' | 'transit' | 'bonded' | 'automated';
  status: 'active' | 'full' | 'maintenance' | 'inactive';
  location: string;
  branch_id: string;
  branch_name: string;
  branch_address: string;
  area: number;
  height: number;
  length: number;
  width: number;
  shelves_total: number;
  shelves_occupied: number;
  capacity: number;
  used: number;
  products: number;
  manager: string;
  manager_employee_id: string | null;
  manager_initials: string;
  operators: number;
  shifts: ('mañana' | 'tarde' | 'noche')[];
  total_skus: number;
  top_categories: string[];
  low_stock_items: number;
  expiring_items: number;
  inventory_value: number;
  inventory_turnover: number;
  last_movement: string;
  inbound_this_month: number;
  outbound_this_month: number;
  daily_movements_avg: number;
  trend: number[] | null;
  recent_movements: {
    id: string;
    date: string;
    type: 'inbound' | 'outbound' | 'transfer' | 'adjustment';
    product_sku: string;
    product_name: string;
    quantity: number;
    operator: string;
    reference: string;
  }[];
  top_products: {
    sku: string;
    name: string;
    category: string;
    quantity: number;
    unit: string;
    min_stock: number;
    max_stock: number;
    expiry_date: string | null;
  }[];
  cameras: number;
  access_control: 'biometrico' | 'tarjetas' | 'teclado' | 'doble_llave' | 'sin_control';
  has_alarm: boolean;
  fire_system: string[];
  last_security_audit: string;
  temperature_range: string;
  humidity_range: string;
  cooling:
    'industrial_ac' | 'refrigeracion' | 'ventilacion_natural' | 'mixto' | 'sin_climatizacion';
  has_ventilation: boolean;
  last_maintenance: string;
  next_maintenance: string;
  maintenance_notes: string;
  sanitary_permit: string | null;
  sanitary_permit_expiry: string | null;
  last_inspection: string;
  certifications: string[];
  images?: { url: string; caption: string; public_id?: string }[];
  created_at: string;
  updated_at: string | null;
}

export interface WarehouseListSummary {
  total_capacity: number;
  total_used: number;
  total_products: number;
  active: number;
  full: number;
  maintenance: number;
  inactive: number;
  status_counts: Record<string, number>;
  branches: { id: string; name: string }[];
}

export interface WarehousePage {
  items: WarehouseOut[];
  meta: PageMeta;
  summary: WarehouseListSummary;
}

export interface WarehouseCategoryOut {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface DashboardSummary {
  active_users: number;
  employees: number;
  warehouses: number;
  events_today: number;
  branches: number;
  onboarding_progress: number;
  department_distribution: { label: string; value: number }[];
  activity_series: { date: string; value: number }[];
  team: { id: string; name: string; initials: string; department: string }[];
  recent_users: {
    id: string;
    name: string;
    initials: string;
    department: string;
    status: 'active' | 'inactive' | 'locked';
    created_at: string;
  }[];
}

export const api = {
  media: {
    uploadImage: async (
      file: File,
      purpose: MediaPurpose,
      companyId?: string | null
    ): Promise<UploadedImage> => {
      const signed = await apiFetch<{
        api_key: string;
        timestamp: number;
        signature: string;
        folder: string;
        public_id: string;
        upload_url: string;
        max_bytes: number;
        allowed_formats: string[];
      }>('/media/upload-signature', {
        method: 'POST',
        body: JSON.stringify({ company_id: companyId || null, purpose })
      });
      if (file.size > signed.max_bytes)
        throw new HttpError(
          'media_too_large',
          `La imagen supera el límite de ${Math.round(signed.max_bytes / 1048576)} MB.`,
          422
        );
      const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
      if (!signed.allowed_formats.includes(extension))
        throw new HttpError('media_format_invalid', 'Use una imagen JPG, PNG o WebP.', 422);
      const form = new FormData();
      form.set('file', file);
      form.set('api_key', signed.api_key);
      form.set('timestamp', String(signed.timestamp));
      form.set('signature', signed.signature);
      form.set('folder', signed.folder);
      form.set('public_id', signed.public_id);
      const response = await fetch(signed.upload_url, { method: 'POST', body: form });
      if (!response.ok)
        throw new HttpError(
          'cloudinary_upload_failed',
          'Cloudinary no pudo cargar la imagen.',
          response.status
        );
      const result = (await response.json()) as {
        secure_url: string;
        public_id: string;
        width: number;
        height: number;
        bytes: number;
        format: string;
      };
      await apiFetch('/media/confirm', {
        method: 'POST',
        body: JSON.stringify({
          company_id: companyId || null,
          purpose,
          public_id: result.public_id,
          secure_url: result.secure_url,
          format: result.format,
          bytes: result.bytes,
          width: result.width,
          height: result.height
        })
      });
      return {
        url: result.secure_url,
        publicId: result.public_id,
        width: result.width,
        height: result.height,
        bytes: result.bytes,
        format: result.format
      };
    },
    deleteImage: (companyId: string, publicId: string) =>
      apiFetch<{ message: string; code: string }>('/media/delete', {
        method: 'POST',
        body: JSON.stringify({ company_id: companyId, public_id: publicId })
      }),
    deleteImageByUrl: (companyId: string, secureUrl: string) =>
      apiFetch<{ message: string; code: string }>('/media/delete', {
        method: 'POST',
        body: JSON.stringify({ company_id: companyId, secure_url: secureUrl })
      })
  },
  auth: {
    login: (login: string, password: string) =>
      apiFetch<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ login, password }),
        noAuth: true
      }),
    refresh: () =>
      apiFetch<TokenResponse>('/auth/refresh', {
        method: 'POST',
        noAuth: true,
        noRefresh: true
      }),
    logout: () =>
      apiFetch<{ message: string; code: string }>('/auth/logout', {
        method: 'POST'
      }),
    me: () => apiFetch<UserOut>('/auth/me'),
    myPermissions: () => apiFetch<EffectivePermissions>('/auth/me/permissions')
  },
  roles: {
    list: (
      params: {
        page?: number;
        size?: number;
        search?: string;
        isSystem?: boolean;
        module?: string;
        signal?: AbortSignal;
      } = {}
    ) => {
      const query = new URLSearchParams({
        page: String(params.page ?? 1),
        size: String(params.size ?? 12)
      });
      if (params.search) query.set('search', params.search);
      if (params.isSystem !== undefined) query.set('is_system', String(params.isSystem));
      if (params.module) query.set('module', params.module);
      return apiFetch<Page<RoleWithPermissions>>(`/roles?${query}`, { signal: params.signal });
    },
    catalogue: (signal?: AbortSignal) =>
      apiFetch<RoleWithPermissions[]>('/roles/catalogue', { signal }),
    listPermissions: () => apiFetch<PermissionOut[]>('/roles/permissions'),
    get: (id: string) => apiFetch<RoleWithPermissions>(`/roles/${id}`),
    create: (data: { name: string; description?: string }) =>
      apiFetch<RoleOut>('/roles', { method: 'POST', body: JSON.stringify(data) }),
    duplicate: (id: string, data: { name: string; description?: string }) =>
      apiFetch<RoleWithPermissions>(`/roles/${id}/duplicate`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    update: (id: string, data: { name?: string; description?: string }) =>
      apiFetch<RoleOut>(`/roles/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/roles/${id}`, { method: 'DELETE' }),
    setPermissions: (id: string, permissionCodes: string[]) =>
      apiFetch<RoleWithPermissions>(`/roles/${id}/permissions`, {
        method: 'PUT',
        body: JSON.stringify({ permission_codes: permissionCodes })
      }),
    assign: (userId: string, roleId: string) =>
      apiFetch<{ message: string; code: string }>('/roles/assign', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, role_id: roleId })
      }),
    revoke: (userId: string, roleId: string) =>
      apiFetch<{ message: string; code: string }>('/roles/revoke', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, role_id: roleId })
      }),
    userRoles: (userId: string) => apiFetch<RoleOut[]>(`/roles/users/${userId}/roles`),
    createPermission: (data: { code: string; description?: string; module?: string }) =>
      apiFetch<PermissionOut>('/roles/permissions', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    updatePermission: (
      id: string,
      data: { code?: string; description?: string; module?: string }
    ) =>
      apiFetch<PermissionOut>(`/roles/permissions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      }),
    deletePermission: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/roles/permissions/${id}`, {
        method: 'DELETE'
      })
  },
  users: {
    list: (
      params: {
        page?: number;
        size?: number;
        search?: string;
        status?: UserStatusFilter;
        signal?: AbortSignal;
      } = {}
    ) => {
      const qs = buildUserListQuery(params, { companyId: company.id, branchId: branch.id });
      return apiFetch<Page<UserOut>>(`/users${qs ? `?${qs}` : ''}`, { signal: params.signal });
    },
    rolesBatch: (userIds: string[], signal?: AbortSignal) => {
      const sp = new URLSearchParams();
      userIds.forEach((id) => sp.append('user_ids', id));
      if (company.id) sp.set('company_id', company.id);
      if (branch.id) sp.set('branch_id', branch.id);
      return apiFetch<Record<string, RoleOut[]>>(`/users/batch/roles?${sp.toString()}`, {
        signal
      });
    },
    get: (id: string) => apiFetch<UserOut>(`/users/${id}`),
    create: (data: {
      username: string;
      email: string;
      password: string;
      is_superuser?: boolean;
      employee_id?: string;
      role_ids?: string[];
    }) =>
      apiFetch<UserOut>('/users', {
        method: 'POST',
        body: JSON.stringify({ ...data, company_id: company.id })
      }),
    update: (id: string, data: { is_active?: boolean; is_superuser?: boolean }) =>
      apiFetch<UserOut>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    forcePasswordReset: (id: string, newPassword: string) =>
      apiFetch<{ message: string; code: string }>(`/users/${id}/force-password-reset`, {
        method: 'POST',
        body: JSON.stringify({ new_password: newPassword })
      }),
    unlock: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/users/${id}/unlock`, { method: 'POST' }),
    deactivate: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/users/${id}`, { method: 'DELETE' }),
    branchAccess: (userId: string) =>
      apiFetch<OperationalContext>(`/users/${userId}/companies/${company.id}/branch-access`),
    setBranchAccess: (
      userId: string,
      data: { access_all_branches: boolean; branch_ids: string[]; default_branch_id: string | null }
    ) =>
      apiFetch<OperationalContext>(`/users/${userId}/companies/${company.id}/branch-access`, {
        method: 'PUT',
        body: JSON.stringify(data)
      })
  },
  health: {
    live: () =>
      apiFetch<HealthReport>(`${API_BASE_URL}/health/live`, {
        noAuth: true,
        noRefresh: true
      })
  },
  departments: {
    list: (
      params: {
        page?: number;
        size?: number;
        search?: string;
        level?: 'root' | 'child';
        signal?: AbortSignal;
      } = {}
    ) => {
      const query = new URLSearchParams({
        company_id: company.id ?? '',
        page: String(params.page ?? 1),
        size: String(params.size ?? 12)
      });
      if (params.search) query.set('search', params.search);
      if (params.level) query.set('level', params.level);
      return apiFetch<Page<DepartmentOut>>(`/departments?${query}`, { signal: params.signal });
    },
    catalogue: (signal?: AbortSignal) =>
      apiFetch<DepartmentOut[]>(`/departments/catalogue?company_id=${company.id ?? ''}`, { signal }),
    get: (id: string) => apiFetch<DepartmentOut>(`/departments/${id}`),
    create: (data: { name: string; description?: string; parent_department_id?: string }) =>
      apiFetch<DepartmentOut>('/departments', {
        method: 'POST',
        body: JSON.stringify({ ...data, company_id: company.id })
      }),
    update: (
      id: string,
      data: { name?: string; description?: string; parent_department_id?: string }
    ) =>
      apiFetch<DepartmentOut>(`/departments/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/departments/${id}`, { method: 'DELETE' })
  },
  employees: {
    list: (
      params: {
        page?: number;
        size?: number;
        search?: string;
        department_id?: string;
        status?: string;
        branch_id?: string;
        signal?: AbortSignal;
      } = {}
    ) => {
      const sp = new URLSearchParams();
      if (params.page) sp.set('page', String(params.page));
      if (params.size) sp.set('size', String(params.size));
      if (params.search) sp.set('search', params.search);
      if (params.department_id) sp.set('department_id', params.department_id);
      if (params.status) sp.set('status', params.status);
      if (company.id) sp.set('company_id', company.id);
      if (params.branch_id ?? branch.id) sp.set('branch_id', params.branch_id ?? branch.id ?? '');
      const qs = sp.toString();
      return apiFetch<Page<EmployeeOut>>(`/employees${qs ? `?${qs}` : ''}`, {
        signal: params.signal
      });
    },
    stats: () =>
      apiFetch<{
        total: number;
        active: number;
        inactive: number;
        on_leave: number;
        terminated: number;
        linked_to_user: number;
      }>(
        `/employees/stats?company_id=${company.id ?? ''}${branch.id ? `&branch_id=${branch.id}` : ''}`
      ),
    get: (id: string) =>
      apiFetch<EmployeeOut>(`/employees/${id}${branch.id ? `?branch_id=${branch.id}` : ''}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<EmployeeOut>('/employees', {
        method: 'POST',
        body: JSON.stringify({ ...data, company_id: company.id })
      }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<EmployeeOut>(`/employees/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/employees/${id}`, { method: 'DELETE' })
  },
  workforce: {
    employeeAssignments: (employeeId: string) =>
      apiFetch<EmployeeBranchAssignmentOut[]>(`/employees/${employeeId}/branch-assignments`),
    assignEmployee: (data: {
      employee_id: string;
      branch_id: string;
      is_primary?: boolean;
      assigned_from?: string;
      position?: string;
      shift?: string;
    }) =>
      apiFetch<EmployeeBranchAssignmentOut>('/employee-branch-assignments', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    endEmployeeAssignment: (id: string) =>
      apiFetch<EmployeeBranchAssignmentOut>(`/employee-branch-assignments/${id}/end`, {
        method: 'POST'
      }),
    departmentAssignments: (departmentId: string) =>
      apiFetch<DepartmentBranchAssignmentOut[]>(`/departments/${departmentId}/branch-assignments`),
    enableDepartment: (data: {
      department_id: string;
      branch_id: string;
      manager_employee_id?: string;
    }) =>
      apiFetch<DepartmentBranchAssignmentOut>('/department-branch-assignments', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    endDepartmentAssignment: (id: string) =>
      apiFetch<DepartmentBranchAssignmentOut>(`/department-branch-assignments/${id}/end`, {
        method: 'POST'
      })
  },
  audit: {
    list: (
      params: {
        page?: number;
        size?: number;
        user_id?: string;
        action?: string;
        resource_type?: string;
        status?: string;
        start_date?: string;
        end_date?: string;
        signal?: AbortSignal;
      } = {}
    ) => {
      const sp = new URLSearchParams();
      if (params.page) sp.set('page', String(params.page));
      if (params.size) sp.set('size', String(params.size));
      if (params.user_id) sp.set('user_id', params.user_id);
      if (params.action) sp.set('action', params.action);
      if (params.resource_type) sp.set('resource_type', params.resource_type);
      if (params.status) sp.set('status', params.status);
      if (params.start_date) sp.set('start_date', params.start_date);
      if (params.end_date) sp.set('end_date', params.end_date);
      if (company.id) sp.set('company_id', company.id);
      if (branch.id) sp.set('branch_id', branch.id);
      const qs = sp.toString();
      return apiFetch<AuditLogPage>(`/audit-logs${qs ? `?${qs}` : ''}`, {
        signal: params.signal
      });
    },
    get: (id: string) => apiFetch<AuditLogOut>(`/audit-logs/${id}`),
    exportCsv: (
      params: {
        user_id?: string;
        action?: string;
        resource_type?: string;
        start_date?: string;
        end_date?: string;
      } = {}
    ) => {
      const sp = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value) sp.set(key, value);
      }
      if (company.id) sp.set('company_id', company.id);
      if (branch.id) sp.set('branch_id', branch.id);
      const qs = sp.toString();
      return apiDownload(`/audit-logs/export${qs ? `?${qs}` : ''}`);
    }
  },
  geography: {
    departments: () => apiFetch<{ id: string; name: string }[]>('/geographic-departments'),
    municipalities: (departmentId?: string) =>
      apiFetch<{ id: string; department_id: string; name: string }[]>(
        `/municipalities${departmentId ? `?department_id=${departmentId}` : ''}`
      ),
    districts: (municipalityId?: string) =>
      apiFetch<{ id: string; municipality_id: string; name: string }[]>(
        `/districts${municipalityId ? `?municipality_id=${municipalityId}` : ''}`
      )
  },
  companies: {
    accessible: () => apiFetch<CompanyOut[]>('/companies/accessible'),
    list: () => apiFetch<CompanyOut[]>('/companies'),
    get: (id: string) => apiFetch<CompanyOut>(`/companies/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<CompanyOut>('/companies', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<CompanyOut>(`/companies/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    activate: (id: string) => apiFetch<CompanyOut>(`/companies/${id}/activate`, { method: 'POST' }),
    deactivate: (id: string) =>
      apiFetch<CompanyOut>(`/companies/${id}/deactivate`, { method: 'POST' })
  },
  operationalContext: {
    get: (companyId: string) => apiFetch<OperationalContext>(`/operational-contexts/${companyId}`),
    select: (companyId: string, branchId: string | null) =>
      apiFetch<OperationalContext>(`/operational-contexts/${companyId}/preference`, {
        method: 'PATCH',
        body: JSON.stringify({ branch_id: branchId })
      })
  },
  dashboard: {
    summary: (signal?: AbortSignal) => {
      const sp = new URLSearchParams();
      if (company.id) sp.set('company_id', company.id);
      if (branch.id) sp.set('branch_id', branch.id);
      return apiFetch<DashboardSummary>(`/dashboard/summary?${sp.toString()}`, { signal });
    }
  },
  branches: {
    list: (signal?: AbortSignal) =>
      apiFetch<BranchOut[]>(`/branches?company_id=${company.id ?? ''}`, { signal }),
    get: (id: string) => apiFetch<BranchOut>(`/branches/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<BranchOut>('/branches', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<BranchOut>(`/branches/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    activate: (id: string) => apiFetch<BranchOut>(`/branches/${id}/activate`, { method: 'POST' }),
    deactivate: (id: string) =>
      apiFetch<BranchOut>(`/branches/${id}/deactivate`, { method: 'POST' })
  },
  warehouseCategories: {
    list: (
      params: { page?: number; size?: number; search?: string; signal?: AbortSignal } = {}
    ) => {
      const query = new URLSearchParams({
        company_id: company.id ?? '',
        page: String(params.page ?? 1),
        size: String(params.size ?? 12)
      });
      if (params.search) query.set('search', params.search);
      return apiFetch<Page<WarehouseCategoryOut>>(`/warehouse-categories?${query}`, {
        signal: params.signal
      });
    },
    catalogue: (signal?: AbortSignal) =>
      apiFetch<WarehouseCategoryOut[]>(
        `/warehouse-categories/catalogue?company_id=${company.id ?? ''}`,
        { signal }
      ),
    create: (data: Record<string, unknown>) =>
      apiFetch('/warehouse-categories', {
        method: 'POST',
        body: JSON.stringify({ ...data, company_id: company.id })
      }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch(`/warehouse-categories/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ...data, company_id: company.id })
      }),
    activate: (id: string) => apiFetch(`/warehouse-categories/${id}/activate`, { method: 'POST' }),
    deactivate: (id: string) =>
      apiFetch(`/warehouse-categories/${id}/deactivate`, { method: 'POST' })
  },
  warehouses: {
    list: (
      params: {
        branch_id?: string;
        page?: number;
        size?: number;
        search?: string;
        status?: string;
        sort?: 'capacity' | 'name' | 'movement';
        signal?: AbortSignal;
      } = {}
    ) => {
      const sp = new URLSearchParams();
      if (params.branch_id ?? branch.id) sp.set('branch_id', params.branch_id ?? branch.id ?? '');
      if (company.id) sp.set('company_id', company.id);
      sp.set('page', String(params.page ?? 1));
      sp.set('size', String(params.size ?? 9));
      if (params.search) sp.set('search', params.search);
      if (params.status) sp.set('status', params.status);
      if (params.sort) sp.set('sort', params.sort);
      const qs = sp.toString();
      return apiFetch<WarehousePage>(`/warehouses${qs ? `?${qs}` : ''}`, {
        signal: params.signal
      });
    },
    catalogue: (params: { branch_id?: string; signal?: AbortSignal } = {}) => {
      const sp = new URLSearchParams();
      if (params.branch_id ?? branch.id) sp.set('branch_id', params.branch_id ?? branch.id ?? '');
      if (company.id) sp.set('company_id', company.id);
      return apiFetch<WarehouseOut[]>(`/warehouses/catalogue?${sp}`, { signal: params.signal });
    },
    get: (id: string) => apiFetch<WarehouseOut>(`/warehouses/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<WarehouseOut>('/warehouses', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<WarehouseOut>(`/warehouses/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    activate: (id: string) =>
      apiFetch<WarehouseOut>(`/warehouses/${id}/activate`, { method: 'POST' }),
    deactivate: (id: string) =>
      apiFetch<WarehouseOut>(`/warehouses/${id}/deactivate`, { method: 'POST' })
  },
  locations: {
    list: (warehouseId: string) =>
      apiFetch<Record<string, unknown>[]>(`/locations?warehouse_id=${warehouseId}`),
    create: (data: Record<string, unknown>) =>
      apiFetch('/locations', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch(`/locations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    activate: (id: string) => apiFetch(`/locations/${id}/activate`, { method: 'POST' }),
    deactivate: (id: string) => apiFetch(`/locations/${id}/deactivate`, { method: 'POST' })
  },
  lifecycle: {
    list: (
      params: {
        page?: number;
        size?: number;
        resource?: string;
        search?: string;
        signal?: AbortSignal;
      } = {}
    ) => {
      const query = new URLSearchParams({
        page: String(params.page ?? 1),
        size: String(params.size ?? 20)
      });
      if (params.resource) query.set('resource', params.resource);
      if (params.search) query.set('search', params.search);
      return apiFetch<Page<DeletedRecordOut>>(`/lifecycle/trash?${query}`, {
        signal: params.signal
      });
    },
    delete: (resource: string, recordId: string, reason: string) =>
      apiFetch<DeletedRecordOut>(`/lifecycle/${resource}/${recordId}`, {
        method: 'DELETE',
        body: JSON.stringify({ reason })
      }),
    restore: (resource: string, recordId: string) =>
      apiFetch<DeletedRecordOut>(`/lifecycle/${resource}/${recordId}/restore`, {
        method: 'POST'
      })
  }
};
