<script lang="ts">
  import { onMount } from 'svelte';
  import {
    api,
    HttpError,
    type DocumentCategoryOut,
    type DocumentFolderOut,
    type DocumentRecordOut
  } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import DocumentList from '$lib/features/documents/components/DocumentList.svelte';
  import DocumentDetailPanel from '$lib/features/documents/components/DocumentDetailPanel.svelte';
  import DocumentFolderGrid from '$lib/features/documents/components/DocumentFolderGrid.svelte';
  import DocumentMetadataModal from '$lib/features/documents/components/DocumentMetadataModal.svelte';
  import DocumentUploadQueue from '$lib/features/documents/components/DocumentUploadQueue.svelte';
  import {
    DocumentBrowserOpenError,
    openDocumentInBrowser
  } from '$lib/features/documents/open-document';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  interface Props {
    employeeId: string;
    employeeName: string;
  }
  let { employeeId, employeeName }: Props = $props();
  let documents = $state<DocumentRecordOut[]>([]);
  let categories = $state<DocumentCategoryOut[]>([]);
  let folders = $state<DocumentFolderOut[]>([]);
  let page = $state(1);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let search = $state('');
  let categoryFilter = $state('');
  let statusFilter = $state('');
  let expiryFilter = $state('');
  let confidentialityFilter = $state<'internal' | 'restricted' | ''>('');
  let viewMode = $state<'grid' | 'table'>('grid');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showUpload = $state(false);
  let openingDocumentId = $state<string | null>(null);
  let versionDocument = $state<DocumentRecordOut | null>(null);
  let versions = $state<DocumentRecordOut[]>([]);
  let editDocument = $state<DocumentRecordOut | null>(null);
  let replaceDocument = $state<DocumentRecordOut | null>(null);
  let selectedDocument = $state<DocumentRecordOut | null>(null);

  const canRead = $derived(permissions.hasPermission('employee_documents:read'));
  const canUpload = $derived(permissions.hasPermission('employee_documents:upload'));
  const canUpdate = $derived(permissions.hasPermission('employee_documents:update'));
  const canDownload = $derived(permissions.hasPermission('employee_documents:download'));
  const canDelete = $derived(permissions.hasPermission('employee_documents:delete'));
  const canProcess = $derived(permissions.hasPermission('employee_documents:process'));

  async function load() {
    if (!canRead) {
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const [result, categoryResult, folderResult] = await Promise.all([
        api.documents.employeeList(employeeId, {
          page,
          size: 24,
          category_id: categoryFilter || undefined,
          search: search.trim() || undefined,
          status: statusFilter || undefined,
          confidentiality: confidentialityFilter || undefined,
          expires_within_days: expiryFilter ? Number(expiryFilter) : undefined
        }),
        api.documents.categories('employees'),
        api.documents.folders({ parent: 'employee', employee_id: employeeId, page: 1, size: 100 })
      ]);
      documents = result.items;
      meta = result.meta;
      categories = categoryResult;
      folders = folderResult.items;
    } catch (err) {
      error =
        err instanceof HttpError ? err.message : 'No se pudo cargar el expediente documental.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const id = employeeId;
    const _page = page;
    const _category = categoryFilter;
    const _status = statusFilter;
    const _search = search;
    const _expiry = expiryFilter;
    const _confidentiality = confidentialityFilter;
    void id;
    void _page;
    void _category;
    void _status;
    void _search;
    void _expiry;
    void _confidentiality;
    void load();
  });

  function resetAndLoad() {
    page = 1;
    void load();
  }

  function setViewMode(mode: 'grid' | 'table') {
    viewMode = mode;
    if (typeof window !== 'undefined')
      window.localStorage.setItem('employee-documents-view-mode', mode);
  }

  function folderHref(folder: DocumentFolderOut): string {
    return `/documents/employees/${employeeId}/categories/${folder.category_id}`;
  }

  onMount(() => {
    const saved = window.localStorage.getItem('employee-documents-view-mode');
    if (saved === 'grid' || saved === 'table') viewMode = saved;
  });

  async function download(document: DocumentRecordOut) {
    try {
      const result = await api.documents.downloadUrl(document.id, 'original', employeeId);
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo generar la descarga.';
    }
  }

  async function downloadOcr(document: DocumentRecordOut) {
    try {
      const result = await api.documents.downloadUrl(document.id, 'ocr', employeeId);
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo generar la descarga OCR.';
    }
  }

  async function openInBrowser(document: DocumentRecordOut): Promise<void> {
    if (openingDocumentId === document.id) return;
    openingDocumentId = document.id;
    error = null;
    try {
      await openDocumentInBrowser(document.id, employeeId);
    } catch (err) {
      error =
        err instanceof DocumentBrowserOpenError || err instanceof HttpError
          ? err.message
          : 'No se pudo abrir el documento en el navegador.';
    } finally {
      if (openingDocumentId === document.id) openingDocumentId = null;
    }
  }

  async function showVersions(document: DocumentRecordOut) {
    versionDocument = document;
    try {
      versions = await api.documents.versions(document.id, employeeId);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el historial.';
      versionDocument = null;
    }
  }

  function openEdit(document: DocumentRecordOut) {
    editDocument = document;
  }

  function openReplace(document: DocumentRecordOut) {
    replaceDocument = document;
  }

  function deleteDocument(document: DocumentRecordOut) {
    confirmation.request({
      kind: 'delete',
      title: 'Enviar documento a la papelera',
      description:
        'El documento seguirá conservado en el gestor central y podrá restaurarse después.',
      resourceName: document.title,
      confirmLabel: 'Enviar a papelera',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('documents', document.id, reason);
        await load();
      }
    });
  }
</script>

{#if canRead}
  <Card class="mt-5 p-6">
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold text-foreground">Expediente documental</h3>
          <span
            class="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary"
            >{documents.length}</span
          >
        </div>
        <p class="mt-1 text-xs text-foreground-muted">
          Contratos, identificaciones, formación y seguimiento de {employeeName}.
        </p>
      </div>
      {#if canUpload}<Button size="sm" class="min-h-11" onclick={() => (showUpload = true)}>Agregar documento</Button
        >{/if}
    </div>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-surface-muted/30 px-3 py-2.5">
      <p class="text-xs text-foreground-muted">
        Organiza este expediente por carpetas virtuales, sin cambiar el almacenamiento original.
      </p>
      <a
        href={`/documents/employees/${employeeId}`}
        class="inline-flex min-h-11 items-center rounded-lg px-3 text-xs font-medium text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        Abrir gestor documental
        <span class="ml-1" aria-hidden="true">→</span>
      </a>
    </div>
    <section class="mb-5" aria-labelledby="employee-document-folders-heading">
      <div class="mb-3 flex items-center justify-between gap-2">
        <div>
          <h4 id="employee-document-folders-heading" class="text-xs font-semibold text-foreground">
            Carpetas del expediente
          </h4>
          <p class="mt-0.5 text-[11px] text-foreground-muted">Categorías documentales disponibles.</p>
        </div>
        <span class="font-mono text-[11px] tabular-nums text-foreground-muted">{folders.length}</span>
      </div>
      <DocumentFolderGrid
        {folders}
        loading={loading}
        hrefFor={folderHref}
        emptyTitle="Sin categorías documentales"
        emptyDescription="Las categorías aparecerán cuando estén configuradas para empleados."
      />
    </section>
    <div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div class="rounded-lg bg-surface-muted/50 p-3">
        <p class="text-[11px] text-foreground-muted">Vigentes</p>
        <p class="mt-1 font-mono text-xl font-semibold text-foreground">
          {documents.filter(
            (item) => item.business_status === 'current' || item.business_status === 'active'
          ).length}
        </p>
      </div>
      <div class="rounded-lg bg-warning/5 p-3">
        <p class="text-[11px] text-foreground-muted">Por vencer</p>
        <p class="mt-1 font-mono text-xl font-semibold text-warning">
          {documents.filter((item) => item.business_status === 'expiring').length}
        </p>
      </div>
      <div class="rounded-lg bg-danger/5 p-3">
        <p class="text-[11px] text-foreground-muted">Vencidos</p>
        <p class="mt-1 font-mono text-xl font-semibold text-danger">
          {documents.filter((item) => item.business_status === 'expired').length}
        </p>
      </div>
      <div class="rounded-lg bg-primary/5 p-3">
        <p class="text-[11px] text-foreground-muted">Procesándose</p>
        <p class="mt-1 font-mono text-xl font-semibold text-primary">
          {documents.filter((item) => item.business_status === 'processing').length}
        </p>
      </div>
    </div>
    <div class="mb-4 rounded-xl border border-border p-3">
      <div class="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px_180px_180px]">
        <div>
          <label for="employee-document-search" class="sr-only">Buscar expediente</label>
          <input
            id="employee-document-search"
            bind:value={search}
            oninput={() => (page = 1)}
            placeholder="Buscar por título, nombre o referencia…"
            class="min-h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <select
          bind:value={categoryFilter}
          onchange={resetAndLoad}
          class="min-h-11 rounded-lg border border-border bg-surface px-3 text-xs text-foreground"
          ><option value="">Todas las categorías</option
          >{#each categories as category (category.id)}<option value={category.id}
              >{category.name}</option
            >{/each}</select
        >
        <select
          bind:value={statusFilter}
          onchange={resetAndLoad}
          class="min-h-11 rounded-lg border border-border bg-surface px-3 text-xs text-foreground"
          ><option value="">Todos los estados</option><option value="current">Vigentes</option
          ><option value="expiring">Por vencer</option><option value="expired">Vencidos</option
          ><option value="processing">Procesando</option></select
        >
        <select
          bind:value={expiryFilter}
          onchange={resetAndLoad}
          class="min-h-11 rounded-lg border border-border bg-surface px-3 text-xs text-foreground"
          ><option value="">Cualquier vencimiento</option><option value="7">Próximos 7 días</option
          ><option value="30">Próximos 30 días</option><option value="60">Próximos 60 días</option
          ><option value="90">Próximos 90 días</option></select
        >
        <select
          bind:value={confidentialityFilter}
          onchange={resetAndLoad}
          class="min-h-11 rounded-lg border border-border bg-surface px-3 text-xs text-foreground"
          aria-label="Filtrar por visibilidad"
          ><option value="">Toda visibilidad</option><option value="restricted">Restringidos</option
          ><option value="internal">Internos</option></select
        >
      </div>
      <div class="mt-3 flex items-center justify-end gap-2 border-t border-border pt-3">
        <span class="text-xs text-foreground-muted">Vista</span>
        <button
          type="button"
          aria-label="Vista de cuadrícula"
          aria-pressed={viewMode === 'grid'}
          class="min-h-11 min-w-11 rounded-md px-2 py-1 text-xs {viewMode === 'grid'
            ? 'bg-primary/10 text-primary'
            : 'text-foreground-muted hover:text-foreground'}"
          onclick={() => setViewMode('grid')}>▦</button
        ><button
          type="button"
          aria-label="Vista de tabla"
          aria-pressed={viewMode === 'table'}
          class="min-h-11 min-w-11 rounded-md px-2 py-1 text-xs {viewMode === 'table'
            ? 'bg-primary/10 text-primary'
            : 'text-foreground-muted hover:text-foreground'}"
          onclick={() => setViewMode('table')}>☷</button
        >
      </div>
    </div>
    {#if error}<div
        class="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
        role="alert"
      >
        <span>{error}</span>
        <Button variant="ghost" size="sm" class="min-h-11 text-danger" onclick={() => void load()}>Reintentar</Button>
      </div>{/if}
    {#if openingDocumentId}<p class="sr-only" role="status" aria-live="polite">Abriendo documento en una nueva pestaña…</p>{/if}
    <DocumentList
      {documents}
      {loading}
      {canDownload}
      {canUpdate}
      canReplace={canUpload}
      {canProcess}
      {canDelete}
      {viewMode}
      {openingDocumentId}
      ondownload={download}
      onocrdownload={downloadOcr}
      onopenbrowser={(document) => void openInBrowser(document)}
      ondetail={(document) => (selectedDocument = document)}
      onupdate={openEdit}
      onreplace={openReplace}
      onversions={showVersions}
      ondelete={deleteDocument}
      onretry={(document) =>
        api.documents
          .retryOcr(document.id, employeeId)
          .then(load)
          .catch(
            (err) =>
              (error = err instanceof HttpError ? err.message : 'No se pudo reintentar el OCR.')
          )}
    />
    {#if meta && meta.pages > 1}<div
        class="mt-4 flex items-center justify-between border-t border-border pt-3"
      >
        <p class="text-xs text-foreground-muted">Página {meta.page} de {meta.pages}</p>
        <div class="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            class="min-h-11"
            disabled={page <= 1}
            onclick={() => {
              page -= 1;
            }}>Anterior</Button
          ><Button
            variant="secondary"
            size="sm"
            class="min-h-11"
            disabled={page >= meta.pages}
            onclick={() => {
              page += 1;
            }}>Siguiente</Button
          >
        </div>
      </div>{/if}
  </Card>
  {#if selectedDocument}<DocumentDetailPanel
      document={selectedDocument}
      onclose={() => (selectedDocument = null)}
      ondownload={canDownload ? download : undefined}
      onocrdownload={canDownload ? downloadOcr : undefined}
      onopenbrowser={canDownload ? (document) => void openInBrowser(document) : undefined}
      opening={openingDocumentId === selectedDocument.id}
      onversions={showVersions}
      onupdate={canUpdate ? openEdit : undefined}
      onreplace={canUpload ? openReplace : undefined}
    />{/if}
  {#if showUpload}<Modal
      open={showUpload}
      title="Agregar al expediente"
      size="lg"
      onclose={() => (showUpload = false)}
      ><DocumentUploadQueue
        {categories}
        {employeeId}
        onclose={() => (showUpload = false)}
        onfinished={() => {
          showUpload = false;
          void load();
        }}
      /></Modal
    >{/if}
  {#if editDocument}<DocumentMetadataModal
      document={editDocument}
      {categories}
      {employeeId}
      onclose={() => (editDocument = null)}
      onsaved={() => {
        editDocument = null;
        void load();
      }}
    />{/if}
  {#if replaceDocument}<Modal
      open={true}
      title={'Reemplazar · ' + replaceDocument.title}
      size="lg"
      onclose={() => (replaceDocument = null)}
      ><DocumentUploadQueue
        {categories}
        {employeeId}
        replaceDocumentId={replaceDocument.id}
        onclose={() => (replaceDocument = null)}
        onfinished={() => {
          replaceDocument = null;
          void load();
        }}
      /></Modal
    >{/if}
  {#if versionDocument}<Modal
      open={true}
      title={`Versiones · ${versionDocument.title}`}
      size="lg"
      onclose={() => (versionDocument = null)}
      ><div class="space-y-2">
        {#each versions as item (item.id)}<div
            class="flex items-center justify-between rounded-lg border border-border p-3"
          >
            <div>
              <p class="text-sm font-medium text-foreground">
                Versión {item.version_number}{item.is_current ? ' · vigente' : ''}
              </p>
              <p class="text-xs text-foreground-muted">{item.original_filename}</p>
            </div>
            {#if item.technical_status === 'active'}<Button
                variant="ghost"
                size="sm"
                class="min-h-11"
                onclick={() => download(item)}>Descargar</Button
              >{/if}
          </div>{/each}
      </div></Modal
    >{/if}
{/if}
