<script lang="ts">
  import { onDestroy } from 'svelte';
  import Button from './Button.svelte';
  import { apiDownload } from '$lib/api/client';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';

  let {
    path,
    code,
    formats = ['pdf', 'xlsx']
  }: {
    path: string;
    code: string;
    formats?: ('pdf' | 'xlsx')[];
  } = $props();
  let busy = $state<string | null>(null);
  let error = $state('');
  let notice = $state('');
  let active = true;
  onDestroy(() => {
    active = false;
  });

  async function download(format: 'pdf' | 'xlsx') {
    if (busy) return;
    busy = format;
    error = '';
    notice = '';
    const requestedPath = path;
    const requestedCode = code;
    const companyId = company.id;
    const branchId = branch.id;
    try {
      const blob = await apiDownload(
        `${requestedPath}${requestedPath.includes('?') ? '&' : '?'}format=${format}`
      );
      if (!active) return;
      if (path !== requestedPath || company.id !== companyId || branch.id !== branchId) {
        error = 'Cambió el documento, la empresa o la sucursal. Vuelve a solicitar el reporte.';
        return;
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${requestedCode.replace(/[^\w-]/g, '_')}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      notice = `${format === 'pdf' ? 'PDF' : 'Excel'} preparado. Revisa las descargas de tu navegador.`;
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      if (active)
        error = cause instanceof Error ? cause.message : 'No se pudo descargar el reporte.';
    } finally {
      if (active) busy = null;
    }
  }
</script>

<div class="space-y-2">
  <div
    class="flex flex-wrap gap-2"
    role="group"
    aria-label={`Reportes de ${code}`}
    aria-busy={busy !== null}
  >
    {#each formats as format}
      <span class="inline-flex" style="min-width: 10rem">
        <Button
          variant="secondary"
          size="lg"
          class="w-full"
          disabled={busy !== null}
          onclick={() => void download(format)}
        >
          {busy === format ? 'Preparando…' : format === 'pdf' ? 'Descargar PDF' : 'Descargar Excel'}
        </Button>
      </span>
    {/each}
  </div>
  <p class="text-xs text-foreground-muted">Exporta los datos guardados del documento.</p>
  <p role="status" class="text-xs text-foreground-muted">{busy ? 'Preparando reporte…' : notice}</p>
  {#if error}<p
      role="alert"
      class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
    >
      {error} Puedes volver a intentar la descarga.
    </p>{/if}
</div>
