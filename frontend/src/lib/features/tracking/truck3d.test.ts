import { describe, expect, it } from 'vitest';
import { animationPath, bearing, pointAlong } from './truck3d';

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
