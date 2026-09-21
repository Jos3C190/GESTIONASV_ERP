import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseDraftEditor from '$lib/features/purchases/components/PurchaseDraftEditor.svelte';
import type { Purchase, PurchaseReceivable } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  get: vi.fn(),
  getReceivable: vi.fn(),
  update: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.get,
    getReceivable: mocks.getReceivable,
    update: mocks.update
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: mocks.listUnits,
    getProduct: mocks.getProduct
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
      unit_price: '10.000000',
      discount: '0.000000',
      subtotal: '20.000000',
      tax_rate: '13.000000',
      tax_amount: '2.600000',
      total: '22.600000',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '20.000000',
  discount: '0.000000',
  tax: '2.600000',
  total: '22.600000',
  status: 'draft',
  notes: 'Inicial',
  created_at: null,
  updated_at: null
};

const receivable: PurchaseReceivable = {
  purchase_order_id: purchase.purchase_order_id,
  code: 'OC-0001',
  status: 'partially_received',
  supplier_id: 25,
  branch_id: purchase.branch_id,
  warehouse_id: purchase.warehouse_id,
  currency: 'USD',
  lines: [
    {
      purchase_order_detail_id: purchase.details[0]!.purchase_order_detail_id,
      product_id: 10,
      unit_id: 3,
      quantity_ordered: '5.000000',
      quantity_received: '1.000000',
      quantity_pending: '4.000000',
      unit_price: '10.000000',
      discount: '0.000000',
      tax_rate: '13.000000',
      notes: null
    },
    {
      purchase_order_detail_id: '99999999-9999-9999-9999-999999999999',
      product_id: 11,
      unit_id: 3,
      quantity_ordered: '3.000000',
      quantity_received: '0.000000',
      quantity_pending: '3.000000',
      unit_price: '8.000000',
      discount: '0.000000',
      tax_rate: '13.000000',
      notes: null
    }
  ]
};

describe('PurchaseDraftEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.get.mockReset();
    mocks.getReceivable.mockReset();
    mocks.update.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:manage');

    mocks.get.mockResolvedValue(purchase);
    mocks.getReceivable.mockResolvedValue(receivable);

    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 3,
        code: 'UND',
        name: 'Unidad'
      }
    ]);

    mocks.getProduct.mockImplementation((id: number) =>
      Promise.resolve({
        id_product: id,
        sku: `SKU-${id}`,
        name: `Producto ${id}`
      })
    );
  });

  it('updates the draft using exact purchase-order-detail identity', async () => {
    mocks.update.mockResolvedValue({
      ...purchase,
      supplier_invoice_number: 'FAC-EDIT'
    });

    render(PurchaseDraftEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText(`Editar ${purchase.code}`)).toBeInTheDocument();

    const firstQuantity = screen.getByRole('spinbutton', {
      name: 'Cantidad a recibir línea 1'
    });

    expect(firstQuantity).toHaveValue(2);

    await fireEvent.input(firstQuantity, {
      target: { value: '3' }
    });

    await fireEvent.input(
      screen.getByRole('textbox', {
        name: 'Factura del proveedor'
      }),
      {
        target: { value: 'FAC-EDIT' }
      }
    );

    await fireEvent.submit(
      screen
        .getByRole('button', {
          name: 'Guardar cambios'
        })
        .closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(purchase.id, {
        supplier_invoice_number: 'FAC-EDIT',
        supplier_invoice_date: '2026-09-20',
        lines: [
          {
            purchase_order_detail_id: purchase.details[0]!.purchase_order_detail_id,
            quantity_received: 3
          }
        ],
        notes: 'Inicial'
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/purchases/${purchase.id}`);
  });

  it('shows backend-confirmed received and pending quantities without counting the draft twice', async () => {
    render(PurchaseDraftEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText(`Editar ${purchase.code}`)).toBeInTheDocument();

    const row = screen.getByText('SKU-10 — Producto 10').closest('tr');

    expect(row).not.toBeNull();
    expect(row).toHaveTextContent('5');
    expect(row).toHaveTextContent('1');
    expect(row).toHaveTextContent('4');

    expect(
      screen.getByRole('spinbutton', {
        name: 'Cantidad a recibir línea 1'
      })
    ).toHaveValue(2);

    expect(
      screen.getByRole('checkbox', {
        name: 'Incluir línea 2'
      })
    ).not.toBeChecked();
  });

  it('blocks editing for a non-draft purchase', async () => {
    mocks.get.mockResolvedValue({
      ...purchase,
      status: 'received'
    });

    render(PurchaseDraftEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Solo las compras en borrador pueden editarse.'
    );

    expect(mocks.getReceivable).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', {
        name: 'Guardar cambios'
      })
    ).not.toBeInTheDocument();
  });

  it('blocks editing without purchases:manage', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(PurchaseDraftEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar recepciones de compra.'
    );

    expect(mocks.get).not.toHaveBeenCalled();
  });
});
