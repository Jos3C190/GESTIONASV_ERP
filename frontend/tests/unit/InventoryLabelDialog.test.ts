import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import HandlingUnitLabelDialog from '../../src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte';
import HandlingUnitsPanel from '../../src/lib/features/inventory/components/HandlingUnitsPanel.svelte';
import type { HandlingUnit, InventoryLabelPreview } from '../../src/lib/features/inventory/types';
import { saveRetaceoPreview } from './retaceo-preview';

const api = vi.hoisted(() => ({
  previewInventoryLabel: vi.fn(),
  recordInventoryLabelPrint: vi.fn(),
  createTraceCapability: vi.fn(),
  confirmInventoryLabelPlacement: vi.fn(),
  revokeTraceCapabilities: vi.fn(),
  listHandlingUnits: vi.fn(),
  listLocations: vi.fn(),
  qr: vi.fn()
}));
vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: api }));
vi.mock('$lib/features/locations/services', () => ({ listLocations: api.listLocations }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/features/inventory/components/LabelPrintPreview.svelte', async () => ({
  default: (await import('./fixtures/InventoryLabelPreviewStub.svelte')).default
}));
vi.mock('qrcode', async (original) => {
  const module = await original<{ default: typeof import('qrcode') }>();
  return { ...module, default: { ...module.default, toDataURL: api.qr } };
});
vi.mock('$lib/features/inventory/label-printing', async (original) => {
  const module = await original<typeof import('$lib/features/inventory/label-printing')>();
  return {
    ...module,
    prepareLabelPrintWindow: vi.fn(async (target: Window, html: string) => {
      target.document.write(html);
    })
  };
});

const unit = {
  id: 'hu-1',
  code: 'HU-DD17851A961041B8',
  warehouse_id: 'wh',
  inventory_item_id: 'item',
  product_name: 'Azúcar Glass Premium 10kg',
  quantity_base: 10,
  stock_status: 'quarantine',
  release_requirements: ['label_confirmation_required'],
  closed_at: null,
  measurement_status: 'verified',
  location_id: 'loc'
} as HandlingUnit;
const preview: InventoryLabelPreview = {
  inventory_lot_id: 'lot',
  inventory_lot_detail_id: 'detail',
  handling_unit_id: unit.id,
  handling_unit_code: unit.code,
  inventory_item_id: 'item',
  product_internal_code: 'INT-004',
  product_name: unit.product_name!,
  receipt_lot_code: 'LOT-COM-00027-DD3EB6A00CFDB48C49D4AED9BCCDAF3F5',
  receipt_lot_header_code: 'LOT-COM-00027',
  manufacturer_lot_code: 'FAB-2026-10',
  received_on: '2026-10-28',
  quantity_base: '10',
  base_unit_symbol: 'cj',
  expiry_date: '2027-02-01',
  stock_status: 'quarantine',
  print_count: 0,
  has_initial_print: false,
  label_revision: 1,
  label_print_id: null,
  label_confirmation_required: true,
  label_confirmed: false,
  presentation_equivalence: null
};

async function acceptPreview() {
  const iframe = await screen.findByTitle(/Vista previa de impresión/);
  (iframe as HTMLIFrameElement).contentDocument!.body.innerHTML =
    '<article class="label"></article>';
  await fireEvent.load(iframe);
}

describe('label dialog and pending-label queue', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.previewInventoryLabel.mockResolvedValue(preview);
    api.createTraceCapability.mockResolvedValue({ token: 'demo-label-token' });
    const qr = process.env.LABEL_QR_FIXTURE
      ? readFileSync(process.env.LABEL_QR_FIXTURE, 'utf8')
      : 'data:image/png;base64,AA==';
    api.qr.mockResolvedValue(qr);
    api.listHandlingUnits.mockResolvedValue([
      unit,
      {
        ...unit,
        id: 'hu-2',
        code: 'HU-DISPONIBLE',
        stock_status: 'available',
        release_requirements: []
      }
    ]);
    api.listLocations.mockResolvedValue({ items: [], meta: { pages: 1 } });
  });

  it('previews visible lot/dates in both compact formats and prints optional notes with the saved snapshot', async () => {
    const write = vi.fn();
    const popup = {
      document: { write },
      close: vi.fn(),
      focus: vi.fn(),
      print: vi.fn(),
      addEventListener: vi.fn()
    };
    vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    api.recordInventoryLabelPrint.mockImplementation(async (body) => ({
      id: 'printed',
      quantity_printed: body.quantity_printed,
      label_snapshot: { ...preview, notes: body.notes }
    }));
    const { container } = render(HandlingUnitLabelDialog, { unit, canVerify: true });
    await screen.findByText(preview.product_name);
    await fireEvent.change(screen.getByLabelText('Contenido'), { target: { value: 'qr' } });
    let iframe = await screen.findByTitle(/Vista previa de impresión/);
    expect(iframe.getAttribute('srcdoc')).toContain(preview.receipt_lot_code);
    expect(iframe.getAttribute('srcdoc')).toContain('28/10/2026');
    saveRetaceoPreview('etiqueta-qr', container);
    await fireEvent.change(screen.getByLabelText('Contenido'), { target: { value: 'barcode' } });
    await fireEvent.input(screen.getByLabelText(/Observaciones de la etiqueta/), {
      target: { value: 'Mantener seco' }
    });
    await acceptPreview();
    iframe = screen.getByTitle(/Vista previa de impresión/);
    expect(iframe.getAttribute('srcdoc')).toContain('01/02/2027');
    expect(iframe.getAttribute('srcdoc')).toContain('Mantener seco');
    expect(iframe.getAttribute('srcdoc')).not.toContain('<img');
    saveRetaceoPreview('etiqueta-code128', container);
    const print = screen.getByRole('button', { name: 'Imprimir etiqueta' });
    await waitFor(() => expect(print).toBeEnabled());
    await fireEvent.click(print);
    await waitFor(() => expect(api.recordInventoryLabelPrint).toHaveBeenCalledOnce());
    expect(api.recordInventoryLabelPrint).toHaveBeenCalledWith(
      expect.objectContaining({
        notes: 'Mantener seco',
        layout: { content: 'barcode', width_mm: 80, height_mm: 50 }
      })
    );
    expect(write.mock.calls.at(-1)?.[0]).toContain(preview.receipt_lot_code);
    expect(api.confirmInventoryLabelPlacement).not.toHaveBeenCalled();
  });

  it('keeps printing unavailable when the server blocks an unclosed retaceo', async () => {
    api.previewInventoryLabel.mockRejectedValue(new Error('Cierra el retaceo antes de imprimir.'));
    const { container } = render(HandlingUnitLabelDialog, { unit, canVerify: true });
    expect(await screen.findByRole('alert')).toHaveTextContent('Cierra el retaceo');
    expect(screen.getByRole('button', { name: 'Imprimir etiqueta' })).toBeDisabled();
    expect(api.recordInventoryLabelPrint).not.toHaveBeenCalled();
    saveRetaceoPreview('etiqueta-bloqueada', container);
  });

  it('associates invalid copies with its field and does not offer a server refresh for local errors', async () => {
    render(HandlingUnitLabelDialog, { unit, canVerify: true });
    await screen.findByText(preview.product_name);
    const copies = screen.getByLabelText('Copias (1–100)');
    await fireEvent.input(copies, { target: { value: '0' } });
    expect(copies).toHaveAttribute('aria-invalid', 'true');
    const issue = screen.getByRole('alert');
    expect(issue).toHaveTextContent('Indica entre 1 y 100 copias.');
    expect(copies.getAttribute('aria-describedby')).toBe(issue.id);
    expect(screen.getByRole('button', { name: 'Imprimir etiqueta' })).toBeDisabled();
    expect(
      screen.queryByRole('button', { name: 'Actualizar datos de etiqueta' })
    ).not.toBeInTheDocument();
    expect(api.recordInventoryLabelPrint).not.toHaveBeenCalled();
  });

  it('filters label work independently of available inventory and restores the full list', async () => {
    render(HandlingUnitsPanel, { warehouseId: 'wh', canVerify: false, canRelease: false });
    await screen.findByText('HU-DISPONIBLE');
    const filter = screen.getByLabelText('Solo etiquetas pendientes de imprimir o confirmar');
    await fireEvent.click(filter);
    expect(screen.queryByText('HU-DISPONIBLE')).not.toBeInTheDocument();
    expect(screen.getByText(unit.code)).toBeInTheDocument();
    await fireEvent.click(filter);
    expect(screen.getByText('HU-DISPONIBLE')).toBeInTheDocument();
  });

  it('associates invalid paper dimensions with the corresponding fields', async () => {
    render(HandlingUnitLabelDialog, { unit, canVerify: true });
    await screen.findByText(preview.product_name);
    await fireEvent.change(screen.getByLabelText('Tamaño · ancho × alto'), {
      target: { value: 'custom' }
    });
    const width = screen.getByLabelText('Ancho (mm)');
    const height = screen.getByLabelText('Alto (mm)');
    await fireEvent.input(width, { target: { value: '24' } });
    expect(width).toHaveAttribute('aria-invalid', 'true');
    expect(document.getElementById(width.getAttribute('aria-describedby')!)).toHaveTextContent(
      'ancho'
    );
    expect(height).toHaveAttribute('aria-invalid', 'false');
    await fireEvent.input(height, { target: { value: '19' } });
    expect(height).toHaveAttribute('aria-invalid', 'true');
    expect(document.getElementById(height.getAttribute('aria-describedby')!)).toHaveTextContent(
      'alto'
    );
    expect(screen.getByRole('button', { name: 'Imprimir etiqueta' })).toBeDisabled();
  });

  it('moves focus to cancel in the inline revocation confirmation and returns it on cancel or Escape', async () => {
    render(HandlingUnitLabelDialog, { unit, canVerify: true });
    const trigger = await screen.findByRole('button', { name: 'Invalidar enlaces públicos' });
    await fireEvent.click(trigger);
    const cancel = screen.getByRole('button', { name: /^Cancelar$/ });
    await waitFor(() => expect(cancel).toHaveFocus());
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    await fireEvent.click(cancel);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Invalidar enlaces públicos' })).toHaveFocus()
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Invalidar enlaces públicos' }));
    await fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Invalidar enlaces públicos' })).toHaveFocus()
    );
    expect(api.revokeTraceCapabilities).not.toHaveBeenCalled();
  });
});
