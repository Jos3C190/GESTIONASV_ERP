// Review evidence only: copy temporarily to frontend/tests/unit to run.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HandlingUnitLabelDialog from '$lib/features/inventory/components/HandlingUnitLabelDialog.svelte';
import HandlingUnitsPanel from '$lib/features/inventory/components/HandlingUnitsPanel.svelte';
import type { HandlingUnit } from '$lib/features/inventory/types';

const api = vi.hoisted(() => ({
  listHandlingUnits: vi.fn(),
  verifyHandlingUnitMeasurements: vi.fn(),
  createTraceCapability: vi.fn(),
  previewInventoryLabel: vi.fn(),
  confirmInventoryLabelPlacement: vi.fn()
}));
const locations = vi.hoisted(() => ({ listLocations: vi.fn() }));
vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: api }));
vi.mock('$lib/features/locations/services', () => locations);
vi.mock('jsbarcode', () => ({ default: vi.fn() }));
vi.mock('qrcode', () => ({ default: { toDataURL: vi.fn(async () => 'data:image/png;base64,TEST') } }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function unit(id: string, code: string): HandlingUnit {
  return {
    id, code, company_id: 'company-1', warehouse_id: 'warehouse-1',
    location_id: 'location-1', inventory_item_id: 'item-1',
    packaging_definition_id: null, lot_code: null, expiry_date: null,
    quantity_base: 10, actual_gross_weight_kg: null, actual_length_m: null,
    actual_width_m: null, actual_height_m: null, actual_volume_m3: null,
    occupied_weight_kg: null, occupied_volume_m3: null,
    stock_status: 'quarantine', measurement_status: 'incomplete',
    measurement_source: 'receipt', closed_at: null,
    created_at: '2026-10-15T12:00:00Z', updated_at: null
  };
}

function preview(id: string, code: string, product: string) {
  return {
    handling_unit_id: id, handling_unit_code: code,
    inventory_lot_id: `lot-${id}`, inventory_lot_detail_id: `detail-${id}`,
    inventory_item_id: `item-${id}`, product_internal_code: `PRD-${id}`,
    product_name: product, receipt_lot_code: `LOT-${id}`,
    manufacturer_lot_code: null, received_on: '2026-10-15',
    quantity_base: '10', base_unit_symbol: 'u', expiry_date: null,
    stock_status: 'quarantine', print_count: 1, has_initial_print: true,
    label_revision: 1, label_print_id: `print-${id}`,
    label_confirmation_required: true, label_confirmed: false,
    presentation_equivalence: null
  };
}

const locationPage = {
  items: [{ id: 'location-1', code: 'LOC-1', is_active: true,
    storage_eligible: true, lifecycle_status: 'active' }],
  meta: { page: 1, size: 100, total: 1, pages: 1 }
};

describe('Block 4 independent correction review', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.createTraceCapability.mockResolvedValue({ token: 'r'.repeat(43) });
    locations.listLocations.mockResolvedValue(locationPage);
  });

  it('keeps unit B preview when confirmation for closed unit A resolves late', async () => {
    const confirmation = deferred<unknown>();
    const onconfirmed = vi.fn();
    api.confirmInventoryLabelPlacement.mockReturnValueOnce(confirmation.promise);
    api.previewInventoryLabel
      .mockResolvedValueOnce(preview('A', 'HU-A', 'Producto A'))
      .mockResolvedValueOnce(preview('B', 'HU-B', 'Producto B'));
    const view = render(HandlingUnitLabelDialog, {
      props: { unit: unit('A', 'HU-A'), canVerify: true, onconfirmed }
    });
    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar etiqueta colocada' }));
    expect(api.confirmInventoryLabelPlacement).toHaveBeenCalledOnce();
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar código QR' }));
    await view.rerender({ unit: unit('B', 'HU-B'), canVerify: true, onconfirmed });
    await screen.findByText('Producto B');
    confirmation.resolve({ handling_unit_id: 'A' });
    await waitFor(() => expect(onconfirmed).toHaveBeenCalledWith('A'));
    expect({
      qrBelongsToB: Boolean(screen.queryByRole('img', { name: 'Código QR para HU-B' })),
      productA: Boolean(screen.queryByText('Producto A')),
      productB: Boolean(screen.queryByText('Producto B')),
      confirmationShown: Boolean(screen.queryByText('Etiqueta vigente confirmada como colocada.'))
    }).toEqual({ qrBelongsToB: true, productA: false, productB: true, confirmationShown: false });
  });

  it('keeps successful measurement after an older list completes its locations request', async () => {
    const pending = unit('A', 'HU-A');
    const verified = { ...pending, measurement_status: 'verified' as const,
      measurement_source: 'manual' as const, occupied_weight_kg: 8, occupied_volume_m3: 0.2 };
    const measurement = deferred<HandlingUnit>();
    const delayedLocations = deferred<typeof locationPage>();
    api.listHandlingUnits.mockResolvedValue([pending]);
    api.verifyHandlingUnitMeasurements.mockReturnValueOnce(measurement.promise);
    render(HandlingUnitsPanel, { props: { warehouseId: 'warehouse-1', canVerify: true } });
    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-A' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);
    expect(api.verifyHandlingUnitMeasurements).toHaveBeenCalledOnce();
    locations.listLocations.mockReturnValueOnce(delayedLocations.promise);
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(api.listHandlingUnits).toHaveBeenCalledTimes(2));
    measurement.resolve(verified);
    await screen.findByText('Medidas de HU-A verificadas correctamente.');
    delayedLocations.resolve(locationPage);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Actualizar' })).toBeEnabled());
    expect({
      verified: Boolean(screen.queryByText('Medición verificada')),
      pending: Boolean(screen.queryByText('Medición pendiente'))
    }).toEqual({ verified: true, pending: false });
  });
});
