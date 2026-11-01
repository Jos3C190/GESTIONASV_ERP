/**
 * Camiones 3D para la vista inclinada de Seguimiento.
 *
 * three.js y su cargador glTF se descargan solo al inclinar el mapa (versión fija). Cada
 * unidad es un Isuzu ELF 400 refrigerado (modelo propio del ERP, en /models/vehicles) con cinco
 * zonas de logo (caja, puertas y parte trasera) donde se pone el logo de la empresa activa,
 * como en Flota. Si el modelo no carga, se usa un camión armado con figuras básicas.
 */
import type { MapLibre } from './maplibre';
import type { TrackingStatus } from './tracking';

// El cargador de jsDelivr importa three desde esta misma URL: ambos comparten instancia.
const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.169.0/+esm';
const GLTF_LOADER_URL =
  'https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/loaders/GLTFLoader.js/+esm';
const TRUCK_MODEL_URL = '/models/vehicles/isuzu-elf400.glb';
/** Las zonas de logo del modelo se llaman LOGO_CAJA_IZQUIERDA, LOGO_PUERTA_DERECHA, etc. */
const LOGO_PREFIX = 'LOGO_';

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
 * Camión normalizado: largo real, apoyado en el suelo, centrado y con el frente hacia -Z.
 * Sus zonas de logo comparten un solo material (en `userData.logoMaterial`), oculto hasta que
 * se le pone el logo de la empresa. Devuelve null si no se pudo cargar.
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
      // El ELF 400 mira hacia -X; la capa espera el frente hacia -Z.
      scaled.rotation.y = -Math.PI / 2;
      const template = new THREE.Group();
      template.add(scaled);
      template.userData.logoMaterial = logoMaterial(THREE, model);
      return template;
    })
    .catch(() => null);
  return modelPromise;
}

/**
 * Un material compartido por las cinco zonas de logo de todas las unidades: cambiar su imagen
 * cambia el logo en todo el mapa. Va levemente adelantado en profundidad para no parpadear
 * sobre la caja con el mapa alejado, y oculto mientras no haya logo.
 */
function logoMaterial(THREE: Three, model: Three) {
  const material = new THREE.MeshStandardMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    roughness: 0.39,
    metalness: 0,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1
  });
  material.visible = false;
  model.traverse((object: Three) => {
    const name = String(object.name);
    if (!object.isMesh || !name.startsWith(LOGO_PREFIX)) return;
    object.material = material;
    const zone = Object.keys(LOGO_ZONE_SCALE).find((prefix) => name.startsWith(prefix));
    if (zone) object.scale.multiplyScalar(LOGO_ZONE_SCALE[zone]!);
  });
  return material;
}

/**
 * Cuánto se agranda cada zona de logo respecto del modelo, medido para que no se salga de su
 * superficie: en la caja (1,6 → 1,84 m) queda a 6 cm del borde superior; en la puerta
 * (0,44 → 0,57 m) por debajo de la ventana; atrás (1,2 → 1,44 m) con aire entre las bisagras de las puertas.
 */
const LOGO_ZONE_SCALE: Record<string, number> = {
  LOGO_CAJA_: 1.15,
  LOGO_PUERTA_: 1.3,
  LOGO_TRASERO: 1.2
};

/** Lado del lienzo cuadrado del logo y margen para que no toque el borde de la zona. */
const LOGO_CANVAS_PX = 1024;
const LOGO_INSET = 0.03;
/** Resolución de trabajo para quitar el fondo y recortar el margen del logo. */
const LOGO_WORK_PX = 1024;
/** Opacidad mínima para considerar que un píxel es parte del logo al recortar. */
const CONTENT_ALPHA = 16;

/** Rectángulo con contenido visible (sin el margen transparente); null si está vacío. */
export function contentBounds(data: Uint8ClampedArray, width: number, height: number) {
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++)
      if (data[(y * width + x) * 4 + 3]! >= CONTENT_ALPHA) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
  if (maxX < 0) return null;
  return { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 };
}

let logoRequest = 0;

/** Diferencia de color hasta la que un píxel es fondo, y hasta la que se funde con el borde. */
const BACKGROUND_TOLERANCE = 48;
const EDGE_TOLERANCE = 110;

/**
 * Quita el fondo liso de un logo sin transparencia (un JPG con fondo blanco): vacía los píxeles
 * del color de las esquinas conectados con el borde y suaviza el contorno. El blanco dentro del
 * emblema se conserva porque no está conectado con el borde. Devuelve false si no tocó nada
 * (el logo ya trae transparencia o su fondo no es de un solo color).
 */
export function keyOutBackground(data: Uint8ClampedArray, width: number, height: number): boolean {
  const total = width * height;
  for (let index = 0; index < total; index++) if (data[index * 4 + 3]! < 250) return false;
  const corners = [0, width - 1, (height - 1) * width, total - 1];
  const background = [0, 1, 2].map(
    (channel) => corners.reduce((sum, pixel) => sum + data[pixel * 4 + channel]!, 0) / 4
  );
  const distance = (pixel: number) =>
    Math.hypot(
      data[pixel * 4]! - background[0]!,
      data[pixel * 4 + 1]! - background[1]!,
      data[pixel * 4 + 2]! - background[2]!
    );
  if (corners.some((pixel) => distance(pixel) > BACKGROUND_TOLERANCE)) return false;
  const visited = new Uint8Array(total);
  const queue: number[] = [];
  for (let x = 0; x < width; x++) queue.push(x, (height - 1) * width + x);
  for (let y = 0; y < height; y++) queue.push(y * width, y * width + width - 1);
  while (queue.length) {
    const pixel = queue.pop()!;
    if (visited[pixel]) continue;
    visited[pixel] = 1;
    const gap = distance(pixel);
    if (gap > EDGE_TOLERANCE) continue;
    if (gap > BACKGROUND_TOLERANCE) {
      // Contorno: semitransparente según cuánto se parece al fondo; no se sigue de largo.
      const keep = (gap - BACKGROUND_TOLERANCE) / (EDGE_TOLERANCE - BACKGROUND_TOLERANCE);
      data[pixel * 4 + 3] = Math.round(255 * keep);
      continue;
    }
    data[pixel * 4 + 3] = 0;
    const x = pixel % width;
    if (x > 0) queue.push(pixel - 1);
    if (x < width - 1) queue.push(pixel + 1);
    if (pixel >= width) queue.push(pixel - width);
    if (pixel < total - width) queue.push(pixel + width);
  }
  return true;
}

/**
 * Pone `url` (el logo de la empresa activa) en las zonas de logo, ajustado sin deformarse a un
 * lienzo transparente. Sin logo, o si no se puede leer, las zonas quedan vacías: nunca se
 * muestra la marca de otra empresa.
 */
export async function applyTruckLogo(THREE: Three, template: Three | null, url: string | null) {
  const material = template?.userData.logoMaterial;
  if (!material) return;
  const request = ++logoRequest;
  const clear = () => {
    material.map?.dispose();
    material.map = null;
    material.visible = false;
    material.needsUpdate = true;
  };
  if (!url) {
    clear();
    return;
  }
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.crossOrigin = 'anonymous';
      element.onload = () => resolve(element);
      element.onerror = reject;
      element.src = url;
    });
    if (request !== logoRequest) return;
    // Se trabaja a buena resolución: luego se recorta el margen vacío y se amplía lo útil.
    const work = Math.min(1, LOGO_WORK_PX / Math.max(image.naturalWidth, image.naturalHeight));
    const width = Math.max(1, Math.round(image.naturalWidth * work));
    const height = Math.max(1, Math.round(image.naturalHeight * work));
    const art = document.createElement('canvas');
    art.width = width;
    art.height = height;
    const artContext = art.getContext('2d', { willReadFrequently: true })!;
    artContext.drawImage(image, 0, 0, width, height);
    // Leer los píxeles falla si el logo es de otro dominio sin CORS: WebGL tampoco podría usarlo.
    const pixels = artContext.getImageData(0, 0, width, height);
    if (keyOutBackground(pixels.data, width, height)) artContext.putImageData(pixels, 0, 0);
    // El margen transparente que traen muchos logos achicaría la marca en la carrocería.
    const content = contentBounds(pixels.data, width, height) ?? { x: 0, y: 0, width, height };
    const room = LOGO_CANVAS_PX * (1 - 2 * LOGO_INSET);
    const fit = room / Math.max(content.width, content.height);
    const drawWidth = content.width * fit;
    const drawHeight = content.height * fit;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = LOGO_CANVAS_PX;
    const context = canvas.getContext('2d')!;
    context.imageSmoothingQuality = 'high';
    context.drawImage(
      art,
      content.x,
      content.y,
      content.width,
      content.height,
      (LOGO_CANVAS_PX - drawWidth) / 2,
      (LOGO_CANVAS_PX - drawHeight) / 2,
      drawWidth,
      drawHeight
    );
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    // Las coordenadas de textura de glTF no se invierten en Y.
    texture.flipY = false;
    texture.anisotropy = 4;
    material.map?.dispose();
    material.map = texture;
    material.visible = true;
    material.needsUpdate = true;
  } catch {
    if (request === logoRequest) clear();
  }
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

/** Largo real del ELF 400 en metros (unos 2,2 m de ancho): cabe en un carril. */
const TRUCK_LENGTH_M = 7.2;
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
 * Una unidad a partir del modelo: su carrocería no se tiñe (el logo y los cristales se verían
 * mal), así que el estado se muestra con un disco de color bajo el vehículo.
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
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(3.9, 3.9, 0.1, 48), paint);
  disc.position.y = 0.08;
  group.add(disc);
  const ring = selectionRing(THREE);
  group.add(ring);
  return { group, paint, ring };
}

function selectionRing(THREE: Three) {
  // Aro con volumen ligeramente elevado: no compite con el suelo del mapa.
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(4.8, 0.22, 8, 64),
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
  /**
   * Del modelo (X derecha, Y arriba, frente hacia -Z) a Mercator (X este, Y sur, Z arriba).
   * Mercator crece hacia el sur, así que este paso es un reflejo que compensa el del mapa: sin
   * él el camión se dibujaría en espejo (logos invertidos y caras internas a la vista).
   */
  const MODEL_TO_MERCATOR = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
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
        // El rumbo (horario desde el norte) gira el camión sobre su eje vertical (Y arriba).
        truck.group.rotation.set(0, (-state.course * Math.PI) / 180, 0);
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
          .multiply(MODEL_TO_MERCATOR);
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
