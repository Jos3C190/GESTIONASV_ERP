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
import type { HandlingUnit } from './types';

describe('inventory service', () => {
  beforeEach(() => vi.clearAllMocks());

  it('envía filtros de movimientos y cancelación sin descargar el historial completo', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce([]);
    const controller = new AbortController();
    await inventoryApi.listWarehouseMovements('warehouse-1', 26, 'receipt', 25, {
      period_from: '2026-10-01', period_to: '2026-10-28', q: ' Chocolate ',
      lot_code: 'LOT 28', direction: 'incoming'
    }, controller.signal);
    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/inventory/warehouses/warehouse-1/movements?limit=26&offset=25&movement_type=receipt&period_from=2026-10-01&period_to=2026-10-28&q=Chocolate&lot_code=LOT+28&direction=incoming',
      { signal: controller.signal }
    );
  });

  it('permite paginar todos los movimientos de bodega', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce([]);

    await inventoryApi.listWarehouseMovements('warehouse-1', 1000, 'transfer', 1000);

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/inventory/warehouses/warehouse-1/movements?limit=1000&offset=1000&movement_type=transfer'
    );
  });

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

  it('obtiene la ficha QR y normaliza cantidades e historial de movimientos', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      handling_unit: {
        id: 'hu-1',
        company_id: 'company-1',
        warehouse_id: 'warehouse-1',
        location_id: 'location-1',
        inventory_item_id: 'item-1',
        packaging_definition_id: null,
        code: 'HU-0001',
        lot_code: 'L-01',
        receipt_lot_code: 'LOT-COM-0001-D1',
        receipt_lot_header_code: 'LOT-COM-0001',
        expiry_date: null,
        quantity_base: '25.500000',
        actual_gross_weight_kg: null,
        actual_length_m: null,
        actual_width_m: null,
        actual_height_m: null,
        actual_volume_m3: null,
        occupied_weight_kg: null,
        occupied_volume_m3: null,
        stock_status: 'available',
        measurement_status: 'complete',
        measurement_source: 'receipt',
        closed_at: null,
        created_at: '2026-10-05T10:00:00Z',
        updated_at: null
      },
      product_sku: 'PRD-01',
      product_name: 'Producto de prueba',
      base_unit_name: 'Caja',
      base_unit_symbol: 'cj',
      warehouse_code: 'BOD-CENTRAL',
      warehouse_name: 'Bodega madre',
      location_code: 'REC-01',
      origin: {
        supplier_code: 'PROV-01',
        supplier_name: 'Proveedor de prueba',
        purchase_code: 'COMP-0001',
        purchase_order_code: 'OC-0001',
        received_at: '2026-10-05T10:00:00Z',
        purchase_date: '2026-10-05T09:00:00Z',
        consolidation_code: 'CD-0001',
        requests: [
          {
            request_code: 'SCR-0001',
            branch_name: 'Sucursal Centro',
            requested_at: '2026-10-01T09:00:00Z',
            required_date: null
          }
        ]
      },
      movements: [
        {
          movement_id: 'move-1',
          movement_type: 'receipt',
          source_reference: 'purchase-receipt:abc',
          posted_at: '2026-10-05T10:00:00Z',
          posted_by: 'user-1',
          operator: 'compras',
          from_warehouse_code: null,
          from_warehouse_name: null,
          from_location_code: null,
          from_stock_status: null,
          to_warehouse_code: 'BOD-CENTRAL',
          to_warehouse_name: 'Bodega madre',
          to_location_code: 'REC-01',
          to_stock_status: 'quarantine',
          quantity_base: '25.500000'
        }
      ]
    });

    const result = await inventoryApi.getHandlingUnitTraceability('hu-1');

    expect(apiMocks.apiFetch).toHaveBeenCalledWith('/inventory/handling-units/hu-1/traceability');
    expect(result.handling_unit.quantity_base).toBe(25.5);
    expect(result.handling_unit.receipt_lot_code).toBe('LOT-COM-0001-D1');
    expect(result.handling_unit.receipt_lot_header_code).toBe('LOT-COM-0001');
    expect(result.origin.requests[0]?.branch_name).toBe('Sucursal Centro');
    expect(result.movements[0]?.quantity_base).toBe(25.5);
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

  it('crea enlaces QR y resuelve la ficha pública sin autenticación', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      token: 'q'.repeat(43),
      created_at: '2026-10-14T10:00:00Z'
    });
    const capability = await inventoryApi.createTraceCapability('hu/one');
    expect(capability.token).toBe('q'.repeat(43));
    expect(apiMocks.apiFetch).toHaveBeenNthCalledWith(1, '/inventory/trace-capabilities', {
      method: 'POST',
      body: JSON.stringify({ handling_unit_id: 'hu/one' })
    });

    const publicTrace = { handling_unit_code: 'HU-0001', movements: [] };
    apiMocks.apiFetch.mockResolvedValueOnce(publicTrace);
    await expect(inventoryApi.getPublicTraceability(capability.token)).resolves.toBe(publicTrace);
    expect(apiMocks.apiFetch).toHaveBeenNthCalledWith(2, '/inventory/public-traces/resolve', {
      method: 'POST',
      body: JSON.stringify({ token: capability.token }),
      noAuth: true,
      noRefresh: true,
      noCredentials: true
    });
  });

  it('traslada la unidad logística completa a la ubicación de la sucursal', async () => {
    const unit: HandlingUnit = {
      id: 'hu-1',
      company_id: 'company-1',
      warehouse_id: 'mother-warehouse',
      location_id: 'mother-location',
      inventory_item_id: 'item-1',
      packaging_definition_id: null,
      code: 'HU-0001',
      lot_code: null,
      expiry_date: null,
      quantity_base: 500,
      actual_gross_weight_kg: null,
      actual_length_m: null,
      actual_width_m: null,
      actual_height_m: null,
      actual_volume_m3: null,
      occupied_weight_kg: null,
      occupied_volume_m3: null,
      stock_status: 'available',
      measurement_status: 'verified',
      measurement_source: 'receipt',
      closed_at: null,
      created_at: null,
      updated_at: null
    };
    apiMocks.apiFetch.mockResolvedValueOnce(undefined);

    await inventoryApi.transferHandlingUnit(unit, 'branch-location', 'idem-1');

    expect(apiMocks.apiFetch).toHaveBeenCalledWith('/inventory/movements/confirm', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: 'idem-1',
        source_reference: 'warehouse-transfer:hu-1:idem-1',
        movement_type: 'transfer',
        lines: [
          {
            inventory_item_id: 'item-1',
            handling_unit_id: 'hu-1',
            from_location_id: 'mother-location',
            to_location_id: 'branch-location',
            from_stock_status: 'available',
            to_stock_status: 'in_transit',
            quantity_base: 500
          }
        ]
      })
    });
  });

  it('despacha solo la cantidad asignada y conserva la solicitud como referencia', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce(undefined);

    await inventoryApi.transferAllocations(
      [
        {
          unit: {
            id: 'hu-mother-1',
            inventory_item_id: 'item-1',
            location_id: 'mother-location',
            quantity_base: 2200
          },
          quantity_base: 500
        }
      ],
      'branch-receiving-location',
      'TR-20261007 · Solicitud SCR-00013 · surtido parcial',
      'dispatch-1'
    );

    const [, request] = apiMocks.apiFetch.mock.calls[0]!;
    expect(JSON.parse(request.body)).toMatchObject({
      idempotency_key: 'dispatch-1',
      source_reference: 'TR-20261007 · Solicitud SCR-00013 · surtido parcial',
      movement_type: 'transfer',
      lines: [
        {
          inventory_item_id: 'item-1',
          handling_unit_id: 'hu-mother-1',
          from_location_id: 'mother-location',
          to_location_id: 'branch-receiving-location',
          from_stock_status: 'available',
          to_stock_status: 'in_transit',
          quantity_base: 500
        }
      ]
    });
  });

  it('registra la cantidad contada en cuarentena y mantiene el destino en tránsito', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce(undefined);

    await inventoryApi.receiveTransferAllocations(
      [
        {
          unit: {
            id: 'hu-transit-1',
            inventory_item_id: 'item-1',
            location_id: 'branch-receiving-location',
            quantity_base: 2200
          },
          quantity_base: 2180
        }
      ],
      'branch-receiving-location',
      'RECIBIDO · TR-20261007',
      'receipt-1'
    );

    const [, request] = apiMocks.apiFetch.mock.calls[0]!;
    expect(JSON.parse(request.body)).toMatchObject({
      idempotency_key: 'receipt-1',
      movement_type: 'transfer',
      lines: [
        {
          inventory_item_id: 'item-1',
          handling_unit_id: 'hu-transit-1',
          from_location_id: 'branch-receiving-location',
          to_location_id: 'branch-receiving-location',
          from_stock_status: 'in_transit',
          to_stock_status: 'quarantine',
          quantity_base: 2180
        }
      ]
    });
  });
});
