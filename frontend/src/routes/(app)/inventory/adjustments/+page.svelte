<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { adjustmentInputClass, adjustmentNoticeClass } from '$lib/features/inventory/adjustment-styles';
  import { inventoryAdjustmentsApi, type AdjustmentStatus, type InventoryAdjustment } from '$lib/features/inventory/adjustments';
  import { getWarehouses } from '$lib/services/warehouses';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  const canCreate = $derived(permissions.hasPermission('inventory:adjust'));
  let items = $state<InventoryAdjustment[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let total = $state(0);
  let warehouses = $state<Warehouse[]>([]);
  let warehouseId = $state('');
  let status = $state<AdjustmentStatus | ''>('');
  let dateFrom = $state('');
  let dateTo = $state('');
  let requestSequence = 0;
  let loadedScope = '';

  const statusLabel: Record<AdjustmentStatus, string> = {
    draft: 'Borrador', approved: 'Aprobado', applied: 'Aplicado', cancelled: 'Cancelado'
  };

  function errorText(cause: unknown) {
    return cause instanceof Error ? cause.message : 'No se pudieron cargar los ajustes.';
  }

  async function load() {
    const sequence = ++requestSequence;
    const scope = `${company.id ?? ''}:${branch.id ?? ''}`;
    loadedScope = scope;
    loading = true;
    error = null;
    try {
      const result = await inventoryAdjustmentsApi.list({
        status: status || undefined,
        warehouse_id: warehouseId || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 100,
        offset: 0
      });
      if (sequence !== requestSequence || scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      items = result.items;
      total = result.total;
    } catch (cause) {
      if (sequence === requestSequence) error = errorText(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function submitFilters(event: SubmitEvent) {
    event.preventDefault();
    void load();
  }

  function date(value: string) {
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'America/El_Salvador' }).format(new Date(`${value}T12:00:00-06:00`));
  }

  async function loadWarehouses() {
    const scope = `${company.id ?? ''}:${branch.id ?? ''}`;
    try {
      const all: Warehouse[] = [];
      let page = 1;
      let pages = 1;
      do {
        const result = await getWarehouses({ branchId: branch.id ?? undefined, page, size: 100, status: 'active' });
        if (scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
        all.push(...result.items);
        pages = Math.max(1, result.meta.pages);
        page += 1;
      } while (page <= pages);
      if (scope === `${company.id ?? ''}:${branch.id ?? ''}`) warehouses = all;
    } catch {
      // The adjustment list remains usable without its optional filter.
    }
  }

  onMount(() => { void loadWarehouses(); void load(); });
  $effect(() => {
    const scope = `${company.id ?? ''}:${branch.id ?? ''}`;
    if (loadedScope && loadedScope !== scope) { void loadWarehouses(); void load(); }
  });
</script>

<svelte:head><title>Ajustes de inventario | GestionaSV</title></svelte:head>

<main class="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
  <header class="flex flex-wrap items-end justify-between gap-4">
    <div><p class="text-xs font-semibold uppercase tracking-wider text-primary">Inventario</p><h1 class="mt-1 text-2xl font-semibold text-foreground">Ajustes de inventario</h1><p class="mt-1 max-w-3xl text-sm text-foreground-muted">Corrige cantidades con motivo, documento de respaldo, aprobación e historial. Crear o aprobar no modifica existencias.</p></div>
    {#if canCreate}<Button onclick={() => void goto('/inventory/adjustments/new')}>Nuevo ajuste</Button>{/if}
  </header>

  <section class="rounded-xl border border-border bg-surface p-4">
    <form class="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1fr_1fr_auto] lg:items-end" onsubmit={submitFilters}>
      <label class="space-y-1 text-sm font-medium text-foreground">Bodega<select class={adjustmentInputClass} bind:value={warehouseId}><option value="">Todas las bodegas</option>{#each warehouses as warehouse (warehouse.id)}<option value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>{/each}</select></label>
      <label class="space-y-1 text-sm font-medium text-foreground">Estado<select class={adjustmentInputClass} bind:value={status}><option value="">Todos los estados</option><option value="draft">Borrador</option><option value="approved">Aprobado</option><option value="applied">Aplicado</option><option value="cancelled">Cancelado</option></select></label>
      <label class="space-y-1 text-sm font-medium text-foreground">Desde<input class={adjustmentInputClass} type="date" bind:value={dateFrom} /></label>
      <label class="space-y-1 text-sm font-medium text-foreground">Hasta<input class={adjustmentInputClass} type="date" bind:value={dateTo} /></label>
      <Button type="submit" variant="secondary" disabled={loading}>Filtrar</Button>
    </form>
  </section>

  {#if error}
    <section class={`${adjustmentNoticeClass} border-danger/30 bg-danger/10 flex flex-wrap items-center justify-between gap-3`} role="alert"><span>{error}</span><Button size="sm" variant="secondary" onclick={() => void load()}>Reintentar</Button></section>
  {:else if loading}
    <section class="rounded-xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted" role="status">Consultando ajustes autorizados…</section>
  {:else if items.length === 0}
    <section class="rounded-xl border border-border bg-surface px-5 py-12 text-center"><div class="mx-auto max-w-lg"><div class="mx-auto grid size-12 place-items-center rounded-full bg-primary/10 text-xl text-primary" aria-hidden="true">↗</div><h2 class="mt-4 text-lg font-semibold text-foreground">{total === 0 ? 'Todavía no hay ajustes' : 'No hay resultados para esos filtros'}</h2><p class="mt-2 text-sm text-foreground-muted">{total === 0 ? 'Cuando registres una diferencia, aquí podrás seguir su soporte y estado sin alterar movimientos anteriores.' : 'Cambia los filtros para ampliar la consulta.'}</p>{#if canCreate && total === 0}<Button class="mt-5" onclick={() => void goto('/inventory/adjustments/new')}>Crear primer ajuste</Button>{/if}</div></section>
  {:else}
    <section class="space-y-3" aria-label="Ajustes registrados"><p class="text-sm text-foreground-muted">{total} ajuste(s) · mostramos hasta 100 registros</p>
      {#each items as item (item.id)}
        <a class="block rounded-xl border border-border bg-surface p-4 transition-colors hover:border-primary/40 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" href={`/inventory/adjustments/${item.id}`}>
          <div class="flex flex-wrap items-start justify-between gap-3"><div><p class="font-mono text-sm font-semibold text-primary">{item.code}</p><h2 class="mt-1 font-semibold text-foreground">{item.warehouse_name}</h2><p class="mt-1 text-sm text-foreground-muted">{item.reason}</p></div><span class="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground">{statusLabel[item.status]}</span></div>
          <div class="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4"><div><span class="text-foreground-muted">Referencia</span><p class="mt-0.5 font-medium text-foreground">{item.document_reference}</p></div><div><span class="text-foreground-muted">Fecha operativa</span><p class="mt-0.5 font-medium text-foreground">{date(item.operational_date)}</p></div><div><span class="text-foreground-muted">Líneas</span><p class="mt-0.5 font-medium text-foreground">{item.lines.length}</p></div><div><span class="text-foreground-muted">Soporte vigente</span><p class="mt-0.5 font-medium text-foreground">{item.documents.filter((document) => document.active && document.upload_completed && document.technical_status === 'active').length} comprobante(s)</p></div></div>
          <div class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-foreground-muted">{#each item.lines.slice(0, 2) as line (line.id)}<span>{line.product_name} · {line.direction === 'increase' ? '+' : '−'}{line.quantity_base} {line.base_unit_symbol ?? line.base_unit_name}</span>{/each}{#if item.lines.length > 2}<span>y {item.lines.length - 2} más</span>{/if}</div>
        </a>
      {/each}
    </section>
  {/if}
</main>
