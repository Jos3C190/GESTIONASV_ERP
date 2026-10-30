import { describe, expect, it } from 'vitest';
import type { SimulationOut } from '$lib/api/client';
import {
  countdown,
  driveStep,
  formatDistance,
  inputFromKeys,
  offsetPoint,
  progressOf,
  roundTripActions,
  sessionKey,
  sessionStatus,
  typingTarget,
  type DriveState
} from './simulator';

const START: DriveState = { lngLat: [-88.18, 13.48], course: 90, speedKmh: 0 };

function run(state: DriveState, input: { throttle: number; steer: number }, seconds: number) {
  let current = state;
  for (let t = 0; t < seconds * 20; t++) current = driveStep(current, input, 0.05, 60);
  return current;
}

function session(overrides: Partial<SimulationOut> = {}): SimulationOut {
  return {
    id: 's1',
    vehicle_id: 'v1',
    vehicle_code: 'VEH-SM-01',
    vehicle_plate: 'C 118-402',
    branch_id: 'b1',
    transfer_id: null,
    transfer_code: null,
    traccar_device_id: 42,
    mode: 'route',
    state: 'running',
    route: [],
    stops: [
      [-88.19, 13.48],
      [-88.18, 13.49]
    ],
    leg: 'outbound',
    route_length_m: 2000,
    progress_m: 500,
    speed_kmh: 60,
    current_speed_kmh: 58.4,
    longitude: -88.18,
    latitude: 13.48,
    course: 90,
    stop_until: null,
    signal_lost_until: null,
    last_report_at: null,
    started_at: '2026-10-30T15:00:00Z',
    started_by_name: null,
    can_control: true,
    ...overrides
  };
}

describe('joystick', () => {
  it('accelerates up to the maximum speed and moves along the heading', () => {
    const moved = run(START, { throttle: 1, steer: 0 }, 6);
    expect(moved.speedKmh).toBeCloseTo(60, 0);
    expect(moved.lngLat[0]).toBeGreaterThan(START.lngLat[0]);
    expect(moved.lngLat[1]).toBeCloseTo(START.lngLat[1], 5);
  });

  it('brakes harder than it coasts and never reverses', () => {
    const cruising = run(START, { throttle: 1, steer: 0 }, 6);
    const braked = run(cruising, { throttle: -1, steer: 0 }, 1);
    const coasted = run(cruising, { throttle: 0, steer: 0 }, 1);
    expect(braked.speedKmh).toBeLessThan(coasted.speedKmh);
    expect(run(cruising, { throttle: -1, steer: 0 }, 5).speedKmh).toBe(0);
  });

  it('turns only while moving, like a vehicle', () => {
    expect(run(START, { throttle: 0, steer: 1 }, 2).course).toBe(90);
    const turning = run(START, { throttle: 1, steer: 1 }, 3);
    expect(turning.course).toBeGreaterThan(90);
  });

  it('maps WASD, arrows and space', () => {
    expect(inputFromKeys(new Set(['w', 'd']))).toEqual({ throttle: 1, steer: 1 });
    expect(inputFromKeys(new Set(['arrowup', ' ']))).toEqual({ throttle: -1, steer: 0 });
    expect(inputFromKeys(new Set(['arrowleft']))).toEqual({ throttle: 0, steer: -1 });
  });

  it('ignores keys while typing in a field', () => {
    expect(typingTarget(document.createElement('input'))).toBe(true);
    expect(typingTarget(document.createElement('div'))).toBe(false);
  });

  it('offsets points by metres', () => {
    const north = offsetPoint([-88.18, 13.48], 0, 1000);
    expect(north[0]).toBeCloseTo(-88.18, 6);
    expect(north[1] - 13.48).toBeCloseTo(0.009, 3);
  });
});

describe('session status', () => {
  const now = Date.parse('2026-10-30T15:10:00Z');

  it('prioritises signal loss, then holds, then motion', () => {
    expect(sessionStatus(session({ signal_lost_until: '2026-10-30T15:12:05Z' }), now)).toEqual({
      label: 'Sin señal · 2:05',
      tone: 'lost'
    });
    expect(sessionStatus(session({ state: 'paused' }), now).tone).toBe('hold');
    expect(sessionStatus(session({ stop_until: '2026-10-30T15:30:00Z' }), now).label).toBe(
      'Detenida · 20:00'
    );
    expect(sessionStatus(session({ state: 'arrived' }), now).tone).toBe('done');
    expect(sessionStatus(session(), now).label).toBe('En ruta · 58 km/h');
    expect(sessionStatus(session({ mode: 'joystick' }), now).label).toBe('Manejo manual');
  });

  it('names the return leg and offers the round trip that fits', () => {
    expect(sessionStatus(session({ leg: 'return' }), now).label).toBe('Regresando · 58 km/h');
    expect(sessionStatus(session({ leg: 'return', state: 'arrived' }), now).label).toBe(
      'De vuelta en el inicio'
    );
    expect(roundTripActions(session())).toEqual(['return']);
    expect(roundTripActions(session({ leg: 'return' }))).toEqual(['outbound']);
    expect(roundTripActions(session({ mode: 'joystick', stops: [[-88.19, 13.48]] }))).toEqual([
      'return'
    ]);
    // Empezó con joystick y volvió solo al inicio: puede retomar el control.
    expect(roundTripActions(session({ leg: 'return', stops: [[-88.19, 13.48]] }))).toEqual([
      'take_control'
    ]);
  });

  it('reports progress, distances and the map key', () => {
    expect(progressOf(session())).toBe(0.25);
    expect(progressOf(session({ mode: 'joystick' }))).toBe(0);
    expect(formatDistance(850)).toBe('850 m');
    expect(formatDistance(12_340)).toBe('12.3 km');
    expect(countdown(65_000)).toBe('1:05');
    expect(sessionKey(session())).toBe('traccar-42');
  });
});
