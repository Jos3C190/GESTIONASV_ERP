<script lang="ts">
  import { onDestroy } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { kardexApi, kardexErrorMessage, type KardexItemOption } from '../kardex';

  interface Props {
    warehouseId: string;
    warehouseName: string;
    selected: KardexItemOption | null;
    disabled?: boolean;
    onselect: (item: KardexItemOption) => void;
  }

  let { warehouseId, warehouseName, selected, disabled = false, onselect }: Props = $props();
  let open = $state(false);
  let dialog = $state<HTMLDialogElement | null>(null);
  let searchInput = $state<HTMLInputElement | null>(null);
  let query = $state('');
  let options = $state<KardexItemOption[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let retryVersion = $state(0);
  let sequence = 0;

  function openPicker() {
    if (disabled || !warehouseId) return;
    query = '';
    open = true;
  }

  function choose(item: KardexItemOption) {
    if (loading || disabled) return;
    open = false;
    onselect(item);
  }

  function retrySearch() {
    searchInput?.focus();
    retryVersion += 1;
  }

  function movementDate(value: string | null | undefined): string {
    if (!value) return 'Con existencias · sin movimiento registrado';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Fecha de movimiento no disponible';
    return `Último movimiento: ${new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(date)}`;
  }

  function focusResult(index: number) {
    const results = dialog?.querySelectorAll<HTMLButtonElement>('[data-product-result]');
    if (!results?.length) return;
    const next = Math.max(0, Math.min(index, results.length - 1));
    results[next]?.focus();
    results[next]?.scrollIntoView({ block: 'nearest' });
  }

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      searchInput?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });

  $effect(() => {
    const warehouse = warehouseId;
    const search = query.trim();
    const isOpen = open;
    const blocked = disabled;
    void retryVersion;
    const request = ++sequence;
    options = [];
    error = null;
    const shouldLoad = isOpen && !blocked && Boolean(warehouse);
    loading = shouldLoad;
    if (!shouldLoad) return;

    const timer = setTimeout(
      async () => {
        try {
          const result = await kardexApi.searchItems(warehouse, search);
          if (request === sequence) options = result;
        } catch (cause) {
          if (request === sequence)
            error = kardexErrorMessage(
              cause,
              'No se pudieron cargar los productos. Vuelve a intentarlo.'
            );
        } finally {
          if (request === sequence) loading = false;
        }
      },
      search ? 200 : 0
    );

    return () => {
      clearTimeout(timer);
      sequence += 1;
    };
  });

  onDestroy(() => {
    sequence += 1;
    dialog?.close();
  });
</script>

<div class="min-w-0">
  <label for="kardex-item" class="mb-1 block text-sm font-medium text-foreground">Producto</label>
  <button
    id="kardex-item"
    type="button"
    class="flex min-h-14 w-full items-center gap-3 rounded-lg border border-foreground/50 bg-surface px-3 py-2 text-left text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
    disabled={disabled || !warehouseId}
    aria-haspopup="dialog"
    aria-expanded={open}
    aria-controls="kardex-product-dialog"
    onclick={openPicker}
  >
    <svg
      class="shrink-0 text-foreground-muted"
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      aria-hidden="true"
    >
      <circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" />
    </svg>
    <span class="min-w-0 flex-1">
      <span class="block break-words text-sm font-medium"
        >{selected?.product_name ?? 'Seleccionar producto'}</span
      >
      <span class="mt-0.5 block break-words text-xs text-foreground-muted">
        {selected
          ? `${selected.sku ?? 'Sin SKU'} · ${selected.base_unit_symbol}`
          : 'Ver recientes o buscar por nombre y SKU'}
      </span>
    </span>
    <svg
      class="shrink-0 text-foreground-muted"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg
    >
  </button>
</div>

<dialog
  bind:this={dialog}
  id="kardex-product-dialog"
  class="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-foreground shadow-floating backdrop:bg-black/60"
  aria-labelledby="kardex-product-title"
  aria-describedby="kardex-product-warehouse"
  oncancel={(event) => {
    event.preventDefault();
    open = false;
  }}
  onclose={() => {
    if (!dialog?.open) open = false;
  }}
>
  <header class="flex items-start justify-between gap-3 border-b border-border p-4 sm:px-5">
    <div class="min-w-0">
      <h2 id="kardex-product-title" class="text-base font-semibold">Selecciona un producto</h2>
      <p id="kardex-product-warehouse" class="mt-1 break-words text-sm text-foreground-muted">
        {warehouseName}
      </p>
    </div>
    <button
      type="button"
      class="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-foreground-muted hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      aria-label="Cerrar selector de productos"
      onclick={() => {
        open = false;
      }}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg
      >
    </button>
  </header>
  <div class="p-4 sm:px-5">
    <label for="kardex-product-query" class="sr-only">Buscar por nombre, SKU o código interno</label
    >
    <div class="relative">
      <svg
        class="pointer-events-none absolute left-3 top-3.5 text-foreground-muted"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg
      >
      <input
        bind:this={searchInput}
        bind:value={query}
        id="kardex-product-query"
        type="search"
        maxlength="120"
        autocomplete="off"
        spellcheck="false"
        placeholder="Ej. Azúcar, PRD-AZU-004 o código interno"
        class="h-12 w-full rounded-lg border border-foreground/50 bg-surface pl-10 pr-3 text-sm placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        onkeydown={(event) => {
          if (event.key === 'ArrowDown' && !loading) {
            event.preventDefault();
            focusResult(0);
          }
          if (event.key === 'Enter' && !loading && options.length === 1) {
            event.preventDefault();
            choose(options[0]!);
          }
        }}
      />
    </div>
    <div class="mt-4 flex flex-wrap items-baseline justify-between gap-1">
      <h3 class="text-xs font-semibold text-foreground">
        {query.trim() ? 'Resultados de búsqueda' : 'Productos de esta bodega'}
      </h3>
      <span class="text-xs text-foreground-muted"
        >{query.trim()
          ? 'Nombre y SKU para identificar cada opción'
          : 'Movimientos más recientes primero'}</span
      >
    </div>
    <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {loading
        ? 'Cargando productos.'
        : error
          ? 'No se pudieron cargar los productos. Puedes reintentar.'
          : `${options.length} productos disponibles para seleccionar.`}
    </p>
  </div>

  <div
    class="max-h-[45dvh] overflow-y-auto border-y border-border px-2 py-1 sm:px-3"
    aria-busy={loading}
  >
    {#if loading}
      <div class="space-y-3 p-3">
        <p class="text-sm text-foreground-muted">
          {query.trim() ? 'Buscando productos…' : 'Cargando productos recientes…'}
        </p>
        <div class="skeleton h-16 rounded-lg"></div>
        <div class="skeleton h-16 rounded-lg"></div>
      </div>
    {:else if error}
      <div class="space-y-3 p-4">
        <p role="alert" class="text-sm text-foreground">{error}</p>
        <Button variant="secondary" onclick={retrySearch}>Reintentar</Button>
      </div>
    {:else if options.length === 0}
      <div role="status" class="space-y-2 p-6 text-center">
        <p class="text-sm font-medium">
          {query.trim()
            ? 'No encontramos ese producto en esta bodega'
            : 'Esta bodega aún no tiene productos para consultar'}
        </p>
        <p class="text-sm text-foreground-muted">
          {query.trim()
            ? 'Prueba con parte del nombre, el SKU o un código interno.'
            : 'Aparecerán al registrar existencias o movimientos.'}
        </p>
        {#if query.trim()}<Button
            variant="secondary"
            onclick={() => {
              query = '';
              searchInput?.focus();
            }}>Ver recientes</Button
          >{/if}
      </div>
    {:else}
      <ul class="divide-y divide-border">
        {#each options as item, index (item.inventory_item_id)}
          <li>
            <button
              type="button"
              data-product-result
              class="my-1 flex min-h-20 w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
              onclick={() => choose(item)}
              onkeydown={(event) => {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  focusResult(index + 1);
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  if (index === 0) searchInput?.focus();
                  else focusResult(index - 1);
                }
              }}
            >
              <span class="min-w-0 flex-1">
                <span class="block break-words text-sm font-medium">{item.product_name}</span>
                <span
                  class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-foreground-muted"
                  ><span class="break-all font-mono text-foreground">{item.sku ?? 'Sin SKU'}</span
                  ><span>Unidad: {item.base_unit_symbol}</span></span
                >
                <span class="mt-1 block text-xs text-foreground-muted"
                  >{movementDate(item.last_movement_at)}</span
                >
              </span>
              {#if item.inventory_item_id === selected?.inventory_item_id}<span
                  class="shrink-0 rounded-md border border-border bg-surface-muted px-2 py-1 text-xs text-foreground"
                  >Actual</span
                >{/if}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
  <footer
    class="flex flex-wrap justify-between gap-2 px-4 py-3 text-xs text-foreground-muted sm:px-5"
  >
    <span>Al seleccionar, se consultan sus movimientos.</span>
    <span
      >{options.length === 20
        ? 'Hasta 20 resultados · busca para acotar'
        : 'Escape para cerrar'}</span
    >
  </footer>
</dialog>
