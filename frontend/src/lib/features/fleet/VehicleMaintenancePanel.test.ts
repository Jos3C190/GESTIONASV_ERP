import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle } from './api';

const apiMock = vi.hoisted(() => ({ plans: vi.fn(), orders: vi.fn() }));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));

vi.mock('./api', () => ({ fleetApi: apiMock }));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));

import VehicleMaintenancePanel from './VehicleMaintenancePanel.svelte';

const vehicle = {
  id: 'v1',
  status: 'active',
  operational_status: 'available',
  odometer_km: '6200.0'
} as FleetVehicle;

beforeEach(() => {
  permissionMock.codes = new Set(['fleet:read']);
  apiMock.plans.mockResolvedValue([
    {
      id: 'p1',
      name: 'Cambio de aceite',
      interval_km: 5000,
      interval_days: null,
      last_service_km: '1000.0',
      last_service_on: null,
      due_km: '6000.0',
      due_on: null,
      state: 'overdue',
      is_active: true
    }
  ]);
  apiMock.orders.mockResolvedValue([
    {
      id: 'o1',
      plan_id: null,
      plan_name: null,
      kind: 'corrective',
      status: 'completed',
      title: 'Cambio de frenos',
      description: null,
      workshop: 'Taller Central',
      scheduled_on: null,
      started_at: '2026-10-01T10:00:00Z',
      completed_at: '2026-10-02T10:00:00Z',
      odometer_km: '5900.0',
      cost: '120.00',
      cancel_reason: null,
      created_at: '2026-10-01T09:00:00Z'
    }
  ]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('vehicle maintenance panel', () => {
  it('shows due state and history read-only without fleet:maintenance', async () => {
    render(VehicleMaintenancePanel, { vehicle, onchanged: () => undefined });
    expect(await screen.findByText('Cambio de aceite')).toBeVisible();
    expect(screen.getByText('Vencido')).toBeVisible();
    expect(screen.getByText('Cambio de frenos')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Nuevo plan' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Nueva orden' })).not.toBeInTheDocument();
  });

  it('offers plan and order actions with fleet:maintenance', async () => {
    permissionMock.codes.add('fleet:maintenance');
    render(VehicleMaintenancePanel, { vehicle, onchanged: () => undefined });
    expect(await screen.findByRole('button', { name: 'Nuevo plan' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Programar orden' })).toBeVisible();
  });
});
