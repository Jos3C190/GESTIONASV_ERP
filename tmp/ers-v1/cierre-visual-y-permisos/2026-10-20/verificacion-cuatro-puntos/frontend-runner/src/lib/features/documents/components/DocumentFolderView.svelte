<script lang="ts">
  import { afterNavigate, goto } from '$app/navigation';
  import { page as currentPage } from '$app/state';
  import { onMount } from 'svelte';
  import {
    api,
    HttpError,
    type DocumentBreadcrumbOut,
    type DocumentCategoryOut,
    type DocumentFolderOut,
    type DocumentRecordOut,
    type EmployeeOut
  } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import DocumentBreadcrumbs from './DocumentBreadcrumbs.svelte';
  import DocumentDetailPanel from './DocumentDetailPanel.svelte';
  import DocumentFolderGrid from './DocumentFolderGrid.svelte';
  import DocumentLibraryToolbar from './DocumentLibraryToolbar.svelte';
  import DocumentList from './DocumentList.svelte';
  import DocumentMetadataModal from './DocumentMetadataModal.svelte';
  import DocumentRecentFiles from './DocumentRecentFiles.svelte';
  import DocumentUploadQueue from './DocumentUploadQueue.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import {
    DocumentBrowserOpenError,
    openDocumentInBrowser
  } from '$lib/features/documents/open-document';

  export type DocumentFolderViewScope = 'root' | 'general' | 'employees' | 'employee' | 'category';

  interface Props {
    scope: DocumentFolderViewScope;
    employeeId?: string;
    categoryId?: string;
    categoryModule?: 'general' | 'employees';
  }

  let { scope, employeeId, categoryId, categoryModule }: Props = $props();

  let folders = $state<DocumentFolderOut[]>([]);
  let documents = $state<DocumentRecordOut[]>([]);
  let recentDocuments = $state<DocumentRecordOut[]>([]);
  let categories = $state<DocumentCategoryOut[]>([]);
  let breadcrumbs = $state<DocumentBreadcrumbOut[]>([{ label: 'Documentos', href: '/documents' }]);
  let loading = $state(true);
  let filesLoading = $state(false);
  let error = $state<string | null>(null);
  let page = $state(1);
  let pageSize = $state(24);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let search = $state(currentPage.url.searchParams.get('search') ?? '');
  let statusFilter = $state(currentPage.url.searchParams.get('status') ?? '');
  let expiryFilter = $state(currentPage.url.searchParams.get('expires') ?? '');
  let categoryFilter = $state(currentPage.url.searchParams.get('category') ?? '');
  let confidentialityFilter = $state<'internal' | 'restricted' | ''>(
    parseConfidentiality(currentPage.url.searchParams.get('visibility'))
  );
  let sort = $state<'updated' | 'name' | 'expiry' | 'size'>(
    parseSort(currentPage.url.searchParams.get('sort'))
  );
  let viewMode = $state<'grid' | 'table'>(
    currentPage.url.searchParams.get('view') === 'grid' ? 'grid' : 'table'
  );
  let showFilters = $state(false);
  let showUpload = $state(false);
  let uploadDestination = $state<'general' | 'employee'>('general');
  let uploadEmployeeId = $state('');
  let uploadEmployees = $state<EmployeeOut[]>([]);
  let uploadEmployeesLoading = $state(false);
  let selectedDocument = $state<DocumentRecordOut | null>(null);
  let editDocument = $state<DocumentRecordOut | null>(null);
  let replaceDocument = $state<DocumentRecordOut | null>(null);
  let versionDocument = $state<DocumentRecordOut | null>(null);
  let versions = $state<DocumentRecordOut[]>([]);
  let versionsLoading = $state(false);
  let openingDocumentId = $state<string | null>(null);
  let requestController: AbortController | null = null;

  function parseSort(value: string | null): 'updated' | 'name' | 'expiry' | 'size' {
    return value === 'name' || value === 'expiry' || value === 'size' ? value : 'updated';
  }

  function parseConfidentiality(value: string | null): 'internal' | 'restricted' | '' {
    return value === 'internal' || value === 'restricted' ? value : '';
  }

  function applyQueryFromUrl(url: URL) {
    search = url.searchParams.get('search') ?? '';
    statusFilter = url.searchParams.get('status') ?? '';
    expiryFilter = url.searchParams.get('expires') ?? '';
    categoryFilter = url.searchParams.get('category') ?? '';
    confidentialityFilter = parseConfidentiality(url.searchParams.get('visibility'));
    sort = parseSort(url.searchParams.get('sort'));
    if (url.searchParams.has('view')) {
      viewMode = url.searchParams.get('view') === 'grid' ? 'grid' : 'table';
    }
    page = 1;
  }

  const canGeneralUpload = $derived(permissions.hasPermission('documents:upload'));
  const canEmployeeUpload = $derived(permissions.hasPermission('employee_documents:upload'));
  const canCategories = $derived(
    permissions.hasAnyPermission(['documents:categories', 'employee_documents:manage_categories'])
  );

  const folderParent = $derived(
    scope === 'root'
      ? 'root'
      : scope === 'category'
        ? categoryModule === 'employees'
          ? 'employee'
          : 'general'
        : scope
  );
  const currentEmployeeId = $derived(
    scope === 'employee' || (scope === 'category' && categoryModule === 'employees')
      ? employeeId
      : undefined
  );
  const canUploadInContext = $derived(
    scope === 'employee' || (scope === 'category' && categoryModule === 'employees')
      ? canEmployeeUpload
      : scope === 'general' || (scope === 'category' && categoryModule === 'general')
        ? canGeneralUpload
        : canGeneralUpload || canEmployeeUpload
  );
  const visibleCategoryModule = $derived<'general' | 'employees' | undefined>(
    scope === 'general'
      ? 'general'
      : scope === 'employee' || scope === 'employees'
        ? 'employees'
        : undefined
  );
  const activeFilterCount = $derived(
    (statusFilter ? 1 : 0) +
      (expiryFilter ? 1 : 0) +
      (scope === 'category' || !categoryFilter ? 0 : 1) +
      (confidentialityFilter ? 1 : 0)
  );

  let sortedDocuments = $derived.by(() => {
    const result = [...documents];
    if (sort === 'name') return result.sort((a, b) => a.title.localeCompare(b.title, 'es'));
    if (sort === 'size') return result.sort((a, b) => b.size_bytes - a.size_bytes);
    if (sort === 'expiry') {
      return result.sort((a, b) => {
        const left = a.expires_on ? Date.parse(a.expires_on) : Number.MAX_SAFE_INTEGER;
        const right = b.expires_on ? Date.parse(b.expires_on) : Number.MAX_SAFE_INTEGER;
        return left - right;
      });
    }
    return result.sort((a, b) => Date.parse(b.updated_at ?? '') - Date.parse(a.updated_at ?? ''));
  });

  const stats = $derived.by(() => ({
    active: folders.reduce((total, folder) => total + folder.active_count, 0),
    expiring: folders.reduce((total, folder) => total + folder.expiring_count, 0),
    expired: folders.reduce((total, folder) => total + folder.expired_count, 0),
    processing: folders.reduce(
      (total, folder) => total + Math.max(folder.document_count - folder.active_count, 0),
      0
    )
  }));

  const heading = $derived.by(() => {
    if (scope === 'root') return 'Documentos';
    if (scope === 'general') return 'General';
    if (scope === 'employees') return 'Empleados';
    if (scope === 'employee') return breadcrumbs.at(-1)?.label ?? 'Expediente del empleado';
    return folders.find((item) => item.category_id === categoryId)?.name ?? 'Documentos';
  });

  const description = $derived.by(() => {
    if (scope === 'root')
      return 'Un espacio claro para consultar y organizar los archivos autorizados.';
    if (scope === 'general')
      return 'Documentos compartidos de la empresa, organizados por categoría.';
    if (scope === 'employees')
      return 'Cada empleado tiene una carpeta con su expediente documental.';
    if (scope === 'employee') return 'Categorías y archivos que forman parte de este expediente.';
    return 'Archivos clasificados en esta categoría documental.';
  });

  const contentSummary = $derived.by(() => {
    if (loading) return 'Cargando...';
    if (scope === 'employees') {
      return `${folders.length} empleado${folders.length === 1 ? '' : 's'}`;
    }

    const total = meta?.total ?? folders.reduce((sum, folder) => sum + folder.document_count, 0);
    return `${total} documento${total === 1 ? '' : 's'}`;
  });

  function employeeFolderHref(folder: DocumentFolderOut): string {
    if (folder.kind === 'module') return `/documents/${folder.module}`;
    if (folder.kind === 'employee') return `/documents/employees/${folder.employee_id}`;
    if (folder.module === 'employees') {
      return `/documents/employees/${folder.employee_id}/categories/${folder.category_id}`;
    }
    return `/documents/general/categories/${folder.category_id}`;
  }

  function fileEmployeeId(document: DocumentRecordOut): string | undefined {
    return document.module === 'employees' ? (document.owner_id ?? undefined) : undefined;
  }

  function documentPermission(document: DocumentRecordOut, action: string): boolean {
    const family = document.module === 'employees' ? 'employee_documents' : 'documents';
    return permissions.hasPermission(`${family}:${action}`);
  }

  async function load() {
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    loading = true;
    error = null;
    try {
      const folderResult = await api.documents.folders({
        parent: folderParent,
        employee_id: currentEmployeeId,
        // A category route must keep its breadcrumb/category context even
        // when the global search term only matches a file name.
        search: scope === 'category' ? undefined : search.trim() || undefined,
        page: 1,
        size: 100,
        signal: controller.signal
      });
      if (controller.signal.aborted) return;
      folders = folderResult.items;
      const selectedCategory =
        scope === 'category' && categoryId
          ? folderResult.items.find((item) => item.category_id === categoryId)
          : undefined;
      breadcrumbs = selectedCategory
        ? [
            ...folderResult.breadcrumbs,
            {
              label: selectedCategory.name,
              href:
                categoryModule === 'employees'
                  ? `/documents/employees/${employeeId}/categories/${categoryId}`
                  : `/documents/general/categories/${categoryId}`
            }
          ]
        : folderResult.breadcrumbs;

      const categoryResult = await api.documents.categories(undefined, controller.signal);
      if (controller.signal.aborted) return;
      categories = categoryResult;

      const shouldLoadFiles =
        scope === 'root' || scope === 'general' || scope === 'employee' || scope === 'category';
      if (!shouldLoadFiles) {
        documents = [];
        recentDocuments = [];
        meta = null;
        return;
      }

      filesLoading = true;
      const module =
        scope === 'general' || (scope === 'category' && categoryModule === 'general')
          ? 'general'
          : scope === 'category' && categoryModule === 'employees'
            ? 'employees'
            : undefined;
      const common = {
        page: scope === 'root' ? 1 : page,
        size: scope === 'root' ? 8 : pageSize,
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        confidentiality: confidentialityFilter || undefined,
        expires_within_days: expiryFilter ? Number(expiryFilter) : undefined,
        signal: controller.signal
      };
      const result =
        module === 'employees' || scope === 'employee'
          ? await api.documents.employeeList(currentEmployeeId ?? employeeId ?? '', {
              ...common,
              category_id: scope === 'category' ? categoryId : categoryFilter || undefined
            })
          : await api.documents.list({
              ...common,
              module: module ?? undefined,
              category_id: scope === 'category' ? categoryId : categoryFilter || undefined
            });
      if (controller.signal.aborted) return;
      documents = result.items;
      meta = result.meta;
      recentDocuments = scope === 'root' ? result.items : [];
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (err instanceof HttpError && err.code === 'http_error' && err.status === 0) return;
      error =
        err instanceof HttpError ? err.message : 'No se pudo cargar la biblioteca documental.';
    } finally {
      if (!controller.signal.aborted) {
        loading = false;
        filesLoading = false;
      }
    }
  }

  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const key = `${scope}:${employeeId ?? ''}:${categoryId ?? ''}:${categoryModule ?? ''}:${search}:${statusFilter}:${expiryFilter}:${categoryFilter}:${confidentialityFilter}:${page}:${pageSize}`;
    void key;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void load(), search.trim() ? 240 : 0);
    return () => {
      if (searchTimer) clearTimeout(searchTimer);
    };
  });

  onMount(() => {
    const saved = window.localStorage.getItem('documents-library-view-mode');
    if (!currentPage.url.searchParams.has('view') && (saved === 'grid' || saved === 'table')) {
      viewMode = saved;
    }
    return () => requestController?.abort();
  });

  // Keep browser Back/Forward and shared deep links authoritative.  SvelteKit
  // preserves this component between query-only navigations, so local filter
  // state must be refreshed after every completed navigation.
  afterNavigate(({ to }) => {
    if (to) applyQueryFromUrl(to.url);
  });

  function setViewMode(mode: 'grid' | 'table') {
    viewMode = mode;
    if (typeof window !== 'undefined')
      window.localStorage.setItem('documents-library-view-mode', mode);
    void syncQuery();
  }

  function setSearch(value: string) {
    search = value;
    page = 1;
    void syncQuery();
  }

  function setSort(value: 'updated' | 'name' | 'expiry' | 'size') {
    sort = value;
    void syncQuery();
  }

  function resetFilters() {
    statusFilter = '';
    expiryFilter = '';
    categoryFilter = '';
    confidentialityFilter = '';
    page = 1;
    void syncQuery();
  }

  async function syncQuery() {
    if (typeof window === 'undefined') return;
    const query = new URLSearchParams();
    if (search.trim()) query.set('search', search.trim());
    if (statusFilter) query.set('status', statusFilter);
    if (expiryFilter) query.set('expires', expiryFilter);
    if (categoryFilter) query.set('category', categoryFilter);
    if (confidentialityFilter) query.set('visibility', confidentialityFilter);
    if (sort !== 'updated') query.set('sort', sort);
    if (viewMode !== 'table') query.set('view', viewMode);
    const next = query.toString();
    const current = currentPage.url.search;
    if (next !== current.replace(/^\?/, '')) {
      await goto(`${currentPage.url.pathname}${next ? `?${next}` : ''}`, {
        replaceState: true,
        noScroll: true,
        keepFocus: true
      });
    }
  }

  async function openUpload() {
    if (scope === 'employee' || (scope === 'category' && categoryModule === 'employees')) {
      uploadDestination = 'employee';
      uploadEmployeeId = employeeId ?? '';
    } else if (scope === 'general' || (scope === 'category' && categoryModule === 'general')) {
      uploadDestination = 'general';
      uploadEmployeeId = '';
    } else {
      uploadDestination = canGeneralUpload ? 'general' : 'employee';
      uploadEmployeeId = '';
    }
    if (uploadDestination === 'employee' && canEmployeeUpload) await ensureUploadEmployees();
    showUpload = true;
  }

  async function ensureUploadEmployees() {
    if (uploadEmployees.length > 0 || uploadEmployeesLoading || !canEmployeeUpload) return;
    uploadEmployeesLoading = true;
    try {
      const result = await api.employees.list({ page: 1, size: 100, status: 'activo' });
      uploadEmployees = result.items;
      if (!uploadEmployeeId) uploadEmployeeId = result.items[0]?.id ?? '';
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los empleados.';
    } finally {
      uploadEmployeesLoading = false;
    }
  }

  $effect(() => {
    const destination = uploadDestination;
    const shouldLoadEmployees = scope === 'root' && destination === 'employee' && showUpload;
    if (shouldLoadEmployees) void ensureUploadEmployees();
  });

  function uploadDestinationPath(): string {
    if (uploadDestination === 'general') {
      const category =
        scope === 'category' && categoryModule === 'general'
          ? categories.find((item) => item.id === categoryId)?.name
          : undefined;
      return category ? `General / ${category}` : 'General';
    }
    const employeeFromCrumb =
      scope === 'category' && categoryModule === 'employees'
        ? breadcrumbs.at(-2)?.label
        : scope === 'employee'
          ? breadcrumbs.at(-1)?.label
          : undefined;
    const selectedEmployee = uploadEmployees.find((item) => item.id === uploadEmployeeId);
    const employee =
      employeeFromCrumb ??
      (selectedEmployee
        ? `${selectedEmployee.first_name} ${selectedEmployee.last_name}`.trim()
        : 'Empleado');
    const category =
      scope === 'category' && categoryModule === 'employees'
        ? categories.find((item) => item.id === categoryId)?.name
        : undefined;
    return `Empleados / ${employee || 'Empleado'}${category ? ` / ${category}` : ''}`;
  }

  async function download(document: DocumentRecordOut, variant: 'original' | 'ocr' = 'original') {
    try {
      const result = await api.documents.downloadUrl(
        document.id,
        variant,
        fileEmployeeId(document)
      );
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo generar la descarga.';
    }
  }

  async function openInBrowser(document: DocumentRecordOut): Promise<void> {
    if (openingDocumentId === document.id) return;
    openingDocumentId = document.id;
    error = null;
    try {
      await openDocumentInBrowser(document.id, fileEmployeeId(document));
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
    versionsLoading = true;
    try {
      versions = await api.documents.versions(document.id, fileEmployeeId(document));
    } catch (err) {
      error =
        err instanceof HttpError ? err.message : 'No se pudo cargar el historial de versiones.';
      versionDocument = null;
    } finally {
      versionsLoading = false;
    }
  }

  function deleteDocument(document: DocumentRecordOut) {
    confirmation.request({
      kind: 'delete',
      title: 'Enviar documento a la papelera',
      description:
        'El documento dejará de estar disponible, pero podrá restaurarse desde la Papelera.',
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

  function retryOcr(document: DocumentRecordOut) {
    api.documents
      .retryOcr(document.id, fileEmployeeId(document))
      .then(() => load())
      .catch((err) => {
        error = err instanceof HttpError ? err.message : 'No se pudo reintentar el OCR.';
      });
  }
</script>

<svelte:head><title>{heading} — GestionaSV</title></svelte:head>

<div class="document-library-view p-6 md:p-8">
  {#if scope !== 'root'}
    <DocumentBreadcrumbs items={breadcrumbs.slice(0, -1)} current={breadcrumbs.at(-1)?.label} />
  {/if}

  <header class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div class="min-w-0">
      <h1 class="sr-only">{heading}</h1>
      <p class="text-sm text-foreground-muted">
        {contentSummary}
        <span class="hidden text-foreground-subtle md:inline"> · {description}</span>
      </p>
    </div>
    <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
      {#if scope === 'employee' && employeeId}
        <a
          href={`/employees/${employeeId}`}
          class="inline-flex min-h-9 items-center rounded-lg border border-border px-3 text-xs font-medium text-foreground-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >Abrir expediente del empleado</a
        >
      {/if}
      {#if canCategories}<a
          href="/documents/categories"
          class="inline-flex min-h-9 items-center rounded-lg border border-border px-3 text-xs font-medium text-foreground-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >Categorías</a
        >{/if}
      {#if canUploadInContext}<Button size="sm" class="min-h-9" onclick={openUpload}
          >Cargar documento</Button
        >{/if}
    </div>
  </header>

  {#if scope === 'root' || scope === 'general' || scope === 'employee'}
    <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card class="h-[120px] rounded-xl p-4 shadow-sm md:p-5"
        ><p class="text-[11px] text-foreground-muted">Vigentes</p>
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">
          {stats.active}
        </p></Card
      >
      <Card class="h-[120px] rounded-xl p-4 shadow-sm md:p-5"
        ><p class="text-[11px] text-foreground-muted">Por vencer</p>
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-warning">
          {stats.expiring}
        </p></Card
      >
      <Card class="h-[120px] rounded-xl p-4 shadow-sm md:p-5"
        ><p class="text-[11px] text-foreground-muted">Vencidos</p>
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-danger">
          {stats.expired}
        </p></Card
      >
      <Card class="h-[120px] rounded-xl p-4 shadow-sm md:p-5"
        ><p class="text-[11px] text-foreground-muted">En proceso</p>
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-primary">
          {stats.processing}
        </p></Card
      >
    </div>
  {/if}

  <div class="mb-5">
    <DocumentLibraryToolbar
      {search}
      onsearch={setSearch}
      {sort}
      onsort={setSort}
      {viewMode}
      onviewmode={setViewMode}
      filterCount={activeFilterCount}
      filtersOpen={showFilters}
      onfilters={() => (showFilters = !showFilters)}
    />
    {#if showFilters}
      <div
        id="document-library-filters"
        class="mt-2 grid grid-cols-1 gap-3 rounded-2xl border border-border bg-surface-elevated p-4 sm:grid-cols-2 lg:grid-cols-4"
        aria-label="Filtros documentales"
      >
        <label
          class="flex flex-col gap-1 text-[11px] font-medium text-foreground-muted"
          for="folder-status"
          >Estado<select
            id="folder-status"
            bind:value={statusFilter}
            onchange={() => {
              page = 1;
              void syncQuery();
            }}
            class="min-h-11 rounded-xl border border-border bg-surface px-3 text-xs text-foreground"
            ><option value="">Todos</option><option value="current">Vigentes</option><option
              value="expiring">Por vencer</option
            ><option value="expired">Vencidos</option><option value="processing">En proceso</option
            ></select
          ></label
        >
        <label
          class="flex flex-col gap-1 text-[11px] font-medium text-foreground-muted"
          for="folder-expiry"
          >Vencimiento<select
            id="folder-expiry"
            bind:value={expiryFilter}
            onchange={() => {
              page = 1;
              void syncQuery();
            }}
            class="min-h-11 rounded-xl border border-border bg-surface px-3 text-xs text-foreground"
            ><option value="">Cualquier fecha</option><option value="7">Próximos 7 días</option
            ><option value="30">Próximos 30 días</option><option value="90">Próximos 90 días</option
            ></select
          ></label
        >
        {#if scope !== 'category'}
          <label
            class="flex flex-col gap-1 text-[11px] font-medium text-foreground-muted"
            for="folder-category"
            >Categoría<select
              id="folder-category"
              bind:value={categoryFilter}
              onchange={() => {
                page = 1;
                void syncQuery();
              }}
              class="min-h-11 rounded-xl border border-border bg-surface px-3 text-xs text-foreground"
              ><option value="">Todas</option
              >{#each categories.filter((item) => !visibleCategoryModule || item.module === visibleCategoryModule) as category (category.id)}<option
                  value={category.id}>{category.name}</option
                >{/each}</select
            ></label
          >
        {/if}
        <label
          class="flex flex-col gap-1 text-[11px] font-medium text-foreground-muted"
          for="folder-visibility"
          >Visibilidad<select
            id="folder-visibility"
            bind:value={confidentialityFilter}
            onchange={() => {
              page = 1;
              void syncQuery();
            }}
            class="min-h-11 rounded-xl border border-border bg-surface px-3 text-xs text-foreground"
            ><option value="">Todas</option><option value="restricted">Restringidos</option><option
              value="internal">Internos</option
            ></select
          ></label
        >
        <div class="flex items-end">
          <Button
            variant="ghost"
            size="sm"
            class="min-h-11"
            onclick={resetFilters}
            disabled={activeFilterCount === 0}>Limpiar filtros</Button
          >
        </div>
      </div>
    {/if}
  </div>

  {#if error}<div
      class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      <span>{error}</span><Button
        variant="ghost"
        size="sm"
        class="min-h-11 text-danger"
        onclick={() => void load()}>Reintentar</Button
      >
    </div>{/if}

  {#if scope !== 'category'}
    <section class="mb-8" aria-labelledby="folders-heading">
      <div class="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 id="folders-heading" class="text-sm font-semibold text-foreground">
            {scope === 'root' ? 'Carpetas' : scope === 'employees' ? 'Empleados' : 'Categorías'}
          </h2>
          <p class="mt-0.5 text-xs text-foreground-muted">
            {scope === 'employees'
              ? 'Abre una carpeta para consultar el expediente.'
              : 'Organización virtual de tus documentos.'}
          </p>
        </div>
        {#if meta && scope === 'employees' && meta.pages > 1}<span
            class="font-mono text-xs tabular-nums text-foreground-muted">{meta.total}</span
          >{/if}
      </div>
      <DocumentFolderGrid
        {folders}
        {loading}
        hrefFor={employeeFolderHref}
        emptyTitle={scope === 'employees'
          ? 'No hay empleados visibles'
          : 'No hay carpetas disponibles'}
        emptyDescription="Las carpetas aparecerán cuando existan elementos autorizados."
      />
    </section>
  {/if}

  {#if activeFilterCount > 0}
    <div class="mb-5 flex flex-wrap items-center gap-2" aria-label="Filtros activos">
      {#if statusFilter}<button
          type="button"
          class="inline-flex min-h-9 items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-3 text-[11px] font-medium text-primary"
          onclick={() => {
            statusFilter = '';
            page = 1;
            void syncQuery();
          }}>Estado: {statusFilter}<span aria-hidden="true">×</span></button
        >{/if}
      {#if expiryFilter}<button
          type="button"
          class="inline-flex min-h-9 items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-3 text-[11px] font-medium text-primary"
          onclick={() => {
            expiryFilter = '';
            page = 1;
            void syncQuery();
          }}>Vence en {expiryFilter} días<span aria-hidden="true">×</span></button
        >{/if}
      {#if categoryFilter && scope !== 'category'}<button
          type="button"
          class="inline-flex min-h-9 items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-3 text-[11px] font-medium text-primary"
          onclick={() => {
            categoryFilter = '';
            page = 1;
            void syncQuery();
          }}
          >Categoría: {categories.find((item) => item.id === categoryFilter)?.name ??
            'Seleccionada'}<span aria-hidden="true">×</span></button
        >{/if}
      {#if confidentialityFilter}<button
          type="button"
          class="inline-flex min-h-9 items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-3 text-[11px] font-medium text-primary"
          onclick={() => {
            confidentialityFilter = '';
            page = 1;
            void syncQuery();
          }}
          >Visibilidad: {confidentialityFilter === 'restricted' ? 'Restringidos' : 'Internos'}<span
            aria-hidden="true">×</span
          ></button
        >{/if}
    </div>
  {/if}

  {#if scope === 'root'}
    <DocumentRecentFiles
      documents={recentDocuments}
      loading={filesLoading || loading}
      onopen={(document) => (selectedDocument = document)}
    />
  {:else if scope !== 'employees'}
    <section aria-labelledby="folder-files-heading">
      <div class="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 id="folder-files-heading" class="text-sm font-semibold text-foreground">
            {scope === 'employee' ? 'Archivos del expediente' : 'Archivos'}
          </h2>
          <p class="mt-0.5 text-xs text-foreground-muted">
            {meta?.total ?? documents.length} documento(s) en esta ubicación.
          </p>
        </div>
      </div>
      {#if openingDocumentId}<p class="sr-only" role="status" aria-live="polite">
          Abriendo documento en una nueva pestaña…
        </p>{/if}
      <DocumentList
        documents={sortedDocuments}
        loading={filesLoading || loading}
        canDownload={permissions.hasAnyPermission([
          'documents:download',
          'employee_documents:download'
        ])}
        canDownloadDocument={(document) => documentPermission(document, 'download')}
        canUpdate={permissions.hasAnyPermission(['documents:update', 'employee_documents:update'])}
        canUpdateDocument={(document) => documentPermission(document, 'update')}
        canReplace={permissions.hasAnyPermission(['documents:upload', 'employee_documents:upload'])}
        canReplaceDocument={(document) => documentPermission(document, 'upload')}
        canProcess={permissions.hasAnyPermission([
          'documents:process',
          'employee_documents:process'
        ])}
        canProcessDocument={(document) => documentPermission(document, 'process')}
        canDelete={permissions.hasAnyPermission(['documents:delete', 'employee_documents:delete'])}
        canDeleteDocument={(document) => documentPermission(document, 'delete')}
        {viewMode}
        {openingDocumentId}
        ondownload={(document) => void download(document)}
        onocrdownload={(document) => void download(document, 'ocr')}
        onopenbrowser={(document) => void openInBrowser(document)}
        ondetail={(document) => (selectedDocument = document)}
        onupdate={(document) => (editDocument = document)}
        onreplace={(document) => (replaceDocument = document)}
        onversions={(document) => void showVersions(document)}
        onretry={retryOcr}
        ondelete={deleteDocument}
      />
      {#if meta && meta.pages > 1}<div class="mt-5 flex items-center justify-between">
          <p class="text-xs text-foreground-muted">Página {meta.page} de {meta.pages}</p>
          <div class="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              class="min-h-11"
              disabled={page <= 1}
              onclick={() => (page -= 1)}>Anterior</Button
            ><Button
              variant="secondary"
              size="sm"
              class="min-h-11"
              disabled={page >= meta.pages}
              onclick={() => (page += 1)}>Siguiente</Button
            >
          </div>
        </div>{/if}
    </section>
  {/if}
</div>

{#if selectedDocument}<DocumentDetailPanel
    document={selectedDocument}
    onclose={() => (selectedDocument = null)}
    ondownload={documentPermission(selectedDocument, 'download')
      ? (document) => void download(document)
      : undefined}
    onocrdownload={documentPermission(selectedDocument, 'download')
      ? (document) => void download(document, 'ocr')
      : undefined}
    onopenbrowser={documentPermission(selectedDocument, 'download')
      ? (document) => void openInBrowser(document)
      : undefined}
    opening={openingDocumentId === selectedDocument.id}
    onversions={(document) => void showVersions(document)}
    onupdate={documentPermission(selectedDocument, 'update')
      ? (document) => (editDocument = document)
      : undefined}
    onreplace={documentPermission(selectedDocument, 'upload')
      ? (document) => (replaceDocument = document)
      : undefined}
  />{/if}

{#if showUpload}<Modal
    open={showUpload}
    title="Cargar documento"
    size="lg"
    onclose={() => (showUpload = false)}
  >
    <div
      class="mb-4 rounded-xl border border-border bg-surface-muted/50 px-4 py-3 text-xs text-foreground-muted"
      aria-live="polite"
    >
      Destino: <span class="font-medium text-foreground">{uploadDestinationPath()}</span>
    </div>
    {#if scope === 'root'}
      <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <FormField
          id="upload-folder-destination"
          label="Destino"
          bind:value={uploadDestination}
          options={[
            ...(canGeneralUpload ? [{ value: 'general', label: 'General de la empresa' }] : []),
            ...(canEmployeeUpload ? [{ value: 'employee', label: 'Expediente de empleado' }] : [])
          ]}
        />{#if uploadDestination === 'employee'}<FormField
            id="upload-folder-employee"
            label="Empleado"
            bind:value={uploadEmployeeId}
            options={uploadEmployees.map((item) => ({
              value: item.id,
              label: `${item.first_name} ${item.last_name} · ${item.employee_code}`
            }))}
          />{:else}<p class="pt-8 text-xs text-foreground-muted">
            El archivo será visible para los usuarios autorizados de la empresa.
          </p>{/if}
      </div>
      {#if uploadDestination === 'employee' && uploadEmployeesLoading}<p
          class="mb-4 text-xs text-foreground-muted"
        >
          Cargando empleados…
        </p>{/if}
    {/if}
    <DocumentUploadQueue
      categories={categories.filter(
        (item) => item.module === (uploadDestination === 'employee' ? 'employees' : 'general')
      )}
      employeeId={uploadDestination === 'employee' ? uploadEmployeeId || undefined : undefined}
      initialCategoryId={scope === 'category' ? categoryId : undefined}
      disabled={uploadDestination === 'employee' && !uploadEmployeeId}
      onclose={() => (showUpload = false)}
      onfinished={() => {
        showUpload = false;
        void load();
      }}
    />
  </Modal>{/if}

{#if editDocument}<DocumentMetadataModal
    document={editDocument}
    categories={categories.filter((item) => item.module === editDocument?.module)}
    employeeId={fileEmployeeId(editDocument)}
    onclose={() => (editDocument = null)}
    onsaved={() => {
      editDocument = null;
      void load();
    }}
  />{/if}

{#if replaceDocument}<Modal
    open={true}
    title={`Reemplazar · ${replaceDocument.title}`}
    size="lg"
    onclose={() => (replaceDocument = null)}
    ><DocumentUploadQueue
      categories={categories.filter((item) => item.module === replaceDocument?.module)}
      employeeId={fileEmployeeId(replaceDocument)}
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
      {#if versionsLoading}<p class="py-8 text-center text-sm text-foreground-muted">
          Cargando historial…
        </p>{:else}{#each versions as item (item.id)}<div
            class="flex items-center justify-between gap-3 rounded-xl border border-border p-4"
          >
            <div>
              <p class="text-sm font-medium text-foreground">
                Versión {item.version_number}{item.is_current ? ' · vigente' : ''}
              </p>
              <p class="text-xs text-foreground-muted">
                {item.original_filename} · {item.created_at
                  ? new Date(item.created_at).toLocaleDateString('es-SV')
                  : '—'}
              </p>
            </div>
            {#if item.technical_status === 'active'}<Button
                variant="ghost"
                size="sm"
                class="min-h-11"
                onclick={() => void download(item)}>Descargar</Button
              >{/if}
          </div>{/each}{/if}
    </div></Modal
  >{/if}

<style>
  .document-library-view {
    animation: document-library-enter 180ms ease-out both;
  }

  @keyframes document-library-enter {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .document-library-view {
      animation: none;
    }
  }
</style>
