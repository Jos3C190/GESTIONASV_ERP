import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoWorkflowActions from '$lib/features/retaceos/components/RetaceoWorkflowActions.svelte';
import type { Retaceo } from '$lib/types/retaceo';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  calculate: vi.fn(),
  verify: vi.fn(),
  cancel: vi.fn(),
  close: vi.fn(),
  apply: vi.fn(),
  valuationStatus: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    calculate: mocks.calculate,
    verify: mocks.verify,
    cancel: mocks.cancel,
    close: mocks.close,
    apply: mocks.apply,
    valuationStatus: mocks.valuationStatus
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { accessAllBranches: true } }));

const retaceo: Retaceo = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'RET-0001',
  purchase_id: '22222222-2222-2222-2222-222222222222',
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  currency: 'USD',
  details: [],
  total_fob: '100.000000',
  total_freight: '10.000000',
  total_expenses: '5.000000',
  total_dai: '3.000000',
  import_vat: '15.340000',
  total_cost: '118.000000',
  freight_percentage: '10.000000',
  expense_percentage: '5.000000',
  dai_percentage: '3.000000',
  status: 'draft',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('RetaceoWorkflowActions', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.calculate.mockReset();
    mocks.verify.mockReset();
    mocks.cancel.mockReset();
    mocks.close.mockReset();
    mocks.apply.mockReset();
    mocks.valuationStatus.mockReset().mockResolvedValue({ enabled: false });
    mocks.hasPermission.mockReset();
  });

  it('opens draft editing with retaceos:manage', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');

    render(RetaceoWorkflowActions, {
      props: {
        retaceo,
        onupdated: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Editar borrador' }));

    expect(mocks.goto).toHaveBeenCalledWith(`/retaceos/${retaceo.id}/edit`);
  });

  it('calculates a draft with retaceos:calculate', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:calculate');

    const updated: Retaceo = {
      ...retaceo,
      status: 'calculated'
    };

    mocks.calculate.mockResolvedValue(updated);
    const onupdated = vi.fn();

    render(RetaceoWorkflowActions, {
      props: { retaceo, onupdated }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Calcular retaceo' }));

    await waitFor(() => {
      expect(mocks.calculate).toHaveBeenCalledWith(retaceo.id);
      expect(onupdated).toHaveBeenCalledWith(updated);
    });
  });

  it('verifies a calculated retaceo with retaceos:verify', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:verify');

    const calculated: Retaceo = {
      ...retaceo,
      status: 'calculated'
    };

    const updated: Retaceo = {
      ...retaceo,
      status: 'verified'
    };

    mocks.verify.mockResolvedValue(updated);
    const onupdated = vi.fn();

    render(RetaceoWorkflowActions, {
      props: {
        retaceo: calculated,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Verificar retaceo' }));

    await waitFor(() => {
      expect(mocks.verify).toHaveBeenCalledWith(retaceo.id);
      expect(onupdated).toHaveBeenCalledWith(updated);
    });
  });

  it('cancels a calculated retaceo with retaceos:manage', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');

    const calculated: Retaceo = {
      ...retaceo,
      status: 'calculated'
    };

    const updated: Retaceo = {
      ...retaceo,
      status: 'cancelled'
    };

    mocks.cancel.mockResolvedValue(updated);

    render(RetaceoWorkflowActions, {
      props: {
        retaceo: calculated,
        onupdated: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar retaceo' }));

    await waitFor(() => {
      expect(mocks.cancel).toHaveBeenCalledWith(retaceo.id);
    });
  });

  it('closes a verified retaceo with retaceos:verify', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:verify');

    const verified: Retaceo = {
      ...retaceo,
      status: 'verified'
    };

    const closed: Retaceo = {
      ...retaceo,
      status: 'closed'
    };

    mocks.close.mockResolvedValue(closed);

    render(RetaceoWorkflowActions, {
      props: {
        retaceo: verified,
        onupdated: vi.fn()
      }
    });

    const closeButton = screen.getByRole('button', { name: 'Cerrar retaceo' });
    await waitFor(() => expect(closeButton).toBeEnabled());
    await fireEvent.click(closeButton);

    await waitFor(() => {
      expect(mocks.close).toHaveBeenCalledWith(retaceo.id);
    });
  });

  it('applies verified costs before offering close when valuation is enabled', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.valuationStatus.mockResolvedValue({ enabled: true });
    const applied: Retaceo = {
      ...retaceo,
      status: 'verified',
      applied_at: '2026-10-13T20:00:00Z'
    };
    mocks.apply.mockResolvedValue(applied);
    const onupdated = vi.fn();
    render(RetaceoWorkflowActions, {
      props: { retaceo: { ...retaceo, status: 'verified' }, onupdated }
    });
    await fireEvent.click(
      await screen.findByRole('button', { name: 'Aplicar costo al inventario' })
    );
    await waitFor(() => expect(onupdated).toHaveBeenCalledWith(applied));
    expect(mocks.apply).toHaveBeenCalledWith(retaceo.id);
    expect(mocks.close).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Cerrar retaceo' })).not.toBeInTheDocument();
  });

  it('offers close after costs have been applied', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.valuationStatus.mockResolvedValue({ enabled: true });
    mocks.close.mockResolvedValue({ ...retaceo, status: 'closed' });
    render(RetaceoWorkflowActions, {
      props: {
        retaceo: { ...retaceo, status: 'verified', applied_at: '2026-10-13T20:00:00Z' },
        onupdated: vi.fn()
      }
    });
    const closeButton = screen.getByRole('button', { name: 'Cerrar retaceo' });
    await waitFor(() => expect(closeButton).toBeEnabled());
    await fireEvent.click(closeButton);
    await waitFor(() => expect(mocks.close).toHaveBeenCalledWith(retaceo.id));
    expect(mocks.apply).not.toHaveBeenCalled();
  });

  it('blocks closing when valuation status cannot be checked and supports retry', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.valuationStatus.mockRejectedValueOnce(new Error('Sin conexión'));
    render(RetaceoWorkflowActions, {
      props: { retaceo: { ...retaceo, status: 'verified' }, onupdated: vi.fn() }
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión');
    expect(screen.getByRole('button', { name: 'Cerrar retaceo' })).toBeDisabled();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar consulta' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Cerrar retaceo' })).toBeEnabled()
    );
    expect(mocks.close).not.toHaveBeenCalled();
  });

  it('does not offer application without the valuation permission', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:verify');
    mocks.valuationStatus.mockResolvedValue({ enabled: true });
    render(RetaceoWorkflowActions, {
      props: { retaceo: { ...retaceo, status: 'verified' }, onupdated: vi.fn() }
    });
    await screen.findByText(/requiere permiso de valoración/);
    expect(
      screen.queryByRole('button', { name: 'Aplicar costo al inventario' })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cerrar retaceo' })).not.toBeInTheDocument();
  });

  it('does not expose workflow actions for terminal states', () => {
    mocks.hasPermission.mockReturnValue(true);

    render(RetaceoWorkflowActions, {
      props: {
        retaceo: {
          ...retaceo,
          status: 'closed'
        },
        onupdated: vi.fn()
      }
    });

    expect(screen.queryByLabelText('Acciones de retaceo')).not.toBeInTheDocument();
  });
});
