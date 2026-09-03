<script lang="ts">
  import { onMount } from 'svelte';
  import type { DocumentRecordOut } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';

  interface Props {
    document: DocumentRecordOut;
    onclose: () => void;
    ondownload?: (document: DocumentRecordOut) => void;
    onocrdownload?: (document: DocumentRecordOut) => void;
    onopenbrowser?: (document: DocumentRecordOut) => void;
    opening?: boolean;
    onversions?: (document: DocumentRecordOut) => void;
    onupdate?: (document: DocumentRecordOut) => void;
    onreplace?: (document: DocumentRecordOut) => void;
  }

  let {
    document,
    onclose,
    ondownload,
    onocrdownload,
    onopenbrowser,
    opening = false,
    onversions,
    onupdate,
    onreplace
  }: Props = $props();

  let panel = $state<HTMLDivElement | null>(null);
  let closeButton = $state<HTMLButtonElement | null>(null);

  onMount(() => {
    const dom = globalThis.document;
    const returnFocus = dom.activeElement instanceof HTMLElement ? dom.activeElement : null;
    const previousOverflow = dom.body.style.overflow;
    dom.body.style.overflow = 'hidden';

    const focusPanel = () => closeButton?.focus();
    const frame = requestAnimationFrame(focusPanel);

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onclose();
        return;
      }
      if (event.key !== 'Tab' || !panel) return;
      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (focusable.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && dom.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && dom.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }

    window.addEventListener('keydown', handleKeydown);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('keydown', handleKeydown);
      dom.body.style.overflow = previousOverflow;
      requestAnimationFrame(() => returnFocus?.focus());
    };
  });

  function formatDate(value: string | null): string {
    return value ? new Date(value).toLocaleDateString('es-SV') : 'Sin fecha';
  }

  function formatSize(bytes: number): string {
    return bytes < 1024 * 1024
      ? String(Math.max(1, Math.round(bytes / 1024))) + ' KB'
      : (bytes / 1048576).toFixed(1) + ' MB';
  }

  function statusLabel(status: string): string {
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
      }[status] ?? status
    );
  }

  function statusClass(status: string): string {
    if (status === 'current' || status === 'active')
      return 'border-success/20 bg-success/10 text-success';
    if (status === 'expiring') return 'border-warning/20 bg-warning/10 text-warning';
    if (status === 'expired' || status === 'rejected' || status === 'quarantined')
      return 'border-danger/20 bg-danger/10 text-danger';
    return 'border-border bg-surface-muted text-foreground-muted';
  }
</script>

<div class="fixed inset-0 z-50 flex justify-end bg-black/45" role="presentation">
  <button
    type="button"
    class="absolute inset-0 cursor-default"
    aria-label="Cerrar detalle del documento"
    onclick={onclose}
  ></button>
  <div
    bind:this={panel}
    class="relative flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-border bg-surface-elevated shadow-floating focus:outline-none"
    role="dialog"
    aria-modal="true"
    aria-labelledby="document-detail-title"
    tabindex="-1"
  >
    <div class="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div class="min-w-0">
        <p class="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
          Detalle documental
        </p>
        <h2 id="document-detail-title" class="mt-1 truncate text-lg font-semibold text-foreground">
          {document.title}
        </h2>
        <p class="mt-1 truncate text-xs text-foreground-muted" title={document.original_filename}>
          {document.original_filename}
        </p>
      </div>
      <button
        type="button"
        bind:this={closeButton}
        class="flex h-11 w-11 items-center justify-center rounded-lg text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        aria-label="Cerrar detalle"
        onclick={onclose}>×</button
      >
    </div>

    <div class="flex-1 space-y-5 px-5 py-5">
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium {statusClass(
            document.business_status
          )}">{statusLabel(document.business_status)}</span
        >
        <span class="rounded-full border border-border px-2.5 py-1 text-xs text-foreground-muted"
          >{document.confidentiality === 'restricted' ? 'Restringido' : 'Interno'}</span
        >
        {#if document.ocr_available}<span
            class="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-xs text-primary"
            >PDF buscable</span
          >{/if}
      </div>

      <dl class="divide-y divide-border rounded-xl border border-border">
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Módulo</dt>
          <dd class="text-right text-xs font-medium text-foreground">
            {document.module === 'employees' ? 'Empleados' : 'General'}
          </dd>
        </div>
        {#if document.owner_label}<div class="grid grid-cols-2 gap-3 px-4 py-3">
            <dt class="text-xs text-foreground-muted">Propietario</dt>
            <dd class="text-right text-xs font-medium text-foreground">
              {document.owner_label}{document.owner_deleted ? ' · eliminado' : ''}
            </dd>
          </div>{/if}
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Categoría</dt>
          <dd class="text-right text-xs font-medium text-foreground">
            {document.category_name ?? 'Otros'}{#if document.category_group}<span
                class="block text-[11px] font-normal text-foreground-muted"
                >{document.category_group}</span
              >{/if}
          </dd>
        </div>
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Formato y tamaño</dt>
          <dd class="text-right text-xs font-medium uppercase text-foreground">
            {document.extension.replace('.', '')} · {formatSize(document.size_bytes)}
          </dd>
        </div>
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Versión</dt>
          <dd class="text-right text-xs font-medium text-foreground">
            {document.version_number}{document.is_current ? ' · vigente' : ' · histórica'}
          </dd>
        </div>
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Emisión</dt>
          <dd class="text-right text-xs font-medium text-foreground">
            {formatDate(document.issued_on)}
          </dd>
        </div>
        <div class="grid grid-cols-2 gap-3 px-4 py-3">
          <dt class="text-xs text-foreground-muted">Vencimiento</dt>
          <dd
            class="text-right text-xs font-medium {document.business_status === 'expired'
              ? 'text-danger'
              : document.business_status === 'expiring'
                ? 'text-warning'
                : 'text-foreground'}"
          >
            {formatDate(document.expires_on)}
          </dd>
        </div>
        {#if document.issuer}<div class="grid grid-cols-2 gap-3 px-4 py-3">
            <dt class="text-xs text-foreground-muted">Emisor</dt>
            <dd class="text-right text-xs font-medium text-foreground">{document.issuer}</dd>
          </div>{/if}
        {#if document.reference_code}<div class="grid grid-cols-2 gap-3 px-4 py-3">
            <dt class="text-xs text-foreground-muted">Referencia</dt>
            <dd class="text-right text-xs font-medium text-foreground">
              {document.reference_code}
            </dd>
          </div>{/if}
      </dl>

      {#if document.description}<div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Descripción
          </p>
          <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground-muted">
            {document.description}
          </p>
        </div>{/if}
      {#if document.tags.length > 0}<div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Etiquetas
          </p>
          <div class="mt-2 flex flex-wrap gap-1.5">
            {#each document.tags as tag (tag)}<span
                class="rounded-full bg-surface-muted px-2.5 py-1 text-xs text-foreground-muted"
                >{tag}</span
              >{/each}
          </div>
        </div>{/if}
    </div>

    <div class="flex flex-wrap gap-2 border-t border-border px-5 py-4">
      {#if ondownload && document.technical_status === 'active'}<Button
          variant="secondary"
          size="sm"
          class="min-h-11"
          onclick={() => ondownload?.(document)}>Descargar</Button
        >{/if}
      {#if onopenbrowser && document.extension === '.pdf' && document.technical_status === 'active'}<Button
          variant="ghost"
          size="sm"
          class="min-h-11"
          disabled={opening}
          onclick={() => onopenbrowser?.(document)}>{opening ? 'Abriendo…' : 'Abrir en navegador'}</Button
        >{/if}
      {#if onocrdownload && document.ocr_available}<Button
          variant="ghost"
          size="sm"
          class="min-h-11"
          onclick={() => onocrdownload?.(document)}>Descargar OCR</Button
        >{/if}
      {#if onupdate && document.business_status !== 'deleted'}<Button
          variant="ghost"
          size="sm"
          class="min-h-11"
          onclick={() => onupdate?.(document)}>Editar</Button
        >{/if}
      {#if onreplace && document.business_status === 'current' && document.technical_status === 'active'}<Button
          variant="ghost"
          size="sm"
          class="min-h-11"
          onclick={() => onreplace?.(document)}>Reemplazar</Button
        >{/if}
      {#if onversions}<Button variant="ghost" size="sm" class="min-h-11" onclick={() => onversions?.(document)}
          >Versiones</Button
        >{/if}
    </div>
  </div>
</div>
