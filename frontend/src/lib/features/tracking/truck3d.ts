/**
 * Camiones 3D para la vista inclinada de Seguimiento.
 *
 * three.js se descarga solo al inclinar el mapa (versión fija, mismo CDN que MapLibre) y
 * dibuja un camión de pocos polígonos por unidad dentro de una capa personalizada de
 * MapLibre. El modelo se arma con figuras básicas: no depende de archivos de terceros.
 */
import type { MapLibre } from './maplibre';
import type { TrackingStatus } from './tracking';

const THREE_URL = 'https://unpkg.com/three@0.169.0/build/three.module.min.js';

// three.js se carga en tiempo de ejecución, sin tipos empaquetados.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Three = any;

let threePromise: Promise<Three> | null = null;

export function loadThree(): Promise<Three> {
  threePromise ??= import(/* @vite-ignore */ THREE_URL).catch((error: unknown) => {
    threePromise = null;
    throw error;
  });
  return threePromise;
}

export interface TruckState {
  lngLat: [number, number];
  /** Rumbo en grados desde el norte, en sentido horario. */
  course: number;
  status: TrackingStatus;
  selected: boolean;
}

const STATUS_COLORS: Record<TrackingStatus, number> = {
  moving: 0x16a34a,
  stopped: 0xd97706,
  offline: 0x71717a
};

/** Largo real aproximado del modelo, en metros (la escala lo agranda al alejarse). */
const TRUCK_LENGTH_M = 8;
/** Tamaño mínimo en pantalla para que la unidad se distinga a cualquier zoom. */
const MIN_SCREEN_PX = 46;

/**
 * Camión mirando hacia -Z (norte una vez ubicado en el mapa), con Y hacia arriba.
 * Devuelve el grupo y los materiales que cambian con el estado.
 */
function buildTruck(THREE: Three) {
  const group = new THREE.Group();
  const paint = new THREE.MeshLambertMaterial({ color: STATUS_COLORS.moving });
  const cargoMaterial = new THREE.MeshLambertMaterial({ color: 0xf8fafc });
  const dark = new THREE.MeshLambertMaterial({ color: 0x1f2937 });
  const glass = new THREE.MeshLambertMaterial({ color: 0x93c5fd });
  const light = new THREE.MeshBasicMaterial({ color: 0xfef9c3 });
  const box = (
    w: number,
    h: number,
    d: number,
    material: unknown,
    x: number,
    y: number,
    z: number
  ) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
    mesh.position.set(x, y, z);
    group.add(mesh);
    return mesh;
  };
  // Chasis, caja de carga y cabina.
  box(2.3, 0.35, 7.6, dark, 0, 0.75, 0.2);
  box(2.4, 2.5, 5.2, cargoMaterial, 0, 2.2, 1.4);
  box(2.3, 0.18, 5.2, paint, 0, 3.5, 1.4); // franja superior con el color de estado
  box(2.3, 2.0, 2.0, paint, 0, 1.95, -2.4);
  box(2.0, 0.85, 0.08, glass, 0, 2.45, -3.42); // parabrisas
  box(0.45, 0.25, 0.08, light, -0.75, 1.2, -3.42);
  box(0.45, 0.25, 0.08, light, 0.75, 1.2, -3.42);
  // Ruedas: eje delantero y doble eje trasero.
  const wheel = new THREE.CylinderGeometry(0.5, 0.5, 0.4, 14);
  for (const z of [-2.5, 1.6, 2.9]) {
    for (const x of [-1.15, 1.15]) {
      const mesh = new THREE.Mesh(wheel, dark);
      mesh.rotation.z = Math.PI / 2;
      mesh.position.set(x, 0.5, z);
      group.add(mesh);
    }
  }
  // Aro de selección en el suelo.
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(5.2, 6.2, 40),
    new THREE.MeshBasicMaterial({
      color: 0x0284c7,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide
    })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.05;
  group.add(ring);
  group.traverse((node: Three) => {
    if (node.material) node.material.side = THREE.DoubleSide;
  });
  return { group, paint, ring };
}

/**
 * Capa personalizada de MapLibre que dibuja un camión por unidad. `states` se lee en cada
 * cuadro, así que la animación de las posiciones solo necesita pedir un repintado.
 */
export function createTruckLayer(
  maplibregl: MapLibre,
  THREE: Three,
  states: () => Iterable<[string, TruckState]>
) {
  let renderer: Three;
  let map: MapLibre;
  const scene = new THREE.Scene();
  const camera = new THREE.Camera();
  const trucks = new Map<string, ReturnType<typeof buildTruck>>();
  // Luz ambiente, sol y relleno opuesto: ninguna cara del camión queda negra al girar.
  scene.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.9));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(30, -40, 80);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.8);
  fill.position.set(-30, 40, 30);
  scene.add(fill);

  return {
    id: 'trucks-3d',
    type: 'custom' as const,
    renderingMode: '3d' as const,
    onAdd(instance: MapLibre, gl: WebGLRenderingContext) {
      map = instance;
      renderer = new THREE.WebGLRenderer({
        canvas: instance.getCanvas(),
        context: gl,
        antialias: true
      });
      renderer.autoClear = false;
    },
    onRemove() {
      trucks.forEach(({ group }) => scene.remove(group));
      trucks.clear();
    },
    // MapLibre 5 entrega los datos de proyección; versiones anteriores, la matriz directa.
    render(_gl: WebGLRenderingContext, args: Three) {
      const projection = new THREE.Matrix4().fromArray(
        args?.defaultProjectionData?.mainMatrix ?? args
      );
      const zoom = map.getZoom();
      const seen = new Set<string>();
      for (const [key, state] of states()) {
        seen.add(key);
        let truck = trucks.get(key);
        if (!truck) {
          truck = buildTruck(THREE);
          trucks.set(key, truck);
          scene.add(truck.group);
        }
        truck.paint.color.setHex(STATUS_COLORS[state.status]);
        truck.ring.visible = state.selected;
        const mercator = maplibregl.MercatorCoordinate.fromLngLat(state.lngLat, 0);
        const metersPerPixel =
          (156543.03392 * Math.cos((state.lngLat[1] * Math.PI) / 180)) / 2 ** zoom;
        const sizeMeters = Math.max(TRUCK_LENGTH_M, MIN_SCREEN_PX * metersPerPixel);
        const scale = mercator.meterInMercatorCoordinateUnits() * (sizeMeters / TRUCK_LENGTH_M);
        truck.group.matrixAutoUpdate = false;
        truck.group.matrix = new THREE.Matrix4()
          .makeTranslation(mercator.x, mercator.y, mercator.z)
          .scale(new THREE.Vector3(scale, -scale, scale))
          .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2))
          .multiply(new THREE.Matrix4().makeRotationY((-state.course * Math.PI) / 180));
      }
      for (const [key, truck] of trucks) {
        if (!seen.has(key)) {
          scene.remove(truck.group);
          trucks.delete(key);
        }
      }
      camera.projectionMatrix = projection;
      renderer.resetState();
      renderer.render(scene, camera);
    }
  };
}

type LngLat = [number, number];

const toRad = (value: number) => (value * Math.PI) / 180;

/** Rumbo (grados desde el norte) entre dos puntos. */
export function bearing([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const y = Math.sin(toRad(lng2 - lng1)) * Math.cos(toRad(lat2));
  const x =
    Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
    Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(toRad(lng2 - lng1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

const planar = (a: LngLat, b: LngLat) =>
  Math.hypot((b[0] - a[0]) * Math.cos(toRad((a[1] + b[1]) / 2)), b[1] - a[1]);

function nearestIndex(path: LngLat[], point: LngLat): number {
  let best = 0;
  let bestDistance = Infinity;
  path.forEach((candidate, index) => {
    const distance = planar(candidate, point);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = index;
    }
  });
  return best;
}

/**
 * Camino para animar la unidad de `from` a `to`. Si hay un recorrido ajustado a calles que
 * pasa por ambos puntos, se sigue ese tramo; si no, la línea recta. Nunca va más allá de `to`
 * (la última posición real reportada).
 */
export function animationPath(from: LngLat, to: LngLat, trail: LngLat[] = []): LngLat[] {
  if (trail.length >= 2) {
    const start = nearestIndex(trail, from);
    const end = nearestIndex(trail, to);
    const tolerance = 0.0015; // ~150 m: los extremos deben estar sobre el recorrido
    if (
      end > start &&
      planar(trail[start]!, from) < tolerance &&
      planar(trail[end]!, to) < tolerance
    )
      return [from, ...trail.slice(start + 1, end), to];
  }
  return [from, to];
}

/** Punto y rumbo a una fracción `t` (0–1) del largo del camino. */
export function pointAlong(path: LngLat[], t: number): { point: LngLat; course: number | null } {
  if (path.length < 2) return { point: path[0]!, course: null };
  const lengths = path.slice(1).map((point, index) => planar(path[index]!, point));
  const total = lengths.reduce((sum, value) => sum + value, 0);
  if (total === 0) return { point: path[path.length - 1]!, course: null };
  let remaining = Math.min(Math.max(t, 0), 1) * total;
  for (let index = 0; index < lengths.length; index++) {
    const length = lengths[index]!;
    const a = path[index]!;
    const b = path[index + 1]!;
    if (remaining <= length || index === lengths.length - 1) {
      const f = length === 0 ? 1 : Math.min(remaining / length, 1);
      return {
        point: [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f],
        course: length === 0 ? null : bearing(a, b)
      };
    }
    remaining -= length;
  }
  return { point: path[path.length - 1]!, course: null };
}
