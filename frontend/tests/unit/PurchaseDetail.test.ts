import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseDetail from '$lib/features/purchases/components/PurchaseDetail.svelte';
import type { Purchase } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  receive: vi.fn(),
  verify: vi.fn(),
  cancel: vi.fn(),
  close: vi.fn(),
  getSupplier: vi.fn(),
  getOrder: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  getWarehouse: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.get,
    receive: mocks.receive,
    verify: mocks.verify,
    cancel: mocks.cancel,
    close: mocks.close
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    getSupplier: mocks.getSupplier
  }
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    get: mocks.getOrder
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: mocks.listUnits,
    getProduct: mocks.getProduct
  }
}));

vi.mock('$lib/services/warehouses', () => ({
  getWarehouse: mocks.getWarehouse
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    branches: [
      {
        id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        code: 'CENTRO',
        name: 'Sucursal Centro',
        is_active: true
      }
    ]
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const purchase: Purchase = {
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
  details: [
    {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      purchase_id: '11111111-1111-1111-1111-111111111111',
      purchase_order_detail_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      product_id: 10,
      quantity_ordered: '5.000000',
      quantity_received: '2.000000',
      unit_id: 3,
      unit_price: '50.000000',
      discount: '0.000000',
      subtotal: '100.000000',
      tax_rate: '13.000000',
      tax_amount: '13.000000',
      total: '113.000000',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'draft',
  notes: 'Recepción parcial',
  created_at: null,
  updated_at: null
};

describe('PurchaseDetail', () => {
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.receive.mockReset();
    mocks.verify.mockReset();
    mocks.cancel.mockReset();
    mocks.close.mockReset();
    mocks.getSupplier.mockReset();
    mocks.getOrder.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();
    mocks.getWarehouse.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockReturnValue(false);
    mocks.get.mockResolvedValue(purchase);

    mocks.getSupplier.mockResolvedValue({
      id_supplier: 25,
      code: 'PRV-025',
      name: 'Proveedor Central'
    });

    mocks.getOrder.mockResolvedValue({
      id: purchase.purchase_order_id,
      code: 'OC-0001'
    });

    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 3,
        code: 'UND',
        name: 'Unidad'
      }
    ]);

    mocks.getProduct.mockResolvedValue({
      id_product: 10,
      sku: 'PROD-10',
      name: 'Producto A'
    });

    mocks.getWarehouse.mockResolvedValue({
      id: purchase.warehouse_id,
      code: 'ALM-01',
      name: 'Almacén principal'
    });
  });

  it('renders readable purchase data and source-order traceability', async () => {
    render(PurchaseDetail, {
      props: { id: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.getAllByText('PRV-025 — Proveedor Central').length).toBeGreaterThan(0);
    expect(screen.getByText('CENTRO — Sucursal Centro')).toBeInTheDocument();
    expect(screen.getByText('ALM-01 — Almacén principal')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'OC-0001' })).toHaveAttribute(
      'href',
      `/purchase-orders/${purchase.purchase_order_id}`
    );

    expect(screen.getByText('PROD-10 — Producto A')).toBeInTheDocument();
    expect(screen.getByText('UND — Unidad')).toBeInTheDocument();
    expect(screen.getByText('FAC-001')).toBeInTheDocument();
    expect(document.body.textContent).toContain('113');
  });

  it('exposes retaceo creation for eligible purchases with manage permission', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');
    mocks.get.mockResolvedValue({
      ...purchase,
      status: 'received'
    });

    render(PurchaseDetail, {
      props: { id: purchase.id }
    });

    const link = await screen.findByRole('link', { name: 'Crear retaceo' });

    expect(link).toHaveAttribute('href', `/retaceos/new?purchase_id=${purchase.id}`);
  });

  it('does not expose retaceo creation for a draft purchase', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');

    render(PurchaseDetail, {
      props: { id: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Crear retaceo' })).not.toBeInTheDocument();
  });

  it('does not expose retaceo creation without retaceos:manage', async () => {
    mocks.get.mockResolvedValue({
      ...purchase,
      status: 'received'
    });

    render(PurchaseDetail, {
      props: { id: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Crear retaceo' })).not.toBeInTheDocument();
  });

  it('renders an error and retries the purchase request', async () => {
    mocks.get.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce(purchase);

    render(PurchaseDetail, {
      props: { id: purchase.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });
});
