import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LocationOut } from '$lib/features/locations/types';
import type { InventoryReceiptLot } from '../types';
import GroupedPutawayPanel from './GroupedPutawayPanel.svelte';

const inventoryMocks = vi.hoisted(() => ({
  listReceiptLots: vi.fn(),
  confirmPutawayGroup: vi.fn()
}));
const locationMocks = vi.hoisted(() => ({ listLocations: vi.fn() }));

vi.mock('../services', () => ({ inventoryApi: inventoryMocks }));
vi.mock('$lib/features/locations/services', () => locationMocks);

function receiptLot(): InventoryReceiptLot {
  return {
    id: 'receipt-lot-1',
    company_id: 'company-1',
    purchase_id: 'purchase-1',
    purchase_code: 'COM-00001',
    warehouse_id: 'warehouse-1',
    code: 'LOT-COM-00001',
    received_at: '2026-10-13T01:00:00Z',
    placement_status: 'pending_placement',
    costing_status: 'applied',
    lines: [
      {
        inventory_lot_detail_ids: ['lot-detail-1'],
        inventory_lot_detail_id: 'lot-detail-1',
        receipt_lot_detail_code: 'LOT-COM-00001-D1',
        purchase_detail_id: 'purchase-detail-1',
        inventory_item_id: 'item-1',
        product_sku: 'PRD-0001',
        product_name: 'Producto de prueba',
        base_unit_id: 1,
        base_unit_name: 'Caja',
        base_unit_symbol: 'cj',
        accepted_quantity_base: '20',
        placed_quantity_base: '0',
        pending_placement_quantity_base: '20',
        handling_units: [
          {
            id: 'hu-source',
            company_id: 'company-1',
            warehouse_id: 'warehouse-1',
            location_id: 'receiving-1',
            inventory_item_id: 'item-1',
            packaging_definition_id: null,
            code: 'HU-0001',
            lot_code: 'FAB-LOT-1',
            expiry_date: null,
            quantity_base: 20,
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
            created_at: '2026-10-13T12:00:00Z',
            updated_at: null,
            location_code: 'REC-01',
            pending_placement_quantity_base: '20',
            placed_quantity_base: '0'
          }
        ]
      }
    ]
  };
}

function location(id: string, code: string): LocationOut {
  return {
    id,
    code,
    barcode: `BAR-${code}`,
    is_active: true,
    storage_eligible: true,
    lifecycle_status: 'active',
    location_type: 'standard'
  } as unknown as LocationOut;
}

describe('GroupedPutawayPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    inventoryMocks.listReceiptLots.mockResolvedValue({
      items: [receiptLot()],
      page: 1,
      size: 20,
      total: 1
    });
    inventoryMocks.confirmPutawayGroup.mockResolvedValue({
      idempotency_key: 'attempt-1',
      receipt_lot_id: 'receipt-lot-1',
      inventory_item_id: 'item-1',
      total_quantity_base: '20',
      allocations: [
        {
          source_handling_unit_id: 'hu-source',
          handling_unit_id: 'hu-child-a',
          handling_unit_code: 'HU-CHILD-A',
          movement_id: 'move-a',
          destination_location_id: 'location-a',
          destination_location_code: 'A-01',
          quantity_base: '12',
          stock_status: 'quarantine',
          measurement_status: 'incomplete',
          measurement_source: 'transfer_estimate'
        },
        {
          source_handling_unit_id: 'hu-source',
          handling_unit_id: 'hu-child-b',
          handling_unit_code: 'HU-CHILD-B',
          movement_id: 'move-b',
          destination_location_id: 'location-b',
          destination_location_code: 'B-01',
          quantity_base: '8',
          stock_status: 'quarantine',
          measurement_status: 'incomplete',
          measurement_source: 'transfer_estimate'
        }
      ],
      replayed: false
    });
    locationMocks.listLocations.mockResolvedValue({
      items: [location('location-a', 'A-01'), location('location-b', 'B-01')],
      meta: { page: 1, size: 100, total: 2, pages: 1 }
    });
  });

  it('escanea el producto y reparte una HU de 20 en 12 y 8 sin volver a recibirla', async () => {
    inventoryMocks.listReceiptLots
      .mockResolvedValueOnce({ items: [receiptLot()], page: 1, size: 20, total: 1 })
      .mockResolvedValueOnce({ items: [], page: 1, size: 20, total: 0 });
    const onconfirmed = vi.fn();
    render(GroupedPutawayPanel, { props: { warehouseId: 'warehouse-1', onconfirmed } });

    await screen.findByText('LOT-COM-00001');
    expect(await screen.findByRole('option', { name: /12\/10\/26/ })).toBeInTheDocument();
    const productScan = screen.getByLabelText('Escanear código del producto');
    await fireEvent.input(productScan, { target: { value: 'PRD-0001' } });
    await fireEvent.keyDown(productScan, { key: 'Enter' });

    const locationScan = screen.getByLabelText('Escanear ubicación');
    const quantity = screen.getByLabelText('Cantidad base');
    await fireEvent.input(locationScan, { target: { value: 'A-01' } });
    await fireEvent.keyDown(locationScan, { key: 'Enter' });
    await fireEvent.input(quantity, { target: { value: '12' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Agregar destino' }));

    await fireEvent.input(locationScan, { target: { value: 'B-01' } });
    await fireEvent.keyDown(locationScan, { key: 'Enter' });
    await fireEvent.input(quantity, { target: { value: '8' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Agregar destino' }));
    expect(screen.getByText('Quedará pendiente').nextElementSibling).toHaveTextContent('0');

    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar ubicación del grupo' }));
    await waitFor(() => expect(inventoryMocks.confirmPutawayGroup).toHaveBeenCalledTimes(1));
    const request = inventoryMocks.confirmPutawayGroup.mock.calls[0]?.[0];
    expect(request).toMatchObject({
      receipt_lot_id: 'receipt-lot-1',
      inventory_item_id: 'item-1',
      allocations: [
        {
          handling_unit_id: 'hu-source',
          destination_location_id: 'location-a',
          quantity_base: '12'
        },
        {
          handling_unit_id: 'hu-source',
          destination_location_id: 'location-b',
          quantity_base: '8'
        }
      ]
    });
    expect(onconfirmed).toHaveBeenCalledOnce();
    expect(await screen.findByRole('link', { name: 'Revisar unidad HU-CHILD-A' })).toHaveAttribute(
      'href',
      '/warehouses/warehouse-1?tab=inventario&handling_unit=hu-child-a'
    );
    expect(screen.getByRole('link', { name: 'Revisar unidad HU-CHILD-B' })).toHaveAttribute(
      'href',
      '/warehouses/warehouse-1?tab=inventario&handling_unit=hu-child-b'
    );
    expect(
      await screen.findByText('No hay recepciones pendientes de ubicación')
    ).toBeInTheDocument();
  });
});
