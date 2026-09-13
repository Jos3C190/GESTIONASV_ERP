import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationList from '$lib/features/purchase-quotations/components/PurchaseQuotationList.svelte';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  listSuppliers: vi.fn()
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    list: mocks.list
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: mocks.listSuppliers
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
  details: [],
  expenses: [],
  valid_until: null,
  payment_terms: null,
  delivery_days: null,
  subtotal: '100.00',
  discount: '0.00',
  tax: '13.00',
  total: '113.00',
  status: 'received',
  notes: null,
  created_at: null,
  updated_at: null
} as const;

const supplier = {
  id_supplier: 25,
  uuid: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  code: 'PRV-025',
  name: 'Proveedor Central',
  country: 1,
  is_active: true,
  contacts: []
};

describe('PurchaseQuotationList', () => {
  beforeEach(() => {
    mocks.list.mockReset();
    mocks.listSuppliers.mockReset();

    mocks.listSuppliers.mockResolvedValue({
      items: [supplier],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
  });

  it('renders quotations and applies status and supplier filters', async () => {
    mocks.list.mockResolvedValue({
      items: [quotation],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseQuotationList);

    expect(await screen.findByText('CQ-0001')).toBeInTheDocument();
    expect(screen.getByText('Proveedor Central')).toBeInTheDocument();
    const row = screen.getByRole('link', { name: 'CQ-0001' }).closest('tr')!;
    expect(row).toHaveTextContent('Recibida');

    const statusSelect = screen.getByLabelText('Estado') as HTMLSelectElement;
    statusSelect.value = 'received';
    await fireEvent.change(statusSelect);

    const supplierSelect = screen.getByLabelText('Proveedor') as HTMLSelectElement;
    supplierSelect.value = '25';
    await fireEvent.change(supplierSelect);

    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith({
        status: 'received',
        supplier_id: 25,
        page: 1,
        size: 20
      });
    });
  });

  it('renders the empty state', async () => {
    mocks.list.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });

    render(PurchaseQuotationList);

    expect(await screen.findByText('No hay cotizaciones para mostrar')).toBeInTheDocument();
  });

  it('renders an error and retries the list request', async () => {
    mocks.list.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce({
      items: [quotation],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseQuotationList);

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('CQ-0001')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });
});
