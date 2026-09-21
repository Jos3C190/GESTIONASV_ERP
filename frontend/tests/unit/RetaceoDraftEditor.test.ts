import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoDraftEditor from '$lib/features/retaceos/components/RetaceoDraftEditor.svelte';
import type { Retaceo } from '$lib/types/retaceo';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  getRetaceo: vi.fn(),
  update: vi.fn(),
  getPurchase: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    get: mocks.getRetaceo,
    update: mocks.update
  }
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.getPurchase
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

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
  notes: 'Inicial',
  created_at: null,
  updated_at: null
};

describe('RetaceoDraftEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.getRetaceo.mockReset();
    mocks.update.mockReset();
    mocks.getPurchase.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');
    mocks.getRetaceo.mockResolvedValue(retaceo);
    mocks.getPurchase.mockResolvedValue({
      id: retaceo.purchase_id,
      code: 'COM-0001'
    });
  });

  it('updates a draft and redirects to its detail', async () => {
    mocks.update.mockResolvedValue({
      ...retaceo,
      total_freight: '12.000000',
      notes: 'Actualizado'
    });

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(await screen.findByText('Editar RET-0001')).toBeInTheDocument();
    expect(screen.getByText('COM-0001')).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText('Flete'), {
      target: { value: '12.000000' }
    });

    await fireEvent.input(screen.getByLabelText('Notas'), {
      target: { value: 'Actualizado' }
    });

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(retaceo.id, {
        total_freight: '12.000000',
        total_expenses: '5.000000',
        total_dai: '3.000000',
        import_vat: '15.340000',
        notes: 'Actualizado'
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/retaceos/${retaceo.id}`);
  });

  it('blocks editing for a non-draft retaceo', async () => {
    mocks.getRetaceo.mockResolvedValue({
      ...retaceo,
      status: 'calculated'
    });

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Solo los retaceos en borrador pueden editarse.'
    );

    expect(mocks.getPurchase).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument();
  });

  it('blocks editing without retaceos:manage', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar retaceos.'
    );

    expect(mocks.getRetaceo).not.toHaveBeenCalled();
  });
});
