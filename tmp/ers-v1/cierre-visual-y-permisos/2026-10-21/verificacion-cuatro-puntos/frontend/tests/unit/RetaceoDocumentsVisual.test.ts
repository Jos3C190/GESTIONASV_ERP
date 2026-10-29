import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoDraftEditor from '$lib/features/retaceos/components/RetaceoDraftEditor.svelte';
import type { Retaceo, RetaceoCostDocument } from '$lib/types/retaceo';

const mocks = vi.hoisted(() => ({
  getRetaceo: vi.fn(),
  update: vi.fn(),
  initiateCostDocument: vi.fn(),
  completeCostDocument: vi.fn(),
  createCostDocumentDownloadUrl: vi.fn(),
  removeCostDocument: vi.fn(),
  getPurchase: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    get: mocks.getRetaceo,
    update: mocks.update,
    initiateCostDocument: mocks.initiateCostDocument,
    completeCostDocument: mocks.completeCostDocument,
    createCostDocumentDownloadUrl: mocks.createCostDocumentDownloadUrl,
    removeCostDocument: mocks.removeCostDocument
  }
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: { get: mocks.getPurchase }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: { listUnits: mocks.listUnits, getProduct: mocks.getProduct }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: mocks.hasPermission }
}));

vi.mock('$lib/stores/confirmation.svelte', () => ({
  confirmation: { request: vi.fn() }
}));

const retaceoId = 'retaceo-1';
const costId = 'cost-1';
const purchaseDetailId = 'purchase-detail-1';

function makeDocument(index: number): RetaceoCostDocument {
  return {
    id: `link-${index}`,
    retaceo_cost_id: costId,
    document_id: `asset-${index}`,
    file_name: `respaldo-${index}.pdf`,
    file_type: 'application/pdf',
    size_bytes: 1024,
    status: 'active',
    failure_code: null,
    uploaded_at: '2026-10-04T08:00:00Z',
    created_at: '2026-10-04T08:00:00Z',
    updated_at: '2026-10-04T08:00:00Z'
  };
}

const record: Retaceo = {
  id: retaceoId,
  company_id: 'company-1',
  code: 'RET-0001',
  purchase_id: 'purchase-1',
  branch_id: 'branch-1',
  created_by_id: 'user-1',
  currency: 'USD',
  details: [
    {
      id: 'retaceo-detail-1',
      retaceo_id: retaceoId,
      purchase_detail_id: purchaseDetailId,
      product_id: 1,
      unit_id: 1,
      quantity: '1.000000',
      cost_fob: '100.000000',
      freight: '0.000000',
      expenses: '0.000000',
      dai: '0.000000',
      total_cost: '100.000000',
      unit_cost: '100.000000',
      created_at: null,
      updated_at: null
    }
  ],
  costs: [
    {
      id: costId,
      retaceo_id: retaceoId,
      source_purchase_order_expense_id: null,
      expense_type_id: null,
      classification: 'freight',
      title: 'Flete',
      description: null,
      amount: '120.000000',
      is_active: true,
      allocations: [{ purchase_detail_id: purchaseDetailId, amount: '0.000000' }],
      documents: Array.from({ length: 5 }, (_, index) => makeDocument(index + 1)),
      created_at: null,
      updated_at: null
    }
  ],
  total_fob: '100.000000',
  total_freight: '120.000000',
  total_expenses: '0.000000',
  total_dai: '0.000000',
  import_vat: '0.000000',
  total_cost: '220.000000',
  freight_percentage: '120.000000',
  expense_percentage: '0.000000',
  dai_percentage: '0.000000',
  status: 'draft',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('Retaceo document list and viewport behavior', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    mocks.getRetaceo.mockReset().mockResolvedValue(record);
    mocks.update.mockReset();
    mocks.initiateCostDocument.mockReset().mockResolvedValue({
      document: { document_id: 'asset-6' },
      upload_url: 'https://storage.test/upload',
      method: 'PUT',
      required_headers: { 'content-type': 'application/pdf' },
      expires_at: '2026-10-04T09:00:00Z'
    });
    mocks.completeCostDocument.mockReset().mockResolvedValue({
      ...makeDocument(6),
      file_name: 'factura-extra.pdf',
      document_id: 'asset-6'
    });
    mocks.createCostDocumentDownloadUrl.mockReset().mockResolvedValue({
      url: 'https://storage.test/signed.pdf',
      expires_at: '2026-10-04T09:00:00Z'
    });
    mocks.removeCostDocument.mockReset();
    mocks.getPurchase.mockReset().mockResolvedValue({ id: 'purchase-1', code: 'COM-0001' });
    mocks.listUnits.mockReset().mockResolvedValue([]);
    mocks.getProduct.mockReset().mockResolvedValue(null);
    mocks.hasPermission.mockReset().mockReturnValue(true);

    if (globalThis.crypto?.subtle) {
      vi.spyOn(globalThis.crypto.subtle, 'digest').mockResolvedValue(new ArrayBuffer(32));
    }
  });

  it('keeps attachments and draft actions available through the full upload', async () => {
    render(RetaceoDraftEditor, { props: { retaceoId } });

    const initialList = await screen.findByRole('list', { name: 'Comprobantes adjuntos: 5' });
    expect(within(initialList).getAllByRole('listitem')).toHaveLength(5);
    expect(initialList.className).not.toMatch(/max-h-|overflow-y-auto/);

    const saveButton = screen.getByRole('button', { name: 'Guardar borrador' });
    expect(saveButton).toBeInTheDocument();
    const actions = document.querySelector('[aria-label="Acciones del borrador de retaceo"]');
    expect(actions).toBeInTheDocument();
    expect(actions?.className).not.toMatch(/sticky|fixed/);

    const file = new File([new Uint8Array([37, 80, 68, 70])], 'factura-extra.pdf', {
      type: 'application/pdf'
    });
    if (!file.arrayBuffer) {
      Object.defineProperty(file, 'arrayBuffer', {
        value: async () => new Uint8Array([37, 80, 68, 70]).buffer
      });
    }

    let finishUpload: ((response: Response) => void) | undefined;
    vi.mocked(fetch).mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finishUpload = resolve;
        })
    );

    const fileInput = screen.getByLabelText('Adjuntar comprobante a Flete');
    await fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Adjuntando comprobante a Flete.')
    );

    finishUpload?.({ ok: true } as Response);

    const updatedList = await screen.findByRole('list', { name: 'Comprobantes adjuntos: 6' });
    expect(within(updatedList).getAllByRole('listitem')).toHaveLength(6);
    expect(within(updatedList).getByText('factura-extra.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar borrador' })).toBeInTheDocument();
    expect(screen.getByLabelText('Concepto')).toHaveValue('Flete');
    expect(fetch).toHaveBeenCalledWith(
      'https://storage.test/upload',
      expect.objectContaining({ method: 'PUT', body: file, credentials: 'omit' })
    );
  });

  it('lays the file input over the visible attachment control', async () => {
    render(RetaceoDraftEditor, { props: { retaceoId } });
    await screen.findByRole('list', { name: 'Comprobantes adjuntos: 5' });

    const fileInput = screen.getByLabelText('Adjuntar comprobante a Flete');
    const visibleControl = fileInput.closest('label');
    expect(fileInput).toHaveAttribute('type', 'file');
    expect(fileInput).toHaveClass('absolute', 'inset-0', 'h-full', 'w-full', 'opacity-0');
    expect(visibleControl).toHaveClass('relative');
    expect(visibleControl).toHaveTextContent('Adjuntar documento');
  });

  it('opens the comprobante tab during the click before the signed URL request resolves', async () => {
    render(RetaceoDraftEditor, { props: { retaceoId } });
    await screen.findByRole('list', { name: 'Comprobantes adjuntos: 5' });

    const replace = vi.fn();
    const popup = {
      opener: window,
      location: { replace },
      close: vi.fn(),
      document: {
        createElement: vi.fn(() => ({ name: '', content: '' })),
        head: { appendChild: vi.fn() }
      }
    } as unknown as Window;
    const open = vi.spyOn(window, 'open').mockReturnValue(popup);

    await fireEvent.click(screen.getAllByRole('button', { name: 'Descargar' })[0]!);

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith('https://storage.test/signed.pdf');
    });
    expect(open).toHaveBeenCalledWith('about:blank', '_blank');
    expect(mocks.createCostDocumentDownloadUrl).toHaveBeenCalledWith(retaceoId, costId, 'asset-1');
    expect(popup.opener).toBeNull();
  });
});
