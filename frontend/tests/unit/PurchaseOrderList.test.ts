import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderList from '$lib/features/purchase-orders/components/PurchaseOrderList.svelte';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  listSuppliers: vi.fn()
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    list: mocks.list
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: mocks.listSuppliers
  }
}));

const order = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'OC-0001',
  supplier_id: 25,
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  purchase_quotation_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  created_by_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
  order_date: '2026-09-13T12:00:00-06:00',
  expected_date: '2026-09-20T12:00:00-06:00',
  currency: 'USD',
  payment_terms: '30 días',
  details: [],
  expenses: [],
  subtotal: '100.00',
  discount: '0.00',
  tax: '13.00',
  additional_expenses: '0.00',
  total: '113.00',
  status: 'pending_approval',
  notes: null,
  created_at: null,
  updated_at: null
} as const;

const supplier = {
  id_supplier: 25,
  uuid: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
  code: 'PRV-025',
  name: 'Proveedor Central',
  country: 1,
  is_active: true,
  contacts: []
};

describe('PurchaseOrderList', () => {
  beforeEach(() => {
    mocks.list.mockReset();
    mocks.listSuppliers.mockReset();

    mocks.listSuppliers.mockResolvedValue({
      items: [supplier],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
  });

  it('renders orders and applies status and supplier filters', async () => {
    mocks.list.mockResolvedValue({
      items: [order],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseOrderList);

    expect(await screen.findByText('OC-0001')).toBeInTheDocument();
    expect(screen.getByText('Proveedor Central')).toBeInTheDocument();
    const row = screen.getByRole('link', { name: 'OC-0001' }).closest('tr')!;
    expect(row).toHaveTextContent('Pendiente de aprobación');

    const statusSelect = screen.getByLabelText('Estado') as HTMLSelectElement;
    statusSelect.value = 'pending_approval';
    await fireEvent.change(statusSelect);

    const supplierSelect = screen.getByLabelText('Proveedor') as HTMLSelectElement;
    supplierSelect.value = '25';
    await fireEvent.change(supplierSelect);

    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith({
        status: 'pending_approval',
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

    render(PurchaseOrderList);

    expect(await screen.findByText('No hay órdenes para mostrar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
  });

  it('renders an error and retries the list request', async () => {
    mocks.list.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce({
      items: [order],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseOrderList);

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('OC-0001')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });
});
