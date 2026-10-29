import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import QRCode from 'qrcode';
import { confirmation } from '$lib/stores/confirmation.svelte';
import type { HandlingUnit } from '$lib/features/inventory/types';
import HandlingUnitLabelDialog from '$lib/features/inventory/components/HandlingUnitLabelDialog.svelte';
import HandlingUnitsPanel from '$lib/features/inventory/components/HandlingUnitsPanel.svelte';

const inventoryMocks = vi.hoisted(() => ({
  listHandlingUnits: vi.fn(),
  listReceiptLots: vi.fn(),
  confirmPutawayGroup: vi.fn(),
  verifyHandlingUnitMeasurements: vi.fn(),
  releaseHandlingUnit: vi.fn(),
  transferHandlingUnit: vi.fn(),
  prepareHandlingUnitSplit: vi.fn(),
  createTraceCapability: vi.fn(),
  revokeTraceCapabilities: vi.fn(),
  previewInventoryLabel: vi.fn(),
  recordInventoryLabelPrint: vi.fn(),
  confirmInventoryLabelPlacement: vi.fn()
}));

const locationMocks = vi.hoisted(() => ({
  listLocations: vi.fn()
}));

const warehouseMocks = vi.hoisted(() => ({
  getWarehouses: vi.fn()
}));

vi.mock('$lib/features/inventory/services', () => ({
  inventoryApi: inventoryMocks
}));
vi.mock('jsbarcode', () => ({ default: vi.fn() }));

vi.mock('$lib/features/locations/services', () => locationMocks);
vi.mock('$lib/services/warehouses', () => warehouseMocks);

function handlingUnit(overrides: Partial<HandlingUnit> = {}): HandlingUnit {
  return {
    id: 'hu-1',
    company_id: 'company-1',
    warehouse_id: 'warehouse-1',
    location_id: 'location-2',
    inventory_item_id: 'item-1',
    packaging_definition_id: null,
    code: 'HU-0001',
    lot_code: 'LOTE-A',
    expiry_date: '2027-01-15',
    quantity_base: 12,
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
    created_at: '2026-08-19T12:00:00Z',
    updated_at: null,
    ...overrides
  };
}

function locationPage(id: string, code: string, page: number, pages: number) {
  return {
    items: [{ id, code }],
    meta: { page, size: 100, total: pages, pages }
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function inventoryLabelPreview(unit: HandlingUnit) {
  return {
    inventory_lot_id: `lot-${unit.id}`,
    inventory_lot_detail_id: `detail-${unit.id}`,
    handling_unit_id: unit.id,
    handling_unit_code: unit.code,
    inventory_item_id: unit.inventory_item_id,
    product_internal_code: `PRD-${unit.id}`,
    product_name: `Producto ${unit.code}`,
    receipt_lot_code: `LOTE-${unit.code}`,
    manufacturer_lot_code: null,
    received_on: '2026-10-15',
    quantity_base: '10',
    base_unit_symbol: 'unidad',
    expiry_date: null,
    stock_status: 'quarantine',
    print_count: 1,
    has_initial_print: true,
    label_revision: 1,
    label_print_id: `print-${unit.id}`,
    label_confirmation_required: true,
    label_confirmed: false,
    presentation_equivalence: null
  };
}

describe('HandlingUnitsPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    confirmation.reset();
    inventoryMocks.listHandlingUnits.mockResolvedValue([handlingUnit()]);
    inventoryMocks.listReceiptLots.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });
    inventoryMocks.confirmPutawayGroup.mockResolvedValue({ allocations: [] });
    inventoryMocks.releaseHandlingUnit.mockResolvedValue(undefined);
    inventoryMocks.transferHandlingUnit.mockResolvedValue(undefined);
    inventoryMocks.createTraceCapability.mockResolvedValue({
      token: 'r'.repeat(43),
      created_at: '2026-10-14T10:00:00Z'
    });
    warehouseMocks.getWarehouses.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 100, total: 0, pages: 0 }
    });
    locationMocks.listLocations
      .mockResolvedValueOnce(locationPage('location-1', 'REC-A-01', 1, 2))
      .mockResolvedValueOnce(locationPage('location-2', 'CAL-A-02', 2, 2));
  });

  it('review: la revocación tardía de A conserva el QR y la ficha de B', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const revokeA = deferred<{ revoked_count: number }>();
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(handling_unit_id === unitA.id ? unitA : unitB)
    );
    inventoryMocks.revokeTraceCapabilities.mockReturnValueOnce(revokeA.promise);
    const props = { unit: unitA, canVerify: true, contextKey: 'company-A|branch-A' };
    const view = render(HandlingUnitLabelDialog, { props });
    await screen.findByRole('img', { name: 'Código QR para HU-A' });
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenCalledWith('hu-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar código QR' }));
    await view.rerender({ ...props, unit: null });
    await view.rerender({ ...props, unit: unitB });
    await screen.findByRole('img', { name: 'Código QR para HU-B' });
    await screen.findByText('Producto HU-B');
    revokeA.resolve({ revoked_count: 2 });
    await Promise.resolve();
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    await waitFor(() => {
      expect(screen.getByRole('img', { name: 'Código QR para HU-B' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();
      expect(screen.queryByText(/Se invalidaron 2 enlace/)).not.toBeInTheDocument();
    });
  });
});
