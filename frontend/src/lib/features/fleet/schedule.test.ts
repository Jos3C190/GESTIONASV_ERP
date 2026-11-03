import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle } from './api';
import { localDate } from './catalog';
import VehicleSchedulePanel from './VehicleSchedulePanel.svelte';

const apiMock = vi.hoisted(() => ({
  reservations: vi.fn(),
  loans: vi.fn(),
  addReservation: vi.fn(),
  cancelReservation: vi.fn(),
  lend: vi.fn(),
  returnLoan: vi.fn()
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
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    branches: [
      { id: 'b1', name: 'Matriz' },
      { id: 'b2', name: 'Sucursal Norte' }
    ]
  }
}));

const vehicle = {
  id: 'v1',
  status: 'active',
  operational_status: 'available',
  branch_id: 'b1',
  driver: null
} as unknown as FleetVehicle;

const loan = (overrides = {}) => ({
  id: 'l1',
  from_branch_id: 'b1',
  from_branch_name: 'Matriz',
  to_branch_id: 'b2',
  to_branch_name: 'Sucursal Norte',
  starts_on: '2026-11-01',
  expected_return_on: '2099-01-01',
  reason: 'Apoyo',
  returned_at: null,
  created_by_name: 'ana',
  ...overrides
});

async function choose(label: RegExp | string, value: string) {
  const select = screen.getByLabelText(label) as HTMLSelectElement;
  const real = select.querySelector.bind(select);
  select.querySelector = ((query: string) =>
    query === ':checked' ? real(`option[value="${value}"]`) : real(query)) as typeof real;
  await fireEvent.change(select, { target: { value } });
  select.querySelector = real;
}

describe('vehicle schedule', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:loans', 'fleet:reservations']);
    apiMock.reservations.mockResolvedValue([]);
    apiMock.loans.mockResolvedValue([]);
    apiMock.addReservation.mockResolvedValue({});
    apiMock.lend.mockResolvedValue(loan());
  });
  afterEach(cleanup);

  it('offers a retry when loading fails', async () => {
    apiMock.loans.mockRejectedValue(new Error('caído'));
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('asks what is missing before lending, and refreshes the vehicle after', async () => {
    const onchanged = vi.fn();
    render(VehicleSchedulePanel, { vehicle, onchanged });
    await fireEvent.click(await screen.findByRole('button', { name: 'Prestar' }));
    const submit = () => fireEvent.submit(document.getElementById('lend-form') as HTMLFormElement);
    await submit();
    expect(await screen.findByText('Elige la sucursal.')).toBeInTheDocument();
    expect(apiMock.lend).not.toHaveBeenCalled();

    await choose(/^Sucursal/, 'b2');
    await fireEvent.input(screen.getByLabelText(/Devolución esperada/), {
      target: { value: localDate(new Date()) }
    });
    await fireEvent.input(screen.getByLabelText(/^Motivo/), { target: { value: 'Apoyo' } });
    await submit();
    await vi.waitFor(() => expect(apiMock.lend).toHaveBeenCalled());
    await vi.waitFor(() => expect(onchanged).toHaveBeenCalled());
  });

  it('cannot lend while on the road, and says why', async () => {
    render(VehicleSchedulePanel, {
      vehicle: { ...vehicle, operational_status: 'in_route' },
      onchanged: vi.fn()
    });
    expect(await screen.findByText(/se podrá prestar cuando termine/)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Prestar' })).toBeDisabled();
  });

  it('shows who has it and lets it come back', async () => {
    apiMock.loans.mockResolvedValue([loan()]);
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByText('Prestado a Sucursal Norte')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Prestar' })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar devolución' }));
    expect(confirmMock.request).toHaveBeenCalled();
  });

  it('marks a loan that should already be back', async () => {
    apiMock.loans.mockResolvedValue([loan({ expected_return_on: '2020-01-01' })]);
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByText(/atrasado/)).toBeInTheDocument();
  });

  it('checks that a reservation ends after it starts', async () => {
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: 'Reservar' }));
    await fireEvent.input(screen.getByLabelText(/^Desde/), {
      target: { value: '2030-01-02T10:00' }
    });
    await fireEvent.input(screen.getByLabelText(/^Hasta/), {
      target: { value: '2030-01-02T09:00' }
    });
    await fireEvent.input(screen.getByLabelText(/^Motivo/), { target: { value: 'Visita' } });
    await fireEvent.submit(document.getElementById('reserve-form') as HTMLFormElement);
    expect(await screen.findByText('Debe terminar después de empezar.')).toBeInTheDocument();
    expect(apiMock.addReservation).not.toHaveBeenCalled();
  });

  it('hides past and cancelled reservations from what is coming', async () => {
    apiMock.reservations.mockResolvedValue([
      {
        id: 'r1',
        starts_at: '2020-01-01T08:00:00Z',
        ends_at: '2020-01-01T09:00:00Z',
        reason: 'Pasada',
        status: 'active',
        reserved_by_name: 'ana',
        cancel_reason: null
      },
      {
        id: 'r2',
        starts_at: '2099-01-01T08:00:00Z',
        ends_at: '2099-01-01T09:00:00Z',
        reason: 'Cancelada',
        status: 'cancelled',
        reserved_by_name: 'ana',
        cancel_reason: 'No'
      }
    ]);
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByText('No hay reservas próximas.')).toBeInTheDocument();
  });

  it('hides actions without permission', async () => {
    permissionMock.codes = new Set();
    render(VehicleSchedulePanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText('No se ha prestado.');
    expect(screen.queryByRole('button', { name: 'Prestar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reservar' })).not.toBeInTheDocument();
  });
});
