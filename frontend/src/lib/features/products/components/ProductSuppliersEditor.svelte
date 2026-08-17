<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { suppliersApi } from '$lib/api/suppliers';
  import type { Currency, Supplier } from '$lib/types/supplier';
  import type { ProductSupplierDraft } from '$lib/types/catalog';
  import Button from '$lib/components/ui/Button.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';

  interface Props {
    relations: ProductSupplierDraft[];
    editable?: boolean;
  }

  let { relations = $bindable(), editable = true }: Props = $props();
  let suppliers = $state<Supplier[]>([]);
  let currencies = $state<Currency[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);

  const supplierOptions = $derived(
    suppliers.map((supplier) => ({
      value: String(supplier.id_supplier),
      label: supplier.name,
      description: `${supplier.code}${supplier.default_currency_code ? ` · ${supplier.default_currency_code}` : ''}`
    }))
  );
  const currencyOptions = $derived(
    currencies.map((currency) => ({
      value: currency.code,
      label: `${currency.code} — ${currency.name}`
    }))
  );

  onMount(async () => {
    try {
      const [supplierPage, currencyData] = await Promise.all([
        // Include inactive suppliers so existing historical relations remain readable.
        suppliersApi.listSuppliers({ active_only: false, page: 1, size: 100 }),
        suppliersApi.currencies()
      ]);
      suppliers = supplierPage.items;
      currencies = currencyData.filter((currency) => currency.is_active);
    } catch (error: unknown) {
      loadError =
        error instanceof HttpError
          ? error.status === 401
            ? 'Su sesión expiró. Inicie sesión nuevamente para cargar proveedores.'
            : error.status === 422
              ? 'No se pudo cargar la lista de proveedores. Verifique los filtros y vuelva a intentar.'
              : error.message
          : error instanceof Error
            ? error.message
            : 'No se pudieron cargar los proveedores.';
    } finally {
      loading = false;
    }
  });

  function addRelation() {
    if (!editable) return;
    relations = [
      ...relations,
      {
        supplier_id: 0,
        supplier_product_code: '',
        unit_cost: null,
        currency_code: null,
        minimum_order_qty: null,
        order_multiple: null,
        lead_time_days: null,
        is_preferred: relations.length === 0,
        status: 'active',
        valid_from: null,
        valid_until: null,
        notes: null
      }
    ];
  }

  function updateRelation(index: number, changes: Partial<ProductSupplierDraft>) {
    if (!editable) return;
    relations = relations.map((relation, relationIndex) =>
      relationIndex === index ? { ...relation, ...changes } : relation
    );
  }

  function setSupplier(index: number, value: string) {
    const supplierId = Number(value);
    if (!supplierId) return;
    updateRelation(index, { supplier_id: supplierId });
  }

  function setPreferred(index: number) {
    if (!editable) return;
    relations = relations.map((relation, relationIndex) => ({
      ...relation,
      is_preferred: relationIndex === index,
      status: relationIndex === index ? 'active' : relation.status
    }));
  }

  function removeRelation(index: number) {
    if (!editable) return;
    const next = relations.filter((_, relationIndex) => relationIndex !== index);
    if (next.length && !next.some((relation) => relation.is_preferred)) {
      const first = next[0];
      if (first) next[0] = { ...first, is_preferred: true, status: 'active' };
    }
    relations = next;
  }

  function numberValue(value: string): number | null {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
</script>

<section class="space-y-4" aria-labelledby="product-suppliers-title">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 id="product-suppliers-title" class="mb-1 text-base font-semibold">Proveedores</h2>
      <p class="text-sm text-foreground-muted">
        Relacione los proveedores autorizados, sus condiciones de compra y el proveedor preferido.
      </p>
    </div>
    {#if editable}
      <Button size="sm" variant="secondary" onclick={addRelation} disabled={loading || !!loadError}>
        Agregar proveedor
      </Button>
    {/if}
  </div>

  {#if loadError}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {loadError}
    </div>
  {:else if loading}
    <div class="h-24 rounded-xl skeleton" aria-label="Cargando proveedores"></div>
  {:else if !relations.length}
    <div
      class="rounded-xl border border-dashed border-border p-6 text-center text-sm text-foreground-muted"
    >
      No hay proveedores vinculados. Puede agregar uno ahora o hacerlo después desde el detalle del
      producto.
    </div>
  {:else}
    <div class="space-y-3">
      {#each relations as relation, index (relation.id ?? `new-supplier-${index}`)}
        <article class="rounded-xl border border-border bg-surface-muted/30 p-4">
          <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-foreground">Proveedor {index + 1}</span>
              {#if relation.is_preferred}
                <span class="badge-success rounded-md px-2 py-0.5 text-[11px] font-medium"
                  >Preferido</span
                >
              {/if}
            </div>
            {#if editable}
              <button
                type="button"
                class="text-xs text-danger hover:underline"
                onclick={() => removeRelation(index)}>Quitar relación</button
              >
            {/if}
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <SmartSelect
              id={`product-supplier-${index}`}
              label="Proveedor"
              value={relation.supplier_id ? String(relation.supplier_id) : ''}
              options={supplierOptions}
              placeholder="Buscar proveedor…"
              required
              disabled={!editable}
              onselect={(value) => setSupplier(index, value)}
            />
            <div>
              <label
                for={`supplier-code-${index}`}
                class="mb-1 block text-sm font-medium text-foreground"
              >
                Código del producto en el proveedor
              </label>
              <input
                id={`supplier-code-${index}`}
                value={relation.supplier_product_code ?? ''}
                maxlength="120"
                disabled={!editable}
                placeholder="Ej. DLC-HAR-25KG"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-50"
                oninput={(event) =>
                  updateRelation(index, {
                    supplier_product_code: (event.currentTarget as HTMLInputElement).value
                  })}
              />
            </div>
            <div>
              <label
                for={`supplier-cost-${index}`}
                class="mb-1 block text-sm font-medium text-foreground"
                >Costo unitario de referencia</label
              >
              <input
                id={`supplier-cost-${index}`}
                type="number"
                min="0"
                step="0.0001"
                value={relation.unit_cost ?? ''}
                disabled={!editable}
                placeholder="Ej. 24.50"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-50"
                oninput={(event) =>
                  updateRelation(index, {
                    unit_cost: numberValue((event.currentTarget as HTMLInputElement).value)
                  })}
              />
              <p class="mt-1 text-xs text-foreground-muted">
                Precio de referencia del proveedor; el costo real se determina en la compra.
              </p>
            </div>
            <SmartSelect
              id={`supplier-currency-${index}`}
              label="Moneda"
              value={relation.currency_code ?? ''}
              options={currencyOptions}
              placeholder="Seleccionar moneda…"
              disabled={!editable || relation.unit_cost == null}
              onselect={(value) => updateRelation(index, { currency_code: value || null })}
            />
            <div>
              <label
                for={`supplier-moq-${index}`}
                class="mb-1 block text-sm font-medium text-foreground">Cantidad mínima</label
              >
              <input
                id={`supplier-moq-${index}`}
                type="number"
                min="0.0001"
                step="0.0001"
                value={relation.minimum_order_qty ?? ''}
                disabled={!editable}
                placeholder="Opcional"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-50"
                oninput={(event) =>
                  updateRelation(index, {
                    minimum_order_qty: numberValue((event.currentTarget as HTMLInputElement).value)
                  })}
              />
            </div>
            <div>
              <label
                for={`supplier-multiple-${index}`}
                class="mb-1 block text-sm font-medium text-foreground">Múltiplo de pedido</label
              >
              <input
                id={`supplier-multiple-${index}`}
                type="number"
                min="0.0001"
                step="0.0001"
                value={relation.order_multiple ?? ''}
                disabled={!editable}
                placeholder="Opcional"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-50"
                oninput={(event) =>
                  updateRelation(index, {
                    order_multiple: numberValue((event.currentTarget as HTMLInputElement).value)
                  })}
              />
            </div>
            <div>
              <label
                for={`supplier-lead-${index}`}
                class="mb-1 block text-sm font-medium text-foreground"
                >Plazo de entrega (días)</label
              >
              <input
                id={`supplier-lead-${index}`}
                type="number"
                min="0"
                step="1"
                value={relation.lead_time_days ?? ''}
                disabled={!editable}
                placeholder="Opcional"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-50"
                oninput={(event) =>
                  updateRelation(index, {
                    lead_time_days: numberValue((event.currentTarget as HTMLInputElement).value)
                  })}
              />
            </div>
            <SmartSelect
              id={`supplier-status-${index}`}
              label="Estado de la relación"
              value={relation.status}
              options={[
                { value: 'active', label: 'Activa' },
                { value: 'inactive', label: 'Inactiva' }
              ]}
              disabled={!editable || relation.is_preferred}
              onselect={(value) =>
                updateRelation(index, { status: value as 'active' | 'inactive' })}
            />
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-3 text-sm">
            <label class="flex items-center gap-2 text-foreground-muted">
              <input
                type="checkbox"
                checked={relation.is_preferred}
                disabled={!editable || relation.status !== 'active'}
                onchange={() => setPreferred(index)}
              />
              Usar como proveedor preferido
            </label>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</section>
