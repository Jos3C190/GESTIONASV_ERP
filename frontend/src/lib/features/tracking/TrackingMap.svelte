<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import type { GeofenceOut, SiteOut } from '$lib/api/client';
  import { geofenceCollection } from './geofences';
  import { siteAreas, sitePopup } from './sites';
  import {
    animationPath,
    createTruckLayer,
    loadThree,
    loadTruckModel,
    pointAlong,
    type TruckState
  } from './truck3d';
  import { DEFAULT_CENTER, loadMapLibre, MAP_STYLE, type MapLibre } from './maplibre';
  import { STATUS_LABELS, type TrackedVehicle } from './tracking';

  type LngLat = [number, number];

  let {
    vehicles,
    selectedKey = null,
    follow = false,
    trail = [],
    plannedRoute = null,
    originalRoute = null,
    geofences = [],
    sites = [],
    highlightedGeofence = null,
    draft = null,
    drawing = false,
    focusPoint = null,
    endpoints = null,
    simRoutes = [],
    simPoints = [],
    pilot = null,
    onselect,
    ondrawpoint,
    ondrawfinish
  }: {
    vehicles: TrackedVehicle[];
    selectedKey?: string | null;
    follow?: boolean;
    trail?: LngLat[];
    plannedRoute?: LngLat[] | null;
    /** Ruta planeada original cuando la unidad se desvió y se recalculó. */
    originalRoute?: LngLat[] | null;
    geofences?: GeofenceOut[];
    /** Sucursales y almacenes: capa fija que no se puede ocultar. */
    sites?: SiteOut[];
    highlightedGeofence?: number | null;
    /** Contorno en edición: anillo del polígono o círculo y sus vértices. */
    draft?: { ring: LngLat[]; vertices: LngLat[] } | null;
    drawing?: boolean;
    /** Punto a resaltar (p. ej. el lugar de un evento). */
    focusPoint?: { key: string; at: LngLat } | null;
    /** Origen y destino de un traslado (marcadores A y B). */
    endpoints?: {
      origin: { at: LngLat; label: string } | null;
      destination: { at: LngLat; label: string } | null;
    } | null;
    /** Recorridos de las sesiones del simulador y los puntos que se están marcando. */
    simRoutes?: LngLat[][];
    simPoints?: LngLat[];
    /** Unidad manejada con el joystick: se dibuja en cada cuadro, sin esperar al servidor. */
    pilot?: { key: string; lngLat: LngLat; course: number } | null;
    onselect: (key: string | null) => void;
    ondrawpoint?: (point: LngLat) => void;
    ondrawfinish?: () => void;
  } = $props();

  const SITE_BRANCH_ICON =
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/></svg>';
  const SITE_WAREHOUSE_ICON =
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-5 9 5v11H3zM7 20v-7h10v7M7 16h10"/></svg>';
  const TRUCK_PATH =
    'M3 5h11v12H3z M14 9h4l3 4v4h-7 M7 19a2 2 0 100-4 2 2 0 000 4 M17 19a2 2 0 100-4 2 2 0 000 4';

  let container = $state<HTMLDivElement>();
  let map = $state.raw<MapLibre | null>(null);
  let loadError = $state<string | null>(null);
  let styleReady = $state(0);
  let fitted = false;
  const markers = new Map<string, { marker: MapLibre; element: HTMLDivElement }>();

  const line = (coordinates: LngLat[]) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'LineString', coordinates }
  });
  const points = (coordinates: LngLat[]) => ({
    type: 'FeatureCollection',
    features: coordinates.map((point) => ({
      type: 'Feature',
      properties: {},
      geometry: { type: 'Point', coordinates: point }
    }))
  });
  const lines = (paths: LngLat[][]) => ({
    type: 'FeatureCollection',
    features: paths.filter((path) => path.length > 1).map(line)
  });
  /** Puntos numerados del recorrido simulado y la línea que los une. */
  const waypointFeatures = (coordinates: LngLat[]) => ({
    type: 'FeatureCollection',
    features: [
      ...(coordinates.length > 1 ? [line(coordinates)] : []),
      ...coordinates.map((point, index) => ({
        type: 'Feature',
        properties: { label: String(index + 1) },
        geometry: { type: 'Point', coordinates: point }
      }))
    ]
  });
  const polygon = (ring: LngLat[]) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: ring.length >= 4 ? [ring] : [] }
  });
  let focusMarker: MapLibre | null = null;

  /** Margen para encuadrar sin quedar debajo del panel lateral (solo en pantallas anchas). */
  const mapPadding = () => {
    const wide = (container?.clientWidth ?? 0) > 900;
    return { top: 60, bottom: 60, left: wide ? 380 : 40, right: 60 };
  };
  let endpointMarkers: MapLibre[] = [];
  let siteMarkers: MapLibre[] = [];
  /** Algo menos que el ciclo de consulta: la unidad se mueve de forma continua. */
  const ANIMATION_MS = 4000;
  /** Inclinación a partir de la cual las unidades se dibujan como camiones 3D. */
  const TILT_3D = 25;
  const animations = new Map<string, number>();
  /** Posición animada, rumbo y estado de cada unidad; lo lee la capa 3D en cada cuadro. */
  const truckStates = new Map<string, TruckState>();
  let threeD = $state(false);
  let truckLayerReady = false;
  let truckLayerFailed = false;

  const repaint = () => {
    if (threeD) map?.triggerRepaint();
  };

  // Desliza la unidad desde su posición anterior hasta la nueva siguiendo `path` (el
  // recorrido ajustado a calles cuando se conoce); nunca pasa de la última posición real.
  function animateTo(key: string, marker: MapLibre, path: LngLat[], course: number) {
    const target = path[path.length - 1]!;
    const from = path[0]!;
    const start = performance.now();
    cancelAnimationFrame(animations.get(key) ?? 0);
    const jump = Math.abs(from[0] - target[0]) > 0.5 || Math.abs(from[1] - target[1]) > 0.5;
    const place = (point: LngLat, heading: number) => {
      marker.setLngLat(point);
      const state = truckStates.get(key);
      if (state) {
        state.lngLat = point;
        state.course = heading;
      }
      repaint();
    };
    if (jump || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      place(target, course);
      return;
    }
    const step = (time: number) => {
      const t = Math.min((time - start) / ANIMATION_MS, 1);
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
      const along = pointAlong(path, eased);
      place(along.point, along.course ?? course);
      if (t < 1) animations.set(key, requestAnimationFrame(step));
      else {
        animations.delete(key);
        place(target, course);
      }
    };
    animations.set(key, requestAnimationFrame(step));
  }

  // Al inclinar el mapa las unidades pasan a camiones 3D; three.js se descarga entonces.
  function updateTilt() {
    if (!map) return;
    const tilted = map.getPitch() > TILT_3D;
    if (!tilted || truckLayerFailed) {
      threeD = false;
      repaint();
      return;
    }
    if (truckLayerReady) {
      threeD = true;
      map.triggerRepaint();
      return;
    }
    truckLayerReady = true;
    loadThree()
      .then(async (THREE) => [THREE, await loadTruckModel(THREE)] as const)
      .then(([THREE, template]) => {
        if (!map) return;
        map.addLayer(
          createTruckLayer(
            map.__maplibregl,
            THREE,
            () => (threeD ? truckStates.entries() : []),
            template
          )
        );
        threeD = map.getPitch() > TILT_3D;
        map.triggerRepaint();
      })
      .catch(() => {
        // Sin three.js se mantienen los marcadores planos.
        truckLayerFailed = true;
        threeD = false;
      });
  }

  /** Botón 3D/2D junto al control de navegación. */
  function tiltControl() {
    let button: HTMLButtonElement;
    return {
      onAdd(instance: MapLibre) {
        const wrapper = document.createElement('div');
        wrapper.className = 'maplibregl-ctrl maplibregl-ctrl-group';
        button = document.createElement('button');
        button.type = 'button';
        button.className = 'tm-tilt';
        const sync = () => {
          const tilted = instance.getPitch() > TILT_3D;
          button.textContent = tilted ? '2D' : '3D';
          button.title = tilted ? 'Vista plana' : 'Vista 3D con camiones';
          button.setAttribute('aria-label', button.title);
        };
        button.addEventListener('click', () => {
          const tilted = instance.getPitch() > TILT_3D;
          instance.easeTo({
            pitch: tilted ? 0 : 60,
            bearing: tilted ? 0 : instance.getBearing(),
            zoom: tilted ? instance.getZoom() : Math.max(instance.getZoom(), 14),
            duration: 900
          });
        });
        instance.on('pitchend', sync);
        sync();
        wrapper.appendChild(button);
        return wrapper;
      },
      onRemove() {
        button?.parentElement?.remove();
      }
    };
  }

  // Las capas propias se agregan cuando el estilo termina de cargar.
  function addOverlayLayers() {
    if (!map || map.getSource('planned-route')) return;
    map.addSource('site-areas', { type: 'geojson', data: siteAreas([]) });
    map.addLayer({
      id: 'site-areas-fill',
      type: 'fill',
      source: 'site-areas',
      paint: { 'fill-color': '#0f766e', 'fill-opacity': 0.06 }
    });
    map.addLayer({
      id: 'site-areas-line',
      type: 'line',
      source: 'site-areas',
      paint: {
        'line-color': '#0f766e',
        'line-width': 1.5,
        'line-opacity': 0.7,
        'line-dasharray': [2, 2]
      }
    });
    map.addSource('geofences', { type: 'geojson', data: geofenceCollection([]) });
    map.addLayer({
      id: 'geofences-fill',
      type: 'fill',
      source: 'geofences',
      paint: {
        'fill-color': '#7c3aed',
        'fill-opacity': ['case', ['boolean', ['feature-state', 'highlight'], false], 0.24, 0.1]
      }
    });
    map.addLayer({
      id: 'geofences-line',
      type: 'line',
      source: 'geofences',
      paint: { 'line-color': '#7c3aed', 'line-width': 2, 'line-opacity': 0.8 }
    });
    map.addLayer({
      id: 'geofences-label',
      type: 'symbol',
      source: 'geofences',
      layout: {
        'text-field': ['get', 'name'],
        'text-font': ['Noto Sans Bold'],
        'text-size': 12
      },
      paint: { 'text-color': '#5b21b6', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 }
    });
    map.addSource('draft', { type: 'geojson', data: polygon([]) });
    map.addSource('draft-vertices', { type: 'geojson', data: points([]) });
    map.addLayer({
      id: 'draft-fill',
      type: 'fill',
      source: 'draft',
      paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.18 }
    });
    map.addLayer({
      id: 'draft-line',
      type: 'line',
      source: 'draft',
      paint: { 'line-color': '#d97706', 'line-width': 2, 'line-dasharray': [2, 1] }
    });
    map.addLayer({
      id: 'draft-vertices',
      type: 'circle',
      source: 'draft-vertices',
      paint: {
        'circle-radius': 5,
        'circle-color': '#ffffff',
        'circle-stroke-color': '#d97706',
        'circle-stroke-width': 2
      }
    });
    map.addSource('sim-routes', { type: 'geojson', data: lines([]) });
    map.addSource('sim-points', { type: 'geojson', data: lines([]) });
    map.addLayer({
      id: 'sim-routes',
      type: 'line',
      source: 'sim-routes',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#7c3aed',
        'line-width': 3,
        'line-opacity': 0.5,
        'line-dasharray': [0.5, 1.6]
      }
    });
    map.addLayer({
      id: 'sim-points-line',
      type: 'line',
      source: 'sim-points',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: { 'line-color': '#7c3aed', 'line-width': 2, 'line-dasharray': [2, 1.5] }
    });
    map.addLayer({
      id: 'sim-points',
      type: 'circle',
      source: 'sim-points',
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#ffffff',
        'circle-stroke-color': '#7c3aed',
        'circle-stroke-width': 2.5
      }
    });
    map.addLayer({
      id: 'sim-points-label',
      type: 'symbol',
      source: 'sim-points',
      filter: ['==', ['geometry-type'], 'Point'],
      layout: {
        'text-field': ['get', 'label'],
        'text-font': ['Noto Sans Bold'],
        'text-size': 10,
        'text-allow-overlap': true
      },
      paint: { 'text-color': '#6d28d9' }
    });
    map.addSource('original-route', { type: 'geojson', data: line([]) });
    map.addLayer({
      id: 'original-route',
      type: 'line',
      source: 'original-route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#71717a',
        'line-width': 3,
        'line-opacity': 0.45,
        'line-dasharray': [1, 2]
      }
    });
    map.addSource('planned-route', { type: 'geojson', data: line([]) });
    map.addSource('trail', { type: 'geojson', data: line([]) });
    map.addLayer({
      id: 'planned-route',
      type: 'line',
      source: 'planned-route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#0ea5e9',
        'line-width': 3,
        'line-opacity': 0.55,
        'line-dasharray': [1.5, 1.5]
      }
    });
    map.addLayer({
      id: 'trail',
      type: 'line',
      source: 'trail',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0284c7', 'line-width': 4, 'line-opacity': 0.9 }
    });
    styleReady++;
  }

  function createMarkerElement(vehicle: TrackedVehicle): HTMLDivElement {
    const element = document.createElement('div');
    element.className = 'tm-marker';
    element.innerHTML = `<span class="tm-heading"></span><span class="tm-pin"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${TRUCK_PATH}"/></svg></span><span class="tm-label"><span class="tm-name"></span><span class="tm-sim-tag">SIM</span></span>`;
    element.setAttribute('role', 'button');
    element.tabIndex = 0;
    const select = (event: Event) => {
      event.stopPropagation();
      onselect(vehicle.key);
    };
    element.addEventListener('click', select);
    element.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') select(event);
    });
    return element;
  }

  function syncMarkers(maplibregl: MapLibre) {
    const seen = new Set<string>();
    const piloted = untrack(() => pilot?.key ?? null);
    for (const vehicle of vehicles) {
      seen.add(vehicle.key);
      let entry = markers.get(vehicle.key);
      if (!entry) {
        const element = createMarkerElement(vehicle);
        const marker = new maplibregl.Marker({ element, anchor: 'center' })
          .setLngLat([vehicle.longitude, vehicle.latitude])
          .addTo(map);
        entry = { marker, element };
        markers.set(vehicle.key, entry);
      }
      const target: LngLat = [vehicle.longitude, vehicle.latitude];
      const current = entry.marker.getLngLat();
      const from: LngLat = [current.lng, current.lat];
      let state = truckStates.get(vehicle.key);
      if (!state) {
        state = { lngLat: from, course: vehicle.course, status: vehicle.status, selected: false };
        truckStates.set(vehicle.key, state);
      }
      state.status = vehicle.status;
      state.selected = vehicle.key === selectedKey;
      if (vehicle.key === piloted) {
        // La posición manejada manda: la del servidor llega con retraso.
      } else if (from[0] !== target[0] || from[1] !== target[1]) {
        // La unidad del traslado abierto avanza por su recorrido ajustado a calles.
        const path = animationPath(from, target, vehicle.key === selectedKey ? trail : []);
        animateTo(vehicle.key, entry.marker, path, vehicle.course);
      } else {
        state.course = vehicle.course;
      }
      const { element } = entry;
      element.dataset.status = vehicle.status;
      element.classList.toggle('selected', vehicle.key === selectedKey);
      element.classList.toggle('sim', vehicle.simulated);
      element.setAttribute(
        'aria-label',
        `${vehicle.name}${vehicle.simulated ? ' (simulado)' : ''}, ${STATUS_LABELS[vehicle.status]}`
      );
      element.querySelector<HTMLElement>('.tm-name')!.textContent = vehicle.name;
      if (vehicle.key !== piloted)
        element.querySelector<HTMLElement>('.tm-heading')!.style.transform =
          `rotate(${vehicle.course}deg)`;
    }
    for (const [key, entry] of markers) {
      if (!seen.has(key)) {
        cancelAnimationFrame(animations.get(key) ?? 0);
        entry.marker.remove();
        markers.delete(key);
        truckStates.delete(key);
      }
    }
  }

  onMount(() => {
    let disposed = false;
    let resizeObserver: ResizeObserver | undefined;
    loadMapLibre()
      .then((maplibregl) => {
        if (disposed || !container) return;
        const instance = new maplibregl.Map({
          container,
          style: MAP_STYLE,
          center: DEFAULT_CENTER,
          zoom: 9,
          attributionControl: { compact: true }
        });
        instance.addControl(
          new maplibregl.NavigationControl({ visualizePitch: true }),
          'top-right'
        );
        instance.addControl(tiltControl(), 'top-right');
        instance.addControl(new maplibregl.FullscreenControl(), 'top-right');
        instance.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
        instance.on('style.load', addOverlayLayers);
        instance.on('pitch', updateTilt);
        instance.on('click', (event: MapLibre) => {
          if (drawing) ondrawpoint?.([event.lngLat.lng, event.lngLat.lat]);
          else onselect(null);
        });
        instance.on('dblclick', (event: MapLibre) => {
          if (!drawing) return;
          event.preventDefault();
          ondrawfinish?.();
        });
        (instance as MapLibre).__maplibregl = maplibregl;
        map = instance;
        // El contenedor cambia de tamaño sin que cambie la ventana (menú lateral,
        // paneles); MapLibre solo escucha la ventana, así que se le avisa aquí.
        resizeObserver = new ResizeObserver(() => instance.resize());
        resizeObserver.observe(container);
      })
      .catch((error: Error) => (loadError = error.message));
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      animations.forEach((frame) => cancelAnimationFrame(frame));
      markers.forEach((entry) => entry.marker.remove());
      markers.clear();
      map?.remove();
    };
  });

  $effect(() => {
    if (!map) return;
    void selectedKey;
    syncMarkers(map.__maplibregl);
    if (!fitted && vehicles.length) {
      fitted = true;
      const bounds = new map.__maplibregl.LngLatBounds();
      vehicles.forEach((vehicle) => bounds.extend([vehicle.longitude, vehicle.latitude]));
      map.fitBounds(bounds, {
        padding: mapPadding(),
        maxZoom: 13,
        duration: 0
      });
    }
  });

  // Unidad manejada con el joystick: marcador y camión 3D siguen al control en cada cuadro.
  $effect(() => {
    if (!map || !pilot) return;
    const entry = markers.get(pilot.key);
    if (!entry) return;
    cancelAnimationFrame(animations.get(pilot.key) ?? 0);
    animations.delete(pilot.key);
    entry.marker.setLngLat(pilot.lngLat);
    entry.element.querySelector<HTMLElement>('.tm-heading')!.style.transform =
      `rotate(${pilot.course}deg)`;
    const state = truckStates.get(pilot.key);
    if (state) {
      state.lngLat = pilot.lngLat;
      state.course = pilot.course;
    }
    repaint();
    if (follow && pilot.key === selectedKey) map.setCenter(pilot.lngLat);
  });

  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('sim-routes')?.setData(lines(simRoutes));
    map.getSource('sim-points')?.setData(waypointFeatures(simPoints));
  });

  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('trail')?.setData(line(trail));
    map.getSource('planned-route')?.setData(line(plannedRoute ?? []));
    map.getSource('original-route')?.setData(line(originalRoute ?? []));
  });

  let highlighted: number | null = null;
  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('geofences')?.setData(geofenceCollection(geofences));
    if (highlighted !== null)
      map.setFeatureState({ source: 'geofences', id: Math.abs(highlighted) }, { highlight: false });
    highlighted = highlightedGeofence;
    if (highlighted !== null)
      map.setFeatureState({ source: 'geofences', id: Math.abs(highlighted) }, { highlight: true });
  });

  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('site-areas')?.setData(siteAreas(sites));
  });

  // Marcadores de sucursales y almacenes; quedan debajo de las unidades (z-index en CSS).
  $effect(() => {
    if (!map) return;
    siteMarkers.forEach((marker) => marker.remove());
    siteMarkers = [];
    for (const site of sites) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = `tm-site ${site.kind}`;
      element.setAttribute(
        'aria-label',
        `${site.kind === 'branch' ? 'Sucursal' : 'Almacén'} ${site.name}`
      );
      element.innerHTML = `<span class="tm-site-pin">${
        site.kind === 'branch' ? SITE_BRANCH_ICON : SITE_WAREHOUSE_ICON
      }</span>`;
      const popup = new map.__maplibregl.Popup({
        offset: 18,
        closeButton: false,
        maxWidth: '260px'
      }).setDOMContent(sitePopup(site));
      siteMarkers.push(
        new map.__maplibregl.Marker({ element, anchor: 'bottom' })
          .setLngLat([site.longitude, site.latitude])
          .setPopup(popup)
          .addTo(map)
      );
    }
  });

  let sitesFitted = false;
  $effect(() => {
    // Sin unidades en el mapa, se encuadran los lugares de la empresa.
    if (!map || sitesFitted || fitted || vehicles.length || !sites.length) return;
    sitesFitted = true;
    const bounds = new map.__maplibregl.LngLatBounds();
    sites.forEach((site) => bounds.extend([site.longitude, site.latitude]));
    map.fitBounds(bounds, { padding: mapPadding(), maxZoom: 13, duration: 0 });
  });

  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('draft')?.setData(polygon(draft?.ring ?? []));
    map.getSource('draft-vertices')?.setData(points(draft?.vertices ?? []));
  });

  $effect(() => {
    if (!map) return;
    map.getCanvas().style.cursor = drawing ? 'crosshair' : '';
    if (drawing) map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
  });

  $effect(() => {
    if (!map) return;
    focusMarker?.remove();
    focusMarker = null;
    if (!focusPoint) return;
    const element = document.createElement('div');
    element.className = 'tm-focus';
    focusMarker = new map.__maplibregl.Marker({ element }).setLngLat(focusPoint.at).addTo(map);
    map.flyTo({
      center: focusPoint.at,
      zoom: Math.max(map.getZoom(), 13),
      offset: [160, 0],
      duration: 900
    });
  });

  $effect(() => {
    if (!map) return;
    endpointMarkers.forEach((marker) => marker.remove());
    endpointMarkers = [];
    if (!endpoints) return;
    for (const [kind, point] of [
      ['A', endpoints.origin],
      ['B', endpoints.destination]
    ] as const) {
      if (!point) continue;
      const element = document.createElement('div');
      element.className = `tm-endpoint ${kind === 'A' ? 'origin' : 'destination'}`;
      element.innerHTML = `<span class="tm-endpoint-pin"><b>${kind}</b></span><span class="tm-endpoint-label"></span>`;
      element.querySelector<HTMLElement>('.tm-endpoint-label')!.textContent = point.label;
      endpointMarkers.push(
        new map.__maplibregl.Marker({ element, anchor: 'bottom' }).setLngLat(point.at).addTo(map)
      );
    }
  });

  /** Encuadra un contorno completo (lo usa el panel al elegir una geocerca). */
  export function fitRing(ring: LngLat[]) {
    if (!map || !ring.length) return;
    const bounds = new map.__maplibregl.LngLatBounds();
    ring.forEach((point) => bounds.extend(point));
    map.fitBounds(bounds, {
      padding: mapPadding(),
      maxZoom: 16,
      duration: 800
    });
  }

  $effect(() => {
    if (!map || !follow || !selectedKey) return;
    const vehicle = vehicles.find((item) => item.key === selectedKey);
    if (vehicle) map.easeTo({ center: [vehicle.longitude, vehicle.latitude], duration: 800 });
  });

  let lastFocused: string | null = null;
  $effect(() => {
    if (!map || !selectedKey || selectedKey === lastFocused) return;
    lastFocused = selectedKey;
    // En un traslado el mapa encuadra la ruta completa; no se acerca a la unidad.
    if (endpoints) return;
    const vehicle = vehicles.find((item) => item.key === selectedKey);
    if (vehicle)
      map.flyTo({
        center: [vehicle.longitude, vehicle.latitude],
        zoom: Math.max(map.getZoom(), 12),
        offset: [160, 0],
        duration: 900
      });
  });
</script>

<div class="tracking-map" class:tm-3d={threeD} bind:this={container}>
  {#if loadError}
    <div class="map-error">{loadError} Revisa tu conexión a internet.</div>
  {/if}
</div>

<style>
  /* En 3D el camión reemplaza al pin; el marcador queda como zona de clic y etiqueta. */
  .tm-3d :global(.tm-marker .tm-pin),
  .tm-3d :global(.tm-marker .tm-heading) {
    opacity: 0;
  }
  .tm-3d :global(.tm-marker .tm-label) {
    transform: translateY(16px);
  }
  :global(.tm-tilt) {
    font-size: 11px !important;
    font-weight: 700;
    color: #0f172a;
  }

  :global(.tm-site) {
    z-index: 0;
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
  }
  :global(.tm-site-pin) {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border: 2px solid #fff;
    border-radius: 50% 50% 50% 0;
    background: #0f766e;
    color: #fff;
    box-shadow: 0 2px 6px rgb(15 23 42 / 0.3);
    transform: rotate(-45deg);
  }
  :global(.tm-site-pin svg) {
    transform: rotate(45deg);
  }
  :global(.tm-site.warehouse .tm-site-pin) {
    background: #b45309;
  }
  :global(.tm-marker) {
    z-index: 2;
  }
  :global(.tm-site-popup) {
    display: grid;
    gap: 4px;
    font-size: 12px;
    color: #0f172a;
  }
  :global(.tm-site-popup strong) {
    font-size: 13px;
  }
  :global(.tm-site-popup small) {
    color: #64748b;
  }
  :global(.tm-site-popup ul) {
    display: grid;
    gap: 2px;
    margin: 4px 0 0;
    padding-left: 14px;
  }

  .tracking-map {
    position: absolute;
    inset: 0;
    background: rgb(var(--surface-muted));
  }
  .map-error {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 24px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-align: center;
  }
  :global(.tm-marker) {
    position: relative;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    cursor: pointer;
    --tm-color: 22 163 74;
  }
  :global(.tm-marker[data-status='stopped']) {
    --tm-color: 217 119 6;
  }
  :global(.tm-marker[data-status='offline']) {
    --tm-color: 113 113 122;
  }
  :global(.tm-marker .tm-pin) {
    position: relative;
    z-index: 1;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 2px solid #fff;
    border-radius: 50%;
    background: rgb(var(--tm-color));
    color: #fff;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.35);
    transition: transform 150ms;
  }
  :global(.tm-marker .tm-heading) {
    position: absolute;
    inset: -7px;
    transition: transform 600ms ease-out;
  }
  :global(.tm-marker .tm-heading::before) {
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-bottom: 9px solid rgb(var(--tm-color));
  }
  :global(.tm-marker:not([data-status='moving']) .tm-heading) {
    display: none;
  }
  :global(.tm-marker .tm-label) {
    position: absolute;
    top: 36px;
    left: 50%;
    transform: translateX(-50%);
    padding: 1px 6px;
    border-radius: 4px;
    background: rgb(255 255 255 / 0.92);
    color: #18181b;
    font-size: 10px;
    font-weight: 650;
    white-space: nowrap;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.25);
  }
  /* GPS virtual del simulador: contorno punteado violeta y etiqueta SIM, también en 3D. */
  :global(.tm-marker .tm-sim-tag) {
    display: none;
    margin-left: 4px;
    padding: 0 4px;
    border-radius: 3px;
    background: #7c3aed;
    color: #fff;
    font-size: 8.5px;
    font-weight: 800;
    letter-spacing: 0.06em;
  }
  :global(.tm-marker.sim .tm-sim-tag) {
    display: inline-block;
  }
  :global(.tm-marker.sim .tm-pin) {
    outline: 2px dashed #7c3aed;
    outline-offset: 2px;
  }
  :global(.tm-marker.selected) {
    z-index: 2;
  }
  :global(.tm-marker.selected .tm-pin) {
    transform: scale(1.18);
    box-shadow:
      0 0 0 4px rgb(var(--tm-color) / 0.35),
      0 2px 10px rgb(0 0 0 / 0.4);
  }
  :global(.tm-marker:focus-visible) {
    outline: none;
  }
  :global(.tm-marker:focus-visible .tm-pin) {
    box-shadow: 0 0 0 3px rgb(var(--primary));
  }
  :global(.tm-endpoint) {
    display: grid;
    justify-items: center;
    pointer-events: none;
  }
  :global(.tm-endpoint-pin) {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border: 3px solid #fff;
    border-radius: 50% 50% 50% 0;
    background: #0f172a;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    transform: rotate(-45deg);
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.35);
  }
  :global(.tm-endpoint.destination .tm-endpoint-pin) {
    background: #16a34a;
  }
  :global(.tm-endpoint-pin b) {
    transform: rotate(45deg);
  }
  :global(.tm-endpoint-label) {
    order: -1;
    margin-bottom: 4px;
    padding: 2px 7px;
    border-radius: 5px;
    background: rgb(255 255 255 / 0.95);
    color: #18181b;
    font-size: 11px;
    font-weight: 650;
    white-space: nowrap;
    box-shadow: 0 1px 4px rgb(0 0 0 / 0.25);
  }
  :global(.tm-focus) {
    width: 22px;
    height: 22px;
    border: 3px solid #fff;
    border-radius: 50%;
    background: rgb(220 38 38);
    box-shadow: 0 0 0 0 rgb(220 38 38 / 0.6);
    animation: tm-ping 1.4s ease-out infinite;
  }
  @keyframes -global-tm-ping {
    to {
      box-shadow: 0 0 0 18px rgb(220 38 38 / 0);
    }
  }
  :global(.tracking-map .maplibregl-ctrl-group) {
    border-radius: 10px;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.18);
  }
</style>
