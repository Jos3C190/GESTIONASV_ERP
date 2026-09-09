<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { DocumentCategoryOut } from '$lib/api/client';
  import type { ExplorerSort, ExplorerStatus, ExplorerView } from './types';

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
  }</script>

<div class="space-y-3">
  <div class="explorer-commandbar">
    <div class="min-w-0">
      <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-foreground-subtle">
        Explorador
      </p>
      <p class="truncate text-sm font-medium text-foreground">Contenido de esta carpeta</p>
    </div>
    <div class="flex shrink-0 items-center gap-2">
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
  </div>

  <div class="explorer-filterbar">
    <label class="relative min-w-0 flex-1">
      <span class="sr-only">Buscar en Documentos generales</span>
      <svg
        class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
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
        class="h-10 w-full rounded-lg border border-border bg-surface px-3 pl-9 text-sm text-foreground outline-none transition placeholder:text-foreground-subtle focus:border-primary focus:ring-2 focus:ring-primary/20"
        autocomplete="off"
      />
    </label>

    <div class="flex flex-wrap items-center gap-2">
      <label class="explorer-select">
        <span>Categoría</span>
        <select
          value={category}
          onchange={(event) => oncategory((event.currentTarget as HTMLSelectElement).value)}
        >
          <option value="">Todas</option>
          {#each categories.filter((item) => item.is_active) as item (item.id)}
            <option value={item.id}>{item.name}</option>
          {/each}
        </select>
      </label>
      <label class="explorer-select">
        <span>Estado</span>
        <select
          value={status}
          onchange={(event) => onstatus((event.currentTarget as HTMLSelectElement).value as ExplorerStatus)}
        >
          <option value="">Todos</option>
          <option value="active">Activos</option>
          <option value="processing">Procesando</option>
          <option value="deleted">En papelera</option>
        </select>
      </label>
      <label class="explorer-select">
        <span>Ordenar</span>
        <select
          value={sort}
          onchange={(event) => onsort((event.currentTarget as HTMLSelectElement).value as ExplorerSort)}
        >
          <option value="name">Nombre</option>
          <option value="updated">Modificado</option>
          <option value="size">Tamaño</option>
        </select>
      </label>
      <div class="view-toggle-group" aria-label="Vista">
        <button
          type="button"
          class:view-toggle-active={view === 'list'}
          aria-pressed={view === 'list'}
          onclick={() => onview('list')}
          title="Vista de lista"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
          <span class="sr-only">Vista de lista</span>
        </button>
        <button
          type="button"
          class:view-toggle-active={view === 'grid'}
          aria-pressed={view === 'grid'}
          onclick={() => onview('grid')}
          title="Vista de cuadrícula"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg>
          <span class="sr-only">Vista de cuadrícula</span>
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .explorer-commandbar,
  .explorer-filterbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--surface-elevated));
    padding: 0.75rem;
  }
  .explorer-commandbar {
    min-height: 62px;
    border-radius: 0.875rem 0.875rem 0 0;
    border-bottom-color: rgb(var(--border) / 0.7);
  }
  .explorer-filterbar {
    align-items: stretch;
    border-radius: 0 0 0.875rem 0.875rem;
    padding-top: 0.625rem;
  }
  .explorer-select {
    display: inline-flex;
    min-height: 40px;
    align-items: center;
    gap: 0.45rem;
    border: 1px solid rgb(var(--border));
    border-radius: 0.5rem;
    background: rgb(var(--surface));
    padding: 0 0.625rem;
    font-size: 0.75rem;
    color: rgb(var(--foreground-muted));
  }
  .explorer-select select {
    max-width: 8rem;
    background: transparent;
    color: rgb(var(--foreground));
    font-size: 0.8125rem;
    outline: none;
  }
  .view-toggle-group {
    display: inline-flex;
    min-height: 40px;
    align-items: center;
    gap: 0.125rem;
    border: 1px solid rgb(var(--border));
    border-radius: 0.5rem;
    background: rgb(var(--surface));
    padding: 0.1875rem;
  }
  .view-toggle-group button {
    display: inline-flex;
    min-height: 32px;
    min-width: 34px;
    align-items: center;
    justify-content: center;
    border-radius: 0.375rem;
    color: rgb(var(--foreground-muted));
    transition: background-color 120ms ease, color 120ms ease;
  }
  .view-toggle-group button:hover,
  .view-toggle-group button:focus-visible,
  .view-toggle-active {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  @media (max-width: 760px) {
    .explorer-commandbar,
    .explorer-filterbar { align-items: stretch; flex-direction: column; }
    .explorer-filterbar > div { justify-content: space-between; }
    .explorer-select { flex: 1 1 auto; }
    .explorer-select select { max-width: none; flex: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .view-toggle-group button { transition: none; }
  }
</style>