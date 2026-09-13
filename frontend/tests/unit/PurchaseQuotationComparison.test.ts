import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationComparison from '$lib/features/purchase-quotations/components/PurchaseQuotationComparison.svelte';

const mocks = vi.hoisted(() => ({
  compare: vi.fn(),
  listSuppliers: vi.fn(),
  currencies: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    compare: mocks.compare
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: mocks.listSuppliers,
    currencies: mocks.currencies
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const requestId = '11111111-1111-1111-1111-111111111111';

describe('PurchaseQuotationComparison', () => {
  beforeEach(() => {
    mocks.compare.mockReset();
    mocks.listSuppliers.mockReset();
    mocks.currencies.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_quotations:read');

    mocks.listSuppliers.mockResolvedValue({
      items: [
        {
          id_supplier: 25,
          uuid: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          code: 'PRV-025',
          name: 'Proveedor Central',
          country: 1,
          is_active: true,
          contacts: []
        },
        {
          id_supplier: 30,
          uuid: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          code: 'PRV-030',
          name: 'Proveedor Alterno',
          country: 1,
          is_active: true,
          contacts: []
        }
      ],
      meta: { page: 1, size: 100, total: 2, pages: 1 }
    });

    mocks.currencies.mockResolvedValue([
      {
        code: 'USD',
        name: 'Dólar estadounidense',
        symbol: '$',
        decimal_places: 2,
        is_active: true
      }
    ]);
  });

  it('renders the backend comparison order and supplier names', async () => {
    mocks.compare.mockResolvedValue([
      {
        quotation_id: '22222222-2222-2222-2222-222222222222',
        code: 'CQ-0002',
        supplier_id: 30,
        currency: 'USD',
        total: '100.000000',
        delivery_days: 3,
        valid_until: '2026-09-30T12:00:00-06:00',
        status: 'received'
      },
      {
        quotation_id: '33333333-3333-3333-3333-333333333333',
        code: 'CQ-0003',
        supplier_id: 25,
        currency: 'USD',
        total: '110.000000',
        delivery_days: 2,
        valid_until: null,
        status: 'under_evaluation'
      }
    ]);

    render(PurchaseQuotationComparison, {
      props: { requestId }
    });

    const firstQuotation = await screen.findByRole('link', { name: 'CQ-0002' });
    const firstRow = firstQuotation.closest('tr')!;
    expect(within(firstRow).getByText('#1')).toBeInTheDocument();
    expect(within(firstRow).getByText('Proveedor Alterno')).toBeInTheDocument();
    expect(within(firstRow).getByText('$100.00')).toBeInTheDocument();

    expect(mocks.compare).toHaveBeenCalledWith(requestId, undefined);
  });

  it('requeries the backend when a currency is selected', async () => {
    mocks.compare.mockResolvedValue([]);

    render(PurchaseQuotationComparison, {
      props: { requestId }
    });

    const select = (await screen.findByLabelText('Moneda de comparación')) as HTMLSelectElement;
    select.value = 'USD';
    await fireEvent.change(select);

    expect(mocks.compare).toHaveBeenLastCalledWith(requestId, 'USD');
  });

  it('shows backend comparison errors and keeps the currency filter available', async () => {
    mocks.compare.mockRejectedValue(
      new Error(
        'No se pueden comparar importes de cotizaciones en monedas distintas sin conversión.'
      )
    );

    render(PurchaseQuotationComparison, {
      props: { requestId }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pueden comparar importes de cotizaciones en monedas distintas sin conversión.'
    );
    expect(screen.getByLabelText('Moneda de comparación')).toBeInTheDocument();
  });

  it('blocks direct access without read permission', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(PurchaseQuotationComparison, {
      props: { requestId }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para consultar cotizaciones de compra.'
    );
    expect(mocks.compare).not.toHaveBeenCalled();
  });
});
