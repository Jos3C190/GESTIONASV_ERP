<script lang="ts">
  import { onDestroy } from 'svelte';
  interface FolderNode {
    id: string;
    name: string;
    parentId: string | null;
  }

  interface VisibleFolder extends FolderNode {
    depth: number;
    hasChildren: boolean;
  }

  interface Props {
    folders: FolderNode[];
    currentFolderId: string | null;
    onnavigate: (folderId: string | null) => void;
    ontrash: () => void;
    onmobilechange?: (open: boolean) => void;
    inert?: boolean;
  }

  let { folders, currentFolderId, onnavigate, ontrash, onmobilechange, inert = false }: Props = $props();
  let expanded = $state<Set<string>>(new Set());
  let mobileOpen = $state(false);
  let mobileToggle: HTMLButtonElement | null = null;
  function setGlobalChromeInert(next: boolean) {
    if (typeof document === 'undefined') return;
    const elements = Array.from(document.querySelectorAll<HTMLElement>('[data-app-global-chrome]'));
    for (const element of elements) {
      element.inert = next;
      if (next) element.setAttribute('aria-hidden', 'true');
      else element.removeAttribute('aria-hidden');
    }
  }


  const childrenByParent = $derived.by(() => {
    const map = new Map<string | null, FolderNode[]>();
    for (const folder of folders) {
      const siblings = map.get(folder.parentId) ?? [];
      siblings.push(folder);
      map.set(folder.parentId, siblings);
    }
    for (const siblings of map.values()) {
      siblings.sort((left, right) => left.name.localeCompare(right.name, 'es'));
    }
    return map;
  });

  const activeAncestorIds = $derived.by(() => {
    const byId = new Map(folders.map((folder) => [folder.id, folder]));
    const ancestors = new Set<string>();
    let parentId = currentFolderId ? byId.get(currentFolderId)?.parentId ?? null : null;
    while (parentId && !ancestors.has(parentId)) {
      ancestors.add(parentId);
      parentId = byId.get(parentId)?.parentId ?? null;
    }
    return ancestors;
  });
  let visibleFolders = $derived.by(() => {
    const result: VisibleFolder[] = [];
    const walk = (parentId: string | null, depth: number) => {
      for (const folder of childrenByParent.get(parentId) ?? []) {
        const hasChildren = childrenByParent.has(folder.id);
        result.push({ ...folder, depth, hasChildren });
        if (expanded.has(folder.id) || activeAncestorIds.has(folder.id)) walk(folder.id, depth + 1);
      }
    };
    walk(null, 0);
    return result;
  });

  function toggle(folderId: string) {
    const next = new Set(expanded);
    if (next.has(folderId)) next.delete(folderId);
    else next.add(folderId);
    expanded = next;
  }

  function toggleMobile() {
    mobileOpen = !mobileOpen;
    onmobilechange?.(mobileOpen);
    setGlobalChromeInert(mobileOpen);
    if (mobileOpen) requestAnimationFrame(() => document.querySelector<HTMLElement>('#explorer-sidebar-nav button')?.focus());
    if (!mobileOpen) requestAnimationFrame(() => mobileToggle?.focus());
  }

  function navigate(folderId: string | null) {
    onnavigate(folderId);
    if (mobileOpen) toggleMobile();
  }

  function openTrash() {
    ontrash();
    if (mobileOpen) toggleMobile();
  }

  onDestroy(() => setGlobalChromeInert(false));

  function handleWindowKeydown(event: KeyboardEvent) {
    if (!mobileOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      toggleMobile();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(
      [mobileToggle, ...Array.from(document.querySelectorAll<HTMLElement>('#explorer-sidebar-nav button:not([disabled])'))].filter(Boolean) as HTMLElement[]
    );
    if (focusable.length === 0) return;
    const first = focusable[0]!;
    const last = focusable[focusable.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>
<svelte:window onkeydown={handleWindowKeydown} />

{#if mobileOpen}<button type="button" class="explorer-sidebar-backdrop" aria-label="Cerrar navegación" tabindex="-1" onclick={toggleMobile}></button>{/if}
<aside class:mobile-open={mobileOpen} class="explorer-sidebar" inert={inert ? true : undefined} aria-label="Ubicaciones de Documentos generales" aria-labelledby="explorer-sidebar-title" role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen ? 'true' : undefined}>
  <div class="explorer-sidebar-heading">
    <span id="explorer-sidebar-title">Ubicaciones</span>
    <div class="flex items-center gap-2">
      <span class="explorer-sidebar-count">{folders.length}</span>
      <button
        type="button"
        bind:this={mobileToggle}
        class="explorer-sidebar-mobile-toggle"
        aria-expanded={mobileOpen}
        aria-controls="explorer-sidebar-nav"
        onclick={toggleMobile}
      >
        <span>{mobileOpen ? 'Ocultar' : 'Mostrar'}</span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d={mobileOpen ? 'm6 15 6-6 6 6' : 'm6 9 6 6 6-6'} /></svg>
      </button>
    </div>
  </div>

  <nav id="explorer-sidebar-nav" class="explorer-sidebar-nav" aria-label="Navegación del explorador">
    <button
      type="button"
      class:explorer-nav-active={currentFolderId === null}
      aria-current={currentFolderId === null ? 'page' : undefined}
      class="explorer-nav-row"
      onclick={() => navigate(null)}
    >
      <span class="explorer-nav-icon explorer-nav-icon-home" aria-hidden="true">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10.5 12 4l8 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z" /><path d="M9.5 20v-5h5v5" /></svg>
      </span>
      <span class="min-w-0 flex-1 truncate text-left">General</span>
      <span class="explorer-nav-meta">Raíz</span>
    </button>

    <div class="explorer-sidebar-divider"></div>
    <p class="explorer-sidebar-section-label">Carpetas</p>

    {#if visibleFolders.length === 0}
      <p class="explorer-sidebar-empty">Aún no hay carpetas personalizadas.</p>
    {:else}
      {#each visibleFolders as folder (folder.id)}
        <div class="explorer-nav-folder-row">
          {#if folder.hasChildren}
            <button
              type="button"
              class="explorer-folder-toggle"
              aria-label={expanded.has(folder.id) ? `Contraer ${folder.name}` : `Expandir ${folder.name}`}
              aria-expanded={expanded.has(folder.id) || activeAncestorIds.has(folder.id)}
              onclick={() => toggle(folder.id)}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true" class:rotate-90={expanded.has(folder.id) || activeAncestorIds.has(folder.id)}><path d="m9 5 7 7-7 7" /></svg>
            </button>
          {:else}
            <span class="explorer-folder-toggle-spacer" aria-hidden="true"></span>
          {/if}
          <button
            type="button"
            class:explorer-nav-active={currentFolderId === folder.id}
            aria-current={currentFolderId === folder.id ? 'page' : undefined}
            class="explorer-nav-row explorer-nav-folder"
            style={`--folder-depth: ${folder.depth}`}
            onclick={() => navigate(folder.id)}
          >
            <span class="explorer-nav-icon explorer-nav-icon-folder" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M3.5 9h17" /></svg>
            </span>
            <span class="min-w-0 flex-1 truncate text-left">{folder.name}</span>
          </button>
        </div>
      {/each}
    {/if}

    <div class="explorer-sidebar-divider"></div>
    <button type="button" class="explorer-nav-row explorer-trash-row" onclick={openTrash}>
      <span class="explorer-nav-icon" aria-hidden="true"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6.5 7l1 13h9l1-13M9 7V4h6v3" /></svg></span>
      <span class="min-w-0 flex-1 truncate text-left">Papelera</span>
      <span class="explorer-nav-meta">Ver</span>
    </button>
  </nav>
</aside>

<style>
  .explorer-sidebar {
    width: 13.5rem;
    flex: 0 0 13.5rem;
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-lg);
    background: rgb(var(--surface-elevated));
    padding: 0.75rem;
  }
  .explorer-sidebar-heading { display: flex; align-items: center; justify-content: space-between; padding: 0.2rem 0.35rem 0.65rem; color: rgb(var(--foreground)); font-size: 0.75rem; font-weight: 700; }
  .explorer-sidebar-count { border-radius: 999px; background: rgb(var(--surface-hover)); padding: 0.15rem 0.4rem; color: rgb(var(--foreground-muted)); font-family: 'Geist Mono', monospace; font-size: 0.625rem; }
  .explorer-sidebar-backdrop { display: none; }
  .explorer-sidebar-mobile-toggle { display: none; min-height: var(--explorer-control-height); align-items: center; gap: 0.3rem; border-radius: 0.5rem; padding: 0 0.45rem; color: rgb(var(--foreground-muted)); font-size: 0.6875rem; font-weight: 650; }
  .explorer-sidebar-mobile-toggle:hover, .explorer-sidebar-mobile-toggle:focus-visible { background: rgb(var(--surface-hover)); color: rgb(var(--foreground)); outline: none; }
  .explorer-sidebar-nav { display: grid; gap: 0.15rem; }
  .explorer-nav-row { display: flex; min-height: var(--explorer-control-height); width: 100%; align-items: center; gap: 0.55rem; border-radius: var(--explorer-radius-sm); padding: 0 0.5rem; color: rgb(var(--foreground-muted)); font-size: 0.75rem; font-weight: 550; }
  .explorer-nav-row:hover, .explorer-nav-row:focus-visible { background: rgb(var(--surface-hover)); color: rgb(var(--foreground)); outline: none; }
  .explorer-nav-active { background: rgb(var(--primary) / 0.1); color: rgb(var(--primary)); box-shadow: inset 2px 0 0 rgb(var(--primary)); }
  .explorer-nav-icon { display: inline-flex; height: 1.65rem; width: 1.65rem; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: var(--explorer-radius-sm); color: rgb(var(--foreground-muted)); }
  .explorer-nav-icon-home { background: rgb(var(--primary) / 0.1); color: rgb(var(--primary)); }
  .explorer-nav-icon-folder { color: rgb(var(--warning)); }
  .explorer-nav-meta { color: rgb(var(--foreground-subtle)); font-size: 0.625rem; font-weight: 500; }
  .explorer-sidebar-divider { height: 1px; margin: var(--explorer-space-2) 0; background: rgb(var(--border)); }
  .explorer-sidebar-section-label { padding: 0 0.35rem 0.35rem; color: rgb(var(--foreground-subtle)); font-size: 0.6875rem; font-weight: 650; letter-spacing: 0.01em; }
  .explorer-sidebar-empty { padding: 0.35rem; color: rgb(var(--foreground-muted)); font-size: 0.6875rem; line-height: 1.45; }
  .explorer-nav-folder-row { display: flex; min-width: 0; align-items: center; }
  .explorer-folder-toggle, .explorer-folder-toggle-spacer { display: inline-flex; height: var(--explorer-control-height); width: var(--explorer-control-height); flex: 0 0 var(--explorer-control-height); align-items: center; justify-content: center; color: rgb(var(--foreground-subtle)); }
  .explorer-folder-toggle:hover, .explorer-folder-toggle:focus-visible { color: rgb(var(--foreground)); outline: none; }
  .explorer-nav-folder { min-width: 0; padding-left: calc(0.5rem + var(--folder-depth) * 0.75rem); }
  .explorer-trash-row { color: rgb(var(--foreground-muted)); }
  @media (max-width: 900px) {
    .explorer-sidebar { width: 100%; flex-basis: auto; border-color: transparent; background: transparent; padding: 0; }
    .explorer-sidebar-backdrop { position: fixed; inset: 0; z-index: 90; display: block; border: 0; background: rgb(0 0 0 / 0.52); }
    .explorer-sidebar.mobile-open { position: fixed; top: 4.5rem; left: 1rem; z-index: 100; width: min(21rem, calc(100vw - 2rem)); max-height: calc(100vh - 6rem); overflow: auto; border: 1px solid rgb(var(--border)); border-radius: var(--explorer-radius-lg); background: rgb(var(--surface-elevated)); padding: 0.75rem; box-shadow: var(--shadow-xl); }
    .explorer-sidebar-mobile-toggle { display: inline-flex; }
    .explorer-sidebar-heading { min-height: var(--explorer-control-height); border: 1px solid rgb(var(--border)); border-radius: var(--explorer-radius-md); background: rgb(var(--surface-elevated)); padding: 0 var(--explorer-space-2); }
    .explorer-sidebar-nav { display: none; grid-template-columns: 1fr; }
    .explorer-sidebar.mobile-open .explorer-sidebar-nav { display: grid; }
    .explorer-sidebar-divider { margin: 0.35rem 0; }
    .explorer-sidebar-section-label { display: block; }
    .explorer-sidebar-empty { display: block; }
    .explorer-nav-folder-row, .explorer-trash-row { display: flex; }
  }
  @media (prefers-reduced-motion: reduce) { .explorer-folder-toggle svg { transition: none; } }
</style>
