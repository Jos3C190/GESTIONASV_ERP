<script lang="ts">
  import { tick, untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import HandlingUnitLabelDialog from './HandlingUnitLabelDialog.svelte';
  import LocationGridPicker from '$lib/features/locations/components/LocationGridPicker.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { inventoryApi } from '../services';
  import { preparationApi, preparationQuantityIssue, type PreparationUnit } from '../preparation';

  let {
    warehouseId,
    contextKey,
    canOperate = false,
    onplaced
  }: {
    warehouseId: string;
    contextKey: string;
    canOperate?: boolean;
    onplaced?: () => void;
  } = $props();
  let units = $state<PreparationUnit[]>([]);
  let selected = $state<PreparationUnit | null>(null);
  let labelUnit = $state<PreparationUnit | null>(null);
  let total = $state(0);
  let page = $state(1);
  let pages = $state(1);
  let search = $state('');
  let query = $state('');
  let revision = $state(0);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let errorField = $state<'scan' | 'quantity' | 'location' | 'measurement' | null>(null);
  let message = $state<string | null>(null);
  let unitScan = $state('');
  let locationScan = $state('');
  let quantity = $state('');
  let weight = $state('');
  let volume = $state('');
  let locations = $state<LocationOut[]>([]);
  let locationPage = $state(0);
  let moreLocations = $state(false);
  let loadingLocations = $state(false);
  let locationError = $state<string | null>(null);
  let locationSequence = 0;
  let sequence = 0;
  let alive = true;
  let preferredId: string | null = null;
  const attempts = new Map<string, string>();
  const field =
    'min-h-11 w-full min-w-0 rounded-lg border border-border-control bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
  const phaseName = {
    measure: 'Revisar medidas',
    label: 'Colocar etiqueta',
    place: 'Lista para ubicar'
  };
  let partial = $derived(
    !!selected && Number(quantity) > 0 && Number(quantity) < selected.quantity_base
  );
  let nextStep = $derived(
    partial
      ? 'preparation-split'
      : selected?.phase === 'measure'
        ? 'preparation-weight'
        : selected?.phase === 'label'
          ? 'preparation-label'
          : 'preparation-location'
  );
  const formatQuantity = (value: number) =>
    value.toLocaleString('es-SV', { maximumFractionDigits: 6 });

  $effect(() => {
    const id = selected?.id;
    const phase = selected?.phase;
    void warehouseId;
    void contextKey;
    locationSequence++;
    locations = [];
    locationPage = 0;
    moreLocations = false;
    loadingLocations = false;
    locationError = null;
    if (id && phase === 'place') untrack(() => void loadLocations(true));
    return () => {
      locationSequence++;
    };
  });

  async function loadLocations(reset = false) {
    if (loadingLocations) return;
    const request = locationSequence;
    const warehouse = warehouseId;
    const nextPage = reset ? 1 : locationPage + 1;
    loadingLocations = true;
    locationError = null;
    try {
      const result = await listLocations(warehouse, {
        page: nextPage,
        size: 100,
        is_active: true,
        lifecycle_status: 'active'
      });
      if (request !== locationSequence) return;
      const eligible = result.items.filter(
        (location) =>
          location.warehouse_id === warehouse &&
          location.is_active &&
          location.lifecycle_status === 'active' &&
          location.storage_eligible
      );
      locations = reset
        ? eligible
        : [
            ...new Map(
              [...locations, ...eligible].map((location) => [location.id, location])
            ).values()
          ];
      locationPage = nextPage;
      moreLocations = result.meta.page < result.meta.pages;
    } catch (cause) {
      if (request === locationSequence)
        locationError =
          cause instanceof Error ? cause.message : 'No se pudieron cargar las ubicaciones.';
    } finally {
      if (request === locationSequence) loadingLocations = false;
    }
  }

  $effect(() => {
    void warehouseId;
    void contextKey;
    const currentPage = page;
    const currentQuery = query;
    void revision;
    const request = ++sequence;
    loading = true;
    error = null;
    untrack(() => {
      units = [];
      selected = null;
      labelUnit = null;
    });
    void preparationApi
      .list(warehouseId, currentPage, currentQuery)
      .then((result) => {
        if (!alive || request !== sequence) return;
        units = result.items;
        total = result.meta.total;
        pages = Math.max(1, result.meta.pages);
        if (page > pages) {
          page = pages;
          return;
        }
        const retained = units.find((unit) => unit.id === preferredId);
        if (retained) {
          choose(retained, false);
          void tick().then(() =>
            document
              .getElementById(
                retained.phase === 'label' ? 'preparation-label' : 'preparation-unit-scan'
              )
              ?.focus()
          );
        } else if (message) {
          void tick().then(() => document.getElementById('preparation-heading')?.focus());
        }
        preferredId = null;
      })
      .catch((cause) => {
        if (alive && request === sequence)
          error = cause instanceof Error ? cause.message : 'No se pudieron cargar los pendientes.';
      })
      .finally(() => {
        if (alive && request === sequence) loading = false;
      });
    return () => {
      sequence += 1;
    };
  });
  $effect(() => {
    alive = true;
    return () => {
      alive = false;
      sequence += 1;
    };
  });
  $effect(() => {
    void unitScan;
    void locationScan;
    void quantity;
    void weight;
    void volume;
    actionError = null;
    errorField = null;
  });

  function choose(unit: PreparationUnit, focus = true) {
    selected = unit;
    unitScan = unit.code;
    locationScan = '';
    quantity = String(unit.quantity_base);
    weight = '';
    volume = '';
    actionError = null;
    if (focus) void tick().then(() => document.getElementById('preparation-unit-scan')?.focus());
  }
  function refresh(id?: string) {
    preferredId = id ?? null;
    revision += 1;
  }
  function scannerNext(event: KeyboardEvent, nextId: string) {
    if (event.key === 'Enter') {
      event.preventDefault();
      document.getElementById(nextId)?.focus();
    }
  }
  async function measure() {
    if (!selected || busy) return;
    if (
      ![weight, volume].every(
        (value) => value.trim() && Number.isFinite(Number(value)) && Number(value) > 0
      )
    ) {
      errorField = 'measurement';
      actionError = 'Indica el peso bruto y volumen positivos de esta unidad completa.';
      return;
    }
    const request = sequence;
    const id = selected.id;
    busy = true;
    actionError = null;
    try {
      await inventoryApi.verifyHandlingUnitMeasurements(id, {
        gross_weight_kg: Number(weight),
        volume_m3: Number(volume)
      });
      if (!alive || request !== sequence) return;
      message = 'Medidas verificadas. Continúa con la etiqueta de esta unidad.';
      refresh(id);
    } catch (cause) {
      if (alive && request === sequence)
        actionError =
          cause instanceof Error ? cause.message : 'No se pudieron guardar las medidas.';
    } finally {
      if (alive) busy = false;
    }
  }
  async function execute() {
    if (!selected || busy || !canOperate) return;
    actionError = preparationQuantityIssue(quantity, selected.quantity_base);
    if (actionError) {
      errorField = 'quantity';
      return;
    }
    if (!unitScan.trim()) {
      actionError = 'Escanea o escribe el código de la unidad seleccionada.';
      errorField = 'scan';
      return;
    }
    if (!partial && !locationScan.trim()) {
      actionError = 'Escanea o escribe el código de la ubicación.';
      errorField = 'location';
      return;
    }
    const action = partial ? 'split' : 'place';
    const unit = selected;
    const command = {
      quantity_base: quantity.trim(),
      unit_scan: unitScan.trim(),
      ...(action === 'place' ? { location_scan: locationScan.trim() } : {})
    };
    const fingerprint = JSON.stringify([contextKey, unit.id, action, command]);
    const key = attempts.get(fingerprint) ?? crypto.randomUUID();
    attempts.set(fingerprint, key);
    const request = sequence;
    busy = true;
    actionError = null;
    message = null;
    try {
      const result = await preparationApi.execute(unit.id, action, {
        ...command,
        idempotency_key: key
      });
      if (!alive || request !== sequence) return;
      if (action === 'split') {
        message =
          'Porción preparada. Revisa las medidas y etiquetas de la porción y del remanente antes de ubicarlos.';
        refresh(result.prepared_unit_id);
      } else {
        message = `${formatQuantity(Number(result.quantity_base))} ${unit.base_unit_symbol ?? 'unidades'} ingresaron en ${command.location_scan}.`;
        refresh();
        onplaced?.();
      }
    } catch (cause) {
      if (alive && request === sequence)
        actionError =
          cause instanceof Error
            ? cause.message
            : 'No se pudo confirmar. Puedes reintentar con los mismos datos.';
    } finally {
      if (alive) busy = false;
    }
  }
</script>

<section
  class="overflow-hidden rounded-xl border border-border bg-surface"
  aria-labelledby="preparation-heading"
>
  <div class="flex flex-wrap items-start justify-between gap-4 border-b border-border p-4 sm:p-5">
    <div>
      <div class="flex items-center gap-2">
        <span aria-hidden="true" class="text-primary">▣</span>
        <h3
          id="preparation-heading"
          tabindex="-1"
          class="font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Preparar y ubicar
        </h3>
      </div>
      <p class="mt-2 max-w-xl text-sm leading-6 text-foreground-muted">
        Revisa medidas y etiquetas. El inventario se suma al confirmar la ubicación.
      </p>
    </div>
    <Button
      size="lg"
      variant="secondary"
      disabled={loading || busy}
      onclick={() => refresh(selected?.id)}>Actualizar</Button
    >
  </div>
  {#if message}<div
      class="m-4 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-foreground"
      role="status"
    >
      <span class="mr-1 font-medium">Última operación:</span>{message}
    </div>{/if}
  <form
    class="flex flex-wrap items-end gap-2 border-b border-border p-4 sm:px-5"
    onsubmit={(event) => {
      event.preventDefault();
      if (!busy) {
        page = 1;
        query = search.trim();
        revision += 1;
      }
    }}
  >
    <label class="min-w-0 flex-1"
      ><span class="mb-1.5 block text-xs font-medium text-foreground-muted"
        >Buscar unidad o lote</span
      ><input
        class={field}
        type="search"
        bind:value={search}
        placeholder="HU-… o LOT-…"
        disabled={busy}
      /></label
    >
    <Button size="lg" variant="secondary" type="submit" disabled={busy}>Buscar</Button>
  </form>
  <div aria-busy={loading}>
    {#if loading}
      <div class="space-y-3 p-5" aria-label="Cargando pendientes">
        {#each [1, 2, 3] as n (n)}<div class="skeleton h-24 rounded-lg"></div>{/each}
      </div>
    {:else if error}
      <div class="m-5 rounded-lg border border-danger/30 bg-danger/10 p-4" role="alert">
        <p class="text-sm text-foreground">{error}</p>
        <Button size="lg" class="mt-3" variant="secondary" onclick={() => refresh()}
          >Reintentar</Button
        >
      </div>
    {:else if !units.length}
      <div class="flex flex-col items-center p-8 text-center">
        <span class="rounded-full bg-surface-muted p-3 text-foreground-muted"
          ><span aria-hidden="true" class="text-xl">✓</span></span
        >
        <h4 class="mt-4 font-medium text-foreground">
          {query ? 'Sin coincidencias' : 'No hay unidades pendientes'}
        </h4>
        <p class="mt-2 max-w-md text-sm leading-6 text-foreground-muted">
          {query
            ? 'Prueba con otro código de unidad o lote.'
            : 'Aquí aparecerán las unidades que compras haya dejado listas para preparar y colocar en bodega.'}
        </p>
        {#if query}<Button
            size="lg"
            class="mt-4"
            variant="secondary"
            onclick={() => {
              search = '';
              query = '';
              page = 1;
            }}>Limpiar búsqueda</Button
          >{/if}
      </div>
    {:else}
      <div
        class="grid divide-y divide-border lg:grid-cols-[minmax(260px,0.85fr)_minmax(0,1.4fr)] lg:divide-x lg:divide-y-0"
      >
        <div class="min-w-0 p-4 sm:p-5 {selected ? 'hidden lg:block' : ''}">
          <p
            id="preparation-pending-heading"
            tabindex="-1"
            class="mb-3 text-xs font-medium text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {total} pendiente{total === 1 ? '' : 's'} · Página {page} de {pages}
          </p>
          <div class="space-y-2">
            {#each units as unit (unit.id)}
              <button
                type="button"
                disabled={busy}
                aria-pressed={selected?.id === unit.id}
                onclick={() => choose(unit)}
                class="w-full min-w-0 rounded-lg border p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60 {selected?.id ===
                unit.id
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:bg-surface-hover'}"
              >
                <span class="flex flex-wrap items-start justify-between gap-2"
                  ><span class="text-sm font-semibold text-foreground"
                    >{unit.product_name ?? 'Producto recibido'}</span
                  ><span
                    class="whitespace-nowrap text-sm font-semibold tabular-nums text-foreground"
                    >{formatQuantity(unit.quantity_base)} {unit.base_unit_symbol ?? 'u'}</span
                  ></span
                >
                <span class="mt-2 block break-all font-mono text-[11px] text-foreground-muted"
                  >{unit.code}</span
                >
                <span
                  class="mt-3 inline-flex items-center gap-1 rounded-md bg-surface-muted px-2 py-1 text-xs text-foreground"
                  >{phaseName[unit.phase]} <span aria-hidden="true">→</span></span
                >
              </button>
            {/each}
          </div>
          <div class="mt-4 flex justify-between gap-2">
            <Button
              size="lg"
              variant="secondary"
              disabled={busy || page <= 1}
              onclick={() => (page -= 1)}>Anterior</Button
            ><Button
              size="lg"
              variant="secondary"
              disabled={busy || page >= pages}
              onclick={() => (page += 1)}>Siguiente</Button
            >
          </div>
        </div>
        <div class="min-w-0 bg-surface-muted/40 p-4 sm:p-5 {!selected ? 'hidden lg:block' : ''}">
          {#if selected}
            <Button
              size="lg"
              variant="ghost"
              class="mb-4 lg:hidden"
              onclick={() => {
                selected = null;
                actionError = null;
                void tick().then(() =>
                  document.getElementById('preparation-pending-heading')?.focus()
                );
              }}>← Volver a pendientes</Button
            >
            <div class="mb-5 border-b border-border pb-4">
              <p class="text-xs font-medium text-foreground-muted">
                {phaseName[selected.phase]}
              </p>
              <h4 class="mt-2 font-semibold text-foreground">
                {selected.product_name ?? 'Producto recibido'}
              </h4>
              <p class="mt-2 break-all font-mono text-xs text-foreground-muted">{selected.code}</p>
              <details class="mt-2 text-xs text-foreground-muted">
                <summary
                  class="cursor-pointer rounded py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >Lote de recepción</summary
                >
                <p class="mt-2 break-all font-mono">
                  {selected.receipt_lot_code ?? selected.lot_code ?? 'Sin lote informado'}
                </p>
              </details>
            </div>
            {#if !canOperate}<p class="text-sm text-foreground-muted">
                Necesitas los permisos de recepción y movimiento para preparar esta unidad.
              </p>{:else}
              <div class="space-y-4">
                <label class="block"
                  ><span class="mb-1.5 flex items-center gap-2 text-sm font-medium text-foreground"
                    ><span aria-hidden="true">⌁</span> Código de unidad o producto</span
                  ><input
                    id="preparation-unit-scan"
                    aria-invalid={errorField === 'scan' && !!actionError}
                    aria-describedby={actionError ? 'preparation-action-error' : undefined}
                    class={field}
                    bind:value={unitScan}
                    disabled={busy}
                    autocomplete="off"
                    placeholder="Escanea o escribe el código"
                    onkeydown={(e) => scannerNext(e, 'preparation-quantity')}
                  /><span class="mt-1.5 block text-xs text-foreground-muted"
                    >Código de esta unidad, completado automáticamente. Puedes editarlo o escanear
                    su etiqueta.</span
                  ></label
                >
                <label class="block"
                  ><span class="mb-1.5 block text-sm font-medium text-foreground"
                    >Cantidad a ubicar ({selected.base_unit_symbol ?? 'unidad base'})</span
                  ><input
                    id="preparation-quantity"
                    aria-invalid={errorField === 'quantity' && !!actionError}
                    aria-describedby={actionError ? 'preparation-action-error' : undefined}
                    class={field}
                    type="text"
                    inputmode="decimal"
                    bind:value={quantity}
                    disabled={busy}
                    onkeydown={(e) => scannerNext(e, nextStep)}
                  /></label
                >
                {#if partial}
                  <div class="rounded-lg border border-warning/30 bg-warning/10 p-4">
                    <h5 class="text-sm font-medium text-foreground">Preparar una porción</h5>
                    <p class="mt-2 text-sm leading-6 text-foreground-muted">
                      Quedarán {formatQuantity(selected.quantity_base - Number(quantity))}
                      {selected.base_unit_symbol ?? 'unidades'} pendientes en la unidad original. Ambas
                      partes necesitarán medidas y etiquetas actualizadas.
                    </p>
                  </div>
                  <Button
                    id="preparation-split"
                    size="lg"
                    disabled={busy}
                    onclick={() => void execute()}
                    >{busy ? 'Preparando…' : 'Preparar porción'}</Button
                  >
                {:else}
                  <ol
                    class="flex flex-wrap gap-x-4 gap-y-2 text-xs text-foreground-muted"
                    aria-label="Avance de preparación"
                  >
                    <li class:text-primary={selected.phase === 'measure'}>
                      1. Medidas {selected.measurement_status === 'verified' ? '✓' : ''}
                    </li>
                    <li class:text-primary={selected.phase === 'label'}>
                      2. Etiqueta {selected.label_confirmed ? '✓' : ''}
                    </li>
                    <li class:text-primary={selected.phase === 'place'}>3. Ubicación</li>
                  </ol>
                  {#if selected.phase === 'measure'}
                    <p class="text-sm leading-6 text-foreground-muted">
                      Registra las medidas totales de esta unidad logística completa.
                    </p>
                    <div class="grid gap-3 sm:grid-cols-2">
                      <label
                        ><span class="mb-1.5 block text-sm text-foreground">Peso bruto (kg)</span
                        ><input
                          class={field}
                          inputmode="decimal"
                          bind:value={weight}
                          id="preparation-weight"
                          aria-invalid={errorField === 'measurement' && !!actionError}
                          aria-describedby={actionError ? 'preparation-action-error' : undefined}
                          onkeydown={(e) => scannerNext(e, 'preparation-volume')}
                          disabled={busy}
                        /></label
                      ><label
                        ><span class="mb-1.5 block text-sm text-foreground">Volumen (m³)</span
                        ><input
                          class={field}
                          inputmode="decimal"
                          bind:value={volume}
                          id="preparation-volume"
                          aria-invalid={errorField === 'measurement' && !!actionError}
                          aria-describedby={actionError ? 'preparation-action-error' : undefined}
                          onkeydown={(e) => scannerNext(e, 'preparation-measure')}
                          disabled={busy}
                        /></label
                      >
                    </div>
                    <Button
                      id="preparation-measure"
                      size="lg"
                      disabled={busy}
                      onclick={() => void measure()}
                      >{busy ? 'Guardando…' : 'Confirmar medidas'}</Button
                    >
                  {:else if selected.phase === 'label'}
                    <p class="text-sm leading-6 text-foreground-muted">
                      Imprime la etiqueta y confirma que quedó pegada a esta unidad.
                    </p>
                    <Button
                      id="preparation-label"
                      size="lg"
                      disabled={busy}
                      onclick={() => (labelUnit = selected)}>Revisar y colocar etiqueta</Button
                    >
                  {:else}
                    {#if loadingLocations}<p class="text-sm text-foreground-muted" role="status">
                        Cargando ubicaciones…
                      </p>{/if}
                    {#if locationError}<div
                        class="rounded-lg border border-danger/30 p-3 text-sm"
                        role="alert"
                      >
                        <p>{locationError}</p>
                        <Button variant="secondary" onclick={() => void loadLocations(true)}
                          >Reintentar ubicaciones</Button
                        >
                      </div>{/if}
                    <LocationGridPicker
                      id="preparation-destination"
                      {locations}
                      selectedLocationId={locations.find(
                        (location) => location.code === locationScan
                      )?.id ?? ''}
                      productName={selected.product_name ?? 'Producto recibido'}
                      disabled={busy || loadingLocations}
                      hasMoreLocations={moreLocations}
                      onselect={(id) => {
                        locationScan = locations.find((location) => location.id === id)?.code ?? '';
                      }}
                    />
                    {#if moreLocations}<Button
                        variant="secondary"
                        disabled={busy || loadingLocations}
                        onclick={() => void loadLocations()}>Cargar más ubicaciones</Button
                      >{/if}
                    <label class="block"
                      ><span class="mb-1.5 block text-sm font-medium text-foreground"
                        >Código de ubicación</span
                      ><input
                        id="preparation-location"
                        aria-invalid={errorField === 'location' && !!actionError}
                        aria-describedby={actionError ? 'preparation-action-error' : undefined}
                        class={field}
                        bind:value={locationScan}
                        disabled={busy}
                        autocomplete="off"
                        placeholder="Ej. A02-R01-N01-P01"
                        onkeydown={(e) => scannerNext(e, 'preparation-confirm')}
                      /><span class="mt-1.5 block text-xs text-foreground-muted"
                        >Se completa al elegir una ubicación. También puedes escanearla. La
                        capacidad se valida al confirmar.</span
                      ></label
                    >
                    <Button
                      size="lg"
                      id="preparation-confirm"
                      type="button"
                      disabled={busy}
                      onclick={() => void execute()}
                      >{busy ? 'Ingresando…' : 'Confirmar ubicación e ingresar'}</Button
                    >
                  {/if}
                {/if}
                {#if actionError}<p
                    id="preparation-action-error"
                    class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
                    role="alert"
                  >
                    {actionError}
                  </p>{/if}
              </div>
            {/if}
          {:else}<div class="flex min-h-64 flex-col items-center justify-center text-center">
              <span aria-hidden="true" class="text-3xl text-foreground-muted">⌁</span>
              <h4 class="mt-4 font-medium text-foreground">Elige una unidad para continuar</h4>
              <p class="mt-2 max-w-xs text-sm leading-6 text-foreground-muted">
                Aquí revisarás su etiqueta y confirmarás dónde quedó colocada.
              </p>
            </div>{/if}
        </div>
      </div>
    {/if}
  </div>
</section>
<HandlingUnitLabelDialog
  unit={labelUnit}
  {contextKey}
  canVerify={canOperate}
  onclose={() => (labelUnit = null)}
  onconfirmed={(id) => {
    labelUnit = null;
    message = 'Etiqueta confirmada. La unidad está lista para ubicar.';
    refresh(id);
  }}
/>
