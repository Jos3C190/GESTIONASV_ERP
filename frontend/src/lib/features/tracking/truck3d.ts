/**
 * Camiones 3D para la vista inclinada de Seguimiento.
 *
 * three.js y su cargador glTF se descargan solo al inclinar el mapa (versión fija). Cada
 * unidad es el furgón de reparto del Car Kit de Kenney (licencia CC0, servido por el propio
 * ERP en /models/vehicles); si no se puede cargar, se usa un camión armado con figuras básicas.
 */
import type { MapLibre } from './maplibre';
import type { TrackingStatus } from './tracking';

// El cargador de jsDelivr importa three desde esta misma URL: ambos comparten instancia.
const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.169.0/+esm';
const GLTF_LOADER_URL =
  'https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/loaders/GLTFLoader.js/+esm';
const TRUCK_MODEL_URL = '/models/vehicles/delivery.glb';

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

let modelPromise: Promise<Three | null> | null = null;

/**
 * Furgón normalizado: 7 m de largo, apoyado en el suelo, centrado y con el frente hacia -Z.
 * Devuelve null si no se pudo cargar (la capa usa entonces el camión de respaldo).
 */
export function loadTruckModel(THREE: Three): Promise<Three | null> {
  modelPromise ??= import(/* @vite-ignore */ GLTF_LOADER_URL)
    .then(
      ({ GLTFLoader }) =>
        new Promise<Three>((resolve, reject) =>
          new GLTFLoader().load(TRUCK_MODEL_URL, resolve, undefined, reject)
        )
    )
    .then((gltf: Three) => {
      const model = gltf.scene;
      const bounds = new THREE.Box3().setFromObject(model);
      const size = bounds.getSize(new THREE.Vector3());
      const center = bounds.getCenter(new THREE.Vector3());
      const scale = TRUCK_LENGTH_M / Math.max(size.z, size.x);
      model.position.set(-center.x, -bounds.min.y, -center.z);
      const scaled = new THREE.Group();
      scaled.add(model);
      scaled.scale.setScalar(scale);
      // El modelo del kit mira hacia +Z; la capa espera el frente hacia -Z.
      scaled.rotation.y = Math.PI;
      const template = new THREE.Group();
      template.add(scaled);
      return template;
    })
    .catch(() => null);
  return modelPromise;
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
/**
 * Una unidad a partir del furgón del kit: su textura no se tiñe (ventanas y llantas se
 * verían mal), así que el estado se muestra con un disco de color bajo el vehículo.
 */
function buildFromModel(THREE: Three, template: Three) {
  const group = new THREE.Group();
  group.add(template.clone(true));
  // Base fina con grosor real (no un plano): se ve sobre el asfalto sin parpadear.
  const paint = new THREE.MeshBasicMaterial({
    color: STATUS_COLORS.moving,
    transparent: true,
    opacity: 0.5,
    depthWrite: false
  });
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(3.0, 3.0, 0.1, 40), paint);
  disc.position.y = 0.08;
  group.add(disc);
  const ring = selectionRing(THREE);
  group.add(ring);
  return { group, paint, ring };
}

function selectionRing(THREE: Three) {
  // Aro con volumen ligeramente elevado: no compite con el suelo del mapa.
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(4.3, 0.22, 8, 56),
    new THREE.MeshBasicMaterial({ color: 0x0284c7 })
  );
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.35;
  return ring;
}

/** Camión de respaldo armado con figuras básicas, por si el modelo no carga. */
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
  const ring = selectionRing(THREE);
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
  states: () => Iterable<[string, TruckState]>,
  template: Three | null = null
) {
  let renderer: Three;
  let map: MapLibre;
  const scene = new THREE.Scene();
  const camera = new THREE.Camera();
  const trucks = new Map<string, ReturnType<typeof buildTruck>>();
  // Luz ambiente, sol y relleno opuesto: ninguna cara del camión queda negra al girar.
  scene.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.9));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(30, 80, 40);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff);
  fill.position.set(-30, 40, -30);
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
      const frame: [ReturnType<typeof buildTruck>, Three][] = [];
      for (const [key, state] of states()) {
        seen.add(key);
        let truck = trucks.get(key);
        if (!truck) {
          truck = template ? buildFromModel(THREE, template) : buildTruck(THREE);
          trucks.set(key, truck);
          scene.add(truck.group);
        }
        truck.paint.color.setHex(STATUS_COLORS[state.status]);
        truck.ring.visible = state.selected;
        // El rumbo queda en el propio camión (Y arriba); Mercator crece hacia el sur,
        // de ahí el medio giro extra para que el frente -Z apunte al rumbo.
        truck.group.rotation.set(0, Math.PI + (state.course * Math.PI) / 180, 0);
        const mercator = maplibregl.MercatorCoordinate.fromLngLat(state.lngLat, 0);
        const metersPerPixel =
          (156543.03392 * Math.cos((state.lngLat[1] * Math.PI) / 180)) / 2 ** zoom;
        const sizeMeters = Math.max(TRUCK_LENGTH_M, MIN_SCREEN_PX * metersPerPixel);
        const scale = mercator.meterInMercatorCoordinateUnits() * (sizeMeters / TRUCK_LENGTH_M);
        // Posición y escala se combinan con la matriz del mapa en la CPU (doble precisión):
        // en la GPU, en precisión simple, los triángulos se recortarían.
        const placement = new THREE.Matrix4()
          .makeTranslation(mercator.x, mercator.y, mercator.z)
          .scale(new THREE.Vector3(scale, scale, scale))
          .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2));
        frame.push([truck, projection.clone().multiply(placement)]);
      }
      for (const [key, truck] of trucks) {
        if (!seen.has(key)) {
          scene.remove(truck.group);
          trucks.delete(key);
        }
      }
      renderer.resetState();
      trucks.forEach((truck) => (truck.group.visible = false));
      for (const [truck, matrix] of frame) {
        truck.group.visible = true;
        camera.projectionMatrix = matrix;
        camera.projectionMatrixInverse.copy(matrix).invert();
        renderer.render(scene, camera);
        truck.group.visible = false;
      }
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

/** Proyección de `point` sobre el camino: segmento, punto más cercano y distancia recorrida. */
function locate(path: LngLat[], point: LngLat) {
  let best = { segment: 0, point: path[0]!, along: 0, offset: Infinity };
  let walked = 0;
  for (let index = 0; index < path.length - 1; index++) {
    const a = path[index]!;
    const b = path[index + 1]!;
    const scale = Math.cos(toRad((a[1] + b[1]) / 2));
    const dx = (b[0] - a[0]) * scale;
    const dy = b[1] - a[1];
    const length = Math.hypot(dx, dy);
    const t =
      length === 0
        ? 0
        : Math.min(
            1,
            Math.max(0, ((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / length ** 2)
          );
    const closest: LngLat = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    const offset = planar(closest, point);
    if (offset < best.offset)
      best = { segment: index, point: closest, along: walked + length * t, offset };
    walked += length;
  }
  return best;
}

/** ~40 m: un punto más lejos de la línea no está sobre ese recorrido. */
const ON_PATH = 0.0004;

/**
 * Tramo del camino entre dos puntos que están sobre él (proyectados sobre sus segmentos,
 * no sobre el vértice más cercano: en una esquina eso cortaba la cuadra). `null` si alguno
 * de los dos queda fuera del camino o si `to` está antes que `from`.
 */
export function pathBetween(path: LngLat[], from: LngLat, to: LngLat): LngLat[] | null {
  if (path.length < 2) return null;
  const start = locate(path, from);
  const end = locate(path, to);
  if (start.offset > ON_PATH || end.offset > ON_PATH || end.along < start.along) return null;
  return [from, ...path.slice(start.segment + 1, end.segment + 1), to];
}

/**
 * Camino para animar la unidad de `from` a `to`. Si hay un recorrido ajustado a calles que
 * pasa por ambos puntos, se sigue ese tramo; si no, la línea recta. Nunca va más allá de `to`
 * (la última posición real reportada).
 */
export function animationPath(from: LngLat, to: LngLat, trail: LngLat[] = []): LngLat[] {
  return pathBetween(trail, from, to) ?? [from, to];
}

const METERS_PER_DEGREE = 111_320;
/** Tramo antes y después con que se mide el rumbo: en las esquinas gira de forma gradual. */
export const HEADING_WINDOW_M = 6;

export interface MeasuredPath {
  points: LngLat[];
  /** Distancia acumulada en metros hasta cada punto. */
  cumulative: number[];
  length: number;
}

export function measurePath(points: LngLat[]): MeasuredPath {
  const cumulative = [0];
  for (let index = 1; index < points.length; index++)
    cumulative.push(
      cumulative[index - 1]! + planar(points[index - 1]!, points[index]!) * METERS_PER_DEGREE
    );
  return { points, cumulative, length: cumulative[cumulative.length - 1] ?? 0 };
}

/** Punto a `meters` metros del inicio del camino. */
export function sampleAt(path: MeasuredPath, meters: number): LngLat {
  const { points, cumulative, length } = path;
  if (points.length < 2) return points[0]!;
  const distance = Math.min(Math.max(meters, 0), length);
  let low = 1;
  let high = cumulative.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (cumulative[middle]! < distance) low = middle + 1;
    else high = middle;
  }
  const a = points[low - 1]!;
  const b = points[low]!;
  const span = cumulative[low]! - cumulative[low - 1]!;
  const t = span <= 0 ? 0 : (distance - cumulative[low - 1]!) / span;
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/**
 * Posición y rumbo a `meters` metros. La posición queda siempre exactamente sobre la calle;
 * solo el rumbo se mide entre un punto un poco antes y uno un poco después, así en las
 * esquinas la unidad gira de forma gradual sin salirse del trazo.
 */
export function poseAt(
  path: MeasuredPath,
  meters: number,
  window = HEADING_WINDOW_M
): { point: LngLat; course: number | null } {
  const distance = Math.min(Math.max(meters, 0), path.length);
  const before = sampleAt(path, distance - window);
  const after = sampleAt(path, distance + window);
  const course = before[0] === after[0] && before[1] === after[1] ? null : bearing(before, after);
  return { point: sampleAt(path, distance), course };
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
