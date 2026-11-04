<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { fleetApi, type InspectionItem } from '$lib/features/fleet/api';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let items = $state<InspectionItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let open = $state(false);
  let editing = $state<InspectionItem | null>(null);
  let name = $state('');
  let critical = $state(false);
  let saving = $state(false);
  let attempted = $state(false);
  let formError = $state<string | null>(null);

  const canManage = $derived(permissions.hasPermission('fleet:manage_types'));
  const nameError = $derived(name.trim().length >= 2 ? undefined : 'Escribe el nombre del punto.');

  function message(err: unknown, fallback: string): string {
    return err instanceof HttpError ? err.message : fallback;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      items = await fleetApi.inspectionItems(true);
    } catch (err) {
      error = message(err, 'No se pudo cargar la lista.');
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (canManage) void load();
    else loading = false;
  });

  function edit(item: InspectionItem | null) {
    editing = item;
    name = item?.name ?? '';
    critical = item?.is_critical ?? false;
    attempted = false;
    formError = null;
    success = null;
    open = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    if (nameError) {
      await tick();
      document.getElementById('item-name')?.focus();
      return;
    }
    saving = true;
    formError = null;
    try {
      if (editing) {
        await fleetApi.updateInspectionItem(editing.id, {
          name: name.trim(),
          is_critical: critical,
          is_active: editing.is_active
        });
      } else {
        await fleetApi.createInspectionItem({ name: name.trim(), is_critical: critical });
      }
      success = editing ? 'Se guardó el punto.' : 'El punto ya está en la lista.';
      open = false;
      await load();
    } catch (err) {
      formError = message(err, 'No se pudo guardar el punto.');
    } finally {
      saving = false;
    }
  }

  function toggle(item: InspectionItem) {
    const activating = !item.is_active;
    success = null;
    confirmation.request({
      kind: activating ? 'restore' : 'deactivate',
      title: activating ? 'Reactivar punto' : 'Desactivar punto',
      description: activating
        ? 'Volverá a pedirse en las inspecciones.'
        : 'Dejará de pedirse en las inspecciones nuevas. Las anteriores no cambian.',
      resourceName: item.name,
      confirmLabel: activating ? 'Reactivar' : 'Desactivar',
      execute: async () => {
        await fleetApi.updateInspectionItem(item.id, {
          name: item.name,
          is_critical: item.is_critical,
          is_active: activating
        });
        success = activating ? 'Se reactivó el punto.' : 'Se desactivó el punto.';
        await load();
      }
    });
  }
</script>

<svelte:head>
  <title>Puntos de inspección | GestionaSV</title>
</svelte:head>

{#if !canManage}
  <div
    class="m-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
    role="alert"
  >
    No tienes permiso para administrar la lista de inspección.
  </div>
{:else}
  <div class="space-y-5 p-4 sm:p-6 md:p-8">
    <a href="/fleet" class="back">← Flota</a>
    <header class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-foreground">Puntos de inspección</h1>
        <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
          Lo que se revisa antes de salir. Si un punto crítico falla, el vehículo no se despacha
          hasta resolverlo o autorizarlo.
        </p>
      </div>
      <Button size="lg" onclick={() => edit(null)}>Nuevo punto</Button>
    </header>

    <div role="status">
      {#if success}<p class="success">{success}</p>{/if}
    </div>

    {#if error}
      <div class="failure" role="alert">
        <p>{error}</p>
        <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
      </div>
    {:else if loading}
      <p class="muted" role="status">Cargando…</p>
    {:else if items.length === 0}
      <p class="empty">Aún no hay puntos. Agrega el primero.</p>
    {:else}
      <ul class="items">
        {#each items as item (item.id)}
          <li class:inactive={!item.is_active}>
            <div>
              <strong>{item.name}</strong>
              <small>
                {item.is_critical
                  ? 'Crítico: frena el despacho'
                  : 'No frena el despacho'}{item.is_active ? '' : ' · Inactivo'}
              </small>
            </div>
            <div class="actions">
              <button type="button" aria-label={`Editar ${item.name}`} onclick={() => edit(item)}
                >Editar</button
              >
              <button
                type="button"
                aria-label={`${item.is_active ? 'Desactivar' : 'Reactivar'} ${item.name}`}
                onclick={() => toggle(item)}>{item.is_active ? 'Desactivar' : 'Reactivar'}</button
              >
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<Modal
  {open}
  title={editing ? 'Editar punto' : 'Nuevo punto'}
  size="sm"
  mobileFullScreen
  preventClose={saving}
  onclose={() => (open = false)}
>
  <form id="item-form" class="form" onsubmit={save} novalidate>
    <FormField
      id="item-name"
      label="Nombre"
      bind:value={name}
      maxlength={120}
      required
      placeholder="Ej. Rampa hidráulica"
      error={attempted ? nameError : undefined}
    />
    <label class="check">
      <input type="checkbox" bind:checked={critical} />
      <span>
        <strong>Es crítico</strong>
        <small>Si falla, el vehículo no se despacha hasta resolverlo o autorizarlo.</small>
      </span>
    </label>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={() => (open = false)}>
      Cancelar
    </Button>
    <Button size="lg" type="submit" form="item-form" disabled={saving}>
      {saving ? 'Guardando…' : 'Guardar'}
    </Button>
  {/snippet}
</Modal>

<style>
  .back {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  small,
  .muted {
    display: block;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  .success,
  .failure,
  .empty {
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    font-size: 13px;
  }
  .success {
    border-color: rgb(var(--success) / 0.3);
    background: rgb(var(--success) / 0.1);
    color: rgb(var(--success));
  }
  .failure {
    display: grid;
    gap: 10px;
    justify-items: start;
    border-color: rgb(var(--danger) / 0.3);
    color: rgb(var(--danger));
  }
  .empty {
    background: rgb(var(--surface));
    color: rgb(var(--foreground-muted));
  }
  .items {
    display: grid;
    gap: 8px;
    list-style: none;
  }
  .items li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 4px 12px;
    padding: 8px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 14px;
  }
  .items li > div:first-child {
    flex: 1 1 220px;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .inactive strong {
    color: rgb(var(--foreground-muted));
    font-weight: 500;
  }
  .actions {
    display: flex;
    gap: 14px;
  }
  .actions button {
    min-width: 44px;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .form :global(input:not([type='checkbox'])) {
    border-color: rgb(var(--control-border));
    font-size: 16px;
  }
  .check {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 14px;
  }
  .check input {
    width: 20px;
    height: 20px;
    margin-top: 1px;
    flex: none;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  @media (min-width: 768px) {
    .form :global(input:not([type='checkbox'])) {
      font-size: 13px;
    }
  }
</style>
