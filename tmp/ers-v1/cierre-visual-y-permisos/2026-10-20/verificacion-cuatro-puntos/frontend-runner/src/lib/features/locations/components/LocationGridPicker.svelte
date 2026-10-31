<script lang="ts">
  import { tick } from 'svelte';
  import type { LocationOut } from '../types';

  interface Props {
    id: string;
    locations: LocationOut[];
    selectedLocationId: string;
    productName: string;
    disabled?: boolean;
    hasMoreLocations?: boolean;
    onselect: (locationId: string) => void;
  }

  interface LocationGroup {
    key: string;
    area: string;
    aisle: string;
    rack: string;
    locations: LocationOut[];
  }

  interface AisleLane {
    key: string;
    area: string;
    aisle: string;
    racks: LocationGroup[];
  }

  let {
    id,
    locations,
    selectedLocationId,
    productName,
    disabled = false,
    hasMoreLocations = false,
    onselect
  }: Props = $props();

  let open = $state(false);
  let rackChosen = $state(false);
  let selectedGroupKey = $state('');
  let search = $state('');
  let triggerButton = $state<HTMLButtonElement | null>(null);
  let rackMapRegion = $state<HTMLElement | null>(null);
  let rackDetailsButton = $state<HTMLButtonElement | null>(null);

  const collator = new Intl.Collator('es-SV', { numeric: true, sensitivity: 'base' });

  function component(value: string | null | undefined): string {
    const normalized = value?.trim() ?? '';
    return normalized && normalized !== '-' ? normalized : '';
  }

  function groupKey(location: Pick<LocationOut, 'area' | 'aisle' | 'rack'>): string {
    return JSON.stringify([
      component(location.area),
      component(location.aisle),
      component(location.rack)
    ]);
  }

  function locationRoute(location: LocationOut): string {
    return [
      component(location.area) ? `Área ${component(location.area)}` : '',
      component(location.aisle) ? `Pasillo ${component(location.aisle)}` : '',
      component(location.rack) ? `Rack ${component(location.rack)}` : '',
      component(location.level) ? `Nivel ${component(location.level)}` : '',
      component(location.position) ? `Posición ${component(location.position)}` : ''
    ]
      .filter(Boolean)
      .join(' · ');
  }

  function locationLabel(location: LocationOut): string {
    const route = locationRoute(location);
    return route ? `${location.code} · ${route}` : location.code;
  }

  function matrixCellKey(level: string, position: string): string {
    return JSON.stringify([level, position]);
  }

  let groups = $derived.by(() => {
    const grouped = new Map<string, LocationGroup>();
    for (const location of locations) {
      const key = groupKey(location);
      const existing = grouped.get(key);
      if (existing) {
        existing.locations.push(location);
      } else {
        grouped.set(key, {
          key,
          area: component(location.area),
          aisle: component(location.aisle),
          rack: component(location.rack),
          locations: [location]
        });
      }
    }
    return [...grouped.values()].sort((left, right) =>
      collator.compare(groupLabel(left), groupLabel(right))
    );
  });

  let aisleLanes = $derived.by(() => {
    const lanes = new Map<string, AisleLane>();
    for (const group of groups) {
      const key = JSON.stringify([group.area, group.aisle]);
      const lane = lanes.get(key);
      if (lane) {
        lane.racks.push(group);
      } else {
        lanes.set(key, {
          key,
          area: group.area,
          aisle: group.aisle,
          racks: [group]
        });
      }
    }
    return [...lanes.values()].sort((left, right) =>
      collator.compare(`${left.area} ${left.aisle}`, `${right.area} ${right.aisle}`)
    );
  });

  let selectedLocation = $derived(
    locations.find((location) => location.id === selectedLocationId) ?? null
  );

  let activeGroupKey = $derived.by(() => {
    if (selectedGroupKey && groups.some((group) => group.key === selectedGroupKey)) {
      return selectedGroupKey;
    }
    if (selectedLocation) return groupKey(selectedLocation);
    return groups[0]?.key ?? '';
  });

  let activeGroup = $derived(groups.find((group) => group.key === activeGroupKey) ?? null);
  let levels = $derived(
    activeGroup
      ? [
          ...new Set(
            activeGroup.locations.map((location) => component(location.level)).filter(Boolean)
          )
        ].sort((left, right) => collator.compare(left, right))
      : []
  );
  let positions = $derived(
    activeGroup
      ? [
          ...new Set(
            activeGroup.locations.map((location) => component(location.position)).filter(Boolean)
          )
        ].sort((left, right) => collator.compare(left, right))
      : []
  );
  let matrixCells = $derived.by(() => {
    const cells = new Map<string, LocationOut[]>();
    for (const location of activeGroup?.locations ?? []) {
      const level = component(location.level);
      const position = component(location.position);
      if (!level || !position) continue;
      const key = matrixCellKey(level, position);
      const cell = cells.get(key);
      if (cell) cell.push(location);
      else cells.set(key, [location]);
    }
    return cells;
  });
  let hasMatrix = $derived(levels.length > 0 && positions.length > 0);
  let unplacedLocations = $derived(
    locations.filter((location) => !component(location.level) || !component(location.position))
  );
  let filteredLocations = $derived.by(() => {
    const query = search.trim().toLocaleLowerCase('es-SV');
    return locations
      .filter(
        (location) => !query || locationLabel(location).toLocaleLowerCase('es-SV').includes(query)
      )
      .sort((left, right) => collator.compare(locationLabel(left), locationLabel(right)));
  });

  function groupLabel(group: LocationGroup): string {
    return (
      [
        group.area ? `Área ${group.area}` : '',
        group.aisle ? `Pasillo ${group.aisle}` : '',
        group.rack ? `Rack ${group.rack}` : ''
      ]
        .filter(Boolean)
        .join(' · ') || 'Ubicaciones sin pasillo o rack'
    );
  }

  function locationsAt(level: string, position: string): LocationOut[] {
    return matrixCells.get(matrixCellKey(level, position)) ?? [];
  }

  function groupPositions(group: LocationGroup): string[] {
    return [
      ...new Set(group.locations.map((location) => component(location.position)).filter(Boolean))
    ].sort((left, right) => collator.compare(left, right));
  }

  function groupLevels(group: LocationGroup): string[] {
    return [
      ...new Set(group.locations.map((location) => component(location.level)).filter(Boolean))
    ].sort((left, right) => collator.compare(left, right));
  }

  function groupHasCoordinate(group: LocationGroup, level: string, position: string): boolean {
    return group.locations.some(
      (location) => component(location.level) === level && component(location.position) === position
    );
  }

  function openPicker() {
    selectedGroupKey = selectedLocation ? groupKey(selectedLocation) : (groups[0]?.key ?? '');
    search = '';
    rackChosen = Boolean(selectedLocation);
    open = true;
  }

  async function chooseRack(group: LocationGroup) {
    selectedGroupKey = group.key;
    rackChosen = true;
    await tick();
    rackDetailsButton?.focus();
  }

  async function showRackMap() {
    rackChosen = false;
    await tick();
    rackMapRegion?.focus();
  }

  function choose(location: LocationOut) {
    onselect(location.id);
    selectedGroupKey = groupKey(location);
    open = false;
    void returnFocus();
  }

  async function returnFocus() {
    await tick();
    triggerButton?.focus();
  }
</script>

<div class="min-w-0 space-y-2">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <div class="min-w-0">
      <p class="font-medium text-foreground">Ubicación de destino</p>
      {#if selectedLocation}
        <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1" aria-live="polite">
          <p class="break-words text-xs text-foreground-muted">
            <span class="font-semibold text-primary">{selectedLocation.code}</span>
            <span>· {locationRoute(selectedLocation) || 'Ruta sin desglose'}</span>
          </p>
          <span
            class="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
          >
            <span aria-hidden="true">✓</span> Destino asignado
          </span>
        </div>
      {:else}
        <p class="mt-1 text-xs text-foreground-muted">Selecciona una casilla real del almacén.</p>
      {/if}
    </div>
    <button
      type="button"
      class="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground transition-colors motion-reduce:transition-none hover:border-primary/60 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
      aria-expanded={open}
      aria-controls={`location-map-${id}`}
      disabled={disabled || locations.length === 0}
      bind:this={triggerButton}
      onclick={() => (open ? (open = false) : openPicker())}
    >
      {open ? 'Cerrar mapa' : selectedLocation ? 'Cambiar ubicación' : 'Elegir en el mapa'}
    </button>
  </div>

  <section
    id={`location-map-${id}`}
    class="space-y-3 rounded-lg border border-border bg-surface-muted p-3"
    aria-label={`Mapa de ubicaciones para ${productName}`}
    hidden={!open}
  >
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <p class="text-sm font-semibold text-foreground">Ubica el producto</p>
        <p class="mt-1 max-w-xl text-xs text-foreground-muted">
          {productName}. Elige un pasillo, abre el rack y selecciona nivel/posición.
        </p>
      </div>
      <span
        class="rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-foreground-muted"
      >
        Ubicaciones cargadas: {locations.length}
      </span>
    </div>

    {#if hasMoreLocations}
      <p
        class="rounded-md border border-info/20 bg-info/5 px-3 py-2 text-xs leading-relaxed text-foreground-muted"
        role="status"
      >
        La cuadrícula muestra {locations.length} ubicaciones cargadas. Hay más en el almacén; usa «Cargar
        más ubicaciones» encima de las líneas para añadirlas al mapa.
      </p>
    {/if}

    {#if locations.length === 0}
      <p
        class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
        role="status"
      >
        Este almacén no tiene ubicaciones activas para seleccionar.
      </p>
    {:else}
      {#if !rackChosen}
        <section
          class="space-y-3 rounded-xl border border-border bg-surface p-3"
          aria-label="Vista superior esquemática del almacén"
          tabindex="-1"
          bind:this={rackMapRegion}
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h4 class="text-sm font-semibold text-foreground">Distribución del almacén</h4>
              <p class="mt-1 text-xs text-foreground-muted">
                Esquema orientativo por pasillo y rack; no está a escala.
              </p>
            </div>
            <span class="text-xs text-foreground-muted">
              Pasillos: {aisleLanes.length} · Ubicaciones cargadas: {locations.length}
            </span>
          </div>

          <div class="space-y-2">
            {#each aisleLanes as lane, laneIndex (lane.key)}
              <div
                class="grid gap-2 rounded-lg border border-border bg-surface-muted p-2 sm:p-3 md:grid-cols-[8rem_minmax(0,1fr)]"
              >
                <div
                  class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 md:flex-col md:items-start md:justify-center"
                >
                  <div class="min-w-24 text-center md:text-left">
                    <span
                      class="block text-xs font-medium uppercase tracking-wide text-foreground-muted"
                      >Pasillo</span
                    >
                    <span class="font-semibold text-primary">{lane.aisle || 'Sin código'}</span>
                  </div>
                  {#if lane.area}
                    <span class="text-xs text-foreground-muted">Área {lane.area}</span>
                  {/if}
                </div>

                <div
                  class="relative min-w-0 rounded-md border border-dashed border-border bg-background/40 p-2"
                >
                  <div
                    class="mb-2 flex items-center gap-2 px-1 text-[11px] font-medium uppercase tracking-wide text-foreground-subtle"
                    aria-hidden="true"
                  >
                    <span class="flex-1 border-t border-dashed border-primary/30"></span>
                    <span>Pasillo de circulación</span>
                    <span class="flex-1 border-t border-dashed border-primary/30"></span>
                  </div>
                  <div
                    class="relative grid grid-cols-1 gap-x-3 gap-y-2 sm:grid-cols-2 lg:grid-flow-col lg:auto-cols-fr lg:grid-cols-none"
                  >
                    {#each lane.racks as group, rackIndex (group.key)}
                      {@const rackLevels = groupLevels(group)}
                      {@const rackPositions = groupPositions(group)}
                      {@const previewLevels = rackLevels.slice(0, 3)}
                      {@const previewPositions = rackPositions.slice(0, 4)}
                      {@const previewId = `rack-preview-${id}-${laneIndex}-${rackIndex}`}
                      <button
                        type="button"
                        class={`min-h-20 rounded-sm border-x-4 border-b-4 border-t-2 p-2.5 text-left transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                          rackChosen && activeGroupKey === group.key
                            ? 'border-primary bg-primary/10 ring-1 ring-primary'
                            : 'border-border bg-surface hover:border-primary/60 hover:bg-surface-hover'
                        }`}
                        aria-pressed={rackChosen && activeGroupKey === group.key}
                        aria-describedby={previewId}
                        aria-label={`Seleccionar ${groupLabel(group)}; ${group.locations.length} ubicaciones cargadas`}
                        {disabled}
                        onclick={() => void chooseRack(group)}
                      >
                        <span class="flex items-center justify-between gap-2">
                          <span class="min-w-0">
                            <span class="block text-xs text-foreground-muted">Rack / estante</span>
                            <span class="block truncate font-semibold text-foreground">
                              {group.rack || 'Sin código'}
                            </span>
                          </span>
                          <span
                            class="shrink-0 rounded-full border border-border bg-surface-muted px-2 py-1 text-xs text-foreground-muted"
                          >
                            {group.locations.length} ubic.
                          </span>
                        </span>
                        {#if previewLevels.length > 0 && previewPositions.length > 0}
                          <span class="mt-2 block border-t border-border bg-background/70 p-2">
                            <span
                              class="mb-1 grid gap-1 text-center text-[11px] text-foreground-muted"
                              style={`grid-template-columns: 1.6rem repeat(${previewPositions.length}, minmax(0, 1fr))`}
                              aria-hidden="true"
                            >
                              <span>NV</span>
                              {#each previewPositions as position (position)}
                                <span class="truncate">{position}</span>
                              {/each}
                            </span>
                            <span class="grid gap-1">
                              {#each previewLevels as level (level)}
                                <span
                                  class="grid gap-1 text-center"
                                  style={`grid-template-columns: 1.6rem repeat(${previewPositions.length}, minmax(0, 1fr))`}
                                  aria-hidden="true"
                                >
                                  <span
                                    class="self-center truncate text-[11px] text-foreground-muted"
                                    >{level}</span
                                  >
                                  {#each previewPositions as position (position)}
                                    {@const configured = groupHasCoordinate(group, level, position)}
                                    <span
                                      class={`flex h-6 items-center justify-center border text-[11px] ${
                                        configured
                                          ? 'border-primary/40 bg-primary/20 text-primary'
                                          : hasMoreLocations
                                            ? 'border-info/30 bg-info/5 text-info'
                                            : 'border-border border-dashed text-foreground-subtle'
                                      }`}
                                    >
                                      {configured ? '●' : hasMoreLocations ? '?' : '—'}
                                    </span>
                                  {/each}
                                </span>
                              {/each}
                            </span>
                            {#if rackLevels.length > 3 || rackPositions.length > 4}
                              <span class="mt-1 block text-right text-[11px] text-foreground-muted">
                                Vista parcial
                                {rackLevels.length > 3
                                  ? ` · +${rackLevels.length - 3} niveles`
                                  : ''}{rackPositions.length > 4
                                  ? ` · +${rackPositions.length - 4} posiciones`
                                  : ''}
                              </span>
                            {/if}
                          </span>
                        {:else}
                          <span
                            class="mt-2 block rounded-md border border-dashed border-border px-2 py-3 text-center text-xs text-foreground-muted"
                          >
                            Sin niveles y posiciones para previsualizar
                          </span>
                        {/if}
                        <span id={previewId} class="sr-only">
                          {#if previewLevels.length > 0 && previewPositions.length > 0}
                            Vista previa con filas por nivel y columnas por posición.
                            {#each previewLevels as level (level)}
                              Nivel {level}:
                              {#each previewPositions as position (position)}
                                Posición {position}: {groupHasCoordinate(group, level, position)
                                  ? 'ubicación registrada'
                                  : hasMoreLocations
                                    ? 'pendiente de cargar más ubicaciones'
                                    : 'sin ubicación activa'}.
                              {/each}
                            {/each}
                            {#if rackLevels.length > 3 || rackPositions.length > 4}
                              La miniatura no muestra todos los niveles o posiciones.
                            {/if}
                          {:else}
                            Este rack no tiene niveles y posiciones suficientes para una vista
                            previa.
                          {/if}
                        </span>
                        <span class="mt-2 block text-xs font-medium text-primary">
                          Abrir rack →
                        </span>
                      </button>
                    {/each}
                  </div>
                </div>
              </div>
            {/each}
          </div>
          <div
            class="flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-2 text-xs text-foreground-muted"
          >
            <span
              ><span class="mr-1 text-primary" aria-hidden="true">●</span> Ubicación registrada</span
            >
            {#if hasMoreLocations}
              <span><span class="mr-1 text-info" aria-hidden="true">?</span> Por cargar</span>
            {:else}
              <span
                ><span class="mr-1 text-foreground-subtle" aria-hidden="true">—</span> Sin ubicación configurada</span
              >
            {/if}
            <span>La cuadrícula indica ubicaciones, no existencias.</span>
          </div>
        </section>
      {:else if activeGroup}
        <div
          class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2"
        >
          <div>
            <p class="text-xs text-foreground-muted">Rack seleccionado</p>
            <p class="text-sm font-semibold text-foreground">{groupLabel(activeGroup)}</p>
          </div>
          <button
            type="button"
            class="min-h-10 rounded-lg border border-border bg-surface-muted px-3 py-2 text-sm font-medium text-foreground hover:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            {disabled}
            bind:this={rackDetailsButton}
            onclick={() => void showRackMap()}
          >
            Cambiar pasillo o rack
          </button>
        </div>
      {/if}

      {#if rackChosen && hasMatrix && activeGroup}
        <div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1">
          <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">
            <span class="mr-1 text-primary" aria-hidden="true">▦</span> Mapa del rack
          </p>
          <p class="text-xs text-foreground-muted">
            Filas: nivel <span aria-hidden="true">↓</span> · Columnas: posición
            <span aria-hidden="true">→</span>
          </p>
        </div>
        {#if positions.length <= 6}
          <div class="hidden overflow-x-auto rounded-lg border border-border bg-surface lg:block">
            <table class="w-full border-separate border-spacing-1 p-1 text-center text-xs">
              <caption class="sr-only">
                Vista de {groupLabel(activeGroup)}. Las filas representan niveles y las columnas
                representan posiciones.
              </caption>
              <thead>
                <tr>
                  <th
                    scope="col"
                    class="min-w-12 px-1 py-2 text-left font-medium text-foreground-muted sm:min-w-20 sm:px-2"
                    >Nivel</th
                  >
                  {#each positions as position (position)}
                    <th
                      scope="col"
                      class="min-w-12 px-1 py-2 font-medium text-foreground-muted sm:min-w-24 sm:px-2"
                      >{position}</th
                    >
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each levels as level (level)}
                  <tr>
                    <th
                      scope="row"
                      class="min-w-12 px-1 py-1 text-left font-semibold text-foreground sm:px-2"
                      >{level}</th
                    >
                    {#each positions as position (position)}
                      {@const cells = locationsAt(level, position)}
                      <td class="min-w-12 p-0.5 sm:min-w-24">
                        {#if cells.length}
                          {#if cells.length > 1}
                            <p class="mb-1 text-xs font-medium text-warning">
                              {cells.length} destinos
                            </p>
                          {/if}
                          <div class="flex min-w-12 flex-col gap-1 sm:min-w-24">
                            {#each cells as location (location.id)}
                              <button
                                type="button"
                                class={`flex min-h-12 w-full flex-col items-center justify-center rounded-md border px-1 py-1.5 text-center transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:min-h-14 sm:px-2 ${
                                  selectedLocationId === location.id
                                    ? 'border-primary bg-primary/10 text-primary ring-1 ring-primary'
                                    : 'border-border bg-surface-muted text-foreground hover:border-primary/60 hover:bg-primary/5'
                                }`}
                                aria-pressed={selectedLocationId === location.id}
                                aria-label={`Asignar ${locationLabel(location)} a ${productName}`}
                                {disabled}
                                onclick={() => choose(location)}
                              >
                                <span class="break-words font-semibold leading-tight"
                                  >{location.code}</span
                                >
                                <span class="mt-0.5 hidden text-xs text-foreground-muted sm:block">
                                  {selectedLocationId === location.id
                                    ? 'Destino elegido'
                                    : 'Elegir casilla'}
                                </span>
                              </button>
                            {/each}
                          </div>
                        {:else}
                          <span
                            class={`flex min-h-12 min-w-12 items-center justify-center rounded-md border border-dashed text-xs font-medium sm:min-h-14 sm:min-w-24 ${
                              hasMoreLocations
                                ? 'border-info/30 bg-info/5 text-info'
                                : 'border-border text-foreground-subtle'
                            }`}
                            role="img"
                            aria-label={`Nivel ${level}, posición ${position}: ${hasMoreLocations ? 'aún no se cargó una ubicación' : 'sin ubicación activa configurada'}`}
                          >
                            {hasMoreLocations ? '?' : '—'}
                          </span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
        <div
          class={`space-y-2 ${positions.length <= 6 ? 'lg:hidden' : ''}`}
          aria-label="Niveles y posiciones del rack"
        >
          {#each levels as level (level)}
            <section class="rounded-lg border border-border bg-surface p-3">
              <h5 class="mb-2 text-sm font-semibold text-foreground">Nivel {level}</h5>
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
                {#each positions as position (position)}
                  {@const cells = locationsAt(level, position)}
                  <div class="min-w-0 rounded-md border border-border bg-surface-muted p-2">
                    <p class="mb-2 text-xs font-medium text-foreground-muted">
                      Posición {position}
                    </p>
                    {#if cells.length}
                      <div class="space-y-1">
                        {#each cells as location (location.id)}
                          <button
                            type="button"
                            class={`min-h-12 w-full break-words rounded-md border px-2 py-2 text-left text-xs font-semibold transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                              selectedLocationId === location.id
                                ? 'border-primary bg-primary/10 text-primary ring-1 ring-primary'
                                : 'border-border bg-surface text-foreground hover:border-primary/60'
                            }`}
                            aria-pressed={selectedLocationId === location.id}
                            aria-label={`Asignar ${locationLabel(location)} a ${productName}`}
                            {disabled}
                            onclick={() => choose(location)}
                          >
                            {location.code}
                            {#if selectedLocationId === location.id}
                              <span class="ml-1 text-success">✓</span>
                            {/if}
                          </button>
                        {/each}
                      </div>
                    {:else}
                      <span
                        class={`flex min-h-12 items-center justify-center rounded-md border border-dashed text-sm font-medium ${
                          hasMoreLocations
                            ? 'border-info/30 bg-info/5 text-info'
                            : 'border-border text-foreground-subtle'
                        }`}
                        role="img"
                        aria-label={`Nivel ${level}, posición ${position}: ${hasMoreLocations ? 'aún no se cargó una ubicación' : 'sin ubicación activa configurada'}`}
                      >
                        {hasMoreLocations ? '?' : '—'}
                      </span>
                    {/if}
                  </div>
                {/each}
              </div>
            </section>
          {/each}
        </div>
        <p class="text-xs leading-relaxed text-foreground-muted">
          Solo aparecen como seleccionables las ubicaciones activas registradas.
          {#if hasMoreLocations}
            Las casillas «?» aún no están confirmadas; carga las ubicaciones restantes antes de
            asumir que están vacías.
          {:else}
            Las casillas con guion no tienen una ubicación activa configurada.
          {/if}
          Las casillas se agrupan por nivel y se adaptan al ancho; con teclado, usa Tab y Enter para elegir.
        </p>
      {:else if rackChosen}
        <p
          class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
          role="status"
        >
          Este grupo no tiene nivel y posición suficientes para dibujar la cuadrícula. Usa la lista
          {hasMoreLocations ? 'de ubicaciones cargadas.' : 'completa de ubicaciones.'}
        </p>
      {/if}

      {#if unplacedLocations.length > 0 || !hasMatrix}
        <details class="rounded-lg border border-border bg-surface px-3 py-2">
          <summary
            class="cursor-pointer rounded-sm text-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {hasMoreLocations ? 'Ver ubicaciones cargadas' : 'Ver lista completa de ubicaciones'}
          </summary>
          <label class="mt-3 block text-sm">
            <span class="font-medium text-foreground">Buscar por código o ruta</span>
            <input
              type="search"
              class="mt-1 h-10 w-full rounded-lg border border-border bg-surface-muted px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              bind:value={search}
              placeholder="Ej. REC-01 o pasillo REC"
              {disabled}
            />
          </label>
          <ul class="mt-2 max-h-56 space-y-1 overflow-y-auto" aria-label="Ubicaciones activas">
            {#each filteredLocations as location (location.id)}
              <li>
                <button
                  type="button"
                  class={`min-h-10 w-full rounded-md border px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    selectedLocationId === location.id
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-transparent text-foreground hover:border-border hover:bg-surface-muted'
                  }`}
                  aria-pressed={selectedLocationId === location.id}
                  aria-label={`Asignar ${locationLabel(location)} a ${productName}`}
                  {disabled}
                  onclick={() => choose(location)}
                >
                  {locationLabel(location)}
                </button>
              </li>
            {:else}
              <li class="px-3 py-2 text-sm text-foreground-muted">No hay coincidencias.</li>
            {/each}
          </ul>
        </details>
      {/if}
    {/if}
  </section>
</div>
