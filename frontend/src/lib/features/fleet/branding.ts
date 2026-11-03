import type { BaseImage } from './catalog';

/**
 * Branding de vehículos: cada imagen base declara zonas de decal (cuadriláteros en
 * coordenadas de la imagen original) donde se proyecta el logo de la empresa activa
 * en perspectiva, como un smart object.
 */
export type Point = [number, number];
/** Esquinas en orden: superior izquierda, superior derecha, inferior derecha, inferior izquierda. */
export type Quad = [Point, Point, Point, Point];

export interface DecalZone {
  id: 'side' | 'door';
  quad: Quad;
  /** Relación ancho/alto real de la superficie; por defecto se estima con el cuadrilátero. */
  aspect?: number;
  /** Margen interno relativo para que el logo no toque los bordes de la zona. */
  inset?: number;
}

export interface VehicleDecalSpec {
  width: number;
  height: number;
  zones: DecalZone[];
}

const TRUCK_DOOR: Quad = [
  [592, 556],
  [716, 556],
  [718, 652],
  [594, 658]
];

export const VEHICLE_DECALS: Record<BaseImage, VehicleDecalSpec> = {
  refrigerated: {
    width: 1536,
    height: 1024,
    zones: [
      {
        id: 'side',
        quad: [
          [872, 100],
          [1464, 196],
          [1466, 628],
          [872, 640]
        ]
      },
      { id: 'door', quad: TRUCK_DOOR }
    ]
  },
  cargo_van: {
    width: 1774,
    height: 887,
    zones: [
      {
        id: 'side',
        quad: [
          [1090, 152],
          [1640, 144],
          [1648, 532],
          [1090, 544]
        ]
      },
      {
        id: 'door',
        quad: [
          [790, 432],
          [1028, 432],
          [1032, 556],
          [798, 562]
        ]
      }
    ]
  },
  dry_box: {
    width: 1536,
    height: 1024,
    zones: [
      {
        id: 'side',
        quad: [
          [872, 88],
          [1464, 196],
          [1466, 628],
          [872, 640]
        ]
      },
      { id: 'door', quad: TRUCK_DOOR }
    ]
  },
  pickup: {
    width: 1774,
    height: 887,
    zones: [
      {
        id: 'door',
        quad: [
          [872, 420],
          [1102, 418],
          [1106, 604],
          [876, 610]
        ]
      }
    ]
  },
  flatbed: {
    width: 1619,
    height: 971,
    zones: [
      {
        id: 'door',
        quad: [
          [612, 470],
          [768, 462],
          [770, 590],
          [614, 600]
        ]
      }
    ]
  },
  compact_van: {
    width: 1620,
    height: 971,
    zones: [
      {
        id: 'side',
        quad: [
          [1176, 212],
          [1504, 216],
          [1504, 588],
          [1180, 598]
        ]
      },
      {
        id: 'door',
        quad: [
          [932, 526],
          [1144, 526],
          [1144, 618],
          [936, 624]
        ]
      }
    ]
  },
  curtain_side: {
    width: 1619,
    height: 971,
    zones: [
      {
        id: 'side',
        quad: [
          [832, 96],
          [1568, 196],
          [1568, 498],
          [832, 500]
        ]
      },
      {
        id: 'door',
        quad: [
          [592, 498],
          [724, 490],
          [726, 598],
          [594, 608]
        ]
      }
    ]
  },
  semi_trailer: {
    width: 1774,
    height: 887,
    zones: [
      {
        id: 'side',
        quad: [
          [748, 128],
          [1718, 292],
          [1720, 560],
          [748, 544]
        ]
      },
      {
        id: 'door',
        quad: [
          [452, 470],
          [652, 470],
          [656, 608],
          [456, 614]
        ]
      }
    ]
  },
  tanker: {
    width: 1774,
    height: 887,
    zones: [
      {
        id: 'side',
        quad: [
          [900, 230],
          [1640, 236],
          [1640, 440],
          [900, 456]
        ]
      },
      {
        id: 'door',
        quad: [
          [602, 440],
          [750, 434],
          [752, 578],
          [604, 584]
        ]
      }
    ]
  }
};

const distance = ([ax, ay]: Point, [bx, by]: Point) => Math.hypot(bx - ax, by - ay);

/** Tamaño plano (sin perspectiva) de la zona: promedio de lados opuestos o el aspecto declarado. */
export function zoneSize(zone: DecalZone): { width: number; height: number } {
  const [tl, tr, br, bl] = zone.quad;
  const height = (distance(tl, bl) + distance(tr, br)) / 2;
  const width = zone.aspect ? height * zone.aspect : (distance(tl, tr) + distance(bl, br)) / 2;
  return { width, height };
}

type Homography = [number, number, number, number, number, number, number, number];

/** Resuelve A·x = b por eliminación gaussiana con pivoteo parcial. */
function solve(a: number[][], b: number[]): number[] {
  const n = b.length;
  const m = a.map((row, i) => [...row, b[i]!]);
  const at = (row: number, col: number) => m[row]![col]!;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) {
      if (Math.abs(at(row, col)) > Math.abs(at(pivot, col))) pivot = row;
    }
    [m[col], m[pivot]] = [m[pivot]!, m[col]!];
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = at(row, col) / at(col, col);
      for (let k = col; k <= n; k++) m[row]![k] = at(row, k) - factor * at(col, k);
    }
  }
  return m.map((_, i) => at(i, n) / at(i, i));
}

/** Homografía [a, b, c, d, e, f, g, h] que lleva el rectángulo (0,0)-(w,h) al cuadrilátero. */
export function rectToQuadHomography(width: number, height: number, quad: Quad): Homography {
  const source: Quad = [
    [0, 0],
    [width, 0],
    [width, height],
    [0, height]
  ];
  const a: number[][] = [];
  const b: number[] = [];
  source.forEach(([x, y], i) => {
    const [u, v] = quad[i as 0 | 1 | 2 | 3];
    a.push([x, y, 1, 0, 0, 0, -u * x, -u * y]);
    b.push(u);
    a.push([0, 0, 0, x, y, 1, -v * x, -v * y]);
    b.push(v);
  });
  return solve(a, b) as Homography;
}

export function projectPoint(homography: Homography, [x, y]: Point): Point {
  const [a, b, c, d, e, f, g, h] = homography;
  const w = g * x + h * y + 1;
  return [(a * x + b * y + c) / w, (d * x + e * y + f) / w];
}

/** Transformación CSS para un elemento de w×h px con `transform-origin: 0 0`. */
export function quadToMatrix3d(width: number, height: number, quad: Quad): string {
  const [a, b, c, d, e, f, g, h] = rectToQuadHomography(width, height, quad);
  const values = [a, d, 0, g, b, e, 0, h, 0, 0, 1, 0, c, f, 0, 1];
  return `matrix3d(${values.map((value) => +value.toFixed(10)).join(',')})`;
}
