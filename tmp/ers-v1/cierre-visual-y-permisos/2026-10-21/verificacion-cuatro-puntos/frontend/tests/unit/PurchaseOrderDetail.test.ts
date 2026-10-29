import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderDetail from '$lib/features/purchase-orders/components/PurchaseOrderDetail.svelte';
import type { PurchaseOrder } from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  listExpenseTypes: vi.fn(),
  submit: vi.fn(),
  approve: vi.fn(),
  send: vi.fn(),
  cancel: vi.fn(),
  getSupplier: vi.fn(),
  getQuotation: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  getWarehouse: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    get: mocks.get,
    listExpenseTypes: mocks.listExpenseTypes,
    submit: mocks.submit,
    approve: mocks.approve,
    send: mocks.send,
    cancel: mocks.cancel
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    getSupplier: mocks.getSupplier
  }
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    get: mocks.getQuotation
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

const order: PurchaseOrder = {
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
  details: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      purchase_quotation_detail_id: '33333333-3333-3333-3333-333333333333',
      product_id: 10,
      quantity: '2.000000',
      unit_id: 2,
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
  expenses: [
    {
      id: '33333333-3333-3333-3333-333333333333',
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      expense_type_id: '77777777-7777-7777-7777-777777777777',
      amount: '5.000000',
      description: 'Flete',
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  additional_expenses: '5.000000',
  total: '118.000000',
  status: 'sent',
  notes: 'Entrega prioritaria',
  created_at: null,
  updated_at: null
};

describe('PurchaseOrderDetail', () => {
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.listExpenseTypes.mockReset();
    mocks.submit.mockReset();
    mocks.approve.mockReset();
    mocks.send.mockReset();
    mocks.cancel.mockReset();
    mocks.getSupplier.mockReset();
    mocks.getQuotation.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();
    mocks.getWarehouse.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockReturnValue(false);
    mocks.get.mockResolvedValue(order);
    mocks.listExpenseTypes.mockResolvedValue([
      {
        id: order.expenses[0]!.expense_type_id,
        name: 'Flete nacional',
        description: null
      }
    ]);
    mocks.getSupplier.mockResolvedValue({
      id_supplier: 25,
      code: 'PRV-025',
      name: 'Proveedor Central'
    });
    mocks.getQuotation.mockResolvedValue({
      id: order.purchase_quotation_id,
      code: 'CQ-0007'
    });
    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 2,
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
      id: order.warehouse_id,
      code: 'ALM-01',
      name: 'Almacén principal'
    });
  });

  it('renders readable related data and backend-provided totals', async () => {
    render(PurchaseOrderDetail, {
      props: { id: order.id }
    });

    expect(await screen.findByText('OC-0001')).toBeInTheDocument();
    expect(screen.getAllByText('PRV-025 — Proveedor Central').length).toBeGreaterThan(0);
    expect(screen.getByText('CENTRO — Sucursal Centro')).toBeInTheDocument();
    expect(screen.getByText('ALM-01 — Almacén principal')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'CQ-0007' })).toHaveAttribute(
      'href',
      `/purchase-quotations/${order.purchase_quotation_id}`
    );
    expect(screen.getByText('PROD-10 — Producto A')).toBeInTheDocument();
    expect(screen.getByText('UND — Unidad')).toBeInTheDocument();
    expect(screen.getByText('Flete')).toBeInTheDocument();
    expect(screen.getByText('Tipo de gasto: Flete nacional')).toBeInTheDocument();
    expect(document.body.textContent).toContain('118');
  });

  it('renders an error and retries the order request', async () => {
    mocks.get.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce(order);

    render(PurchaseOrderDetail, {
      props: { id: order.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('OC-0001')).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });
});
