import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseList from '$lib/features/purchases/components/PurchaseList.svelte';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  listSuppliers: vi.fn()
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    list: mocks.list
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: mocks.listSuppliers
  }
}));

const purchase = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'COM-0001',
  purchase_order_id: '22222222-2222-2222-2222-222222222222',
  supplier_id: 25,
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  purchase_date: '2026-09-20T12:00:00-06:00',
  supplier_invoice_number: 'FAC-001',
  supplier_invoice_date: '2026-09-20',
  currency: 'USD',
  details: [],
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
  uuid: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
  code: 'PRV-025',
  name: 'Proveedor Central',
  country: 1,
  is_active: true,
  contacts: []
};

describe('PurchaseList', () => {
  beforeEach(() => {
    mocks.list.mockReset();
    mocks.listSuppliers.mockReset();

    mocks.listSuppliers.mockResolvedValue({
      items: [supplier],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
  });

  it('renders purchases and applies status and supplier filters', async () => {
    mocks.list.mockResolvedValue({
      items: [purchase],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseList);

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.getByText('Proveedor Central')).toBeInTheDocument();
    expect(screen.getByText('FAC-001')).toBeInTheDocument();
    const row = screen.getByText('COM-0001').closest('tr');
    expect(row).not.toBeNull();
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

    render(PurchaseList);

    expect(await screen.findByText('No hay compras para mostrar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
  });

  it('renders an error and retries the list request', async () => {
    mocks.list.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce({
      items: [purchase],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(PurchaseList);

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });
});
