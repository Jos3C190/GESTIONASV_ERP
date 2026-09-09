<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { DocumentCategoryOut } from '$lib/api/client';
  import type { ExplorerSort, ExplorerStatus, ExplorerView } from './types';
  import FilterSelect, { type ExplorerFilterOption } from './FilterSelect.svelte';

  interface Props {
    search: string;
    category: string;
    status: ExplorerStatus;
    sort: ExplorerSort;
    view: ExplorerView;
    categories: DocumentCategoryOut[];
    canCreateFolder: boolean;
    canUpload: boolean;
    onsearch: (value: string) => void;
    oncategory: (value: string) => void;
    onstatus: (value: ExplorerStatus) => void;
    onsort: (value: ExplorerSort) => void;
    onview: (value: ExplorerView) => void;
    oncreatefolder: () => void;
    onupload: () => void;
  }

  let {
    search,
    category,
    status,
    sort,
    view,
    categories,
    canCreateFolder,
    canUpload,
    onsearch,
    oncategory,
    onstatus,
    onsort,
    onview,
    oncreatefolder,
    onupload
  }: Props = $props();

  let searchValue = $state('');
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    searchValue = search;
  });

  function handleSearch(value: string) {
    searchValue = value;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      if (searchValue === value) onsearch(value);
    }, 250);
  }

  function clearSearch() {
    searchValue = '';
    if (searchTimer) clearTimeout(searchTimer);
    onsearch('');
  }

  let categoryOptions = $derived<ExplorerFilterOption[]>([
    { value: '', label: 'Todas' },
    ...categories
      .filter((item) => item.is_active)
      .map((item) => ({ value: item.id, label: item.name }))
  ]);

  const statusOptions: ExplorerFilterOption[] = [
    { value: '', label: 'Todos' },
    { value: 'active', label: 'Activos' },
    { value: 'processing', label: 'Procesando' },
    { value: 'deleted', label: 'En papelera' }
  ];

  const sortOptions: ExplorerFilterOption[] = [
    { value: 'name', label: 'Nombre' },
    { value: 'updated', label: 'Modificado' },
    { value: 'size', label: 'Tamaño' }
  ];
</script>

<div class="explorer-toolbar">
  <div class="explorer-filterbar">
    <div class="explorer-search-wrap" role="search">
      <label class="relative min-w-0 flex-1">
        <span class="sr-only">Buscar en Documentos generales</span>
        <svg
          class="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-subtle"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        ><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
        <input
          value={searchValue}
          oninput={(event) => handleSearch((event.currentTarget as HTMLInputElement).value)}
          placeholder="Buscar en General"
          class="explorer-search-input h-11 w-full rounded-lg border border-border bg-surface px-3 pl-10 pr-16 text-sm text-foreground outline-none transition placeholder:text-foreground-subtle focus:border-primary focus:ring-2 focus:ring-primary/20"
          autocomplete="off"
        />
        <span class="explorer-search-shortcut" aria-hidden="true">Ctrl K</span>
        {#if searchValue}
          <button type="button" class="explorer-search-clear" aria-label="Limpiar búsqueda" onclick={clearSearch}>
            <span aria-hidden="true">×</span>
          </button>
        {/if}
      </label>
    </div>

    <div class="explorer-commandbar-actions">
      {#if canCreateFolder}
        <Button variant="secondary" size="sm" class="min-h-10" onclick={oncreatefolder}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
            <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M12 11v5M9.5 13.5h5" />
          </svg>
          Nueva carpeta
        </Button>
      {/if}
      {#if canUpload}
        <Button size="sm" class="min-h-10" onclick={onupload}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
            <path d="M12 16V4M7.5 8.5 12 4l4.5 4.5M5 19.5h14" />
          </svg>
          Cargar
        </Button>
      {/if}
    </div>

    <div class="explorer-filter-controls" aria-label="Filtros y orden">
      <FilterSelect id="explorer-category" label="Categoría" value={category} options={categoryOptions} onselect={oncategory} />
      <FilterSelect id="explorer-status" label="Estado" value={status} options={statusOptions} onselect={(value) => onstatus(value as ExplorerStatus)} />
      <FilterSelect id="explorer-sort" label="Ordenar" value={sort} options={sortOptions} onselect={(value) => onsort(value as ExplorerSort)} />
      <div class="view-toggle-group" role="group" aria-label="Vista">
        <button
          type="button"
          class:view-toggle-active={view === 'list'}
          aria-pressed={view === 'list'}
          onclick={() => onview('list')}
          title="Vista de lista"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
          <span class="sr-only">Vista de lista</span>
        </button>
        <button
          type="button"
          class:view-toggle-active={view === 'grid'}
          aria-pressed={view === 'grid'}
          onclick={() => onview('grid')}
          title="Vista de cuadrícula"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg>
          <span class="sr-only">Vista de cuadrícula</span>
        </button>
      </div>
    </div>
  </div>
</div>
<style>
  .explorer-toolbar { overflow: visible; }
  .explorer-filterbar {
    position: relative;
    display: grid;
    grid-template-columns: minmax(230px, 1fr) auto auto;
    align-items: center;
    gap: var(--explorer-space-2);
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-lg);
    background: rgb(var(--surface-elevated));
    padding: var(--explorer-space-2) var(--explorer-space-2) var(--explorer-space-2) var(--explorer-space-3);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.025), 0 12px 32px rgb(0 0 0 / 0.12);
  }

  .explorer-search-wrap { min-width: 0; }
  .explorer-commandbar-actions { display: flex; flex-shrink: 0; align-items: center; gap: 0.5rem; }
  .explorer-filter-controls { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 0.5rem; }
  .explorer-search-input { box-shadow: inset 0 0 0 1px rgb(var(--surface-hover) / 0.35); }
  .explorer-search-shortcut {
    position: absolute;
    right: var(--explorer-space-2);
    top: 50%;
    transform: translateY(-50%);
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-xs);
    background: rgb(var(--surface-elevated));
    padding: var(--explorer-space-3xs) var(--explorer-space-0);
    color: rgb(var(--foreground-subtle));
    font-family: 'Geist Mono', monospace;
    font-size: 0.625rem;
    pointer-events: none;
  }
  .explorer-search-clear {
    position: absolute;
    right: 0.55rem;
    top: 50%;
    display: inline-flex;
    height: var(--explorer-control-height);
    width: var(--explorer-control-height);
    align-items: center;
    justify-content: center;
    transform: translateY(-50%);
    border-radius: 0.5rem;
    background: rgb(var(--surface-elevated));
    color: rgb(var(--foreground-muted));
    font-size: 1.1rem;
  }
  .explorer-search-clear:hover { background: rgb(var(--surface-hover)); color: rgb(var(--foreground)); }
  .explorer-search-clear:focus-visible { outline: none; box-shadow: 0 0 0 2px rgb(var(--surface)), 0 0 0 4px rgb(var(--primary)); }
  .view-toggle-group {
    display: inline-flex;
    min-height: 40px;
    align-items: center;
    gap: 0.125rem;
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-md);
    background: rgb(var(--surface));
    padding: 0.1875rem;
  }
  .view-toggle-group button {
    display: inline-flex;
    min-height: 44px;
    min-width: 44px;
    align-items: center;
    justify-content: center;
    border-radius: var(--explorer-radius-sm);
    color: rgb(var(--foreground-muted));
    transition: background-color 120ms ease, color 120ms ease;
  }
  .view-toggle-group button:hover,
  .view-toggle-group button:focus-visible,
  .view-toggle-active { background: rgb(var(--surface-hover)); color: rgb(var(--foreground)); }
  .view-toggle-group button:focus-visible { outline: none; box-shadow: 0 0 0 2px rgb(var(--surface)), 0 0 0 4px rgb(var(--primary)); }
  @media (max-width: 1150px) {
    .explorer-filterbar { grid-template-columns: minmax(220px, 1fr) auto; }
    .explorer-filter-controls { grid-column: 1 / -1; justify-content: flex-start; }
  }
  @media (max-width: 760px) {
    .explorer-filterbar { grid-template-columns: 1fr; align-items: stretch; }
    .explorer-commandbar-actions,
    .explorer-filter-controls { width: 100%; }
    .explorer-commandbar-actions :global(button) { flex: 1; min-height: 44px; }
    .explorer-filter-controls { justify-content: stretch; }
    .explorer-filter-controls > :global(.explorer-filter) { flex: 1 1 9rem; }
  }
  @media (max-width: 480px) {
    .explorer-filter-controls > :global(.explorer-filter) { flex-basis: calc(50% - 0.25rem); }
    .view-toggle-group { margin-left: auto; }
  }
  @media (prefers-reduced-motion: reduce) {
    .view-toggle-group button { transition: none; }
  }
</style>