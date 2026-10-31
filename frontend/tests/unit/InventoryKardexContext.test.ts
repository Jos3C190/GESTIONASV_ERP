import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KardexPage from '../../src/routes/(app)/inventory/kardex/+page.svelte';
import { branch } from '$lib/stores/branch.svelte';
import { company } from '$lib/stores/company.svelte';
import { permissions } from '$lib/stores/permissions.svelte';

const mocks = vi.hoisted(() => ({
  getWarehouses: vi.fn(),
  searchItems: vi.fn(),
  physical: vi.fn(),
  reconciliation: vi.fn(),
  valued: vi.fn()
}));

vi.mock('$app/state', () => ({
  page: { url: new URL('http://localhost/inventory/kardex'), params: {} }
}));
vi.mock('$lib/services/warehouses', () => ({ getWarehouses: mocks.getWarehouses }));
vi.mock('$lib/features/inventory/kardex', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  kardexApi: {
    searchItems: mocks.searchItems,
    physical: mocks.physical,
    reconciliation: mocks.reconciliation,
    valued: mocks.valued
  }
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function reconciliationResult() {
  return {
    valuation_enabled: true,
    currency: 'USD',
    items: [
      {
        inventory_item_id: 'item-1',
        product_name: 'Chocolate',
        sku: 'PRD-001',
        base_unit_symbol: 'cj',
        physical_quantity: '10',
        valued_quantity: '10',
        quantity_difference: '0',
        inventory_value: '42.10',
        average_unit_cost: '4.21'
      }
    ],
    page: 1,
    page_size: 50,
    total: 1
  };
}

function valuedResult() {
  return {
    inventory_item_id: 'item-1',
    setting: { currency: 'USD', opened_at: '2026-10-01', opening_reference: 'CORTE-1' },
    period_from: '2026-10-01',
    period_to: '2026-10-15',
    opening_known: true,
    opening_quantity: '10',
    opening_value: '42.10',
    closing_known: true,
    closing_quantity: '10',
    closing_value: '42.10',
    period_value_change: '42.10',
    entries: [],
    page: 1,
    page_size: 25,
    total: 0
  };
}

function setGlobalAccess() {
  company.select({ id: 'company-1', name: 'Empresa uno', commercial_name: 'Uno', logo: null });
  branch.configure({
    company_id: 'company-1',
    access_all_branches: true,
    last_branch_id: 'branch-1',
    branches: [
      {
        id: 'branch-1',
        company_id: 'company-1',
        name: 'Sucursal uno',
        code: 'S1',
        is_active: true
      },
      { id: 'branch-2', company_id: 'company-1', name: 'Sucursal dos', code: 'S2', is_active: true }
    ]
  });
  permissions.set(['inventory:read', 'inventory:valuation'], false);
}

async function openValuedKardex() {
  fireEvent.click(await screen.findByRole('tab', { name: 'Conciliación' }));
  await screen.findAllByText('Chocolate');
  fireEvent.click(screen.getAllByRole('button', { name: 'Ver Kardex de Chocolate' })[0]!);
  await waitFor(() => expect(mocks.valued).toHaveBeenCalledOnce());
}

describe('Kardex valorado y cambio de alcance', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    company.clear();
    branch.clear();
    permissions.clear();
    setGlobalAccess();
    mocks.getWarehouses.mockResolvedValue({
      items: [{ id: 'warehouse-1', code: 'BOD-001', name: 'Bodega central', status: 'active' }]
    });
    mocks.searchItems.mockResolvedValue([]);
    mocks.physical.mockResolvedValue({ items: [], page: 1, page_size: 25, total: 0 });
    mocks.reconciliation.mockResolvedValue(reconciliationResult());
  });

  it.each(['branch', 'company', 'permission'] as const)(
    'descarta una respuesta valorada pendiente al cambiar %s',
    async (change) => {
      const valued = deferred<ReturnType<typeof valuedResult>>();
      mocks.valued.mockReturnValueOnce(valued.promise);
      render(KardexPage);
      await openValuedKardex();

      if (change === 'branch') {
        branch.select('branch-2');
      } else if (change === 'company') {
        company.select({
          id: 'company-2',
          name: 'Empresa dos',
          commercial_name: 'Dos',
          logo: null
        });
      } else {
        permissions.set(['inventory:read'], false);
      }

      await waitFor(() =>
        expect(screen.queryByText('Consultando movimientos de costo…')).not.toBeInTheDocument()
      );
      valued.resolve(valuedResult());
      await waitFor(() => expect(screen.queryByText('Saldo anterior')).not.toBeInTheDocument());
      expect(screen.queryByText('USD 42.10')).not.toBeInTheDocument();
    }
  );

  it('ignora también un error tardío del alcance anterior', async () => {
    const valued = deferred<ReturnType<typeof valuedResult>>();
    mocks.valued.mockReturnValueOnce(valued.promise);
    render(KardexPage);
    await openValuedKardex();

    branch.select('branch-2');
    await waitFor(() =>
      expect(screen.queryByText('Consultando movimientos de costo…')).not.toBeInTheDocument()
    );
    valued.reject(new Error('Error de la sucursal anterior'));

    await waitFor(() =>
      expect(screen.queryByText('Error de la sucursal anterior')).not.toBeInTheDocument()
    );
    expect(screen.queryByText('Saldo anterior')).not.toBeInTheDocument();
  });

  it('no aplica el resultado si la página se desmonta durante la consulta', async () => {
    const valued = deferred<ReturnType<typeof valuedResult>>();
    mocks.valued.mockReturnValueOnce(valued.promise);
    const view = render(KardexPage);
    await openValuedKardex();
    view.unmount();
    valued.resolve(valuedResult());
    await waitFor(() => expect(mocks.valued).toHaveBeenCalledOnce());
  });
});
