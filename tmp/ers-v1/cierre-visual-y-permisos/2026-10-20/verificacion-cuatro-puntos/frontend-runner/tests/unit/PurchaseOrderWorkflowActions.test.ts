import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderWorkflowActions from '$lib/features/purchase-orders/components/PurchaseOrderWorkflowActions.svelte';
import type { PurchaseOrder } from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  submit: vi.fn(),
  approve: vi.fn(),
  send: vi.fn(),
  cancel: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    submit: mocks.submit,
    approve: mocks.approve,
    send: mocks.send,
    cancel: mocks.cancel
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const baseOrder: PurchaseOrder = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'OC-0001',
  supplier_id: 25,
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  purchase_quotation_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  created_by_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
  order_date: '2026-09-13T12:00:00-06:00',
  expected_date: null,
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
  expenses: [],
  subtotal: '20.000000',
  discount: '0.000000',
  tax: '2.600000',
  additional_expenses: '0.000000',
  total: '22.600000',
  status: 'draft',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('PurchaseOrderWorkflowActions', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.submit.mockReset();
    mocks.approve.mockReset();
    mocks.send.mockReset();
    mocks.cancel.mockReset();
    mocks.hasPermission.mockReset();
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_orders:manage');
  });

  it('opens draft editing only for managers', async () => {
    render(PurchaseOrderWorkflowActions, {
      props: {
        order: baseOrder,
        onupdated: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Editar' }));

    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-orders/${baseOrder.id}/edit`);
  });

  it('submits a draft and returns the updated order', async () => {
    const updated: PurchaseOrder = { ...baseOrder, status: 'pending_approval' };
    const onupdated = vi.fn();
    mocks.submit.mockResolvedValue(updated);

    render(PurchaseOrderWorkflowActions, {
      props: {
        order: baseOrder,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Enviar a aprobación' }));

    expect(mocks.submit).toHaveBeenCalledWith(baseOrder.id);
    expect(onupdated).toHaveBeenCalledWith(updated);
  });

  it('separates approval permission from manage permission', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_orders:approve');
    const updated: PurchaseOrder = { ...baseOrder, status: 'approved' };
    mocks.approve.mockResolvedValue(updated);

    render(PurchaseOrderWorkflowActions, {
      props: {
        order: { ...baseOrder, status: 'pending_approval' },
        onupdated: vi.fn()
      }
    });

    expect(screen.getByRole('button', { name: 'Aprobar orden' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar orden' })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Aprobar orden' }));
    expect(mocks.approve).toHaveBeenCalledWith(baseOrder.id);
  });

  it('separates send permission from manage permission', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_orders:send');
    const updated: PurchaseOrder = { ...baseOrder, status: 'sent' };
    mocks.send.mockResolvedValue(updated);

    render(PurchaseOrderWorkflowActions, {
      props: {
        order: { ...baseOrder, status: 'approved' },
        onupdated: vi.fn()
      }
    });

    expect(screen.getByRole('button', { name: 'Enviar al proveedor' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar orden' })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Enviar al proveedor' }));
    expect(mocks.send).toHaveBeenCalledWith(baseOrder.id);
  });

  it('does not invent workflow actions after the order has been sent', () => {
    mocks.hasPermission.mockReturnValue(true);

    render(PurchaseOrderWorkflowActions, {
      props: {
        order: { ...baseOrder, status: 'sent' },
        onupdated: vi.fn()
      }
    });

    expect(screen.queryByLabelText('Acciones de orden de compra')).not.toBeInTheDocument();
  });

  it('surfaces backend transition errors without changing the order', async () => {
    const onupdated = vi.fn();
    mocks.cancel.mockRejectedValue(new Error('Transición no permitida'));

    render(PurchaseOrderWorkflowActions, {
      props: {
        order: baseOrder,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar orden' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Transición no permitida');
    expect(onupdated).not.toHaveBeenCalled();
  });
});
