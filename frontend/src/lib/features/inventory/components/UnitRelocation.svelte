<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import type { HandlingUnit } from '../types';
  import { inventoryApi } from '../services';
  import { workspaceField } from '../workspace';
  import { formatMovementQuantity as qty } from '../movement-presentation';
  let { unit, onclose, onmoved }: { unit: HandlingUnit; onclose: () => void; onmoved: () => void } =
    $props();
  let dialog = $state<HTMLDialogElement>();
  let locations = $state<LocationOut[]>([]);
  let page = $state(0);
  let pages = $state(1);
  let loading = $state(true);
  let error = $state('');
  let destination = $state('');
  let reason = $state('');
  let saving = $state(false);
  let alive = true;
  let attempt: { fingerprint: string; key: string } | null = null;
  $effect(() => {
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      dialog?.close();
    };
  });
  $effect(() => {
    alive = true;
    untrack(() => void load());
    return () => {
      alive = false;
    };
  });
  async function load(reset = false) {
    loading = true;
    error = '';
    try {
      const data = await listLocations(unit.warehouse_id, {
        page: reset ? 1 : page + 1,
        size: 100,
        is_active: true,
        lifecycle_status: 'active'
      });
      if (!alive) return;
      const eligible = data.items.filter(
        (row) => row.storage_eligible && row.id !== unit.location_id
      );
      locations = reset ? eligible : [...locations, ...eligible];
      page = data.meta.page;
      pages = data.meta.pages;
    } catch (cause) {
      if (alive)
        error = cause instanceof Error ? cause.message : 'No se pudieron cargar las ubicaciones.';
    } finally {
      if (alive) loading = false;
    }
  }
  async function confirm(event: SubmitEvent) {
    event.preventDefault();
    if (!destination || reason.trim().length < 5 || saving) return;
    const fingerprint = `${destination}:${reason.trim()}`;
    if (!attempt || attempt.fingerprint !== fingerprint)
      attempt = { fingerprint, key: crypto.randomUUID() };
    saving = true;
    error = '';
    try {
      await inventoryApi.transferUnits(
        [unit],
        destination,
        `Reubicación: ${reason.trim()}`,
        'available',
        'available',
        attempt.key
      );
      onmoved();
      onclose();
    } catch (cause) {
      if (alive)
        error = cause instanceof Error ? cause.message : 'No se pudo confirmar la reubicación.';
    } finally {
      if (alive) saving = false;
    }
  }
</script>

<dialog
  bind:this={dialog}
  aria-labelledby="relocation-title"
  class="m-auto max-h-[90dvh] w-[min(94vw,560px)] overflow-auto rounded-xl border border-border bg-surface p-5 text-foreground shadow-xl backdrop:bg-black/60"
  oncancel={(event) => {
    event.preventDefault();
    if (!saving) onclose();
  }}
>
  <h2 id="relocation-title" class="text-lg font-semibold">Reubicar en esta bodega</h2>
  <p class="mt-2 text-sm text-foreground-muted">
    {unit.product_name ?? 'Producto'} · {qty(unit.quantity_base)}
    {unit.base_unit_symbol}
  </p>
  <p class="mt-1 break-all font-mono text-xs text-foreground-muted">{unit.code}</p>
  <form class="mt-5 space-y-4" onsubmit={confirm}>
    <label class="block text-sm font-medium"
      >Nueva ubicación<select
        class={workspaceField}
        value={destination}
        onchange={(event) => (destination = event.currentTarget.value)}
        required
        disabled={saving || loading}
        ><option value="">Selecciona un espacio</option>{#each locations as row (row.id)}<option
            value={row.id}>{row.code}</option
          >{/each}</select
      ></label
    >
    {#if page < pages}<Button
        type="button"
        variant="secondary"
        disabled={loading || saving}
        onclick={() => load()}>Cargar más espacios</Button
      >{/if}
    {#if !loading && !error && !locations.length && page >= pages}<div
        class="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm"
      >
        <p>
          No hay otra ubicación de almacenamiento habilitada. Revisa los espacios de esta bodega
          antes de mover la unidad.
        </p>
        <Button type="button" variant="secondary" class="mt-3" onclick={() => load(true)}
          >Volver a consultar ubicaciones</Button
        >
      </div>{/if}
    <label class="block text-sm font-medium"
      >Motivo<textarea
        class={workspaceField}
        bind:value={reason}
        minlength="5"
        maxlength="120"
        required
        disabled={saving}
        placeholder="Ej. Reacomodo del pasillo"
      ></textarea></label
    >
    <p class="text-sm text-foreground-muted">
      Mueve la unidad completa y conserva la cantidad total, el lote y su costo. La capacidad del
      destino se valida al confirmar.
    </p>
    {#if error}<div
        role="alert"
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm"
      >
        {error}{#if !locations.length}<Button
            class="mt-2"
            type="button"
            variant="secondary"
            onclick={() => load(true)}>Reintentar</Button
          >{/if}
      </div>{/if}
    <div class="flex flex-wrap justify-end gap-3">
      <Button type="button" variant="secondary" disabled={saving} onclick={onclose}>Cancelar</Button
      ><Button type="submit" disabled={saving || loading || !destination}
        >{saving ? 'Confirmando…' : 'Confirmar reubicación'}</Button
      >
    </div>
  </form>
</dialog>
