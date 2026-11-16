<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { fiscalApi } from '$lib/api/fiscal';
  import {
    CERTIFICATION_LABELS,
    EVENT_DOCUMENT_TYPES,
    formatFiscalDate
  } from '$lib/features/fiscal/labels';
  import type { CertificationStatus, DocumentTypeSetting, OperatingMode } from '$lib/types/fiscal';

  let { canManage }: { canManage: boolean } = $props();

  const STATUSES: CertificationStatus[] = ['pending', 'in_progress', 'approved'];

  let documents = $state<DocumentTypeSetting[]>([]);
  let mode = $state<OperatingMode>('simulated');
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let rowError = $state<{ code: string; message: string } | null>(null);
  let savingCode = $state<string | null>(null);

  const enabledCount = $derived(documents.filter((d) => d.is_enabled).length);

  async function load() {
    loading = true;
    loadError = null;
    try {
      const [items, profile] = await Promise.all([
        fiscalApi.listDocumentTypes(),
        fiscalApi.getProfile()
      ]);
      documents = items;
      mode = profile.operating_mode;
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar los documentos.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  /** Guarda un cambio; si el servidor lo rechaza, el control vuelve al valor guardado. */
  async function save(
    item: DocumentTypeSetting,
    changes: Partial<DocumentTypeSetting>,
    control: HTMLInputElement | HTMLSelectElement
  ) {
    savingCode = item.document_type;
    rowError = null;
    const next = { ...item, ...changes };
    try {
      const saved = await fiscalApi.updateDocumentType(item.document_type, {
        is_enabled: next.is_enabled,
        certification_status: next.certification_status,
        notes: next.notes
      });
      documents = documents.map((d) => (d.document_type === saved.document_type ? saved : d));
    } catch (cause) {
      if (control instanceof HTMLInputElement) control.checked = item.is_enabled;
      else control.value = item.certification_status;
      rowError = {
        code: item.document_type,
        message: cause instanceof HttpError ? cause.message : 'No se pudo guardar el cambio.'
      };
    } finally {
      savingCode = null;
    }
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div class="border-b border-border p-4">
    <h2 class="font-semibold text-foreground">Documentos que emite la empresa</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Las pantallas de venta solo ofrecen los documentos habilitados.
      {#if mode === 'production'}
        En producción solo se habilita un documento cuyas pruebas aprobó Hacienda.
      {:else}
        Mientras la empresa no esté en producción puedes habilitar cualquiera para probarlo.
      {/if}
    </p>
    {#if !loading && !loadError}
      <p class="mt-2 text-xs text-foreground-muted">
        {enabledCount === 1 ? '1 habilitado' : `${enabledCount} habilitados`} de {documents.length}
      </p>
    {/if}
  </div>

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando documentos…</p>
      {#each [1, 2, 3, 4] as row (row)}
        <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
      {/each}
    </div>
  {:else if loadError}
    <div
      class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else}
    <ul class="divide-y divide-border">
      {#each documents as item (item.document_type)}
        {@const busy = savingCode === item.document_type}
        <li class="grid gap-3 p-4 md:grid-cols-[1fr_auto_auto] md:items-center">
          <div class="min-w-0">
            <p class="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
              <span class="font-mono text-foreground-muted">{item.document_type}</span>
              {item.name}
              {#if EVENT_DOCUMENT_TYPES.has(item.document_type)}
                <Badge variant="neutral">Evento</Badge>
              {/if}
            </p>
            {#if item.certified_at}
              <p class="mt-1 text-xs text-success">
                Pruebas aprobadas el {formatFiscalDate(item.certified_at)}
              </p>
            {/if}
            {#if rowError?.code === item.document_type}
              <p class="mt-2 text-sm text-danger" role="alert">{rowError.message}</p>
            {/if}
          </div>
          <label class="flex flex-col gap-1 text-xs text-foreground-muted">
            Pruebas ante Hacienda
            <select
              value={item.certification_status}
              disabled={!canManage || busy}
              onchange={(e) =>
                void save(
                  item,
                  { certification_status: e.currentTarget.value as CertificationStatus },
                  e.currentTarget
                )}
              class="h-11 rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60"
            >
              {#each STATUSES as status (status)}
                <option value={status}>{CERTIFICATION_LABELS[status]}</option>
              {/each}
            </select>
          </label>
          <label class="flex min-h-11 items-center gap-2 text-sm text-foreground md:justify-end">
            <input
              type="checkbox"
              checked={item.is_enabled}
              disabled={!canManage || busy}
              onchange={(e) =>
                void save(item, { is_enabled: e.currentTarget.checked }, e.currentTarget)}
            />
            {busy ? 'Guardando…' : 'Habilitado'}
          </label>
        </li>
      {/each}
    </ul>
  {/if}
</section>
