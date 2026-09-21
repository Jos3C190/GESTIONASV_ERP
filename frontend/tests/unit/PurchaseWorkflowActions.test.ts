import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseWorkflowActions from '$lib/features/purchases/components/PurchaseWorkflowActions.svelte';
import type { Purchase } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  receive: vi.fn(),
  verify: vi.fn(),
  cancel: vi.fn(),
  close: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    receive: mocks.receive,
    verify: mocks.verify,
    cancel: mocks.cancel,
    close: mocks.close
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
  details: [],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'draft',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('PurchaseWorkflowActions', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.receive.mockReset();
    mocks.verify.mockReset();
    mocks.cancel.mockReset();
    mocks.close.mockReset();
    mocks.hasPermission.mockReset();
  });

  it('opens draft editing for purchase managers', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:manage');

    render(PurchaseWorkflowActions, {
      props: {
        purchase,
        onupdated: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Editar borrador' }));

    expect(mocks.goto).toHaveBeenCalledWith(`/purchases/${purchase.id}/edit`);
  });

  it('confirms a draft using the receive permission', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:receive');

    const updated: Purchase = {
      ...purchase,
      status: 'received'
    };

    mocks.receive.mockResolvedValue(updated);
    const onupdated = vi.fn();

    render(PurchaseWorkflowActions, {
      props: { purchase, onupdated }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar recepción' }));

    expect(mocks.receive).toHaveBeenCalledWith(purchase.id);
    expect(onupdated).toHaveBeenCalledWith(updated);
  });

  it('verifies a received purchase with purchases:verify', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:verify');

    const received: Purchase = {
      ...purchase,
      status: 'received'
    };

    const verified: Purchase = {
      ...purchase,
      status: 'verified'
    };

    mocks.verify.mockResolvedValue(verified);
    const onupdated = vi.fn();

    render(PurchaseWorkflowActions, {
      props: {
        purchase: received,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Verificar recepción' }));

    expect(mocks.verify).toHaveBeenCalledWith(purchase.id);
    expect(onupdated).toHaveBeenCalledWith(verified);
  });

  it('closes a verified purchase with purchases:verify', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchases:verify');

    const verified: Purchase = {
      ...purchase,
      status: 'verified'
    };

    const closed: Purchase = {
      ...purchase,
      status: 'closed'
    };

    mocks.close.mockResolvedValue(closed);

    render(PurchaseWorkflowActions, {
      props: {
        purchase: verified,
        onupdated: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar recepción' }));

    expect(mocks.close).toHaveBeenCalledWith(purchase.id);
  });

  it('does not expose workflow actions for terminal states', () => {
    mocks.hasPermission.mockReturnValue(true);

    render(PurchaseWorkflowActions, {
      props: {
        purchase: { ...purchase, status: 'closed' },
        onupdated: vi.fn()
      }
    });

    expect(screen.queryByLabelText('Acciones de compra')).not.toBeInTheDocument();
  });
});
