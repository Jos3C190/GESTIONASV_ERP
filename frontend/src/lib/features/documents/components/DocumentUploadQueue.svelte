<script lang="ts">
  import {
    api,
    HttpError,
    type DocumentCategoryOut,
    type DocumentMetadataInput
  } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  interface Props {
    categories: DocumentCategoryOut[];
    employeeId?: string;
    initialCategoryId?: string;
    replaceDocumentId?: string;
    disabled?: boolean;
    onclose: () => void;
    onfinished?: () => void;
  }

  type QueueState =
    | 'queued'
    | 'preparing'
    | 'authorizing'
    | 'uploading'
    | 'verifying'
    | 'scanning'
    | 'done'
    | 'error';
  interface MetadataDraft {
    categoryId: string;
    title: string;
    description: string;
    referenceCode: string;
    issuer: string;
    issuedOn: string;
    expiresOn: string;
    confidentiality: 'internal' | 'restricted';
    tagsText: string;
  }
  interface QueueItem {
    id: string;
    file: File;
    state: QueueState;
    progress: number;
    error: string | null;
    metadata: MetadataDraft;
  }

  let {
    categories,
    employeeId,
    initialCategoryId,
    replaceDocumentId,
    disabled = false,
    onclose,
    onfinished
  }: Props = $props();
  let queue = $state<QueueItem[]>([]);
  let categoryId = $state('');
  let appliedInitialCategoryId = '';
  let title = $state('');
  let description = $state('');
  let referenceCode = $state('');
  let issuer = $state('');
  let issuedOn = $state('');
  let expiresOn = $state('');
  let confidentiality = $state<'internal' | 'restricted'>('restricted');
  let tagsText = $state('');
  let running = $state(false);
  let error = $state<string | null>(null);
  let dragActive = $state(false);
  let fileInput: HTMLInputElement;

  const maxQueue = 20;
  const maxConcurrency = 3;

  $effect(() => {
    const value = initialCategoryId ?? '';
    if (value && value !== appliedInitialCategoryId) {
      categoryId = value;
      appliedInitialCategoryId = value;
    }
  });

  const allowed = new Set(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'odt', 'ods']);
  const maxBytes = 50 * 1024 * 1024;

  function currentMetadata(): MetadataDraft {
    return {
      categoryId,
      title,
      description,
      referenceCode,
      issuer,
      issuedOn,
      expiresOn,
      confidentiality,
      tagsText
    };
  }

  function addFiles(selected: File[]) {
    if (selected.length === 0) return;
    const queueLimit = replaceDocumentId ? 1 : maxQueue;
    let limitExceeded = false;
    if (queue.length + selected.length > queueLimit) {
      limitExceeded = true;
      error = replaceDocumentId
        ? 'Un reemplazo solo admite un archivo nuevo.'
        : `La cola admite como máximo ${maxQueue} archivos.`;
      selected = selected.slice(0, Math.max(0, queueLimit - queue.length));
    }
    const invalid = selected.find((file) => {
      const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
      return file.size < 1 || file.size > maxBytes || !allowed.has(extension);
    });
    if (invalid) {
      error = `«${invalid.name}» no es válido. Use documentos permitidos de hasta 50 MB.`;
      return;
    }
    queue = [
      ...queue,
      ...selected.map((file) => ({
        id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
        state: 'queued' as QueueState,
        progress: 0,
        error: null,
        metadata: currentMetadata()
      }))
    ];
    if (!limitExceeded) error = null;
  }

  function chooseFiles(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    addFiles(Array.from(input.files ?? []));
    input.value = '';
  }

  function dropFiles(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
    addFiles(Array.from(event.dataTransfer?.files ?? []));
  }

  function activatePicker(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      fileInput?.click();
    }
  }

  function removeItem(id: string) {
    const item = queue.find((candidate) => candidate.id === id);
    if (!item || (running && item.state !== 'queued')) return;
    queue = queue.filter((candidate) => candidate.id !== id);
  }

  function updateMetadata(id: string, changes: Partial<MetadataDraft>) {
    queue = queue.map((item) =>
      item.id === id ? { ...item, metadata: { ...item.metadata, ...changes } } : item
    );
  }

  function applyMetadataToAll() {
    queue = queue.map((item) =>
      item.state === 'queued'
        ? {
            ...item,
            metadata: currentMetadata()
          }
        : item
    );
    error = 'Metadatos aplicados a los archivos en cola.';
  }

  async function checksum(file: File): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
      ''
    );
  }

  function metadata(draft: MetadataDraft): DocumentMetadataInput {
    const tags = draft.tagsText
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    return {
      ...(draft.categoryId ? { category_id: draft.categoryId } : {}),
      ...(draft.title.trim() ? { title: draft.title.trim() } : {}),
      ...(draft.description.trim() ? { description: draft.description.trim() } : {}),
      ...(draft.referenceCode.trim() ? { reference_code: draft.referenceCode.trim() } : {}),
      ...(draft.issuer.trim() ? { issuer: draft.issuer.trim() } : {}),
      ...(draft.issuedOn ? { issued_on: draft.issuedOn } : {}),
      ...(draft.expiresOn ? { expires_on: draft.expiresOn } : {}),
      confidentiality: draft.confidentiality,
      tags
    };
  }

  function setItem(id: string, changes: Partial<QueueItem>) {
    queue = queue.map((item) => (item.id === id ? { ...item, ...changes } : item));
  }

  async function processItem(item: QueueItem): Promise<boolean> {
    if (!queue.some((candidate) => candidate.id === item.id && candidate.state === 'queued')) {
      return false;
    }
    try {
      setItem(item.id, { state: 'preparing', progress: 0, error: null });
      const sha = await checksum(item.file);
      setItem(item.id, { state: 'authorizing' });
      const input = {
        file_name: item.file.name,
        content_type: item.file.type || 'application/octet-stream',
        size_bytes: item.file.size,
        checksum_sha256: sha,
        ...metadata(item.metadata)
      };
      const ticket = replaceDocumentId
        ? await api.documents.replace(replaceDocumentId, input, employeeId)
        : employeeId
          ? await api.documents.initiateEmployee(employeeId, input)
          : await api.documents.initiate(input);
      setItem(item.id, { state: 'uploading' });
      await api.documents.uploadDirect(ticket, item.file, (progress) =>
        setItem(item.id, { progress })
      );
      setItem(item.id, { state: 'verifying', progress: 100 });
      setItem(item.id, { state: 'scanning' });
      await api.documents.complete(ticket.document_id, employeeId);
      // The completion response means the synchronous antivirus phase ended;
      // OCR, when applicable, remains asynchronous and does not block success.
      setItem(item.id, { state: 'done', progress: 100 });
      return true;
    } catch (err) {
      setItem(item.id, {
        state: 'error',
        error: err instanceof HttpError ? err.message : 'No se pudo procesar el archivo.'
      });
      return false;
    }
  }

  async function start(ids?: string[], closeOnSuccess = true) {
    if (queue.length === 0 || running) return;
    running = true;
    error = null;
    const pending = queue.filter(
      (item) => item.state !== 'done' && (!ids || ids.includes(item.id))
    );
    let cursor = 0;
    let failed = false;
    const worker = async () => {
      while (cursor < pending.length) {
        const item = pending[cursor++];
        if (!item) return;
        const succeeded = await processItem(item);
        failed ||= !succeeded;
      }
    };
    await Promise.all(
      Array.from({ length: Math.min(maxConcurrency, pending.length) }, () => worker())
    );
    running = false;
    if (failed) error = 'Algunos archivos requieren atención. Puede reintentarlos.';
    else if (closeOnSuccess) onfinished?.();
  }

  async function retryItem(id: string) {
    if (running) return;
    const item = queue.find((candidate) => candidate.id === id);
    if (!item || item.state !== 'error') return;
    setItem(id, { state: 'queued', progress: 0, error: null });
    await start([id], false);
  }

  function stateLabel(state: QueueState): string {
    return {
      queued: 'En cola',
      uploading: 'Cargando',
      preparing: 'Preparando',
      authorizing: 'Autorizando',
      verifying: 'Verificando',
      scanning: 'Analizando',
      done: 'Listo',
      error: 'Revisar'
    }[state];
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  let completedCount = $derived(queue.filter((item) => item.state === 'done').length);
  let failedCount = $derived(queue.filter((item) => item.state === 'error').length);

  $effect(() => {
    if (!running || typeof window === 'undefined') return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeLeaving);
    return () => window.removeEventListener('beforeunload', warnBeforeLeaving);
  });
</script>

<div class="space-y-5">
  <div>
    <p class="text-sm text-foreground-muted">
      Seleccione uno o varios archivos. Cada archivo se verifica y escanea antes de estar
      disponible.
    </p>
    <div
      role="button"
      tabindex="0"
      aria-label="Seleccionar documentos para cargar"
      class="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed {dragActive
        ? 'border-primary bg-primary/10'
        : 'border-border-strong bg-surface-muted/40'} px-5 py-8 text-center transition hover:border-primary/60 hover:bg-primary/5"
      onkeydown={activatePicker}
      ondragover={(event) => {
        event.preventDefault();
        dragActive = true;
      }}
      ondragleave={() => (dragActive = false)}
      ondrop={dropFiles}
      onclick={() => fileInput?.click()}
    >
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        class="text-primary"
        aria-hidden="true"
      >
        <path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
      </svg>
      <span class="mt-2 text-sm font-medium text-foreground">Agregar documentos</span>
      <span class="mt-1 text-xs text-foreground-subtle"
        >Arrastre aquí o seleccione PDF, Word, Excel, CSV, TXT, ODT u ODS · máximo 50 MB</span
      >
      <span class="mt-2 text-[11px] text-foreground-muted"
        >{replaceDocumentId
          ? 'Seleccione un solo archivo para crear la nueva versión'
          : `Hasta ${maxQueue} archivos por cola`}</span
      >
    </div>
    <input
      id="document-files"
      bind:this={fileInput}
      class="sr-only"
      type="file"
      multiple
      accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.odt,.ods"
      onchange={chooseFiles}
    />
  </div>

  {#if queue.length > 0}
    <div class="space-y-2 rounded-xl border border-border p-3">
      <div class="flex flex-wrap items-center justify-between gap-2 px-1">
        <span class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle"
          >{replaceDocumentId ? 'Nueva versión' : `Cola (${queue.length}/${maxQueue})`}</span
        >
        <div class="flex items-center gap-3 text-[11px] text-foreground-muted">
          <span>{completedCount} listos</span>{#if failedCount > 0}<span class="text-danger"
              >{failedCount} con error</span
            >{/if}{#if !running}<button
              type="button"
              class="text-xs text-foreground-muted hover:text-danger"
              onclick={() => (queue = [])}>Vaciar</button
            >{/if}
        </div>
      </div>
      {#each queue as item (item.id)}
        <div class="rounded-lg bg-surface-muted/60 p-3">
          <div class="flex items-center gap-3">
            <div
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                aria-hidden="true"
                ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path
                  d="M14 2v6h6"
                /></svg
              >
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-foreground">{item.file.name}</p>
              <p
                class="text-xs {item.state === 'error'
                  ? 'text-danger'
                  : item.state === 'done'
                    ? 'text-success'
                    : 'text-foreground-muted'}"
              >
                {item.error ?? `${stateLabel(item.state)} · ${formatSize(item.file.size)}`}
              </p>
            </div>
            {#if item.state !== 'done' && (!running || item.state === 'queued')}<button
                type="button"
                class="text-foreground-subtle hover:text-foreground"
                aria-label="Quitar archivo"
                onclick={() => removeItem(item.id)}>×</button
              >{/if}
          </div>
          {#if item.state === 'uploading'}<div
              class="mt-2 h-1 overflow-hidden rounded-full bg-border"
            >
              <div
                class="h-full rounded-full bg-primary transition-all"
                style={`width:${item.progress}%`}
              ></div>
            </div>{/if}
          {#if item.state === 'error' && !running}<button
              type="button"
              class="mt-2 text-xs font-medium text-warning hover:underline"
              onclick={() => retryItem(item.id)}>Reintentar este archivo</button
            >{/if}
          {#if item.state === 'queued'}
            <details class="mt-3 border-t border-border pt-2">
              <summary class="cursor-pointer text-xs font-medium text-foreground-muted"
                >Editar metadatos de este archivo</summary
              >
              <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField
                  id={`category-${item.id}`}
                  label="Categoría"
                  value={item.metadata.categoryId}
                  options={[
                    { value: '', label: 'Otros' },
                    ...categories
                      .filter((category) => category.is_active)
                      .map((category) => ({ value: category.id, label: category.name }))
                  ]}
                  oninput={(event) =>
                    updateMetadata(item.id, {
                      categoryId: (event.currentTarget as HTMLSelectElement).value
                    })}
                />
                <FormField
                  id={`title-${item.id}`}
                  label="Título"
                  value={item.metadata.title}
                  oninput={(event) =>
                    updateMetadata(item.id, {
                      title: (event.currentTarget as HTMLInputElement).value
                    })}
                />
                <FormField
                  id={`expires-${item.id}`}
                  label="Vencimiento"
                  type="date"
                  value={item.metadata.expiresOn}
                  oninput={(event) =>
                    updateMetadata(item.id, {
                      expiresOn: (event.currentTarget as HTMLInputElement).value
                    })}
                />
                <FormField
                  id={`visibility-${item.id}`}
                  label="Visibilidad"
                  value={item.metadata.confidentiality}
                  options={[
                    { value: 'restricted', label: 'Restringido' },
                    { value: 'internal', label: 'Interno' }
                  ]}
                  oninput={(event) =>
                    updateMetadata(item.id, {
                      confidentiality: (event.currentTarget as HTMLSelectElement).value as
                        'internal' | 'restricted'
                    })}
                />
              </div>
            </details>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <FormField
      id="document-category"
      label="Categoría"
      bind:value={categoryId}
      options={[
        { value: '', label: 'Otros' },
        ...categories
          .filter((item) => item.is_active)
          .map((item) => ({ value: item.id, label: item.name }))
      ]}
    />
    <FormField
      id="document-title"
      label="Título (opcional)"
      bind:value={title}
      placeholder="Ej. Contrato laboral 2026"
    />
    <FormField
      id="document-reference"
      label="Código o referencia"
      bind:value={referenceCode}
      placeholder="Ej. RH-CT-001"
    />
    <FormField
      id="document-issuer"
      label="Emisor"
      bind:value={issuer}
      placeholder="Institución o persona"
    />
    <FormField id="document-issued" label="Fecha de emisión" type="date" bind:value={issuedOn} />
    <FormField
      id="document-expires"
      label="Fecha de vencimiento"
      type="date"
      bind:value={expiresOn}
    />
  </div>
  {#if queue.some((item) => item.state === 'queued')}<button
      type="button"
      class="text-xs font-medium text-primary hover:underline"
      onclick={applyMetadataToAll}>Aplicar estos metadatos a los archivos en cola</button
    >{/if}
  <div>
    <label for="document-description" class="mb-1 block text-sm font-medium text-foreground"
      >Descripción</label
    >
    <textarea
      id="document-description"
      bind:value={description}
      rows="2"
      maxlength="4000"
      placeholder="Notas útiles para localizar el documento"
      class="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    ></textarea>
  </div>
  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <FormField
      id="document-tags"
      label="Etiquetas (máximo 10)"
      bind:value={tagsText}
      placeholder="contrato, 2026"
    />
    <FormField
      id="document-confidentiality"
      label="Visibilidad"
      bind:value={confidentiality}
      options={[
        { value: 'restricted', label: 'Restringido' },
        { value: 'internal', label: 'Interno' }
      ]}
    />
  </div>

  {#if error}<div
      class="rounded-lg border {error.includes('aplicados')
        ? 'border-primary/30 bg-primary/10 text-primary'
        : 'border-danger/30 bg-danger/10 text-danger'} px-3 py-2 text-sm"
      role="alert"
      aria-live="polite"
    >
      {error}
    </div>{/if}
  <p class="sr-only" aria-live="polite">
    {completedCount} archivos listos. {failedCount} archivos con error.
  </p>
  {#if running}<p
      class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
      role="status"
    >
      Hay transferencias activas. Si navega a otra página, la carga podría interrumpirse.
    </p>{/if}
  <div class="flex items-center justify-end gap-2 border-t border-border pt-4">
    <Button variant="ghost" onclick={onclose} disabled={running}>Cancelar</Button>
    <Button onclick={() => start()} disabled={disabled || running || queue.length === 0}
      >{running
        ? 'Procesando…'
        : replaceDocumentId
          ? 'Crear nueva versión'
          : `Cargar ${queue.length || ''}`}</Button
    >
  </div>
</div>
