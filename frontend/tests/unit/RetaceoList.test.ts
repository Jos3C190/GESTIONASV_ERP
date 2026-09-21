import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoList from '$lib/features/retaceos/components/RetaceoList.svelte';

const mocks = vi.hoisted(() => ({
  list: vi.fn()
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    list: mocks.list
  }
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    ready: true,
    id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
  }
}));

const retaceo = {
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
  status: 'calculated',
  notes: null,
  created_at: '2026-09-20T12:00:00-06:00',
  updated_at: null
} as const;

describe('RetaceoList', () => {
  beforeEach(() => {
    mocks.list.mockReset();
  });

  it('renders retaceos and applies status and branch scope', async () => {
    mocks.list.mockResolvedValue({
      items: [retaceo],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(RetaceoList);

    expect(await screen.findByText('RET-0001')).toBeInTheDocument();

    const row = screen.getByText('RET-0001').closest('tr');
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent('Calculado');

    expect(screen.getByRole('link', { name: 'Abrir compra' })).toHaveAttribute(
      'href',
      `/purchases/${retaceo.purchase_id}`
    );

    const statusSelect = screen.getByLabelText('Estado') as HTMLSelectElement;
    statusSelect.value = 'calculated';
    await fireEvent.change(statusSelect);

    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith({
        status: 'calculated',
        branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        page: 1,
        size: 20
      });
    });
  });

  it('renders the empty state', async () => {
    mocks.list.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });

    render(RetaceoList);

    expect(await screen.findByText('No hay retaceos para mostrar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
  });

  it('renders an error and retries the list request', async () => {
    mocks.list.mockRejectedValueOnce(new Error('No disponible')).mockResolvedValueOnce({
      items: [retaceo],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });

    render(RetaceoList);

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('RET-0001')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });
});
