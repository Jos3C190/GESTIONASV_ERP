import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationDetail from '$lib/features/purchase-quotations/components/PurchaseQuotationDetail.svelte';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  getSupplier: vi.fn()
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    get: mocks.get
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    getSupplier: mocks.getSupplier
  }
}));

const quotation = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'CQ-0001',
  supplier_id: 25,
  quotation_date: '2026-09-13T12:00:00-06:00',
  currency: 'USD',
  created_by_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  request_links: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      purchase_request_id: '33333333-3333-3333-3333-333333333333',
      details: [
        {
          id: '44444444-4444-4444-4444-444444444444',
          purchase_quotation_request_id: '22222222-2222-2222-2222-222222222222',
          purchase_quotation_detail_id: '55555555-5555-5555-5555-555555555555',
          purchase_request_detail_id: '66666666-6666-6666-6666-666666666666',
          quantity: '5.000000',
          created_at: null,
          updated_at: null
        }
      ],
      created_at: null,
      updated_at: null
    }
  ],
  details: [
    {
      id: '55555555-5555-5555-5555-555555555555',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      unit_price: '20.000000',
      discount: '0.000000',
      subtotal: '100.000000',
      tax_rate: '13.000000',
      tax_amount: '13.000000',
      total: '113.000000',
      delivery_days: 4,
      available_quantity: '5.000000',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  expenses: [
    {
      id: '77777777-7777-7777-7777-777777777777',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      expense_type_id: '88888888-8888-8888-8888-888888888888',
      amount: '8.000000',
      description: 'Flete',
      created_at: null,
      updated_at: null
    }
  ],
  valid_until: '2026-09-30T12:00:00-06:00',
  payment_terms: '30 días',
  delivery_days: 4,
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'received',
  notes: 'Oferta recibida',
  created_at: null,
  updated_at: null
} as const;

const supplier = {
  id_supplier: 25,
  uuid: '99999999-9999-9999-9999-999999999999',
  code: 'PRV-025',
  name: 'Proveedor Central',
  country: 1,
  is_active: true,
  contacts: []
};

describe('PurchaseQuotationDetail', () => {
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.getSupplier.mockReset();
  });

  it('renders the quotation contract and related information', async () => {
    mocks.get.mockResolvedValue(quotation);
    mocks.getSupplier.mockResolvedValue(supplier);

    render(PurchaseQuotationDetail, {
      props: { id: quotation.id }
    });

    expect(await screen.findByRole('heading', { name: 'CQ-0001' })).toBeInTheDocument();
    expect(screen.getByText('PRV-025 — Proveedor Central')).toBeInTheDocument();
    expect(screen.getByText('Recibida')).toBeInTheDocument();
    expect(screen.getByText('Producto #10')).toBeInTheDocument();
    expect(screen.getByText('Flete')).toBeInTheDocument();
    expect(screen.getByText('Oferta recibida')).toBeInTheDocument();

    const requestLink = screen.getByRole('link', {
      name: /Solicitud 33333333-3333-3333-3333-333333333333/
    });
    expect(requestLink).toHaveAttribute(
      'href',
      '/purchase-requests/33333333-3333-3333-3333-333333333333'
    );

    const totals = screen.getByRole('heading', { name: 'Totales' }).closest('article')!;
    expect(within(totals).getByText('$113.00')).toBeInTheDocument();
  });

  it('keeps the detail usable when supplier lookup fails', async () => {
    mocks.get.mockResolvedValue({
      ...quotation,
      details: [],
      expenses: []
    });
    mocks.getSupplier.mockRejectedValue(new Error('Proveedor no disponible'));

    render(PurchaseQuotationDetail, {
      props: { id: quotation.id }
    });

    expect(await screen.findAllByText('Proveedor #25')).toHaveLength(2);
    expect(screen.getByText('Aún no hay respuesta registrada')).toBeInTheDocument();
  });

  it('renders load errors and retries the quotation request', async () => {
    mocks.get.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce(quotation);
    mocks.getSupplier.mockResolvedValue(supplier);

    render(PurchaseQuotationDetail, {
      props: { id: quotation.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByRole('heading', { name: 'CQ-0001' })).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });
});
