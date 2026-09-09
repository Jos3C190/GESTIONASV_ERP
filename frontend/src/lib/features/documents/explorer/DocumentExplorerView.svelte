<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    api,
    HttpError,
    type DocumentBreadcrumbOut,
    type DocumentCategoryOut
  } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import DocumentBreadcrumbs from '$lib/features/documents/components/DocumentBreadcrumbs.svelte';
  import {
    openDocumentInBrowser,
    DocumentBrowserOpenError
  } from '$lib/features/documents/open-document';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { parseExplorerQuery, serializeExplorerQuery } from './query';
  import { keyboardAction, documentOpenAction, canExplorerAction, canDropIntoFolder } from './interaction';
  import { normalizeExplorerPage, type ExplorerItem, type ExplorerQuery } from './types';
  import Toolbar from './Toolbar.svelte';
  import List from './List.svelte';
  import Grid from './Grid.svelte';
  import EmptyState from './EmptyState.svelte';
  import ExplorerSidebar from './ExplorerSidebar.svelte';
  import ExplorerOverlays from './ExplorerOverlays.svelte';
  import { gridNavigationIndex } from './grid-navigation';

  let query = $state<ExplorerQuery>(parseExplorerQuery(page.url));
  let items = $state<ExplorerItem[]>([]);
  let breadcrumbs = $state<DocumentBreadcrumbOut[]>([]);
  let categories = $state<DocumentCategoryOut[]>([]);
  let folders = $state<{ id: string; name: string; parentId: string | null }[]>([]);
  let total = $state(0);
  let pages = $state(1);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let successTimer: ReturnType<typeof setTimeout> | undefined;
  let uploadOpen = $state(false);
  let createOpen = $state(false);
  let createName = $state('');
  let createSaving = $state(false);
  let createAttempted = $state(false);
  let selectedIds = $state<Set<string>>(new Set());
  let selectionAnchorId = $state<string | null>(null);
  let focusedItemId = $state<string | null>(null);
  let deleteConfirmItem = $state<ExplorerItem | null>(null);
  let context = $state<{ item: ExplorerItem; x: number; y: number } | null>(null);
  let contextInvoker = $state<HTMLElement | null>(null);
  let renameItem = $state<ExplorerItem | null>(null);
  let moveItem = $state<ExplorerItem | null>(null);
  let mutationBusy = $state(false);
  let draggingId = $state<string | null>(null);
  let dropTargetId = $state<string | null>(null);
  let rootDropActive = $state(false);
  let controller: AbortController | null = null;
  let loadSequence = 0;
  let mobileNavigationOpen = $state(false);

  const canFolder = $derived(canExplorerAction('create-folder', permissions.hasPermission));
  const canMove = $derived(canExplorerAction('move', permissions.hasPermission));
  const canRename = $derived(canExplorerAction('rename', permissions.hasPermission));
  const canRenameFiles = $derived(permissions.hasPermission('documents:update'));
  const canDeleteFiles = $derived(canExplorerAction('delete', permissions.hasPermission));
  const canDelete = $derived(canFolder || canDeleteFiles);
  const canRestore = $derived(canExplorerAction('restore', permissions.hasPermission));
  const canUpload = $derived(canExplorerAction('upload', permissions.hasPermission));
  const hasActiveFilters = $derived(Boolean(query.search || query.category || query.status));
  const activeCategoryLabel = $derived(categories.find((category) => category.id === query.category)?.name ?? 'Categoría');
  const activeStatusLabel = $derived(({ active: 'Activos', processing: 'Procesando', deleted: 'En papelera' } as Record<string, string>)[query.status] ?? query.status);
  const selectedItems = $derived(items.filter((item) => selectedIds.has(item.id)));
  const modalOpen = $derived(uploadOpen || createOpen || Boolean(deleteConfirmItem || renameItem || moveItem));
  const selectedItem = $derived(selectedItems.length === 1 ? selectedItems[0] : null);

  function updateQuery(changes: Partial<ExplorerQuery>) {
    const next = { ...query, ...changes };
    success = null;
    error = null;
    const serialized = serializeExplorerQuery(next);
    void goto('/documents/general' + (serialized ? '?' + serialized : ''), {
      replaceState: !('folder' in changes),
      keepFocus: true,
      noScroll: true
    });
  }

  async function load(nextQuery: ExplorerQuery) {
    const sequence = ++loadSequence;
    controller?.abort();
    const requestController = new AbortController();
    controller = requestController;
    loading = true;
    error = null;
    try {
      const result = await api.documents.general.list({
        folder_id: nextQuery.folder || null,
        search: nextQuery.search || undefined,
        category_id: nextQuery.category || undefined,
        status: nextQuery.status || undefined,
        sort: nextQuery.sort,
        page: nextQuery.page,
        signal: requestController.signal
      });
      const categoryResult = categories.length
        ? categories
        : await api.documents.categories('general', requestController.signal);
      const tree = await api.documents.general.tree(requestController.signal);
      if (sequence !== loadSequence) return;
      const data = normalizeExplorerPage(result, categoryResult as DocumentCategoryOut[]);
      items = data.items;
      breadcrumbs = data.breadcrumbs;
      categories = data.categories;
      total = data.total;
      pages = data.pages;
      folders = tree.items
        .filter((entry) => entry.kind === 'folder' && !entry.deleted_at)
        .map((entry) => ({ id: entry.id, name: entry.name, parentId: entry.parent_id }));
      selectedIds = new Set();
      selectionAnchorId = null;
      focusedItemId = data.items[0]?.id ?? null;
    } catch (cause) {
      if (sequence !== loadSequence) return;
      if (cause instanceof DOMException && cause.name === 'AbortError') return;
      error = cause instanceof HttpError ? cause.message : 'No se pudo cargar General.';
    } finally {
      if (sequence === loadSequence) loading = false;
    }
  }

  $effect(() => {
    const nextQuery = parseExplorerQuery(page.url);
    query = nextQuery;
    void load(nextQuery);
  });

  $effect(() => {
    if (successTimer) clearTimeout(successTimer);
    if (!success) return;
    successTimer = setTimeout(() => (success = null), 4200);
  });

  function openCreateFolder() {
    createName = '';
    createAttempted = false;
    createOpen = true;
  }

  function openItem(item: ExplorerItem) {
    if (item.kind === 'folder') {
      updateQuery({ folder: item.id, page: 1 });
      return;
    }
    void openFile(item);
  }

  async function openFile(item: Extract<ExplorerItem, { kind: 'file' }>) {
    try {
      if (documentOpenAction(item.document) === 'open-pdf') {
        await openDocumentInBrowser(item.document.id);
      } else {
        const result = await api.documents.downloadUrl(item.document.id);
        window.open(result.url, '_blank', 'noopener,noreferrer');
      }
    } catch (cause) {
      error =
        cause instanceof DocumentBrowserOpenError || cause instanceof HttpError
          ? cause.message
          : 'No se pudo abrir el documento.';
    }
  }

  function selectItem(item: ExplorerItem, event: MouseEvent) {
    const next = new Set(selectedIds);
    const itemIndex = items.findIndex((candidate) => candidate.id === item.id);
    const anchorIndex = selectionAnchorId
      ? items.findIndex((candidate) => candidate.id === selectionAnchorId)
      : -1;

    if (event.shiftKey && anchorIndex >= 0 && itemIndex >= 0) {
      const start = Math.min(anchorIndex, itemIndex);
      const end = Math.max(anchorIndex, itemIndex);
      selectedIds = new Set(items.slice(start, end + 1).map((candidate) => candidate.id));
      focusedItemId = item.id;
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
    } else {
      next.clear();
      next.add(item.id);
    }
    selectionAnchorId = item.id;
    focusedItemId = item.id;
    selectedIds = next;
  }

  function openContext(item: ExplorerItem, event: MouseEvent | PointerEvent) {
    if (!selectedIds.has(item.id)) {
      selectedIds = new Set([item.id]);
      selectionAnchorId = item.id;
    }
    const source = event.currentTarget as HTMLElement | null;
    contextInvoker = source?.closest('button') ?? source;
    context = { item, x: event.clientX, y: event.clientY };
  }

  function itemElement(itemId: string): HTMLElement | null {
    return Array.from(document.querySelectorAll<HTMLElement>('[data-explorer-item-id]')).find(
      (element) => element.dataset.explorerItemId === itemId
    ) ?? null;
  }

  function openKeyboardContext(item: ExplorerItem, anchor?: HTMLElement | null) {
    const target = anchor ?? itemElement(item.id)?.querySelector<HTMLElement>('.explorer-item-main');
    const rect = target?.getBoundingClientRect();
    contextInvoker = target ?? null;
    context = { item, x: rect?.left ?? 280, y: rect ? rect.bottom : 160 };
  }

  function nextGridItemIndex(currentIndex: number, key: string): number {
    const layout = items.map((candidate, index) => {
      const rect = itemElement(candidate.id)?.getBoundingClientRect();
      return rect ? { index, left: rect.left, top: rect.top, width: rect.width, height: rect.height } : null;
    }).filter(Boolean) as Array<{ index: number; left: number; top: number; width: number; height: number }>;
    return gridNavigationIndex(layout, currentIndex, key);
  }
  function keyItem(item: ExplorerItem, event: KeyboardEvent) {
    if (event.key === ' ') {
      event.preventDefault();
      selectItem(item, event as unknown as MouseEvent);
      return;
    }

    if (event.key === 'Home' || event.key === 'End' || event.key === 'ArrowDown' || event.key === 'ArrowUp' || (query.view === 'grid' && (event.key === 'ArrowLeft' || event.key === 'ArrowRight'))) {
      event.preventDefault();
      const currentIndex = items.findIndex((candidate) => candidate.id === item.id);
      const nextIndex =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? items.length - 1
            : query.view === 'grid'
              ? nextGridItemIndex(currentIndex, event.key)
              : Math.max(0, Math.min(items.length - 1, currentIndex + (event.key === 'ArrowDown' ? 1 : -1)));
      const nextItem = items[nextIndex];
      if (!nextItem) return;

      focusedItemId = nextItem.id;

      if (event.shiftKey) {
        const anchorIndex = selectionAnchorId
          ? items.findIndex((candidate) => candidate.id === selectionAnchorId)
          : currentIndex;
        const start = Math.min(anchorIndex < 0 ? currentIndex : anchorIndex, nextIndex);
        const end = Math.max(anchorIndex < 0 ? currentIndex : anchorIndex, nextIndex);
        selectedIds = new Set(items.slice(start, end + 1).map((candidate) => candidate.id));
        focusedItemId = nextItem.id;
      } else {
        selectedIds = new Set([nextItem.id]);
        selectionAnchorId = nextItem.id;
      }
      requestAnimationFrame(() => {
        const focusTarget = Array.from(document.querySelectorAll<HTMLElement>('[data-explorer-item-id]')).find(
          (element) => element.dataset.explorerItemId === nextItem.id
        )?.querySelector<HTMLElement>('.explorer-item-main');
        focusTarget?.focus();
      });
      return;
    }

    const action = keyboardAction(event.key, {
      ctrl: event.ctrlKey,
      meta: event.metaKey,
      shift: event.shiftKey
    });
    if (action === 'open') {
      event.preventDefault();
      openItem(item);
    } else if (action === 'select-all') {
      event.preventDefault();
      selectedIds = new Set(items.map((candidate) => candidate.id));
      selectionAnchorId = items[0]?.id ?? null;
    } else if (action === 'rename' && (item.kind === 'folder' ? canFolder : canRenameFiles)) {
      event.preventDefault();
      renameItem = item;
    } else if (action === 'delete' && canDelete) {
      event.preventDefault();
      requestDelete(item);
    } else if (action === 'context-menu') {
      event.preventDefault();
      openKeyboardContext(item, event.currentTarget as HTMLElement | null);

    } else if (action === 'close') {
      context = null;
    }
  }

  function draggedItem(event?: DragEvent): ExplorerItem | null {
    const id = event?.dataTransfer?.getData('text/plain') || draggingId;
    return id ? items.find((candidate) => candidate.id === id) ?? null : null;
  }

  function draggedItems(event?: DragEvent): ExplorerItem[] {
    const rawIds = event?.dataTransfer?.getData('application/x-document-entry-ids');
    const ids = rawIds ? rawIds.split('\n').filter(Boolean) : [];
    if (ids.length > 0) return ids.map((id) => items.find((candidate) => candidate.id === id)).filter(Boolean) as ExplorerItem[];
    const source = draggedItem(event);
    if (!source) return [];
    return selectedIds.has(source.id) ? items.filter((item) => selectedIds.has(item.id)) : [source];
  }

  function canMoveToParent(item: ExplorerItem, parentId: string | null): boolean {
    if (!canDropIntoFolder({ id: item.id, kind: item.kind, parentId: item.entry.parent_id }, parentId)) return false;
    if (item.kind !== 'folder' || parentId === null) return true;

    const visited = new Set<string>();
    let currentId: string | null = parentId;
    while (currentId && !visited.has(currentId)) {
      if (currentId === item.id) return false;
      visited.add(currentId);
      currentId = folders.find((folder) => folder.id === currentId)?.parentId ?? null;
    }
    return true;
  }

  function dragStart(item: ExplorerItem, event: DragEvent) {
    if (!canMove) return;
    draggingId = item.id;
    rootDropActive = false;
    const dragSelection = selectedIds.has(item.id) ? items.filter((candidate) => selectedIds.has(candidate.id)) : [item];
    event.dataTransfer?.setData('text/plain', item.id);
    event.dataTransfer?.setData('application/x-document-entry-ids', dragSelection.map((candidate) => candidate.id).join('\n'));
    event.dataTransfer?.setData('application/x-document-entry-kind', item.kind);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function dragEnd() {
    draggingId = null;
    dropTargetId = null;
    rootDropActive = false;
  }

  function dragOverFolder(folder: ExplorerItem, event: DragEvent) {
    const sources = draggedItems(event);
    if (sources.length === 0 || !canMove || folder.kind !== 'folder') return;
    if (sources.some((source) => !canMoveToParent(source, folder.id))) {
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
      dropTargetId = null;
      return;
    }
    event.preventDefault();
    rootDropActive = false;
    dropTargetId = folder.id;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  }

  async function dropOnFolder(folder: ExplorerItem, event: DragEvent) {
    event.preventDefault();
    const sources = draggedItems(event);
    dragEnd();
    if (sources.length === 0 || folder.kind !== 'folder') return;
    await moveItems(sources, folder.id);
  }

  function dragOverRoot(event: DragEvent) {
    const sources = draggedItems(event);
    if (sources.length === 0 || !canMove) return;
    if (sources.some((source) => !canMoveToParent(source, null))) {
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
      rootDropActive = false;
      return;
    }
    event.preventDefault();
    dropTargetId = null;
    rootDropActive = true;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  }

  async function dropOnRoot(event: DragEvent) {
    event.preventDefault();
    const sources = draggedItems(event);
    dragEnd();
    if (sources.length > 0) await moveItems(sources, null);
  }

  async function moveItems(sourceItems: ExplorerItem[], parentId: string | null) {
    if (mutationBusy || !canMove || sourceItems.length === 0) return;
    if (sourceItems.some((item) => !canMoveToParent(item, parentId))) {
      error = 'Uno o más elementos no se pueden mover a esa carpeta.';
      return;
    }
    mutationBusy = true;
    try {
      await api.documents.general.moveBatch(
        sourceItems.map((item) => ({ entry_id: item.id, kind: item.kind })),
        parentId
      );
      moveItem = null;
      success =
        sourceItems.length === 1
          ? sourceItems[0]!.name + ' se movió correctamente.'
          : sourceItems.length + ' elementos se movieron correctamente.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron mover los elementos. No se aplicaron cambios.';
    } finally {
      mutationBusy = false;
    }
  }
  async function move(item: ExplorerItem, parentId: string | null) {
    await moveItems([item], parentId);
  }

  async function createFolder() {
    const name = createName.trim();
    if (createSaving) return;
    if (!name) {
      createAttempted = true;
      return;
    }
    createSaving = true;
    try {
      await api.documents.general.createFolder({ name, parent_id: query.folder || null });
      createName = '';
      createAttempted = false;
      createOpen = false;
      success = 'Carpeta creada correctamente.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo crear la carpeta.';
    } finally {
      createSaving = false;
    }
  }

  async function rename(name: string) {
    if (!renameItem || mutationBusy) return;
    if (renameItem.kind === 'folder' ? !canFolder : !canRenameFiles) return;
    mutationBusy = true;
    try {
      if (renameItem.kind === 'folder') {
        await api.documents.general.renameFolder(renameItem.id, name);
      } else {
        await api.documents.general.renameFile(renameItem.document.id, name);
      }
      renameItem = null;
      success = 'Nombre actualizado correctamente.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo renombrar el elemento.';
    } finally {
      mutationBusy = false;
    }
  }

  function requestDelete(item: ExplorerItem) {
    if (mutationBusy || item.entry.deleted_at) return;
    if (item.kind === 'folder' ? !canFolder : !canDeleteFiles) return;
    deleteConfirmItem = item;
  }

  async function confirmDelete() {
    const item = deleteConfirmItem;
    if (!item || mutationBusy) return;
    mutationBusy = true;
    try {
      if (item.kind === 'folder') {
        await api.documents.general.deleteFolder(item.id);
      } else {
        await api.lifecycle.delete(
          'documents',
          item.document.id,
          'Eliminado desde Documentos generales'
        );
      }
      deleteConfirmItem = null;
      success = 'Elemento enviado a la Papelera.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo enviar a la Papelera.';
    } finally {
      mutationBusy = false;
    }
  }

  async function restoreItem(item: ExplorerItem) {
    if (mutationBusy || !canRestore) return;
    mutationBusy = true;
    try {
      if (item.kind === 'folder') {
        await api.documents.general.restoreFolder(item.id);
      } else {
        await api.lifecycle.restore('documents', item.document.id);
      }
      success = 'Elemento restaurado correctamente.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo restaurar el elemento.';
    } finally {
      mutationBusy = false;
    }
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.defaultPrevented) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      document.querySelector<HTMLInputElement>('.explorer-search-input')?.focus();
      return;
    }
    const target = event.target as HTMLElement | null;
    const itemMain = target?.closest('.explorer-item-main');
    if (
      target?.matches('input, select, textarea, [contenteditable="true"]') ||
      (target?.closest('button, [role="dialog"], [role="menu"], [role="combobox"], [role="listbox"]') && !itemMain)
    ) return;
    const selected = items.filter((item) => selectedIds.has(item.id));
    const selectedItem = selected[0];
    const action = keyboardAction(event.key, {
      ctrl: event.ctrlKey,
      meta: event.metaKey,
      shift: event.shiftKey
    });
    if (action === 'select-all') {
      event.preventDefault();
      selectedIds = new Set(items.map((item) => item.id));
      selectionAnchorId = items[0]?.id ?? null;
    } else if (action === 'close') {
      context = null;
    } else if (selectedItem && action === 'rename' && (selectedItem.kind === 'folder' ? canFolder : canRenameFiles)) {
      event.preventDefault();
      renameItem = selectedItem;
    } else if (selectedItem && action === 'delete' && canDelete) {
      event.preventDefault();
      requestDelete(selectedItem);
    } else if (selectedItem && action === 'context-menu') {
      event.preventDefault();
      openKeyboardContext(selectedItem);

    }
  }
  function closeMenu() {
    const invoker = contextInvoker;
    context = null;
    contextInvoker = null;
    requestAnimationFrame(() => invoker?.focus());
  }
</script>

<svelte:head><title>General · Documentos · GestionaSV</title></svelte:head>
<svelte:window onkeydown={handleWindowKeydown} />

<div class="explorer-page-shell mx-auto w-full max-w-[1600px] p-4 md:p-8">
  <header class="explorer-page-heading mb-5" inert={modalOpen || mobileNavigationOpen} aria-hidden={modalOpen || mobileNavigationOpen ? 'true' : undefined}>
    <div class="explorer-heading-copy min-w-0">
      <div class="explorer-heading-eyebrow"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 9h17"/></svg><span>Biblioteca empresarial</span><span aria-hidden="true">/</span><strong>General</strong></div>
      <h1 class="mt-1 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">General</h1>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">Archivos compartidos de la empresa, organizados con claridad.</p>
    </div>
    <div class="explorer-heading-meta" aria-label="Resumen del espacio">
      <div><span class="explorer-heading-meta-label">Elementos</span><strong>{total}</strong></div>
      <span class="explorer-heading-meta-divider" aria-hidden="true"></span>
      <div><span class="explorer-heading-meta-label">Atajo</span><kbd>Ctrl K</kbd></div>
    </div>
  </header>

  <div class="explorer-workspace">
    <ExplorerSidebar
      {folders}
      currentFolderId={query.folder || null}
      onnavigate={(folderId: string | null) => updateQuery({ folder: folderId ?? '', page: 1 })}
      ontrash={() => void goto('/trash')}
      onmobilechange={(open) => (mobileNavigationOpen = open)}
      inert={modalOpen}
    />

    <section class="explorer-content" inert={modalOpen || mobileNavigationOpen} aria-hidden={modalOpen || mobileNavigationOpen ? 'true' : undefined}>
      <div class="explorer-breadcrumb-wrap">
        <DocumentBreadcrumbs
          items={breadcrumbs.slice(0, -1)}
          current={breadcrumbs.at(-1)?.label ?? 'General'}
        />
      </div>
  <Toolbar
    search={query.search}
    category={query.category}
    status={query.status}
    sort={query.sort}
    view={query.view}
    {categories}
    canCreateFolder={canFolder}
    {canUpload}
    onsearch={(value) => updateQuery({ search: value, page: 1 })}
    oncategory={(value) => updateQuery({ category: value, page: 1 })}
    onstatus={(value) => updateQuery({ status: value, page: 1 })}
    onsort={(value) => updateQuery({ sort: value, page: 1 })}
    onview={(value) => updateQuery({ view: value })}
    oncreatefolder={openCreateFolder}
    onupload={() => (uploadOpen = true)}
  />

  {#if hasActiveFilters}
    <div class="explorer-filter-chips" aria-label="Filtros activos">
      {#if query.search}
        <button type="button" class="explorer-filter-chip" onclick={() => updateQuery({ search: '', page: 1 })}>
          Buscar: “{query.search}” <span aria-hidden="true">×</span>
        </button>
      {/if}
      {#if query.category}
        <button type="button" class="explorer-filter-chip" onclick={() => updateQuery({ category: '', page: 1 })}>
          {activeCategoryLabel} <span aria-hidden="true">×</span>
        </button>
      {/if}
      {#if query.status}
        <button type="button" class="explorer-filter-chip" onclick={() => updateQuery({ status: '', page: 1 })}>
          {activeStatusLabel} <span aria-hidden="true">×</span>
        </button>
      {/if}
      <button type="button" class="explorer-filter-reset" onclick={() => updateQuery({ search: '', category: '', status: '', page: 1 })}>Restablecer</button>
    </div>
  {/if}

  <div class="explorer-statusbar mt-4" aria-live="polite">
    {#if loading && items.length > 0}<span class="explorer-refreshing" role="status">Actualizando…</span>{/if}
    {#if selectedItems.length > 0}
      <div class="explorer-selection-bar">
        <div class="flex min-w-0 items-center gap-3">
          <span class="explorer-selection-count">{selectedItems.length} seleccionado{selectedItems.length === 1 ? '' : 's'}</span>
          {#if selectedItems.length > 1}<span class="explorer-selection-hint">Arrastra la selección para moverla</span>{/if}
        </div>
        <div class="explorer-selection-actions">
          {#if selectedItem && canMove}
            <button type="button" class="explorer-inline-action" onclick={() => (moveItem = selectedItem!)}>Mover a…</button>
          {/if}
          {#if selectedItem && (selectedItem.kind === 'folder' ? canFolder : canDeleteFiles)}
            <button type="button" class="explorer-inline-action explorer-inline-action-danger" onclick={() => requestDelete(selectedItem!)}>Papelera</button>
          {/if}
          <button type="button" class="explorer-clear-selection" onclick={() => { selectedIds = new Set(); selectionAnchorId = null; }}>Limpiar selección</button>
        </div>
      </div>
    {:else}
      <div class="flex min-w-0 items-center gap-3">
        <span class="explorer-status-count">{total} elemento{total === 1 ? '' : 's'}</span>
      </div>
      <span class="explorer-shortcuts hidden text-xs md:inline">Doble clic abrir · Arrastra mover · Clic derecho opciones</span>
      {#if success}<span class="explorer-success" role="status">{success}</span>{/if}
    {/if}
  </div>

{#if error && items.length > 0}
    <div
      class="mt-3 flex items-center gap-3 rounded-xl border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      <span>{error}</span>
      <button
        type="button"
        class="ml-auto shrink-0 font-medium underline underline-offset-2 hover:no-underline"
        onclick={() => void load(query)}
      >
        Reintentar
      </button>
    </div>
  {/if}

  <div class="mt-3">
    {#if loading && items.length === 0}
      {#if query.view === 'grid'}
        <div class="explorer-loading-grid" aria-busy="true" aria-label="Cargando documentos generales" role="status">
          {#each Array(6) as _}<div class="h-40 rounded-xl border border-border bg-surface-elevated skeleton"></div>{/each}
        </div>
      {:else}
        <div
          class="grid gap-2 rounded-2xl border border-border bg-surface-elevated p-3"
          aria-busy="true"
          aria-label="Cargando documentos generales"
          role="status"
        >
          {#each Array(7) as _}<div class="h-12 rounded-lg skeleton"></div>{/each}
        </div>
      {/if}
    {:else if error && items.length === 0}
      <EmptyState
        title="No se pudo cargar esta carpeta"
        description="Conservamos tu contexto. Reintenta para volver a consultar los documentos."
        actionLabel="Reintentar"
        onaction={() => void load(query)}
      />
    {:else if items.length === 0}
      <EmptyState
        title={hasActiveFilters ? 'No hay coincidencias' : 'Esta carpeta está vacía'}
        description={hasActiveFilters
          ? 'Prueba con otro término o limpia los filtros para ver más resultados.'
          : 'Crea una carpeta o carga el primer documento para comenzar.'}
        actionLabel={hasActiveFilters ? 'Limpiar filtros' : canFolder ? 'Nueva carpeta' : undefined}
        onaction={() => (hasActiveFilters ? updateQuery({ search: '', category: '', status: '', page: 1 }) : openCreateFolder())}
        secondaryLabel={!hasActiveFilters && canUpload ? 'Cargar documento' : undefined}
        onsecondary={() => (uploadOpen = true)}
      />
    {:else if query.view === 'grid'}
      <Grid
        {items}
        {selectedIds}
        canRename={canRenameFiles}
        {canMove}
        {canDelete}
        {canRestore}
        contextItemId={context?.item.id ?? null}
      {focusedItemId}
        dropTargetId={dropTargetId}
        rootDropActive={rootDropActive}
        onselect={selectItem}
        onopen={openItem}
        oncontextmenu={openContext}
        ondragstart={dragStart}
        ondragend={dragEnd}
        ondragover={dragOverFolder}
        ondrop={dropOnFolder}
        onrootdragover={dragOverRoot}
        onrootdrop={dropOnRoot}
        onkeydown={keyItem}
      />
    {:else}
      <List
        {items}
        {selectedIds}
        canRename={canRenameFiles}
        {canMove}
        {canDelete}
        {canRestore}
        contextItemId={context?.item.id ?? null}
      {focusedItemId}
        dropTargetId={dropTargetId}
        rootDropActive={rootDropActive}
        onselect={selectItem}
        onopen={openItem}
        oncontextmenu={openContext}
        ondragstart={dragStart}
        ondragend={dragEnd}
        ondragover={dragOverFolder}
        ondrop={dropOnFolder}
        onrootdragover={dragOverRoot}
        onrootdrop={dropOnRoot}
        onkeydown={keyItem}
      />
    {/if}
  </div>

  {#if pages > 1}
    <div class="mt-4 flex items-center justify-between text-xs text-foreground-muted">
      <span>Página {query.page} de {pages}</span>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={query.page <= 1}
          onclick={() => updateQuery({ page: query.page - 1 })}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          disabled={query.page >= pages}
          onclick={() => updateQuery({ page: query.page + 1 })}>Siguiente</Button
        >
      </div>
    </div>
  {/if}
    </section>
  </div>
</div>

<ExplorerOverlays
  {context}
  {renameItem}
  {moveItem}
  {deleteConfirmItem}
  {createOpen}
  {createName}
  {createSaving}
  {createAttempted}
  {uploadOpen}
  folderId={query.folder || null}
  {folders}
  {categories}
  {mutationBusy}
  {canFolder}
  {canRenameFiles}
  {canMove}
  {canDeleteFiles}
  {canRestore}
  onopen={openItem}
  onrename={(item) => (renameItem = item)}
  onmove={(item) => (moveItem = item)}
  ondelete={requestDelete}
  onrestore={(item) => void restoreItem(item)}
  oncontextclose={closeMenu}
  onrenameclose={() => (renameItem = null)}
  onrenameconfirm={rename}
  onmoveclose={() => (moveItem = null)}
  onmoveconfirm={(folderId) => moveItem ? void move(moveItem, folderId) : undefined}
  ondeleteclose={() => (deleteConfirmItem = null)}
  ondeleteconfirm={confirmDelete}
  oncreateclose={() => (createOpen = false)}
  oncreateNameChange={(value) => (createName = value)}
  oncreateAttempted={() => (createAttempted = true)}
  oncreate={createFolder}
  onuploadclose={() => (uploadOpen = false)}
  onuploadfinished={() => {
    uploadOpen = false;
    success = 'Documentos cargados correctamente.';
    void load(query);
  }}
/>

<style>
  .explorer-page-shell { position: relative; }

  .explorer-heading-copy, .explorer-heading-meta { position: relative; z-index: 1; }
  .explorer-heading-eyebrow { display: flex; align-items: center; gap: 0.5rem; color: rgb(var(--foreground-muted)); font-size: 0.75rem; font-weight: 600; }

  .explorer-heading-meta { display: flex; align-items: center; gap: var(--explorer-space-2); border-left: 1px solid rgb(var(--border)); padding-left: 1rem; color: rgb(var(--foreground-muted)); font-size: 0.75rem; }
  .explorer-heading-meta > div { display: flex; align-items: center; gap: var(--explorer-space-1); }
  .explorer-heading-meta-label { color: rgb(var(--foreground-subtle)); font-size: 0.6875rem; font-weight: 550; letter-spacing: 0.01em; }
  .explorer-heading-meta strong { color: rgb(var(--foreground)); font-family: 'Geist Mono', monospace; font-size: 0.8125rem; }
  .explorer-heading-meta-divider { width: 1px; height: var(--explorer-space-4); background: rgb(var(--border)); }
  .explorer-heading-meta kbd { border: 1px solid rgb(var(--border)); border-bottom-color: rgb(var(--border-strong)); border-radius: var(--explorer-radius-xs); background: rgb(var(--surface-elevated)); padding: 0.22rem 0.38rem; color: rgb(var(--foreground)); font-family: 'Geist Mono', monospace; font-size: 0.625rem; }
  .explorer-page-heading { position: relative; display: flex; align-items: flex-end; justify-content: space-between; gap: var(--explorer-space-5); border-bottom: 1px solid rgb(var(--border)); padding-bottom: var(--explorer-space-2); }

  .explorer-breadcrumb-wrap { margin-bottom: 1rem; overflow-x: auto; }
  .explorer-statusbar { display: flex; min-height: 2.25rem; align-items: center; justify-content: space-between; gap: 1rem; color: rgb(var(--foreground-muted)); }
  .explorer-status-count { color: rgb(var(--foreground)); font-size: 0.8125rem; font-weight: 650; }
  .explorer-filter-chips { display: flex; flex-wrap: wrap; align-items: center; gap: var(--explorer-space-1); margin-top: var(--explorer-space-2); }
  .explorer-filter-chip { min-height: 2.25rem; border: 1px solid rgb(var(--primary) / 0.24); border-radius: 999px; background: rgb(var(--primary) / 0.08); padding: 0 var(--explorer-space-2); color: rgb(var(--foreground)); font-size: 0.6875rem; font-weight: 650; }
  .explorer-filter-chip:hover { background: rgb(var(--primary) / 0.14); }
  .explorer-filter-chip:focus-visible, .explorer-filter-reset:focus-visible { outline: none; box-shadow: 0 0 0 2px rgb(var(--surface)), 0 0 0 4px rgb(var(--primary)); }
  .explorer-filter-reset { min-height: 2.25rem; padding: 0 0.45rem; color: rgb(var(--foreground-muted)); font-size: 0.6875rem; font-weight: 650; text-decoration: underline; text-underline-offset: 0.2em; }
  .explorer-workspace { display: flex; align-items: flex-start; gap: 1rem; }
  .explorer-content { min-width: 0; flex: 1 1 auto; }
  .explorer-loading-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(184px, 1fr)); gap: 0.75rem; }
  .explorer-selection-bar { display: flex; min-width: 0; width: 100%; align-items: center; justify-content: space-between; gap: var(--explorer-space-3); border: 1px solid rgb(var(--primary) / 0.22); border-radius: var(--explorer-radius-md); background: rgb(var(--surface-elevated)); padding: var(--explorer-space-1) var(--explorer-space-2); }
  .explorer-selection-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 0.75rem; }
  .explorer-selection-hint { color: rgb(var(--foreground-muted)); font-size: 0.6875rem; }
  .explorer-inline-action { min-height: 1.8rem; border-radius: var(--explorer-radius-sm); padding: 0.2rem 0.55rem; color: rgb(var(--primary)); font-size: 0.6875rem; font-weight: 700; }
  .explorer-inline-action:hover { background: rgb(var(--primary) / 0.1); }
  .explorer-inline-action-danger { color: rgb(var(--danger)); }
  .explorer-inline-action-danger:hover { background: rgb(var(--danger) / 0.1); }
  .explorer-selection-count { border-radius: 999px; background: rgb(var(--primary) / 0.1); padding: 0.25rem 0.55rem; color: rgb(var(--foreground)); font-size: 0.6875rem; font-weight: 650; }
  .explorer-shortcuts { color: rgb(var(--foreground-subtle)); }
  .explorer-success { color: rgb(var(--success)); font-size: 0.75rem; font-weight: 600; }
  .explorer-refreshing { margin-left: auto; color: rgb(var(--foreground-muted)); font-size: 0.6875rem; font-weight: 650; }
  @media (max-width: 900px) {
    .explorer-workspace { flex-direction: column; }
  }
  @media (max-width: 640px) {
    .explorer-loading-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .explorer-page-heading { align-items: flex-start; flex-direction: column; gap: var(--explorer-space-2); }
    .explorer-heading-meta { border-left: 0; padding-left: 0; }
    .explorer-statusbar { align-items: flex-start; flex-direction: column; gap: 0.35rem; }
  }
  .explorer-clear-selection { color: rgb(var(--foreground-muted)); font-size: 0.6875rem; font-weight: 600; text-decoration: underline; text-underline-offset: 0.2em; }
  .explorer-clear-selection:hover { color: rgb(var(--foreground)); }
  .explorer-clear-selection:focus-visible { outline: none; border-radius: var(--explorer-radius-xs); box-shadow: 0 0 0 2px rgb(var(--primary) / 0.7); }
</style>