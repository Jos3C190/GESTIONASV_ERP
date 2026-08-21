import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock('$lib/api/client', () => ({
  apiFetch: apiMocks.apiFetch,
  HttpError: class HttpError extends Error {
    status: number;
    constructor(_code: string, message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
}));

import { inventoryApi } from './services';

describe('inventory service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('conserva desconocidos y normaliza decimales del resumen físico', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      scope_type: 'warehouse',
      warehouse_id: 'warehouse-1',
      location_id: null,
      measurement_status: 'incomplete',
      status: 'incomplete',
      limiting_metric: 'volume',
      weight: {
        certified: '1000.000000',
        operational: '900.000000',
        occupied: null,
        reserved: null,
        projected: null,
        available: null,
        utilization_pct: null
      },
      volume: {
        certified: '100.000000',
        operational: '80.000000',
        occupied: null,
        reserved: null,
        projected: null,
        available: null,
        utilization_pct: null
      },
      effective_utilization_pct: null,
      unmeasured_handling_units: 2,
      unmeasured_reservations: 1,
      scope_path: [
        {
          scope_type: 'warehouse',
          scope_id: 'warehouse-1',
          code: 'BOD-01',
          name: 'Bodega principal',
          measurement_status: 'incomplete',
          status: 'incomplete',
          limiting_metric: 'volume',
          weight: {
            certified: '1000',
            operational: '900',
            occupied: null,
            reserved: null,
            projected: null,
            available: null,
            utilization_pct: null
          },
          volume: {
            certified: '100',
            operational: '80',
            occupied: null,
            reserved: null,
            projected: null,
            available: null,
            utilization_pct: null
          },
          effective_utilization_pct: null,
          unmeasured_handling_units: 2,
          unmeasured_reservations: 1
        }
      ],
      limiting_scope: null
    });

    const result = await inventoryApi.getCapacitySummary('warehouse-1');

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/inventory/warehouses/warehouse-1/capacity-summary'
    );
    expect(result.weight.operational).toBe(900);
    expect(result.weight.occupied).toBeNull();
    expect(result.effectiveUtilizationPct).toBeNull();
    expect(result.unmeasuredHandlingUnits).toBe(2);
    expect(result.scopePath[0]).toMatchObject({ scopeId: 'warehouse-1', code: 'BOD-01' });
    expect(result.limitingScope).toBeNull();
  });

  it('conserva la alarma de exceso certificado en el contrato del resumen', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      scope_type: 'warehouse',
      warehouse_id: 'warehouse-1',
      location_id: null,
      measurement_status: 'complete',
      status: 'over_certified',
      limiting_metric: 'weight',
      weight: {
        certified: '100',
        operational: '90',
        occupied: '110',
        reserved: '0',
        projected: '110',
        available: '-20',
        utilization_pct: '122.222222'
      },
      volume: {
        certified: '50',
        operational: '45',
        occupied: '20',
        reserved: '0',
        projected: '20',
        available: '25',
        utilization_pct: '44.444444'
      },
      effective_utilization_pct: '122.222222',
      unmeasured_handling_units: 0,
      unmeasured_reservations: 0
    });

    const result = await inventoryApi.getCapacitySummary('warehouse-1');

    expect(result.status).toBe('over_certified');
    expect(result.weight.projected).toBe(110);
    expect(result.weight.available).toBe(-20);
  });

  it('normaliza una presentación versionada sin perder valores nulos', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce([
      {
        id: 'pack-1',
        company_id: 'company-1',
        inventory_item_id: 'item-1',
        code: 'CAJA12',
        name: 'Caja de 12',
        packaging_type: 'box',
        version: 2,
        base_quantity: '12.000000',
        gross_weight_kg: '6.250000',
        length_m: '0.400000',
        width_m: '0.300000',
        height_m: '0.200000',
        volume_m3: '0.024000',
        stackable: true,
        max_stack: 5,
        is_current: true,
        is_active: true,
        created_at: null
      }
    ]);

    const result = await inventoryApi.listPackaging('item-1');

    expect(result[0]).toMatchObject({ base_quantity: 12, gross_weight_kg: 6.25, volume_m3: 0.024 });
  });

  it('mantiene como desconocida la ocupación de una unidad logística sin medir', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce([
      {
        id: 'hu-1',
        company_id: 'company-1',
        warehouse_id: 'warehouse-1',
        location_id: 'location-1',
        inventory_item_id: 'item-1',
        packaging_definition_id: null,
        code: 'HU-0001',
        lot_code: null,
        expiry_date: null,
        quantity_base: '4.000000',
        actual_gross_weight_kg: null,
        actual_length_m: null,
        actual_width_m: null,
        actual_height_m: null,
        actual_volume_m3: null,
        occupied_weight_kg: null,
        occupied_volume_m3: null,
        stock_status: 'quarantine',
        measurement_status: 'incomplete',
        measurement_source: 'receipt',
        closed_at: null,
        created_at: null,
        updated_at: null
      }
    ]);

    const result = await inventoryApi.listHandlingUnits('warehouse-1');

    expect(result[0]).toMatchObject({
      quantity_base: 4,
      occupied_weight_kg: null,
      occupied_volume_m3: null,
      measurement_status: 'incomplete'
    });
  });

  it('normaliza el resumen global de una variante sin convertir medidas desconocidas en cero', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      inventory_item_id: 'item-variant-1',
      company_id: 'company-1',
      product_id: null,
      variant_id: 'variant-1',
      base_unit_id: 1,
      is_active: true,
      total_quantity_base: '14.000000',
      status_totals: [
        {
          stock_status: 'available',
          quantity_base: '10.000000',
          occupied_weight_kg: '20.000000',
          occupied_volume_m3: '0.500000',
          measurement_status: 'complete'
        },
        {
          stock_status: 'quarantine',
          quantity_base: '4.000000',
          occupied_weight_kg: null,
          occupied_volume_m3: null,
          measurement_status: 'incomplete'
        }
      ],
      occupied_weight_kg: null,
      occupied_volume_m3: null,
      measurement_status: 'incomplete',
      handling_unit_count: 3,
      unmeasured_handling_units: 1,
      warehouse_count: 2,
      location_count: 3,
      lot_count: 1
    });

    const result = await inventoryApi.getItemSummary('item-variant-1');

    expect(apiMocks.apiFetch).toHaveBeenCalledWith('/inventory/items/item-variant-1/summary');
    expect(result.total_quantity_base).toBe(14);
    expect(result.occupied_weight_kg).toBeNull();
    expect(result.status_totals[0]!.occupied_weight_kg).toBe(20);
    expect(result.status_totals[1]!.occupied_volume_m3).toBeNull();
  });
});
