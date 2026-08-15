<script lang="ts">
  import { onDestroy } from 'svelte';
  import { HttpError, type PageMeta } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { getLocationBatch } from '../services';
  import type { LocationBatchJob, LocationBatchRow } from '../types';

  interface Props {
    job: LocationBatchJob;
    pageSize?: number;
  }

  let { job, pageSize = 100 }: Props = $props();
  let pageJob = $state<LocationBatchJob | null>(null);
  let currentPage = $state(1);
  let loading = $state(false);
  let loadError = $state<string | null>(null);
  let contextJobId = $state('');
  let controller: AbortController | null = null;
  let displayedJob = $derived(pageJob ?? job);

  let pageMeta = $derived.by((): PageMeta => {
    const received = displayedJob.rows_meta ?? displayedJob.meta;
    if (received) return received;
    return {
      page: currentPage,
      size: pageSize,
      total: displayedJob.total_rows,
      pages: Math.max(1, Math.ceil(displayedJob.total_rows / pageSize))
    };
  });
  let visibleRows = $derived.by(() => {
    if (displayedJob.rows.length <= pageSize) return displayedJob.rows;
    const offset = (currentPage - 1) * pageSize;
    return displayedJob.rows.slice(offset, offset + pageSize);
  });
  let firstVisibleRow = $derived(
    visibleRows.length === 0 ? 0 : (pageMeta.page - 1) * pageMeta.size + 1
  );
  let lastVisibleRow = $derived(
    visibleRows.length === 0
      ? 0
      : Math.min(pageMeta.total, firstVisibleRow + visibleRows.length - 1)
  );

  $effect(() => {
    if (job.id === contextJobId) return;
    contextJobId = job.id;
    controller?.abort();
    pageJob = job;
    currentPage = job.rows_meta?.page ?? job.meta?.page ?? 1;
    loadError = null;
  });

  async function goToPage(nextPage: number) {
    if (loading || nextPage < 1 || nextPage > pageMeta.pages || nextPage === currentPage) return;
    controller?.abort();
    controller = new AbortController();
    loading = true;
    loadError = null;
    try {
      const result = await getLocationBatch(job.id, nextPage, pageSize, controller.signal);
      pageJob = result;
      currentPage = result.rows_meta?.page ?? result.meta?.page ?? nextPage;
    } catch (cause) {
      if (controller.signal.aborted) return;
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar esta página del lote.';
    } finally {
      if (!controller.signal.aborted) loading = false;
    }
  }

  onDestroy(() => controller?.abort());

  function variant(operation: string): 'success' | 'warning' | 'danger' | 'neutral' | 'primary' {
    if (operation === 'create') return 'success';
    if (operation === 'update') return 'primary';
    if (operation === 'conflict' || operation === 'error') return 'danger';
    return 'neutral';
  }

  function operationLabel(operation: string): string {
    return (
      (
        {
          create: 'Crear',
          update: 'Actualizar',
          unchanged: 'Sin cambios',
          conflict: 'Conflicto',
          error: 'Error'
        } as Record<string, string>
      )[operation] ?? operation
    );
  }

  function rowRoute(row: LocationBatchRow): string {
    const data = row.normalized_data;
    return [data.area, data.aisle, data.rack, data.level, data.position]
      .filter(Boolean)
      .map(String)
      .join(' › ');
  }

  function diffSummary(row: LocationBatchRow): string[] {
    return Object.entries(row.diff)
      .slice(0, 4)
      .map(([field, change]) => {
        if (change && typeof change === 'object' && !Array.isArray(change)) {
          const value = change as Record<string, unknown>;
          const before = value.before ?? value.old ?? value.from;
          const after = value.after ?? value.new ?? value.to;
          if (before !== undefined || after !== undefined) {
            return `${field}: ${String(before ?? '—')} → ${String(after ?? '—')}`;
          }
        }
        return `${field}: ${typeof change === 'string' ? change : JSON.stringify(change)}`;
      });
  }
</script>

<div class="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
  {#each [['Total', job.total_rows, 'neutral'], ['Nuevas', job.create_count, 'success'], ['Cambios', job.update_count, 'primary'], ['Sin cambios', job.unchanged_count, 'neutral'], ['Conflictos', job.conflict_count, 'warning'], ['Errores', job.error_count, 'danger']] as metric (metric[0])}
    <div class="rounded-xl border border-border bg-surface-muted/40 p-3">
      <p class="text-xs text-foreground-muted">{metric[0]}</p>
      <p class="mt-1 font-mono text-lg font-semibold text-foreground">
        {Number(metric[1]).toLocaleString('es-SV')}
      </p>
    </div>
  {/each}
</div>

<div class="mt-4 overflow-hidden rounded-xl border border-border">
  <div class="max-h-[340px] overflow-auto">
    <table class="w-full min-w-[680px] text-xs">
      <thead class="sticky top-0 z-10 border-b border-border bg-surface-muted">
        <tr>
          <th class="px-3 py-2 text-left font-semibold">Fila</th>
          <th class="px-3 py-2 text-left font-semibold">Acción</th>
          <th class="px-3 py-2 text-left font-semibold">Código</th>
          <th class="px-3 py-2 text-left font-semibold">Ruta normalizada</th>
          <th class="px-3 py-2 text-left font-semibold">Observaciones</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border">
        {#each visibleRows as row (row.id || row.row_number)}
          {@const changes = diffSummary(row)}
          <tr class="align-top">
            <td class="px-3 py-2 font-mono text-foreground-muted">{row.row_number}</td>
            <td class="px-3 py-2"
              ><Badge variant={variant(row.operation)}>{operationLabel(row.operation)}</Badge></td
            >
            <td class="px-3 py-2 font-mono font-medium text-foreground">{row.code ?? '—'}</td>
            <td class="px-3 py-2 text-foreground-muted">{rowRoute(row) || '—'}</td>
            <td class="max-w-xs px-3 py-2">
              {#if row.errors.length > 0}
                <ul class="space-y-1 text-danger">
                  {#each row.errors as rowError}<li>{rowError}</li>{/each}
                </ul>
              {:else if changes.length > 0}
                <ul class="space-y-1 text-foreground-muted">
                  {#each changes as change}<li class="font-mono">{change}</li>{/each}
                </ul>
              {:else}
                <span class="text-foreground-subtle">Validada</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div
    class="flex flex-col gap-2 border-t border-border bg-surface-muted/40 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
  >
    <p class="text-center text-xs text-foreground-muted sm:text-left">
      {#if visibleRows.length > 0}
        Filas {firstVisibleRow.toLocaleString('es-SV')}–{lastVisibleRow.toLocaleString('es-SV')} de
        {pageMeta.total.toLocaleString('es-SV')} · Página {pageMeta.page} de {pageMeta.pages}
      {:else}
        No hay filas para revisar.
      {/if}
    </p>
    {#if pageMeta.pages > 1}
      <div class="flex justify-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || pageMeta.page <= 1}
          onclick={() => void goToPage(pageMeta.page - 1)}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || pageMeta.page >= pageMeta.pages}
          onclick={() => void goToPage(pageMeta.page + 1)}
          >{loading ? 'Cargando…' : 'Siguiente'}</Button
        >
      </div>
    {/if}
  </div>
</div>

{#if loadError}
  <div
    class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
    role="alert"
  >
    {loadError}
  </div>
{/if}
