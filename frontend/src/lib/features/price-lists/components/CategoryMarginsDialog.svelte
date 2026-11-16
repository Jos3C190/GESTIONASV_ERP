<script lang="ts">
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { priceListsApi } from '#lib/api/price-lists.ts';
  import type { Category, PriceList, PriceListInput } from '#lib/types/price-list.ts';

  let {
    priceList,
    open,
    onclose,
    onsaved
  }: {
    priceList: PriceList;
    open: boolean;
    onclose: () => void;
    onsaved: (updated: PriceList) => void;
  } = $props();

  const inputClass =
    'h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let categories = $state<Category[]>([]);
  let values = $state<Record<number, string>>({});
  let listMargin = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    if (open) void load();
  });

  async function load() {
    loading = true;
    error = null;
    listMargin = priceList.target_margin_percent
      ? String(Number(priceList.target_margin_percent))
      : '';
    try {
      const [all, margins] = await Promise.all([
        priceListsApi.categories(),
        priceListsApi.categoryMargins(priceList.id)
      ]);
      categories = all;
      values = Object.fromEntries(
        margins.map((m) => [m.category_id, String(Number(m.target_margin_percent))])
      );
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los márgenes.';
    } finally {
      loading = false;
    }
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = null;
    try {
      const payload: PriceListInput = {
        code: priceList.code,
        name: priceList.name,
        description: priceList.description,
        prices_include_vat: priceList.prices_include_vat,
        is_default: priceList.is_default,
        is_active: priceList.is_active,
        target_margin_percent: listMargin === '' ? null : String(listMargin)
      };
      const updated = await priceListsApi.update(priceList.id, payload);
      await priceListsApi.replaceCategoryMargins(
        priceList.id,
        Object.entries(values)
          .filter(([, value]) => value !== '' && value !== null)
          .map(([category, value]) => ({
            category_id: Number(category),
            target_margin_percent: String(value)
          }))
      );
      onsaved(updated);
      onclose();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron guardar los márgenes.';
    } finally {
      saving = false;
    }
  }
</script>

<Modal {open} title="Margen objetivo" {onclose}>
  <form class="space-y-4" onsubmit={save}>
    <p class="text-sm text-foreground-muted">
      Margen sobre el precio sin IVA que se busca en esta lista. Con él se calcula el precio
      sugerido y se resaltan los precios que quedan por debajo. Una categoría puede tener el suyo.
    </p>
    {#if error}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </p>
    {/if}
    <div>
      <label for="list-margin" class="mb-1 block text-sm font-medium text-foreground"
        >Margen de la lista (%)</label
      >
      <input
        id="list-margin"
        type="number"
        min="0"
        max="95"
        step="any"
        value={listMargin}
        oninput={(e) => (listMargin = e.currentTarget.value)}
        placeholder="Sin margen objetivo"
        class={inputClass}
      />
    </div>
    <fieldset>
      <legend class="mb-2 text-sm font-medium text-foreground">Por categoría (opcional)</legend>
      {#if loading}
        <div class="skeleton h-24 rounded-lg motion-reduce:animate-none" aria-busy="true"></div>
      {:else if categories.length === 0}
        <p class="text-sm text-foreground-muted">La empresa no tiene categorías de productos.</p>
      {:else}
        <ul class="max-h-72 divide-y divide-border overflow-y-auto rounded-lg border border-border">
          {#each categories as category (category.id)}
            <li class="flex items-center justify-between gap-3 px-3 py-2">
              <label for={`category-${category.id}`} class="text-sm text-foreground"
                >{category.name}</label
              >
              <input
                id={`category-${category.id}`}
                type="number"
                min="0"
                max="95"
                step="any"
                value={values[category.id] ?? ''}
                oninput={(e) => (values = { ...values, [category.id]: e.currentTarget.value })}
                placeholder="La de la lista"
                class="h-9 w-32 rounded-lg border border-border bg-surface px-2 text-sm text-foreground"
              />
            </li>
          {/each}
        </ul>
      {/if}
    </fieldset>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={onclose}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
