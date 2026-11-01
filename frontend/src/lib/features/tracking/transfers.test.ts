import { describe, expect, it } from 'vitest';
import { formatDistance, fromApiTrack } from './transfers';

describe('transfer tracking', () => {
  it('maps the API response', () => {
    const track = fromApiTrack({
      id: 'a1',
      code: 'TR-1',
      status: 'in_transit',
      dispatched_at: '2026-10-28T14:00:00Z',
      vehicle_code: 'FL-001',
      vehicle_name: 'Camión 1',
      vehicle_plate: 'C 123',
      driver_name: 'Carlos Martínez',
      origin: {
        warehouse_name: 'B1',
        branch_name: 'Roosevelt',
        latitude: 13.48,
        longitude: -88.18
      },
      destination: {
        warehouse_name: 'B2',
        branch_name: 'Santa Rosa',
        latitude: null,
        longitude: null
      },
      gps_configured: true,
      device_found: true,
      route: {
        coordinates: [[-88.18, 13.48]],
        distance_m: 41400,
        duration_s: 2400,
        source: 'osrm'
      },
      trail: [[-88.18, 13.48]],
      trail_matched: true,
      remaining_route: [[-88.1, 13.5]],
      rerouted: true,
      position: { latitude: 13.5, longitude: -88.1, speed_kmh: 50, course: 60, fix_time: null },
      progress: 0.4,
      remaining_m: 24840,
      eta: '2026-10-28T15:30:00Z',
      arrived: false,
      off_route: false,
      off_route_m: 12
    });
    expect(track.origin.point).toEqual([-88.18, 13.48]);
    expect(track.driverName).toBe('Carlos Martínez');
    expect(track.destination.point).toBeNull();
    expect(track.position?.speedKmh).toBe(50);
    expect(track.rerouted).toBe(true);
    expect(track.remainingRoute).toEqual([[-88.1, 13.5]]);
    expect(track.eta?.toISOString()).toBe('2026-10-28T15:30:00.000Z');
    expect(formatDistance(track.remainingM)).toBe('24.8 km');
    expect(formatDistance(420)).toBe('420 m');
  });
});
