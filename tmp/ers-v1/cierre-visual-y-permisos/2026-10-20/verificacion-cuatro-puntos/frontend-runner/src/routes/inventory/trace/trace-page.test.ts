import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TracePage from './+page.svelte';

const inventoryMocks = vi.hoisted(() => ({
  getPublicTraceability: vi.fn()
}));

vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: inventoryMocks }));

describe('public inventory trace page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(window.history.state, '', `/inventory/trace#${'t'.repeat(43)}`);
    inventoryMocks.getPublicTraceability.mockResolvedValue({
      handling_unit_code: 'HU-0001',
      product_sku: 'PRD-001',
      product_name: 'Producto de prueba',
      quantity_base: '12',
      base_unit_symbol: 'caja',
      lot_code: null,
      receipt_lot_code: null,
      expiry_date: null,
      stock_status: 'quarantine',
      warehouse_code: 'BOD-001',
      warehouse_name: null,
      location_code: null,
      origin: {
        supplier_name: 'Proveedor de prueba',
        purchase_code: 'COM-0001',
        purchase_order_code: 'OC-0001',
        received_at: null,
        consolidation_code: null
      },
      movements: []
    });
  });

  it('muestra una ubicación legible cuando la unidad aún no tiene posición asignada', async () => {
    render(TracePage);

    expect(await screen.findByText('HU-0001')).toBeInTheDocument();
    expect(screen.getByText('BOD-001 · Sin ubicación asignada')).toBeInTheDocument();
    expect(inventoryMocks.getPublicTraceability).toHaveBeenCalledWith('t'.repeat(43));
    expect(window.location.hash).toBe('');
  });

  it('explica que el origen no está disponible cuando la unidad no tiene recepción enlazada', async () => {
    inventoryMocks.getPublicTraceability.mockResolvedValueOnce({
      handling_unit_code: 'HU-LEGACY',
      product_sku: 'PRD-001',
      product_name: 'Producto heredado',
      quantity_base: '12',
      base_unit_symbol: 'caja',
      lot_code: null,
      receipt_lot_code: null,
      expiry_date: null,
      stock_status: 'quarantine',
      warehouse_code: 'BOD-001',
      warehouse_name: null,
      location_code: null,
      origin: {
        supplier_name: null,
        purchase_code: null,
        purchase_order_code: null,
        received_at: null,
        consolidation_code: null
      },
      movements: []
    });

    render(TracePage);

    expect(await screen.findByText('HU-LEGACY')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Esta unidad está registrada en inventario, pero no tiene una recepción o lote de compra enlazado. El origen no está disponible.'
      )
    ).toBeInTheDocument();
    expect(screen.getAllByText('No enlazada')).toHaveLength(2);
  });
});
