<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import { inventoryApi } from '../services';
  import type { HandlingUnit, PhysicalMeasuresInput, StockStatus } from '../types';

  interface Props {
    warehouseId: string;
    canVerify?: boolean;
    onverified?: () => void;
  }

  type MeasurementMethod = 'volume' | 'dimensions';
  type MeasurementField = 'weight' | 'volume' | 'length' | 'width' | 'height';

  const STOCK_STATUS_OPTIONS: { value: StockStatus; label: string }[] = [
    { value: 'available', label: 'Disponible' },
    { value: 'quarantine', label: 'Cuarentena' },
    { value: 'blocked', label: 'Bloqueada' },
    { value: 'damaged', label: 'Dañada' },
    { value: 'in_transit', label: 'En tránsito' }
  ];

  const inputClass =
    'mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let { warehouseId, canVerify = false, onverified }: Props = $props();

  let units = $state<HandlingUnit[]>([]);
  let locationCodes = $state<Map<string, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let locationWarning = $state<string | null>(null);
  let success = $state<string | null>(null);
  let search = $state('');
  let locationFilter = $state('');
  let statusFilter = $state<StockStatus | ''>('');
  let includeClosed = $state(false);
  let measuringUnitId = $state<string | null>(null);
  let savingUnitId = $state<string | null>(null);
  let measurementMethod = $state<MeasurementMethod>('volume');
  let weightKg = $state<number | undefined>(undefined);
  let volumeM3 = $state<number | undefined>(undefined);
  let lengthM = $state<number | undefined>(undefined);
  let widthM = $state<number | undefined>(undefined);
  let heightM = $state<number | undefined>(undefined);
  let measurementErrors = $state<Partial<Record<MeasurementField, string>>>({});
  let measurementError = $state<string | null>(null);
  let loadSequence = 0;

  let locationOptions = $derived.by(() =>
    [...locationCodes.entries()]
      .map(([id, code]) => ({ id, code }))
      .sort((left, right) => left.code.localeCompare(right.code, 'es-SV'))
  );

  let filteredUnits = $derived.by(() => {
    const needle = search.trim().toLocaleLowerCase('es-SV');
    return units.filter((unit) => {
      if (locationFilter && unit.location_id !== locationFilter) return false;
      if (statusFilter && unit.stock_status !== statusFilter) return false;
      if (!needle) return true;
      return [unit.code, unit.lot_code, locationCodes.get(unit.location_id)]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase('es-SV').includes(needle));
    });
  });

  let pendingMeasurementCount = $derived(units.filter((unit) => isPendingMeasurement(unit)).length);

  async function loadLocationCodes(requestedWarehouseId: string): Promise<Map<string, string>> {
    const codes = new Map<string, string>();
    let currentPage = 1;
    let totalPages = 1;

    do {
      const response = await listLocations(requestedWarehouseId, {
        page: currentPage,
        size: 100
      });
      for (const location of response.items) codes.set(location.id, location.code);
      totalPages = Math.max(1, response.meta.pages);
      currentPage += 1;
    } while (currentPage <= totalPages);

    return codes;
  }

  async function loadData(
    requestedWarehouseId: string,
    requestedIncludeClosed: boolean,
    sequence: number
  ) {
    loading = true;
    error = null;
    locationWarning = null;
    success = null;
    measuringUnitId = null;

    try {
      const [loadedUnits, locationsResult] = await Promise.all([
        inventoryApi.listHandlingUnits(requestedWarehouseId, {
          includeClosed: requestedIncludeClosed
        }),
        loadLocationCodes(requestedWarehouseId)
          .then((codes) => ({ codes, warning: null as string | null }))
          .catch(() => ({
            codes: new Map<string, string>(),
            warning:
              'Las unidades se cargaron, pero no fue posible resolver los códigos de ubicación.'
          }))
      ]);
      if (sequence !== loadSequence) return;
      units = loadedUnits;
      locationCodes = locationsResult.codes;
      locationWarning = locationsResult.warning;
    } catch (loadError) {
      if (sequence !== loadSequence) return;
      units = [];
      locationCodes = new Map();
      error =
        loadError instanceof Error
          ? loadError.message
          : 'No se pudieron cargar las unidades logísticas.';
    } finally {
      if (sequence === loadSequence) loading = false;
    }
  }

  function requestLoad() {
    const sequence = ++loadSequence;
    void loadData(warehouseId, includeClosed, sequence);
  }

  $effect(() => {
    void warehouseId;
    void includeClosed;
    requestLoad();
  });

  function isPendingMeasurement(unit: HandlingUnit): boolean {
    return (
      unit.stock_status === 'quarantine' &&
      unit.measurement_status === 'incomplete' &&
      unit.closed_at == null
    );
  }

  function canMeasure(unit: HandlingUnit): boolean {
    return canVerify && isPendingMeasurement(unit);
  }

  function statusLabel(status: StockStatus): string {
    return STOCK_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
  }

  function statusVariant(
    status: StockStatus
  ): 'success' | 'warning' | 'danger' | 'neutral' | 'primary' {
    if (status === 'available') return 'success';
    if (status === 'quarantine') return 'warning';
    if (status === 'blocked' || status === 'damaged') return 'danger';
    if (status === 'in_transit') return 'primary';
    return 'neutral';
  }

  function measurementLabel(unit: HandlingUnit): string {
    if (unit.measurement_status === 'verified') return 'Medición verificada';
    if (unit.measurement_status === 'complete') return 'Medición completa';
    return 'Medición pendiente';
  }

  function number(value: number, maximumFractionDigits = 3): string {
    return value.toLocaleString('es-SV', { maximumFractionDigits });
  }

  function physical(value: number | null, unit: string): string {
    return value == null ? 'Sin medir' : `${number(value)} ${unit}`;
  }

  function expiry(value: string | null): string {
    if (!value) return 'Sin vencimiento';
    const parsed = new Date(`${value}T00:00:00`);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleDateString('es-SV', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        });
  }

  function locationCode(unit: HandlingUnit): string {
    return locationCodes.get(unit.location_id) ?? 'Código no disponible';
  }

  function resetMeasurementForm() {
    measuringUnitId = null;
    savingUnitId = null;
    measurementMethod = 'volume';
    weightKg = undefined;
    volumeM3 = undefined;
    lengthM = undefined;
    widthM = undefined;
    heightM = undefined;
    measurementErrors = {};
    measurementError = null;
  }

  function startMeasurement(unit: HandlingUnit) {
    success = null;
    measurementErrors = {};
    measurementError = null;
    measuringUnitId = unit.id;
    weightKg = unit.actual_gross_weight_kg ?? undefined;
    volumeM3 = unit.actual_volume_m3 ?? undefined;
    lengthM = unit.actual_length_m ?? undefined;
    widthM = unit.actual_width_m ?? undefined;
    heightM = unit.actual_height_m ?? undefined;
    measurementMethod =
      unit.actual_length_m != null && unit.actual_width_m != null && unit.actual_height_m != null
        ? 'dimensions'
        : 'volume';
  }

  function positive(value: number | undefined): number | null {
    return value != null && Number.isFinite(value) && value > 0 ? value : null;
  }

  function validateMeasurement(): PhysicalMeasuresInput | null {
    const errors: Partial<Record<MeasurementField, string>> = {};
    const weight = positive(weightKg);
    if (weight == null) errors.weight = 'Ingrese un peso mayor que cero.';

    let measures: PhysicalMeasuresInput;
    if (measurementMethod === 'volume') {
      const volume = positive(volumeM3);
      if (volume == null) errors.volume = 'Ingrese un volumen mayor que cero.';
      measures = {
        gross_weight_kg: weight,
        volume_m3: volume,
        length_m: null,
        width_m: null,
        height_m: null
      };
    } else {
      const length = positive(lengthM);
      const width = positive(widthM);
      const height = positive(heightM);
      if (length == null) errors.length = 'Ingrese un largo mayor que cero.';
      if (width == null) errors.width = 'Ingrese un ancho mayor que cero.';
      if (height == null) errors.height = 'Ingrese un alto mayor que cero.';
      measures = {
        gross_weight_kg: weight,
        volume_m3: null,
        length_m: length,
        width_m: width,
        height_m: height
      };
    }

    measurementErrors = errors;
    return Object.keys(errors).length === 0 ? measures : null;
  }

  async function verifyMeasurement(event: SubmitEvent, unit: HandlingUnit) {
    event.preventDefault();
    if (!canMeasure(unit) || savingUnitId) return;
    measurementError = null;
    success = null;
    const measures = validateMeasurement();
    if (!measures) return;

    savingUnitId = unit.id;
    try {
      const verified = await inventoryApi.verifyHandlingUnitMeasurements(
        unit.id,
        measures,
        'manual'
      );
      units = units.map((candidate) => (candidate.id === verified.id ? verified : candidate));
      resetMeasurementForm();
      success = `Medidas de ${verified.code} verificadas correctamente.`;
      onverified?.();
    } catch (verifyError) {
      measurementError =
        verifyError instanceof Error
          ? verifyError.message
          : 'No se pudieron verificar las medidas.';
    } finally {
      savingUnitId = null;
    }
  }
</script>

<Card class="overflow-hidden">
  <div
    class="flex flex-col gap-4 border-b border-border px-5 py-4 lg:flex-row lg:items-start lg:justify-between"
  >
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">Unidades logísticas</h3>
        {#if !loading}<Badge variant="neutral">{units.length} registradas</Badge>{/if}
        {#if !loading && pendingMeasurementCount > 0}
          <Badge variant="warning">{pendingMeasurementCount} por medir</Badge>
        {/if}
      </div>
      <p class="mt-1 max-w-3xl text-xs leading-5 text-foreground-muted">
        Existencias físicas identificables por caja, saco, paquete, contenedor o producto suelto.
        Los valores desconocidos nunca se interpretan como cero.
      </p>
    </div>
    <Button variant="secondary" size="sm" onclick={requestLoad} disabled={loading}>
      {loading ? 'Actualizando…' : 'Actualizar'}
    </Button>
  </div>

  <div class="space-y-4 p-5">
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_220px_180px_auto]">
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-search">
        Buscar por código, lote o ubicación
        <input
          id="handling-unit-search"
          class={inputClass}
          type="search"
          bind:value={search}
          placeholder="Ej. HU-000123 o LOTE-A"
        />
      </label>
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-location">
        Ubicación
        <select
          id="handling-unit-location"
          class={inputClass}
          value={locationFilter}
          onchange={(event) => {
            locationFilter = (event.currentTarget as HTMLSelectElement).value;
          }}
        >
          <option value="">Todas las ubicaciones</option>
          {#each locationOptions as location (location.id)}
            <option value={location.id}>{location.code}</option>
          {/each}
        </select>
      </label>
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-status">
        Estado de existencia
        <select
          id="handling-unit-status"
          class={inputClass}
          value={statusFilter}
          onchange={(event) => {
            statusFilter = (event.currentTarget as HTMLSelectElement).value as StockStatus | '';
          }}
        >
          <option value="">Todos los estados</option>
          {#each STOCK_STATUS_OPTIONS as option (option.value)}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>
      <label
        class="mt-5 flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-xs text-foreground"
      >
        <input type="checkbox" bind:checked={includeClosed} /> Mostrar cerradas
      </label>
    </div>

    {#if success}
      <div
        class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
        role="status"
      >
        {success}
      </div>
    {/if}
    {#if locationWarning}
      <div
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning"
        role="status"
      >
        {locationWarning}
      </div>
    {/if}

    {#if loading}
      <div class="space-y-2" role="status" aria-label="Cargando unidades logísticas">
        {#each Array(4) as _}
          <div class="skeleton h-12 rounded-lg"></div>
        {/each}
      </div>
    {:else if error}
      <div class="rounded-xl border border-danger/30 bg-danger/10 p-5" role="alert">
        <p class="text-sm font-semibold text-danger">No se pudo cargar el inventario físico</p>
        <p class="mt-1 text-xs text-danger/90">{error}</p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={requestLoad}>Reintentar</Button>
        </div>
      </div>
    {:else if units.length === 0}
      <div
        class="rounded-xl border border-dashed border-border px-6 py-10 text-center"
        role="status"
      >
        <div
          class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path
              d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
            />
            <path d="m3.3 7 8.7 5 8.7-5M12 22V12" />
          </svg>
        </div>
        <p class="mt-3 text-sm font-semibold text-foreground">Sin unidades logísticas activas</p>
        <p class="mt-1 text-xs text-foreground-muted">
          Se mostrarán aquí cuando se confirme la recepción de mercancía identificable.
        </p>
      </div>
    {:else if filteredUnits.length === 0}
      <div
        class="rounded-xl border border-dashed border-border px-6 py-8 text-center"
        role="status"
      >
        <p class="text-sm font-semibold text-foreground">Sin coincidencias</p>
        <p class="mt-1 text-xs text-foreground-muted">Ajuste la búsqueda o los filtros.</p>
      </div>
    {:else}
      <div class="overflow-x-auto rounded-xl border border-border">
        <table class="w-full min-w-[1020px] text-xs">
          <caption class="sr-only">
            Unidades logísticas, ubicación, estado, trazabilidad y ocupación física
          </caption>
          <thead class="border-b border-border bg-surface-muted/40 text-left text-foreground-muted">
            <tr>
              <th scope="col" class="px-3 py-2.5">Unidad logística</th>
              <th scope="col" class="px-3 py-2.5">Ubicación</th>
              <th scope="col" class="px-3 py-2.5">Estado</th>
              <th scope="col" class="px-3 py-2.5">Lote y vencimiento</th>
              <th scope="col" class="px-3 py-2.5 text-right">Cantidad</th>
              <th scope="col" class="px-3 py-2.5 text-right">Peso ocupado</th>
              <th scope="col" class="px-3 py-2.5 text-right">Volumen ocupado</th>
              {#if canVerify}<th scope="col" class="px-3 py-2.5 text-right">Acción</th>{/if}
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each filteredUnits as unit (unit.id)}
              <tr class="align-top hover:bg-surface-muted/25">
                <td class="px-3 py-3">
                  <p class="font-mono font-semibold text-foreground">{unit.code}</p>
                  <p class="mt-1 text-[10px] text-foreground-muted">
                    {unit.closed_at ? 'Cerrada' : measurementLabel(unit)}
                  </p>
                </td>
                <td class="px-3 py-3">
                  <p class="font-mono text-foreground">{locationCode(unit)}</p>
                </td>
                <td class="px-3 py-3">
                  <Badge variant={statusVariant(unit.stock_status)}>
                    {statusLabel(unit.stock_status)}
                  </Badge>
                </td>
                <td class="px-3 py-3">
                  <p class="font-mono text-foreground">{unit.lot_code ?? 'Sin lote'}</p>
                  <p class="mt-1 text-[10px] text-foreground-muted">{expiry(unit.expiry_date)}</p>
                </td>
                <td class="px-3 py-3 text-right font-mono tabular-nums text-foreground">
                  {number(unit.quantity_base, 6)}
                  <span class="block text-[10px] text-foreground-muted">unidad base</span>
                </td>
                <td class="px-3 py-3 text-right font-mono tabular-nums text-foreground">
                  {physical(unit.occupied_weight_kg, 'kg')}
                </td>
                <td class="px-3 py-3 text-right font-mono tabular-nums text-foreground">
                  {physical(unit.occupied_volume_m3, 'm³')}
                </td>
                {#if canVerify}
                  <td class="px-3 py-3 text-right">
                    {#if canMeasure(unit)}
                      <button
                        type="button"
                        class="inline-flex h-8 items-center justify-center rounded-lg border border-border bg-surface-elevated px-3 text-xs font-medium text-foreground shadow-soft transition-all hover:bg-surface-hover disabled:pointer-events-none disabled:opacity-40"
                        disabled={savingUnitId != null}
                        onclick={() =>
                          measuringUnitId === unit.id
                            ? resetMeasurementForm()
                            : startMeasurement(unit)}
                        aria-expanded={measuringUnitId === unit.id}
                        aria-controls={`measurement-${unit.id}`}
                      >
                        {measuringUnitId === unit.id ? 'Cerrar' : 'Verificar medidas'}
                      </button>
                    {/if}
                  </td>
                {/if}
              </tr>
              {#if measuringUnitId === unit.id && canMeasure(unit)}
                <tr id={`measurement-${unit.id}`}>
                  <td colspan={canVerify ? 8 : 7} class="bg-warning/5 px-4 py-4">
                    <form
                      class="rounded-xl border border-warning/30 bg-surface p-4"
                      aria-label={`Verificar medidas de ${unit.code}`}
                      onsubmit={(event) => void verifyMeasurement(event, unit)}
                    >
                      <div
                        class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div>
                          <h4 class="text-sm font-semibold text-foreground">
                            Verificación física · {unit.code}
                          </h4>
                          <p class="mt-1 text-xs text-foreground-muted">
                            Registre el peso bruto y el volumen total de la unidad logística
                            completa, ya sea directamente o mediante sus tres dimensiones
                            exteriores.
                          </p>
                        </div>
                        <Badge variant="warning">Cuarentena</Badge>
                      </div>

                      {#if measurementError}
                        <div
                          class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
                          role="alert"
                        >
                          {measurementError}
                        </div>
                      {/if}

                      <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`measurement-weight-${unit.id}`}
                        >
                          Peso bruto total de la unidad logística (kg) *
                          <input
                            id={`measurement-weight-${unit.id}`}
                            class={inputClass}
                            type="number"
                            min="0.000001"
                            step="any"
                            bind:value={weightKg}
                            required
                            aria-invalid={measurementErrors.weight ? 'true' : undefined}
                            aria-describedby={measurementErrors.weight
                              ? `measurement-weight-${unit.id}-error`
                              : undefined}
                          />
                          {#if measurementErrors.weight}
                            <span
                              id={`measurement-weight-${unit.id}-error`}
                              class="mt-1 block text-[11px] text-danger"
                              >{measurementErrors.weight}</span
                            >
                          {/if}
                        </label>

                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`measurement-method-${unit.id}`}
                        >
                          Método de volumen *
                          <select
                            id={`measurement-method-${unit.id}`}
                            class={inputClass}
                            value={measurementMethod}
                            onchange={(event) => {
                              measurementMethod = (event.currentTarget as HTMLSelectElement)
                                .value as MeasurementMethod;
                              measurementErrors = {};
                              measurementError = null;
                            }}
                          >
                            <option value="volume">Volumen directo</option>
                            <option value="dimensions">Calcular por dimensiones</option>
                          </select>
                        </label>

                        {#if measurementMethod === 'volume'}
                          <label
                            class="text-xs font-medium text-foreground-muted md:col-span-2 xl:col-span-1"
                            for={`measurement-volume-${unit.id}`}
                          >
                            Volumen (m³) *
                            <input
                              id={`measurement-volume-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={volumeM3}
                              required
                              aria-invalid={measurementErrors.volume ? 'true' : undefined}
                              aria-describedby={measurementErrors.volume
                                ? `measurement-volume-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.volume}
                              <span
                                id={`measurement-volume-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.volume}</span
                              >
                            {/if}
                          </label>
                        {:else}
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-length-${unit.id}`}
                          >
                            Largo (m) *
                            <input
                              id={`measurement-length-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={lengthM}
                              required
                              aria-invalid={measurementErrors.length ? 'true' : undefined}
                              aria-describedby={measurementErrors.length
                                ? `measurement-length-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.length}
                              <span
                                id={`measurement-length-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.length}</span
                              >
                            {/if}
                          </label>
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-width-${unit.id}`}
                          >
                            Ancho (m) *
                            <input
                              id={`measurement-width-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={widthM}
                              required
                              aria-invalid={measurementErrors.width ? 'true' : undefined}
                              aria-describedby={measurementErrors.width
                                ? `measurement-width-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.width}
                              <span
                                id={`measurement-width-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.width}</span
                              >
                            {/if}
                          </label>
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-height-${unit.id}`}
                          >
                            Alto (m) *
                            <input
                              id={`measurement-height-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={heightM}
                              required
                              aria-invalid={measurementErrors.height ? 'true' : undefined}
                              aria-describedby={measurementErrors.height
                                ? `measurement-height-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.height}
                              <span
                                id={`measurement-height-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.height}</span
                              >
                            {/if}
                          </label>
                        {/if}
                      </div>

                      <div class="mt-4 flex flex-wrap justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={savingUnitId === unit.id}
                          onclick={resetMeasurementForm}>Cancelar</Button
                        >
                        <Button type="submit" size="sm" disabled={savingUnitId === unit.id}>
                          {savingUnitId === unit.id ? 'Verificando…' : 'Confirmar medición'}
                        </Button>
                      </div>
                    </form>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</Card>
