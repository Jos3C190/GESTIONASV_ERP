import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import QRCode from 'qrcode';
import { HttpError } from '$lib/api/client';
import { confirmation } from '$lib/stores/confirmation.svelte';
import type { HandlingUnit } from '../types';
import HandlingUnitLabelDialog from './HandlingUnitLabelDialog.svelte';
import HandlingUnitsPanel from './HandlingUnitsPanel.svelte';

const inventoryMocks = vi.hoisted(() => ({
  listHandlingUnits: vi.fn(),
  listReceiptLots: vi.fn(),
  listWarehouseMovements: vi.fn(),
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

const navigationMocks = vi.hoisted(() => ({ goto: vi.fn() }));

const locationMocks = vi.hoisted(() => ({
  listLocations: vi.fn()
}));

vi.mock('../services', () => ({
  inventoryApi: inventoryMocks
}));
vi.mock('jsbarcode', () => ({ default: vi.fn() }));
vi.mock('./LabelPrintPreview.svelte', async () => ({
  default: (await import('../../../../../tests/unit/fixtures/InventoryLabelPreviewStub.svelte'))
    .default
}));
vi.mock('../label-printing', async (original) => ({
  ...(await original<typeof import('../label-printing')>()),
  prepareLabelPrintWindow: vi.fn(async (target: Window, html: string) => {
    target.document.write(html);
  })
}));
vi.mock('$app/navigation', () => navigationMocks);
vi.mock('$lib/features/locations/services', () => locationMocks);

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

async function waitForTrace(code: string) {
  await screen.findByRole('heading', { name: code });
  return screen.findByRole('link', { name: 'Abrir ficha' });
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
  it('identifica el producto y permite cerrar la división y recargar sin crear ramas', async () => {
    inventoryMocks.listHandlingUnits.mockResolvedValue([
      handlingUnit({
        product_name: 'Café Tostado y Molido 1kg',
        product_sku: 'PRD-CAF-011',
        base_unit_name: 'Caja',
        base_unit_symbol: 'cj',
        packaging_name: 'Caja de café',
        packaging_base_quantity: '12',
        lot_code: null,
        receipt_lot_code: 'LOT-COM-00017',
        stock_status: 'available',
        measurement_status: 'verified'
      })
    ]);
    locationMocks.listLocations.mockResolvedValue({ items: [], meta: { pages: 1 } });
    render(HandlingUnitsPanel, { props: { warehouseId: 'warehouse-1', canPrepareSplit: true } });
    expect(await screen.findByText('Café Tostado y Molido 1kg')).toBeInTheDocument();
    expect(screen.getByText('PRD-CAF-011')).toBeInTheDocument();
    expect(screen.getByText('Caja (cj)')).toBeInTheDocument();
    expect(screen.getByText('Recepción: LOT-COM-00017')).toBeInTheDocument();
    expect(screen.getByText(/Presentación de origen: Caja de café/)).toHaveTextContent(
      '12 Caja (cj)'
    );
    expect(screen.getByText('Revisión terminada · disponible para uso')).toBeInTheDocument();
    expect(screen.getByText('Otras acciones').closest('details')).not.toHaveAttribute('open');
    await fireEvent.click(screen.getByText('Otras acciones'));
    // happy-dom does not implement the native details toggle on click.
    screen.getByText('Otras acciones').closest('details')!.open = true;
    await fireEvent.click(screen.getByRole('button', { name: 'Dividir unidad' }));
    expect(screen.getByRole('spinbutton')).toHaveValue(null);
    expect(screen.getByRole('button', { name: 'Confirmar división' })).toBeDisabled();
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar formulario' }));
    expect(screen.queryByRole('form', { name: 'Dividir unidad HU-0001' })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Dividir unidad' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));
    expect(inventoryMocks.prepareHandlingUnitSplit).not.toHaveBeenCalled();
    expect(screen.getAllByText('HU-0001')).toHaveLength(1);
    await fireEvent.input(screen.getByRole('searchbox'), { target: { value: 'Café' } });
    expect(screen.getByText('HU-0001')).toBeInTheDocument();
    await fireEvent.input(screen.getByRole('searchbox'), { target: { value: 'PRD-CAF-011' } });
    expect(screen.getByText('HU-0001')).toBeInTheDocument();
    await fireEvent.input(screen.getByRole('searchbox'), { target: { value: 'LOT-COM-00017' } });
    expect(screen.getByText('HU-0001')).toBeInTheDocument();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    navigationMocks.goto.mockResolvedValue(undefined);
    confirmation.reset();
    inventoryMocks.listHandlingUnits.mockResolvedValue([handlingUnit()]);
    inventoryMocks.listReceiptLots.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });
    inventoryMocks.listWarehouseMovements.mockResolvedValue([]);
    inventoryMocks.confirmPutawayGroup.mockResolvedValue({ allocations: [] });
    inventoryMocks.releaseHandlingUnit.mockResolvedValue(undefined);
    inventoryMocks.transferHandlingUnit.mockResolvedValue(undefined);
    inventoryMocks.createTraceCapability.mockResolvedValue({
      token: 'r'.repeat(43),
      created_at: '2026-10-14T10:00:00Z'
    });
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(
        handlingUnit({
          id: handling_unit_id,
          code: handling_unit_id === 'hu-1' ? 'HU-0001' : handling_unit_id
        })
      )
    );
    locationMocks.listLocations
      .mockResolvedValueOnce(locationPage('location-1', 'REC-A-01', 1, 2))
      .mockResolvedValueOnce(locationPage('location-2', 'CAL-A-02', 2, 2));
  });

  it('resuelve ubicaciones paginadas y conserva las medidas desconocidas como Sin medir', async () => {
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    expect(await screen.findByText('HU-0001')).toBeInTheDocument();
    expect(screen.getAllByRole('columnheader')).toHaveLength(8);
    expect(screen.getAllByText('CAL-A-02')).toHaveLength(2);
    expect(screen.getAllByText('Sin medir')).toHaveLength(2);
    expect(screen.getByText('Fabricante: LOTE-A')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ver QR de HU-0001' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verificar medidas' })).not.toBeInTheDocument();
    expect(locationMocks.listLocations).toHaveBeenNthCalledWith(1, 'warehouse-1', {
      page: 1,
      size: 100
    });
    expect(locationMocks.listLocations).toHaveBeenNthCalledWith(2, 'warehouse-1', {
      page: 2,
      size: 100
    });
  });

  it('abre las acciones de medición al llegar con una unidad seleccionada desde recepción', async () => {
    render(HandlingUnitsPanel, {
      props: {
        warehouseId: 'warehouse-1',
        focusHandlingUnitId: 'hu-1',
        canVerify: true
      }
    });

    expect(
      await screen.findByRole('form', { name: 'Verificar medidas de HU-0001' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ver QR de HU-0001' })).toBeInTheDocument();
  });

  it('genera un QR individual y abre la ficha en una pestaña nueva', async () => {
    const qrSpy = vi.spyOn(QRCode, 'toDataURL');
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));

    const qrImage = await screen.findByRole('img', { name: 'Código QR para HU-0001' });
    expect(qrImage).toHaveAttribute('src', expect.stringMatching(/^data:image\/png;base64,/));
    expect(qrSpy).toHaveBeenCalledWith(
      new URL(`/inventory/trace#${'r'.repeat(43)}`, window.location.origin).toString(),
      expect.objectContaining({ width: 512, margin: 4, errorCorrectionLevel: 'M' })
    );
    const openTraceLink = screen.getByRole('link', { name: 'Abrir ficha' });
    expect(openTraceLink).toHaveAttribute('href', `/inventory/trace#${'r'.repeat(43)}`);
    expect(openTraceLink).toHaveAttribute('target', '_blank');
    expect(openTraceLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('permite reintentar la generación del QR sin emitir un enlace adicional', async () => {
    const qrSpy = vi
      .spyOn(QRCode, 'toDataURL')
      .mockRejectedValueOnce(new Error('Fallo temporal al dibujar el QR'));
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));
    expect(await screen.findByText('Fallo temporal al dibujar el QR')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar QR' }));
    expect(await screen.findByRole('img', { name: 'Código QR para HU-0001' })).toHaveAttribute(
      'src',
      expect.stringMatching(/^data:image\/png;base64,/)
    );
    expect(qrSpy).toHaveBeenCalledTimes(2);
    expect(inventoryMocks.createTraceCapability).toHaveBeenCalledTimes(1);
    qrSpy.mockRestore();
  });

  it('no cancela el QR pendiente al reintentar la vista previa de impresión', async () => {
    let finishQr!: (value: string) => void;
    const pendingQr = new Promise<string>((resolve) => {
      finishQr = resolve;
    });
    const qrSpy = vi.spyOn(QRCode, 'toDataURL');
    qrSpy.mockReturnValueOnce(pendingQr as never);
    inventoryMocks.previewInventoryLabel
      .mockRejectedValueOnce(new Error('Fallo temporal de vista previa'))
      .mockResolvedValueOnce({
        inventory_lot_id: 'lot-1',
        inventory_lot_detail_id: 'lot-detail-1',
        handling_unit_id: 'hu-1',
        handling_unit_code: 'HU-0001',
        inventory_item_id: 'item-1',
        product_internal_code: 'PRD-0001',
        product_name: 'Producto de prueba',
        receipt_lot_code: 'LOT-COM-001',
        manufacturer_lot_code: null,
        received_on: '2026-10-13',
        quantity_base: '12',
        base_unit_symbol: 'caja',
        expiry_date: null,
        stock_status: 'quarantine',
        print_count: 0,
        has_initial_print: false
      });

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));
    expect(await screen.findByText('Fallo temporal de vista previa')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await screen.findByText('Producto de prueba');
    finishQr('data:image/png;base64,cGVuZGluZy1jb21wbGV0ZQ==');

    expect(await waitForTrace('HU-0001')).toHaveAttribute(
      'href',
      expect.stringContaining('/inventory/trace#')
    );
    expect(screen.getByTitle(/Vista previa de impresión/).getAttribute('srcdoc')).toContain(
      'cGVuZGluZy1jb21wbGV0ZQ=='
    );
    qrSpy.mockRestore();
  });

  it('mantiene disponible el QR cuando la unidad no tiene lote para etiqueta física', async () => {
    inventoryMocks.previewInventoryLabel.mockRejectedValueOnce(
      new HttpError(
        'inventory_label_receipt_lot_required',
        'La unidad existe, pero no está vinculada a un lote de recepción y no puede usarse para imprimir una etiqueta de recepción.',
        409
      )
    );

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));

    expect(await waitForTrace('HU-0001')).toBeInTheDocument();
    expect(
      await screen.findByText(
        'La unidad existe, pero no está vinculada a un lote de recepción y no puede usarse para imprimir una etiqueta de recepción.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument();
  });

  it('sincroniza el estado si el diálogo se cierra de forma nativa', async () => {
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));
    await waitForTrace('HU-0001');

    const dialog = screen.getByRole('dialog', { name: 'HU-0001' });
    await fireEvent(dialog, new Event('close'));

    await waitFor(() => {
      expect(screen.queryByRole('img', { name: 'Código QR para HU-0001' })).not.toBeInTheDocument();
    });
  });

  it('separa el lote de recepción del lote del fabricante en la etiqueta', async () => {
    inventoryMocks.previewInventoryLabel.mockResolvedValueOnce({
      inventory_lot_id: 'lot-1',
      inventory_lot_detail_id: 'lot-detail-1',
      handling_unit_id: 'hu-1',
      handling_unit_code: 'HU-0001',
      inventory_item_id: 'item-1',
      product_internal_code: 'PRD-0001',
      product_name: 'Chocolate de prueba',
      receipt_lot_code: 'LOT-COM-001',
      manufacturer_lot_code: 'FAB-2026-09',
      received_on: '2026-10-13',
      quantity_base: '12.000000',
      base_unit_symbol: 'caja',
      expiry_date: '2027-01-15',
      stock_status: 'quarantine',
      print_count: 0,
      has_initial_print: false
    });
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));

    await waitForTrace('HU-0001');
    const printed = screen.getByTitle(/Vista previa de impresión/).getAttribute('srcdoc');
    expect(printed).toContain('LOT-COM-001');
    expect(printed).toContain('FAB-2026-09');
    expect(printed).toContain('13/10/2026');
    expect(screen.getByRole('button', { name: 'Imprimir etiqueta' })).toBeEnabled();
    expect(inventoryMocks.previewInventoryLabel).toHaveBeenCalledWith({ handling_unit_id: 'hu-1' });
  });

  it('registra reimpresión y exige confirmación expresa aunque termine afterprint', async () => {
    const pendingUnit = handlingUnit({
      measurement_status: 'verified',
      release_requirements: ['label_confirmation_required', 'retaceo_cost_unapplied']
    });
    const currentUnit = handlingUnit({
      measurement_status: 'verified',
      release_requirements: ['retaceo_cost_unapplied']
    });
    inventoryMocks.listHandlingUnits.mockImplementation(async () =>
      inventoryMocks.confirmInventoryLabelPlacement.mock.calls.length > 0
        ? [currentUnit]
        : [pendingUnit]
    );
    inventoryMocks.previewInventoryLabel.mockResolvedValueOnce({
      inventory_lot_id: 'lot-1',
      inventory_lot_detail_id: 'lot-detail-1',
      handling_unit_id: 'hu-1',
      handling_unit_code: 'HU-0001',
      inventory_item_id: 'item-1',
      product_internal_code: 'PRD-0001',
      product_name: 'Producto de prueba',
      receipt_lot_code: 'LOT-COM-001',
      manufacturer_lot_code: null,
      received_on: '2026-10-13',
      quantity_base: '12',
      base_unit_symbol: 'caja',
      expiry_date: null,
      stock_status: 'quarantine',
      print_count: 1,
      has_initial_print: true,
      label_revision: 1,
      label_print_id: 'print-old',
      label_confirmation_required: true,
      label_confirmed: false,
      presentation_equivalence: '1 caja × 12 caja = 12 caja'
    });
    inventoryMocks.recordInventoryLabelPrint.mockResolvedValueOnce({
      id: 'print-1',
      quantity_printed: 1,
      label_snapshot: {
        ...inventoryLabelPreview(handlingUnit()),
        product_internal_code: 'PRD-0001',
        product_name: 'Producto de prueba',
        receipt_lot_code: 'LOT-COM-001',
        quantity_base: '12',
        received_on: '2026-10-13',
        base_unit_symbol: 'caja',
        presentation_equivalence: '1 caja × 12 caja = 12 caja'
      }
    });
    inventoryMocks.confirmInventoryLabelPlacement
      .mockRejectedValueOnce(new Error('Fallo temporal al confirmar la etiqueta'))
      .mockResolvedValueOnce({
        id: 'confirmation-1',
        handling_unit_id: 'hu-1',
        label_print_id: 'print-1',
        handling_unit_code: 'HU-0001',
        label_revision: 1,
        quantity_base: '12',
        label_fingerprint: 'fingerprint',
        confirmed_by: 'user-1',
        confirmed_at: '2026-10-14T10:00:00Z'
      });
    const write = vi.fn();
    const printWindow = {
      opener: null,
      document: { open: vi.fn(), write, close: vi.fn() },
      addEventListener: vi.fn(),
      setTimeout: vi.fn(),
      close: vi.fn()
    } as unknown as Window;
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(printWindow);
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, canRelease: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));
    await waitForTrace('HU-0001');
    await fireEvent.click(await screen.findByRole('button', { name: 'Reimprimir etiqueta' }));

    await waitFor(() =>
      expect(inventoryMocks.recordInventoryLabelPrint).toHaveBeenCalledWith(
        expect.objectContaining({ reason: 'reprint' })
      )
    );
    expect(inventoryMocks.recordInventoryLabelPrint).toHaveBeenCalledOnce();
    const html = write.mock.calls[0]?.[0] as string;
    expect(html).toContain('QR de trazabilidad de la unidad');
    expect(html).toContain('LOT-COM-001');
    expect(html).toContain('1 caja × 12 caja = 12 caja');
    expect(openWindow).toHaveBeenCalledWith('', '_blank', 'width=520,height=640');

    const afterPrintListener = (printWindow.addEventListener as unknown as ReturnType<typeof vi.fn>)
      .mock.calls[0]?.[1] as (() => void) | undefined;
    afterPrintListener?.();
    expect(inventoryMocks.confirmInventoryLabelPlacement).not.toHaveBeenCalled();
    const listCallsBeforeConfirmation = inventoryMocks.listHandlingUnits.mock.calls.length;
    await fireEvent.click(
      await screen.findByRole('button', { name: 'Confirmar etiqueta colocada' })
    );
    expect(await screen.findByText('Fallo temporal al confirmar la etiqueta')).toBeInTheDocument();
    expect(inventoryMocks.listHandlingUnits.mock.calls.length).toBe(listCallsBeforeConfirmation);
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    await waitFor(() =>
      expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenCalledWith(
        expect.objectContaining({
          handling_unit_id: 'hu-1',
          handling_unit_code: 'HU-0001',
          label_print_id: 'print-1'
        })
      )
    );
    expect(
      await screen.findByText('Etiqueta vigente confirmada como colocada.')
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(inventoryMocks.listHandlingUnits.mock.calls.length).toBeGreaterThan(
        listCallsBeforeConfirmation
      )
    );
    expect(
      screen.queryByText(
        'Confirme la impresión y colocación de la etiqueta vigente antes de liberar.'
      )
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/debe aplicar el retaceo al costo antes de liberar/)
    ).toBeInTheDocument();
    openWindow.mockRestore();
  });

  it('aísla confirmaciones tardías por unidad y permite confirmar B mientras A sigue pendiente', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const confirmationA = deferred<unknown>();
    const confirmationB = deferred<unknown>();
    inventoryMocks.listHandlingUnits.mockResolvedValue([unitA, unitB]);
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(handling_unit_id === unitA.id ? unitA : unitB)
    );
    inventoryMocks.confirmInventoryLabelPlacement
      .mockReturnValueOnce(confirmationA.promise)
      .mockReturnValueOnce(confirmationB.promise);

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });

    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-A' }));
    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ handling_unit_id: 'hu-A', label_print_id: 'print-hu-A' })
    );

    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-B' }));
    await screen.findByText('Producto HU-B');
    expect(screen.queryByText('Producto HU-A')).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ handling_unit_id: 'hu-B', label_print_id: 'print-hu-B' })
    );

    confirmationA.resolve({ handling_unit_id: 'hu-A' });
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: 'Confirmando…' })).toBeDisabled();
    expect(screen.getByText('Producto HU-B')).toBeInTheDocument();
    expect(screen.queryByText('Producto HU-A')).not.toBeInTheDocument();

    confirmationB.resolve({ handling_unit_id: 'hu-B' });
    expect(await screen.findByText(/Colocación de etiqueta confirmada/)).toBeInTheDocument();

    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(3));
    expect(screen.getByText('Producto HU-B')).toBeInTheDocument();
    expect(screen.queryByText('Producto HU-A')).not.toBeInTheDocument();
    expect(screen.getByText(/Colocación de etiqueta confirmada/)).toBeInTheDocument();
  });

  it('no muestra el error de confirmación de A en B ni al reabrir la misma unidad', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const confirmationA = deferred<unknown>();
    inventoryMocks.listHandlingUnits.mockResolvedValue([unitA, unitB]);
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(handling_unit_id === unitA.id ? unitA : unitB)
    );
    inventoryMocks.confirmInventoryLabelPlacement.mockReturnValueOnce(confirmationA.promise);

    render(HandlingUnitsPanel, { props: { warehouseId: 'warehouse-1', canVerify: true } });
    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-A' }));
    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    const firstAttemptKey =
      inventoryMocks.confirmInventoryLabelPlacement.mock.calls[0]?.[0].idempotency_key;
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-B' }));
    await screen.findByText('Producto HU-B');

    confirmationA.reject(new Error('Error tardío de HU-A'));
    await waitFor(() =>
      expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenCalledOnce()
    );
    expect(screen.queryByText('Error tardío de HU-A')).not.toBeInTheDocument();
    expect(screen.getByText('Producto HU-B')).toBeInTheDocument();
    expect(screen.queryByText('Producto HU-A')).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-A' }));
    await screen.findByText('Producto HU-A');
    expect(screen.queryByText('Error tardío de HU-A')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' })).toBeEnabled();
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    await waitFor(() =>
      expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenCalledTimes(2)
    );
    expect(inventoryMocks.confirmInventoryLabelPlacement.mock.calls[1]?.[0].idempotency_key).toBe(
      firstAttemptKey
    );
    expect(await screen.findByText(/Colocación de etiqueta confirmada/)).toBeInTheDocument();
  });

  it('ignora el éxito tardío de A después de cerrar y reabrir la misma unidad', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const confirmationA = deferred<unknown>();
    const onconfirmed = vi.fn();
    inventoryMocks.createTraceCapability.mockResolvedValue({ token: 'r'.repeat(43) });
    inventoryMocks.previewInventoryLabel.mockResolvedValue(inventoryLabelPreview(unitA));
    inventoryMocks.confirmInventoryLabelPlacement
      .mockReturnValueOnce(confirmationA.promise)
      .mockResolvedValueOnce({ handling_unit_id: 'hu-A' });
    const props = { unit: unitA, canVerify: true, contextKey: 'company-A|branch-A', onconfirmed };
    const view = render(HandlingUnitLabelDialog, { props });

    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await view.rerender({ ...props, unit: null });
    await view.rerender(props);
    await waitFor(() => expect(inventoryMocks.previewInventoryLabel).toHaveBeenCalledTimes(2));
    await screen.findByText('Producto HU-A');

    confirmationA.resolve({ handling_unit_id: 'hu-A' });
    await waitFor(() => expect(onconfirmed).toHaveBeenCalledWith('hu-A'));
    expect(screen.queryByText(/Colocación de etiqueta confirmada/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' })).toBeEnabled();
  });

  it('inicia una sesión nueva al cambiar el contexto y descarta la confirmación anterior', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const confirmationA = deferred<unknown>();
    const onconfirmed = vi.fn();
    inventoryMocks.createTraceCapability.mockResolvedValue({ token: 'r'.repeat(43) });
    inventoryMocks.previewInventoryLabel.mockResolvedValue(inventoryLabelPreview(unitA));
    inventoryMocks.confirmInventoryLabelPlacement.mockReturnValueOnce(confirmationA.promise);
    const props = { unit: unitA, canVerify: true, contextKey: 'company-A|branch-A', onconfirmed };
    const view = render(HandlingUnitLabelDialog, { props });

    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    await view.rerender({ ...props, contextKey: 'company-B|branch-B' });
    await waitFor(() => expect(inventoryMocks.previewInventoryLabel).toHaveBeenCalledTimes(2));
    await screen.findByText('Producto HU-A');

    confirmationA.resolve({ handling_unit_id: 'hu-A' });
    await waitFor(() =>
      expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenCalledOnce()
    );
    expect(onconfirmed).not.toHaveBeenCalled();
    expect(screen.queryByText(/Colocación de etiqueta confirmada/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' })).toBeEnabled();
  });

  it('imprime solo los datos de B aunque una confirmación previa de A siga pendiente', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const confirmationA = deferred<unknown>();
    inventoryMocks.listHandlingUnits.mockResolvedValue([unitA, unitB]);
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(handling_unit_id === unitA.id ? unitA : unitB)
    );
    inventoryMocks.confirmInventoryLabelPlacement.mockReturnValueOnce(confirmationA.promise);
    inventoryMocks.recordInventoryLabelPrint.mockResolvedValueOnce({
      id: 'print-B-next',
      quantity_printed: 1,
      label_snapshot: inventoryLabelPreview(unitB)
    });
    const write = vi.fn();
    const printWindow = {
      opener: null,
      document: { open: vi.fn(), write, close: vi.fn() },
      addEventListener: vi.fn(),
      setTimeout: vi.fn(),
      close: vi.fn()
    } as unknown as Window;
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(printWindow);

    render(HandlingUnitsPanel, { props: { warehouseId: 'warehouse-1', canVerify: true } });
    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-A' }));
    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));

    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-B' }));
    await screen.findByText('Producto HU-B');
    const printButton = await screen.findByRole('button', {
      name: /Imprimir etiqueta|Reimprimir etiqueta/
    });
    await waitFor(() => expect(printButton).toBeEnabled());
    await fireEvent.click(printButton);
    await waitFor(() => expect(inventoryMocks.recordInventoryLabelPrint).toHaveBeenCalledOnce());
    const html = write.mock.calls[0]?.[0] as string;
    expect(html).toContain('Producto HU-B');
    expect(html).toContain('LOTE-HU-B');
    expect(html).toContain('HU-B');
    expect(html).not.toContain('Producto HU-A');
    expect(html).not.toContain('LOTE-HU-A');

    confirmationA.resolve({ handling_unit_id: 'hu-A' });
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));
    expect(screen.getByText('Producto HU-B')).toBeInTheDocument();
    expect(screen.queryByText('Producto HU-A')).not.toBeInTheDocument();
    openWindow.mockRestore();
  });

  it('no notifica al padre si la confirmación termina después de desmontar el diálogo', async () => {
    const pendingUnit = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const confirmation = deferred<unknown>();
    const onverified = vi.fn();
    inventoryMocks.listHandlingUnits.mockResolvedValue([pendingUnit]);
    inventoryMocks.previewInventoryLabel.mockResolvedValue(inventoryLabelPreview(pendingUnit));
    inventoryMocks.confirmInventoryLabelPlacement.mockReturnValueOnce(confirmation.promise);
    const view = render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, onverified }
    });
    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-A' }));
    await screen.findByText('Producto HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));

    view.unmount();
    confirmation.resolve({ handling_unit_id: 'hu-A' });
    await waitFor(() =>
      expect(inventoryMocks.confirmInventoryLabelPlacement).toHaveBeenCalledOnce()
    );
    expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledOnce();
    expect(onverified).not.toHaveBeenCalled();
  });

  it('refresca la etiqueta al cerrar, conserva filtros y mantiene el bloqueo de retaceo hasta liberar', async () => {
    const pendingUnit = handlingUnit({
      release_requirements: ['label_confirmation_required', 'retaceo_cost_unapplied']
    });
    const measuredUnit = handlingUnit({
      ...pendingUnit,
      actual_gross_weight_kg: 8,
      actual_volume_m3: 0.2,
      occupied_weight_kg: 8,
      occupied_volume_m3: 0.2,
      measurement_status: 'verified',
      measurement_source: 'manual',
      release_requirements: ['label_confirmation_required', 'retaceo_cost_unapplied']
    });
    const labelConfirmedUnit = handlingUnit({
      ...measuredUnit,
      release_requirements: ['retaceo_cost_unapplied']
    });
    const eligibleUnit = handlingUnit({
      ...measuredUnit,
      release_requirements: []
    });
    let measurementSaved = false;
    let labelConfirmed = false;
    let retaceoFinished = false;
    inventoryMocks.listHandlingUnits.mockImplementation(async () => {
      if (!measurementSaved) return [pendingUnit];
      if (!labelConfirmed) return [measuredUnit];
      return [retaceoFinished ? eligibleUnit : labelConfirmedUnit];
    });
    inventoryMocks.verifyHandlingUnitMeasurements.mockImplementation(async () => {
      measurementSaved = true;
      return measuredUnit;
    });
    inventoryMocks.previewInventoryLabel.mockResolvedValue(inventoryLabelPreview(measuredUnit));
    inventoryMocks.recordInventoryLabelPrint.mockResolvedValue({
      id: 'print-hu-1-next',
      quantity_printed: 1,
      label_snapshot: inventoryLabelPreview(measuredUnit)
    });
    inventoryMocks.confirmInventoryLabelPlacement.mockImplementation(async () => {
      labelConfirmed = true;
      return { handling_unit_id: measuredUnit.id };
    });
    locationMocks.listLocations.mockImplementation(async () => ({
      items: [
        {
          id: 'location-2',
          warehouse_id: 'warehouse-1',
          code: 'RACK-01',
          area: 'A',
          aisle: '01',
          rack: 'R1',
          level: '1',
          position: '01',
          is_active: true,
          storage_eligible: true,
          lifecycle_status: 'active'
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    }));
    const printWindow = {
      opener: null,
      document: { open: vi.fn(), write: vi.fn(), close: vi.fn() },
      addEventListener: vi.fn(),
      setTimeout: vi.fn(),
      close: vi.fn()
    } as unknown as Window;
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(printWindow);

    render(HandlingUnitsPanel, {
      props: {
        warehouseId: 'warehouse-1',
        canVerify: true,
        canRelease: true,
        canVerifyRetaceos: true
      }
    });
    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const measurementForm = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(measurementForm).getByLabelText(/Peso bruto/), {
      target: { value: '8' }
    });
    await fireEvent.input(within(measurementForm).getByLabelText(/Volumen/), {
      target: { value: '0.2' }
    });
    await fireEvent.submit(measurementForm);
    expect(
      await screen.findByText('Medidas de HU-0001 verificadas correctamente.')
    ).toBeInTheDocument();

    await fireEvent.input(
      screen.getByLabelText('Buscar por producto, SKU, código, lote o ubicación'),
      {
        target: { value: 'HU-0001' }
      }
    );
    await fireEvent.change(screen.getByLabelText('Ubicación'), {
      target: { value: 'location-2' }
    });
    await fireEvent.change(screen.getByLabelText('Estado de existencia'), {
      target: { value: 'quarantine' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Revisar etiqueta' }));
    await screen.findByText('Producto HU-0001');
    const printButton = await screen.findByRole('button', {
      name: /Imprimir etiqueta|Reimprimir etiqueta/
    });
    await waitFor(() => expect(printButton).toBeEnabled());
    await fireEvent.click(printButton);
    await waitFor(() => expect(inventoryMocks.recordInventoryLabelPrint).toHaveBeenCalledOnce());
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar etiqueta colocada' }));
    expect(await screen.findByText(/Colocación de etiqueta confirmada/)).toBeInTheDocument();
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));

    expect(screen.getByLabelText('Buscar por producto, SKU, código, lote o ubicación')).toHaveValue(
      'HU-0001'
    );
    expect(screen.getByLabelText('Ubicación')).toHaveValue('location-2');
    expect(screen.getByLabelText('Estado de existencia')).toHaveValue('quarantine');
    expect(
      await screen.findByText(
        'Aplique el retaceo verificado al costo del inventario antes de liberar.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Liberar a disponible' })).not.toBeInTheDocument();

    retaceoFinished = true;
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(await screen.findByRole('button', { name: 'Liberar a disponible' })).toBeEnabled();
    await fireEvent.click(screen.getByRole('button', { name: 'Liberar a disponible' }));
    expect(confirmation.current?.kind).toBe('release');
    await confirmation.proceed();
    await waitFor(() =>
      expect(inventoryMocks.releaseHandlingUnit).toHaveBeenCalledWith(
        eligibleUnit,
        'location-2',
        expect.any(String)
      )
    );
    expect(await screen.findByText('HU-0001 quedó disponible en inventario.')).toBeInTheDocument();
    openWindow.mockRestore();
  });

  it('conserva la medición del servidor frente a un listado anterior con ubicaciones demoradas', async () => {
    const pendingUnit = handlingUnit({
      release_requirements: ['label_confirmation_required', 'retaceo_cost_unapplied']
    });
    const verifiedUnit = handlingUnit({
      ...pendingUnit,
      actual_gross_weight_kg: 8,
      actual_volume_m3: 0.2,
      occupied_weight_kg: 8,
      occupied_volume_m3: 0.2,
      measurement_status: 'verified',
      measurement_source: 'manual',
      release_requirements: ['label_confirmation_required', 'retaceo_cost_unapplied']
    });
    const measurement = deferred<HandlingUnit>();
    const delayedLocations = deferred<ReturnType<typeof locationPage>>();
    inventoryMocks.listHandlingUnits
      .mockResolvedValueOnce([pendingUnit])
      .mockResolvedValueOnce([pendingUnit])
      .mockResolvedValueOnce([verifiedUnit]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockReturnValueOnce(measurement.promise);
    locationMocks.listLocations.mockReset();
    locationMocks.listLocations.mockImplementation(async () =>
      locationPage('location-2', 'RACK-01', 1, 1)
    );

    render(HandlingUnitsPanel, {
      props: {
        warehouseId: 'warehouse-1',
        canVerify: true,
        canRelease: true,
        canVerifyRetaceos: true
      }
    });
    await screen.findByText('HU-0001');
    await waitFor(() => expect(locationMocks.listLocations).toHaveBeenCalledTimes(2));
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);

    locationMocks.listLocations.mockReturnValueOnce(delayedLocations.promise);
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));
    measurement.resolve(verifiedUnit);
    expect(
      await screen.findByText('Medidas de HU-0001 verificadas correctamente.')
    ).toBeInTheDocument();
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(3));
    delayedLocations.resolve(locationPage('location-2', 'RACK-01', 1, 1));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Actualizar' })).toBeEnabled();
      expect(screen.getByText('Medición verificada')).toBeInTheDocument();
    });
    expect(screen.queryByText('Medición pendiente')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Confirme la impresión y colocación de la etiqueta vigente/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Aplique el retaceo verificado al costo del inventario/)
    ).toBeInTheDocument();
  });

  it('descarta una medición de otro contexto sin limpiar la operación nueva', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const measurementA = deferred<HandlingUnit>();
    const measurementB = deferred<HandlingUnit>();
    const onverified = vi.fn();
    inventoryMocks.listHandlingUnits.mockImplementation(async (warehouseId: string) =>
      warehouseId === 'warehouse-A' ? [unitA] : [unitB]
    );
    locationMocks.listLocations.mockImplementation(async (warehouseId: string) =>
      locationPage(
        warehouseId === 'warehouse-A' ? 'location-A' : 'location-B',
        warehouseId === 'warehouse-A' ? 'RACK-A' : 'RACK-B',
        1,
        1
      )
    );
    inventoryMocks.verifyHandlingUnitMeasurements
      .mockReturnValueOnce(measurementA.promise)
      .mockReturnValueOnce(measurementB.promise);
    const view = render(HandlingUnitsPanel, {
      props: {
        warehouseId: 'warehouse-A',
        contextKey: 'company-A|branch-A|inventory:receive',
        canVerify: true,
        onverified
      }
    });

    await screen.findByText('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    let form = screen.getByRole('form', { name: 'Verificar medidas de HU-A' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);

    await view.rerender({
      warehouseId: 'warehouse-B',
      contextKey: 'company-B|branch-B|inventory:receive',
      canVerify: true,
      onverified
    });
    await screen.findByText('HU-B');
    expect(screen.queryByText('HU-A')).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    form = screen.getByRole('form', { name: 'Verificar medidas de HU-B' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '9' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.3' } });
    await fireEvent.submit(form);

    measurementA.resolve({
      ...unitA,
      measurement_status: 'verified',
      measurement_source: 'manual',
      actual_gross_weight_kg: 8,
      actual_volume_m3: 0.2
    });
    await waitFor(() => expect(onverified).not.toHaveBeenCalled());
    expect(
      screen.queryByText('Medidas de HU-A verificadas correctamente.')
    ).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Verificando…' })).toBeDisabled();

    measurementB.resolve({
      ...unitB,
      measurement_status: 'verified',
      measurement_source: 'manual',
      actual_gross_weight_kg: 9,
      actual_volume_m3: 0.3
    });
    expect(
      await screen.findByText('Medidas de HU-B verificadas correctamente.')
    ).toBeInTheDocument();
    expect(onverified).toHaveBeenCalledOnce();
  });

  it('conserva la medición si la recarga posterior falla y termina el estado de carga', async () => {
    const pendingUnit = handlingUnit();
    const verifiedUnit = handlingUnit({
      actual_gross_weight_kg: 8,
      actual_volume_m3: 0.2,
      occupied_weight_kg: 8,
      occupied_volume_m3: 0.2,
      measurement_status: 'verified',
      measurement_source: 'manual'
    });
    const measurement = deferred<HandlingUnit>();
    const oldLocations = deferred<ReturnType<typeof locationPage>>();
    inventoryMocks.listHandlingUnits
      .mockResolvedValueOnce([pendingUnit])
      .mockResolvedValueOnce([pendingUnit])
      .mockRejectedValueOnce(new Error('Fallo de la recarga actual'));
    inventoryMocks.verifyHandlingUnitMeasurements.mockReturnValueOnce(measurement.promise);
    locationMocks.listLocations.mockReset();
    locationMocks.listLocations.mockImplementation(async () =>
      locationPage('location-2', 'RACK-01', 1, 1)
    );

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });
    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);
    locationMocks.listLocations
      .mockReturnValueOnce(oldLocations.promise)
      .mockResolvedValueOnce(locationPage('location-2', 'RACK-01', 1, 1));
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(inventoryMocks.listHandlingUnits).toHaveBeenCalledTimes(2));

    measurement.resolve(verifiedUnit);
    expect(await screen.findByText('Fallo de la recarga actual')).toBeInTheDocument();
    oldLocations.resolve(locationPage('location-2', 'RACK-01', 1, 1));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Actualizar' })).toBeEnabled();
      expect(screen.getByText('Medición verificada')).toBeInTheDocument();
    });
    expect(screen.getByText('HU-0001')).toBeInTheDocument();
  });

  it('no ejecuta callback de medición después de desmontar el panel', async () => {
    const pendingUnit = handlingUnit();
    const measurement = deferred<HandlingUnit>();
    const onverified = vi.fn();
    inventoryMocks.listHandlingUnits.mockResolvedValue([pendingUnit]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockReturnValueOnce(measurement.promise);
    const view = render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, onverified }
    });
    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);

    view.unmount();
    measurement.resolve({
      ...pendingUnit,
      measurement_status: 'verified',
      measurement_source: 'manual',
      actual_gross_weight_kg: 8,
      actual_volume_m3: 0.2
    });
    await waitFor(() =>
      expect(inventoryMocks.verifyHandlingUnitMeasurements).toHaveBeenCalledOnce()
    );
    expect(onverified).not.toHaveBeenCalled();
  });

  it('permite invalidar todos los enlaces públicos de una unidad', async () => {
    inventoryMocks.revokeTraceCapabilities.mockResolvedValueOnce({ revoked_count: 2 });
    inventoryMocks.previewInventoryLabel.mockResolvedValueOnce({
      inventory_lot_id: 'lot-1',
      inventory_lot_detail_id: 'lot-detail-1',
      handling_unit_id: 'hu-1',
      handling_unit_code: 'HU-0001',
      inventory_item_id: 'item-1',
      product_internal_code: 'PRD-0001',
      product_name: 'Producto de prueba',
      receipt_lot_code: 'LOT-COM-001',
      manufacturer_lot_code: null,
      received_on: '2026-10-13',
      quantity_base: '12',
      base_unit_symbol: 'caja',
      expiry_date: null,
      stock_status: 'quarantine',
      print_count: 0,
      has_initial_print: false
    });
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Ver QR de HU-0001' }));
    await waitForTrace('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));

    await waitFor(() =>
      expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenCalledWith('hu-1')
    );
    expect(await screen.findByText(/Se invalidaron 2 enlace\(s\) QR/)).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Código QR para HU-0001' })).not.toBeInTheDocument();
  });

  it('aísla revocaciones tardías de A y permite invalidar B mientras A sigue pendiente', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const unitB = handlingUnit({ id: 'hu-B', code: 'HU-B' });
    const revokeA = deferred<{ revoked_count: number }>();
    const revokeB = deferred<{ revoked_count: number }>();
    inventoryMocks.previewInventoryLabel.mockImplementation(async ({ handling_unit_id }) =>
      inventoryLabelPreview(handling_unit_id === unitA.id ? unitA : unitB)
    );
    inventoryMocks.revokeTraceCapabilities
      .mockReturnValueOnce(revokeA.promise)
      .mockReturnValueOnce(revokeB.promise);
    inventoryMocks.createTraceCapability
      .mockResolvedValueOnce({ token: 'a'.repeat(43) })
      .mockResolvedValueOnce({ token: 'b'.repeat(43) });
    const props = { unit: unitA, canVerify: true, contextKey: 'company-A|branch-A' };
    const view = render(HandlingUnitLabelDialog, { props });

    await waitForTrace('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenNthCalledWith(1, 'hu-A');

    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await view.rerender({ ...props, unit: null });
    await view.rerender({ ...props, unit: unitB });
    await waitForTrace('HU-B');
    await screen.findByText('Producto HU-B');
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenNthCalledWith(2, 'hu-B');
    expect(screen.getByRole('button', { name: 'Invalidando…' })).toBeDisabled();

    revokeA.resolve({ revoked_count: 2 });
    await Promise.resolve();
    expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();
    expect(screen.queryByText(/Se invalidaron 2 enlace/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Invalidando…' })).toBeDisabled();

    revokeB.resolve({ revoked_count: 3 });
    expect(await screen.findByText(/Se invalidaron 3 enlace/)).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Código QR para HU-B' })).not.toBeInTheDocument();
  });

  it('ignora error de revocación tras reabrir la misma unidad o cambiar contexto', async () => {
    const unitA = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const revokeAfterReopen = deferred<{ revoked_count: number }>();
    const revokeAfterContextChange = deferred<{ revoked_count: number }>();
    const revokeAfterPermissionChange = deferred<{ revoked_count: number }>();
    inventoryMocks.revokeTraceCapabilities
      .mockReturnValueOnce(revokeAfterReopen.promise)
      .mockReturnValueOnce(revokeAfterContextChange.promise)
      .mockReturnValueOnce(revokeAfterPermissionChange.promise);
    const props = { unit: unitA, canVerify: true, contextKey: 'company-A|branch-A' };
    const view = render(HandlingUnitLabelDialog, { props });

    await waitForTrace('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar etiqueta de inventario' }));
    await view.rerender({ ...props, unit: null });
    await view.rerender(props);
    await waitForTrace('HU-A');
    revokeAfterReopen.reject(new Error('Error de sesión anterior'));
    await Promise.resolve();
    expect(screen.queryByText('Error de sesión anterior')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    await view.rerender({ ...props, contextKey: 'company-B|branch-B' });
    await waitForTrace('HU-A');
    revokeAfterContextChange.reject(new Error('Error de contexto anterior'));
    await Promise.resolve();
    expect(screen.queryByText('Error de contexto anterior')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    await view.rerender({
      ...props,
      canVerify: false,
      contextKey: 'company-B|branch-B|inventory:read-only'
    });
    await waitForTrace('HU-A');
    revokeAfterPermissionChange.reject(new Error('Error de permiso anterior'));
    await Promise.resolve();
    expect(screen.queryByText('Error de permiso anterior')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir ficha' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Invalidar enlaces públicos' })
    ).not.toBeInTheDocument();
  });

  it('ignora una respuesta de revocación posterior al desmontaje', async () => {
    const pendingUnit = handlingUnit({ id: 'hu-A', code: 'HU-A' });
    const revocation = deferred<{ revoked_count: number }>();
    inventoryMocks.revokeTraceCapabilities.mockReturnValueOnce(revocation.promise);
    const view = render(HandlingUnitLabelDialog, {
      props: { unit: pendingUnit, canVerify: true, contextKey: 'company-A|branch-A' }
    });

    await waitForTrace('HU-A');
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces' }));
    expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenCalledWith('hu-A');
    view.unmount();
    revocation.resolve({ revoked_count: 1 });
    await Promise.resolve();
    expect(inventoryMocks.revokeTraceCapabilities).toHaveBeenCalledOnce();
  });

  it('filtra por código y por estado sin convertir los datos físicos', async () => {
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([
      handlingUnit(),
      handlingUnit({
        id: 'hu-2',
        code: 'HU-0002',
        lot_code: 'LOTE-B',
        location_id: 'location-1',
        stock_status: 'available',
        measurement_status: 'verified',
        measurement_source: 'manual',
        occupied_weight_kg: 25,
        occupied_volume_m3: 0.5
      })
    ]);

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    expect(await screen.findByText('HU-0002')).toBeInTheDocument();
    await fireEvent.input(
      screen.getByLabelText('Buscar por producto, SKU, código, lote o ubicación'),
      {
        target: { value: 'LOTE-A' }
      }
    );
    await waitFor(() => {
      expect(screen.getByText('HU-0001')).toBeInTheDocument();
      expect(screen.queryByText('HU-0002')).not.toBeInTheDocument();
    });

    await fireEvent.input(
      screen.getByLabelText('Buscar por producto, SKU, código, lote o ubicación'),
      {
        target: { value: '' }
      }
    );
    await fireEvent.change(screen.getByLabelText('Estado de existencia'), {
      target: { value: 'available' }
    });
    await waitFor(() => {
      expect(screen.getByText('HU-0002')).toBeInTheDocument();
      expect(screen.queryByText('HU-0001')).not.toBeInTheDocument();
    });
  });

  it('verifica por dimensiones solo una unidad incompleta en cuarentena con permiso de recepción', async () => {
    const onverified = vi.fn();
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([
      handlingUnit(),
      handlingUnit({
        id: 'hu-available',
        code: 'HU-AVAILABLE',
        stock_status: 'available'
      })
    ]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockResolvedValueOnce(
      handlingUnit({
        actual_gross_weight_kg: 18.5,
        actual_length_m: 0.8,
        actual_width_m: 0.5,
        actual_height_m: 0.4,
        actual_volume_m3: 0.16,
        occupied_weight_kg: 18.5,
        occupied_volume_m3: 0.16,
        measurement_status: 'verified',
        measurement_source: 'manual'
      })
    );

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, onverified }
    });

    const verifyButton = await screen.findByRole('button', { name: 'Verificar medidas' });
    expect(screen.getAllByRole('button', { name: 'Verificar medidas' })).toHaveLength(1);
    await fireEvent.click(verifyButton);

    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), {
      target: { value: '18.5' }
    });
    await fireEvent.change(within(form).getByLabelText(/Método de volumen/), {
      target: { value: 'dimensions' }
    });
    const lengthInput = await within(form).findByLabelText(/Largo/);
    await fireEvent.input(lengthInput, {
      target: { value: '0.8' }
    });
    await fireEvent.input(within(form).getByLabelText(/Ancho/), {
      target: { value: '0.5' }
    });
    await fireEvent.input(within(form).getByLabelText(/Alto/), {
      target: { value: '0.4' }
    });
    await fireEvent.submit(form);

    await waitFor(() =>
      expect(inventoryMocks.verifyHandlingUnitMeasurements).toHaveBeenCalledWith(
        'hu-1',
        {
          gross_weight_kg: 18.5,
          volume_m3: null,
          length_m: 0.8,
          width_m: 0.5,
          height_m: 0.4
        },
        'manual'
      )
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Medidas de HU-0001 verificadas correctamente.'
    );
    expect(screen.getByText('18.5 kg')).toBeInTheDocument();
    expect(screen.getByText('0.16 m³')).toBeInTheDocument();
    expect(onverified).toHaveBeenCalledOnce();
  });

  it('permite verificar tanto la fracción como el remanente con medidas estimadas', async () => {
    const split = handlingUnit({
      id: 'hu-split',
      code: 'HU-FRACCION',
      quantity_base: 4,
      measurement_status: 'complete',
      measurement_source: 'split_estimate'
    });
    const remainder = handlingUnit({
      id: 'hu-remainder',
      code: 'HU-REMANENTE',
      quantity_base: 6,
      measurement_status: 'complete',
      measurement_source: 'split_estimate'
    });
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([split, remainder]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockResolvedValueOnce(
      handlingUnit({
        ...split,
        actual_gross_weight_kg: 8,
        actual_volume_m3: 0.2,
        occupied_weight_kg: 8,
        occupied_volume_m3: 0.2,
        measurement_status: 'verified',
        measurement_source: 'manual'
      })
    );

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, canRelease: true }
    });

    const verifyButtons = await screen.findAllByRole('button', { name: 'Verificar medidas' });
    expect(verifyButtons).toHaveLength(2);
    await fireEvent.click(verifyButtons[0]!);
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-FRACCION' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);

    await waitFor(() =>
      expect(inventoryMocks.verifyHandlingUnitMeasurements).toHaveBeenCalledWith(
        'hu-split',
        {
          gross_weight_kg: 8,
          volume_m3: 0.2,
          length_m: null,
          width_m: null,
          height_m: null
        },
        'manual'
      )
    );
    expect(
      screen.getByText('Medidas de HU-FRACCION verificadas correctamente.')
    ).toBeInTheDocument();
  });

  it('conserva los requisitos de etiqueta y retaceo del payload de medición', async () => {
    const pending = handlingUnit({
      stock_status: 'quarantine',
      measurement_status: 'incomplete',
      measurement_source: 'receipt',
      release_requirements: ['label_confirmation_required', 'retaceo_not_final']
    });
    const verified = handlingUnit({
      ...pending,
      measurement_status: 'verified',
      measurement_source: 'manual',
      release_requirements: ['label_confirmation_required', 'retaceo_not_final']
    });
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([pending]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockResolvedValueOnce(verified);

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, canRelease: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByRole('button', { name: 'Verificar medidas' }));
    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), { target: { value: '8' } });
    await fireEvent.input(within(form).getByLabelText(/Volumen/), { target: { value: '0.2' } });
    await fireEvent.submit(form);

    await waitFor(() => expect(inventoryMocks.verifyHandlingUnitMeasurements).toHaveBeenCalled());
    expect(
      await screen.findByText(
        'Confirme la impresión y colocación de la etiqueta vigente antes de liberar.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/retaceos:verify debe verificar y cerrar el retaceo antes de liberar/)
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Liberar a disponible' })).not.toBeInTheDocument();
  });

  it('explica el permiso de retaceo pendiente y solo ofrece la lista cuando puede consultarse', async () => {
    const unit = handlingUnit({
      stock_status: 'quarantine',
      measurement_status: 'verified',
      measurement_source: 'manual',
      release_requirements: ['retaceo_cost_unapplied'],
      purchase_code: 'COM-00013',
      receipt_lot_code: 'LOT-COM-013'
    });
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([unit]);

    const { unmount } = render(HandlingUnitsPanel, {
      props: {
        warehouseId: 'warehouse-1',
        canRelease: true,
        canReadRetaceos: true,
        canVerifyRetaceos: false
      }
    });

    await screen.findByText('HU-0001');
    expect(
      screen.getByText(/permiso retaceos:verify debe aplicar el retaceo al costo/)
    ).toBeInTheDocument();
    expect(screen.getByText('Referencia: Compra COM-00013 · Lote LOT-COM-013')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir retaceos' })).toHaveAttribute(
      'href',
      '/retaceos'
    );
    unmount();

    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([unit]);
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canRelease: true }
    });
    expect(
      await screen.findByText(/permiso retaceos:verify debe aplicar el retaceo al costo/)
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Abrir retaceos' })).not.toBeInTheDocument();
  });

  it('prepara una fracción disponible atómicamente y advierte que ambas partes quedan en cuarentena', async () => {
    const unit = handlingUnit({
      stock_status: 'available',
      measurement_status: 'verified',
      measurement_source: 'manual',
      quantity_base: 10
    });
    inventoryMocks.listHandlingUnits.mockResolvedValue([unit]);
    inventoryMocks.prepareHandlingUnitSplit.mockResolvedValue({
      idempotency_key: 'split-attempt-1',
      source_reference: 'hu-split:test',
      remainder_handling_unit_id: 'hu-remainder',
      remainder_handling_unit_code: 'HU-REMANENTE',
      remainder_quantity_base: '6',
      split_handling_unit_id: 'hu-child',
      split_handling_unit_code: 'HU-FRACCION',
      split_quantity_base: '4',
      stock_status: 'quarantine',
      measurement_status: 'complete'
    });
    locationMocks.listLocations.mockReset();
    locationMocks.listLocations.mockImplementation(async () => ({
      items: [
        {
          id: 'location-2',
          warehouse_id: 'warehouse-1',
          code: 'RACK-01',
          area: 'A',
          aisle: '01',
          rack: 'R1',
          level: '1',
          position: '01',
          is_active: true,
          storage_eligible: true,
          lifecycle_status: 'active'
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    }));

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canPrepareSplit: true }
    });

    await screen.findByText('HU-0001');
    await fireEvent.click(screen.getByText('Otras acciones'));
    await fireEvent.click(screen.getByRole('button', { name: 'Dividir unidad' }));
    expect(screen.queryByRole('button', { name: 'Trasladar a sucursal' })).not.toBeInTheDocument();
    const form = screen.getByRole('form', { name: 'Dividir unidad HU-0001' });
    await waitFor(() =>
      expect(within(form).getByLabelText('Ubicación de la nueva unidad')).toBeEnabled()
    );
    expect(within(form).getByLabelText(/Cantidad para la nueva unidad/)).toHaveValue(null);
    await fireEvent.input(within(form).getByLabelText(/Cantidad para la nueva unidad/), {
      target: { value: '4' }
    });
    expect(within(form).getByLabelText(/Cantidad para la nueva unidad/)).toHaveValue(4);
    expect(within(form).getByLabelText('Ubicación de la nueva unidad')).toHaveValue('location-2');
    expect(form).toHaveTextContent('remanente HU-0001 con 6');
    await fireEvent.submit(form);

    await waitFor(() => expect(confirmation.current).not.toBeNull());
    expect(confirmation.current?.description).toContain('remanente de 6 unidades base');
    expect(confirmation.current?.description).toContain(
      'la etiqueta anterior dejará de estar vigente'
    );
    expect(confirmation.current?.description).toContain('una etiqueta vigente para cada una');
    expect(confirmation.current?.resourceName).toContain('nueva unidad 4 + remanente 6');
    await confirmation.proceed();

    await waitFor(() =>
      expect(inventoryMocks.prepareHandlingUnitSplit).toHaveBeenCalledWith(
        'hu-1',
        4,
        'location-2',
        expect.any(String)
      )
    );
    const result = await screen.findByRole('status');
    expect(result).toHaveTextContent('remanente HU-REMANENTE (6)');
    expect(result).toHaveTextContent('El remanente conserva el código original');
    expect(result).toHaveTextContent('el total de inventario no cambia');
    expect(result).toHaveTextContent(
      'No es otra recepción: se dividió una unidad disponible en dos.'
    );
    expect(result).toHaveTextContent('la etiqueta de esa unidad');
    expect(result).toHaveTextContent('Liberar a disponible');
  });

  it('abre el flujo documental B03 desde la acción de Almacenes', async () => {
    const unit = handlingUnit({
      stock_status: 'available',
      measurement_status: 'verified'
    });
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([unit]);

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canTransfer: true }
    });

    await fireEvent.click(await screen.findByRole('button', { name: 'Trasladar a sucursal' }));

    await waitFor(() =>
      expect(navigationMocks.goto).toHaveBeenCalledWith(
        '/transfers?warehouse_id=warehouse-1&handling_unit_id=hu-1'
      )
    );
    expect(inventoryMocks.transferHandlingUnit).not.toHaveBeenCalled();
    expect(inventoryMocks.prepareHandlingUnitSplit).not.toHaveBeenCalled();
  });
});
