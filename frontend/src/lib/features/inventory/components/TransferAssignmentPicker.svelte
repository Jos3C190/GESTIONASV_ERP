<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import { HttpError } from '$lib/api/client';
  import {
    inventoryTransfersApi,
    type AssignmentOptions,
    type DispatchIssue,
    type TransportJudgement
  } from '$lib/features/inventory/transfer-documents';
  import {
    COMPLIANCE_LABEL,
    FITNESS_LABEL,
    transferErrorMessage
  } from '$lib/features/inventory/transfer-operations';

  /**
   * Vehicle and driver of a transfer, with a live verdict. In planning mode it judges a draft
   * (what only matters at departure is a warning); in dispatch mode it judges the departure.
   */
  interface Props {
    mode: 'planning' | 'dispatch';
    /** Dispatch: the transfer being dispatched. Planning: the saved transfer being edited, if any. */
    transferId?: string | null;
    /** Planning only: the origin warehouse whose branch supplies vehicles and drivers. */
    originWarehouseId?: string;
    /** Planning only: the lines of the draft; they give the weight of the load. */
    draftLines?: Array<{ handling_unit_id: string; quantity_base: string }>;
    vehicleId: string;
    driverId: string;
    /** Planning: the transport is needed to send the transfer for approval. */
    required?: boolean;
    disabled?: boolean;
    /** Keeps the element ids unique when two pickers are on the page. */
    idPrefix?: string;
    /** Names for a saved choice the list no longer offers (e.g. a vehicle that went inactive). */
    vehicleFallbackLabel?: string;
    driverFallbackLabel?: string;
    /** The driver saved in the transfer; changing vehicle moves a driver that was only that one. */
    savedDriverId?: string;
    judgement?: TransportJudgement | null;
    checking?: boolean;
    options?: AssignmentOptions | null;
    /** Waits for the person to stop typing before judging; planning only by default. */
    debounceMs?: number;
  }

  let {
    mode,
    transferId = null,
    originWarehouseId = '',
    draftLines = [],
    vehicleId = $bindable(''),
    driverId = $bindable(''),
    required = false,
    disabled = false,
    idPrefix = 'transport',
    vehicleFallbackLabel = '',
    driverFallbackLabel = '',
    savedDriverId = '',
    judgement = $bindable(null),
    checking = $bindable(false),
    options = $bindable(null),
    debounceMs
  }: Props = $props();

  let loadError = $state<string | null>(null);
  let checkError = $state<string | null>(null);
  let optionsSequence = 0;
  let checkSequence = 0;

  const vehicle = $derived(
    options?.vehicles.find((item) => item.inventory_vehicle_id === vehicleId) ?? null
  );
  const availableVehicles = $derived(options?.vehicles.filter((item) => item.available) ?? []);
  const unavailableVehicles = $derived(options?.vehicles.filter((item) => !item.available) ?? []);
  // Every driver is a real choice; nothing is left to a server-side default.
  const driverChoices = $derived(options?.drivers ?? []);
  const blockingIssues = $derived<DispatchIssue[]>(
    judgement
      ? [...judgement.vehicleIssues, ...judgement.driverIssues].filter(
          (issue) => issue.severity === 'blocking'
        )
      : []
  );
  const warningIssues = $derived<DispatchIssue[]>(
    judgement
      ? [...judgement.vehicleIssues, ...judgement.driverIssues].filter(
          (issue) => issue.severity === 'warning'
        )
      : []
  );
  const chipVariant = $derived(
    judgement?.fitness === 'blocked'
      ? 'danger'
      : judgement?.fitness === 'warning'
        ? 'warning'
        : 'success'
  );
  const helpText = $derived(
    mode === 'planning'
      ? required
        ? 'Obligatorio para enviar a aprobación'
        : 'Opcional; se confirma al despachar'
      : ''
  );
  const vehicleFieldId = $derived(`${idPrefix}-vehicle`);
  const driverFieldId = $derived(`${idPrefix}-driver`);

  async function loadOptions(
    currentMode: 'planning' | 'dispatch',
    id: string | null,
    origin: string
  ) {
    const sequence = ++optionsSequence;
    loadError = null;
    options = null;
    if (currentMode === 'dispatch' ? !id : !origin) return;
    try {
      const result =
        currentMode === 'dispatch'
          ? await inventoryTransfersApi.dispatchOptions(id as string)
          : await inventoryTransfersApi.assignmentOptions(origin, id);
      if (sequence === optionsSequence) options = result;
    } catch (cause) {
      if (sequence !== optionsSequence) return;
      loadError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudieron consultar vehículos y conductores.';
    }
  }

  $effect(() => {
    void loadOptions(mode, transferId, originWarehouseId);
  });

  async function runCheck(
    sequence: number,
    currentMode: 'planning' | 'dispatch',
    id: string | null,
    origin: string,
    vehicleChoice: string,
    driverChoice: string,
    lines: Array<{ handling_unit_id: string; quantity_base: string }>
  ) {
    try {
      let next: TransportJudgement;
      if (currentMode === 'dispatch') {
        const result = await inventoryTransfersApi.dispatchCheck(
          id as string,
          vehicleChoice,
          driverChoice || null
        );
        const hasIssues = result.vehicle_issues.length + result.driver_issues.length > 0;
        next = {
          mode: currentMode,
          fitness: result.blocked ? 'blocked' : hasIssues ? 'warning' : 'ok',
          vehicleIssues: result.vehicle_issues,
          driverIssues: result.driver_issues,
          blocked: result.blocked,
          hardBlocked: result.hard_blocked,
          canOverride: result.can_override,
          conflicts: [],
          loadKg: null,
          missingWeight: 0,
          driverId: result.driver_id
        };
      } else {
        const result = await inventoryTransfersApi.assignmentCheck({
          origin_warehouse_id: origin,
          vehicle_id: vehicleChoice,
          driver_id: driverChoice || null,
          transfer_id: id,
          lines
        });
        const hasIssues = result.vehicle_issues.length + result.driver_issues.length > 0;
        next = {
          mode: currentMode,
          fitness: result.planning_blocked
            ? 'blocked'
            : hasIssues || result.warnings > 0 || result.conflicts.length > 0
              ? 'warning'
              : 'ok',
          vehicleIssues: result.vehicle_issues,
          driverIssues: result.driver_issues,
          blocked: result.planning_blocked,
          hardBlocked: result.planning_blocked,
          canOverride: false,
          conflicts: result.conflicts,
          loadKg: result.load_kg,
          missingWeight: result.load_missing_weight,
          driverId: result.driver_id
        };
      }
      // A newer choice made this answer stale.
      if (sequence === checkSequence) judgement = next;
    } catch (cause) {
      if (sequence === checkSequence) {
        judgement = null;
        checkError =
          cause instanceof HttpError
            ? transferErrorMessage(cause, cause.message)
            : 'No se pudo validar la selección.';
      }
    } finally {
      if (sequence === checkSequence) checking = false;
    }
  }

  $effect(() => {
    const currentMode = mode;
    const id = transferId;
    const origin = originWarehouseId;
    const vehicle = vehicleId;
    const driver = driverId;
    const lines = currentMode === 'planning' ? $state.snapshot(draftLines) : [];
    const wait = debounceMs ?? (currentMode === 'planning' ? 350 : 0);
    const sequence = ++checkSequence;
    checkError = null;
    if (!vehicle || (currentMode === 'planning' && !origin)) {
      judgement = null;
      checking = false;
      return;
    }
    checking = true;
    const timer = setTimeout(
      () => void runCheck(sequence, currentMode, id, origin, vehicle, driver, lines),
      wait
    );
    return () => clearTimeout(timer);
  });

  function chooseVehicle(value: string) {
    const previous = vehicle;
    vehicleId = value;
    const next = options?.vehicles.find((item) => item.inventory_vehicle_id === value);
    // The driver follows the vehicle when nobody chose one, or the current one was only the
    // previous vehicle's (or the saved) driver; a driver picked on purpose is kept.
    const followsVehicle =
      !driverId ||
      (previous?.driver_id != null && driverId === previous.driver_id) ||
      (savedDriverId !== '' && driverId === savedDriverId);
    if (followsVehicle && next?.driver_id) driverId = next.driver_id;
  }

  function vehicleLabel(item: AssignmentOptions['vehicles'][number]): string {
    const status = item.available
      ? COMPLIANCE_LABEL[item.compliance_state]
      : (item.unavailable_reason ?? 'No disponible');
    return `${item.code} · ${item.plate ?? 'Sin placa'} · ${item.brand} ${item.model} · ${status}`;
  }
</script>

<div class="space-y-3">
  <div class="grid gap-3 sm:grid-cols-2">
    <div class="space-y-1">
      <label for={vehicleFieldId} class="block text-sm font-medium text-foreground"
        >Vehículo de {options?.origin_branch_name || 'la sucursal de origen'}</label
      >
      <select
        id={vehicleFieldId}
        class="field-control"
        value={vehicleId}
        onchange={(event) => chooseVehicle(event.currentTarget.value)}
        disabled={disabled || !options}
        aria-describedby={helpText ? `${idPrefix}-help` : undefined}
      >
        <option value="">Selecciona vehículo</option>
        {#if vehicleId && !vehicle && vehicleFallbackLabel}
          <option value={vehicleId}>{vehicleFallbackLabel}</option>
        {/if}
        {#if unavailableVehicles.length}
          <optgroup label="Disponibles">
            {#each availableVehicles as item (item.inventory_vehicle_id)}
              <option value={item.inventory_vehicle_id}>{vehicleLabel(item)}</option>
            {/each}
          </optgroup>
          <optgroup label="No disponibles">
            {#each unavailableVehicles as item (item.inventory_vehicle_id)}
              <!-- The saved choice stays selectable so the verdict can explain what changed. -->
              <option
                value={item.inventory_vehicle_id}
                disabled={item.inventory_vehicle_id !== vehicleId}>{vehicleLabel(item)}</option
              >
            {/each}
          </optgroup>
        {:else}
          {#each availableVehicles as item (item.inventory_vehicle_id)}
            <option value={item.inventory_vehicle_id}>{vehicleLabel(item)}</option>
          {/each}
        {/if}
      </select>
      {#if vehicle?.note}<p class="text-xs text-foreground-muted">{vehicle.note}</p>{/if}
    </div>
    <div class="space-y-1">
      <label for={driverFieldId} class="block text-sm font-medium text-foreground">Conductor</label>
      <select
        id={driverFieldId}
        class="field-control"
        value={driverId}
        onchange={(event) => (driverId = event.currentTarget.value)}
        disabled={disabled || !options}
        aria-describedby={helpText ? `${idPrefix}-help` : undefined}
      >
        <option value="">Selecciona conductor</option>
        {#if driverId && !options?.drivers.some((item) => item.id === driverId) && driverFallbackLabel}
          <option value={driverId}>{driverFallbackLabel}</option>
        {/if}
        {#each driverChoices as item (item.id)}
          <option value={item.id}
            >{item.name} · {COMPLIANCE_LABEL[item.compliance_state]}{item.current_vehicle_code
              ? ` · conduce ${item.current_vehicle_code}`
              : ''}</option
          >
        {/each}
      </select>
    </div>
  </div>
  {#if helpText}<p id="{idPrefix}-help" class="text-xs text-foreground-muted">{helpText}</p>{/if}

  {#if options && options.vehicles.length === 0}
    <p class="text-sm text-foreground-muted">
      La sucursal de origen no tiene vehículos de traslado. Regístralos en <a
        class="font-medium text-primary underline underline-offset-2"
        href="/fleet">Flota</a
      >.
    </p>
  {/if}

  <div class="space-y-2" aria-live="polite">
    {#if checking}
      <p class="text-xs text-foreground-muted" role="status">Validando vehículo y conductor…</p>
    {:else if judgement}
      <div class="flex flex-wrap items-center gap-2">
        <Badge variant={chipVariant}>{FITNESS_LABEL[judgement.fitness]}</Badge>
        {#if judgement.loadKg != null}
          <span class="text-xs text-foreground-muted">
            Carga estimada: {new Intl.NumberFormat('es-SV', { maximumFractionDigits: 1 }).format(
              Number(judgement.loadKg)
            )} kg{judgement.missingWeight > 0
              ? ` · ${judgement.missingWeight} ${judgement.missingWeight === 1 ? 'producto' : 'productos'} sin peso registrado`
              : ''}
          </span>
        {/if}
      </div>
      {#if blockingIssues.length}
        <ul
          class="space-y-1 rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
          aria-label={mode === 'dispatch'
            ? 'Impedimentos para despachar'
            : 'Impedimentos para planificar'}
        >
          {#each blockingIssues as issue, index (index)}
            <li>
              {issue.message}{mode === 'dispatch' && !issue.overridable
                ? ' (no admite excepción)'
                : ''}
            </li>
          {/each}
        </ul>
      {:else if judgement.fitness === 'ok'}
        <p class="text-sm font-medium text-success">
          {mode === 'dispatch'
            ? 'Vehículo y conductor aptos para el despacho.'
            : 'Vehículo y conductor aptos para planificar.'}
        </p>
      {/if}
      {#if warningIssues.length}
        <ul
          class="space-y-1 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground"
          aria-label="Advertencias"
        >
          {#each warningIssues as issue, index (index)}<li>{issue.message}</li>{/each}
        </ul>
      {/if}
      {#if judgement.conflicts.length}
        <ul
          class="space-y-1 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground"
          aria-label="Otros traslados con este transporte"
        >
          {#each judgement.conflicts as conflict (conflict.transfer_id)}
            <li>{conflict.message}</li>
          {/each}
        </ul>
      {/if}
    {/if}
    {#if checkError}<p class="text-sm text-danger" role="alert">{checkError}</p>{/if}
    {#if loadError}<p class="text-sm text-danger" role="alert">{loadError}</p>{/if}
  </div>
</div>
