import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KardexPage from '../../src/routes/(app)/inventory/kardex/+page.svelte';
import { HttpError } from '$lib/api/client';

const mocks = vi.hoisted(() => ({
  getWarehouses: vi.fn(),
  searchItems: vi.fn(),
  physical: vi.fn(),
  reconciliation: vi.fn(),
  valued: vi.fn(),
  accessAllBranches: false
}));

vi.mock('$lib/services/warehouses', () => ({ getWarehouses: mocks.getWarehouses }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: 'branch-1',
    get accessAllBranches() {
      return mocks.accessAllBranches;
    }
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: (permission: string) =>
      permission === 'inventory:read' ||
      (permission === 'inventory:valuation' && mocks.accessAllBranches)
  }
}));
vi.mock('$lib/features/inventory/kardex', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  kardexApi: {
    searchItems: mocks.searchItems,
    physical: mocks.physical,
    reconciliation: mocks.reconciliation,
    valued: mocks.valued
  }
}));

describe('Kardex page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.accessAllBranches = false;
    mocks.getWarehouses.mockResolvedValue({
      items: [{ id: 'warehouse-1', code: 'BOD-001', name: 'Bodega Central', status: 'active' }],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
    mocks.searchItems
      .mockRejectedValueOnce(
        new HttpError('unavailable', 'Servicio temporalmente no disponible', 503)
      )
      .mockResolvedValue([
        {
          inventory_item_id: 'item-1',
          product_name: 'Chocolate',
          sku: 'PRD-001',
          base_unit_symbol: 'cj'
        }
      ]);
  });

  it('explica los filtros sin coincidencias y permite limpiarlos conservando el corte', async () => {
    mocks.accessAllBranches = true;
    mocks.reconciliation.mockResolvedValue({
      valuation_enabled: true,
      currency: 'USD',
      items: [],
      page: 1,
      page_size: 50,
      total: 0
    });
    render(KardexPage);
    await fireEvent.click(screen.getByRole('tab', { name: 'Conciliación' }));
    await screen.findByText('No hay artículos de inventario para mostrar');
    const date = (screen.getByLabelText('Corte por fecha de registro') as HTMLInputElement).value;
    await fireEvent.input(screen.getByLabelText('Producto o código'), {
      target: { value: 'No existe' }
    });
    await fireEvent.click(screen.getByRole('checkbox', { name: 'Con diferencia o sin base' }));
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Consultar corte' }).closest('form')!
    );
    expect(await screen.findByText('Sin coincidencias con estos filtros')).toBeInTheDocument();
    await fireEvent.click(
      screen.getByRole('button', { name: 'Quitar filtros de producto y estado' })
    );
    await waitFor(() => expect(screen.getByLabelText('Producto o código')).toHaveValue(''));
    expect(screen.getByRole('checkbox', { name: 'Con diferencia o sin base' })).not.toBeChecked();
    expect(mocks.reconciliation).toHaveBeenLastCalledWith(1, 50, {
      as_of: date,
      q: '',
      difference_only: false
    });
  });

  it('carga todas las bodegas usando el límite de paginación permitido por la API', async () => {
    mocks.getWarehouses
      .mockResolvedValueOnce({
        items: [{ id: 'warehouse-1', code: 'BOD-001', name: 'Bodega Central', status: 'active' }],
        meta: { page: 1, size: 100, total: 101, pages: 2 }
      })
      .mockResolvedValueOnce({
        items: [
          { id: 'warehouse-2', code: 'BOD-002', name: 'Bodega Secundaria', status: 'active' }
        ],
        meta: { page: 2, size: 100, total: 101, pages: 2 }
      });

    render(KardexPage);

    expect(await screen.findByText('BOD-002 · Bodega Secundaria')).toBeInTheDocument();
    expect(mocks.getWarehouses.mock.calls.slice(0, 2).map(([params]) => params)).toEqual([
      { branchId: 'branch-1', page: 1, size: 100, status: 'active' },
      { branchId: 'branch-1', page: 2, size: 100, status: 'active' }
    ]);
  });

  it('explica cómo iniciar la consulta y reintenta la búsqueda de artículos', async () => {
    render(KardexPage);

    await screen.findByText('BOD-001 · Bodega Central');
    await fireEvent.click(screen.getByRole('button', { name: 'Producto' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Servicio temporalmente no disponible'
    );
    expect(mocks.searchItems).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    await waitFor(() => expect(mocks.searchItems).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('button', { name: /Chocolate/ })).toBeInTheDocument();
    expect(screen.queryByText('Servicio temporalmente no disponible')).not.toBeInTheDocument();
  });

  it('permite recorrer las vistas con las flechas de teclado', async () => {
    mocks.accessAllBranches = true;
    render(KardexPage);

    const physicalTab = screen.getByRole('tab', { name: 'Movimientos físicos' });
    fireEvent.keyDown(physicalTab, { key: 'ArrowRight' });

    const valuationTab = screen.getByRole('tab', { name: 'Valoración' });
    await waitFor(() => expect(valuationTab).toHaveAttribute('aria-selected', 'true'));
    await waitFor(() => expect(valuationTab).toHaveFocus());
    expect(screen.getByRole('tabpanel')).toHaveAttribute(
      'aria-labelledby',
      'kardex-tab-valuation valuation-title'
    );
  });

  it('descarta un Kardex físico solicitado antes de que cambie la fecha', async () => {
    let resolvePhysical!: (value: unknown) => void;
    mocks.searchItems.mockReset().mockResolvedValue([
      {
        inventory_item_id: 'item-1',
        product_name: 'Chocolate',
        sku: 'PRD-001',
        base_unit_symbol: 'cj'
      }
    ]);
    mocks.physical.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePhysical = resolve;
      })
    );
    render(KardexPage);

    await screen.findByText('BOD-001 · Bodega Central');
    await fireEvent.click(screen.getByRole('button', { name: 'Producto' }));
    await fireEvent.click(await screen.findByRole('button', { name: /Chocolate/ }));
    await waitFor(() => expect(mocks.physical).toHaveBeenCalledOnce());

    fireEvent.input(screen.getByLabelText('Desde'), { target: { value: '2026-10-10' } });
    resolvePhysical({
      warehouse_id: 'warehouse-1',
      inventory_item_id: 'item-1',
      period_from: '2026-10-01',
      period_to: '2026-10-14',
      balance_basis: 'Corte de prueba',
      opening_known: true,
      opening_quantity: '0',
      incoming_quantity: '0',
      outgoing_quantity: '0',
      closing_known: true,
      closing_quantity: '0',
      items: [],
      page: 1,
      page_size: 25,
      total: 0
    });

    await waitFor(() =>
      expect(screen.queryByText(/0 movimiento\(s\) · Página/)).not.toBeInTheDocument()
    );
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-10-10');
  });

  it('no conserva el saldo del artículo anterior si falla la consulta valorada nueva', async () => {
    mocks.accessAllBranches = true;
    mocks.reconciliation.mockResolvedValue({
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
        },
        {
          inventory_item_id: 'item-2',
          product_name: 'Azúcar',
          sku: 'PRD-002',
          base_unit_symbol: 'cj',
          physical_quantity: '5',
          valued_quantity: '5',
          quantity_difference: '0',
          inventory_value: '15.00',
          average_unit_cost: '3.00'
        }
      ],
      page: 1,
      page_size: 50,
      total: 2
    });
    mocks.valued.mockImplementation((itemId: string) => {
      if (itemId === 'item-2')
        return Promise.reject(new HttpError('unavailable', 'Fallo de consulta para Azúcar', 503));
      return Promise.resolve({
        inventory_item_id: itemId,
        setting: { currency: 'USD', opened_at: '2026-10-01', opening_reference: 'CORTE-1' },
        period_from: '2026-10-01',
        period_to: '2026-10-14',
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
      });
    });
    render(KardexPage);

    fireEvent.click(await screen.findByRole('tab', { name: 'Conciliación' }));
    await screen.findAllByText('Chocolate');
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver Kardex de Chocolate' })[0]!);
    expect(await screen.findAllByText('USD 42.10')).not.toHaveLength(0);

    fireEvent.click(screen.getByRole('tab', { name: 'Conciliación' }));
    await screen.findAllByText('Azúcar');
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver Kardex de Azúcar' })[0]!);

    expect(await screen.findByRole('alert')).toHaveTextContent('Fallo de consulta para Azúcar');
    expect(screen.queryByText('USD 42.10')).not.toBeInTheDocument();
    expect(screen.queryByText('Saldo a la fecha final')).not.toBeInTheDocument();
  });

  it('reintenta la misma página del Kardex valorado y conserva el período', async () => {
    mocks.accessAllBranches = true;
    mocks.reconciliation.mockResolvedValue({
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
    });
    const result = (page: number) => ({
      inventory_item_id: 'item-1',
      setting: { currency: 'USD', opened_at: '2026-10-01', opening_reference: 'CORTE-1' },
      period_from: '2026-10-01',
      period_to: '2026-10-14',
      opening_known: true,
      opening_quantity: '10',
      opening_value: '42.10',
      closing_known: true,
      closing_quantity: '10',
      closing_value: '42.10',
      period_value_change: '42.10',
      entries: [
        {
          id: `entry-${page}`,
          sequence: page,
          kind: 'receipt',
          quantity_base: '1',
          source_value: '4.21',
          original_entry_id: null,
          movement_line_id: null,
          purchase_detail_id: null,
          retaceo_id: null,
          source_reference: `COMPRA-${page}`,
          operational_date: '2026-10-10',
          accounting_date: '2026-10-10',
          posted_at: '2026-10-10T12:00:00Z',
          posted_by: 'superadmin',
          inventory_delta: '4.21',
          balance_quantity: '10',
          balance_value: '42.10',
          average_unit_cost: '4.21',
          cost_breakdown: []
        }
      ],
      page,
      page_size: 25,
      total: 26
    });
    mocks.valued
      .mockResolvedValueOnce(result(1))
      .mockRejectedValueOnce(new HttpError('unavailable', 'Fallo temporal al cargar página 2', 503))
      .mockResolvedValueOnce(result(2));
    render(KardexPage);

    fireEvent.click(await screen.findByRole('tab', { name: 'Conciliación' }));
    await screen.findAllByText('Chocolate');
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver Kardex de Chocolate' })[0]!);
    expect(await screen.findByText('26 evento(s) · Página 1 de 2')).toBeInTheDocument();
    const periodFrom = (screen.getByLabelText('Desde') as HTMLInputElement).value;
    const periodTo = (screen.getByLabelText('Hasta') as HTMLInputElement).value;

    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Fallo temporal al cargar página 2');
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    await waitFor(() => expect(mocks.valued).toHaveBeenCalledTimes(3));
    expect(mocks.valued.mock.calls.map(([, query]) => query.page)).toEqual([1, 2, 2]);
    expect(mocks.valued.mock.calls[1]?.[1]).toMatchObject({
      period_from: periodFrom,
      period_to: periodTo
    });
    expect(mocks.valued.mock.calls[2]?.[1]).toMatchObject({
      period_from: periodFrom,
      period_to: periodTo
    });
    expect(await screen.findByText('26 evento(s) · Página 2 de 2')).toBeInTheDocument();
  });

  it('descarta la respuesta valorada cuando cambia el período y libera la consulta', async () => {
    mocks.accessAllBranches = true;
    mocks.reconciliation.mockResolvedValue({
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
    });
    let resolveValued!: (value: unknown) => void;
    mocks.valued.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveValued = resolve;
      })
    );
    render(KardexPage);

    fireEvent.click(await screen.findByRole('tab', { name: 'Conciliación' }));
    await screen.findAllByText('Chocolate');
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver Kardex de Chocolate' })[0]!);
    await waitFor(() => expect(mocks.valued).toHaveBeenCalledOnce());
    expect(screen.getByRole('button', { name: 'Consultando…' })).toBeDisabled();

    fireEvent.input(screen.getByLabelText('Desde'), { target: { value: '2026-10-10' } });
    expect(screen.getByRole('button', { name: 'Actualizar período' })).toBeEnabled();
    resolveValued({
      inventory_item_id: 'item-1',
      setting: { currency: 'USD', opened_at: '2026-10-01', opening_reference: 'CORTE-1' },
      period_from: '2026-09-16',
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
    });

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Actualizar período' })).toBeEnabled()
    );
    expect(screen.queryByText('Saldo anterior')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-10-10');
  });
});
