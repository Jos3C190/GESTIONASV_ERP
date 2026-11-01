import { describe, expect, it } from 'vitest';
import {
  animationPath,
  bearing,
  measurePath,
  pathBetween,
  pointAlong,
  poseAt,
  sampleAt
} from './truck3d';

type LngLat = [number, number];

describe('3D truck motion', () => {
  it('measures the heading clockwise from north', () => {
    expect(bearing([0, 0], [0, 1])).toBeCloseTo(0, 0);
    expect(bearing([0, 0], [1, 0])).toBeCloseTo(90, 0);
    expect(bearing([0, 0], [0, -1])).toBeCloseTo(180, 0);
    expect(bearing([0, 0], [-1, 0])).toBeCloseTo(270, 0);
  });

  it('follows the street trail between two fixes and stops at the last one', () => {
    const trail: LngLat[] = [
      [0, 0],
      [0, 0.001],
      [0.001, 0.001],
      [0.001, 0.002]
    ];
    const path = animationPath([0, 0], [0.001, 0.002], trail);
    expect(path).toEqual([
      [0, 0],
      [0, 0.001],
      [0.001, 0.001],
      [0.001, 0.002]
    ]);
    expect(pointAlong(path, 1).point).toEqual([0.001, 0.002]);
    const middle = pointAlong(path, 0.5);
    expect(middle.point[0]).toBeCloseTo(0.0005, 6);
    expect(middle.point[1]).toBeCloseTo(0.001, 6);
    expect(middle.course).toBeCloseTo(90, 0);
  });

  it('turns the corner between fixes in the middle of long street segments', () => {
    // Calle hacia el norte y luego hacia el este; los reportes caen a media cuadra.
    const route: LngLat[] = [
      [0, 0],
      [0, 0.004],
      [0.004, 0.004]
    ];
    const path = animationPath([0, 0.0031], [0.0012, 0.004], route);
    expect(path).toEqual([
      [0, 0.0031],
      [0, 0.004],
      [0.0012, 0.004]
    ]);
    expect(pathBetween(route, [0.0012, 0.004], [0, 0.0031])).toBeNull();
    expect(pathBetween(route, [0.002, 0.002], [0.0012, 0.004])).toBeNull();
  });

  it('stays on the street at corners while the heading turns gradually', () => {
    // 100 m al norte y luego 100 m al este.
    const path = measurePath([
      [0, 0],
      [0, 0.000898],
      [0.000898, 0.000898]
    ]);
    expect(path.length).toBeCloseTo(200, 0);
    expect(sampleAt(path, 50)[1]).toBeCloseTo(0.000449, 6);
    expect(poseAt(path, 0).point).toEqual([0, 0]);
    expect(poseAt(path, 50).course).toBeCloseTo(0, 0);
    const corner = poseAt(path, 100);
    expect(corner.course).toBeCloseTo(45, 0);
    // En la esquina la posición es el propio vértice: nunca se sale de la calle.
    expect(corner.point[0]).toBeCloseTo(0, 6);
    expect(corner.point[1]).toBeCloseTo(0.000898, 6);
    expect(poseAt(path, 97).course).toBeLessThan(45);
    expect(poseAt(path, 103).course).toBeGreaterThan(45);
    expect(poseAt(path, 200).point).toEqual([0.000898, 0.000898]);
  });

  it('falls back to a straight line when the trail does not cover both fixes', () => {
    const trail: LngLat[] = [
      [1, 1],
      [1.001, 1]
    ];
    expect(animationPath([0, 0], [0, 0.001], trail)).toEqual([
      [0, 0],
      [0, 0.001]
    ]);
    expect(pointAlong([[0, 0]], 0.5)).toEqual({ point: [0, 0], course: null });
  });
});
