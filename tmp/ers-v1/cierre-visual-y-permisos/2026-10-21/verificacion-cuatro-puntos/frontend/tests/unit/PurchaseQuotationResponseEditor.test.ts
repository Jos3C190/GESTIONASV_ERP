import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationResponseEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationResponseEditor.svelte';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  recordResponse: vi.fn(),
  initiateDocument: vi.fn(),
  completeDocument: vi.fn(),
  listDocuments: vi.fn(),
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    get: mocks.get,
    recordResponse: mocks.recordResponse,
    initiateDocument: mocks.initiateDocument,
    completeDocument: mocks.completeDocument,
    listDocuments: mocks.listDocuments
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    getProduct: vi.fn().mockResolvedValue({
      id_product: 10,
      name: 'Producto de prueba'
    }),
    listUnits: vi.fn().mockResolvedValue([
      { id_unit: 2, name: 'Caja', symbol: 'cj' }
    ])
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

vi.mock('$lib/stores/session.svelte', () => ({
  session: {
    user: { id: 'response-editor-test-user' }
  }
}));

function installSessionStorage() {
  const values = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key) {
      return values.get(String(key)) ?? null;
    },
    key(index) {
      return [...values.keys()][index] ?? null;
    },
    removeItem(key) {
      values.delete(String(key));
    },
    setItem(key, value) {
      values.set(String(key), String(value));
    }
  };

  Object.defineProperty(window, 'sessionStorage', {
    configurable: true,
    value: storage
  });
}

const quotation = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'CQ-0001',
  supplier_id: 25,
  quotation_date: '2026-09-13T12:00:00-06:00',
  currency: 'USD',
  created_by_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  snapshots: [],
  request_links: [],
  details: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      unit_price: '0.000000',
      discount: '0.000000',
      subtotal: '0.000000',
      tax_rate: '0.000000',
      tax_amount: '0.000000',
      total: '0.000000',
      delivery_days: null,
      available_quantity: null,
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  expenses: [],
  valid_until: null,
  payment_terms: null,
  delivery_days: null,
  subtotal: '0.000000',
  discount: '0.000000',
  tax: '0.000000',
  total: '0.000000',
  status: 'requested',
  notes: null,
  created_at: null,
  updated_at: null
} as const;

describe('PurchaseQuotationResponseEditor', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    installSessionStorage();
    window.sessionStorage.clear();
    mocks.get.mockReset();
    mocks.recordResponse.mockReset();
    mocks.initiateDocument.mockReset();
    mocks.completeDocument.mockReset();
    mocks.listDocuments.mockReset().mockResolvedValue([]);
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation(
      (code: string) => code === 'purchase_quotations:manage' || code === 'purchase_quotations:read'
    );
    mocks.get.mockResolvedValue(quotation);
  });

  it('keeps the supplier response fields when attaching a PDF', async () => {
    const uploadedDocument = {
      id: '33333333-3333-3333-3333-333333333333',
      purchase_quotation_id: quotation.id,
      document_id: '44444444-4444-4444-4444-444444444444',
      file_name: 'respuesta-proveedor.pdf',
      file_type: 'application/pdf',
      size_bytes: 32,
      status: 'active',
      failure_code: null,
      uploaded_at: '2026-10-05T12:00:00-06:00',
      created_at: null,
      updated_at: null
    };
    mocks.initiateDocument.mockResolvedValue({
      document: uploadedDocument,
      upload_url: 'https://storage.example/signed-upload',
      method: 'PUT',
      required_headers: { 'Content-Type': 'application/pdf' },
      expires_at: '2026-10-05T13:00:00-06:00'
    });
    mocks.completeDocument.mockResolvedValue(uploadedDocument);
    mocks.listDocuments.mockResolvedValueOnce([]).mockResolvedValueOnce([uploadedDocument]);
    vi.stubGlobal('crypto', {
      subtle: { digest: vi.fn().mockResolvedValue(new ArrayBuffer(32)) }
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));

    const { container } = render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    const price = await screen.findByLabelText('Precio unitario');
    await fireEvent.input(price, { target: { value: '20' } });
    expect(window.sessionStorage.length).toBeGreaterThan(0);
    await fireEvent.input(screen.getByLabelText('Disponible ahora'), {
      target: { value: '4' }
    });
    await fireEvent.input(screen.getByLabelText('Términos de pago'), {
      target: { value: '30 días' }
    });
    await fireEvent.input(screen.getByLabelText('Notas de respuesta'), {
      target: { value: 'Entrega parcial acordada' }
    });

    const file = new File(['contenido pdf'], 'respuesta-proveedor.pdf', {
      type: 'application/pdf'
    });
    const fileInput = screen.getByLabelText('Adjuntar archivo original de la oferta del proveedor');
    await waitFor(() => expect(mocks.listDocuments).toHaveBeenCalled());
    await waitFor(() => expect(fileInput).not.toBeDisabled());
    await fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => expect(mocks.initiateDocument).toHaveBeenCalled());

    expect(
      await screen.findByText(/Oferta original adjuntada correctamente/)
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Precio unitario')).toHaveValue(20);
    expect(screen.getByLabelText('Disponible ahora')).toHaveValue(4);
    expect(screen.getByLabelText('Términos de pago')).toHaveValue('30 días');
    expect(screen.getByLabelText('Notas de respuesta')).toHaveValue('Entrega parcial acordada');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(mocks.recordResponse).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="file"]')?.closest('form')).toBeNull();
  });

  it('keeps the supplier response fields and shows an error when PDF upload fails', async () => {
    mocks.initiateDocument.mockRejectedValue(new Error('Falló el servidor al iniciar la carga.'));
    vi.stubGlobal('crypto', {
      subtle: { digest: vi.fn().mockResolvedValue(new ArrayBuffer(32)) }
    });

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    await fireEvent.input(await screen.findByLabelText('Precio unitario'), {
      target: { value: '20' }
    });
    await fireEvent.input(screen.getByLabelText('Términos de pago'), {
      target: { value: '30 días' }
    });

    const file = new File(['contenido pdf'], 'respuesta-proveedor.pdf', {
      type: 'application/pdf'
    });
    await fireEvent.change(
      screen.getByLabelText('Adjuntar archivo original de la oferta del proveedor'),
      { target: { files: [file] } }
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Falló el servidor al iniciar la carga.'
    );
    expect(screen.getByLabelText('Precio unitario')).toHaveValue(20);
    expect(screen.getByLabelText('Términos de pago')).toHaveValue('30 días');
    expect(mocks.recordResponse).not.toHaveBeenCalled();
  });

  it('restores the unsaved response if the editor is remounted', async () => {
    const first = render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    await fireEvent.input(await screen.findByLabelText('Precio unitario'), {
      target: { value: '21.50' }
    });
    await fireEvent.input(screen.getByLabelText('Términos de pago'), {
      target: { value: 'Crédito 30 días' }
    });
    await fireEvent.input(screen.getByLabelText('Notas de respuesta'), {
      target: { value: 'No perder estos datos' }
    });
    const saved = window.sessionStorage.getItem(
      `erp_purchase_quotation_response_draft:response-editor-test-user:${quotation.id}`
    );
    expect(saved).not.toBeNull();
    expect(JSON.parse(saved!)).toMatchObject({
      quotationId: quotation.id,
      userId: 'response-editor-test-user',
      paymentTerms: 'Crédito 30 días',
      notes: 'No perder estos datos'
    });
    first.unmount();

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    expect(
      await screen.findByText('Recuperamos el borrador de tu respuesta sin guardar.')
    ).toBeInTheDocument();
    expect(await screen.findByLabelText('Precio unitario')).toHaveValue(21.5);
    expect(screen.getByLabelText('Términos de pago')).toHaveValue('Crédito 30 días');
    expect(screen.getByLabelText('Notas de respuesta')).toHaveValue('No perder estos datos');
  });

  it('records the supplier response using the requested coverage', async () => {
    mocks.recordResponse.mockResolvedValue({
      ...quotation,
      status: 'received'
    });

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    const price = await screen.findByLabelText('Precio unitario');
    await fireEvent.input(price, { target: { value: '20' } });
    await fireEvent.input(screen.getByLabelText('Impuesto %'), {
      target: { value: '13' }
    });
    await fireEvent.input(screen.getByLabelText('Términos de pago'), {
      target: { value: '30 días' }
    });

    await fireEvent.submit(document.getElementById('purchase-quotation-response-form')!);

    await waitFor(() => {
      expect(mocks.recordResponse).toHaveBeenCalledWith(
        quotation.id,
        expect.objectContaining({
          quotation_date: expect.any(String),
          valid_until: null,
          payment_terms: '30 días',
          delivery_days: null,
          lines: [
            {
              product_id: 10,
              unit_id: 2,
              offered_quantity: 5,
              unit_price: 20,
              discount: 0,
              tax_rate: 13,
              delivery_days: null,
              available_quantity: null,
              notes: null
            }
          ],
          expenses: [],
          notes: null
        }),
        null,
        null
      );
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-quotations/${quotation.id}`);
  });

  it('blocks response capture for quotations outside requested status', async () => {
    mocks.get.mockResolvedValue({
      ...quotation,
      status: 'draft'
    });

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    expect(
      await screen.findByText(
        'Solo las cotizaciones enviadas al proveedor pueden registrar una respuesta.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Registrar respuesta' })).not.toBeInTheDocument();
  });

  it('blocks direct access without manage permission', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar cotizaciones de compra.'
    );
    expect(mocks.get).not.toHaveBeenCalled();
  });
});
