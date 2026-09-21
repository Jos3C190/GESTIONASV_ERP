import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderReceivingAction from '$lib/features/purchase-orders/components/PurchaseOrderReceivingAction.svelte';
import type { PurchaseOrder } from '$lib/types/purchase-order';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
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
  order_date: '2026-09-20T12:00:00-06:00',
  expected_date: null,
  currency: 'USD',
  payment_terms: null,
  details: [],
  expenses: [],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  additional_expenses: '0.000000',
  total: '113.000000',
  status: 'sent',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('PurchaseOrderReceivingAction', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();
  });

  it('opens receiving for sent orders when purchase permissions are available', async () => {
    mocks.hasPermission.mockImplementation(
      (code: string) => code === 'purchases:read' || code === 'purchases:manage'
    );

    render(PurchaseOrderReceivingAction, {
      props: { order }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Registrar recepción' }));

    expect(mocks.goto).toHaveBeenCalledWith(`/purchases/new?order_id=${order.id}`);
  });

  it('allows another reception while the order is partially received', () => {
    mocks.hasPermission.mockReturnValue(true);

    render(PurchaseOrderReceivingAction, {
      props: {
        order: { ...order, status: 'partially_received' }
      }
    });

    expect(screen.getByRole('button', { name: 'Registrar recepción' })).toBeInTheDocument();
  });

  it('does not expose receiving after the order is fully received', () => {
    mocks.hasPermission.mockReturnValue(true);

    render(PurchaseOrderReceivingAction, {
      props: {
        order: { ...order, status: 'received' }
      }
    });

    expect(screen.queryByRole('button', { name: 'Registrar recepción' })).not.toBeInTheDocument();
  });

  it('does not expose receiving without both required purchase permissions', () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:manage');

    render(PurchaseOrderReceivingAction, {
      props: { order }
    });

    expect(screen.queryByRole('button', { name: 'Registrar recepción' })).not.toBeInTheDocument();
  });
});
