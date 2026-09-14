import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderExpenseDocuments from '$lib/features/purchase-orders/components/PurchaseOrderExpenseDocuments.svelte';
import type { PurchaseOrderExpense, PurchaseOrderExpenseDocument } from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  initiate: vi.fn(),
  complete: vi.fn(),
  list: vi.fn(),
  downloadUrl: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    initiateExpenseDocument: mocks.initiate,
    completeExpenseDocument: mocks.complete,
    listExpenseDocuments: mocks.list,
    createExpenseDocumentDownloadUrl: mocks.downloadUrl
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const orderId = '11111111-1111-1111-1111-111111111111';
const expense: PurchaseOrderExpense = {
  id: '22222222-2222-2222-2222-222222222222',
  purchase_order_id: orderId,
  expense_type_id: '33333333-3333-3333-3333-333333333333',
  amount: '12.500000',
  description: 'Flete',
  created_at: null,
  updated_at: null
};

const document: PurchaseOrderExpenseDocument = {
  id: '44444444-4444-4444-4444-444444444444',
  purchase_order_expense_id: expense.id,
  document_id: '55555555-5555-5555-5555-555555555555',
  file_name: 'factura-flete.pdf',
  file_type: 'application/pdf',
  size_bytes: 2048,
  status: 'ready',
  failure_code: null,
  uploaded_at: '2026-09-13T12:00:00-06:00',
  created_at: null,
  updated_at: null
};

describe('PurchaseOrderExpenseDocuments', () => {
  beforeEach(() => {
    mocks.initiate.mockReset();
    mocks.complete.mockReset();
    mocks.list.mockReset();
    mocks.downloadUrl.mockReset();
    mocks.hasPermission.mockReset();
    mocks.hasPermission.mockImplementation(
      (code: string) => code === 'purchase_orders:read' || code === 'purchase_orders:manage'
    );
    mocks.list.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('lists existing documents and obtains a temporary download URL', async () => {
    mocks.list.mockResolvedValue([document]);
    mocks.downloadUrl.mockResolvedValue({
      url: 'https://storage.example/download-token',
      expires_at: '2026-09-13T13:00:00-06:00'
    });
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);

    render(PurchaseOrderExpenseDocuments, {
      props: {
        orderId,
        expense,
        orderStatus: 'sent'
      }
    });

    expect(await screen.findByText('factura-flete.pdf')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar' }));

    expect(mocks.downloadUrl).toHaveBeenCalledWith(orderId, expense.id, document.document_id);
    expect(open).toHaveBeenCalledWith(
      'https://storage.example/download-token',
      '_blank',
      'noopener,noreferrer'
    );
  });

  it('keeps document upload disabled while the order is draft', async () => {
    render(PurchaseOrderExpenseDocuments, {
      props: {
        orderId,
        expense,
        orderStatus: 'draft'
      }
    });

    expect(await screen.findByText('Sin documentos adjuntos.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Adjuntar documento al gasto')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Los documentos se habilitan cuando la orden deja de estar en borrador/)
    ).toBeInTheDocument();
    expect(mocks.initiate).not.toHaveBeenCalled();
  });

  it('uses the presigned PUT headers, completes the upload and refreshes the list', async () => {
    mocks.list.mockResolvedValueOnce([]).mockResolvedValueOnce([document]);
    mocks.initiate.mockResolvedValue({
      document,
      upload_url: 'https://storage.example/presigned-upload',
      method: 'PUT',
      required_headers: {
        'Content-Type': 'application/pdf',
        'x-upload-token': 'signed-value'
      },
      expires_at: '2026-09-13T13:00:00-06:00'
    });
    mocks.complete.mockResolvedValue(document);

    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    render(PurchaseOrderExpenseDocuments, {
      props: {
        orderId,
        expense,
        orderStatus: 'pending_approval'
      }
    });

    expect(await screen.findByText('Sin documentos adjuntos.')).toBeInTheDocument();

    const file = new File(['contenido'], 'comprobante.pdf', { type: 'application/pdf' });
    await fireEvent.change(screen.getByLabelText('Adjuntar documento al gasto'), {
      target: { files: [file] }
    });

    await waitFor(() => {
      expect(mocks.initiate).toHaveBeenCalledWith(orderId, expense.id, {
        file_name: 'comprobante.pdf',
        content_type: 'application/pdf',
        size_bytes: file.size,
        checksum_sha256: expect.stringMatching(/^[0-9a-f]{64}$/)
      });
    });

    expect(fetchMock).toHaveBeenCalledWith('https://storage.example/presigned-upload', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/pdf',
        'x-upload-token': 'signed-value'
      },
      body: file,
      credentials: 'omit'
    });
    expect(mocks.complete).toHaveBeenCalledWith(orderId, expense.id, document.document_id);
    expect(await screen.findByText('factura-flete.pdf')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Documento adjuntado correctamente.');
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });
});
