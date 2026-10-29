<script lang="ts">
  import { onDestroy } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { inventoryAdjustmentsApi, type AdjustmentItemOption } from '../adjustments';

  interface Props {
    id: string;
    warehouseId: string;
    warehouseName: string;
    selected: AdjustmentItemOption | null;
    disabled?: boolean;
    onselect: (item: AdjustmentItemOption) => void;
    searchItems?: typeof inventoryAdjustmentsApi.searchItems;
    purpose?: string;
  }

  let {
    id,
    warehouseId,
    warehouseName,
    selected,
    disabled = false,
    onselect,
    searchItems = inventoryAdjustmentsApi.searchItems,
    purpose = 'el ajuste'
  }: Props = $props();
  let open = $state(false);
  let dialog = $state<HTMLDialogElement | null>(null);
  let searchInput = $state<HTMLInputElement | null>(null);
  let query = $state('');
  let requestedOffset = $state(0);
  let options = $state<AdjustmentItemOption[]>([]);
  let total = $state(0);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let retry = $state(0);
  let sequence = 0;
  const pageSize = 20;
  const focusClass =
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground';
  const buttonClass = `min-h-11 rounded-lg border border-foreground/50 px-3 py-2 text-sm font-medium hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50 ${focusClass}`;

  function openPicker() {
    if (disabled || !warehouseId) return;
    query = '';
    requestedOffset = 0;
    open = true;
  }

  function choose(item: AdjustmentItemOption) {
    if (loading || disabled || !warehouseId) return;
    open = false;
    if (item.id === selected?.id) return;
    onselect(item);
  }

  function focusResult(index: number) {
    const buttons = dialog?.querySelectorAll<HTMLButtonElement>('[data-adjustment-product]');
    if (!buttons?.length) return;
    const next = Math.max(0, Math.min(index, buttons.length - 1));
    buttons[next]?.focus();
    buttons[next]?.scrollIntoView({ block: 'nearest' });
  }

  $effect(() => {
    if (disabled || !warehouseId) open = false;
  });

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      searchInput?.focus();
    } else if (!open && dialog.open) dialog.close();
  });

  $effect(() => {
    const warehouse = warehouseId;
    const search = query.trim();
    const offset = requestedOffset;
    const shouldLoad = open && !disabled && Boolean(warehouse);
    void retry;
    const request = ++sequence;
    options = [];
    total = 0;
    error = null;
    loading = shouldLoad;
    if (!shouldLoad) return;

    const timer = setTimeout(
      async () => {
        try {
          const result = await searchItems(warehouse, search, offset);
          if (request !== sequence) return;
          options = result.items;
          total = result.items_total ?? result.items.length;
        } catch (cause) {
          if (request !== sequence) return;
          error =
            cause instanceof HttpError && [403, 404].includes(cause.status)
              ? cause.message
              : 'No se pudieron cargar los productos. Revisa la conexión y vuelve a intentarlo.';
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
  <label for={id} class="mb-1 block text-sm font-medium text-foreground">Artículo</label>
  <button
    {id}
    type="button"
    class={`flex min-h-14 w-full items-center gap-3 rounded-xl border border-foreground/50 bg-surface px-3 py-2 text-left text-foreground hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50 ${focusClass}`}
    disabled={disabled || !warehouseId}
    aria-haspopup="dialog"
    aria-expanded={open}
    aria-controls={`${id}-dialog`}
    onclick={openPicker}
  >
    <svg
      class="shrink-0 text-foreground-muted"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg
    >
    <span class="min-w-0 flex-1">
      <span class="block break-words text-sm font-medium"
        >{selected?.product_name ?? 'Buscar producto'}</span
      >
      <span class="mt-0.5 block break-words text-xs text-foreground-muted"
        >{selected
          ? `${selected.sku ?? 'Sin SKU'} · ${selected.base_unit_symbol ?? selected.base_unit_name ?? 'Unidad base'}`
          : 'Por nombre o SKU, por ejemplo Azúcar o PRD-AZU-004'}</span
      >
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
  id={`${id}-dialog`}
  class="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-foreground shadow-floating backdrop:bg-black/60"
  aria-labelledby={`${id}-title`}
  aria-describedby={`${id}-context`}
  oncancel={(event) => {
    event.preventDefault();
    open = false;
  }}
  onclose={() => {
    if (!dialog?.open) open = false;
  }}
>
  <header class="flex items-start justify-between gap-3 border-b border-border p-4 sm:p-5">
    <div class="min-w-0">
      <h2 id={`${id}-title`} class="text-lg font-semibold">Buscar producto para {purpose}</h2>
      <p id={`${id}-context`} class="mt-1 break-words text-sm text-foreground-muted">
        {warehouseName}
      </p>
    </div>
    <button
      type="button"
      class={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg hover:bg-surface-hover ${focusClass}`}
      aria-label="Cerrar búsqueda de productos"
      onclick={() => (open = false)}
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

  <div class="space-y-3 px-4 py-4 sm:px-5">
    <label for={`${id}-query`} class="block text-sm font-medium">Nombre o SKU</label>
    <input
      bind:this={searchInput}
      id={`${id}-query`}
      value={query}
      type="search"
      maxlength="120"
      autocomplete="off"
      spellcheck="false"
      placeholder="Ej. Azúcar, premium o PRD-AZU-004"
      class={`h-12 w-full rounded-lg border border-foreground/50 bg-surface px-3 text-base placeholder:text-foreground-muted ${focusClass}`}
      oninput={(event) => {
        query = event.currentTarget.value;
        requestedOffset = 0;
      }}
      onkeydown={(event) => {
        if (event.key === 'ArrowDown' && !loading) {
          event.preventDefault();
          focusResult(0);
        }
        if (event.key === 'Enter') {
          event.preventDefault();
          if (!loading && !error && options.length === 1) choose(options[0]!);
        }
      }}
    />
    <p class="text-xs text-foreground-muted">
      Puedes escribir parte del nombre o combinar palabras. La búsqueda admite nombres con o sin
      tildes.
    </p>
    <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
      <h3 class="font-semibold">
        {query.trim() ? 'Resultados de búsqueda' : 'Catálogo de productos'}
      </h3>
      <span class="text-foreground-muted"
        >{loading
          ? 'Buscando…'
          : error
            ? 'Consulta pendiente'
            : `${total.toLocaleString('es-SV')} productos encontrados`}</span
      >
    </div>
    <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {loading
        ? 'Buscando productos.'
        : error
          ? error
          : `${total} productos encontrados. ${options.length} en esta página.`}
    </p>
  </div>

  <div
    class="max-h-[45dvh] overflow-y-auto border-y border-border px-2 py-1 sm:px-3"
    aria-busy={loading}
  >
    {#if loading}
      <div class="space-y-3 p-3">
        <span class="sr-only">Buscando productos</span>
        <div class="skeleton h-20 rounded-lg"></div>
        <div class="skeleton h-20 rounded-lg"></div>
      </div>
    {:else if error}
      <div class="space-y-3 p-4">
        <p role="alert" class="text-sm">{error}</p>
        <button
          type="button"
          class={buttonClass}
          onclick={() => {
            searchInput?.focus();
            retry += 1;
          }}>Reintentar búsqueda</button
        >
      </div>
    {:else if options.length === 0}
      <div class="space-y-3 px-4 py-8 text-center">
        <svg
          class="mx-auto text-foreground-muted"
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg
        >
        <p class="text-sm font-semibold">
          {query.trim()
            ? 'No encontramos productos con esa búsqueda'
            : 'No hay productos activos para seleccionar'}
        </p>
        <p class="text-sm text-foreground-muted">
          {query.trim()
            ? 'Prueba con menos palabras o con el SKU del producto.'
            : 'Revisa que el producto tenga inventario configurado en esta empresa.'}
        </p>
        {#if query.trim() || requestedOffset > 0}<button
            type="button"
            class={buttonClass}
            onclick={() => {
              query = '';
              requestedOffset = 0;
              searchInput?.focus();
            }}>Ver catálogo</button
          >{/if}
      </div>
    {:else}
      <ul class="divide-y divide-border">
        {#each options as item, index (item.id)}
          <li>
            <button
              type="button"
              data-adjustment-product
              class={`my-1 flex min-h-20 w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-surface-hover ${focusClass}`}
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
              <span class="min-w-0 flex-1"
                ><span class="block break-words text-sm font-semibold">{item.product_name}</span
                ><span class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs"
                  ><span class="break-all font-mono">{item.sku ?? 'Sin SKU'}</span><span
                    class="text-foreground-muted"
                    >Unidad: {item.base_unit_name ?? item.base_unit_symbol ?? 'Unidad base'}</span
                  ></span
                ></span
              >
              {#if item.id === selected?.id}<span
                  class="shrink-0 rounded-md bg-surface-muted px-2 py-1 text-xs">Seleccionado</span
                >{/if}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
  <footer class="space-y-3 p-4 sm:px-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <span class="text-xs text-foreground-muted"
        >{loading || error || total === 0
          ? 'Hasta 20 productos por página'
          : `${requestedOffset + 1}–${requestedOffset + options.length} de ${total.toLocaleString('es-SV')}`}</span
      >
      <div class="flex gap-2">
        <button
          type="button"
          class={buttonClass}
          disabled={loading || Boolean(error) || requestedOffset === 0}
          onclick={() => (requestedOffset = Math.max(0, requestedOffset - pageSize))}
          aria-label="Página anterior de productos">Anterior</button
        >
        <button
          type="button"
          class={buttonClass}
          disabled={loading || Boolean(error) || requestedOffset + options.length >= total}
          onclick={() => (requestedOffset += pageSize)}
          aria-label="Página siguiente de productos">Siguiente</button
        >
      </div>
    </div>
    <p class="text-xs text-foreground-muted">
      Selecciona el producto para continuar. Escape cierra la búsqueda.
    </p>
  </footer>
</dialog>
