import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { PhysicalKardexRow } from '../kardex';
import KardexMovementDetails from './KardexMovementDetails.svelte';

function movement(overrides: Partial<PhysicalKardexRow> = {}): PhysicalKardexRow {
  return {
    id: 'line-1',
    movement_id: 'movement-1',
    movement_type: 'receipt',
    source_reference: 'purchase-receipt:receipt-1',
    posted_at: '2026-10-14T12:00:00Z',
    product_name: 'Chocolate de cobertura',
    product_sku: 'PRD-CH-006',
    base_unit_symbol: 'cj',
    lot_code: 'LOT-001',
    receipt_lot_code: 'LOT-COM-00001-D1',
    receipt_lot_header_code: 'LOT-COM-00001',
    handling_unit_id: 'unit-1',
    handling_unit_code: 'HU-0001',
    from_warehouse_id: null,
    from_warehouse_external: true,
    from_warehouse_code: null,
    from_warehouse_name: null,
    from_location_id: null,
    from_location_code: null,
    from_stock_status: null,
    to_warehouse_id: 'warehouse-1',
    to_warehouse_external: false,
    to_warehouse_code: 'BM-001',
    to_warehouse_name: 'Bodega Madre',
    to_location_id: 'location-1',
    to_location_code: 'REC-01',
    to_stock_status: 'quarantine',
    quantity_base: '12',
    incoming_quantity: '12',
    outgoing_quantity: '0',
    net_quantity: '12',
    balance_after: '12',
    is_internal: false,
    ...overrides
  };
}

describe('KardexMovementDetails', () => {
  it('muestra el movimiento y enlaza solo la unidad logística incluida en la respuesta', () => {
    render(KardexMovementDetails, {
      props: { movement: movement(), onclose: vi.fn() }
    });

    expect(screen.getByRole('dialog', { name: 'Detalle del movimiento físico' })).toBeVisible();
    expect(screen.getByText('Chocolate de cobertura')).toBeVisible();
    expect(screen.getByText('Bodega Madre')).toBeVisible();
    expect(screen.getByText('Origen externo')).toBeVisible();
    expect(screen.getByText(/Fabricante: LOT-001/)).toBeVisible();
    expect(screen.getByText(/Recepción: LOT-COM-00001-D1/)).toBeVisible();
    expect(screen.getByText(/Recepción agrupada: LOT-COM-00001/)).toBeVisible();
    expect(screen.getByText('movement-1')).toBeVisible();
    expect(screen.getByRole('link', { name: 'HU-0001' })).toHaveAttribute(
      'href',
      '/inventory/handling-units/unit-1'
    );
  });

  it('no inventa enlace o ubicación cuando el servidor los oculta por alcance', () => {
    render(KardexMovementDetails, {
      props: {
        movement: movement({
          from_warehouse_external: false,
          handling_unit_id: null,
          handling_unit_code: null,
          to_warehouse_name: null,
          to_location_code: null,
          balance_after: null
        }),
        onclose: vi.fn()
      }
    });

    expect(screen.queryByRole('link', { name: 'HU-0001' })).not.toBeInTheDocument();
    expect(screen.getAllByText('No disponible para este alcance')).toHaveLength(3);
    expect(screen.getByText('No reconstruible')).toBeVisible();
  });

  it('distingue una salida externa de un destino oculto por alcance', () => {
    render(KardexMovementDetails, {
      props: {
        movement: movement({
          from_warehouse_id: 'warehouse-1',
          from_warehouse_external: false,
          from_warehouse_name: 'Bodega Madre',
          to_warehouse_id: null,
          to_warehouse_external: true,
          to_warehouse_name: null
        }),
        onclose: vi.fn()
      }
    });

    expect(screen.getByText('Destino externo')).toBeVisible();
    expect(screen.getByText('Bodega Madre')).toBeVisible();
    expect(screen.queryByText('No disponible para este alcance')).not.toBeInTheDocument();
  });
});
