import { describe, expect, it } from 'vitest';
import { demoSnapshot } from './demo';
import { distanceM } from './geofences';
import { demoTransferTracks, formatDistance, fromApiTrack, travelledAlong } from './transfers';

describe('transfer tracking', () => {
  it('measures how far a point is along the route and cuts the trail there', () => {
    const route: [number, number][] = [
      [0, 0],
      [0, 0.01],
      [0.01, 0.01]
    ];
    const { along, meters } = travelledAlong(route, [0.005, 0.0101]);
    expect(meters).toBeCloseTo(
      distanceM([0, 0], [0, 0.01]) + distanceM([0, 0.01], [0.005, 0.01]),
      -1
    );
    expect(along).toHaveLength(3);
    expect(along[2]![0]).toBeCloseTo(0.005, 4);
  });

  it('follows demo vehicles with progress and ETA', () => {
    const now = Date.parse('2026-10-28T15:00:00Z');
    const tracks = demoTransferTracks(demoSnapshot(now), now);
    expect(tracks.map((track) => track.vehicleCode)).toEqual(['FL-001', 'FL-003', 'FL-004']);
    for (const track of tracks) {
      expect(track.progress).toBeGreaterThan(0);
      expect(track.progress).toBeLessThanOrEqual(1);
      expect(track.eta!.getTime()).toBeGreaterThan(now);
      expect(track.trail.length).toBeGreaterThan(1);
      expect(track.destination.point).not.toBeNull();
    }
  });

  it('maps the API response', () => {
    const track = fromApiTrack({
      id: 'a1',
      code: 'TR-1',
      status: 'in_transit',
      dispatched_at: '2026-10-28T14:00:00Z',
      vehicle_code: 'FL-001',
      vehicle_name: 'Camión 1',
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
      position: { latitude: 13.5, longitude: -88.1, speed_kmh: 50, course: 60, fix_time: null },
      progress: 0.4,
      remaining_m: 24840,
      eta: '2026-10-28T15:30:00Z',
      arrived: false,
      off_route: false,
      off_route_m: 12
    });
    expect(track.origin.point).toEqual([-88.18, 13.48]);
    expect(track.destination.point).toBeNull();
    expect(track.position?.speedKmh).toBe(50);
    expect(track.eta?.toISOString()).toBe('2026-10-28T15:30:00.000Z');
    expect(formatDistance(track.remainingM)).toBe('24.8 km');
    expect(formatDistance(420)).toBe('420 m');
  });
});
