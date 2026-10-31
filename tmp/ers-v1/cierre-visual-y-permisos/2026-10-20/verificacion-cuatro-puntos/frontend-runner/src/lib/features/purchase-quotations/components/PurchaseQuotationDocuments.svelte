<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import {
    DOCUMENT_ACCEPT,
    DOCUMENT_MAX_BYTES,
    documentContentType,
    isSupportedDocumentFile
  } from '$lib/features/documents/document-upload';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type {
    PurchaseQuotationDocument,
    PurchaseQuotationDocumentUpload,
    PurchaseQuotationStatus
  } from '$lib/types/purchase-quotation';

  let {
    quotationId,
    quotationStatus,
    consolidationId = null
  }: {
    quotationId: string;
    quotationStatus: PurchaseQuotationStatus;
    consolidationId?: string | null;
  } = $props();

  let documents = $state<PurchaseQuotationDocument[]>([]);
  let loading = $state(true);
  let loadFailed = $state(false);
  let uploading = $state(false);
  let downloadingId = $state<string | null>(null);
  let removingId = $state<string | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let requestSequence = 0;

  let canRead = $derived(permissions.hasPermission('purchase_quotations:read'));
  let canManage = $derived(permissions.hasPermission('purchase_quotations:manage'));
  let canUpload = $derived(
    canManage &&
      (quotationStatus === 'requested' ||
        quotationStatus === 'received' ||
        quotationStatus === 'under_evaluation')
  );

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function formatSize(sizeBytes: number): string {
    if (sizeBytes < 1024) return `${sizeBytes} B`;
    if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function statusLabel(status: string): string {
    if (status === 'active') return 'Disponible';
    if (status === 'pending_scan' || status === 'scanning') return 'En revisión de seguridad';
    if (status === 'pending_upload') return 'Carga pendiente';
    if (status === 'quarantined' || status === 'rejected') return 'No disponible';
    return status;
  }

  async function checksum(file: File): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
      ''
    );
  }

  async function uploadDirect(ticket: PurchaseQuotationDocumentUpload, file: File) {
    const response = await fetch(ticket.upload_url, {
      method: ticket.method,
      headers: ticket.required_headers,
      body: file,
      credentials: 'omit'
    });
    if (!response.ok) throw new Error('No se pudo cargar el documento al almacenamiento seguro.');
  }

  async function loadDocuments(currentId: string): Promise<boolean> {
    const sequence = ++requestSequence;
    loading = true;
    loadFailed = false;
    error = null;

    try {
      const result = await purchaseQuotationsApi.listDocuments(
        currentId,
        undefined,
        consolidationId
      );
      if (sequence !== requestSequence) return false;
      documents = result;
      loadFailed = false;
      return true;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return false;
      error = errorMessage(cause, 'No se pudieron cargar los documentos de la oferta.');
      loadFailed = true;
      return false;
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  async function chooseFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file || uploading || downloadingId || removingId || !canUpload) return;

    if (!isSupportedDocumentFile(file, DOCUMENT_MAX_BYTES)) {
      error = 'Selecciona un documento permitido de hasta 50 MB.';
      notice = null;
      return;
    }

    uploading = true;
    error = null;
    notice = null;

    try {
      const ticket = await purchaseQuotationsApi.initiateDocument(
        quotationId,
        {
          file_name: file.name,
          content_type: documentContentType(file),
          size_bytes: file.size,
          checksum_sha256: await checksum(file)
        },
        undefined,
        consolidationId
      );
      await uploadDirect(ticket, file);
      const completedDocument = await purchaseQuotationsApi.completeDocument(
        quotationId,
        ticket.document.document_id,
        undefined,
        consolidationId
      );
      documents = [
        ...documents.filter((document) => document.document_id !== completedDocument.document_id),
        completedDocument
      ];
      notice = 'Oferta original adjuntada correctamente. Los datos de la respuesta siguen guardados en el formulario.';
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo adjuntar la oferta original.');
    } finally {
      uploading = false;
    }
  }

  async function downloadDocument(document: PurchaseQuotationDocument) {
    if (downloadingId || uploading || removingId) return;
    const downloadWindow = window.open('about:blank', '_blank');
    if (!downloadWindow) {
      error =
        'El navegador bloqueó la descarga. Permite las ventanas emergentes para este sitio e inténtalo de nuevo.';
      notice = null;
      return;
    }
    downloadWindow.opener = null;
    downloadingId = document.id;
    error = null;
    notice = null;

    try {
      const result = await purchaseQuotationsApi.createDocumentDownloadUrl(
        quotationId,
        document.document_id,
        undefined,
        consolidationId
      );
      downloadWindow.location.href = result.url;
    } catch (cause: unknown) {
      downloadWindow.close();
      error = errorMessage(cause, 'No se pudo preparar la descarga.');
    } finally {
      downloadingId = null;
    }
  }

  async function removeDocument(document: PurchaseQuotationDocument) {
    if (!canUpload || uploading || downloadingId || removingId) return;
    removingId = document.id;
    error = null;
    notice = null;

    try {
      await purchaseQuotationsApi.removeDocument(
        quotationId,
        document.document_id,
        undefined,
        consolidationId
      );
      documents = documents.filter((item) => item.id !== document.id);
      notice = 'El adjunto se quitó de esta respuesta. El archivo original se conserva.';
    } catch (cause: unknown) {
      throw new Error(errorMessage(cause, 'No se pudo quitar el archivo de la respuesta.'));
    } finally {
      removingId = null;
    }
  }

  function requestRemoveDocument(document: PurchaseQuotationDocument) {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar archivo adjunto',
      description:
        'El archivo dejará de aparecer en esta respuesta del proveedor, pero el original se conservará. La acción quedará registrada en la bitácora.',
      confirmLabel: 'Quitar archivo',
      resourceName: document.file_name,
      execute: () => removeDocument(document)
    });
  }

  $effect(() => {
    const readAllowed = canRead;
    const currentId = quotationId;
    if (!readAllowed || !currentId) {
      documents = [];
      loading = false;
      loadFailed = false;
      return;
    }
    void loadDocuments(currentId);
  });
</script>

{#if canRead}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-labelledby="quotation-documents-title"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 id="quotation-documents-title" class="font-semibold text-foreground">
          Oferta original del proveedor
        </h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Adjunta el PDF, Excel u otro archivo recibido como respaldo de las cantidades y precios
          registrados.
        </p>
        <p class="mt-1 text-xs text-foreground-muted">
          Adjuntar o quitar un archivo no envía ni borra los datos capturados arriba. Usa «Registrar respuesta» para guardar la cotización.
        </p>
      </div>
      {#if canUpload}
        <label
          class="relative inline-flex min-h-10 cursor-pointer items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground hover:bg-surface-muted focus-within:outline-none focus-within:ring-2 focus-within:ring-primary"
        >
          {uploading ? 'Adjuntando…' : 'Adjuntar oferta'}
          <input
            class="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
            type="file"
            accept={DOCUMENT_ACCEPT}
            disabled={loading || uploading || downloadingId !== null || removingId !== null}
            aria-label="Adjuntar archivo original de la oferta del proveedor"
            onchange={chooseFile}
          />
        </label>
      {/if}
    </div>

    {#if error}
      <div class="mt-3 flex flex-col gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-sm text-danger" role="alert">{error}</p>
        {#if loadFailed}
          <Button
            size="sm"
            variant="secondary"
            disabled={loading}
            onclick={() => void loadDocuments(quotationId)}
          >
            {loading ? 'Cargando…' : 'Reintentar carga'}
          </Button>
        {/if}
      </div>
    {/if}
    {#if notice}
      <p class="mt-3 text-sm text-success" role="status">{notice}</p>
    {/if}

    {#if loading}
      <div
        class="mt-4 space-y-2"
        role="status"
        aria-label="Cargando archivos de la oferta"
        aria-busy="true"
      >
        <div class="skeleton h-10 rounded-lg"></div>
      </div>
    {:else if documents.length === 0}
      <p class="mt-3 text-sm text-foreground-muted">
        Aún no hay un archivo adjunto. Puedes guardar los datos de la respuesta sin documento y
        agregarlo después.
      </p>
    {:else}
      <ul class="mt-4 divide-y divide-border rounded-lg border border-border">
        {#each documents as document (document.id)}
          <li class="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <p class="break-all text-sm font-medium text-foreground">{document.file_name}</p>
              <p class="mt-1 text-xs text-foreground-muted">
                {formatSize(document.size_bytes)} · {statusLabel(document.status)}
              </p>
              {#if document.status === 'quarantined' || document.status === 'rejected'}
                <p class="mt-1 text-xs text-warning">
                  No se puede descargar un archivo rechazado por seguridad.
                  {canUpload
                    ? ' Adjunta una versión válida.'
                    : ' Solicita revisión al administrador.'}
                </p>
              {/if}
            </div>
            <div class="flex flex-wrap gap-2 sm:justify-end">
              <Button
                size="sm"
                variant="secondary"
                disabled={uploading ||
                  removingId !== null ||
                  downloadingId !== null ||
                  document.status !== 'active'}
                onclick={() => void downloadDocument(document)}
              >
                {downloadingId === document.id ? 'Preparando…' : 'Descargar'}
              </Button>
              {#if canUpload}
                <Button
                  size="sm"
                  variant="danger"
                  disabled={uploading || removingId !== null || downloadingId !== null}
                  onclick={() => requestRemoveDocument(document)}
                >
                  {removingId === document.id ? 'Quitando…' : 'Quitar adjunto'}
                </Button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}
