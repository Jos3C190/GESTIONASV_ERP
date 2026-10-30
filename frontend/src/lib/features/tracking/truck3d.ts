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

/** Largo real del modelo en metros: cabe en un carril (2,3 m de ancho). */
const TRUCK_LENGTH_M = 7;
/**
 * Tamaño mínimo en pantalla: a escala real casi no se ve con el mapa alejado, así que
 * crece solo lo necesario para distinguirse; de cerca queda del tamaño de la calle.
 */
const MIN_SCREEN_PX = 18;

/**
 * Camión de reparto mirando hacia -Z (norte una vez ubicado en el mapa), con Y hacia arriba,
 * en metros. Devuelve el grupo y las piezas que cambian con el estado.
 */
function buildTruck(THREE: Three) {
  const group = new THREE.Group();
  const paint = new THREE.MeshStandardMaterial({
    color: STATUS_COLORS.moving,
    roughness: 0.45,
    metalness: 0.15
  });
  const body = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.6 });
  const trim = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.7 });
  const tyre = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.9 });
  const hub = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.3, metalness: 0.6 });
  const glass = new THREE.MeshStandardMaterial({
    color: 0x1e3a5f,
    roughness: 0.15,
    metalness: 0.3
  });
  const lamp = new THREE.MeshBasicMaterial({ color: 0xfff7cc });
  const rear = new THREE.MeshBasicMaterial({ color: 0xef4444 });

  const box = (size: [number, number, number], material: unknown, at: [number, number, number]) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
    mesh.position.set(...at);
    group.add(mesh);
    return mesh;
  };

  // Chasis y parachoques.
  box([2.0, 0.3, 6.6], trim, [0, 0.62, 0.15]);
  box([2.25, 0.28, 0.22], trim, [0, 0.62, -3.25]);
  // Caja de carga blanca con franja del color de estado y puertas traseras.
  box([2.3, 2.3, 4.4], body, [0, 1.95, 0.95]);
  box([2.32, 0.22, 4.42], paint, [0, 1.0, 0.95]);
  box([0.04, 2.0, 0.02], trim, [0, 1.95, 3.16]);
  box([0.3, 0.18, 0.05], rear, [-0.95, 0.85, 3.18]);
  box([0.3, 0.18, 0.05], rear, [0.95, 0.85, 3.18]);
  // Cabina pintada con techo, parabrisas inclinado y ventanas laterales.
  box([2.2, 1.55, 1.75], paint, [0, 1.55, -2.2]);
  box([2.1, 0.35, 1.5], paint, [0, 2.45, -2.1]);
  const windshield = box([1.95, 0.75, 0.06], glass, [0, 1.95, -3.08]);
  windshield.rotation.x = -0.18;
  box([0.06, 0.6, 0.9], glass, [-1.11, 1.95, -2.25]);
  box([0.06, 0.6, 0.9], glass, [1.11, 1.95, -2.25]);
  box([0.35, 0.18, 0.05], lamp, [-0.75, 1.0, -3.1]);
  box([0.35, 0.18, 0.05], lamp, [0.75, 1.0, -3.1]);
  // Espejos.
  box([0.25, 0.3, 0.06], trim, [-1.3, 1.95, -2.75]);
  box([0.25, 0.3, 0.06], trim, [1.3, 1.95, -2.75]);

  // Ruedas con rin: eje delantero y doble eje trasero.
  const wheel = new THREE.CylinderGeometry(0.46, 0.46, 0.34, 20);
  const rim = new THREE.CylinderGeometry(0.24, 0.24, 0.36, 14);
  for (const z of [-2.25, 1.55, 2.6]) {
    for (const x of [-1.02, 1.02]) {
      for (const [geometry, material] of [
        [wheel, tyre],
        [rim, hub]
      ] as const) {
        const mesh = new THREE.Mesh(geometry, material);
        mesh.rotation.z = Math.PI / 2;
        mesh.position.set(x, 0.46, z);
        group.add(mesh);
      }
    }
  }

  // Aro de selección en el suelo.
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(4.2, 4.8, 48),
    new THREE.MeshBasicMaterial({
      color: 0x0284c7,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      // Se pinta antes que el camión y sin prueba de profundidad: el suelo del mapa no lo corta.
      depthTest: false,
      side: THREE.DoubleSide
    })
  );
  ring.renderOrder = -1;
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.25;
  group.add(ring);
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
  const fill = new THREE.DirectionalLight(0xffffff);
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
          // Escala uniforme (sin espejo, para que la luz caiga bien) y giro: el frente -Z
          // apunta al rumbo; Mercator crece hacia el sur, de ahí el medio giro extra.
          .scale(new THREE.Vector3(scale, scale, scale))
          .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2))
          .multiply(new THREE.Matrix4().makeRotationY(Math.PI + (state.course * Math.PI) / 180));
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
