<script lang="ts">
  import Callout from '$lib/components/ui/Callout.svelte';
  import type { InventoryTransfer } from '$lib/features/inventory/transfer-documents';
  import { substitutionCodeLabel } from '$lib/features/inventory/transfer-operations';

  interface Props {
    transfer: InventoryTransfer;
    formatDate: (value: string | null | undefined) => string;
  }
  let { transfer, formatDate }: Props = $props();

  const vehicle = $derived(transfer.vehicle);
  const driver = $derived(transfer.driver ?? null);
  const approvedVehicle = $derived(transfer.approved_vehicle ?? null);
  const approvedDriver = $derived(transfer.approved_driver ?? null);
  const substitution = $derived(transfer.assignment_substitution ?? null);
  // What the approver authorised is only worth repeating when the trip left with something else.
  const vehicleChanged = $derived(
    approvedVehicle != null && vehicle != null && approvedVehicle.id !== vehicle.id
  );
  const driverChanged = $derived(
    approvedDriver != null && driver != null && approvedDriver.id !== driver.id
  );
  const hasContent = $derived(
    vehicle != null ||
      driver != null ||
      substitution != null ||
      Boolean(transfer.compliance_override_reason)
  );

  function vehicleText(item: { code: string; plate?: string | null }): string {
    return `${item.code} · ${item.plate ?? 'Sin placa'}`;
  }
</script>

{#if hasContent}
  <section
    class="space-y-3 rounded-xl border border-border bg-surface p-4"
    aria-labelledby="transfer-transport-card-title"
  >
    <h3 id="transfer-transport-card-title" class="font-semibold text-foreground">Transporte</h3>
    <dl class="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      <div>
        <dt class="text-xs text-foreground-muted">Vehículo</dt>
        <dd class="font-medium text-foreground">
          {#if vehicle}
            {vehicleText(vehicle)}
            {#if vehicle.name}<span class="font-normal text-foreground-muted">{vehicle.name}</span>{/if}
          {:else}
            <span class="font-normal text-foreground-muted">Sin registrar</span>
          {/if}
        </dd>
        {#if vehicleChanged && approvedVehicle}
          <dd class="text-xs text-foreground-muted">Aprobado: {vehicleText(approvedVehicle)}</dd>
        {/if}
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Conductor</dt>
        <dd class="font-medium text-foreground">
          {#if driver}
            {driver.name}
            <span class="font-normal text-foreground-muted">{driver.employee_code}</span>
          {:else}
            <span class="font-normal text-foreground-muted">Sin registrar</span>
          {/if}
        </dd>
        {#if driverChanged && approvedDriver}
          <dd class="text-xs text-foreground-muted">Aprobado: {approvedDriver.name}</dd>
        {/if}
      </div>
    </dl>
    {#if substitution}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p class="font-medium text-foreground">
          Se cambió el transporte aprobado: {substitutionCodeLabel(substitution.code)}.
        </p>
        <p class="mt-1 text-foreground-muted">
          {substitution.reason}
          <span class="block text-xs"
            >Registrado {substitution.by_name ? `por ${substitution.by_name} ` : ''}el {formatDate(
              substitution.at
            )}.</span
          >
        </p>
      </Callout>
    {/if}
    {#if transfer.compliance_override_reason}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p class="font-medium text-foreground">Salió con una excepción autorizada.</p>
        <p class="mt-1 text-foreground-muted">{transfer.compliance_override_reason}</p>
      </Callout>
    {/if}
  </section>
{/if}
