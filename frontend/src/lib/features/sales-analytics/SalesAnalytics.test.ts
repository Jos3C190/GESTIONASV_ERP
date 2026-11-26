import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesAnalyticsApi } = vi.hoisted(() => ({
  salesAnalyticsApi: { analysis: vi.fn(), goals: vi.fn(), saveGoals: vi.fn() }
}));
vi.mock('#lib/api/sales-analytics.ts', () => ({ salesAnalyticsApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: null, label: 'Todas las sucursales', branches: [] }
}));
vi.mock('#lib/features/dashboard/components/AreaChart.svelte', async () => ({
  default: (await import('./TestStub.svelte')).default
}));

import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { AnalysisBucket, SalesAnalysis } from '#lib/types/sales-analytics.ts';
import AnalyticsPage from './AnalyticsPage.svelte';
import SalesKpis from './SalesKpis.svelte';

function bucket(key: string, label: string, extra: Partial<AnalysisBucket> = {}): AnalysisBucket {
  return {
    key,
    label,
    net_sales: '100.00',
    documents: 1,
    quantity: '2',
    cost: null,
    margin: null,
    margin_percent: null,
    goal: null,
    goal_percent: null,
    ...extra
  };
}

function analysis(costs: boolean): SalesAnalysis {
  return {
    start: '2026-11-01',
    end: '2026-11-26',
    costs_visible: costs,
    totals: {
      net_sales: '200.00',
      documents: 2,
      average_ticket: '100.00',
      returns: '20.00',
      returns_percent: '10.00',
      cost: costs ? '140.00' : null,
      margin: costs ? '60.00' : null,
      margin_percent: costs ? '30.00' : null
    },
    by_day: [bucket('2026-11-03', '2026-11-03')],
    by_hour: [bucket('09', '09:00')],
    by_branch: [
      bucket('b1', 'Centro', {
        goal: '400.00',
        goal_percent: '25.00',
        margin: costs ? '30.00' : null,
        margin_percent: costs ? '30.00' : null
      })
    ],
    by_category: [bucket('Harinas', 'Harinas')],
    top_customers: [bucket('c1', 'Cafetería El Trigal')],
    top_products: [bucket('p1', 'Harina (u)')],
    bottom_products: []
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesAnalyticsApi)) fn.mockReset();
});

it('muestra las cifras sin costo cuando no se pueden ver costos', async () => {
  permissions.set(['sales_analytics:read'], false);
  salesAnalyticsApi.analysis.mockResolvedValue(analysis(false));
  render(AnalyticsPage);

  expect(await screen.findByText('Tiquete promedio')).toBeInTheDocument();
  expect(screen.getAllByText('$200.00').length).toBeGreaterThan(0);
  expect(screen.getByText('10 %')).toBeInTheDocument();
  expect(screen.queryByText('Margen bruto')).not.toBeInTheDocument();
  expect(screen.queryByRole('columnheader', { name: 'Margen' })).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Avance de la meta de Centro' })).toHaveAttribute(
    'aria-valuenow',
    '25'
  );
  expect(screen.queryByRole('button', { name: 'Metas del mes' })).not.toBeInTheDocument();
  const [from, to, scope] = salesAnalyticsApi.analysis.mock.calls[0]!;
  expect(from).toMatch(/-01$/);
  expect(to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(scope).toBeNull();
});

it('con permiso de costos muestra el margen bruto', async () => {
  permissions.set(['sales_analytics:read'], false);
  salesAnalyticsApi.analysis.mockResolvedValue(analysis(true));
  render(AnalyticsPage);
  expect(await screen.findByText('Margen bruto')).toBeInTheDocument();
  expect(screen.getByText('$60.00 sobre costo de salida')).toBeInTheDocument();
});

it('guarda las metas del mes y vuelve a consultar', async () => {
  permissions.set(['sales_analytics:read', 'sales_goals:manage'], false);
  salesAnalyticsApi.analysis.mockResolvedValue(analysis(false));
  salesAnalyticsApi.goals.mockResolvedValue({
    period: '2026-11',
    goals: [
      { branch_id: 'b1', branch_name: 'Centro', amount: '400.00' },
      { branch_id: 'b2', branch_name: 'Norte', amount: null }
    ]
  });
  salesAnalyticsApi.saveGoals.mockResolvedValue({ period: '2026-11', goals: [] });
  render(AnalyticsPage);

  await fireEvent.click(await screen.findByRole('button', { name: 'Metas del mes' }));
  const norte = await screen.findByLabelText('Meta de Norte');
  await fireEvent.input(norte, { target: { value: '250' } });
  await fireEvent.input(screen.getByLabelText('Meta de Centro'), { target: { value: '' } });
  await fireEvent.submit(screen.getByRole('form', { name: 'Metas de venta del mes' }));
  await waitFor(() => expect(salesAnalyticsApi.saveGoals).toHaveBeenCalled());
  const [, goals] = salesAnalyticsApi.saveGoals.mock.calls[0]!;
  expect(goals).toEqual([
    { branch_id: 'b1', amount: null },
    { branch_id: 'b2', amount: '250.00' }
  ]);
  await waitFor(() => expect(salesAnalyticsApi.analysis).toHaveBeenCalledTimes(2));
});

it('avisa si no hay ventas en el rango', async () => {
  permissions.set(['sales_analytics:read'], false);
  salesAnalyticsApi.analysis.mockResolvedValue({
    ...analysis(false),
    totals: { ...analysis(false).totals, documents: 0, net_sales: '0.00' }
  });
  render(AnalyticsPage);
  expect(await screen.findByText('Sin ventas facturadas en el rango')).toBeInTheDocument();
});

it('el Dashboard solo muestra ventas con permiso', async () => {
  permissions.set(['users:read'], false);
  render(SalesKpis);
  expect(screen.queryByText('Ventas del mes · sin IVA')).not.toBeInTheDocument();
  expect(salesAnalyticsApi.analysis).not.toHaveBeenCalled();
});

it('el Dashboard muestra la venta del mes y el avance de metas', async () => {
  permissions.set(['sales_analytics:read'], false);
  salesAnalyticsApi.analysis.mockResolvedValue(analysis(false));
  render(SalesKpis);
  expect(await screen.findByText('Ventas del mes · sin IVA')).toBeInTheDocument();
  expect(await screen.findByText('$200.00')).toBeInTheDocument();
  expect(screen.getByText('25 %')).toBeInTheDocument();
});
