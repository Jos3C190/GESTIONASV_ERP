<script lang="ts">
  import type { GeneralImportManifestItemInput } from '$lib/api/client';

  interface InvalidFile {
    relativePath: string;
    reason: string;
  }

  interface Props {
    manifest: GeneralImportManifestItemInput[];
    invalidFiles: InvalidFile[];
  }

  let { manifest, invalidFiles }: Props = $props();
</script>

<div class="max-h-52 overflow-y-auto rounded-2xl border border-border p-3" aria-label="Contenido de la carpeta">
  <div class="space-y-1 text-xs text-foreground-muted">
    {#each manifest.slice(0, 120) as item}
      <div class="flex items-center gap-2 truncate">
        <span aria-hidden="true">{item.kind === 'folder' ? '📁' : '📄'}</span>
        <span class="truncate">{item.relative_path}</span>
      </div>
    {/each}
  </div>
  {#if manifest.length > 120}
    <p class="mt-2 text-xs text-foreground-subtle">Se muestran los primeros 120 elementos.</p>
  {/if}
</div>

{#if invalidFiles.length}
  <details class="rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
    <summary class="cursor-pointer font-semibold">{invalidFiles.length} archivos se omitirán</summary>
    <div class="mt-2 space-y-1">
      {#each invalidFiles.slice(0, 50) as item}
        <div>{item.relativePath} · {item.reason}</div>
      {/each}
    </div>
    {#if invalidFiles.length > 50}<p class="mt-2">Se muestran los primeros 50 omitidos.</p>{/if}
  </details>
{/if}
