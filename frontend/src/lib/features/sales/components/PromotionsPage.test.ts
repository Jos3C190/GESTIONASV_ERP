import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import PromotionsPage from './PromotionsPage.svelte';

const { salesApi, salesPromotionsApi } = vi.hoisted(() => ({
  salesApi: { catalog: vi.fn() },
  salesPromotionsApi: { list: vi.fn(), create: vi.fn(), end: vi.fn() }
}));
vi.mock('#lib/api/sales.ts', () => ({ salesApi }));
vi.mock('#lib/api/sales-promotions.ts', () => ({ salesPromotionsApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: {
    id: 'branch-1',
    branches: [{ id: 'branch-1', name: 'Centro', code: 'C', is_active: true }]
  }
}));

const PROMO = {
  id: 'promo-1',
  branch_id: 'branch-1',
  branch_name: 'Centro',
  product_id: 7,
  product_name: 'Harina fortificada',
  product_sku: 'PRD-007',
  discount_percent: '10.00',
  valid_from: '2026-11-24',
  valid_to: null,
  notes: null,
  status: 'current' as const
};

beforeEach(() => {
  permissions.set(['sales:read', 'sales_promotions:manage'], false);
  salesPromotionsApi.list.mockReset().mockResolvedValue([PROMO]);
  salesPromotionsApi.create.mockReset();
  salesPromotionsApi.end.mockReset().mockResolvedValue({ ...PROMO, status: 'ended' });
  salesApi.catalog.mockReset().mockResolvedValue([
    { product_id: 7, sku: 'PRD-007', name: 'Harina fortificada' },
    { product_id: 7, sku: 'PRD-007', name: 'Harina fortificada' }
  ]);
});

it('lista las promociones y termina una vigente', async () => {
  render(PromotionsPage);
  expect(await screen.findByText('Harina fortificada')).toBeInTheDocument();
  expect(screen.getByText('Vigente')).toBeInTheDocument();
  expect(screen.getByText('24/11/2026 — sin fin')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Terminar' }));
  expect(salesPromotionsApi.end).toHaveBeenCalledWith('promo-1');
  expect(
    await screen.findByText('Se terminó la promoción de Harina fortificada.')
  ).toBeInTheDocument();
});

it('crea una promoción con sucursal, producto y porcentaje', async () => {
  salesPromotionsApi.list.mockResolvedValue([]);
  salesPromotionsApi.create.mockResolvedValue(PROMO);
  render(PromotionsPage);
  expect(
    await screen.findByText('No hay promociones vigentes ni programadas.')
  ).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Nueva promoción' }));
  const product = await screen.findByLabelText('Producto');
  await waitFor(() => expect(screen.getAllByRole('option', { name: /PRD-007/ })).toHaveLength(1));
  await fireEvent.change(product, { target: { value: '7' } });
  await fireEvent.input(screen.getByLabelText('Descuento de la promoción (%)'), {
    target: { value: '10' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Crear promoción' }));
  expect(salesPromotionsApi.create).toHaveBeenCalledWith({
    branch_id: 'branch-1',
    product_id: 7,
    discount_percent: '10',
    valid_from: null,
    valid_to: null,
    notes: null
  });
  expect(await screen.findByText(/Se creó la promoción del 10/)).toBeInTheDocument();
});

it('sin permiso no ofrece crear ni terminar', async () => {
  permissions.set(['sales:read'], false);
  render(PromotionsPage);
  expect(await screen.findByText('Harina fortificada')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Nueva promoción' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Terminar' })).not.toBeInTheDocument();
});
