<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import {
    ITEM_TYPE_LABELS,
    TAX_TREATMENT_LABELS,
    productFiscalApi
  } from '$lib/api/product-fiscal';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type {
    CatalogEntry,
    DteItemType,
    ProductFiscal,
    TaxTreatment
  } from '$lib/types/product-fiscal';

  let { productId }: { productId: number } = $props();

  const TREATMENTS: TaxTreatment[] = ['taxed', 'exempt', 'not_subject'];
  const TREATMENT_HINTS: Record<TaxTreatment, string> = {
    taxed: 'La venta lleva IVA. Es lo habitual.',
    exempt: 'La ley lo libera del IVA; la venta se registra como exenta.',
    not_subject: 'La operación está fuera del alcance del IVA.'
  };

  let fiscal = $state<ProductFiscal | null>(null);
  let taxes = $state<CatalogEntry[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let open = $state(false);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let treatment = $state<TaxTreatment>('taxed');
  let itemType = $state<DteItemType | ''>('');
  let selected = $state<string[]>([]);
  let taxFilter = $state('');

  const canEdit = $derived(permissions.hasPermission('products:fiscal'));
  const visibleTaxes = $derived(
    taxes.filter((t) =>
      `${t.code} ${t.name}`
        .toLocaleLowerCase('es-SV')
        .includes(taxFilter.trim().toLocaleLowerCase('es-SV'))
    )
  );

  async function load() {
    loading = true;
    loadError = null;
    try {
      fiscal = await productFiscalApi.get(productId);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar la clasificación fiscal.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  async function openEditor() {
    if (!fiscal) return;
    treatment = fiscal.tax_treatment;
    itemType = fiscal.dte_item_type ?? '';
    selected = fiscal.additional_taxes.map((t) => t.code);
    taxFilter = '';
    formError = null;
    open = true;
    if (taxes.length === 0) {
      try {
        taxes = (await productFiscalApi.options()).taxes;
      } catch {
        formError = 'No se pudo cargar el catálogo de tributos.';
      }
    }
  }

  function toggleTax(code: string) {
    selected = selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code];
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      fiscal = await productFiscalApi.update(productId, {
        tax_treatment: treatment,
        dte_item_type: itemType || null,
        additional_tax_codes: treatment === 'taxed' ? selected : []
      });
      open = false;
    } catch (cause) {
      formError =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar la clasificación.';
    } finally {
      saving = false;
    }
  }
</script>

<Card class="p-6">
  <div class="mb-4 flex items-start justify-between gap-3">
    <div>
      <h3 class="text-sm font-semibold text-foreground">Clasificación fiscal</h3>
      <p class="mt-1 text-xs text-foreground-muted">
        Cómo se declara este producto en cada documento tributario electrónico.
      </p>
    </div>
    {#if canEdit && fiscal}
      <Button variant="secondary" size="sm" onclick={() => void openEditor()}>Editar</Button>
    {/if}
  </div>

  {#if loading}
    <div class="skeleton h-24 rounded-lg motion-reduce:animate-none" aria-busy="true">
      <span class="sr-only" role="status">Cargando la clasificación fiscal…</span>
    </div>
  {:else if loadError || !fiscal}
    <div
      class="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError ?? 'No se pudo cargar la clasificación fiscal.'}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else}
    <dl class="grid gap-3 text-sm sm:grid-cols-2">
      <div>
        <dt class="text-xs text-foreground-muted">Tratamiento de IVA</dt>
        <dd class="mt-1">
          <Badge variant={fiscal.tax_treatment === 'taxed' ? 'neutral' : 'warning'}>
            {TAX_TREATMENT_LABELS[fiscal.tax_treatment]}
          </Badge>
        </dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Tipo de ítem en el DTE</dt>
        <dd class="mt-1 text-foreground">
          {ITEM_TYPE_LABELS[fiscal.effective_item_type]}
          {#if !fiscal.dte_item_type}<span class="text-xs text-foreground-muted"
              >(según el tipo de producto)</span
            >{/if}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Unidad de venta ante Hacienda</dt>
        <dd class="mt-1 text-foreground">
          {#if fiscal.sale_unit}
            {fiscal.sale_unit.name} →
            <span class="font-mono">{fiscal.sale_unit.effective_code}</span>
            {fiscal.sale_unit.hacienda_unit_name ?? ''}
          {:else}
            —
          {/if}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Tributos adicionales</dt>
        <dd class="mt-1 text-foreground">
          {#if fiscal.additional_taxes.length === 0}
            Ninguno
          {:else}
            <ul class="space-y-0.5">
              {#each fiscal.additional_taxes as tax (tax.code)}
                <li><span class="font-mono">{tax.code}</span> · {tax.name}</li>
              {/each}
            </ul>
          {/if}
        </dd>
      </div>
    </dl>
    {#if fiscal.billing_issues.length > 0}
      <div class="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
        <p class="font-medium text-foreground">Para facturar este producto falta:</p>
        <ul class="mt-1 list-disc pl-5 text-foreground-muted">
          {#each fiscal.billing_issues as issue (issue)}
            <li>{issue}</li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}
</Card>

<Modal {open} title="Clasificación fiscal" onclose={() => (open = false)} size="lg">
  <form class="space-y-5" onsubmit={save}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <fieldset>
      <legend class="mb-2 text-sm font-medium text-foreground">Tratamiento de IVA</legend>
      <div class="grid gap-2 sm:grid-cols-3">
        {#each TREATMENTS as option (option)}
          <label
            class="flex cursor-pointer gap-2 rounded-lg border p-3 text-sm {treatment === option
              ? 'border-primary bg-primary/5'
              : 'border-border hover:bg-surface-muted/50'}"
          >
            <input
              type="radio"
              name="tax-treatment"
              value={option}
              bind:group={treatment}
              aria-label={TAX_TREATMENT_LABELS[option]}
              class="mt-0.5"
            />
            <span>
              <span class="block font-medium text-foreground">{TAX_TREATMENT_LABELS[option]}</span>
              <span class="block text-xs text-foreground-muted">{TREATMENT_HINTS[option]}</span>
            </span>
          </label>
        {/each}
      </div>
    </fieldset>

    <div>
      <label for="fiscal-item-type" class="mb-1 block text-sm font-medium text-foreground">
        Tipo de ítem en el DTE
      </label>
      <select
        id="fiscal-item-type"
        bind:value={itemType}
        class="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      >
        <option value="">Según el tipo de producto</option>
        {#each Object.entries(ITEM_TYPE_LABELS) as [value, label] (value)}
          <option {value}>{label}</option>
        {/each}
      </select>
    </div>

    <fieldset disabled={treatment !== 'taxed'}>
      <legend class="mb-1 text-sm font-medium text-foreground">Tributos adicionales</legend>
      <p class="mb-2 text-xs text-foreground-muted">
        {treatment === 'taxed'
          ? 'Solo si el producto lleva un tributo además del IVA, por ejemplo FOVIAL y COTRANS en combustibles.'
          : 'Un producto exento o no sujeto no lleva tributos adicionales.'}
      </p>
      <input
        bind:value={taxFilter}
        placeholder="Filtrar tributos…"
        aria-label="Filtrar tributos"
        class="mb-2 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none"
      />
      <div class="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
        {#each visibleTaxes as tax (tax.code)}
          <label
            class="flex min-h-9 items-start gap-2 rounded px-2 py-1 text-sm hover:bg-surface-muted/50"
          >
            <input
              type="checkbox"
              checked={selected.includes(tax.code)}
              onchange={() => toggleTax(tax.code)}
              class="mt-1"
            />
            <span><span class="font-mono text-foreground-muted">{tax.code}</span> · {tax.name}</span
            >
          </label>
        {:else}
          <p class="p-2 text-sm text-foreground-muted">Sin tributos que coincidan.</p>
        {/each}
      </div>
    </fieldset>

    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
