import { HttpError, apiFetch } from '$lib/api/client';
import type {
  CapacityMetric,
  CapacityScopeSummary,
  CapacitySummary,
  HandlingUnit,
  InventoryItem,
  PackagingCreateInput,
  PackagingDefinition,
  PhysicalMeasuresInput,
  StockStatus
} from './types';

type DecimalValue = number | string | null;

interface RawCapacityMetric {
  certified: DecimalValue;
  operational: DecimalValue;
  occupied: DecimalValue;
  reserved: DecimalValue;
  projected: DecimalValue;
  available: DecimalValue;
  utilization_pct: DecimalValue;
}

interface RawCapacitySummary {
  scope_type: 'warehouse' | 'location';
  warehouse_id: string;
  location_id: string | null;
  measurement_status: 'complete' | 'incomplete';
  status: CapacitySummary['status'];
  limiting_metric: 'weight' | 'volume' | null;
  weight: RawCapacityMetric;
  volume: RawCapacityMetric;
  effective_utilization_pct: DecimalValue;
  unmeasured_handling_units: number;
  unmeasured_reservations: number;
  scope_path?: RawCapacityScopeSummary[];
  limiting_scope?: RawCapacityScopeReference | null;
}

interface RawCapacityScopeReference {
  scope_type: 'warehouse' | 'capacity_group' | 'location';
  scope_id: string;
  code: string;
  name: string;
}

interface RawCapacityScopeSummary extends RawCapacityScopeReference {
  measurement_status: 'complete' | 'incomplete';
  status: CapacitySummary['status'];
  limiting_metric: 'weight' | 'volume' | null;
  weight: RawCapacityMetric;
  volume: RawCapacityMetric;
  effective_utilization_pct: DecimalValue;
  unmeasured_handling_units: number;
  unmeasured_reservations: number;
}

type RawPackaging = Omit<
  PackagingDefinition,
  'base_quantity' | 'gross_weight_kg' | 'length_m' | 'width_m' | 'height_m' | 'volume_m3'
> & {
  base_quantity: DecimalValue;
  gross_weight_kg: DecimalValue;
  length_m: DecimalValue;
  width_m: DecimalValue;
  height_m: DecimalValue;
  volume_m3: DecimalValue;
};

type RawHandlingUnit = Omit<
  HandlingUnit,
  | 'quantity_base'
  | 'actual_gross_weight_kg'
  | 'actual_length_m'
  | 'actual_width_m'
  | 'actual_height_m'
  | 'actual_volume_m3'
  | 'occupied_weight_kg'
  | 'occupied_volume_m3'
> & {
  quantity_base: DecimalValue;
  actual_gross_weight_kg: DecimalValue;
  actual_length_m: DecimalValue;
  actual_width_m: DecimalValue;
  actual_height_m: DecimalValue;
  actual_volume_m3: DecimalValue;
  occupied_weight_kg: DecimalValue;
  occupied_volume_m3: DecimalValue;
};

function decimal(value: DecimalValue): number | null {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function requiredDecimal(value: DecimalValue, field: string): number {
  const parsed = decimal(value);
  if (parsed == null)
    throw new Error(`El servidor devolvió ${field} sin un valor numérico válido.`);
  return parsed;
}

function metric(raw: RawCapacityMetric): CapacityMetric {
  return {
    certified: decimal(raw.certified),
    operational: decimal(raw.operational),
    occupied: decimal(raw.occupied),
    reserved: decimal(raw.reserved),
    projected: decimal(raw.projected),
    available: decimal(raw.available),
    utilizationPct: decimal(raw.utilization_pct)
  };
}

function scopeSummary(raw: RawCapacityScopeSummary): CapacityScopeSummary {
  return {
    scopeType: raw.scope_type,
    scopeId: raw.scope_id,
    code: raw.code,
    name: raw.name,
    measurementStatus: raw.measurement_status,
    status: raw.status,
    limitingMetric: raw.limiting_metric,
    weight: metric(raw.weight),
    volume: metric(raw.volume),
    effectiveUtilizationPct: decimal(raw.effective_utilization_pct),
    unmeasuredHandlingUnits: raw.unmeasured_handling_units,
    unmeasuredReservations: raw.unmeasured_reservations
  };
}

function packaging(raw: RawPackaging): PackagingDefinition {
  return {
    ...raw,
    base_quantity: requiredDecimal(raw.base_quantity, 'base_quantity'),
    gross_weight_kg: decimal(raw.gross_weight_kg),
    length_m: decimal(raw.length_m),
    width_m: decimal(raw.width_m),
    height_m: decimal(raw.height_m),
    volume_m3: decimal(raw.volume_m3)
  };
}

function handlingUnit(raw: RawHandlingUnit): HandlingUnit {
  return {
    ...raw,
    quantity_base: requiredDecimal(raw.quantity_base, 'quantity_base'),
    actual_gross_weight_kg: decimal(raw.actual_gross_weight_kg),
    actual_length_m: decimal(raw.actual_length_m),
    actual_width_m: decimal(raw.actual_width_m),
    actual_height_m: decimal(raw.actual_height_m),
    actual_volume_m3: decimal(raw.actual_volume_m3),
    occupied_weight_kg: decimal(raw.occupied_weight_kg),
    occupied_volume_m3: decimal(raw.occupied_volume_m3)
  };
}

export const inventoryApi = {
  getItemByTarget: async (target: { productId?: number; variantId?: string }) => {
    const query = new URLSearchParams();
    if (target.productId != null) query.set('product_id', String(target.productId));
    if (target.variantId) query.set('variant_id', target.variantId);
    try {
      return await apiFetch<InventoryItem>(`/inventory/items/by-target?${query.toString()}`);
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) return null;
      throw error;
    }
  },

  createItem: (body: { product_id?: number; variant_id?: string; base_unit_id: number }) =>
    apiFetch<InventoryItem>('/inventory/items', {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  listPackaging: async (itemId: string) =>
    (await apiFetch<RawPackaging[]>(`/inventory/items/${itemId}/packaging`)).map(packaging),

  createPackaging: async (itemId: string, body: PackagingCreateInput) =>
    packaging(
      await apiFetch<RawPackaging>(`/inventory/items/${itemId}/packaging`, {
        method: 'POST',
        body: JSON.stringify(body)
      })
    ),

  deactivatePackaging: (itemId: string, packagingId: string) =>
    apiFetch<void>(`/inventory/items/${itemId}/packaging/${packagingId}`, {
      method: 'DELETE'
    }),

  getCapacitySummary: async (warehouseId: string, locationId?: string) => {
    const query = locationId ? `?location_id=${encodeURIComponent(locationId)}` : '';
    const raw = await apiFetch<RawCapacitySummary>(
      `/inventory/warehouses/${warehouseId}/capacity-summary${query}`
    );
    return {
      scopeType: raw.scope_type,
      warehouseId: raw.warehouse_id,
      locationId: raw.location_id,
      measurementStatus: raw.measurement_status,
      status: raw.status,
      limitingMetric: raw.limiting_metric,
      weight: metric(raw.weight),
      volume: metric(raw.volume),
      effectiveUtilizationPct: decimal(raw.effective_utilization_pct),
      unmeasuredHandlingUnits: raw.unmeasured_handling_units,
      unmeasuredReservations: raw.unmeasured_reservations,
      scopePath: (raw.scope_path ?? []).map(scopeSummary),
      limitingScope: raw.limiting_scope
        ? {
            scopeType: raw.limiting_scope.scope_type,
            scopeId: raw.limiting_scope.scope_id,
            code: raw.limiting_scope.code,
            name: raw.limiting_scope.name
          }
        : null
    } satisfies CapacitySummary;
  },

  listHandlingUnits: async (
    warehouseId: string,
    filters: {
      locationId?: string;
      inventoryItemId?: string;
      stockStatus?: StockStatus;
      includeClosed?: boolean;
    } = {}
  ) => {
    const query = new URLSearchParams();
    if (filters.locationId) query.set('location_id', filters.locationId);
    if (filters.inventoryItemId) query.set('inventory_item_id', filters.inventoryItemId);
    if (filters.stockStatus) query.set('stock_status', filters.stockStatus);
    if (filters.includeClosed) query.set('include_closed', 'true');
    const suffix = query.size ? `?${query.toString()}` : '';
    return (
      await apiFetch<RawHandlingUnit[]>(
        `/inventory/warehouses/${warehouseId}/handling-units${suffix}`
      )
    ).map(handlingUnit);
  },

  verifyHandlingUnitMeasurements: async (
    handlingUnitId: string,
    measures: PhysicalMeasuresInput,
    source: 'manual' | 'device' = 'manual'
  ) =>
    handlingUnit(
      await apiFetch<RawHandlingUnit>(`/inventory/handling-units/${handlingUnitId}/measurements`, {
        method: 'PATCH',
        body: JSON.stringify({ measures, source })
      })
    )
};

export const inventoryParsers = { decimal, metric };
