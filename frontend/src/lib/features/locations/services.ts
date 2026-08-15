import { apiFetch, HttpError, type PageMeta } from '$lib/api/client';
import type {
  LocationBatchJob,
  LocationBatchRow,
  LocationBatchPreviewInput,
  LocationCodePreviewInput,
  LocationCodePreview,
  LocationCodeScheme,
  LocationCodeSchemeInput,
  LocationImportPreviewInput,
  LocationListParams,
  LocationMutationInput,
  LocationUpdateInput,
  LocationOut,
  LocationPage,
  LocationSummary
} from './types';

const text = (value: unknown, fallback = '') => (typeof value === 'string' ? value : fallback);
const nullableText = (value: unknown) => (typeof value === 'string' && value ? value : null);
const integer = (value: unknown, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
};

export function normalizeLocation(value: unknown, warehouseId = ''): LocationOut {
  const source = (value ?? {}) as Record<string, unknown>;
  return {
    id: text(source.id),
    warehouse_id: text(source.warehouse_id, warehouseId),
    code: text(source.code),
    area: nullableText(source.area),
    aisle: text(source.aisle),
    rack: text(source.rack),
    level: text(source.level),
    position: text(source.position),
    capacity: integer(source.capacity),
    notes: nullableText(source.notes),
    location_type: text(source.location_type, 'standard'),
    lifecycle_status: text(
      source.lifecycle_status,
      source.is_active === false ? 'retired' : 'active'
    ),
    barcode: nullableText(source.barcode),
    verification_code: nullableText(source.verification_code),
    pick_sequence: source.pick_sequence == null ? null : integer(source.pick_sequence),
    putaway_sequence: source.putaway_sequence == null ? null : integer(source.putaway_sequence),
    external_id: nullableText(source.external_id),
    scheme_id: nullableText(source.scheme_id),
    scheme_version: source.scheme_version == null ? null : integer(source.scheme_version),
    code_source: text(source.code_source, 'legacy'),
    is_active: source.is_active !== false,
    created_at: text(source.created_at),
    updated_at: nullableText(source.updated_at)
  };
}

function normalizeMeta(value: unknown, itemCount: number, page: number, size: number): PageMeta {
  const source = (value ?? {}) as Record<string, unknown>;
  const total = integer(source.total, itemCount);
  return {
    page: Math.max(1, integer(source.page, page)),
    size: Math.max(1, integer(source.size, size)),
    total,
    pages: Math.max(1, integer(source.pages, Math.ceil(total / Math.max(size, 1))))
  };
}

function queryString(params: LocationListParams): string {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 25)
  });
  if (params.search) query.set('search', params.search);
  if (params.area) query.set('area', params.area);
  if (params.location_type) query.set('location_type', params.location_type);
  if (params.lifecycle_status) query.set('lifecycle_status', params.lifecycle_status);
  if (params.is_active !== undefined) query.set('is_active', String(params.is_active));
  return query.toString();
}

function normalizeBatchRow(value: unknown): LocationBatchRow {
  const source = (value ?? {}) as Record<string, unknown>;
  return {
    id: text(source.id),
    row_number: integer(source.row_number),
    operation: text(source.operation, 'error'),
    code: nullableText(source.code),
    normalized_data:
      source.normalized_data && typeof source.normalized_data === 'object'
        ? (source.normalized_data as Record<string, unknown>)
        : {},
    diff:
      source.diff && typeof source.diff === 'object'
        ? (source.diff as Record<string, unknown>)
        : {},
    errors: Array.isArray(source.errors)
      ? source.errors.filter((item): item is string => typeof item === 'string')
      : []
  };
}

export function normalizeLocationBatch(
  value: unknown,
  fallbackPage = 1,
  fallbackSize = 100
): LocationBatchJob {
  const source = (value ?? {}) as Record<string, unknown>;
  const summary =
    source.summary && typeof source.summary === 'object' && !Array.isArray(source.summary)
      ? (source.summary as Record<string, unknown>)
      : {};
  const rows = Array.isArray(source.rows) ? source.rows.map(normalizeBatchRow) : [];
  const totalRows = integer(source.total_rows, rows.length);
  const metaSource =
    source.rows_meta ?? source.meta ?? summary.rows_meta ?? summary.meta ?? undefined;
  const rowsMeta = normalizeMeta(metaSource, totalRows, fallbackPage, fallbackSize);
  const requiredPermissionsSource = source.required_permissions ?? summary.required_permissions;
  const requiredPermissions = Array.isArray(requiredPermissionsSource)
    ? requiredPermissionsSource.filter((item): item is string => typeof item === 'string')
    : undefined;

  return {
    id: text(source.id),
    warehouse_id: text(source.warehouse_id),
    kind: text(source.kind),
    status: text(source.status, 'preview'),
    idempotency_key: text(source.idempotency_key),
    input_checksum: text(source.input_checksum),
    scheme_id: nullableText(source.scheme_id),
    scheme_version: source.scheme_version == null ? null : integer(source.scheme_version),
    total_rows: totalRows,
    create_count: integer(source.create_count),
    update_count: integer(source.update_count),
    unchanged_count: integer(source.unchanged_count),
    conflict_count: integer(source.conflict_count),
    error_count: integer(source.error_count),
    summary,
    ...(requiredPermissions ? { required_permissions: requiredPermissions } : {}),
    rows_meta: rowsMeta,
    meta: rowsMeta,
    created_by: text(source.created_by),
    published_by: nullableText(source.published_by),
    created_at: text(source.created_at),
    published_at: nullableText(source.published_at),
    rows
  };
}

export async function listLocations(
  warehouseId: string,
  params: LocationListParams = {}
): Promise<LocationPage> {
  const page = params.page ?? 1;
  const size = params.size ?? 25;
  try {
    const response = await apiFetch<unknown>(
      `/warehouses/${warehouseId}/locations?${queryString(params)}`,
      { signal: params.signal }
    );
    if (Array.isArray(response)) {
      const items = response.map((item) => normalizeLocation(item, warehouseId));
      return { items, meta: normalizeMeta(undefined, items.length, page, size) };
    }
    const source = response as { items?: unknown[]; meta?: unknown };
    const items = (source.items ?? []).map((item) => normalizeLocation(item, warehouseId));
    return { items, meta: normalizeMeta(source.meta, items.length, page, size) };
  } catch (error) {
    if (!(error instanceof HttpError) || error.status !== 404) throw error;
    const legacy = await apiFetch<unknown[]>(`/locations?warehouse_id=${warehouseId}`, {
      signal: params.signal
    });
    let items = legacy.map((item) => normalizeLocation(item, warehouseId));
    const needle = params.search?.trim().toLocaleLowerCase('es');
    if (needle) {
      items = items.filter((item) =>
        [item.code, item.area, item.aisle, item.rack, item.level, item.position]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase('es').includes(needle))
      );
    }
    if (params.area) {
      items = items.filter((item) =>
        params.area === '__none__' ? item.area == null : item.area === params.area
      );
    }
    if (params.location_type)
      items = items.filter((item) => item.location_type === params.location_type);
    if (params.lifecycle_status)
      items = items.filter((item) => item.lifecycle_status === params.lifecycle_status);
    if (params.is_active !== undefined)
      items = items.filter((item) => item.is_active === params.is_active);
    const total = items.length;
    const offset = (page - 1) * size;
    return {
      items: items.slice(offset, offset + size),
      meta: { page, size, total, pages: Math.max(1, Math.ceil(total / size)) }
    };
  }
}

export async function getLocationSummary(
  warehouseId: string,
  signal?: AbortSignal
): Promise<LocationSummary> {
  try {
    const source = await apiFetch<Partial<LocationSummary>>(
      `/warehouses/${warehouseId}/locations/summary`,
      { signal }
    );
    return {
      total: integer(source.total),
      total_capacity: integer(source.total_capacity),
      active: integer(source.active),
      inactive: integer(source.inactive),
      by_status: source.by_status ?? {},
      by_type: source.by_type ?? {},
      areas:
        source.areas && typeof source.areas === 'object' && !Array.isArray(source.areas)
          ? Object.entries(source.areas).reduce<Record<string, number>>(
              (areas, [area, count]) => {
                // Older API responses used the translated label as the key.
                // Merge it into the canonical sentinel so both deployments
                // render one “Sin área” option instead of two.
                const key = area === 'Sin área' ? '__none__' : area;
                areas[key] = (areas[key] ?? 0) + integer(count);
                return areas;
              },
              {}
            )
          : {}
    };
  } catch (error) {
    if (!(error instanceof HttpError) || error.status !== 404) throw error;
    const legacy = await apiFetch<unknown[]>(`/locations?warehouse_id=${warehouseId}`, { signal });
    const items = legacy.map((item) => normalizeLocation(item, warehouseId));
    const byStatus: Record<string, number> = {};
    const byType: Record<string, number> = {};
    for (const item of items) {
      byStatus[item.lifecycle_status] = (byStatus[item.lifecycle_status] ?? 0) + 1;
      byType[item.location_type] = (byType[item.location_type] ?? 0) + 1;
    }
    return {
      total: items.length,
      total_capacity: items.reduce((sum, item) => sum + item.capacity, 0),
      active: items.filter((item) => item.is_active).length,
      inactive: items.filter((item) => !item.is_active).length,
      by_status: byStatus,
      by_type: byType,
      areas: items.reduce<Record<string, number>>((counts, item) => {
        if (item.area) counts[item.area] = (counts[item.area] ?? 0) + 1;
        return counts;
      }, {})
    };
  }
}

export async function previewLocationCode(
  warehouseId: string,
  input: LocationCodePreviewInput,
  signal?: AbortSignal
): Promise<LocationCodePreview> {
  return apiFetch<LocationCodePreview>(`/warehouses/${warehouseId}/locations/code-preview`, {
    method: 'POST',
    body: JSON.stringify(input),
    signal
  });
}

export async function createLocation(
  warehouseId: string,
  input: LocationMutationInput
): Promise<LocationOut> {
  const response = await apiFetch<unknown>(`/warehouses/${warehouseId}/locations`, {
    method: 'POST',
    body: JSON.stringify(input)
  });
  return normalizeLocation(response, warehouseId);
}

export async function updateLocation(
  warehouseId: string,
  locationId: string,
  input: LocationUpdateInput
): Promise<LocationOut> {
  const response = await apiFetch<unknown>(`/warehouses/${warehouseId}/locations/${locationId}`, {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
  return normalizeLocation(response, warehouseId);
}

export async function getLocationCodeScheme(
  warehouseId: string,
  signal?: AbortSignal
): Promise<LocationCodeScheme> {
  return apiFetch<LocationCodeScheme>(`/warehouses/${warehouseId}/location-code-scheme`, {
    signal
  });
}

export async function updateLocationCodeScheme(
  warehouseId: string,
  input: LocationCodeSchemeInput
): Promise<LocationCodeScheme> {
  return apiFetch<LocationCodeScheme>(`/warehouses/${warehouseId}/location-code-scheme`, {
    method: 'PUT',
    body: JSON.stringify(input)
  });
}

export async function previewGeneratedLocations(
  warehouseId: string,
  input: LocationBatchPreviewInput
): Promise<LocationBatchJob> {
  const response = await apiFetch<unknown>(
    `/warehouses/${warehouseId}/location-batches/generate/preview`,
    { method: 'POST', body: JSON.stringify(input) }
  );
  return normalizeLocationBatch(response);
}

export async function previewLocationImport(
  warehouseId: string,
  input: LocationImportPreviewInput
): Promise<LocationBatchJob> {
  const body = new FormData();
  body.set('file', input.file);
  body.set('idempotency_key', input.idempotency_key);
  if (input.scheme_version !== undefined) body.set('scheme_version', String(input.scheme_version));
  const response = await apiFetch<unknown>(`/warehouses/${warehouseId}/location-imports/preview`, {
    method: 'POST',
    body
  });
  return normalizeLocationBatch(response);
}

export async function publishLocationBatch(jobId: string): Promise<LocationBatchJob> {
  const response = await apiFetch<unknown>(`/location-batches/${jobId}/publish`, {
    method: 'POST'
  });
  return normalizeLocationBatch(response);
}

export async function getLocationBatch(
  jobId: string,
  page = 1,
  size = 100,
  signal?: AbortSignal
): Promise<LocationBatchJob> {
  const response = await apiFetch<unknown>(`/location-batches/${jobId}?page=${page}&size=${size}`, {
    signal
  });
  return normalizeLocationBatch(response, page, size);
}
