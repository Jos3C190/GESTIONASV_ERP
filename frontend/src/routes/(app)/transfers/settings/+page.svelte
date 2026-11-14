<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { inventoryTransfersApi } from '$lib/features/inventory/transfer-documents';
  import { permissions } from '$lib/stores/permissions.svelte';

  let form = $state({
    allow_branch_to_branch: false,
    allow_branch_to_central: false,
    require_approval: true
  });
  let pendingCount = $state(0);
  let approvedCount = $state(0);
  let loaded = $state(false);
  let error = $state<string | null>(null);
  let saveError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let saving = $state(false);

  const canSave = $derived(permissions.hasPermission('inventory:transfer_settings'));
  const canRead = $derived(permissions.hasPermission('inventory:read'));
  const frozenCount = $derived(pendingCount + approvedCount);

  function apply(result: Awaited<ReturnType<typeof inventoryTransfersApi.settings>>) {
    form = {
      allow_branch_to_branch: result.allow_branch_to_branch,
      allow_branch_to_central: result.allow_branch_to_central,
      require_approval: result.require_approval
    };
    pendingCount = result.pending_count;
    approvedCount = result.approved_count;
  }

  async function load() {
    error = null;
    try {
      apply(await inventoryTransfersApi.settings());
      loaded = true;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la configuración.';
    }
  }

  onMount(() => {
    if (canRead) void load();
  });

  async function save(event: SubmitEvent) {
    event.preventDefault();
    success = null;
    saveError = null;
    saving = true;
    try {
      apply(
        await inventoryTransfersApi.saveSettings({
          allow_branch_to_branch: form.allow_branch_to_branch,
          allow_branch_to_central: form.allow_branch_to_central,
          require_approval: form.require_approval
        })
      );
      success = 'Se guardó la configuración.';
    } catch (err) {
      saveError = err instanceof HttpError ? err.message : 'No se pudo guardar la configuración.';
    } finally {
      saving = false;
    }
  }

  function countText(count: number, one: string, many: string): string {
    return `${count} ${count === 1 ? one : many}`;
  }
</script>

<svelte:head>
  <title>Reglas de traslados | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para ver los traslados.
  </div>
{:else}
  <div class="space-y-5">
    <a href="/transfers" class="back">← Traslados</a>
    <header>
      <h1 class="text-2xl font-bold tracking-tight text-foreground">Reglas de traslados</h1>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        La distribución desde la bodega central siempre está habilitada y no necesita aprobación.
        Aquí decides si las sucursales también pueden mover mercancía y quién la autoriza.
      </p>
    </header>

    {#if error}
      <div class="failure" role="alert">
        <p>{error}</p>
        <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
      </div>
    {:else if !loaded}
      <p class="muted" role="status">Cargando…</p>
    {:else}
      <form class="form" onsubmit={save} novalidate>
        {#if frozenCount > 0}
          <Callout variant="warning" dismissible={false} class="mb-0">
            <p>
              Hay {countText(pendingCount, 'traslado pendiente', 'traslados pendientes')} de aprobación
              y {countText(approvedCount, 'aprobado', 'aprobados')} esperando despacho. Si apagas una
              ruta, los traslados de esa ruta quedan congelados: no se pueden aprobar ni despachar, pero
              aún se pueden rechazar, retirar o cancelar.
            </p>
          </Callout>
        {/if}

        <fieldset class="card" disabled={!canSave}>
          <legend>Rutas permitidas</legend>
          <label class="check">
            <input type="checkbox" bind:checked={form.allow_branch_to_branch} />
            <span>
              <strong>Permitir traslados entre sucursales</strong>
              <small>
                Una sucursal puede enviar mercancía a la bodega de otra sucursal, por ejemplo para
                cubrir un faltante.
              </small>
            </span>
          </label>
          <label class="check">
            <input type="checkbox" bind:checked={form.allow_branch_to_central} />
            <span>
              <strong>Permitir retornos a la bodega central</strong>
              <small>
                Una sucursal puede devolver a la matriz sobrantes, mercancía dañada o devoluciones.
              </small>
            </span>
          </label>
        </fieldset>

        <fieldset class="card" disabled={!canSave}>
          <legend>Control</legend>
          <label class="check">
            <input type="checkbox" bind:checked={form.require_approval} />
            <span>
              <strong>Exigir aprobación para traslados que salen de una sucursal</strong>
              <small>
                Quien tenga el permiso para aprobar traslados debe autorizar cada uno antes de
                despacharlo, y no puede aprobar lo que él mismo preparó o envió. Si lo apagas, lo
                que está pendiente puede retirarse y despacharse, o aprobarse.
              </small>
            </span>
          </label>
        </fieldset>

        <div role="status">
          {#if success}<p class="success">{success}</p>{/if}
        </div>
        {#if saveError}<p class="error" role="alert">{saveError}</p>{/if}
        {#if canSave}
          <div class="actions">
            <Button size="lg" type="submit" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </Button>
          </div>
        {:else}
          <p class="muted">
            Solo quien tenga el permiso de configurar las reglas de traslados puede cambiar esto.
          </p>
        {/if}
      </form>
    {/if}
  </div>
{/if}

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
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  small {
    display: block;
    font-weight: 400;
  }
  .form {
    display: grid;
    gap: 16px;
    max-width: 720px;
  }
  .card {
    display: grid;
    gap: 14px;
    min-width: 0;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  legend {
    float: left;
    width: 100%;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 600;
  }
  .check {
    clear: both;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-height: 44px;
    color: rgb(var(--foreground));
    font-size: 14px;
  }
  .check strong {
    font-weight: 500;
  }
  .check input {
    width: 20px;
    height: 20px;
    margin-top: 1px;
    flex: none;
  }
  .success,
  .failure {
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
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
  }
</style>
