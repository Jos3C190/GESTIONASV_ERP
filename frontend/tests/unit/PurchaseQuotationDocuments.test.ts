import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationDocuments from '$lib/features/purchase-quotations/components/PurchaseQuotationDocuments.svelte';
import type { PurchaseQuotationDocument } from '$lib/types/purchase-quotation';

const mocks = vi.hoisted(() => ({
  initiate: vi.fn(),
  complete: vi.fn(),
  list: vi.fn(),
  remove: vi.fn(),
  downloadUrl: vi.fn(),
  hasPermission: vi.fn(),
  confirmRequest: vi.fn()
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    initiateDocument: mocks.initiate,
    completeDocument: mocks.complete,
    listDocuments: mocks.list,
    removeDocument: mocks.remove,
    createDocumentDownloadUrl: mocks.downloadUrl
  }
}));

vi.mock('$lib/stores/confirmation.svelte', () => ({
  confirmation: {
    request: mocks.confirmRequest
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const quotationId = '11111111-1111-1111-1111-111111111111';
const document: PurchaseQuotationDocument = {
  id: '22222222-2222-2222-2222-222222222222',
  purchase_quotation_id: quotationId,
  document_id: '33333333-3333-3333-3333-333333333333',
  file_name: 'oferta-proveedor.pdf',
  file_type: 'application/pdf',
  size_bytes: 2048,
  status: 'active',
  failure_code: null,
  uploaded_at: '2026-10-05T12:00:00-06:00',
  created_at: null,
  updated_at: null
};

describe('PurchaseQuotationDocuments', () => {
  beforeEach(() => {
    mocks.initiate.mockReset();
    mocks.complete.mockReset();
    mocks.list.mockReset().mockResolvedValue([document]);
    mocks.remove.mockReset();
    mocks.downloadUrl.mockReset();
    mocks.confirmRequest.mockReset();
    mocks.hasPermission
      .mockReset()
      .mockImplementation(
        (code: string) =>
          code === 'purchase_quotations:read' || code === 'purchase_quotations:manage'
      );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('opens the tab on click before awaiting a signed download URL', async () => {
    let resolveDownload!: (value: { url: string; expires_at: string }) => void;
    const downloadUrl = new Promise<{ url: string; expires_at: string }>((resolve) => {
      resolveDownload = resolve;
    });
    mocks.downloadUrl.mockReturnValue(downloadUrl);

    const temporaryTab = {
      opener: window,
      location: { href: 'about:blank' },
      close: vi.fn()
    } as unknown as Window;
    const open = vi.spyOn(window, 'open').mockReturnValue(temporaryTab);

    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'requested' }
    });

    await screen.findByText(document.file_name);
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar' }));

    expect(open).toHaveBeenCalledWith('about:blank', '_blank');
    expect(temporaryTab.opener).toBeNull();
    expect(mocks.downloadUrl).toHaveBeenCalledWith(
      quotationId,
      document.document_id,
      undefined,
      null
    );
    expect(screen.getByRole('button', { name: 'Preparando…' })).toBeInTheDocument();

    resolveDownload({
      url: 'https://storage.example/signed-offer',
      expires_at: '2026-10-05T13:00:00-06:00'
    });

    await waitFor(() =>
      expect(temporaryTab.location.href).toBe('https://storage.example/signed-offer')
    );
    expect(await screen.findByRole('button', { name: 'Descargar' })).toBeInTheDocument();
  });

  it('explains when the browser blocks the temporary download tab', async () => {
    vi.spyOn(window, 'open').mockReturnValue(null);

    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'requested' }
    });

    await screen.findByText(document.file_name);
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El navegador bloqueó la descarga. Permite las ventanas emergentes para este sitio e inténtalo de nuevo.'
    );
    expect(mocks.downloadUrl).not.toHaveBeenCalled();
  });

  it('asks for confirmation and detaches the selected supplier document', async () => {
    let currentDocuments = [document];
    mocks.list.mockImplementation(async () => currentDocuments);
    mocks.remove.mockImplementation(async () => {
      currentDocuments = [];
    });

    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'requested', consolidationId: 'consolidation-1' }
    });

    await screen.findByText(document.file_name);
    await fireEvent.click(screen.getByRole('button', { name: 'Quitar adjunto' }));

    expect(mocks.confirmRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'delete',
        title: 'Quitar archivo adjunto',
        description:
          'El archivo dejará de aparecer en esta respuesta del proveedor, pero el original se conservará. La acción quedará registrada en la bitácora.',
        confirmLabel: 'Quitar archivo',
        resourceName: document.file_name
      })
    );
    const confirmation = mocks.confirmRequest.mock.calls[0]?.[0];
    if (!confirmation) throw new Error('No se solicitó confirmación para quitar el archivo.');
    await confirmation.execute();

    await waitFor(() =>
      expect(mocks.remove).toHaveBeenCalledWith(
        quotationId,
        document.document_id,
        undefined,
        'consolidation-1'
      )
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'El adjunto se quitó de esta respuesta. El archivo original se conserva.'
    );
    expect(screen.queryByText(document.file_name)).not.toBeInTheDocument();
  });

  it('keeps the detached file hidden after a successful unlink without reloading the list', async () => {
    mocks.list.mockResolvedValueOnce([document]);
    mocks.remove.mockResolvedValue(undefined);

    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'requested' }
    });

    await screen.findByText(document.file_name);
    await fireEvent.click(screen.getByRole('button', { name: 'Quitar adjunto' }));
    const confirmation = mocks.confirmRequest.mock.calls[0]?.[0];
    if (!confirmation) throw new Error('No se solicitó confirmación para quitar el archivo.');
    await confirmation.execute();

    expect(await screen.findByRole('status')).toHaveTextContent(
      'El adjunto se quitó de esta respuesta. El archivo original se conserva.'
    );
    expect(screen.queryByText(document.file_name)).not.toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(1);
  });

  it('hides the remove action when the quotation is no longer editable', async () => {
    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'selected' }
    });

    await screen.findByText(document.file_name);

    expect(screen.queryByRole('button', { name: 'Quitar adjunto' })).not.toBeInTheDocument();
  });

  it('shows upload success from the completed document without reloading the list', async () => {
    mocks.list.mockResolvedValueOnce([]);
    mocks.initiate.mockResolvedValue({
      document,
      upload_url: 'https://storage.example/presigned-upload',
      method: 'PUT',
      required_headers: { 'Content-Type': 'application/pdf' },
      expires_at: '2026-10-05T13:00:00-06:00'
    });
    mocks.complete.mockResolvedValue(document);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));

    render(PurchaseQuotationDocuments, {
      props: { quotationId, quotationStatus: 'requested' }
    });

    await screen.findByText(/Aún no hay un archivo adjunto/);
    const file = new File(['contenido'], 'oferta.pdf', { type: 'application/pdf' });
    await fireEvent.change(
      screen.getByLabelText('Adjuntar archivo original de la oferta del proveedor'),
      {
        target: { files: [file] }
      }
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Oferta original adjuntada correctamente. Los datos de la respuesta siguen guardados en el formulario.'
    );
    expect(screen.getByText(document.file_name)).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(1);
    expect(mocks.complete).toHaveBeenCalledWith(quotationId, document.document_id, undefined, null);
  });
});
