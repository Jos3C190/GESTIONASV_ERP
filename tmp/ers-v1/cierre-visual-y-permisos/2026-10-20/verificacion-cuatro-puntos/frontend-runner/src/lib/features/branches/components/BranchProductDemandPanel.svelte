<script lang="ts">
  import { onMount } from 'svelte';
  import {
    branchProductDemandApi,
    type BranchDemandLevel,
    type BranchProductDemandItem
  } from '$lib/api/branch-product-demand';
  import Card from '$lib/components/ui/Card.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let { branchId }: { branchId: string } = $props();

  let items = $state<BranchProductDemandItem[]>([]);
  let dateFrom = $state('');
  let dateTo = $state('');
  let loading = $state(true);
  let savingProductId = $state<number | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let drafts = $state<Record<number, BranchDemandLevel | ''>>({});

  const canRead = $derived(permissions.hasPermission('purchase_requests:read'));
  const canManage = $derived(permissions.hasPermission('purchase_requests:manage'));

  function localDate(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function setDefaultPeriod() {
    const today = new Date();
    const start = new Date(today);
    start.setDate(start.getDate() - 29);
    dateTo = localDate(today);
    dateFrom = localDate(start);
  }

  async function loadDemand() {
    if (!canRead) {
      loading = false;
      return;
    }
    loading = true;
    error = null;
    notice = null;
    try {
      const response = await branchProductDemandApi.list(branchId, dateFrom, dateTo);
      items = response.items;
      drafts = {};
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo cargar la demanda de productos.';
    } finally {
      loading = false;
    }
  }

  function changedLevel(productId: number, value: string) {
    drafts[productId] = value as BranchDemandLevel | '';
    notice = null;
  }

  function hasUnsavedChange(item: BranchProductDemandItem): boolean {
    if (!(item.product_id in drafts)) return false;
    const next = drafts[item.product_id] || null;
    return next !== item.demand_level;
  }

  async function saveLevel(item: BranchProductDemandItem) {
    if (!canManage || !hasUnsavedChange(item)) return;
    savingProductId = item.product_id;
    error = null;
    notice = null;
    try {
      const level = drafts[item.product_id] || null;
      await branchProductDemandApi.setLevel(branchId, item.product_id, level);
      items = items.map((current) =>
        current.product_id === item.product_id ? { ...current, demand_level: level } : current
      );
      delete drafts[item.product_id];
      notice = `Nivel de demanda guardado para ${item.product_name}.`;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo guardar el nivel de demanda.';
    } finally {
      savingProductId = null;
    }
  }

  function formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium' }).format(new Date(value));
  }

  function formatQuantity(value: number): string {
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 3 }).format(value);
  }

  onMount(() => {
    setDefaultPeriod();
    void loadDemand();
  });
</script>

<div class="space-y-5" id="tab-panel-demanda" role="tabpanel" aria-labelledby="tab-demanda">
  <Card class="p-5 md:p-6">
    <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div>
        <p class="text-[10px] font-bold uppercase tracking-wider text-primary">
          Abastecimiento de sucursal
        </p>
        <h2 class="mt-1 text-lg font-semibold text-foreground">Demanda de productos</h2>
        <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
          Consulta qué productos ha pedido esta sucursal y con qué frecuencia. Esto mide solicitudes
          internas, no ventas al cliente. El nivel es manual y no cambia solicitudes ni compras.
        </p>
      </div>
      <div class="flex flex-wrap items-end gap-3">
        <label class="grid gap-1 text-xs text-foreground-muted">
          Desde
          <input
            class="min-h-10 rounded-md border border-border bg-surface px-3 text-sm text-foreground"
            type="date"
            bind:value={dateFrom}
          />
        </label>
        <label class="grid gap-1 text-xs text-foreground-muted">
          Hasta
          <input
            class="min-h-10 rounded-md border border-border bg-surface px-3 text-sm text-foreground"
            type="date"
            bind:value={dateTo}
          />
        </label>
        <button
          type="button"
          class="min-h-10 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          disabled={loading || !dateFrom || !dateTo || dateFrom > dateTo}
          onclick={loadDemand}
        >
          Consultar
        </button>
      </div>
    </div>
    <div
      class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border pt-4 text-xs text-foreground-muted"
    >
      <span
        ><strong class="text-foreground">{items.length}</strong> productos solicitados en el período</span
      >
      <span
        >Cuenta solicitudes enviadas, incluso si fueron rechazadas; excluye borradores y canceladas.</span
      >
    </div>
  </Card>

  {#if !canRead}
    <Card class="p-6 text-sm text-foreground-muted">
      Necesitas el permiso de lectura de solicitudes de compra para consultar estos datos.
    </Card>
  {:else if error}
    <div role="alert">
      <Card class="border border-danger/30 bg-danger/5 p-5 text-sm text-danger">{error}</Card>
    </div>
  {:else if notice}
    <div role="status">
      <Card class="border border-success/30 bg-success/5 p-4 text-sm text-success">{notice}</Card>
    </div>
  {/if}

  {#if canRead}
    {#if loading}
      <Card class="p-8 text-center text-sm text-foreground-muted"
        >Cargando solicitudes de esta sucursal…</Card
      >
    {:else if !error && items.length === 0}
      <Card class="p-8 text-center">
        <h3 class="font-semibold text-foreground">Todavía no hay demanda en este período</h3>
        <p class="mt-1 text-sm text-foreground-muted">
          Prueba con un período más amplio o revisa las solicitudes de compra de la sucursal.
        </p>
      </Card>
    {:else if !error}
      <Card class="overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full min-w-[900px] text-left text-sm">
            <thead
              class="border-b border-border bg-surface-muted/40 text-[10px] uppercase tracking-wider text-foreground-subtle"
            >
              <tr>
                <th class="px-5 py-3 font-bold">Producto</th>
                <th class="px-4 py-3 font-bold">Solicitudes</th>
                <th class="px-4 py-3 font-bold">Cantidad solicitada por unidad</th>
                <th class="px-4 py-3 font-bold">Última solicitud</th>
                <th class="px-5 py-3 font-bold">Nivel manual</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each items as item (item.product_id)}
                <tr class="align-top">
                  <td class="px-5 py-4">
                    <p class="font-semibold text-foreground">{item.product_name}</p>
                    <p class="mt-1 font-mono text-xs text-foreground-muted">{item.sku}</p>
                  </td>
                  <td class="px-4 py-4 text-foreground">{item.request_count}</td>
                  <td class="px-4 py-4">
                    {#if item.unit_totals.length}
                      <ul class="space-y-1">
                        {#each item.unit_totals as total (`${item.product_id}-${total.unit_id}`)}
                          <li class="text-foreground">
                            {formatQuantity(total.quantity)}
                            <span class="text-foreground-muted"
                              >{total.unit_name} ({total.unit_symbol})</span
                            >
                          </li>
                        {/each}
                      </ul>
                    {:else}
                      <span class="text-foreground-muted">Sin cantidad registrada</span>
                    {/if}
                  </td>
                  <td class="px-4 py-4 text-foreground-muted"
                    >{formatDate(item.last_requested_at)}</td
                  >
                  <td class="px-5 py-4">
                    {#if canManage}
                      <div class="flex items-center gap-2">
                        <select
                          class="min-h-9 rounded-md border border-border bg-surface px-2.5 text-sm text-foreground"
                          aria-label="Nivel manual de demanda para {item.product_name}"
                          value={drafts[item.product_id] ?? item.demand_level ?? ''}
                          onchange={(event) =>
                            changedLevel(item.product_id, event.currentTarget.value)}
                        >
                          <option value="">Sin clasificar</option>
                          <option value="low">Baja</option>
                          <option value="medium">Media</option>
                          <option value="high">Alta</option>
                        </select>
                        {#if hasUnsavedChange(item)}
                          <button
                            type="button"
                            class="min-h-9 rounded-md border border-primary/40 px-3 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-50"
                            disabled={savingProductId === item.product_id}
                            onclick={() => saveLevel(item)}
                          >
                            {savingProductId === item.product_id ? 'Guardando…' : 'Guardar'}
                          </button>
                        {/if}
                      </div>
                    {:else}
                      <span class="text-foreground-muted">
                        {item.demand_level === 'low'
                          ? 'Baja'
                          : item.demand_level === 'medium'
                            ? 'Media'
                            : item.demand_level === 'high'
                              ? 'Alta'
                              : 'Sin clasificar'}
                      </span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </Card>
    {/if}
  {/if}
</div>
