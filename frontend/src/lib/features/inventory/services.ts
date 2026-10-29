import { HttpError, apiFetch } from '$lib/api/client';
import type {
  CapacityMetric,
  CapacityScopeSummary,
  CapacitySummary,
  HandlingUnit,
  TransferHandlingUnit,
  HandlingUnitTraceability,
  InventoryMovementHistory,
  WarehouseMovementFilters,
  InventoryItem,
  InventoryItemSummary,
  PackagingCreateInput,
  PackagingDefinition,
  PhysicalMeasuresInput,
  StockStatus,
  InventoryReceiptLot,
  InventoryLabelPreview,
  InventoryLabelConfirmation,
  InventoryLabelPrint,
  InventoryLabelLayout,
  PutawayGroupResult,
  HandlingUnitSplitPrepareResult,
  InventoryTraceCapability,
  PublicHandlingUnitTrace
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

export type RawHandlingUnit = Omit<
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

type RawTransferHandlingUnit = Omit<
  TransferHandlingUnit,
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

type RawHandlingUnitTraceability = Omit<HandlingUnitTraceability, 'handling_unit' | 'movements'> & {
  handling_unit: RawHandlingUnit;
  movements: Array<
    Omit<HandlingUnitTraceability['movements'][number], 'quantity_base'> & {
      quantity_base: DecimalValue;
    }
  >;
};

interface RawInventoryItemSummary extends Omit<
  InventoryItemSummary,
  'total_quantity_base' | 'status_totals' | 'occupied_weight_kg' | 'occupied_volume_m3'
> {
  total_quantity_base: DecimalValue;
  occupied_weight_kg: DecimalValue;
  occupied_volume_m3: DecimalValue;
  status_totals: Array<{
    stock_status: StockStatus;
    quantity_base: DecimalValue;
    occupied_weight_kg: DecimalValue;
    occupied_volume_m3: DecimalValue;
    measurement_status: 'complete' | 'incomplete';
  }>;
}

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

export function handlingUnit(raw: RawHandlingUnit): HandlingUnit {
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

function transferHandlingUnit(raw: RawTransferHandlingUnit): TransferHandlingUnit {
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

function inventoryItemSummary(raw: RawInventoryItemSummary): InventoryItemSummary {
  return {
    ...raw,
    total_quantity_base: requiredDecimal(raw.total_quantity_base, 'total_quantity_base'),
    occupied_weight_kg: decimal(raw.occupied_weight_kg),
    occupied_volume_m3: decimal(raw.occupied_volume_m3),
    status_totals: raw.status_totals.map((status) => ({
      ...status,
      quantity_base: requiredDecimal(status.quantity_base, 'quantity_base'),
      occupied_weight_kg: decimal(status.occupied_weight_kg),
      occupied_volume_m3: decimal(status.occupied_volume_m3)
    }))
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

  getItemSummary: async (itemId: string) =>
    inventoryItemSummary(
      await apiFetch<RawInventoryItemSummary>(`/inventory/items/${itemId}/summary`)
    ),

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

  listTransferUnits: async (warehouseId: string, stockStatus: 'available' | 'in_transit') =>
    (
      await apiFetch<RawTransferHandlingUnit[]>(
        `/inventory/warehouses/${warehouseId}/transfer-units?stock_status=${stockStatus}`
      )
    ).map(transferHandlingUnit),

  getHandlingUnitTraceability: async (handlingUnitId: string) => {
    const raw = await apiFetch<RawHandlingUnitTraceability>(
      `/inventory/handling-units/${handlingUnitId}/traceability`
    );
    return {
      ...raw,
      handling_unit: handlingUnit(raw.handling_unit),
      movements: raw.movements.map((movement) => ({
        ...movement,
        quantity_base: requiredDecimal(movement.quantity_base, 'quantity_base')
      }))
    } satisfies HandlingUnitTraceability;
  },

  listReceiptLots: async (filters: {
    warehouseId: string;
    status?: 'pending_placement' | 'partially_placed' | 'placed' | 'all';
    page?: number;
    size?: number;
  }) => {
    const query = new URLSearchParams({
      warehouse_id: filters.warehouseId,
      status: filters.status ?? 'pending_placement',
      page: String(filters.page ?? 1),
      size: String(filters.size ?? 20)
    });
    return apiFetch<{
      items: InventoryReceiptLot[];
      page: number;
      size: number;
      total: number;
      legacy_stock: import('./types').LegacyInventoryStock[];
    }>(`/inventory/lots?${query.toString()}`);
  },

  confirmPutawayGroup: (body: {
    idempotency_key: string;
    receipt_lot_id: string;
    inventory_lot_detail_id: string;
    inventory_item_id: string;
    allocations: Array<{
      handling_unit_id: string;
      quantity_base: string;
      destination_location_id: string;
    }>;
  }) =>
    apiFetch<PutawayGroupResult>('/inventory/putaway-groups/confirm', {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  previewInventoryLabel: (target: {
    inventory_lot_detail_id?: string;
    handling_unit_id?: string;
  }) => {
    const query = new URLSearchParams();
    if (target.inventory_lot_detail_id) {
      query.set('inventory_lot_detail_id', target.inventory_lot_detail_id);
    }
    if (target.handling_unit_id) query.set('handling_unit_id', target.handling_unit_id);
    return apiFetch<InventoryLabelPreview>(`/inventory/labels/preview?${query.toString()}`);
  },

  recordInventoryLabelPrint: (body: {
    idempotency_key: string;
    inventory_lot_detail_id?: string;
    handling_unit_id?: string;
    quantity_printed: number;
    print_date: string;
    reason: 'initial' | 'reprint';
    layout?: InventoryLabelLayout;
    notes?: string | null;
  }) =>
    apiFetch<InventoryLabelPrint>('/inventory/labels/prints', {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  confirmInventoryLabelPlacement: (body: {
    idempotency_key: string;
    handling_unit_id: string;
    handling_unit_code: string;
    label_print_id: string;
  }) =>
    apiFetch<InventoryLabelConfirmation>('/inventory/labels/confirmations', {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  createTraceCapability: (handlingUnitId: string) =>
    apiFetch<InventoryTraceCapability>('/inventory/trace-capabilities', {
      method: 'POST',
      body: JSON.stringify({ handling_unit_id: handlingUnitId })
    }),

  revokeTraceCapabilities: (handlingUnitId: string) =>
    apiFetch<{ revoked_count: number }>(
      `/inventory/trace-capabilities/${encodeURIComponent(handlingUnitId)}/revoke`,
      { method: 'POST' }
    ),

  getPublicTraceability: (token: string) =>
    apiFetch<PublicHandlingUnitTrace>('/inventory/public-traces/resolve', {
      method: 'POST',
      body: JSON.stringify({ token }),
      noAuth: true,
      noRefresh: true,
      noCredentials: true
    }),

  listWarehouseMovements: async (
    warehouseId: string,
    limit = 10,
    movementType?: string,
    offset = 0,
    filters: WarehouseMovementFilters = {},
    signal?: AbortSignal
  ) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (offset > 0) query.set('offset', String(offset));
    if (movementType) query.set('movement_type', movementType);
    for (const [key, value] of Object.entries(filters)) {
      if (value?.trim()) query.set(key, value.trim());
    }
    const path = `/inventory/warehouses/${warehouseId}/movements?${query.toString()}`;
    return signal
      ? apiFetch<InventoryMovementHistory[]>(path, { signal })
      : apiFetch<InventoryMovementHistory[]>(path);
  },

  releaseHandlingUnit: async (
    unit: HandlingUnit,
    destinationLocationId: string,
    idempotencyKey: string
  ) => {
    const reference = `quarantine-release:${unit.id}:${idempotencyKey}`;
    await apiFetch<unknown>('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        source_reference: reference,
        movement_type: 'putaway',
        lines: [
          {
            inventory_item_id: unit.inventory_item_id,
            handling_unit_id: unit.id,
            from_location_id: unit.location_id,
            to_location_id: destinationLocationId,
            from_stock_status: 'quarantine',
            to_stock_status: 'available',
            quantity_base: unit.quantity_base
          }
        ]
      })
    });
  },

  transferUnits: async (
    units: Array<Pick<HandlingUnit, 'id' | 'inventory_item_id' | 'location_id' | 'quantity_base'>>,
    destinationLocationId: string,
    sourceReference: string,
    fromStatus: 'available' | 'in_transit',
    toStatus: 'in_transit' | 'available' | 'quarantine',
    idempotencyKey: string,
    destinationStatusByUnitId?: Record<string, 'available' | 'quarantine'>
  ) =>
    apiFetch<unknown>('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        source_reference: sourceReference.slice(0, 160),
        movement_type: 'transfer',
        lines: units.map((unit) => ({
          inventory_item_id: unit.inventory_item_id,
          handling_unit_id: unit.id,
          from_location_id: unit.location_id,
          to_location_id: destinationLocationId,
          from_stock_status: fromStatus,
          to_stock_status: destinationStatusByUnitId?.[unit.id] ?? toStatus,
          quantity_base: unit.quantity_base
        }))
      })
    }),

  transferAllocations: async (
    allocations: Array<{
      unit: Pick<HandlingUnit, 'id' | 'inventory_item_id' | 'location_id' | 'quantity_base'>;
      quantity_base: number;
    }>,
    destinationLocationId: string,
    sourceReference: string,
    idempotencyKey: string
  ) =>
    apiFetch<unknown>('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        source_reference: sourceReference.slice(0, 160),
        movement_type: 'transfer',
        lines: allocations.map(({ unit, quantity_base }) => ({
          inventory_item_id: unit.inventory_item_id,
          handling_unit_id: unit.id,
          from_location_id: unit.location_id,
          to_location_id: destinationLocationId,
          from_stock_status: 'available',
          to_stock_status: 'in_transit',
          quantity_base
        }))
      })
    }),

  receiveTransferAllocations: async (
    allocations: Array<{
      unit: Pick<HandlingUnit, 'id' | 'inventory_item_id' | 'location_id' | 'quantity_base'>;
      quantity_base: number;
    }>,
    destinationLocationId: string,
    sourceReference: string,
    idempotencyKey: string
  ) =>
    apiFetch<unknown>('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        source_reference: sourceReference.slice(0, 160),
        movement_type: 'transfer',
        lines: allocations.map(({ unit, quantity_base }) => ({
          inventory_item_id: unit.inventory_item_id,
          handling_unit_id: unit.id,
          from_location_id: unit.location_id,
          to_location_id: destinationLocationId,
          from_stock_status: 'in_transit',
          to_stock_status: 'quarantine',
          quantity_base
        }))
      })
    }),

  transferHandlingUnit: async (
    unit: HandlingUnit,
    destinationLocationId: string,
    idempotencyKey: string
  ) => {
    const reference = `warehouse-transfer:${unit.id}:${idempotencyKey}`;
    await apiFetch<unknown>('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        source_reference: reference,
        movement_type: 'transfer',
        lines: [
          {
            inventory_item_id: unit.inventory_item_id,
            handling_unit_id: unit.id,
            from_location_id: unit.location_id,
            to_location_id: destinationLocationId,
            from_stock_status: 'available',
            to_stock_status: 'in_transit',
            quantity_base: unit.quantity_base
          }
        ]
      })
    });
  },

  prepareHandlingUnitSplit: (
    unitId: string,
    splitQuantityBase: number,
    destinationLocationId: string,
    idempotencyKey: string
  ) =>
    apiFetch<HandlingUnitSplitPrepareResult>(`/inventory/handling-units/${unitId}/prepare-split`, {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        split_quantity_base: splitQuantityBase.toString(),
        destination_location_id: destinationLocationId
      })
    }),

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
