<script lang="ts">
  import type { GeneralImportOut } from '$lib/api/client';

  interface InvalidFile {
    relativePath: string;
    reason: string;
  }

  interface Props {
    result: GeneralImportOut | null;
    invalidFiles: InvalidFile[];
  }

  let { result, invalidFiles }: Props = $props();
</script>

{#if result?.status === 'partial' || invalidFiles.length}
  <section class="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning" aria-live="polite">
    <h3 class="font-semibold">Importación parcial</h3>
    <p class="mt-1">Los elementos válidos quedaron disponibles. Revisa los omitidos o reintenta los archivos con error.</p>
    {#if invalidFiles.length}
      <details class="mt-3">
        <summary class="cursor-pointer text-xs font-semibold">{invalidFiles.length} omitidos antes de iniciar</summary>
        <div class="mt-2 space-y-1 text-xs">
          {#each invalidFiles.slice(0, 50) as item}<div>{item.relativePath} · {item.reason}</div>{/each}
        </div>
      </details>
    {/if}
  </section>
{:else if result?.status === 'completed'}
  <section class="rounded-2xl border border-success/30 bg-success/10 p-4 text-sm text-success" role="status">
    <h3 class="font-semibold">Importación completada</h3>
    <p class="mt-1">Todos los archivos compatibles fueron verificados y activados.</p>
  </section>
{:else if result?.status === 'cancelled'}
  <section class="rounded-2xl border border-border bg-surface-muted/40 p-4 text-sm text-foreground-muted" role="status">
    <h3 class="font-semibold text-foreground">Importación cancelada</h3>
    <p class="mt-1">Se conservaron las carpetas y archivos que ya habían terminado.</p>
  </section>
{/if}
