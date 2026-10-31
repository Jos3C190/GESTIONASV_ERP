<script lang="ts">
  import type { GeneralImportOut } from '$lib/api/client';

  type LocalState = { status: string; progress: number; message?: string };

  interface Props {
    phase: 'running' | 'report';
    result: GeneralImportOut | null;
    localStates: Record<string, LocalState>;
    progress: number;
    completedCount: number;
    errorCount: number;
  }

  let { phase, result, localStates, progress, completedCount, errorCount }: Props = $props();
</script>

<section class="rounded-2xl border border-border bg-surface-muted/40 p-4">
  <div class="flex items-center justify-between gap-3">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">{phase === 'report' ? 'Resultado' : 'Importando'}</p>
      <p class="mt-1 text-sm text-foreground">{result?.total_files ?? 0} archivos · {result?.total_folders ?? 0} carpetas</p>
    </div>
    <strong class="text-lg text-foreground">{progress}%</strong>
  </div>
  <div class="mt-3 h-2 overflow-hidden rounded-full bg-surface" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress} aria-label="Progreso de importación">
    <div class="h-full rounded-full bg-primary transition-[width] duration-300" style={`width: ${progress}%`}></div>
  </div>
  <div class="mt-3 grid grid-cols-3 gap-2 text-xs text-foreground-muted">
    <span><strong class="text-foreground">{result?.completed_files ?? completedCount}</strong> listos</span>
    <span><strong class="text-foreground">{result?.skipped_files ?? 0}</strong> omitidos</span>
    <span><strong class="text-danger">{result?.failed_files ?? errorCount}</strong> con error</span>
  </div>
</section>

<div class="max-h-64 space-y-1 overflow-y-auto rounded-2xl border border-border p-3" aria-live="polite" aria-label="Progreso por archivo">
  {#each result?.items.filter((item) => item.kind === 'file') ?? [] as item (item.id)}
    {@const state = localStates[item.id]}
    <div class="flex items-center gap-3 rounded-lg px-2 py-2 text-xs hover:bg-surface-hover">
      <span class="w-5 text-center" aria-hidden="true">{state?.status === 'done' || item.status === 'completed' ? '✓' : state?.status === 'error' ? '!' : '·'}</span>
      <span class="min-w-0 flex-1 truncate text-foreground">{item.resolved_path}</span>
      <span class="shrink-0 text-foreground-muted">{state?.status === 'uploading' ? `${state.progress}%` : state?.status === 'error' ? 'Error' : item.status === 'skipped' ? 'Omitido' : item.status === 'completed' ? 'Listo' : 'Pendiente'}</span>
    </div>
  {/each}
</div>
