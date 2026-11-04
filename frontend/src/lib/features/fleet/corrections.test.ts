import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle } from './api';
import { meterJumpLimit } from './catalog';
import VehicleOdometerPanel from './VehicleOdometerPanel.svelte';

const apiMock = vi.hoisted(() => ({
  odometer: vi.fn(),
  odometerTotal: vi.fn(),
  addOdometer: vi.fn(),
  voidReading: vi.fn()
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
  odometer_km: '15000.0',
  type: { meter_unit: 'km' }
} as unknown as FleetVehicle;

const reading = (overrides = {}) => ({
  id: 'r1',
  reading_km: '150000.0',
  read_at: '2026-11-01T10:00:00Z',
  source: 'manual',
  notes: null,
  recorded_by_name: 'ana',
  voided_at: null,
  voided_by_name: null,
  void_reason: null,
  ...overrides
});

describe('correcting readings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:maintenance', 'fleet:correct_records']);
    apiMock.odometer.mockResolvedValue([reading()]);
    apiMock.odometerTotal.mockResolvedValue({ total: '0', replacements: 0 });
    apiMock.addOdometer.mockResolvedValue({});
  });
  afterEach(() => cleanup());

  it('uses a limit by unit for suspicious jumps', () => {
    expect(meterJumpLimit('km')).toBe(5000);
    expect(meterJumpLimit('hours')).toBe(500);
  });

  it('asks for a reason before voiding, through the confirmation', async () => {
    apiMock.voidReading.mockResolvedValue(vehicle);
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });

    await fireEvent.click(await screen.findByRole('button', { name: 'Anular' }));

    const request = confirmMock.request.mock.calls[0]![0];
    expect(request.requireReason).toBe(true);
    await request.execute('Dígito de más');
    expect(apiMock.voidReading).toHaveBeenCalledWith('v1', 'r1', 'Dígito de más');
  });

  it('shows who voided a reading and offers no further action on it', async () => {
    apiMock.odometer.mockResolvedValue([
      reading({
        voided_at: '2026-11-02T10:00:00Z',
        voided_by_name: 'luis',
        void_reason: 'Dígito de más'
      })
    ]);
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });

    expect(await screen.findByText(/Anulada por luis: Dígito de más/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Anular' })).toBeNull();
  });

  it('points to the fuel log instead of voiding a reading that came from it', async () => {
    apiMock.odometer.mockResolvedValue([reading({ source: 'fuel' })]);
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });

    await screen.findByText('Carga de combustible');

    expect(screen.queryByRole('button', { name: 'Anular' })).toBeNull();
  });

  it('hides corrections from who lacks the permission', async () => {
    permissionMock.codes = new Set(['fleet:maintenance']);
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });

    await screen.findByText('Manual');

    expect(screen.queryByRole('button', { name: 'Anular' })).toBeNull();
    expect(screen.queryByText(/Le cambiaron el tablero/)).toBeNull();
  });

  it('confirms a suspicious jump instead of saving it directly', async () => {
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText('Manual');

    await fireEvent.input(screen.getByLabelText(/Nueva lectura/), { target: { value: '150000' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar lectura' }));

    expect(confirmMock.request).toHaveBeenCalledOnce();
    expect(apiMock.addOdometer).not.toHaveBeenCalled();
  });

  it('saves a normal reading directly', async () => {
    render(VehicleOdometerPanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText('Manual');

    await fireEvent.input(screen.getByLabelText(/Nueva lectura/), { target: { value: '15100' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar lectura' }));

    await vi.waitFor(() => expect(apiMock.addOdometer).toHaveBeenCalled());
    expect(confirmMock.request).not.toHaveBeenCalled();
  });
});
