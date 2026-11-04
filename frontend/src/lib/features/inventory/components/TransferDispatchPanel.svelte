<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import {
    inventoryTransfersApi,
    type DispatchCheck,
    type DispatchIssue,
    type DispatchOptions,
    type DispatchSelection,
    type FitnessState,
    type InventoryTransfer
  } from '$lib/features/inventory/transfer-documents';

  interface Props {
    transfer: InventoryTransfer;
    disabled: boolean;
    selection: DispatchSelection;
  }

  let { transfer, disabled, selection = $bindable() }: Props = $props();

  const STATE_LABEL: Record<FitnessState, string> = {
    ok: 'Apto',
    warning: 'Con advertencias',
    blocked: 'No apto'
  };
  const MIN_REASON = 5;

  let options = $state<DispatchOptions | null>(null);
  let check = $state<DispatchCheck | null>(null);
  let vehicleId = $state('');
  let driverId = $state('');
  let overrideReason = $state('');
  let loadError = $state<string | null>(null);
  let checking = $state(false);
  let checkSequence = 0;

  const vehicle = $derived(
    options?.vehicles.find((item) => item.inventory_vehicle_id === vehicleId) ?? null
  );
  const issues = $derived<DispatchIssue[]>(
    check ? [...check.vehicle_issues, ...check.driver_issues] : []
  );
  const blocking = $derived(issues.filter((issue) => issue.severity === 'blocking'));
  const warnings = $derived(issues.filter((issue) => issue.severity === 'warning'));
  const needsOverride = $derived(
    Boolean(check?.blocked && !check.hard_blocked && check.can_override)
  );
  const ready = $derived(
    Boolean(
      vehicleId &&
      check &&
      !checking &&
      !check.hard_blocked &&
      (!check.blocked || (check.can_override && overrideReason.trim().length >= MIN_REASON))
    )
  );

  $effect(() => {
    const driverName =
      options?.drivers.find((item) => item.id === (driverId || check?.driver_id))?.name ?? '';
    selection = {
      vehicleId,
      driverId: driverId || check?.driver_id || '',
      overrideReason: needsOverride ? overrideReason.trim() : '',
      ready,
      label: vehicle
        ? `${vehicle.code} · ${vehicle.plate ?? 'Sin placa'}${driverName ? ` · ${driverName}` : ''}`
        : ''
    };
  });

  async function loadOptions(transferId: string, presetVehicle: string | null) {
    loadError = null;
    options = null;
    check = null;
    try {
      const result = await inventoryTransfersApi.dispatchOptions(transferId);
      if (transfer.id !== transferId) return;
      options = result;
      const preset = result.vehicles.find(
        (item) => item.inventory_vehicle_id === presetVehicle && item.available
      );
      vehicleId =
        preset?.inventory_vehicle_id ??
        result.vehicles.find((item) => item.available)?.inventory_vehicle_id ??
        '';
      driverId = '';
    } catch (cause) {
      loadError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudieron consultar vehículos y conductores.';
    }
  }

  $effect(() => {
    void loadOptions(transfer.id, transfer.vehicle?.id ?? null);
  });

  async function runCheck(transferId: string, vehicle: string, driver: string) {
    const sequence = ++checkSequence;
    if (!vehicle) {
      check = null;
      return;
    }
    checking = true;
    try {
      const result = await inventoryTransfersApi.dispatchCheck(transferId, vehicle, driver || null);
      if (sequence === checkSequence) check = result;
    } catch (cause) {
      if (sequence === checkSequence) {
        check = null;
        loadError = cause instanceof HttpError ? cause.message : 'No se pudo validar la selección.';
      }
    } finally {
      if (sequence === checkSequence) checking = false;
    }
  }

  $effect(() => {
    if (!options) return;
    void runCheck(transfer.id, vehicleId, driverId);
  });

  function chooseVehicle(value: string) {
    vehicleId = value;
    driverId = '';
    overrideReason = '';
  }
</script>

<div class="space-y-3">
  <div class="grid gap-3 sm:grid-cols-2">
    <label class="space-y-1 text-sm font-medium text-foreground"
      >Vehículo de {options?.origin_branch_name || 'la sucursal de origen'}
      <select
        class="field-control"
        value={vehicleId}
        onchange={(event) => chooseVehicle(event.currentTarget.value)}
        disabled={disabled || !options}
      >
        <option value="">Seleccione vehículo</option>
        {#each options?.vehicles ?? [] as item (item.inventory_vehicle_id)}
          <option value={item.inventory_vehicle_id} disabled={!item.available}
            >{item.code} · {item.plate ?? 'Sin placa'} · {item.brand}
            {item.model}{item.available
              ? ` · ${STATE_LABEL[item.compliance_state]}`
              : ` · ${item.unavailable_reason}`}</option
          >
        {/each}
      </select>
    </label>
    <label class="space-y-1 text-sm font-medium text-foreground"
      >Conductor
      <select class="field-control" bind:value={driverId} disabled={disabled || !vehicleId}>
        <option value=""
          >{vehicle?.driver_name
            ? `Asignado: ${vehicle.driver_name}`
            : 'Seleccione conductor'}</option
        >
        {#each options?.drivers ?? [] as item (item.id)}
          {#if item.id !== vehicle?.driver_id}
            <option value={item.id}
              >{item.name} · {STATE_LABEL[item.compliance_state]}{item.current_vehicle_code
                ? ` · conduce ${item.current_vehicle_code}`
                : ''}</option
            >
          {/if}
        {/each}
      </select>
    </label>
  </div>

  {#if options && options.vehicles.length === 0}
    <p class="text-sm text-foreground-muted">
      La sucursal de origen no tiene vehículos de traslado. Regístralos en <a
        class="font-medium text-primary"
        href="/fleet">Flota</a
      >.
    </p>
  {/if}

  {#if checking}
    <p class="text-xs text-foreground-muted" role="status">Validando vehículo y conductor…</p>
  {:else if check}
    {#if blocking.length}
      <ul
        class="space-y-1 rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
        aria-label="Impedimentos para despachar"
      >
        {#each blocking as issue, index (index)}
          <li>
            {issue.message}{issue.overridable ? '' : ' (no admite excepción)'}
          </li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm font-medium text-success">Vehículo y conductor aptos para el despacho.</p>
    {/if}
    {#if warnings.length}
      <ul
        class="space-y-1 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground"
      >
        {#each warnings as issue, index (index)}<li>{issue.message}</li>{/each}
      </ul>
    {/if}
    {#if needsOverride}
      <label class="block space-y-1 text-sm font-medium text-foreground"
        >Motivo de la excepción (queda registrado en la auditoría)
        <textarea
          class="field-control min-h-[72px]"
          maxlength="500"
          bind:value={overrideReason}
          {disabled}
        ></textarea>
      </label>
    {:else if check.blocked && !check.hard_blocked}
      <p class="text-xs text-foreground-muted">
        Solo un usuario autorizado para excepciones puede despachar con estos impedimentos.
      </p>
    {/if}
  {/if}

  {#if loadError}<p class="text-sm text-danger" role="alert">{loadError}</p>{/if}
</div>
