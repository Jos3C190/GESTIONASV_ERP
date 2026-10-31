<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { TransferVehicle } from '$lib/features/inventory/transfer-documents';

  type CollectionState = 'loading' | 'loaded' | 'empty' | 'error';
  interface Props {
    vehicles: TransferVehicle[];
    state: CollectionState;
    error: string | null;
    canManage: boolean;
    saving: boolean;
    code: string;
    name: string;
    onCodeChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onSave: (event: SubmitEvent) => void;
    onToggleStatus: (vehicle: TransferVehicle) => void;
  }

  let {
    vehicles,
    state,
    error,
    canManage,
    saving,
    code,
    name,
    onCodeChange,
    onNameChange,
    onSave,
    onToggleStatus
  }: Props = $props();
</script>

<section class="space-y-5" aria-labelledby="vehicles-heading">
  <header>
    <h2 id="vehicles-heading" class="text-lg font-semibold text-foreground">Vehículos de traslado</h2>
    <p class="mt-1 text-sm text-foreground-muted">El servidor crea la ubicación móvil vinculada a cada vehículo. No se captura una bodega técnica.</p>
  </header>

  {#if error}<p class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</p>{/if}

  {#if canManage}
    <form class="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:grid-cols-[180px_1fr_auto] sm:items-end" onsubmit={onSave}>
      <label class="space-y-1 text-sm font-medium text-foreground">
        Código
        <input class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" required maxlength="32" value={code} oninput={(event) => onCodeChange(event.currentTarget.value)} placeholder="VAN-01" />
      </label>
      <label class="space-y-1 text-sm font-medium text-foreground">
        Nombre
        <input class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" required minlength="2" maxlength="120" value={name} oninput={(event) => onNameChange(event.currentTarget.value)} placeholder="Camioneta de reparto" />
      </label>
      <Button disabled={saving}>{saving ? 'Guardando…' : 'Registrar vehículo'}</Button>
    </form>
  {/if}

  {#if state === 'loading'}
    <p class="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted" role="status">Consultando vehículos…</p>
  {:else if state === 'error'}
    <p class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">No se pudo consultar el catálogo. La recepción en sucursal sigue disponible desde Documentos.</p>
  {:else if state === 'empty'}
    <p class="rounded-xl border border-border border-dashed bg-surface p-7 text-sm text-foreground-muted">No hay vehículos registrados para esta empresa.</p>
  {:else}
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {#each vehicles as vehicle (vehicle.id)}
        <article class="rounded-2xl border border-border bg-surface p-4">
          <div class="flex items-start justify-between gap-3">
            <div><p class="font-mono text-sm font-semibold text-primary">{vehicle.code}</p><h3 class="mt-1 font-medium text-foreground">{vehicle.name}</h3></div>
            <span class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium {vehicle.status === 'active' ? 'border-success/30 bg-success/10 text-success' : 'border-border bg-surface-muted text-foreground-muted'}" data-status={vehicle.status}>{vehicle.status === 'active' ? 'Activo' : 'Inactivo'}</span>
          </div>
          <p class="mt-3 text-xs text-foreground-muted">Ubicación móvil: {vehicle.transit_warehouse_name}</p>
          {#if canManage}
            <Button class="mt-4" variant="secondary" size="sm" disabled={saving} onclick={() => onToggleStatus(vehicle)}>{vehicle.status === 'active' ? 'Desactivar' : 'Activar'}</Button>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>

