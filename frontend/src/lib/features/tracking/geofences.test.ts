import { describe, expect, it } from 'vitest';
import {
  circleRing,
  describeShape,
  distanceM,
  draftRing,
  draftShape,
  shapeAreaM2
} from './geofences';
import { demoEvents, describeEvent, fromTraccarEvents } from './events';

describe('geofence geometry', () => {
  it('draws a closed circle whose points sit on the radius', () => {
    const center: [number, number] = [-88.177, 13.4795];
    const ring = circleRing(center, 500, 32);
    expect(ring).toHaveLength(33);
    expect(ring[0]).toEqual(ring[32]);
    for (const point of ring) expect(distanceM(center, point)).toBeCloseTo(500, -1);
  });

  it('estimates polygon area and describes shapes', () => {
    // ~1.08 km × ~1.11 km cerca de San Miguel.
    const square = {
      type: 'polygon' as const,
      coordinates: [
        [-88.19, 13.48],
        [-88.18, 13.48],
        [-88.18, 13.49],
        [-88.19, 13.49]
      ] as [number, number][]
    };
    expect(shapeAreaM2(square) / 1_000_000).toBeCloseTo(1.2, 1);
    expect(describeShape(square)).toBe('Polígono · 4 vértices · 1.2 km²');
    expect(describeShape({ type: 'circle', center: [0, 0], radius_m: 650 })).toBe(
      'Círculo · radio 650 m'
    );
  });

  it('turns a draft into a shape only when it is complete', () => {
    const polygon = {
      kind: 'polygon' as const,
      radiusM: 0,
      vertices: [
        [0, 0],
        [1, 0]
      ] as [number, number][]
    };
    expect(draftShape(polygon)).toBeNull();
    const closed = { ...polygon, vertices: [...polygon.vertices, [1, 1]] as [number, number][] };
    expect(draftShape(closed)).toEqual({ type: 'polygon', coordinates: closed.vertices });
    expect(draftRing(closed)).toHaveLength(4);
    const circle = {
      kind: 'circle' as const,
      radiusM: 812.4,
      vertices: [[-88, 13]] as [number, number][]
    };
    expect(draftShape(circle)).toEqual({ type: 'circle', center: [-88, 13], radius_m: 812 });
  });
});

describe('tracking events', () => {
  it('describes Traccar events in Spanish', () => {
    const base = { geofence_name: 'Centro', alarm: null, speed_kmh: null };
    expect(describeEvent({ ...base, type: 'geofenceEnter' }).title).toBe('Entró a Centro');
    expect(describeEvent({ ...base, type: 'geofenceExit' }).title).toBe('Salió de Centro');
    const overspeed = describeEvent({ ...base, type: 'deviceOverspeed', speed_kmh: 82.4 });
    expect(overspeed).toMatchObject({ tone: 'danger', detail: '82 km/h · Centro' });
    expect(describeEvent({ ...base, type: 'alarm', alarm: 'sos' }).title).toBe('Botón de pánico');
  });

  it('maps API events to fleet vehicles', () => {
    const [event] = fromTraccarEvents([
      {
        id: 5,
        type: 'ignitionOn',
        event_time: '2026-10-28T15:00:00Z',
        device_id: 1,
        device_name: 'FL-003',
        device_unique_id: 'x',
        geofence_name: null,
        alarm: null,
        speed_kmh: null,
        latitude: 13.4,
        longitude: -88.1
      }
    ]);
    expect(event).toMatchObject({
      id: 'traccar-5',
      vehicleName: 'FL-003',
      title: 'Motor encendido'
    });
    expect(event?.vehicle?.plate).toBe('C 345-678');
  });

  it('builds a demo history relative to now', () => {
    const now = Date.parse('2026-10-28T15:00:00Z');
    const history = demoEvents(now);
    expect(history.length).toBeGreaterThan(5);
    expect(history.every((event) => event.time.getTime() <= now)).toBe(true);
  });
});
