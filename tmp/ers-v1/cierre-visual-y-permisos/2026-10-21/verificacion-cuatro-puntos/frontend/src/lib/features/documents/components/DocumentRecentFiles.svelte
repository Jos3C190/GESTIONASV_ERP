<script lang="ts">
  import type { DocumentRecordOut } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';

  interface Props {
    documents: DocumentRecordOut[];
    loading?: boolean;
    onopen: (document: DocumentRecordOut) => void;
  }

  let { documents, loading = false, onopen }: Props = $props();

  function fileKind(extension: string): string {
    return extension.replace('.', '').toUpperCase() || 'FILE';
  }

  function formatSize(bytes: number): string {
    return bytes < 1048576
      ? `${Math.max(1, Math.round(bytes / 1024))} KB`
      : `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function formatDate(value: string | null): string {
    return value
      ? new Date(value).toLocaleDateString('es-SV', { day: 'numeric', month: 'short' })
      : '—';
  }
</script>

<section aria-labelledby="recent-documents-title">
  <div class="mb-3 flex items-center justify-between gap-3">
    <div>
      <h2 id="recent-documents-title" class="text-sm font-semibold text-foreground">Archivos recientes</h2>
      <p class="mt-0.5 text-xs text-foreground-muted">Últimos documentos disponibles para tu alcance.</p>
    </div>
  </div>

  {#if loading}
    <div class="space-y-2" aria-label="Cargando archivos recientes">
      {#each [1, 2, 3] as item (item)}<div class="skeleton h-16 rounded-xl border border-border"></div>{/each}
    </div>
  {:else if documents.length === 0}
    <div class="rounded-2xl border border-dashed border-border px-5 py-8 text-center">
      <p class="text-sm font-medium text-foreground">Aún no hay documentos recientes</p>
      <p class="mt-1 text-xs text-foreground-muted">Los archivos que cargues aparecerán aquí.</p>
    </div>
  {:else}
    <div class="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface-elevated">
      {#each documents as document (document.id)}
        <div class="flex min-h-[68px] items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-hover">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-[10px] font-semibold text-primary" aria-hidden="true">
            {fileKind(document.extension)}
          </div>
          <button type="button" class="min-h-11 min-w-0 flex-1 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2" onclick={() => onopen(document)}>
            <p class="truncate text-[13px] font-medium text-foreground">{document.title}</p>
            <p class="mt-0.5 truncate text-[11px] text-foreground-muted">
              {document.category_name ?? 'Otros'} · {formatSize(document.size_bytes)} · {formatDate(document.updated_at)}
            </p>
          </button>
          <Button variant="ghost" size="sm" onclick={() => onopen(document)}>Detalles</Button>
        </div>
      {/each}
    </div>
  {/if}
</section>
