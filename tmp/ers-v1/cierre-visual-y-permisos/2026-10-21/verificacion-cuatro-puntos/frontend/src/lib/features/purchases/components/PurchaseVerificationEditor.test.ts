import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Purchase } from '$lib/types/purchase';
import PurchaseVerificationEditor from './PurchaseVerificationEditor.svelte';

const mocks = vi.hoisted(() => ({
  verify: vi.fn(),
  listLocations: vi.fn()
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: { verify: mocks.verify }
}));

vi.mock('$lib/features/locations/services', () => ({
  listLocations: mocks.listLocations
}));

const location = {
  id: 'mother-location-1',
  warehouse_id: 'mother-warehouse',
  capacity_group_id: null,
  code: 'MADRE-A-01',
  area: 'A',
  aisle: '01',
  rack: 'R1',
  level: '',
  position: '',
  certified_max_weight_kg: null,
  operational_max_weight_kg: null,
  certified_usable_volume_m3: null,
  operational_usable_volume_m3: null,
  capacity_profile: 'general_mixed',
  capacity_enforcement_mode: 'disabled',
  capacity_status: 'not_configured',
  storage_eligible: true,
  usable_length_m: null,
  usable_width_m: null,
  usable_height_m: null,
  notes: null,
  location_type: 'standard',
  lifecycle_status: 'active',
  barcode: null,
  verification_code: null,
  pick_sequence: null,
  putaway_sequence: null,
  external_id: null,
  scheme_id: null,
  scheme_version: null,
  code_source: 'generated',
  is_active: true,
  created_at: '2026-10-06T12:00:00Z',
  updated_at: null
} as const;

const purchase: Purchase = {
  id: 'purchase-1',
  company_id: 'company-1',
  code: 'COM-0001',
  purchase_order_id: 'order-1',
  supplier_id: 5,
  branch_id: 'branch-1',
  warehouse_id: 'mother-warehouse',
  created_by_id: 'user-1',
  purchase_date: '2026-10-06T12:00:00Z',
  supplier_invoice_number: null,
  supplier_invoice_date: null,
  currency: 'USD',
  details: [
    {
      id: 'purchase-detail-1',
      purchase_id: 'purchase-1',
      purchase_order_detail_id: 'order-detail-1',
      product_id: 10,
      quantity_ordered: '2.000000',
      quantity_received: '2.000000',
      quantity_accepted: null,
      quantity_rejected: null,
      unit_id: 3,
      inventory_location_id: null,
      unit_price: '1.000000',
      discount: '0.000000',
      subtotal: '2.00',
      tax_rate: '0.000000',
      tax_amount: '0.00',
      total: '2.00',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '2.00',
  discount: '0.00',
  tax: '0.00',
  total: '2.00',
  status: 'received',
  inventory_movement_id: null,
  notes: null,
  created_at: null,
  updated_at: null
};

describe('PurchaseVerificationEditor', () => {
  beforeEach(() => {
    mocks.verify.mockReset().mockResolvedValue(purchase);
    mocks.listLocations.mockReset().mockResolvedValue({
      items: [location],
      meta: { page: 1, size: 200, total: 1, pages: 1 }
    });
  });

  it('splits accepted receipt quantities into independent handling units', async () => {
    render(PurchaseVerificationEditor, {
      props: {
        purchase,
        productLabels: new Map([[10, 'Harina de trigo']]),
        unitLabels: new Map([[3, 'Caja']]),
        onupdated: vi.fn(),
        oncancel: vi.fn()
      }
    });

    const firstQuantity = await screen.findByRole('spinbutton', {
      name: /Unidad separada 1 · cantidad aceptada/
    });
    await fireEvent.input(firstQuantity, { target: { value: '1.25' } });
    await fireEvent.click(screen.getByRole('button', { name: '+ Agregar unidad separada' }));

    const secondQuantity = screen.getByRole('spinbutton', {
      name: /Unidad separada 2 · cantidad aceptada/
    });
    await fireEvent.input(secondQuantity, { target: { value: '0.5' } });

    const mapButtons = screen.getAllByRole('button', { name: 'Elegir en el mapa' });
    const firstMapButton = mapButtons.at(0);
    if (!firstMapButton) throw new Error('No se encontró el mapa de la primera unidad.');
    await fireEvent.click(firstMapButton);
    const firstPicker = screen.getByRole('region', { name: /Mapa de ubicaciones para Harina/ });
    await fireEvent.click(within(firstPicker).getByText('Ver lista completa de ubicaciones'));
    await fireEvent.click(
      within(firstPicker).getByRole('button', { name: /Asignar MADRE-A-01.*Harina de trigo/ })
    );

    const secondMapButton = screen.getByRole('button', { name: 'Elegir en el mapa' });
    await fireEvent.click(secondMapButton);
    const secondPicker = screen.getByRole('region', {
      name: /Mapa de ubicaciones para Harina/
    });
    await fireEvent.click(within(secondPicker).getByText('Ver lista completa de ubicaciones'));
    await fireEvent.click(
      within(secondPicker).getByRole('button', { name: /Asignar MADRE-A-01.*Harina de trigo/ })
    );

    const form = screen.getByRole('form', { name: 'Verificar cantidades aceptadas' });
    await fireEvent.submit(form);

    await waitFor(() =>
      expect(mocks.verify).toHaveBeenCalledWith('purchase-1', {
        lines: [
          {
            purchase_detail_id: 'purchase-detail-1',
            quantity_accepted: 1.25,
            inventory_location_id: 'mother-location-1'
          },
          {
            purchase_detail_id: 'purchase-detail-1',
            quantity_accepted: 0.5,
            inventory_location_id: 'mother-location-1'
          }
        ]
      })
    );
  });
});
