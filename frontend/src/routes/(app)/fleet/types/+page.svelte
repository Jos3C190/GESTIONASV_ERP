<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { fleetApi, type FleetVehicleType } from '$lib/features/fleet/api';
  import { LICENSE_LABELS } from '$lib/features/fleet/catalog';
  import VehicleTypeForm from '$lib/features/fleet/VehicleTypeForm.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let types = $state<FleetVehicleType[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let showInactive = $state(false);
  let modalOpen = $state(false);
  let editing = $state<FleetVehicleType | null>(null);

  const canManage = $derived(permissions.hasPermission('fleet:manage_types'));
  const visible = $derived(types.filter((item) => showInactive || item.is_active));
  const inactiveCount = $derived(types.filter((item) => !item.is_active).length);

  async function load() {
    loading = true;
    error = null;
    try {
      types = await fleetApi.vehicleTypes(true);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los tipos.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (canManage) void load();
    else loading = false;
  });

  function open(item: FleetVehicleType | null) {
    editing = item;
    success = null;
    modalOpen = true;
  }

  async function saved() {
    const wasEditing = Boolean(editing);
    modalOpen = false;
    await load();
    success = wasEditing ? 'Se guardaron los cambios.' : 'El tipo ya está disponible en Flota.';
  }

  function licenses(item: FleetVehicleType): string {
    return item.license_classes.length
      ? item.license_classes.map((value) => LICENSE_LABELS[value]).join(', ')
      : 'No exige licencia';
  }

  function traits(item: FleetVehicleType): string {
    return [
      item.requires_plate ? 'Con placa' : 'Sin placa',
      item.meter_unit === 'hours' ? 'Mide horas' : 'Mide km',
      item.can_tow ? 'Remolca' : item.is_towable ? 'Se remolca' : null
    ]
      .filter(Boolean)
      .join(' · ');
  }

  function toggle(item: FleetVehicleType) {
    const activating = !item.is_active;
    success = null;
    confirmation.request({
      kind: activating ? 'restore' : 'deactivate',
      title: activating ? 'Reactivar tipo' : 'Desactivar tipo',
      description: activating
        ? 'Volverá a ofrecerse al registrar vehículos.'
        : `Dejará de ofrecerse al registrar vehículos. Los ${item.usage_count} que ya lo usan no cambian.`,
      resourceName: item.name,
      confirmLabel: activating ? 'Reactivar' : 'Desactivar',
      execute: async () => {
        await fleetApi.updateVehicleType(item.id, { ...item, is_active: activating });
        await load();
      }
    });
  }
</script>

<svelte:head>
  <title>Tipos de vehículo | GestionaSV</title>
</svelte:head>

{#if !canManage}
  <div
    class="m-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
    role="alert"
  >
    No tienes permiso para administrar los tipos de vehículo.
  </div>
{:else}
  <div class="space-y-5 p-4 sm:p-6 md:p-8">
    <a href="/fleet" class="text-sm text-foreground-muted hover:text-foreground">← Flota</a>
    <header class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-foreground">Tipos de vehículo</h1>
        <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
          Define qué unidades maneja tu empresa y qué se exige a cada una.
        </p>
      </div>
      <Button size="lg" onclick={() => open(null)}>Nuevo tipo</Button>
    </header>

    {#if success}
      <p
        class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success"
        role="status"
      >
        {success}
      </p>
    {/if}

    {#if inactiveCount}
      <label class="flex min-h-11 w-fit items-center gap-2 text-sm text-foreground-muted">
        <input type="checkbox" bind:checked={showInactive} /> Mostrar {inactiveCount} inactivo(s)
      </label>
    {/if}

    {#if loading}
      <p class="text-sm text-foreground-muted" role="status">Cargando tipos…</p>
    {:else if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        <p>{error}</p>
        <Button class="mt-3" variant="secondary" size="sm" onclick={() => void load()}
          >Reintentar</Button
        >
      </div>
    {:else}
      <ul class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {#each visible as item (item.id)}
          <li class="flex flex-col gap-3 rounded-xl border border-border bg-surface-elevated p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 class="font-semibold text-foreground">{item.name}</h2>
                <p class="mt-1 text-sm text-foreground-muted">{traits(item)}</p>
              </div>
              {#if !item.is_active}<Badge variant="neutral">Inactivo</Badge>{/if}
            </div>
            <dl class="grid gap-1 text-sm">
              <div>
                <dt class="inline text-foreground-muted">Licencia:</dt>
                <dd class="inline text-foreground">{licenses(item)}</dd>
              </div>
              <div>
                <dt class="inline text-foreground-muted">Vehículos:</dt>
                <dd class="inline text-foreground">{item.usage_count}</dd>
              </div>
            </dl>
            <div class="mt-auto grid grid-cols-2 gap-2">
              <Button variant="secondary" size="lg" onclick={() => open(item)}>Editar</Button>
              <Button variant="ghost" size="lg" onclick={() => toggle(item)}>
                {item.is_active ? 'Desactivar' : 'Reactivar'}
              </Button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<Modal
  open={modalOpen}
  title={editing ? `Editar ${editing.name}` : 'Nuevo tipo de vehículo'}
  size="md"
  mobileFullScreen
  onclose={() => (modalOpen = false)}
>
  {#if modalOpen}
    <VehicleTypeForm
      item={editing}
      oncancel={() => (modalOpen = false)}
      onsaved={() => void saved()}
    />
  {/if}
</Modal>
