<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { priceListsApi } from '$lib/api/price-lists';
  import {
    STATUS_LABELS,
    STATUS_TONES,
    counterpartPrice,
    formatDay,
    formatPrice,
    todayInElSalvador,
    validityText
  } from '$lib/features/price-lists/labels';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { ListedPrice, PriceEntry, PriceList } from '$lib/types/price-list';

  let { listId }: { listId: string } = $props();

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let priceList = $state<PriceList | null>(null);
  let rows = $state<ListedPrice[]>([]);
  let branches = $state<{ id: string; name: string }[]>([]);
  let search = $state('');
  let branchId = $state('');
  let day = $state(todayInElSalvador());
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  let editing = $state<ListedPrice | null>(null);
  let price = $state('');
  let validFrom = $state(todayInElSalvador());
  let scope = $state('');
  let saving = $state(false);
  let formError = $state<string | null>(null);

  let historyFor = $state<ListedPrice | null>(null);
  let history = $state<PriceEntry[]>([]);
  let historyError = $state<string | null>(null);

  const canManage = $derived(permissions.hasPermission('price_lists:manage'));
  const vatText = $derived(priceList?.prices_include_vat ? 'con IVA' : 'sin IVA');

  async function loadPrices() {
    loading = true;
    loadError = null;
    try {
      rows = await priceListsApi.prices(listId, { search, branch_id: branchId || null, on: day });
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los precios.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    priceListsApi.get(listId).then(
      (item) => (priceList = item),
      (cause) => (loadError = cause instanceof HttpError ? cause.message : 'Lista no encontrada.')
    );
    api.branches.list().then(
      (items) => (branches = items.map((b) => ({ id: b.id, name: b.name }))),
      () => (branches = [])
    );
    void loadPrices();
  });

  function onSearch(value: string) {
    search = value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadPrices(), 300);
  }

  function openEditor(row: ListedPrice) {
    editing = row;
    price = row.current ? Number(row.current.price).toString() : '';
    validFrom = todayInElSalvador();
    scope = branchId;
    formError = null;
  }

  async function savePrice(event: SubmitEvent) {
    event.preventDefault();
    if (!editing) return;
    saving = true;
    formError = null;
    try {
      await priceListsApi.setPrice(listId, {
        product_id: editing.unit.product_id,
        variant_id: editing.unit.variant_id,
        unit_id: editing.unit.unit_id,
        branch_id: scope || null,
        price: String(price),
        valid_from: validFrom
      });
      editing = null;
      await loadPrices();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar el precio.';
    } finally {
      saving = false;
    }
  }

  async function openHistory(row: ListedPrice) {
    historyFor = row;
    historyError = null;
    history = [];
    try {
      history = await priceListsApi.history(listId, row.unit);
    } catch (cause) {
      historyError = cause instanceof HttpError ? cause.message : 'No se pudo cargar el historial.';
    }
  }

  function cancelEntry(entry: PriceEntry) {
    confirmation.request({
      kind: 'delete',
      title: 'Anular precio programado',
      description: `El precio de ${formatPrice(entry.price)} que iba a regir desde el ${formatDay(entry.valid_from)} se elimina y el anterior sigue vigente.`,
      confirmLabel: 'Anular',
      execute: async () => {
        await priceListsApi.cancelPrice(entry.id);
        if (historyFor) await openHistory(historyFor);
        await loadPrices();
      }
    });
  }

  function endEntry(entry: PriceEntry) {
    confirmation.request({
      kind: 'confirm',
      title: 'Terminar precio hoy',
      description: entry.branch_id
        ? `Desde mañana ${entry.branch_name ?? 'la sucursal'} vuelve al precio general de la lista.`
        : 'Desde mañana el producto queda sin precio en esta lista hasta que fijes otro.',
      confirmLabel: 'Terminar',
      execute: async () => {
        await priceListsApi.endPrice(entry.id, todayInElSalvador());
        if (historyFor) await openHistory(historyFor);
        await loadPrices();
      }
    });
  }
</script>

<svelte:head>
  <title>{priceList ? priceList.name : 'Lista de precios'} | GestionaSV</title>
</svelte:head>

<div class="space-y-5">
  <header>
    <a
      href="/sales/price-lists"
      class="text-xs font-semibold uppercase tracking-wider text-primary hover:underline"
      >← Listas de precios</a
    >
    <div class="mt-1 flex flex-wrap items-center gap-2">
      <h1 class="page-title-echo text-2xl font-bold tracking-tight text-foreground">
        {priceList?.name ?? 'Lista de precios'}
      </h1>
      {#if priceList?.is_default}<Badge variant="primary">Predeterminada</Badge>{/if}
      {#if priceList && !priceList.is_active}<Badge variant="neutral">Inactiva</Badge>{/if}
    </div>
    {#if priceList}
      <p class="mt-1 text-sm text-foreground-muted">
        <span class="font-mono">{priceList.code}</span> · Precios {vatText}. Un precio nuevo rige
        desde la fecha que indiques; el anterior queda en el historial.
      </p>
    {/if}
  </header>

  <div class="grid gap-3 rounded-xl border border-border bg-surface-elevated p-4 md:grid-cols-3">
    <div>
      <label for="price-search" class={labelClass}>Buscar producto</label>
      <input
        id="price-search"
        value={search}
        oninput={(e) => onSearch(e.currentTarget.value)}
        placeholder="Nombre o código"
        class={inputClass}
      />
    </div>
    <div>
      <label for="price-branch" class={labelClass}>Sucursal</label>
      <select
        id="price-branch"
        value={branchId}
        onchange={(e) => {
          branchId = e.currentTarget.value;
          void loadPrices();
        }}
        class={inputClass}
      >
        <option value="">Precio general</option>
        {#each branches as branch (branch.id)}
          <option value={branch.id}>{branch.name}</option>
        {/each}
      </select>
    </div>
    <div>
      <label for="price-day" class={labelClass}>Precios al día</label>
      <input
        id="price-day"
        type="date"
        value={day}
        onchange={(e) => {
          day = e.currentTarget.value || todayInElSalvador();
          void loadPrices();
        }}
        class={inputClass}
      />
    </div>
  </div>

  <section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
    {#if loading}
      <div class="space-y-3 p-4" aria-busy="true">
        <p class="sr-only" role="status">Cargando precios…</p>
        <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
        <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
        <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
      </div>
    {:else if loadError}
      <div
        class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
        role="alert"
      >
        <span>{loadError}</span>
        <Button variant="secondary" size="sm" onclick={() => void loadPrices()}>Reintentar</Button>
      </div>
    {:else if rows.length === 0}
      <div class="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <span
          class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            class="h-6 w-6"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path
              d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <div>
          <p class="text-sm font-semibold text-foreground">
            {search ? 'Ningún producto coincide con la búsqueda.' : 'No hay productos para vender.'}
          </p>
          <p class="mt-1 max-w-md text-sm text-foreground-muted">
            {search
              ? 'Prueba con otro nombre o código.'
              : 'Aquí aparecen los productos activos, marcados como vendibles y con artículo de inventario.'}
          </p>
        </div>
        {#if search}
          <Button variant="secondary" onclick={() => onSearch('')}>Limpiar búsqueda</Button>
        {:else}
          <a
            href="/products"
            class="inline-flex min-h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-hover"
            >Ir a productos</a
          >
        {/if}
      </div>
    {:else}
      <div
        class="hidden grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-3 border-b border-border px-4 py-2 text-xs font-medium uppercase tracking-wide text-foreground-muted md:grid"
      >
        <span>Producto</span><span>Unidad</span><span>Precio {vatText}</span><span
          >Próximo cambio</span
        ><span class="sr-only">Acciones</span>
      </div>
      <ul class="divide-y divide-border">
        {#each rows as row (`${row.unit.product_id}-${row.unit.variant_id}-${row.unit.unit_id}`)}
          <li
            class="grid gap-2 px-4 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center md:gap-3"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-foreground">{row.unit.name}</p>
              <p class="font-mono text-xs text-foreground-muted">{row.unit.sku}</p>
            </div>
            <p class="text-sm text-foreground">
              {row.unit.unit_name}
              {#if !row.unit.is_base}
                <span class="block text-xs text-foreground-muted"
                  >{Number(row.unit.factor)} unidades base</span
                >
              {/if}
            </p>
            <div class="text-sm">
              {#if row.current}
                <p class="font-semibold tabular-nums text-foreground">
                  {formatPrice(row.current.price)}
                  {#if row.current.branch_id}<Badge variant="warning">Sucursal</Badge>{/if}
                </p>
                <p class="text-xs text-foreground-muted">
                  {priceList?.prices_include_vat ? 'Sin IVA' : 'Con IVA'}: {counterpartPrice(
                    row.current.price,
                    priceList?.prices_include_vat ?? true
                  )}
                </p>
              {:else}
                <p class="text-foreground-muted">Sin precio</p>
              {/if}
              {#if row.branch_overrides > 0 && !branchId}
                <p class="text-xs text-foreground-muted">
                  {row.branch_overrides}
                  {row.branch_overrides === 1 ? 'sucursal' : 'sucursales'} con precio propio
                </p>
              {/if}
            </div>
            <p class="text-sm text-foreground-muted">
              {#if row.next}
                <span class="font-medium tabular-nums text-foreground"
                  >{formatPrice(row.next.price)}</span
                >
                desde {formatDay(row.next.valid_from)}
              {:else}
                —
              {/if}
            </p>
            <div class="flex gap-2">
              {#if canManage}
                <Button variant="secondary" size="sm" onclick={() => openEditor(row)}>
                  {row.current ? 'Cambiar' : 'Fijar precio'}
                </Button>
              {/if}
              <Button variant="ghost" size="sm" onclick={() => void openHistory(row)}>
                Historial
              </Button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>

<Modal
  open={editing !== null}
  title={editing ? `Precio de ${editing.unit.name}` : ''}
  onclose={() => (editing = null)}
>
  {#if editing}
    <form class="space-y-4" onsubmit={savePrice}>
      {#if formError}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {formError}
        </p>
      {/if}
      <p class="text-sm text-foreground-muted">
        {editing.unit.unit_name} · precio {vatText}.
        {#if editing.current}
          Vigente: {formatPrice(editing.current.price)}
          {validityText(editing.current.valid_from, editing.current.valid_to)}.
        {/if}
      </p>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <label for="price-value" class={labelClass}>Precio (USD)</label>
          <input
            id="price-value"
            type="number"
            min="0"
            step="any"
            bind:value={price}
            required
            class="{inputClass} tabular-nums"
          />
          {#if price !== '' && Number(price) >= 0}
            <p class="mt-1 text-xs text-foreground-muted">
              {priceList?.prices_include_vat ? 'Sin IVA' : 'Con IVA'}: {counterpartPrice(
                String(price),
                priceList?.prices_include_vat ?? true
              )}
            </p>
          {/if}
        </div>
        <div>
          <label for="price-from" class={labelClass}>Rige desde</label>
          <input
            id="price-from"
            type="date"
            min={todayInElSalvador()}
            bind:value={validFrom}
            required
            class={inputClass}
          />
        </div>
      </div>
      <div>
        <label for="price-scope" class={labelClass}>Aplica a</label>
        <select
          id="price-scope"
          value={scope}
          onchange={(e) => (scope = e.currentTarget.value)}
          class={inputClass}
        >
          <option value="">Todas las sucursales (precio general)</option>
          {#each branches as branch (branch.id)}
            <option value={branch.id}>Solo {branch.name}</option>
          {/each}
        </select>
        <p class="mt-1 text-xs text-foreground-muted">
          El precio de una sucursal reemplaza al general solo en esa sucursal.
        </p>
      </div>
      <div class="flex justify-end gap-2 border-t border-border pt-4">
        <Button type="button" variant="ghost" onclick={() => (editing = null)}>Cancelar</Button>
        <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar precio'}</Button>
      </div>
    </form>
  {/if}
</Modal>

<Modal
  open={historyFor !== null}
  title={historyFor ? `Historial de ${historyFor.unit.name}` : ''}
  onclose={() => (historyFor = null)}
  size="lg"
>
  {#if historyError}
    <p class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert">
      {historyError}
    </p>
  {:else if history.length === 0}
    <p class="py-6 text-center text-sm text-foreground-muted">
      Este producto todavía no tiene precios en la lista.
    </p>
  {:else}
    <ul class="divide-y divide-border">
      {#each history as entry (entry.id)}
        <li class="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="text-sm">
            <p class="flex flex-wrap items-center gap-2 font-medium text-foreground">
              <span class="tabular-nums">{formatPrice(entry.price)}</span>
              <Badge variant={STATUS_TONES[entry.status]}>{STATUS_LABELS[entry.status]}</Badge>
              <span class="font-normal text-foreground-muted">
                {entry.branch_name ?? 'Todas las sucursales'}
              </span>
            </p>
            <p class="text-foreground-muted">
              {validityText(entry.valid_from, entry.valid_to)}
              {#if entry.created_by_name}· {entry.created_by_name}{/if}
            </p>
          </div>
          {#if canManage}
            {#if entry.status === 'scheduled'}
              <Button variant="ghost" size="sm" onclick={() => cancelEntry(entry)}>Anular</Button>
            {:else if entry.status === 'current' && !entry.valid_to}
              <Button variant="ghost" size="sm" onclick={() => endEntry(entry)}>Terminar hoy</Button
              >
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</Modal>
