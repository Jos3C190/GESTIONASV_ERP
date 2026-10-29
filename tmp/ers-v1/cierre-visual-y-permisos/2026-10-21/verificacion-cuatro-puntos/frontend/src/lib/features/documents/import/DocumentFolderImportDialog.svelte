<script lang="ts">
  import type { DocumentCategoryOut, GeneralImportItemOut, GeneralImportOut, DocumentMetadataInput } from '$lib/api/client';
  import { api, HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { DOCUMENT_MAX_BYTES } from '$lib/features/documents/document-upload';
  import { buildFolderManifest, selectionFromDrop, selectionFromPicker, sha256, type FolderSelection } from './folder-import';
  import DocumentFolderImportSummary from './DocumentFolderImportSummary.svelte';
  import DocumentFolderImportTree from './DocumentFolderImportTree.svelte';
  import DocumentFolderImportProgress from './DocumentFolderImportProgress.svelte';
  import DocumentFolderImportReport from './DocumentFolderImportReport.svelte';

  interface Props {
    categories: DocumentCategoryOut[];
    parentId: string | null;
    onclose: () => void;
    onfinished: (rootEntryId: string | null) => void;
    onbusychange?: (busy: boolean) => void;
  }

  type LocalStatus = 'pending' | 'hashing' | 'uploading' | 'verifying' | 'done' | 'skipped' | 'error';
  type LocalState = { status: LocalStatus; progress: number; message?: string };

  let { categories, parentId, onclose, onfinished, onbusychange }: Props = $props();
  let picker = $state<HTMLInputElement | null>(null);
  let selection = $state<FolderSelection | null>(null);
  let importResult = $state<GeneralImportOut | null>(null);
  let localStates = $state<Record<string, LocalState>>({});
  let phase = $state<'select' | 'review' | 'running' | 'report'>('select');
  let busy = $state(false);
  let dragActive = $state(false);
  let error = $state<string | null>(null);
  let categoryId = $state('');
  let description = $state('');
  let issuer = $state('');
  let referenceCode = $state('');
  let issuedOn = $state('');
  let expiresOn = $state('');
  let confidentiality = $state<'internal' | 'restricted'>('restricted');
  let tags = $state('');
  let cancelRequested = false;

  function setBusy(next: boolean) {
    busy = next;
    onbusychange?.(next);
  }

  let analysis = $derived(selection ? buildFolderManifest(selection, DOCUMENT_MAX_BYTES) : null);
  let validCount = $derived(analysis?.validFiles.length ?? 0);
  let folderCount = $derived(selection?.folders.length ?? 0);
  let itemCount = $derived((analysis?.manifest.length ?? 0));
  let completedCount = $derived(Object.values(localStates).filter((item) => ['done', 'skipped'].includes(item.status)).length);
  let errorCount = $derived(Object.values(localStates).filter((item) => item.status === 'error').length);
  let progress = $derived(importResult && importResult.total_files > 0
    ? Math.round(completedCount / importResult.total_files * 100)
    : 0);

  function chooseFiles(event: Event) {
    const files = Array.from((event.currentTarget as HTMLInputElement).files ?? []);
    selection = selectionFromPicker(files);
    importResult = null;
    phase = selection.files.length || selection.folders.length ? 'review' : 'select';
    error = null;
  }

  async function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
    if (!event.dataTransfer?.items.length) return;
    try {
      selection = await selectionFromDrop(event.dataTransfer.items);
      importResult = null;
      phase = selection.files.length || selection.folders.length ? 'review' : 'select';
      error = null;
    } catch {
      error = 'No se pudo leer la carpeta seleccionada.';
    }
  }

  function metadata(): DocumentMetadataInput {
    const value: DocumentMetadataInput = { confidentiality };
    if (categoryId) value.category_id = categoryId;
    if (description.trim()) value.description = description.trim();
    if (issuer.trim()) value.issuer = issuer.trim();
    if (referenceCode.trim()) value.reference_code = referenceCode.trim();
    if (issuedOn) value.issued_on = issuedOn;
    if (expiresOn) value.expires_on = expiresOn;
    const parsedTags = tags.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 10);
    if (parsedTags.length) value.tags = parsedTags;
    return value;
  }

  function localFile(path: string): File | undefined {
    return selection?.files.find((entry) => entry.relativePath === path)?.file;
  }

  function setLocal(id: string, state: LocalState) {
    localStates = { ...localStates, [id]: state };
  }

  function failureMessage(cause: unknown): string {
    return cause instanceof HttpError ? cause.message : 'No se pudo procesar el archivo.';
  }

  async function processItem(item: GeneralImportItemOut): Promise<void> {
    const file = localFile(item.source_path);
    if (!file) {
      setLocal(item.id, { status: 'error', progress: 0, message: 'El archivo ya no está disponible en el equipo.' });
      return;
    }
    try {
      setLocal(item.id, { status: 'hashing', progress: 0 });
      const checksum = await sha256(file);
      setLocal(item.id, { status: 'uploading', progress: 0 });
      const ticketResult = await api.documents.general.authorizeImportItem(importResult!.id, item.id, checksum);
      await api.documents.uploadDirect(ticketResult.ticket, file, (value) => setLocal(item.id, { status: 'uploading', progress: value }));
      setLocal(item.id, { status: 'verifying', progress: 100 });
      await api.documents.general.completeImportItem(importResult!.id, item.id);
      setLocal(item.id, { status: 'done', progress: 100 });
    } catch (cause) {
      setLocal(item.id, { status: 'error', progress: 0, message: failureMessage(cause) });
    }
  }

  async function runItems(result: GeneralImportOut, onlyErrors = false) {
    const items = result.items.filter((item) => item.kind === 'file' && item.status !== 'skipped' && (!onlyErrors || localStates[item.id]?.status === 'error'));
    let cursor = 0;
    const worker = async () => {
      while (cursor < items.length && !cancelRequested) {
        const item = items[cursor++];
        if (!item) return;
        await processItem(item);
      }
    };
    await Promise.all(Array.from({ length: Math.min(3, Math.max(1, items.length)) }, () => worker()));
    const refreshed = await api.documents.general.getImport(result.id, { size: 1000 });
    importResult = refreshed;
    if (!cancelRequested && refreshed.status !== 'completed' && refreshed.status !== 'partial' && refreshed.total_files > refreshed.completed_files + refreshed.skipped_files + refreshed.failed_files) {
      error = 'Algunos archivos aún no terminaron de procesarse.';
    }
  }

  async function prepareAndRun() {
    if (!analysis || !selection || busy || !analysis.manifest.length) return;
    if (issuedOn && expiresOn && expiresOn < issuedOn) {
      error = 'La fecha de vencimiento no puede ser anterior a la fecha de emisión.';
      return;
    }
    setBusy(true);
    error = null;
    cancelRequested = false;
    try {
      const result = await api.documents.general.prepareImport({ parent_id: parentId, metadata: metadata(), items: analysis.manifest });
      importResult = result;
      localStates = Object.fromEntries(result.items.filter((item) => item.kind === 'file').map((item) => [item.id, {
        status: item.status === 'skipped' ? 'skipped' : 'pending', progress: item.status === 'skipped' ? 100 : 0, message: item.failure_message ?? undefined
      }]));
      phase = 'running';
      await runItems(result);
      phase = 'report';
    } catch (cause) {
      error = failureMessage(cause);
    } finally {
      setBusy(false);
    }
  }

  async function retryErrors() {
    if (!importResult || busy || errorCount === 0) return;
    setBusy(true);
    error = null;
    cancelRequested = false;
    phase = 'running';
    try {
      await runItems(importResult, true);
      phase = 'report';
    } finally {
      setBusy(false);
    }
  }

  async function cancelImport() {
    cancelRequested = true;
    if (!importResult) { onclose(); return; }
    setBusy(true);
    try {
      await api.documents.general.cancelImport(importResult.id);
      importResult = await api.documents.general.getImport(importResult.id, { size: 1000 });
      phase = 'report';
    } catch (cause) {
      error = failureMessage(cause);
    } finally {
      setBusy(false);
    }
  }

  function finish() {
    onfinished(importResult?.root_entry_id ?? null);
  }
</script>

<div class="space-y-5">
  {#if phase === 'select' || phase === 'review'}
    <div>
      <p class="text-sm text-foreground-muted">Selecciona una carpeta completa. Se conservarán sus subcarpetas, carpetas vacías y archivos compatibles.</p>
      <button
        type="button"
        class="folder-dropzone {dragActive ? 'folder-dropzone-active' : ''}"
        ondragover={(event) => { event.preventDefault(); dragActive = true; }}
        ondragleave={() => (dragActive = false)}
        ondrop={handleDrop}
        onclick={() => picker?.click()}
      >
        <span class="text-2xl" aria-hidden="true">📁</span>
        <strong>{selection?.rootName || 'Seleccionar carpeta'}</strong>
        <span>Arrastra una carpeta aquí o selecciónala desde tu equipo</span>
        <input bind:this={picker} class="sr-only" type="file" multiple webkitdirectory onchange={chooseFiles} />
      </button>
    </div>

    {#if analysis && selection}
      <DocumentFolderImportSummary
        rootName={selection.rootName}
        totalBytes={analysis.totalBytes}
        {validCount}
        folderCount={folderCount}
        skippedCount={analysis.invalidFiles.length}
        {itemCount}
      />

      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label class="text-xs font-semibold text-foreground-muted">Categoría<select bind:value={categoryId} class="import-input mt-1"><option value="">Sin categoría</option>{#each categories.filter((item) => item.is_active) as category}<option value={category.id}>{category.name}</option>{/each}</select></label>
        <label class="text-xs font-semibold text-foreground-muted">Referencia<input bind:value={referenceCode} class="import-input mt-1" placeholder="Ej. IMP-2026-001" /></label>
        <label class="text-xs font-semibold text-foreground-muted">Emisor<input bind:value={issuer} class="import-input mt-1" placeholder="Opcional" /></label>
        <label class="text-xs font-semibold text-foreground-muted">Fecha de emisión<input bind:value={issuedOn} type="date" class="import-input mt-1" /></label>
        <label class="text-xs font-semibold text-foreground-muted">Fecha de vencimiento<input bind:value={expiresOn} type="date" class="import-input mt-1" /></label>
        <label class="text-xs font-semibold text-foreground-muted">Confidencialidad<select bind:value={confidentiality} class="import-input mt-1"><option value="restricted">Restringido</option><option value="internal">Interno</option></select></label>
        <label class="text-xs font-semibold text-foreground-muted sm:col-span-2 lg:col-span-3">Etiquetas<input bind:value={tags} class="import-input mt-1" placeholder="2026, contratos" /></label>
      </div>
      <label class="block text-xs font-semibold text-foreground-muted">Descripción<textarea bind:value={description} class="import-input mt-1 min-h-16" placeholder="Metadatos comunes opcionales"></textarea></label>

      <DocumentFolderImportTree manifest={analysis.manifest} invalidFiles={analysis.invalidFiles} />
    {/if}
    {#if error && (phase === 'select' || phase === 'review')}<p class="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">{error}</p>{/if}
  {:else}
    <DocumentFolderImportProgress
      phase={phase}
      result={importResult}
      {localStates}
      {progress}
      {completedCount}
      {errorCount}
    />
    {#if error}<p class="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">{error}</p>{/if}
    {#if phase === 'report'}<DocumentFolderImportReport result={importResult} invalidFiles={analysis?.invalidFiles ?? []} />{/if}
  {/if}

  <div class="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
    {#if phase === 'report'}
      {#if errorCount > 0}<Button variant="secondary" onclick={() => void retryErrors()} disabled={busy}>Reintentar errores</Button>{/if}
      <Button onclick={finish}>Abrir carpeta importada</Button>
    {:else}
      <Button variant="ghost" onclick={() => void cancelImport()} disabled={busy && !importResult}>{phase === 'select' ? 'Cerrar' : 'Cancelar'}</Button>
      {#if phase === 'review'}<Button onclick={() => void prepareAndRun()} disabled={busy || !analysis?.manifest.length}>{busy ? 'Preparando…' : 'Importar carpeta'}</Button>{/if}
    {/if}
  </div>
</div>

<style>
  .folder-dropzone { display: flex; min-height: 9rem; width: 100%; cursor: pointer; flex-direction: column; align-items: center; justify-content: center; gap: .45rem; border: 1px dashed rgb(var(--border-strong)); border-radius: 1rem; background: rgb(var(--surface)); padding: 1.25rem; color: rgb(var(--foreground-muted)); text-align: center; transition: border-color 120ms ease, background-color 120ms ease; }
  .folder-dropzone:hover, .folder-dropzone-active { border-color: rgb(var(--primary)); background: rgb(var(--primary) / .08); }
  .folder-dropzone strong { color: rgb(var(--foreground)); font-size: .9rem; }
  .folder-dropzone span:last-of-type { font-size: .75rem; }
  .import-input { display: block; min-height: 2.75rem; width: 100%; border: 1px solid rgb(var(--border)); border-radius: .75rem; background: rgb(var(--surface)); padding: .6rem .75rem; color: rgb(var(--foreground)); outline: none; }
  .import-input:focus { border-color: rgb(var(--primary)); box-shadow: 0 0 0 3px rgb(var(--primary) / .18); }
  select.import-input, input[type='date'].import-input { color-scheme: dark; }
  @media (prefers-reduced-motion: reduce) { .folder-dropzone { transition: none; } }
</style>
