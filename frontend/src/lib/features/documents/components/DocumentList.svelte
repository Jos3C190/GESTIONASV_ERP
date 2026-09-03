<script lang="ts">
  import type { DocumentRecordOut } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';

  interface Props {
    documents: DocumentRecordOut[];
    loading?: boolean;
    canDownload?: boolean;
    canDownloadDocument?: (document: DocumentRecordOut) => boolean;
    canUpdate?: boolean;
    canUpdateDocument?: (document: DocumentRecordOut) => boolean;
    canReplace?: boolean;
    canReplaceDocument?: (document: DocumentRecordOut) => boolean;
    canProcess?: boolean;
    canProcessDocument?: (document: DocumentRecordOut) => boolean;
    canDelete?: boolean;
    canDeleteDocument?: (document: DocumentRecordOut) => boolean;
    viewMode?: 'grid' | 'table';
    openingDocumentId?: string | null;
    ondownload?: (document: DocumentRecordOut) => void;
    onocrdownload?: (document: DocumentRecordOut) => void;
    onopenbrowser?: (document: DocumentRecordOut) => void;
    ondetail?: (document: DocumentRecordOut) => void;
    onupdate?: (document: DocumentRecordOut) => void;
    onreplace?: (document: DocumentRecordOut) => void;
    onversions?: (document: DocumentRecordOut) => void;
    onretry?: (document: DocumentRecordOut) => void;
    ondelete?: (document: DocumentRecordOut) => void;
  }

  let {
    documents,
    loading = false,
    canDownload = true,
    canDownloadDocument,
    canUpdate = false,
    canUpdateDocument,
    canReplace = false,
    canReplaceDocument,
    canProcess = false,
    canProcessDocument,
    canDelete = false,
    canDeleteDocument,
    viewMode = 'grid',
    openingDocumentId = null,
    ondownload,
    onocrdownload,
    onopenbrowser,
    ondetail,
    onupdate,
    onreplace,
    onversions,
    onretry,
    ondelete
  }: Props = $props();

  function statusLabel(document: DocumentRecordOut): string {
    return (
      {
        processing: 'Procesando',
        current: 'Vigente',
        active: 'Activo',
        expiring: 'Vence pronto',
        expired: 'Vencido',
        replaced: 'Reemplazado',
        quarantined: 'En cuarentena',
        rejected: 'Rechazado',
        deleted: 'En papelera'
      }[document.business_status] ?? document.business_status
    );
  }

  function statusClass(status: string): string {
    if (status === 'current' || status === 'active')
      return 'bg-success/10 text-success border-success/20';
    if (status === 'expiring') return 'bg-warning/10 text-warning border-warning/20';
    if (status === 'expired' || status === 'rejected' || status === 'quarantined')
      return 'bg-danger/10 text-danger border-danger/20';
    return 'bg-surface-muted text-foreground-muted border-border';
  }

  function formatDate(value: string | null): string {
    return value ? new Date(value).toLocaleDateString('es-SV') : 'Sin vencimiento';
  }

  function formatSize(bytes: number): string {
    return bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(bytes / 1024))} KB`
      : `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function fileKind(extension: string): string {
    return extension === '.pdf' ? 'PDF' : extension.replace('.', '').toUpperCase();
  }

  function allowed(
    fallback: boolean,
    resolver: ((document: DocumentRecordOut) => boolean) | undefined,
    document: DocumentRecordOut
  ): boolean {
    return resolver ? resolver(document) : fallback;
  }

  function secondaryActions(document: DocumentRecordOut): KebabItem[] {
    const items: KebabItem[] = [];
    if (
      allowed(canDownload, canDownloadDocument, document) &&
      document.extension === '.pdf' &&
      document.technical_status === 'active' &&
      onopenbrowser
    ) {
      const opening = openingDocumentId === document.id;
      items.push({
        id: 'open-browser',
        label: opening ? 'Abriendo…' : 'Abrir en navegador',
        icon: 'link',
        disabled: opening,
        onClick: () => onopenbrowser?.(document)
      });
    }
    if (allowed(canDownload, canDownloadDocument, document) && document.ocr_available && onocrdownload) {
      items.push({ id: 'ocr', label: 'Descargar OCR', icon: 'detail', onClick: () => onocrdownload?.(document) });
    }
    if (
      document.ocr_status === 'failed' &&
      allowed(canProcess, canProcessDocument, document) &&
      onretry
    ) {
      items.push({ id: 'ocr-retry', label: 'Reintentar OCR', icon: 'custom', onClick: () => onretry?.(document) });
    }
    if (allowed(canUpdate, canUpdateDocument, document) && document.business_status !== 'deleted' && onupdate) {
      items.push({ id: 'edit', label: 'Editar metadatos', icon: 'edit', onClick: () => onupdate?.(document) });
    }
    if (
      allowed(canReplace, canReplaceDocument, document) &&
      document.business_status === 'current' &&
      document.technical_status === 'active' &&
      onreplace
    ) {
      items.push({ id: 'replace', label: 'Reemplazar archivo', icon: 'custom', onClick: () => onreplace?.(document) });
    }
    if (onversions) {
      items.push({ id: 'versions', label: 'Ver versiones', icon: 'variants', onClick: () => onversions?.(document) });
    }
    if (allowed(canDelete, canDeleteDocument, document) && document.business_status !== 'deleted' && ondelete) {
      items.push({ id: 'delete', label: 'Enviar a papelera', icon: 'delete', variant: 'danger', onClick: () => ondelete?.(document) });
    }
    return items;
  }
</script>

{#if loading}
  <div class="grid gap-3 md:grid-cols-2">
    {#each [1, 2, 3, 4] as item (item)}<div
        class="h-32 animate-pulse rounded-xl border border-border bg-surface-muted/40"
      ></div>{/each}
  </div>
{:else if documents.length === 0}
  <div class="rounded-xl border border-dashed border-border px-6 py-12 text-center">
    <div
      class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        aria-hidden="true"
        ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path
          d="M14 2v6h6"
        /></svg
      >
    </div>
    <p class="mt-3 text-sm font-medium text-foreground">Aún no hay documentos</p>
    <p class="mt-1 text-xs text-foreground-muted">
      Cargue el primer documento para iniciar el expediente.
    </p>
  </div>
{:else if viewMode === 'grid'}
  <div class="grid gap-3 md:grid-cols-2">
    {#each documents as document (document.id)}
      <article
        class="group rounded-xl border border-border bg-surface-elevated p-4 transition hover:border-border-strong hover:shadow-soft"
      >
        <div class="flex items-start gap-3">
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg {document.extension ===
            '.pdf'
              ? 'bg-danger/10 text-danger'
              : 'bg-primary/10 text-primary'} text-xs font-bold"
          >
            {fileKind(document.extension)}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <h3 class="truncate text-sm font-semibold text-foreground" title={document.title}>
                  {document.title}
                </h3>
                <p
                  class="truncate text-xs text-foreground-subtle"
                  title={document.original_filename}
                >
                  {document.original_filename}
                </p>
              </div>
              <span
                class="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-medium {statusClass(
                  document.business_status
                )}">{statusLabel(document)}</span
              >
            </div>
            <div
              class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-foreground-muted"
            >
              <span>{document.category_name ?? 'Otros'}</span><span
                >{formatSize(document.size_bytes)}</span
              ><span>{formatDate(document.expires_on)}</span>
              {#if document.version_number > 1}<span>v{document.version_number}</span>{/if}
            </div>
            {#if document.owner_label}<p class="mt-2 truncate text-xs text-foreground-muted">
                Propietario: {document.owner_label}{document.owner_deleted ? ' · eliminado' : ''}
              </p>{/if}
            {#if document.ocr_available}<span
                class="mt-2 inline-flex items-center gap-1 text-[11px] text-primary"
                ><span class="h-1.5 w-1.5 rounded-full bg-primary"></span>PDF buscable disponible</span
              >{:else if document.ocr_status === 'processing' || document.ocr_status === 'pending'}<span
                class="mt-2 inline-flex items-center gap-1 text-[11px] text-foreground-muted"
                ><span class="h-1.5 w-1.5 animate-pulse rounded-full bg-foreground-muted"></span>OCR
                en proceso</span
              >{:else if document.ocr_status === 'failed' && allowed(canProcess, canProcessDocument, document)}<button
                type="button"
                class="mt-2 text-[11px] text-warning hover:underline"
                onclick={() => onretry?.(document)}>Reintentar OCR</button
              >{/if}
          </div>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {#if ondetail}<Button variant="ghost" size="sm" class="min-h-11" onclick={() => ondetail?.(document)}
              >Detalles</Button
            >{/if}
          {#if allowed(canDownload, canDownloadDocument, document) && document.technical_status === 'active'}<Button
              variant="secondary"
              size="sm"
              class="min-h-11" onclick={() => ondownload?.(document)}>Descargar</Button
            >{/if}
          {#if secondaryActions(document).length > 0}<KebabMenu
              items={secondaryActions(document)}
              ariaLabel={`Más acciones para ${document.title}`}
              triggerClass="h-11 w-11"
            />{/if}
        </div>
      </article>
    {/each}
  </div>
{:else}
  <div class="space-y-2 md:hidden">
    {#each documents as document (document.id)}
      <article class="rounded-xl border border-border bg-surface-elevated p-4">
        <div class="flex items-start gap-3">
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg {document.extension ===
            '.pdf'
              ? 'bg-danger/10 text-danger'
              : 'bg-primary/10 text-primary'} text-[10px] font-bold"
            aria-hidden="true">{fileKind(document.extension)}</span
          >
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <h3 class="truncate text-sm font-semibold text-foreground" title={document.title}>
                {document.title}
              </h3>
              <span
                class="inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium {statusClass(
                  document.business_status
                )}"
                >{statusLabel(document)}</span
              >
            </div>
            <p class="mt-1 truncate text-xs text-foreground-subtle" title={document.original_filename}>
              {document.original_filename}
            </p>
            <p class="mt-2 text-[11px] text-foreground-muted">
              {document.category_name ?? 'Otros'} · {formatSize(document.size_bytes)} · {formatDate(document.expires_on)}
            </p>
            {#if document.owner_label}<p class="mt-1 truncate text-[11px] text-foreground-muted">
                {document.owner_label}
              </p>{/if}
            {#if document.ocr_available}<p class="mt-1 text-[11px] text-primary">PDF buscable disponible</p>{/if}
          </div>
        </div>
          <div class="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
          {#if ondetail}<Button variant="ghost" size="sm" class="min-h-11" onclick={() => ondetail?.(document)}>Detalles</Button>{/if}
          {#if allowed(canDownload, canDownloadDocument, document) && document.technical_status === 'active'}<Button variant="secondary" size="sm" class="min-h-11" onclick={() => ondownload?.(document)}>Descargar</Button>{/if}
          {#if secondaryActions(document).length > 0}<KebabMenu items={secondaryActions(document)} ariaLabel={`Más acciones para ${document.title}`} triggerClass="h-11 w-11" />{/if}
        </div>
      </article>
    {/each}
  </div>
  <div class="hidden overflow-x-auto rounded-xl border border-border md:block">
    <table class="min-w-full divide-y divide-border text-left">
      <thead class="bg-surface-muted/50">
        <tr class="text-[11px] uppercase tracking-wider text-foreground-subtle">
          <th class="px-4 py-3 font-semibold">Documento</th>
          <th class="px-4 py-3 font-semibold">Categoría</th>
          <th class="px-4 py-3 font-semibold">Estado</th>
          <th class="px-4 py-3 font-semibold">Vencimiento</th>
          <th class="px-4 py-3 text-right font-semibold">Acciones</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border bg-surface-elevated">
        {#each documents as document (document.id)}
          <tr class="align-top transition hover:bg-surface-hover/50">
            <td class="max-w-[280px] px-4 py-3">
              <div class="flex items-center gap-3">
                <span
                  class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg {document.extension ===
                  '.pdf'
                    ? 'bg-danger/10 text-danger'
                    : 'bg-primary/10 text-primary'} text-[10px] font-bold"
                  >{fileKind(document.extension)}</span
                >
                <div class="min-w-0">
                  <p class="truncate text-sm font-semibold text-foreground" title={document.title}>
                    {document.title}
                  </p>
                  <p class="truncate text-xs text-foreground-subtle">
                    {document.original_filename} · {formatSize(document.size_bytes)}
                  </p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3 text-xs text-foreground-muted">
              <p>{document.category_name ?? 'Otros'}</p>
              {#if document.owner_label}<p class="mt-1 truncate max-w-[180px]">
                  {document.owner_label}
                </p>{/if}
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium {statusClass(
                  document.business_status
                )}">{statusLabel(document)}</span
              >
              {#if document.ocr_available}<p class="mt-1 text-[10px] text-primary">
                  PDF buscable
                </p>{/if}
            </td>
            <td class="whitespace-nowrap px-4 py-3 text-xs text-foreground-muted">
              {formatDate(document.expires_on)}
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap justify-end gap-1">
                {#if ondetail}<Button variant="ghost" size="sm" class="min-h-11" onclick={() => ondetail?.(document)}
                    >Detalles</Button
                  >{/if}
                {#if allowed(canDownload, canDownloadDocument, document) && document.technical_status === 'active'}<Button
                    variant="secondary"
                    size="sm"
                    class="min-h-11" onclick={() => ondownload?.(document)}>Descargar</Button
                  >{/if}
                {#if secondaryActions(document).length > 0}<KebabMenu
                    items={secondaryActions(document)}
                    ariaLabel={`Más acciones para ${document.title}`}
                    triggerClass="h-11 w-11"
                  />{/if}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
