import { describe, expect, it } from 'vitest';
import type { TrackedDeviceOut } from '$lib/api/client';
import { demoRoute, demoSnapshot, pointAlong } from './demo';
import { compassPoint, fromTraccar, statusFor, timeAgo } from './tracking';

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
  ...patch
});

describe('tracking view model', () => {
  it('links Traccar devices to fleet vehicles by name or unique id', () => {
    const [byName] = fromTraccar([device()]);
    expect(byName?.vehicle?.plate).toBe('C 123-456');
    expect(byName?.status).toBe('moving');
    const [byId] = fromTraccar([device({ name: 'Celular de prueba', unique_id: 'fl-004' })]);
    expect(byId?.name).toBe('FL-004');
    const [unknown] = fromTraccar([device({ name: 'GPS suelto', unique_id: 'x' })]);
    expect(unknown?.vehicle).toBeNull();
    expect(unknown?.name).toBe('GPS suelto');
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

describe('tracking demo', () => {
  it('interpolates along a route and reports the segment heading', () => {
    const route: [number, number][] = [
      [0, 0],
      [0, 1],
      [1, 1]
    ];
    expect(pointAlong(route, 0).point).toEqual([0, 0]);
    expect(pointAlong(route, 0.25).course).toBeCloseTo(0, 0);
    expect(pointAlong(route, 1).point).toEqual([1, 1]);
  });

  it('moves vehicles on route and parks the rest', () => {
    const start = demoSnapshot(0);
    const later = demoSnapshot(60_000);
    const onRoute = start.find((item) => item.name === 'FL-001')!;
    const moved = later.find((item) => item.name === 'FL-001')!;
    expect(onRoute.status).toBe('moving');
    expect([moved.longitude, moved.latitude]).not.toEqual([onRoute.longitude, onRoute.latitude]);
    expect(start.find((item) => item.name === 'FL-002')?.status).toBe('stopped');
    expect(start.find((item) => item.name === 'FL-005')?.status).toBe('offline');
    expect(demoRoute('Santa Rosa de Lima')?.length).toBeGreaterThan(2);
  });
});
