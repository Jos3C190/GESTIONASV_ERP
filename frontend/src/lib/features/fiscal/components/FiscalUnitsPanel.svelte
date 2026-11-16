<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { productFiscalApi } from '$lib/api/product-fiscal';
  import type { CatalogEntry, UnitFiscal } from '$lib/types/product-fiscal';

  let { canManage }: { canManage: boolean } = $props();

  let units = $state<UnitFiscal[]>([]);
  let catalog = $state<CatalogEntry[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let rowError = $state<{ id: number; message: string } | null>(null);
  let savingId = $state<number | null>(null);

  async function load() {
    loading = true;
    loadError = null;
    try {
      const [items, options] = await Promise.all([
        productFiscalApi.listUnits(),
        productFiscalApi.options()
      ]);
      units = items;
      catalog = options.units;
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las unidades.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  async function change(unit: UnitFiscal, control: HTMLSelectElement) {
    savingId = unit.unit_id;
    rowError = null;
    const value = control.value === '' ? null : control.value;
    try {
      const saved = await productFiscalApi.updateUnit(unit.unit_id, value);
      units = units.map((u) => (u.unit_id === saved.unit_id ? saved : u));
    } catch (cause) {
      control.value = unit.hacienda_unit_code ?? '';
      rowError = {
        id: unit.unit_id,
        message: cause instanceof HttpError ? cause.message : 'No se pudo guardar el cambio.'
      };
    } finally {
      savingId = null;
    }
  }

  function suggestionLabel(unit: UnitFiscal): string {
    const name = catalog.find((c) => c.code === unit.suggested_code)?.name ?? '';
    return `Sugerido: ${unit.suggested_code} · ${name}`;
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div class="border-b border-border p-4">
    <h2 class="font-semibold text-foreground">Unidades de medida ante Hacienda</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Cada línea de un documento lleva la unidad de medida del catálogo de Hacienda. Si no eliges
      una, se usa la sugerida. Las presentaciones sin equivalente (caja, paquete) van como «Otra».
    </p>
  </div>

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando unidades…</p>
      {#each [1, 2, 3] as row (row)}
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
  {:else if units.length === 0}
    <p class="p-4 text-sm text-foreground-muted">La empresa no tiene unidades habilitadas.</p>
  {:else}
    <ul class="divide-y divide-border">
      {#each units as unit (unit.unit_id)}
        <li class="grid gap-2 p-4 sm:grid-cols-[1fr_minmax(14rem,auto)] sm:items-center">
          <div class="min-w-0">
            <p class="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
              {unit.name}
              <span class="font-mono text-xs text-foreground-muted">{unit.symbol}</span>
              {#if !unit.is_enabled}<Badge variant="neutral">Deshabilitada</Badge>{/if}
            </p>
            <p class="text-xs text-foreground-muted">
              {unit.hacienda_unit_code ? 'Elegida por la empresa' : suggestionLabel(unit)}
            </p>
            {#if rowError?.id === unit.unit_id}
              <p class="mt-1 text-sm text-danger" role="alert">{rowError.message}</p>
            {/if}
          </div>
          <label class="sr-only" for="unit-code-{unit.unit_id}"
            >Unidad de Hacienda de {unit.name}</label
          >
          <select
            id="unit-code-{unit.unit_id}"
            value={unit.hacienda_unit_code ?? ''}
            disabled={!canManage || savingId === unit.unit_id}
            onchange={(e) => void change(unit, e.currentTarget)}
            class="h-11 rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60"
          >
            <option value="">Usar la sugerida ({unit.suggested_code})</option>
            {#each catalog as entry (entry.code)}
              <option value={entry.code}>{entry.code} · {entry.name}</option>
            {/each}
          </select>
        </li>
      {/each}
    </ul>
  {/if}
</section>
