import { describe, expect, it } from 'vitest';
import type { TrackedDeviceOut, TrackedVehicleOut } from '$lib/api/client';
import { compassPoint, fromTraccar, statusFor, timeAgo } from './tracking';

const fleetVehicle: TrackedVehicleOut = {
  id: 'v1',
  code: 'FL-001',
  plate: 'C 123-456',
  kind: 'refrigerated',
  brand: 'Isuzu',
  model: 'ELF 400',
  branch_id: 'b1',
  branch_name: 'Roosevelt',
  operational_status: 'in_route',
  driver_name: 'Carlos Martínez',
  transfer_code: 'TR-1',
  transfer_destination: 'Santa Rosa'
};

const device = (patch: Partial<TrackedDeviceOut> = {}): TrackedDeviceOut => ({
  id: 7,
  unique_id: '865432100000007',
  name: 'FL-001',
  status: 'online',
  last_update: '2026-10-28T15:30:00Z',
  position: {
    latitude: 13.5,
    longitude: -88.1,
    speed_kmh: 48,
    course: 92,
    fix_time: '2026-10-28T15:29:55Z',
    address: null,
    ignition: true,
    battery_level: 80
  },
  vehicle: fleetVehicle,
  ...patch
});

describe('tracking view model', () => {
  it('uses the fleet vehicle linked to each device by the server', () => {
    const [linked] = fromTraccar([device({ name: 'IMEI 865432' })]);
    expect(linked?.name).toBe('FL-001');
    expect(linked?.vehicle?.plate).toBe('C 123-456');
    expect(linked?.status).toBe('moving');
    const [unlinked] = fromTraccar([device({ name: 'GPS suelto', vehicle: null })]);
    expect(unlinked?.vehicle).toBeNull();
    expect(unlinked?.name).toBe('GPS suelto');
  });

  it('skips devices without a position and marks offline ones', () => {
    expect(fromTraccar([device({ position: null })])).toEqual([]);
    expect(fromTraccar([device({ status: 'offline' })])[0]?.status).toBe('offline');
    expect(statusFor(true, 2)).toBe('stopped');
  });

  it('formats course and elapsed time', () => {
    expect(compassPoint(92)).toBe('E');
    expect(compassPoint(-10)).toBe('N');
    expect(compassPoint(225)).toBe('SO');
    const now = Date.parse('2026-10-28T15:30:00Z');
    expect(timeAgo(new Date(now - 12_000), now)).toBe('hace 12 s');
    expect(timeAgo(new Date(now - 5 * 60_000), now)).toBe('hace 5 min');
    expect(timeAgo(null, now)).toBe('Sin datos');
  });
});
