import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderDraftEditor from '$lib/features/purchase-orders/components/PurchaseOrderDraftEditor.svelte';
import type { PurchaseOrder } from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  get: vi.fn(),
  update: vi.fn(),
  listExpenseTypes: vi.fn(),
  getWarehouses: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    get: mocks.get,
    update: mocks.update,
    listExpenseTypes: mocks.listExpenseTypes
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: mocks.listUnits,
    getProduct: mocks.getProduct
  }
}));

vi.mock('$lib/services/warehouses', () => ({ getWarehouses: mocks.getWarehouses }));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    branches: [
      {
        id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        code: 'SS',
        name: 'San Salvador',
        is_active: true
      }
    ]
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: mocks.hasPermission }
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
  payment_terms: null,
  details: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      purchase_quotation_detail_id: '33333333-3333-3333-3333-333333333333',
      product_id: 10,
      quantity: '2.000000',
      unit_id: 2,
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
  expenses: [
    {
      id: '77777777-7777-7777-7777-777777777777',
      purchase_order_id: '11111111-1111-1111-1111-111111111111',
      expense_type_id: '88888888-8888-8888-8888-888888888888',
      amount: '3.500000',
      description: 'Flete',
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '20.000000',
  discount: '0.000000',
  tax: '2.600000',
  additional_expenses: '3.500000',
  total: '26.100000',
  status: 'draft',
  notes: 'Inicial',
  created_at: null,
  updated_at: null
};

const awardedOrder: PurchaseOrder = {
  ...order,
  details: [
    {
      ...order.details[0]!,
      purchase_consolidation_award_id: '99999999-9999-9999-9999-999999999999'
    }
  ]
};

describe('PurchaseOrderDraftEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.get.mockReset();
    mocks.update.mockReset();
    mocks.listExpenseTypes.mockReset();
    mocks.getWarehouses.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_orders:manage');
    mocks.get.mockResolvedValue(order);
    mocks.listExpenseTypes.mockResolvedValue([
      {
        id: order.expenses[0]!.expense_type_id,
        name: 'Flete',
        description: null
      }
    ]);
    mocks.getWarehouses.mockResolvedValue({
      items: [
        {
          id: order.warehouse_id,
          branchId: order.branch_id,
          code: 'ALM',
          name: 'Principal'
        }
      ]
    });
    mocks.listUnits.mockResolvedValue([{ id_unit: 2, code: 'UND', name: 'Unidad' }]);
    mocks.getProduct.mockResolvedValue({ id_product: 10, sku: 'SKU-10', name: 'Producto 10' });
  });

  it('updates a draft with the persisted quotation-detail identity', async () => {
    mocks.update.mockResolvedValue({ ...order, notes: 'Actualizada' });

    render(PurchaseOrderDraftEditor, { props: { orderId: order.id } });

    expect(await screen.findByText(`Editar ${order.code}`)).toBeInTheDocument();

    await fireEvent.input(
      screen.getByRole('spinbutton', { name: 'Cantidad de SKU-10 — Producto 10' }),
      {
        target: { value: '1.5' }
      }
    );
    await fireEvent.input(screen.getByRole('textbox', { name: 'Notas' }), {
      target: { value: 'Actualizada' }
    });
    expect(screen.getByRole('option', { name: 'Flete' })).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText('Monto gasto 1'), {
      target: { value: '4.25' }
    });
    await fireEvent.input(screen.getByLabelText('Descripción gasto 1'), {
      target: { value: 'Flete actualizado' }
    });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(
        order.id,
        expect.objectContaining({
          lines: [
            {
              purchase_quotation_detail_id: order.details[0]!.purchase_quotation_detail_id,
              quantity: 1.5,
              purchase_consolidation_award_id: null
            }
          ],
          expenses: [
            {
              expense_type_id: order.expenses[0]!.expense_type_id,
              amount: 4.25,
              description: 'Flete actualizado'
            }
          ],
          notes: 'Actualizada'
        })
      );
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-orders/${order.id}`);
  });

  it('blocks editing for a non-draft order', async () => {
    mocks.get.mockResolvedValue({ ...order, status: 'approved' });

    render(PurchaseOrderDraftEditor, { props: { orderId: order.id } });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Solo las órdenes en borrador pueden editarse.'
    );
    expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument();
  });

  it('associates quantity validation with the product input', async () => {
    render(PurchaseOrderDraftEditor, { props: { orderId: order.id } });

    const quantity = await screen.findByRole('spinbutton', {
      name: 'Cantidad de SKU-10 — Producto 10'
    });
    await fireEvent.input(quantity, { target: { value: '0' } });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() => expect(quantity).toHaveAttribute('aria-invalid', 'true'));
    const errorId = quantity.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    expect(document.getElementById(errorId!)).toHaveTextContent(
      'La cantidad debe ser mayor que cero.'
    );
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('explains what to do when an order draft has no lines', async () => {
    mocks.get.mockResolvedValue({ ...order, details: [] });

    render(PurchaseOrderDraftEditor, { props: { orderId: order.id } });

    expect(await screen.findByText('Este borrador no tiene líneas de compra.')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Abrir detalle para revisar la orden' })
    ).toHaveAttribute('href', `/purchase-orders/${order.id}`);
    expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled();
  });

  it('keeps awarded order quantities and line membership locked while allowing metadata edits', async () => {
    mocks.get.mockResolvedValue(awardedOrder);
    mocks.update.mockResolvedValue(awardedOrder);

    render(PurchaseOrderDraftEditor, { props: { orderId: awardedOrder.id } });

    expect(
      await screen.findByText(/Sus líneas y cantidades están protegidas/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Incluir SKU-10 — Producto 10' })).toBeDisabled();
    expect(
      screen.getByRole('spinbutton', { name: 'Cantidad de SKU-10 — Producto 10' })
    ).toBeDisabled();

    await fireEvent.input(screen.getByRole('textbox', { name: 'Notas' }), {
      target: { value: 'Cambió la fecha de recepción' }
    });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() =>
      expect(mocks.update).toHaveBeenCalledWith(
        awardedOrder.id,
        expect.objectContaining({
          lines: [
            {
              purchase_quotation_detail_id: awardedOrder.details[0]!.purchase_quotation_detail_id,
              quantity: 2,
              purchase_consolidation_award_id:
                awardedOrder.details[0]!.purchase_consolidation_award_id
            }
          ],
          notes: 'Cambió la fecha de recepción'
        })
      )
    );
  });

  it('blocks editing without manage permission', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(PurchaseOrderDraftEditor, { props: { orderId: order.id } });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar órdenes de compra.'
    );
    expect(mocks.get).not.toHaveBeenCalled();
  });
});
