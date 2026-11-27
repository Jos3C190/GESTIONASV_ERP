import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { posShowcaseApi } = vi.hoisted(() => ({
  posShowcaseApi: {
    list: vi.fn(),
    warehouseOptions: vi.fn(),
    create: vi.fn(),
    stock: vi.fn(),
    candidates: vi.fn(),
    open: vi.fn(),
    counts: vi.fn(),
    count: vi.fn()
  }
}));
vi.mock('#lib/api/pos.ts', () => ({ posShowcaseApi, posApi: {} }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: 'b1', label: 'Centro', branches: [] }
}));

import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { PosShowcase, ShowcaseStock } from '#lib/types/pos.ts';
import { isPosWorkspace } from './workspace.ts';
import ShowcasePage from './ShowcasePage.svelte';

const SHOWCASE: PosShowcase = {
  id: 's1',
  branch_id: 'b1',
  branch_name: 'Centro',
  warehouse_id: 'w1',
  warehouse_name: 'Bodega Centro',
  location_id: 'l1',
  location_code: 'VITRINA',
  created_at: '2026-11-26T14:00:00Z'
};

function stock(extra: Partial<ShowcaseStock> = {}): ShowcaseStock {
  return {
    inventory_item_id: 'i1',
    product_name: 'Pan francés',
    sku: 'PAN-001',
    unit_symbol: 'u',
    quantity: '10.000000',
    sellable: '10.000000',
    expired: '0',
    next_expiry: '2026-11-28',
    units: [],
    ...extra
  };
}

beforeEach(() => {
  for (const fn of Object.values(posShowcaseApi)) fn.mockReset();
  posShowcaseApi.counts.mockResolvedValue([]);
});

it('crea la vitrina de la sucursal en una de sus bodegas', async () => {
  permissions.set(['pos:registers_manage'], false);
  posShowcaseApi.list.mockResolvedValueOnce([]).mockResolvedValue([SHOWCASE]);
  posShowcaseApi.warehouseOptions.mockResolvedValue([{ id: 'w1', name: 'Bodega Centro' }]);
  posShowcaseApi.create.mockResolvedValue(SHOWCASE);
  posShowcaseApi.stock.mockResolvedValue([]);
  render(ShowcasePage);

  await fireEvent.click(await screen.findByRole('button', { name: 'Crear vitrina' }));
  await waitFor(() => expect(posShowcaseApi.create).toHaveBeenCalledWith('b1', 'w1'));
  expect(await screen.findByText('La vitrina está vacía')).toBeInTheDocument();
});

it('muestra lo vendible y lo vencido por producto', async () => {
  permissions.set(['pos:sell'], false);
  posShowcaseApi.list.mockResolvedValue([SHOWCASE]);
  posShowcaseApi.stock.mockResolvedValue([stock({ sellable: '7', expired: '3' })]);
  render(ShowcasePage);

  expect(await screen.findByText('Pan francés')).toBeInTheDocument();
  expect(screen.getByText('7 u')).toBeInTheDocument();
  expect(screen.getByText('3 u')).toBeInTheDocument();
  // Sin el permiso de vitrina no hay pasar a vitrina ni conteo.
  expect(screen.queryByRole('tab', { name: 'Conteo de cierre' })).not.toBeInTheDocument();
});

it('el conteo pide motivo para la merma y no admite contar de más', async () => {
  permissions.set(['pos:showcase'], false);
  posShowcaseApi.list.mockResolvedValue([SHOWCASE]);
  posShowcaseApi.stock.mockResolvedValue([stock()]);
  posShowcaseApi.count.mockResolvedValue({
    id: 'c1',
    number: 1,
    code: 'CV-000001',
    counted_by_name: 'Marta',
    counted_at: '2026-11-26T22:00:00Z',
    notes: null,
    waste_cost: '14.00',
    movement_id: 'm1',
    lines: []
  });
  render(ShowcasePage);

  await fireEvent.click(await screen.findByRole('tab', { name: 'Conteo de cierre' }));
  const input = screen.getByLabelText('Contado de Pan francés');
  const save = screen.getByRole('button', { name: 'Registrar conteo' });
  await fireEvent.input(input, { target: { value: '12' } });
  expect(screen.getByText('Contaste de más')).toBeInTheDocument();
  expect(save).toBeDisabled();
  await fireEvent.input(input, { target: { value: '8' } });
  expect(save).toBeDisabled();
  await fireEvent.input(screen.getByLabelText('Motivo de la merma de Pan francés'), {
    target: { value: 'Pan aplastado' }
  });
  expect(save).toBeEnabled();
  await fireEvent.click(save);
  await waitFor(() => expect(posShowcaseApi.count).toHaveBeenCalledTimes(1));
  const [branchId, lines] = posShowcaseApi.count.mock.calls[0]!;
  expect(branchId).toBe('b1');
  expect(lines).toEqual([
    { inventory_item_id: 'i1', counted_quantity: '8', reason: 'Pan aplastado' }
  ]);
  expect(await screen.findByText(/merma de \$14\.00/)).toBeInTheDocument();
});

it('la vitrina no saca al cajero de su caja a pantalla completa', () => {
  permissions.set(['pos:sell', 'pos:shift_open', 'pos:shift_close', 'pos:cash_movements'], false);
  expect(isPosWorkspace(permissions)).toBe(true);
});
