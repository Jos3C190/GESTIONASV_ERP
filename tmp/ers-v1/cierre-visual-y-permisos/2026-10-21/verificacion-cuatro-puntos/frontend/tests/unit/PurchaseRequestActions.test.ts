import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestActions from '$lib/features/purchase-requests/components/PurchaseRequestActions.svelte';
import type { PurchaseRequest } from '$lib/types/purchase-request';

const mocks = vi.hoisted(() => ({
  submit: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  cancel: vi.fn(),
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    submit: mocks.submit,
    approve: mocks.approve,
    reject: mocks.reject,
    cancel: mocks.cancel
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const draft: PurchaseRequest = {
  id: '33333333-3333-3333-3333-333333333333',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'SC-0001',
  branch_id: '11111111-1111-1111-1111-111111111111',
  warehouse_id: '22222222-2222-2222-2222-222222222222',
  requested_by_id: '44444444-4444-4444-4444-444444444444',
  request_date: '2026-09-12T15:00:00Z',
  required_date: null,
  justification: 'Reposición de inventario',
  status: 'draft',
  notes: null,
  details: [],
  created_at: null,
  updated_at: null
};

describe('PurchaseRequestActions', () => {
  beforeEach(() => {
    mocks.submit.mockReset();
    mocks.approve.mockReset();
    mocks.reject.mockReset();
    mocks.cancel.mockReset();
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();
  });

  it('shows manage actions for a draft and submits it', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_requests:manage');

    const updated = { ...draft, status: 'submitted' } as const;
    const onupdated = vi.fn();
    mocks.submit.mockResolvedValue(updated);

    render(PurchaseRequestActions, {
      props: { item: draft, onupdated }
    });

    expect(screen.getByRole('button', { name: 'Editar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar solicitud' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar' })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Enviar a aprobación' }));

    await waitFor(() => {
      expect(mocks.submit).toHaveBeenCalledWith(draft.id);
      expect(onupdated).toHaveBeenCalledWith(updated);
    });
  });

  it('shows approval actions for a submitted request with approve permission', () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_requests:approve');

    render(PurchaseRequestActions, {
      props: { item: { ...draft, status: 'submitted' } }
    });

    expect(screen.getByRole('button', { name: 'Aprobar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar solicitud' })).not.toBeInTheDocument();
  });
});
