<script lang="ts">
  import { formatImportBytes } from './folder-import';

  interface Props {
    rootName: string;
    totalBytes: number;
    validCount: number;
    folderCount: number;
    skippedCount: number;
    itemCount: number;
  }

  let { rootName, totalBytes, validCount, folderCount, skippedCount, itemCount }: Props = $props();
</script>

<section class="rounded-2xl border border-border bg-surface-muted/40 p-4" aria-live="polite">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">Resumen</p>
      <h3 class="mt-1 text-base font-semibold text-foreground">{rootName || 'Carpeta seleccionada'}</h3>
    </div>
    <span class="text-xs text-foreground-muted">{formatImportBytes(totalBytes)}</span>
  </div>
  <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-foreground-muted sm:grid-cols-4">
    <span><strong class="text-foreground">{validCount}</strong> archivos válidos</span>
    <span><strong class="text-foreground">{folderCount}</strong> carpetas</span>
    <span><strong class="text-foreground">{skippedCount}</strong> omitidos</span>
    <span><strong class="text-foreground">{itemCount}</strong> elementos</span>
  </div>
</section>
