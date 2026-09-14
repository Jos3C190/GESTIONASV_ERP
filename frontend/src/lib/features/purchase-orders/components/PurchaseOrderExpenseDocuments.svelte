<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import {
    DOCUMENT_ACCEPT,
    DOCUMENT_MAX_BYTES,
    documentContentType,
    isSupportedDocumentFile
  } from '$lib/features/documents/document-upload';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type {
    PurchaseOrderExpense,
    PurchaseOrderExpenseDocument,
    PurchaseOrderExpenseDocumentUpload,
    PurchaseOrderStatus
  } from '$lib/types/purchase-order';

  let {
    orderId,
    expense,
    orderStatus
  }: {
    orderId: string;
    expense: PurchaseOrderExpense;
    orderStatus: PurchaseOrderStatus;
  } = $props();

  let documents = $state<PurchaseOrderExpenseDocument[]>([]);
  let loading = $state(true);
  let uploading = $state(false);
  let downloadingId = $state<string | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let requestSequence = 0;

  let canRead = $derived(permissions.hasPermission('purchase_orders:read'));
  let canManage = $derived(permissions.hasPermission('purchase_orders:manage'));
  let canUpload = $derived(canManage && orderStatus !== 'draft');

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

  async function checksum(file: File): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
      ''
    );
  }

  async function uploadDirect(ticket: PurchaseOrderExpenseDocumentUpload, file: File) {
    const response = await fetch(ticket.upload_url, {
      method: ticket.method,
      headers: ticket.required_headers,
      body: file,
      credentials: 'omit'
    });

    if (!response.ok) {
      throw new Error('No se pudo cargar el documento al almacenamiento seguro.');
    }
  }

  async function loadDocuments(currentOrderId: string, currentExpenseId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const response = await purchaseOrdersApi.listExpenseDocuments(
        currentOrderId,
        currentExpenseId
      );
      if (sequence !== requestSequence) return;
      documents = response;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;
      documents = [];
      error = errorMessage(cause, 'No se pudieron cargar los documentos del gasto.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  async function chooseFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file || uploading || !canUpload) return;

    if (!isSupportedDocumentFile(file, DOCUMENT_MAX_BYTES)) {
      error = 'Selecciona un documento permitido de hasta 50 MB.';
      notice = null;
      return;
    }

    uploading = true;
    error = null;
    notice = null;

    try {
      const sha = await checksum(file);
      const ticket = await purchaseOrdersApi.initiateExpenseDocument(orderId, expense.id, {
        file_name: file.name,
        content_type: documentContentType(file),
        size_bytes: file.size,
        checksum_sha256: sha
      });

      await uploadDirect(ticket, file);
      await purchaseOrdersApi.completeExpenseDocument(
        orderId,
        expense.id,
        ticket.document.document_id
      );
      await loadDocuments(orderId, expense.id);
      notice = 'Documento adjuntado correctamente.';
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo adjuntar el documento al gasto.');
    } finally {
      uploading = false;
    }
  }

  async function downloadDocument(document: PurchaseOrderExpenseDocument) {
    if (downloadingId) return;

    downloadingId = document.id;
    error = null;
    notice = null;

    try {
      const result = await purchaseOrdersApi.createExpenseDocumentDownloadUrl(
        orderId,
        expense.id,
        document.document_id
      );
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo preparar la descarga del documento.');
    } finally {
      downloadingId = null;
    }
  }

  $effect(() => {
    const readAllowed = canRead;
    const currentOrderId = orderId;
    const currentExpenseId = expense.id;

    if (!readAllowed) {
      documents = [];
      loading = false;
      return;
    }

    void loadDocuments(currentOrderId, currentExpenseId);
  });
</script>

{#if canRead}
  <div class="rounded-lg border border-border bg-surface-muted/40 p-3">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">
          Documentos
        </p>
        <p class="mt-1 text-xs text-foreground-muted">
          Comprobantes asociados a este gasto de la orden.
        </p>
      </div>

      {#if canUpload}
        <label
          class="inline-flex h-9 cursor-pointer items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground hover:bg-surface-muted"
        >
          {uploading ? 'Adjuntando…' : 'Adjuntar documento'}
          <input
            class="sr-only"
            type="file"
            accept={DOCUMENT_ACCEPT}
            disabled={uploading}
            aria-label="Adjuntar documento al gasto"
            onchange={chooseFile}
          />
        </label>
      {/if}
    </div>

    {#if orderStatus === 'draft'}
      <p class="mt-3 text-xs text-foreground-muted">
        Los documentos se habilitan cuando la orden deja de estar en borrador y los gastos son
        estables.
      </p>
    {/if}

    {#if error}
      <div
        class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
        role="alert"
      >
        {error}
      </div>
    {/if}

    {#if notice}
      <p class="mt-3 text-xs text-success" role="status">{notice}</p>
    {/if}

    {#if loading}
      <div class="mt-3 space-y-2" aria-label="Cargando documentos">
        <div class="skeleton h-8 rounded"></div>
        <div class="skeleton h-8 rounded"></div>
      </div>
    {:else if documents.length === 0}
      <p class="mt-3 text-xs text-foreground-muted">Sin documentos adjuntos.</p>
    {:else}
      <ul class="mt-3 divide-y divide-border rounded-lg border border-border bg-surface">
        {#each documents as document (document.id)}
          <li class="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-foreground">{document.file_name}</p>
              <p class="mt-0.5 text-xs text-foreground-muted">
                {formatSize(document.size_bytes)} · {document.status}
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              disabled={downloadingId !== null}
              onclick={() => void downloadDocument(document)}
            >
              {downloadingId === document.id ? 'Preparando…' : 'Descargar'}
            </Button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}
