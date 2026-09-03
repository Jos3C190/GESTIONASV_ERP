<script lang="ts">
  interface Props {
    search: string;
    onsearch: (value: string) => void;
    sort: 'updated' | 'name' | 'expiry' | 'size';
    onsort: (value: 'updated' | 'name' | 'expiry' | 'size') => void;
    viewMode: 'grid' | 'table';
    onviewmode: (value: 'grid' | 'table') => void;
    filterCount?: number;
    filtersOpen?: boolean;
    onfilters: () => void;
  }

  let {
    search,
    onsearch,
    sort,
    onsort,
    viewMode,
    onviewmode,
    filterCount = 0,
    filtersOpen = false,
    onfilters
  }: Props = $props();
</script>

<div class="flex flex-col gap-3 rounded-2xl border border-border bg-surface-elevated p-3 shadow-soft lg:flex-row lg:items-center">
  <label class="relative min-w-0 flex-1" for="document-library-search">
    <span class="sr-only">Buscar documentos o carpetas</span>
    <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-muted" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
    <input
      id="document-library-search"
      value={search}
      oninput={(event) => onsearch((event.currentTarget as HTMLInputElement).value)}
      placeholder="Buscar en esta carpeta…"
      autocomplete="off"
      class="min-h-11 w-full rounded-xl border border-border bg-surface pl-10 pr-3 text-[13px] text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    />
  </label>

  <div class="flex flex-wrap items-center gap-2">
    <button
      type="button"
      class="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border px-3 text-xs font-medium text-foreground-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-foreground focus-visible:text-foreground"
      onclick={onfilters}
      aria-label={filterCount > 0 ? `Filtros, ${filterCount} activos` : 'Abrir filtros'}
      aria-expanded={filtersOpen}
      aria-controls="document-library-filters"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M7 12h10m-7 6h4" /></svg>
      Filtros
      {#if filterCount > 0}<span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/10 px-1.5 font-mono tabular-nums text-primary">{filterCount}</span>{/if}
    </button>

    <label class="sr-only" for="document-library-sort">Ordenar documentos</label>
    <select
      id="document-library-sort"
      value={sort}
      onchange={(event) => onsort((event.currentTarget as HTMLSelectElement).value as Props['sort'])}
      class="min-h-11 rounded-xl border border-border bg-surface px-3 text-xs text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    >
      <option value="updated">Más recientes</option>
      <option value="name">Nombre</option>
      <option value="expiry">Vencimiento</option>
      <option value="size">Tamaño</option>
    </select>

    <div class="flex min-h-11 rounded-xl border border-border p-1" role="group" aria-label="Vista de archivos">
      <button
        type="button"
        class="min-w-10 rounded-lg px-2 text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground {viewMode === 'grid' ? 'bg-surface-hover text-foreground' : ''}"
        aria-label="Vista de cuadrícula"
        aria-pressed={viewMode === 'grid'}
        onclick={() => onviewmode('grid')}
      >
        <svg class="mx-auto" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg>
      </button>
      <button
        type="button"
        class="min-w-10 rounded-lg px-2 text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground {viewMode === 'table' ? 'bg-surface-hover text-foreground' : ''}"
        aria-label="Vista de lista"
        aria-pressed={viewMode === 'table'}
        onclick={() => onviewmode('table')}
      >
        <svg class="mx-auto" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></svg>
      </button>
    </div>
  </div>
</div>
