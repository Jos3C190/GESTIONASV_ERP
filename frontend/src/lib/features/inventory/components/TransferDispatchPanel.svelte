<script lang="ts">
  import { untrack } from 'svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import {
    inventoryTransfersApi,
    type DispatchCheck,
    type AssignmentOptions,
    type DispatchSelection,
    type InventoryTransfer,
    type SubstitutionCode,
    type TransportJudgement
  } from '$lib/features/inventory/transfer-documents';
  import { SUBSTITUTION_CODE_OPTIONS } from '$lib/features/inventory/transfer-operations';
  import TransferAssignmentPicker from './TransferAssignmentPicker.svelte';

  interface Props {
    transfer: InventoryTransfer;
    disabled: boolean;
    selection: DispatchSelection;
  }

  let { transfer, disabled, selection = $bindable() }: Props = $props();

  const MIN_REASON = 5;
  const MIN_SUBSTITUTION = 10;

  let vehicleId = $state('');
  let driverId = $state('');
  let overrideReason = $state('');
  let substitutionCode = $state<SubstitutionCode | ''>('');
  let substitutionReason = $state('');
  let judgement = $state<TransportJudgement | null>(null);
  let checking = $state(false);
  let options = $state<AssignmentOptions | null>(null);
  let approvedCheck = $state<DispatchCheck | null>(null);
  let approvedCheckFor = '';

  const approvedVehicle = $derived(transfer.approved_vehicle ?? null);
  const approvedDriver = $derived(transfer.approved_driver ?? null);
  const isApproved = $derived(transfer.status === 'approved' && approvedVehicle != null);
  const effectiveDriverId = $derived(driverId || judgement?.driverId || '');
  const needsSubstitution = $derived(
    isApproved &&
      Boolean(vehicleId) &&
      (vehicleId !== approvedVehicle?.id ||
        (approvedDriver != null &&
          effectiveDriverId !== '' &&
          effectiveDriverId !== approvedDriver.id))
  );
  const needsOverride = $derived(
    Boolean(judgement?.blocked && !judgement.hardBlocked && judgement.canOverride)
  );
  const substitutionReady = $derived(
    !needsSubstitution ||
      (substitutionCode !== '' && substitutionReason.trim().length >= MIN_SUBSTITUTION)
  );
  const ready = $derived(
    Boolean(
      vehicleId &&
      judgement &&
      !checking &&
      !judgement.hardBlocked &&
      (!judgement.blocked ||
        (judgement.canOverride && overrideReason.trim().length >= MIN_REASON)) &&
      substitutionReady
    )
  );
  const vehicle = $derived(
    options?.vehicles.find((item) => item.inventory_vehicle_id === vehicleId) ?? null
  );
  const approvedLabel = $derived.by(() => {
    if (!approvedVehicle) return '';
    const car = `${approvedVehicle.code} · ${approvedVehicle.plate ?? 'Sin placa'}`;
    return approvedDriver ? `${car} y ${approvedDriver.name}` : car;
  });
  const vehicleFallbackLabel = $derived(
    transfer.approved_vehicle || transfer.vehicle
      ? `${(transfer.approved_vehicle ?? transfer.vehicle)!.code} · ${(transfer.approved_vehicle ?? transfer.vehicle)!.plate ?? 'Sin placa'} · no figura entre las opciones`
      : ''
  );
  const driverFallbackLabel = $derived(
    (transfer.approved_driver ?? transfer.driver)
      ? `${(transfer.approved_driver ?? transfer.driver)!.name} · no figura entre las opciones`
      : ''
  );

  // Dispatch starts from what was approved or saved, even if it is no longer available: the
  // verdict below says why, and changing it is an explicit, audited decision.
  $effect(() => {
    const id = transfer.id;
    untrack(() => {
      void id;
      vehicleId = transfer.approved_vehicle?.id ?? transfer.vehicle?.id ?? '';
      driverId = transfer.approved_driver?.id ?? transfer.driver?.id ?? '';
      overrideReason = '';
      substitutionCode = '';
      substitutionReason = '';
      approvedCheck = null;
      approvedCheckFor = '';
    });
  });

  $effect(() => {
    const driverName =
      options?.drivers.find((item) => item.id === effectiveDriverId)?.name ??
      (effectiveDriverId === transfer.driver?.id ? transfer.driver?.name : '') ??
      '';
    selection = {
      vehicleId,
      driverId: effectiveDriverId,
      overrideReason: needsOverride ? overrideReason.trim() : '',
      substitutionCode: needsSubstitution ? substitutionCode : '',
      substitutionReason: needsSubstitution ? substitutionReason.trim() : '',
      ready,
      label: vehicle
        ? `${vehicle.code} · ${vehicle.plate ?? 'Sin placa'}${driverName ? ` · ${driverName}` : ''}`
        : ''
    };
  });

  // When the approved transport is being replaced, say whether it was still fit.
  $effect(() => {
    const id = transfer.id;
    if (!needsSubstitution || approvedCheckFor === id) return;
    approvedCheckFor = id;
    void (async () => {
      try {
        // The verdict of the approved transport as if it left now, not the planning-stage one.
        const result = await inventoryTransfersApi.dispatchCheck(
          id,
          approvedVehicle?.id ?? '',
          approvedDriver?.id ?? null
        );
        if (approvedCheckFor === id) approvedCheck = result;
      } catch {
        // The notice is optional; the server still enforces the rules.
      }
    })();
  });

  const approvedStillFit = $derived(approvedCheck != null && !approvedCheck.blocked);
</script>

<div class="space-y-3">
  {#if isApproved && !needsSubstitution}
    <p class="text-sm text-foreground-muted" id="dispatch-approved-note">
      Aprobado con {approvedLabel}. Puedes cambiarlos si lo necesitas; el cambio exige un motivo y
      queda registrado.
    </p>
  {/if}

  <TransferAssignmentPicker
    mode="dispatch"
    transferId={transfer.id}
    idPrefix="dispatch"
    bind:vehicleId
    bind:driverId
    bind:judgement
    bind:checking
    bind:options
    {disabled}
    {vehicleFallbackLabel}
    {driverFallbackLabel}
    savedDriverId={transfer.approved_driver?.id ?? transfer.driver?.id ?? ''}
  />

  {#if judgement}
    {#if needsOverride}
      <label class="block space-y-1 text-sm font-medium text-foreground" for="dispatch-override"
        >Motivo de la excepción (queda registrado en la auditoría)</label
      >
      <textarea
        id="dispatch-override"
        class="field-control min-h-[72px]"
        maxlength="500"
        bind:value={overrideReason}
        {disabled}
      ></textarea>
    {:else if judgement.blocked && !judgement.hardBlocked}
      <p class="text-xs text-foreground-muted">
        Solo un usuario autorizado para excepciones puede despachar con estos impedimentos.
      </p>
    {/if}
  {/if}

  {#if needsSubstitution}
    <section
      class="space-y-3 rounded-xl border border-warning/30 bg-warning/5 p-3"
      aria-labelledby="dispatch-substitution-title"
    >
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p id="dispatch-substitution-title">
          Se aprobó con {approvedLabel}. El cambio quedará registrado y auditado.
        </p>
        {#if approvedCheck}
          <p class="mt-1 text-xs text-foreground-muted">
            {approvedStillFit
              ? 'Lo aprobado todavía está apto; cambia solo si es necesario.'
              : 'Lo aprobado ya no está apto para el traslado.'}
          </p>
        {/if}
      </Callout>
      <div class="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div class="space-y-1">
          <label class="block text-sm font-medium text-foreground" for="dispatch-substitution-code"
            >Motivo del cambio</label
          >
          <select
            id="dispatch-substitution-code"
            class="field-control"
            value={substitutionCode}
            onchange={(event) =>
              (substitutionCode = event.currentTarget.value as SubstitutionCode | '')}
            {disabled}
          >
            <option value="">Elige el motivo</option>
            {#each SUBSTITUTION_CODE_OPTIONS as option (option.value)}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
        </div>
        <div class="space-y-1">
          <label
            class="block text-sm font-medium text-foreground"
            for="dispatch-substitution-reason">Explica el cambio</label
          >
          <textarea
            id="dispatch-substitution-reason"
            class="field-control min-h-[72px]"
            maxlength="500"
            aria-describedby="dispatch-substitution-help"
            bind:value={substitutionReason}
            {disabled}
          ></textarea>
          <p
            id="dispatch-substitution-help"
            class="text-xs {substitutionReason.trim().length >= MIN_SUBSTITUTION
              ? 'text-foreground-muted'
              : 'text-foreground'}"
          >
            Mínimo {MIN_SUBSTITUTION} caracteres ({substitutionReason.trim().length}).
          </p>
        </div>
      </div>
    </section>
  {/if}
</div>
