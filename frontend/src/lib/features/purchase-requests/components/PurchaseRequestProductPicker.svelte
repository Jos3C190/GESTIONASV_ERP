<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import type { Product } from '$lib/types/catalog';

  interface Props {
    id: string;
    label: string;
    value: string;
    query: string;
    products: Product[];
    hasMoreProducts?: boolean;
    loadingMoreProducts?: boolean;
    loadMoreError?: string | null;
    error?: string;
    onselect?: () => void;
    onloadmore?: () => void;
  }

  let {
    id,
    label,
    value = $bindable(''),
    query = $bindable(''),
    products,
    hasMoreProducts = false,
    loadingMoreProducts = false,
    loadMoreError = null,
    error,
    onselect,
    onloadmore
  }: Props = $props();

  const normalizeSearch = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('es');

  let remoteProducts = $state<Product[]>([]);
  let remoteTotal = $state(0);
  let remotePage = $state(0);
  let remotePages = $state(0);
  let remoteLoading = $state(false);
  let remoteError = $state<string | null>(null);
  let failedRemotePage = $state(1);
  let recentlySelectedProduct = $state<Product | null>(null);
  let fetchedSelectedProduct = $state<Product | null>(null);
  let selectedProductLoading = $state(false);
  let selectedProductLookupError = $state(false);
  let selectedProductLookupRetry = $state(0);
  let searchRequestGeneration = 0;
  let selectedProductRequestGeneration = 0;

  let searchText = $derived(query.trim());
  let usesRemoteSearch = $derived(searchText.length >= 2);
  let normalizedQuery = $derived(normalizeSearch(query.trim()));
  const matchesQuery = (product: Product) => {
    const searchableText = normalizeSearch(
      [product.sku, product.name, product.original_code, product.internal_code]
        .filter(Boolean)
        .join(' ')
    );

    return searchableText.includes(normalizedQuery);
  };
  let selectedProduct = $derived(
    products.find((product) => String(product.id_product) === value) ??
      remoteProducts.find((product) => String(product.id_product) === value) ??
      (recentlySelectedProduct && String(recentlySelectedProduct.id_product) === value
        ? recentlySelectedProduct
        : fetchedSelectedProduct && String(fetchedSelectedProduct.id_product) === value
          ? fetchedSelectedProduct
          : null)
  );
  let localProducts = $derived(
    selectedProduct &&
      !products.some((product) => product.id_product === selectedProduct.id_product)
      ? [selectedProduct, ...products]
      : products
  );
  let localFilteredProducts = $derived(localProducts.filter(matchesQuery));
  let filteredProducts = $derived(
    (usesRemoteSearch ? remoteProducts : localProducts).filter(matchesQuery)
  );

  async function searchProducts(search: string, page: number, generation: number, append: boolean) {
    remoteLoading = true;
    remoteError = null;

    try {
      const response = await catalogApi.listProducts({
        active_only: true,
        search: search.slice(0, 100),
        page,
        size: 100
      });

      if (generation !== searchRequestGeneration) return;

      const knownProductIds = new Set(remoteProducts.map((product) => product.id_product));
      const matchingProducts = response.items.filter(
        (product) => product.can_purchase !== false && !knownProductIds.has(product.id_product)
      );
      remoteProducts = append ? [...remoteProducts, ...matchingProducts] : matchingProducts;
      remoteTotal = response.meta.total;
      remotePage = response.meta.page;
      remotePages = response.meta.pages;
    } catch (err: unknown) {
      if (generation !== searchRequestGeneration) return;

      failedRemotePage = page;
      remoteError =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo buscar en el catálogo.';
    } finally {
      if (generation === searchRequestGeneration) remoteLoading = false;
    }
  }

  $effect(() => {
    const search = searchText;
    const generation = ++searchRequestGeneration;
    remoteProducts = [];
    remoteTotal = 0;
    remotePage = 0;
    remotePages = 0;
    remoteLoading = false;
    remoteError = null;
    failedRemotePage = 1;

    if (search.length < 2) return;

    remoteLoading = true;
    const timeout = setTimeout(() => {
      void searchProducts(search, 1, generation, false);
    }, 250);

    return () => clearTimeout(timeout);
  });

  $effect(() => {
    const selectedId = Number(value);
    const cachedSelection =
      products.some((product) => product.id_product === selectedId) ||
      remoteProducts.some((product) => product.id_product === selectedId) ||
      recentlySelectedProduct?.id_product === selectedId;

    const retryVersion = selectedProductLookupRetry;

    if (!Number.isSafeInteger(selectedId) || selectedId <= 0) {
      fetchedSelectedProduct = null;
      selectedProductLoading = false;
      selectedProductLookupError = false;
      return;
    }

    if (fetchedSelectedProduct?.id_product === selectedId) {
      selectedProductLoading = false;
      return;
    }

    if (cachedSelection) {
      fetchedSelectedProduct = null;
      selectedProductLoading = false;
      selectedProductLookupError = false;
      return;
    }

    const generation = ++selectedProductRequestGeneration;
    let isCurrent = true;
    fetchedSelectedProduct = null;
    selectedProductLoading = true;
    selectedProductLookupError = false;

    void catalogApi
      .getProduct(selectedId)
      .then((product) => {
        if (
          isCurrent &&
          retryVersion === selectedProductLookupRetry &&
          generation === selectedProductRequestGeneration
        ) {
          fetchedSelectedProduct = product;
        }
      })
      .catch(() => {
        if (
          isCurrent &&
          retryVersion === selectedProductLookupRetry &&
          generation === selectedProductRequestGeneration
        ) {
          selectedProductLookupError = true;
        }
      })
      .finally(() => {
        if (
          isCurrent &&
          retryVersion === selectedProductLookupRetry &&
          generation === selectedProductRequestGeneration
        ) {
          selectedProductLoading = false;
        }
      });

    return () => {
      isCurrent = false;
    };
  });

  function focusProduct(product: Product | undefined) {
    if (product) document.getElementById(`${id}-option-${product.id_product}`)?.focus();
  }

  function handleSearchKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowDown' && filteredProducts.length > 0 && !remoteLoading) {
      event.preventDefault();
      focusProduct(filteredProducts[0]);
    } else if (event.key === 'Enter' && filteredProducts.length === 1 && !remoteLoading) {
      event.preventDefault();
      const product = filteredProducts[0];
      if (product) selectProduct(product);
    }
  }

  function handleProductKeydown(event: KeyboardEvent, index: number) {
    if (event.key === 'ArrowDown' && filteredProducts.length > 0) {
      event.preventDefault();
      focusProduct(filteredProducts[(index + 1) % filteredProducts.length]);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (index === 0) {
        document.getElementById(`${id}-search`)?.focus();
      } else {
        focusProduct(filteredProducts[index - 1]);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      document.getElementById(`${id}-search`)?.focus();
    } else if (event.key === 'Enter') {
      const product = filteredProducts[index];
      if (product) {
        event.preventDefault();
        selectProduct(product);
      }
    }
  }

  function loadMoreRemoteProducts() {
    if (remoteLoading || remotePage >= remotePages) return;
    void searchProducts(searchText, remotePage + 1, searchRequestGeneration, true);
  }

  function retryRemoteSearch() {
    if (remoteLoading || !remoteError) return;
    void searchProducts(
      searchText,
      failedRemotePage,
      searchRequestGeneration,
      failedRemotePage > 1
    );
  }

  function retrySelectedProductLookup() {
    selectedProductLookupRetry += 1;
    fetchedSelectedProduct = null;
    selectedProductLookupError = false;
  }

  function selectProduct(product: Product) {
    recentlySelectedProduct = product;
    value = String(product.id_product);
    query = '';
    onselect?.();
  }
</script>

<div class="min-w-0 space-y-2">
  <label for={`${id}-search`} class="mb-1 block text-sm font-medium text-foreground">
    {label} <span class="text-danger">*</span>
  </label>

  {#if selectedProduct}
    <div
      class="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-primary/40 bg-primary/5 px-3 py-2"
      aria-live="polite"
    >
      <span
        class="rounded border border-primary/30 bg-surface px-1.5 py-0.5 text-xs font-semibold text-primary"
      >
        Seleccionado
      </span>
      <span class="font-mono text-xs text-foreground-muted">{selectedProduct.sku}</span>
      <span class="min-w-0 text-sm font-medium text-foreground">{selectedProduct.name}</span>
    </div>
  {:else if value}
    <div
      class="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-foreground"
      role={selectedProductLookupError ? 'alert' : 'status'}
    >
      <span class="rounded border border-border bg-surface px-1.5 py-0.5 text-xs font-semibold">
        Producto guardado
      </span>
      <span class="font-mono text-xs text-foreground-muted">ID {value}</span>
      <span class="text-xs text-foreground-muted">
        {#if selectedProductLoading}
          Cargando su descripción…
        {:else if selectedProductLookupError}
          No se pudo cargar el nombre del producto.
        {/if}
      </span>
      {#if selectedProductLookupError}
        <button
          type="button"
          class="min-h-9 rounded px-2 text-xs font-medium text-foreground underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          onclick={retrySelectedProductLookup}
        >
          Reintentar
        </button>
      {/if}
    </div>
  {/if}

  <input
    id={`${id}-search`}
    aria-label={label}
    aria-invalid={error ? 'true' : undefined}
    aria-describedby={error ? `${id}-hint ${id}-error` : `${id}-hint`}
    aria-required="true"
    aria-controls={`${id}-results`}
    type="search"
    autocomplete="off"
    maxlength="100"
    bind:value={query}
    placeholder="Buscar por SKU, nombre o código"
    onkeydown={handleSearchKeydown}
    class="h-11 w-full min-w-0 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
  />
  <p
    id={`${id}-hint`}
    class="text-xs text-foreground-muted"
    role="status"
    aria-live="polite"
    aria-atomic="true"
  >
    {#if usesRemoteSearch}
      {#if remoteLoading}
        Buscando coincidencias en todo el catálogo…
      {:else}
        El catálogo encontró {remoteTotal}
        {remoteTotal === 1 ? 'coincidencia' : 'coincidencias'}; se muestran los productos
        disponibles para compra.
      {/if}
    {:else if searchText}
      {localFilteredProducts.length}
      {localFilteredProducts.length === 1 ? 'coincidencia' : 'coincidencias'} entre los productos cargados.
      Escribe 2 caracteres para buscar en todo el catálogo.
    {:else}
      Selecciona un producto de la lista o busca por SKU, nombre o código. {products.length}
      {products.length === 1 ? 'producto cargado' : 'productos cargados'}.
    {/if}
  </p>

  {#if usesRemoteSearch && remoteError}
    <p
      class="rounded-md border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-foreground"
      role="alert"
    >
      No se pudo completar la búsqueda: {remoteError}
    </p>
  {/if}

  {#if filteredProducts.length > 0}
    <ul
      aria-label={`Productos disponibles para ${label}`}
      id={`${id}-results`}
      class="m-0 max-h-60 list-none space-y-1 overflow-y-auto rounded-md border border-border bg-surface p-1"
    >
      {#each filteredProducts as product, productIndex (product.id_product)}
        {@const productId = String(product.id_product)}
        <li>
          <button
            id={`${id}-option-${product.id_product}`}
            type="button"
            aria-label={`Seleccionar ${product.sku} — ${product.name}`}
            aria-pressed={value === productId}
            onclick={() => selectProduct(product)}
            onkeydown={(event) => handleProductKeydown(event, productIndex)}
            class="flex min-h-11 w-full min-w-0 items-center gap-3 rounded px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {value ===
            productId
              ? 'bg-primary/10 ring-1 ring-primary/40'
              : ''}"
          >
            <span class="max-w-32 shrink-0 truncate font-mono text-xs text-foreground-muted"
              >{product.sku}</span
            >
            <span class="min-w-0 flex-1 break-words">{product.name}</span>
            {#if value === productId}
              <span class="shrink-0 text-primary" aria-hidden="true">✓</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  {:else}
    <p
      class="rounded-md border border-border bg-surface-muted px-3 py-4 text-sm text-foreground-muted"
    >
      {#if usesRemoteSearch}
        {#if remoteLoading}
          Cargando coincidencias del catálogo…
        {:else}
          No hay productos disponibles para compra que coincidan en el catálogo.
        {/if}
      {:else if products.length === 0}
        No hay productos disponibles para compra.
      {:else if searchText}
        {#if usesRemoteSearch && remoteError}
          La búsqueda no está disponible. Puedes reintentarla desde el botón.
        {:else}
          No hay coincidencias entre los productos cargados. Escribe 2 caracteres para buscar en
          todo el catálogo.
        {/if}
      {:else}
        No hay más resultados cargados.
      {/if}
    </p>
  {/if}

  {#if usesRemoteSearch && (remoteError || remotePage < remotePages)}
    <button
      type="button"
      class="min-h-11 w-full rounded-md border border-border bg-surface-muted px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-wait disabled:opacity-60"
      onclick={remoteError ? retryRemoteSearch : loadMoreRemoteProducts}
      disabled={remoteLoading}
    >
      {remoteLoading
        ? 'Buscando…'
        : remoteError
          ? 'Reintentar búsqueda'
          : 'Cargar más coincidencias'}
    </button>
  {/if}

  {#if !usesRemoteSearch && hasMoreProducts}
    {#if loadMoreError}
      <p
        class="rounded-md border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-foreground"
        role="alert"
      >
        No se pudieron cargar más productos: {loadMoreError}
      </p>
    {/if}
    <button
      type="button"
      class="min-h-11 w-full rounded-md border border-border bg-surface-muted px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-wait disabled:opacity-60"
      onclick={onloadmore}
      disabled={loadingMoreProducts}
    >
      {loadingMoreProducts
        ? 'Cargando…'
        : loadMoreError
          ? 'Reintentar carga de productos'
          : 'Mostrar los siguientes 100 productos'}
    </button>
  {/if}

  {#if error}
    <p id={`${id}-error`} class="text-xs text-danger" role="alert">{error}</p>
  {/if}
</div>
