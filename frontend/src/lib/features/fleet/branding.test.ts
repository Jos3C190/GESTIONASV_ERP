import { describe, expect, it } from 'vitest';
import {
  projectPoint,
  quadToMatrix3d,
  rectToQuadHomography,
  VEHICLE_DECALS,
  zoneSize,
  type Quad
} from './branding';
import { BASE_IMAGE_KEYS } from './catalog';

describe('fleet branding', () => {
  it('maps every rectangle corner onto the matching quad corner', () => {
    const quad: Quad = [
      [872, 100],
      [1464, 196],
      [1466, 628],
      [872, 640]
    ];
    const { width, height } = zoneSize({ id: 'side', quad });
    const homography = rectToQuadHomography(width, height, quad);
    const corners: Quad = [
      [0, 0],
      [width, 0],
      [width, height],
      [0, height]
    ];

    corners.forEach((corner, i) => {
      const [x, y] = projectPoint(homography, corner);
      const [u, v] = quad[i as 0 | 1 | 2 | 3];
      expect(x).toBeCloseTo(u, 6);
      expect(y).toBeCloseTo(v, 6);
    });
  });

  it('builds an identity-like matrix for an axis-aligned rectangle', () => {
    expect(
      quadToMatrix3d(100, 50, [
        [10, 20],
        [110, 20],
        [110, 70],
        [10, 70]
      ])
    ).toBe('matrix3d(1,0,0,0,0,1,0,0,0,0,1,0,10,20,0,1)');
  });

  it('declares decal zones inside the image for every vehicle type', () => {
    for (const kind of BASE_IMAGE_KEYS) {
      const spec = VEHICLE_DECALS[kind];
      expect(spec.zones.length).toBeGreaterThan(0);
      for (const zone of spec.zones) {
        for (const [x, y] of zone.quad) {
          expect(x).toBeGreaterThanOrEqual(0);
          expect(x).toBeLessThanOrEqual(spec.width);
          expect(y).toBeGreaterThanOrEqual(0);
          expect(y).toBeLessThanOrEqual(spec.height);
        }
      }
    }
  });
});
