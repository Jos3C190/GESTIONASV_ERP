<script lang="ts">
  import { HttpError, type DocumentCategoryOut, type DocumentRecordOut } from '$lib/api/client';
  import type { OwnedDocumentsApi } from '$lib/api/owned-documents';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import DocumentList from '$lib/features/documents/components/DocumentList.svelte';
  import DocumentMetadataModal from '$lib/features/documents/components/DocumentMetadataModal.svelte';
  import DocumentUploadQueue from '$lib/features/documents/components/DocumentUploadQueue.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  interface Props {
    owner: OwnedDocumentsApi;
    title: string;
    description: string;
    permissionPrefix?: string;
    /** Permisos explícitos cuando no siguen el patrón prefijo:acción. */
    permissionCodes?: { read: string; upload: string; update: string; download: string };
    /** Avisa al contenedor para recalcular la aptitud tras cambios. */
    onchanged?: () => void;
  }
  let { owner, title, description, permissionPrefix, permissionCodes, onchanged }: Props = $props();
  const codes = $derived(
    permissionCodes ?? {
      read: `${permissionPrefix}:read`,
      upload: `${permissionPrefix}:upload`,
      update: `${permissionPrefix}:update`,
      download: `${permissionPrefix}:download`
    }
  );

  let documents = $state<DocumentRecordOut[]>([]);
  let categories = $state<DocumentCategoryOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let categoryFilter = $state('');
  let statusFilter = $state('');
  let showUpload = $state(false);
  let uploadCategoryId = $state<string | undefined>(undefined);
  let editDocument = $state<DocumentRecordOut | null>(null);
  let replaceDocument = $state<DocumentRecordOut | null>(null);
  let versionDocument = $state<DocumentRecordOut | null>(null);
  let versions = $state<DocumentRecordOut[]>([]);
  let openingDocumentId = $state<string | null>(null);

  const canRead = $derived(permissions.hasPermission(codes.read));
  const canUpload = $derived(permissions.hasPermission(codes.upload));
  const canUpdate = $derived(permissions.hasPermission(codes.update));
  const canDownload = $derived(permissions.hasPermission(codes.download));

  /** Categorías obligatorias sin documento vigente: invitan a cargarlas directamente. */
  const missingRequired = $derived(
    categories.filter(
      (category) =>
        category.compliance_required &&
        !documents.some(
          (item) =>
            item.category_id === category.id &&
            ['current', 'expiring', 'active'].includes(item.business_status)
        )
    )
  );

  async function load() {
    if (!canRead) {
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const [page, categoryList] = await Promise.all([
        owner.list({
          size: 100,
          category_id: categoryFilter || undefined,
          status: statusFilter || undefined
        }),
        owner.categories()
      ]);
      documents = page.items;
      categories = categoryList;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los documentos.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void owner.basePath;
    void categoryFilter;
    void statusFilter;
    void load();
  });

  function changed() {
    void load();
    onchanged?.();
  }

  function openUpload(categoryId?: string) {
    uploadCategoryId = categoryId;
    showUpload = true;
  }

  async function openUrl(document: DocumentRecordOut, preview: boolean) {
    openingDocumentId = document.id;
    error = null;
    try {
      const result = preview
        ? await owner.previewUrl(document.id)
        : await owner.downloadUrl(document.id);
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo abrir el documento.';
    } finally {
      openingDocumentId = null;
    }
  }

  async function showVersions(document: DocumentRecordOut) {
    versionDocument = document;
    try {
      versions = await owner.versions(document.id);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el historial.';
      versionDocument = null;
    }
  }
</script>

{#if canRead}
  <section class="owned-documents" aria-label={title}>
    <header>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {#if canUpload}<Button size="sm" onclick={() => openUpload()}>Agregar documento</Button>{/if}
    </header>

    {#if missingRequired.length}
      <div class="missing" role="status">
        <strong>Documentos obligatorios pendientes</strong>
        <ul>
          {#each missingRequired as category (category.id)}
            <li>
              <span>{category.name}</span>
              {#if canUpload}<button type="button" onclick={() => openUpload(category.id)}
                  >Cargar</button
                >{/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div class="filters">
      <select bind:value={categoryFilter} aria-label="Filtrar por categoría">
        <option value="">Todas las categorías</option>
        {#each categories as category (category.id)}
          <option value={category.id}
            >{category.name}{category.compliance_required ? ' · obligatorio' : ''}</option
          >
        {/each}
      </select>
      <select bind:value={statusFilter} aria-label="Filtrar por estado">
        <option value="">Todos los estados</option>
        <option value="current">Vigentes</option>
        <option value="expiring">Por vencer</option>
        <option value="expired">Vencidos</option>
        <option value="processing">Procesando</option>
      </select>
    </div>

    {#if error}<p class="error" role="alert">{error}</p>{/if}

    <DocumentList
      {documents}
      {loading}
      {canDownload}
      {canUpdate}
      canReplace={canUpload}
      viewMode="table"
      {openingDocumentId}
      ondownload={(document) => openUrl(document, false)}
      onopenbrowser={(document) => openUrl(document, true)}
      onupdate={(document) => (editDocument = document)}
      onreplace={(document) => (replaceDocument = document)}
      onversions={showVersions}
    />
  </section>

  {#if showUpload}
    <Modal
      open={showUpload}
      title="Agregar documento"
      size="lg"
      onclose={() => (showUpload = false)}
    >
      <DocumentUploadQueue
        {categories}
        {owner}
        initialCategoryId={uploadCategoryId}
        onclose={() => (showUpload = false)}
        onfinished={changed}
      />
    </Modal>
  {/if}

  {#if replaceDocument}
    <Modal
      open={true}
      title={`Nueva versión de ${replaceDocument.title}`}
      size="lg"
      onclose={() => (replaceDocument = null)}
    >
      <DocumentUploadQueue
        {categories}
        {owner}
        initialCategoryId={replaceDocument.category_id}
        replaceDocumentId={replaceDocument.id}
        onclose={() => (replaceDocument = null)}
        onfinished={changed}
      />
    </Modal>
  {/if}

  {#if editDocument}
    <DocumentMetadataModal
      document={editDocument}
      {categories}
      {owner}
      onclose={() => (editDocument = null)}
      onsaved={changed}
    />
  {/if}

  {#if versionDocument}
    <Modal
      open={true}
      title={`Historial de ${versionDocument.title}`}
      onclose={() => (versionDocument = null)}
    >
      <ol class="versions">
        {#each versions as version (version.id)}
          <li>
            <strong>Versión {version.version_number}</strong>
            <span>{version.title}{version.expires_on ? ` · vence ${version.expires_on}` : ''}</span>
            {#if version.is_current}<em>Vigente</em>{/if}
          </li>
        {/each}
      </ol>
    </Modal>
  {/if}
{:else}
  <p class="no-access">No tiene permiso para consultar estos documentos.</p>
{/if}

<style>
  .owned-documents {
    display: grid;
    gap: 14px;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  h3 {
    font-size: 14px;
    font-weight: 600;
  }
  header p {
    margin-top: 4px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .missing {
    padding: 12px 14px;
    border: 1px solid rgb(var(--danger) / 0.25);
    border-radius: 10px;
    background: rgb(var(--danger) / 0.06);
    font-size: 12px;
  }
  .missing strong {
    color: rgb(var(--danger));
  }
  .missing ul {
    display: grid;
    gap: 6px;
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
  }
  .missing li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .missing button {
    padding: 3px 9px;
    border: 1px solid rgb(var(--danger) / 0.4);
    border-radius: 6px;
    color: rgb(var(--danger));
    font-size: 11px;
    font-weight: 600;
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .filters select {
    min-height: 38px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 12px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .versions {
    display: grid;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 12px;
  }
  .versions li {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
  }
  .versions em {
    color: rgb(var(--success));
    font-style: normal;
    font-weight: 600;
  }
  .no-access {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
</style>
