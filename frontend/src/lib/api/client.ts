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
import { PUBLIC_API_URL } from '$env/static/public';
import { session } from '$lib/stores/session.svelte';

export const API_BASE_URL = PUBLIC_API_URL ?? 'http://localhost:8000';
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
  let message = `Request failed with status ${res.status}`;
  try {
    const body = (await res.json()) as { code?: string; message?: string };
    if (body?.code) code = body.code;
    if (body?.message) message = body.message;
  } catch {
    // keep defaults
  }
  return new HttpError(code, message, res.status);
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
  }

  const res = await fetch(url, { ...rest, headers, credentials: 'include' });

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

export interface PermissionOut {
  id: string;
  code: string;
  description: string | null;
  module: string | null;
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
  name: string;
  description: string | null;
  parent_department_id: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface EmployeeOut {
  id: string;
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

export interface AuditLogOut {
  id: string;
  user_id: string | null;
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

export interface BranchOut {
  id: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  manager: string;
  manager_initials: string;
  lat: number;
  lng: number;
  status: 'active' | 'inactive' | 'maintenance';
  employees: number;
  warehouses: number;
  sales_this_month: number;
  trend: number[];
  opened_at: string;
  created_at: string;
  updated_at: string | null;
}

export interface WarehouseOut {
  id: string;
  code: string;
  name: string;
  branch_id: string;
  branch_name: string;
  location: string;
  capacity: number;
  used: number;
  status: 'active' | 'full' | 'maintenance';
  products: number;
  last_movement: string;
  trend: number[] | null;
  created_at: string;
  updated_at: string | null;
}

export const api = {
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
    list: () => apiFetch<RoleWithPermissions[]>('/roles'),
    listPermissions: () => apiFetch<PermissionOut[]>('/roles/permissions'),
    get: (id: string) => apiFetch<RoleWithPermissions>(`/roles/${id}`),
    create: (data: { name: string; description?: string }) =>
      apiFetch<RoleOut>('/roles', { method: 'POST', body: JSON.stringify(data) }),
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
    userRoles: (userId: string) => apiFetch<RoleOut[]>(`/roles/users/${userId}/roles`)
  },
  users: {
    list: (params: { page?: number; size?: number; search?: string } = {}) => {
      const sp = new URLSearchParams();
      if (params.page) sp.set('page', String(params.page));
      if (params.size) sp.set('size', String(params.size));
      if (params.search) sp.set('search', params.search);
      const qs = sp.toString();
      return apiFetch<Page<UserOut>>(`/users${qs ? `?${qs}` : ''}`);
    },
    get: (id: string) => apiFetch<UserOut>(`/users/${id}`),
    create: (data: { username: string; email: string; password: string; is_superuser?: boolean }) =>
      apiFetch<UserOut>('/users', { method: 'POST', body: JSON.stringify(data) }),
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
      apiFetch<{ message: string; code: string }>(`/users/${id}`, { method: 'DELETE' })
  },
  health: {
    live: () => apiFetch<HealthReport>('/health/live', { noAuth: true, noRefresh: true })
  },
  departments: {
    list: () => apiFetch<DepartmentOut[]>('/departments'),
    get: (id: string) => apiFetch<DepartmentOut>(`/departments/${id}`),
    create: (data: { name: string; description?: string; parent_department_id?: string }) =>
      apiFetch<DepartmentOut>('/departments', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: { name?: string; description?: string; parent_department_id?: string }) =>
      apiFetch<DepartmentOut>(`/departments/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/departments/${id}`, { method: 'DELETE' })
  },
  employees: {
    list: (params: { page?: number; size?: number; search?: string; department_id?: string; status?: string } = {}) => {
      const sp = new URLSearchParams();
      if (params.page) sp.set('page', String(params.page));
      if (params.size) sp.set('size', String(params.size));
      if (params.search) sp.set('search', params.search);
      if (params.department_id) sp.set('department_id', params.department_id);
      if (params.status) sp.set('status', params.status);
      const qs = sp.toString();
      return apiFetch<Page<EmployeeOut>>(`/employees${qs ? `?${qs}` : ''}`);
    },
    stats: () =>
      apiFetch<{
        total: number; active: number; inactive: number;
        on_leave: number; terminated: number; linked_to_user: number;
      }>('/employees/stats'),
    get: (id: string) => apiFetch<EmployeeOut>(`/employees/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<EmployeeOut>('/employees', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<EmployeeOut>(`/employees/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/employees/${id}`, { method: 'DELETE' }),
    linkUser: (empId: string, userId: string) =>
      apiFetch<{ message: string; code: string }>(`/employees/${empId}/link-user`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId })
      }),
    unlinkUser: (empId: string) =>
      apiFetch<{ message: string; code: string }>(`/employees/${empId}/unlink-user`, { method: 'POST' })
  },
  audit: {
    list: (params: {
      page?: number;
      size?: number;
      user_id?: string;
      action?: string;
      resource_type?: string;
      status?: string;
    } = {}) => {
      const sp = new URLSearchParams();
      if (params.page) sp.set('page', String(params.page));
      if (params.size) sp.set('size', String(params.size));
      if (params.user_id) sp.set('user_id', params.user_id);
      if (params.action) sp.set('action', params.action);
      if (params.resource_type) sp.set('resource_type', params.resource_type);
      if (params.status) sp.set('status', params.status);
      const qs = sp.toString();
      return apiFetch<AuditLogPage>(`/audit-logs${qs ? `?${qs}` : ''}`);
    }
  },
  branches: {
    list: () => apiFetch<BranchOut[]>('/branches'),
    get: (id: string) => apiFetch<BranchOut>(`/branches/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<BranchOut>('/branches', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<BranchOut>(`/branches/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/branches/${id}`, { method: 'DELETE' })
  },
  warehouses: {
    list: (params: { branch_id?: string } = {}) => {
      const sp = new URLSearchParams();
      if (params.branch_id) sp.set('branch_id', params.branch_id);
      const qs = sp.toString();
      return apiFetch<WarehouseOut[]>(`/warehouses${qs ? `?${qs}` : ''}`);
    },
    get: (id: string) => apiFetch<WarehouseOut>(`/warehouses/${id}`),
    create: (data: Record<string, unknown>) =>
      apiFetch<WarehouseOut>('/warehouses', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      apiFetch<WarehouseOut>(`/warehouses/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ message: string; code: string }>(`/warehouses/${id}`, { method: 'DELETE' })
  }
};