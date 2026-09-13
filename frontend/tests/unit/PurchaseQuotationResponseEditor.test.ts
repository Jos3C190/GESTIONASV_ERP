import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationResponseEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationResponseEditor.svelte';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  recordResponse: vi.fn(),
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    get: mocks.get,
    recordResponse: mocks.recordResponse
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
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
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.recordResponse.mockReset();
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_quotations:manage');
    mocks.get.mockResolvedValue(quotation);
  });

  it('records the supplier response using the requested coverage', async () => {
    mocks.recordResponse.mockResolvedValue({
      ...quotation,
      status: 'received'
    });

    render(PurchaseQuotationResponseEditor, {
      props: { id: quotation.id }
    });

    const price = await screen.findByLabelText('Precio producto 10');
    await fireEvent.input(price, { target: { value: '20' } });
    await fireEvent.input(screen.getByLabelText('Impuesto producto 10'), {
      target: { value: '13' }
    });
    await fireEvent.input(screen.getByLabelText('Términos de pago'), {
      target: { value: '30 días' }
    });

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Registrar respuesta' }).closest('form')!
    );

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
              quantity: 5,
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
        })
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
