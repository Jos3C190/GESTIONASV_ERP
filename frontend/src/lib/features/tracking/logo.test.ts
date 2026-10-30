import { describe, expect, it } from 'vitest';
import { keyOutBackground } from './truck3d';

/** Imagen RGBA de `size`×`size` con fondo blanco y un cuadro verde con centro blanco. */
function emblem(size = 12) {
  const data = new Uint8ClampedArray(size * size * 4).fill(255);
  for (let y = 3; y < 9; y++)
    for (let x = 3; x < 9; x++) {
      const inner = x >= 5 && x < 7 && y >= 5 && y < 7;
      const index = (y * size + x) * 4;
      if (!inner) data.set([16, 110, 80, 255], index);
    }
  return data;
}

const alpha = (data: Uint8ClampedArray, size: number, x: number, y: number) =>
  data[(y * size + x) * 4 + 3];

describe('logo background', () => {
  it('removes the plain background but keeps the white inside the emblem', () => {
    const data = emblem();
    expect(keyOutBackground(data, 12, 12)).toBe(true);
    expect(alpha(data, 12, 0, 0)).toBe(0);
    expect(alpha(data, 12, 11, 6)).toBe(0);
    expect(alpha(data, 12, 4, 4)).toBe(255);
    // El blanco dentro del emblema no toca el borde: se conserva.
    expect(alpha(data, 12, 5, 5)).toBe(255);
  });

  it('leaves logos that already have transparency or a busy background untouched', () => {
    const transparent = emblem();
    transparent[3] = 0;
    expect(keyOutBackground(transparent, 12, 12)).toBe(false);
    const busy = emblem();
    busy.set([0, 0, 0, 255], 0);
    expect(keyOutBackground(busy, 12, 12)).toBe(false);
    expect(alpha(busy, 12, 11, 11)).toBe(255);
  });
});
