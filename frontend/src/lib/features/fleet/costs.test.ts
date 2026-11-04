import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle } from './api';
import { costPeriods, localDate } from './catalog';
import VehicleCostsPanel from './VehicleCostsPanel.svelte';

const apiMock = vi.hoisted(() => ({
  costReport: vi.fn(),
  costs: vi.fn(),
  addCost: vi.fn(),
  voidCost: vi.fn(),
  suppliers: vi.fn(),
  documents: vi.fn()
}));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));
const confirmMock = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fleetApi: apiMock
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));
vi.mock('$lib/stores/confirmation.svelte', () => ({ confirmation: confirmMock }));

const vehicle = {
  id: 'v1',
  status: 'active',
  monthly_fee: '450.00',
  type: { meter_unit: 'km' }
} as unknown as FleetVehicle;

const cost = (overrides = {}) => ({
  id: 'c1',
  category: 'insurance',
  incurred_on: '2026-11-01',
  amount: '120.50',
  description: null,
  supplier_id: null,
  supplier_name: 'Aseguradora Sur',
  document_id: null,
  recorded_by_name: 'ana',
  voided_at: null,
  voided_by_name: null,
  void_reason: null,
  ...overrides
});

const report = (row: object | null = null) => ({
  date_from: '2026-11-01',
  date_to: '2026-11-03',
  rows: row ? [row] : [],
  totals: { fuel: '0', maintenance: '0', other: '0', total: '0' },
  other_by_category: {}
});

describe('cost periods', () => {
  it('uses the calendar months, including across a year', () => {
    const periods = costPeriods(new Date(2026, 0, 15));
    expect(periods.month).toEqual({ from: '2026-01-01', to: '2026-01-15' });
    expect(periods.last_month).toEqual({ from: '2025-12-01', to: '2025-12-31' });
    expect(periods.year).toEqual({ from: '2026-01-01', to: '2026-01-15' });
  });
});

describe('vehicle costs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:costs']);
    apiMock.costReport.mockResolvedValue(report());
    apiMock.costs.mockResolvedValue([cost({ incurred_on: localDate(new Date()) })]);
    apiMock.suppliers.mockResolvedValue([]);
    apiMock.addCost.mockResolvedValue(cost());
  });
  afterEach(cleanup);

  it('shows the cost per km only when the vehicle moved', async () => {
    apiMock.costReport.mockResolvedValue(
      report({
        fuel: '100',
        maintenance: '300',
        other: '50',
        total: '450',
        distance: '849.5',
        cost_per_unit: '0.5297'
      })
    );
    render(VehicleCostsPanel, { vehicle });
    expect(await screen.findByText(/por km/)).toHaveTextContent('849.5 km');
  });

  it('explains a period without distance instead of showing zero', async () => {
    render(VehicleCostsPanel, { vehicle });
    expect(await screen.findByText(/Sin recorrido en el periodo/)).toBeInTheDocument();
  });

  it('asks the report for the chosen period', async () => {
    render(VehicleCostsPanel, { vehicle });
    await screen.findByText('Seguro');
    await fireEvent.click(screen.getByRole('button', { name: 'Este año' }));
    const last = apiMock.costReport.mock.calls.at(-1)?.[0];
    expect(last.vehicle_id).toBe('v1');
    expect(last.date_from).toMatch(/-01-01$/);
  });

  it('proposes the contract fee when recording a fee', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.change(screen.getByLabelText(/Categoría/), { target: { value: 'fee' } });
    expect(screen.getByLabelText(/Monto/)).toHaveValue(450);
  });

  it('keeps a typed supplier in the detail when it is not in the catalog', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.change(screen.getByLabelText(/Categoría/), { target: { value: 'tax' } });
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '30' } });
    await fireEvent.input(screen.getByLabelText('Proveedor (opcional)'), {
      target: { value: 'Lavado Don Luis' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(apiMock.addCost).toHaveBeenCalledWith(
      'v1',
      expect.objectContaining({ amount: '30', description: 'Lavado Don Luis', supplier_id: null })
    );
  });

  it('never shows a failed report as zero, and offers to retry', async () => {
    apiMock.costReport.mockRejectedValue(new Error('caído'));
    render(VehicleCostsPanel, { vehicle });
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
    expect(screen.queryByText(/Sin recorrido/)).not.toBeInTheDocument();
    expect(screen.getByText('Seguro')).toBeInTheDocument();
  });

  it('keeps the list in the same period as the totals', async () => {
    const lastYear = new Date().getFullYear() - 1;
    apiMock.costs.mockResolvedValue([cost({ incurred_on: `${lastYear}-03-01` })]);
    render(VehicleCostsPanel, { vehicle });
    expect(await screen.findByText('No hay otros costos en este periodo.')).toBeInTheDocument();
  });

  it('reaches a cost dated outside the usual periods, so it can be voided', async () => {
    apiMock.costs.mockResolvedValue([cost({ incurred_on: '2024-03-01' })]);
    render(VehicleCostsPanel, { vehicle });
    await screen.findByText('No hay otros costos en este periodo.');
    await fireEvent.click(screen.getByRole('button', { name: 'Todo' }));
    expect(await screen.findByRole('button', { name: /^Anular Seguro/ })).toBeInTheDocument();
  });

  it('does not offer a fee of zero', async () => {
    render(VehicleCostsPanel, { vehicle: { ...vehicle, monthly_fee: '0.00' } });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    expect(screen.queryByText(/no se suma sola/)).not.toBeInTheDocument();
    await fireEvent.change(screen.getByLabelText(/Categoría/), { target: { value: 'fee' } });
    expect(screen.getByLabelText(/Monto/)).toHaveValue(null);
  });

  it('does not carry the proposed fee over to another category', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    const category = screen.getByLabelText(/Categoría/);
    await fireEvent.change(category, { target: { value: 'fee' } });
    await fireEvent.change(category, { target: { value: 'tax' } });
    expect(screen.getByLabelText(/Monto/)).toHaveValue(null);
  });

  it('asks for a category instead of filing everything as insurance', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '30' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(await screen.findByText('Elige la categoría.')).toBeInTheDocument();
    expect(apiMock.addCost).not.toHaveBeenCalled();
  });

  it('respects an edited amount when leaving the fee category', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    const category = screen.getByLabelText(/Categoría/);
    await fireEvent.change(category, { target: { value: 'fee' } });
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '430' } });
    await fireEvent.change(category, { target: { value: 'tax' } });
    expect(screen.getByLabelText(/Monto/)).toHaveValue(430);
  });

  it('moves to the period of what was just recorded', async () => {
    const lastMonth = costPeriods(new Date()).last_month.from;
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.change(screen.getByLabelText(/Categoría/), { target: { value: 'tax' } });
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '30' } });
    await fireEvent.input(screen.getByLabelText(/Fecha/), { target: { value: lastMonth } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    await screen.findByText(/Costo registrado/);
    expect(screen.getByRole('button', { name: 'Mes pasado' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('explains what is wrong instead of sending an invalid amount', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '12.345' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(await screen.findByText(/hasta 2 decimales/)).toBeInTheDocument();
    expect(apiMock.addCost).not.toHaveBeenCalled();
  });

  it('confirms what was recorded', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar costo' }));
    await fireEvent.change(screen.getByLabelText(/Categoría/), { target: { value: 'tax' } });
    await fireEvent.input(screen.getByLabelText(/Monto/), { target: { value: '30' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(await screen.findByText(/Costo registrado: Impuesto, \$30\.00/)).toBeInTheDocument();
  });

  it('asks for a reason before voiding and shows who voided', async () => {
    render(VehicleCostsPanel, { vehicle });
    await fireEvent.click(await screen.findByRole('button', { name: /^Anular Seguro/ }));
    expect(confirmMock.request).toHaveBeenCalledWith(
      expect.objectContaining({ requireReason: true })
    );
    cleanup();
    apiMock.costs.mockResolvedValue([
      cost({
        incurred_on: localDate(new Date()),
        voided_at: '2026-11-02T10:00:00Z',
        voided_by_name: 'luis',
        void_reason: 'Duplicado'
      })
    ]);
    render(VehicleCostsPanel, { vehicle });
    expect(await screen.findByText(/Anulado por luis: Duplicado/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Anular/ })).not.toBeInTheDocument();
  });

  it('hides recording without permission', async () => {
    permissionMock.codes = new Set();
    render(VehicleCostsPanel, { vehicle });
    await screen.findByText('Seguro');
    expect(screen.queryByRole('button', { name: 'Registrar costo' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Anular/ })).not.toBeInTheDocument();
  });
});
