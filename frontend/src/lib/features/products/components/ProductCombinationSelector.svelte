<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { ProductVariantConfig, ProductVariantDraft } from '$lib/types/catalog';
  import {
    normalizeVariantToken,
    variantCombinationKey
  } from '$lib/features/products/variant-config';

  interface Props {
    candidates: ProductVariantDraft[];
    selectedKeys: string[];
    existingKeys?: string[];
    attributes?: ProductVariantConfig['attributes'];
    editable?: boolean;
    selectionMode?: 'all' | 'selected';
    onChange?: (keys: string[]) => void;
  }

  let {
    candidates,
    selectedKeys,
    existingKeys = [],
    attributes = [],
    editable = true,
    selectionMode = 'selected',
    onChange
  }: Props = $props();

  let query = $state('');
  let onlySelected = $state(false);
  let typeFilter = $state<'all' | 'existing' | 'new' | 'retired'>('all');
  let statusFilter = $state<'all' | 'active' | 'draft' | 'blocked' | 'retired' | 'discontinued'>(
    'all'
  );
  let attributeFilters = $state<Record<string, string>>({});

  let selectedSet = $derived(new Set(selectedKeys));
  let existingSet = $derived(new Set(existingKeys));
  let attributeFilterOptions = $derived(
    attributes.map((attribute) => ({
      ...attribute,
      values: attribute.values.filter((value) => value.code.trim())
    }))
  );
  let hasActiveFilters = $derived(
    Boolean(query.trim()) ||
      onlySelected ||
      typeFilter !== 'all' ||
      statusFilter !== 'all' ||
      Object.values(attributeFilters).some(Boolean)
  );
  let visibleCandidates = $derived(
    candidates.filter((variant) => {
      const key = variantCombinationKey(variant);
      const isExisting = existingSet.has(key);
      const isRetired = variant.lifecycle_status === 'retired';
      const typeMatches =
        typeFilter === 'all' ||
        (typeFilter === 'existing' && isExisting) ||
        (typeFilter === 'new' && !isExisting) ||
        (typeFilter === 'retired' && isRetired);
      if (!typeMatches) return false;
      if (statusFilter !== 'all' && variant.lifecycle_status !== statusFilter) return false;
      if (onlySelected && !selectedSet.has(key)) return false;
      for (const attribute of attributeFilterOptions) {
        const selectedValue = attributeFilters[attribute.code];
        if (!selectedValue) continue;
        const matches = variant.values.some(
          (value) =>
            normalizeVariantToken(value.attribute_code) === normalizeVariantToken(attribute.code) &&
            normalizeVariantToken(value.value_code) === normalizeVariantToken(selectedValue)
        );
        if (!matches) return false;
      }
      if (!query.trim()) return true;
      const haystack = `${key} ${variant.sku} ${variant.name_override ?? ''}`.toLocaleLowerCase();
      return haystack.includes(query.trim().toLocaleLowerCase());
    })
  );

  function clearFilters() {
    query = '';
    onlySelected = false;
    typeFilter = 'all';
    statusFilter = 'all';
    attributeFilters = {};
  }

  function statusLabel(status: ProductVariantDraft['lifecycle_status']) {
    return {
      active: 'Activa',
      draft: 'Borrador',
      blocked: 'Bloqueada',
      discontinued: 'Descontinuada',
      retired: 'Retirada'
    }[status];
  }

  function typeLabel(variant: ProductVariantDraft) {
    if (variant.lifecycle_status === 'retired') return 'Retirada';
    return 'Existente';
  }

  function displayCombination(variant: ProductVariantDraft) {
    return variant.values
      .map((value) => `${value.attribute_code}: ${value.value_code}`)
      .join(' · ');
  }

  function updateSelection(next: Set<string>) {
    onChange?.([...next]);
  }

  function toggle(variant: ProductVariantDraft) {
    if (!editable) return;
    const next = new Set(selectedKeys);
    const key = variantCombinationKey(variant);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    updateSelection(next);
  }

  function selectVisible(select: boolean) {
    if (!editable) return;
    const next = new Set(selectedKeys);
    for (const variant of visibleCandidates) {
      const key = variantCombinationKey(variant);
      if (select) next.add(key);
      else next.delete(key);
    }
    updateSelection(next);
  }
</script>

<section
  class="rounded-xl border border-border bg-surface p-5"
  aria-labelledby="combination-selection-title"
>
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 id="combination-selection-title" class="text-base font-semibold text-foreground">
        {selectionMode === 'all'
          ? 'Resumen de la matriz completa'
          : 'Seleccione las combinaciones válidas'}
      </h2>
      <p class="mt-1 text-sm text-foreground-muted">
        {#if selectionMode === 'all'}
          Todas las combinaciones validadas se incluirán en esta familia.
        {:else}
          No es obligatorio crear todas las combinaciones posibles. Desmarque las que su negocio no
          comercializa.
        {/if}
      </p>
    </div>
    <div class="text-right">
      <p class="font-mono text-lg font-semibold text-foreground">
        {selectedKeys.length} / {candidates.length}
      </p>
      <p class="text-xs text-foreground-muted">
        {selectionMode === 'all' ? 'incluidas' : 'seleccionadas'}
      </p>
    </div>
  </div>

  {#if selectionMode === 'selected'}
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <label class="min-w-[220px] flex-1">
        <span class="sr-only">Buscar combinación</span>
        <input
          class="w-full rounded-md border border-border bg-surface-muted/20 px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle"
          placeholder="Buscar por combinación o SKU…"
          bind:value={query}
          aria-label="Buscar combinación"
        />
      </label>
      <Button
        size="sm"
        variant="secondary"
        onclick={() => selectVisible(true)}
        disabled={!editable || !visibleCandidates.length}
      >
        Seleccionar visibles
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onclick={() => selectVisible(false)}
        disabled={!editable || !visibleCandidates.length}
      >
        Quitar visibles
      </Button>
      <label class="flex items-center gap-2 px-1 text-xs text-foreground-muted">
        <input type="checkbox" bind:checked={onlySelected} />
        Solo seleccionadas
      </label>
    </div>

    <div class="mt-3 grid gap-2 md:grid-cols-3">
      <label class="text-xs font-medium text-foreground-muted">
        Tipo
        <select
          class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
          value={typeFilter}
          aria-label="Filtrar por tipo"
          onchange={(event) => {
            typeFilter = (event.currentTarget as HTMLSelectElement).value as typeof typeFilter;
          }}
        >
          <option value="all">Todos los tipos</option>
          <option value="existing">Existentes</option>
          <option value="new">Nuevas</option>
          <option value="retired">Retiradas</option>
        </select>
      </label>
      <label class="text-xs font-medium text-foreground-muted">
        Estado
        <select
          class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
          value={statusFilter}
          aria-label="Filtrar por estado"
          onchange={(event) => {
            statusFilter = (event.currentTarget as HTMLSelectElement).value as typeof statusFilter;
          }}
        >
          <option value="all">Todos los estados</option>
          <option value="active">Activa</option>
          <option value="draft">Borrador</option>
          <option value="blocked">Bloqueada</option>
          <option value="retired">Retirada</option>
          <option value="discontinued">Descontinuada</option>
        </select>
      </label>
      {#if hasActiveFilters}
        <div class="flex items-end justify-start md:justify-end">
          <Button size="sm" variant="ghost" onclick={clearFilters}>Limpiar filtros</Button>
        </div>
      {/if}
    </div>

    {#if attributeFilterOptions.length}
      <div class="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
        {#each attributeFilterOptions as attribute (attribute._key ?? attribute.code)}
          <label class="text-xs font-medium text-foreground-muted">
            {attribute.name}
            <select
              class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
              value={attributeFilters[attribute.code] ?? ''}
              aria-label={`Filtrar por ${attribute.name}`}
              onchange={(event) => {
                const value = (event.currentTarget as HTMLSelectElement).value;
                const next = { ...attributeFilters };
                if (value) next[attribute.code] = value;
                else delete next[attribute.code];
                attributeFilters = next;
              }}
            >
              <option value="">Todos los valores</option>
              {#each attribute.values as value (value._key ?? value.code)}
                <option value={value.code}>{value.label} ({value.code})</option>
              {/each}
            </select>
          </label>
        {/each}
      </div>
    {/if}

    <div
      class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-foreground-muted"
    >
      <span>{visibleCandidates.length} de {candidates.length} combinaciones visibles</span>
      {#if hasActiveFilters}<span>Las acciones en bloque aplican solo a las filas visibles.</span
        >{/if}
    </div>
  {/if}

  <div class="mt-4 overflow-x-auto rounded-lg border border-border">
    <table class="min-w-full text-sm">
      <thead
        class="border-b border-border bg-surface-muted/30 text-left text-xs text-foreground-muted"
      >
        <tr>
          <th class="w-12 px-3 py-2">
            <span class="sr-only">{selectionMode === 'all' ? 'Estado' : 'Incluir'}</span>
          </th>
          <th class="px-3 py-2">Combinación</th>
          <th class="px-3 py-2">SKU sugerido</th>
          <th class="px-3 py-2">Estado</th>
        </tr>
      </thead>
      <tbody>
        {#each visibleCandidates as variant, index (`${variant.id ?? variantCombinationKey(variant)}:${variant.lifecycle_status}:${variant.sku}:${index}`)}
          {@const key = variantCombinationKey(variant)}
          <tr class="border-b border-border last:border-0">
            <td class="px-3 py-2 align-middle">
              {#if selectionMode === 'all'}
                <span
                  class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success"
                  aria-label={`Incluida ${displayCombination(variant)}`}
                >
                  <span aria-hidden="true">✓</span> Incluida
                </span>
              {:else}
                <input
                  type="checkbox"
                  checked={selectedSet.has(key)}
                  disabled={!editable}
                  onchange={() => toggle(variant)}
                  aria-label={`Incluir ${displayCombination(variant)}`}
                />
              {/if}
            </td>
            <td class="px-3 py-2 text-xs text-foreground">
              {displayCombination(variant)}
              <span
                class={`ml-2 rounded-full px-2 py-0.5 text-[10px] ${existingSet.has(key) ? 'bg-primary/10 text-primary' : 'bg-surface-muted text-foreground-muted'}`}
                >{existingSet.has(key) ? typeLabel(variant) : 'Nueva'}</span
              >
            </td>
            <td class="px-3 py-2 font-mono text-xs text-foreground-muted">{variant.sku}</td>
            <td class="px-3 py-2 text-xs text-foreground-muted">
              {statusLabel(variant.lifecycle_status)}
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="4" class="px-3 py-8 text-center text-sm text-foreground-muted">
              No hay combinaciones que coincidan con el filtro.
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <p class="mt-3 text-xs text-foreground-muted">
    Los filtros solo cambian las filas visibles; no modifican la selección hasta que use una acción
    en bloque.
    <br />
    Las combinaciones no seleccionadas que ya existan se conservarán en el historial y pasarán a estado
    retirada solo después de confirmar el guardado.
  </p>
</section>
