<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle } from './api';
  import { formatDate, plateLabel } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: (next: FleetVehicle) => void } =
    $props();

  let trailers = $state<FleetVehicle[]>([]);
  let selected = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const canManage = $derived(
    permissions.hasPermission('fleet:update') && vehicle.status !== 'retired'
  );
  const isTractor = $derived(vehicle.type.can_tow);
  const partnerLabel = $derived(isTractor ? 'Remolque' : 'Cabezal');

  async function loadTrailers() {
    try {
      const page = await fleetApi.list({ include_retired: false, page: 1, size: 100 });
      trailers = page.items.filter(
        (item) =>
          item.type.is_towable &&
          !item.coupling &&
          item.branch_id === vehicle.branch_id &&
          item.status !== 'retired'
      );
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los remolques.';
    }
  }

  $effect(() => {
    if (isTractor && canManage && !vehicle.coupling) void loadTrailers();
  });

  async function couple() {
    if (!selected) return;
    saving = true;
    error = null;
    try {
      onchanged(await fleetApi.couple(vehicle.id, selected));
      selected = '';
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo enganchar.';
    } finally {
      saving = false;
    }
  }

  function uncouple() {
    confirmation.request({
      kind: 'release',
      title: 'Desenganchar',
      description: 'Las dos unidades quedarán separadas. El historial se conserva.',
      resourceName: vehicle.coupling?.code,
      confirmLabel: 'Desenganchar',
      execute: async () => onchanged(await fleetApi.uncouple(vehicle.id))
    });
  }
</script>

<section class="coupling">
  <h2>Enganche</h2>
  {#if vehicle.coupling}
    <p class="partner">
      <span>{partnerLabel}</span>
      <a href={`/fleet/${vehicle.coupling.vehicle_id}`}>
        {vehicle.coupling.code} · {plateLabel(vehicle.coupling.plate)}
      </a>
      <small>Desde {formatDate(vehicle.coupling.since)}</small>
    </p>
    {#if canManage}
      <Button variant="secondary" size="lg" onclick={uncouple}>Desenganchar</Button>
    {/if}
  {:else if !isTractor}
    <p class="muted">Sin cabezal. Engánchalo desde la ficha del cabezal.</p>
  {:else if canManage && trailers.length}
    <label>
      <span>Remolque disponible en esta sucursal</span>
      <select bind:value={selected}>
        <option value="">Selecciona un remolque</option>
        {#each trailers as item (item.id)}
          <option value={item.id}>{item.code} · {plateLabel(item.plate)}</option>
        {/each}
      </select>
    </label>
    <Button size="lg" disabled={saving || !selected} onclick={couple}>
      {saving ? 'Enganchando…' : 'Enganchar'}
    </Button>
  {:else}
    <p class="muted">Sin remolque enganchado.</p>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .coupling {
    display: grid;
    justify-items: stretch;
    gap: 10px;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }
  .partner {
    display: grid;
    gap: 2px;
    margin: 0;
    font-size: 14px;
  }
  .partner span,
  .partner small,
  .muted {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .partner a {
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  label {
    display: grid;
    gap: 6px;
    font-size: 13px;
  }
  select {
    min-height: 44px;
    padding: 0 10px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface));
  }
  .error {
    margin: 0;
    color: rgb(var(--danger));
    font-size: 14px;
  }
</style>
