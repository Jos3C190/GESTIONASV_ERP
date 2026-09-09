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
  import Modal from '$lib/components/ui/Modal.svelte';
  import DocumentBreadcrumbs from '$lib/features/documents/components/DocumentBreadcrumbs.svelte';
  import DocumentUploadQueue from '$lib/features/documents/components/DocumentUploadQueue.svelte';
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
  import ContextMenu from './ContextMenu.svelte';
  import RenameDialog from './RenameDialog.svelte';
  import MoveDialog from './MoveDialog.svelte';
  import EmptyState from './EmptyState.svelte';

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
  let uploadOpen = $state(false);
  let createOpen = $state(false);
  let createName = $state('');
  let createSaving = $state(false);
  let selectedIds = $state<Set<string>>(new Set());
  let selectionAnchorId = $state<string | null>(null);
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
  let createInput = $state<HTMLInputElement | undefined>(undefined);

  const canFolder = $derived(canExplorerAction('create-folder', permissions.hasPermission));
  const canMove = $derived(canExplorerAction('move', permissions.hasPermission));
  const canRename = $derived(canExplorerAction('rename', permissions.hasPermission));
  const canRenameFiles = $derived(permissions.hasPermission('documents:update'));
  const canDeleteFiles = $derived(canExplorerAction('delete', permissions.hasPermission));
  const canDelete = $derived(canFolder || canDeleteFiles);
  const canRestore = $derived(canExplorerAction('restore', permissions.hasPermission));
  const canUpload = $derived(canExplorerAction('upload', permissions.hasPermission));

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
    if (createOpen) createInput?.focus();
  });

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

  function keyItem(item: ExplorerItem, event: KeyboardEvent) {
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
      const target = event.currentTarget as HTMLElement | null;
      const rect = target?.getBoundingClientRect();
      contextInvoker = target;
      context = { item, x: rect?.left ?? 280, y: rect ? rect.bottom : 160 };
    } else if (action === 'close') {
      context = null;
    }
  }

  function draggedItem(event?: DragEvent): ExplorerItem | null {
    const id = event?.dataTransfer?.getData('text/plain') || draggingId;
    return id ? items.find((candidate) => candidate.id === id) ?? null : null;
  }

  function dragStart(item: ExplorerItem, event: DragEvent) {
    if (!canMove) return;
    draggingId = item.id;
    rootDropActive = false;
    event.dataTransfer?.setData('text/plain', item.id);
    event.dataTransfer?.setData('application/x-document-entry-kind', item.kind);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function dragEnd() {
    draggingId = null;
    dropTargetId = null;
    rootDropActive = false;
  }

  function dragOverFolder(folder: ExplorerItem, event: DragEvent) {
    const source = draggedItem(event);
    if (!source || !canMove || folder.kind !== 'folder') return;
    if (!canDropIntoFolder({ id: source.id, kind: source.kind, parentId: source.entry.parent_id }, folder.id)) {
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
    const source = draggedItem(event);
    dragEnd();
    if (!source || folder.kind !== 'folder') return;
    await move(source, folder.id);
  }

  function dragOverRoot(event: DragEvent) {
    const source = draggedItem(event);
    if (!source || !canMove) return;
    event.preventDefault();
    dropTargetId = null;
    rootDropActive = true;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  }

  async function dropOnRoot(event: DragEvent) {
    event.preventDefault();
    const source = draggedItem(event);
    dragEnd();
    if (source) await move(source, null);
  }

  async function move(item: ExplorerItem, parentId: string | null) {
    if (mutationBusy || !canMove) return;
    if (!canDropIntoFolder({ id: item.id, kind: item.kind, parentId: item.entry.parent_id }, parentId)) {
      error = 'El elemento ya está dentro de esa carpeta.';
      return;
    }
    mutationBusy = true;
    try {
      if (item.kind === 'folder') {
        await api.documents.general.moveFolder(item.id, parentId);
      } else {
        await api.documents.general.moveFile(item.document.id, parentId);
      }
      moveItem = null;
      success = item.name + ' se movió correctamente.';
      await load(query);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo mover el elemento.';
    } finally {
      mutationBusy = false;
    }
  }

  async function createFolder() {
    const name = createName.trim();
    if (!name || createSaving) return;
    createSaving = true;
    try {
      await api.documents.general.createFolder({ name, parent_id: query.folder || null });
      createName = '';
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
    const target = event.target as HTMLElement | null;
    if (target?.matches('input, select, textarea, [contenteditable="true"]')) return;
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
      contextInvoker = null;
      context = { item: selectedItem, x: 280, y: 160 };
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

<div class="mx-auto w-full max-w-[1600px] p-4 md:p-8">
<div class="mb-4">
    <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Espacio general</p>
    <h1 class="mt-1 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">General</h1>
    <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
      Archivos y carpetas compartidos de la empresa. Arrastra elementos para reorganizarlos.
    </p>
  </div>

  <DocumentBreadcrumbs
    items={breadcrumbs.slice(0, -1)}
    current={breadcrumbs.at(-1)?.label ?? 'General'}
  />

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
    oncreatefolder={() => (createOpen = true)}
    onupload={() => (uploadOpen = true)}
  />

<div class="mt-5 flex flex-wrap items-center justify-between gap-2 text-sm text-foreground-muted">
    <div class="flex items-center gap-3">
      <span class="font-medium text-foreground">{total} elemento{total === 1 ? '' : 's'}</span>
      {#if selectedIds.size > 0}<span>{selectedIds.size} seleccionado{selectedIds.size === 1 ? '' : 's'}</span>{/if}
    </div>
    <span class="hidden text-xs md:inline">Doble clic para abrir · Arrastra para mover · Clic derecho para más</span>
    {#if success}<span class="text-success" role="status">{success}</span>{/if}
  </div>

  {#if error}
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
    {#if loading}
      <div
        class="grid gap-2 rounded-2xl border border-border bg-surface-elevated p-3"
        aria-busy="true"
        aria-label="Cargando documentos generales"
      >
        {#each Array(7) as _}<div class="h-12 rounded-lg skeleton"></div>{/each}
      </div>
    {:else if items.length === 0}
      <EmptyState
        title={query.search ? 'No hay coincidencias' : 'Esta carpeta está vacía'}
        description={query.search
          ? 'Prueba con otro término o limpia la búsqueda.'
          : 'Crea una carpeta o carga el primer documento para comenzar.'}
        actionLabel={!query.search && canFolder ? 'Nueva carpeta' : undefined}
        onaction={() => (createOpen = true)}
        secondaryLabel={!query.search && canUpload ? 'Cargar documento' : undefined}
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
</div>

{#if context}
  <ContextMenu
    item={context.item}
    x={context.x}
    y={context.y}
    canRename={context.item.kind === 'folder' ? canFolder : canRenameFiles}
    {canMove}
    canDelete={context.item.kind === 'folder' ? canFolder : canDeleteFiles}
    {canRestore}
    onopen={() => openItem(context!.item)}
    onrename={() => (renameItem = context!.item)}
    onmove={() => (moveItem = context!.item)}
    ondelete={() => requestDelete(context!.item)}
    onrestore={() => void restoreItem(context!.item)}
    onclose={closeMenu}
  />
{/if}

{#if renameItem}
  <RenameDialog
    item={renameItem}
    saving={mutationBusy}
    onclose={() => (renameItem = null)}
    onconfirm={rename}
  />
{/if}

{#if moveItem}
  <MoveDialog
    item={moveItem}
    {folders}
    saving={mutationBusy}
    onclose={() => (moveItem = null)}
    onconfirm={(folderId) => void move(moveItem!, folderId)}
  />
{/if}

{#if createOpen}
  <Modal open={true} title="Nueva carpeta" onclose={() => (createOpen = false)}>
    {#snippet children()}
      <form
        class="space-y-4"
        onsubmit={(event) => {
          event.preventDefault();
          void createFolder();
        }}
      >
        <label class="block text-sm font-medium text-foreground" for="new-general-folder"
          >Nombre de la carpeta</label
        >
        <input
          id="new-general-folder"
          bind:this={createInput}
          bind:value={createName}
          maxlength="200"
          class="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        <div class="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" type="button" onclick={() => (createOpen = false)}
            >Cancelar</Button
          ><Button type="submit" disabled={createSaving || !createName.trim()}
            >{createSaving ? 'Creando…' : 'Crear carpeta'}</Button
          >
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if deleteConfirmItem}
  <Modal open={true} title="Enviar a la Papelera" onclose={() => (deleteConfirmItem = null)}>
    {#snippet children()}
      <div class="space-y-4">
        <p class="text-sm leading-6 text-foreground-muted">
          ¿Quieres enviar <strong class="font-semibold text-foreground">«{deleteConfirmItem!.name}»</strong>
          a la Papelera? {deleteConfirmItem!.kind === 'folder'
            ? 'Se incluirá todo su contenido y podrás restaurarlo como un árbol completo.'
            : 'El documento y sus versiones se conservarán para restaurarlo después.'}
        </p>
        <div class="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" type="button" onclick={() => (deleteConfirmItem = null)}
            >Cancelar</Button
          >
          <Button
            variant="danger"
            type="button"
            disabled={mutationBusy}
            onclick={() => void confirmDelete()}
            >{mutationBusy ? 'Enviando…' : 'Enviar a la Papelera'}</Button
          >
        </div>
      </div>
    {/snippet}
  </Modal>
{/if}
{#if uploadOpen}
  <Modal open={true} title="Cargar documentos" size="lg" onclose={() => (uploadOpen = false)}>
    {#snippet children()}
      <DocumentUploadQueue
        {categories}
        folderId={query.folder || null}
        onclose={() => (uploadOpen = false)}
        onfinished={() => {
          uploadOpen = false;
          void load(query);
        }}
      />
    {/snippet}
  </Modal>
{/if}
