<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import type { ProductVariantConfig } from '$lib/types/catalog';
  import ProductVariantImageEditor from './ProductVariantImageEditor.svelte';

  interface Props {
    variantConfig: ProductVariantConfig | null | undefined;
    companyId: string;
    productId?: number;
    baseSku?: string;
    canUpload?: boolean;
    canEditImages?: boolean;
    canEditIdentifiers?: boolean;
    canEditVariant?: boolean;
    editable?: boolean;
    stage?: 'all' | 'attributes' | 'variants';
    generationMode?: 'all' | 'selected';
    onGenerate?: (config: ProductVariantConfig) => void | Promise<void>;
  }

  let {
    variantConfig = $bindable(),
    companyId,
    productId,
    baseSku = '',
    canUpload = true,
    canEditImages = true,
    canEditIdentifiers = true,
    canEditVariant = true,
    editable = true,
    stage = 'all',
    generationMode = 'all',
    onGenerate
  }: Props = $props();
  let error = $state<string | null>(null);
  let clientKeySequence = 0;

  function newClientKey(prefix: string) {
    clientKeySequence += 1;
    return `${prefix}-${clientKeySequence}`;
  }

  const emptyConfig = (): ProductVariantConfig => ({ attributes: [], variants: [] });

  function ensureConfig() {
    if (!variantConfig) variantConfig = emptyConfig();
    return variantConfig;
  }

  function updateAttribute(
    index: number,
    patch: Partial<ProductVariantConfig['attributes'][number]>
  ) {
    if (!editable) return;
    const config = ensureConfig();
    config.attributes = config.attributes.map((item, itemIndex) =>
      itemIndex === index ? { ...item, ...patch } : item
    );
    variantConfig = { ...config };
  }

  function addAttribute() {
    if (!editable) return;
    const config = ensureConfig();
    if (config.attributes.length >= 5) {
      error = 'Una familia admite como máximo 5 atributos.';
      return;
    }
    config.attributes = [
      ...config.attributes,
      {
        _key: newClientKey('attribute'),
        code: `atributo_${config.attributes.length + 1}`,
        name: 'Nuevo atributo',
        position: config.attributes.length,
        values: []
      }
    ];
    variantConfig = { ...config };
    error = null;
  }

  function removeAttribute(index: number) {
    if (!editable) return;
    const config = ensureConfig();
    config.attributes = config.attributes
      .filter((_, itemIndex) => itemIndex !== index)
      .map((item, position) => ({ ...item, position }));
    config.variants = [];
    variantConfig = { ...config };
  }

  function addValue(attributeIndex: number) {
    if (!editable) return;
    const config = ensureConfig();
    const attribute = config.attributes[attributeIndex];
    if (!attribute) return;
    const values = [
      ...attribute.values,
      {
        _key: newClientKey('value'),
        code: `valor_${attribute.values.length + 1}`,
        label: `Valor ${attribute.values.length + 1}`,
        position: attribute.values.length
      }
    ];
    updateAttribute(attributeIndex, { values });
  }

  function updateValue(
    attributeIndex: number,
    valueIndex: number,
    patch: { code?: string; label?: string }
  ) {
    if (!editable) return;
    const config = ensureConfig();
    const attribute = config.attributes[attributeIndex];
    if (!attribute) return;
    updateAttribute(attributeIndex, {
      values: attribute.values.map((value, itemIndex) =>
        itemIndex === valueIndex ? { ...value, ...patch } : value
      )
    });
  }

  function removeValue(attributeIndex: number, valueIndex: number) {
    if (!editable) return;
    const config = ensureConfig();
    const attribute = config.attributes[attributeIndex];
    if (!attribute) return;
    updateAttribute(attributeIndex, {
      values: attribute.values
        .filter((_, itemIndex) => itemIndex !== valueIndex)
        .map((value, position) => ({ ...value, position }))
    });
    ensureConfig().variants = [];
    variantConfig = { ...ensureConfig() };
  }

  function cartesian<T>(sets: T[][]): T[][] {
    return sets.reduce<T[][]>(
      (result, set) => result.flatMap((prefix) => set.map((item) => [...prefix, item] as T[])),
      [[]]
    );
  }

  function generateCombinations() {
    if (!editable) return;
    const config = ensureConfig();
    if (
      !config.attributes.length ||
      config.attributes.some((attribute) => !attribute.values.length)
    ) {
      error = 'Cada atributo debe tener al menos un valor antes de generar combinaciones.';
      return;
    }
    const combinations = cartesian(config.attributes.map((attribute) => attribute.values));
    if (combinations.length > 500) {
      if (generationMode === 'selected') {
        config.variants = [];
        variantConfig = { ...config };
        error = null;
        if (onGenerate && variantConfig) void onGenerate(variantConfig);
        return;
      }
      error = 'La matriz supera el límite de 500 variantes.';
      return;
    }
    const previous = new Map(
      config.variants.map((variant) => [
        variant.values
          .map((value) => `${value.attribute_code}:${value.value_code}`)
          .sort()
          .join('|'),
        variant
      ])
    );
    config.variants = combinations.map((combination) => {
      const values = combination.map((value, valueIndex) => ({
        attribute_code: config.attributes[valueIndex]!.code,
        value_code: value.code
      }));
      const key = values
        .map((value) => `${value.attribute_code}:${value.value_code}`)
        .sort()
        .join('|');
      const existing = previous.get(key);
      const suffix = combination.map((value) => value.code.toUpperCase()).join('-');
      const suggestedSku = [baseSku.trim(), suffix].filter(Boolean).join('-') || `SKU-${suffix}`;
      return (
        existing ?? {
          id: null,
          sku: suggestedSku,
          name_override: null,
          lifecycle_status: 'draft',
          values,
          identifiers: [],
          image: null
        }
      );
    });
    variantConfig = { ...config };
    error = null;
    if (onGenerate && variantConfig) void onGenerate(variantConfig);
  }

  function updateVariant(index: number, patch: Partial<ProductVariantConfig['variants'][number]>) {
    if (!editable || !variantConfig) return;
    variantConfig = {
      ...variantConfig,
      variants: variantConfig.variants.map((variant, itemIndex) =>
        itemIndex === index ? { ...variant, ...patch } : variant
      )
    };
  }

  function setVariantStatus(
    index: number,
    status: ProductVariantConfig['variants'][number]['lifecycle_status']
  ) {
    const current = variantConfig?.variants[index];
    if (
      status === 'retired' &&
      current?.lifecycle_status !== 'retired' &&
      !window.confirm('¿Retirar esta variante? Su SKU se conservará para trazabilidad.')
    )
      return;
    updateVariant(index, { lifecycle_status: status });
  }

  function setVariantIdentifier(
    index: number,
    value: string,
    identifierType?: ProductVariantConfig['variants'][number]['identifiers'][number]['identifier_type']
  ) {
    const trimmed = value.trim();
    const currentType =
      identifierType ?? variantConfig?.variants[index]?.identifiers[0]?.identifier_type ?? 'ean';
    updateVariant(index, {
      identifiers: trimmed
        ? [{ identifier_type: currentType, value: trimmed, is_primary: true }]
        : []
    });
  }

  function setVariantIdentifierType(
    index: number,
    identifierType: ProductVariantConfig['variants'][number]['identifiers'][number]['identifier_type']
  ) {
    const currentValue = variantConfig?.variants[index]?.identifiers[0]?.value ?? '';
    setVariantIdentifier(index, currentValue, identifierType);
  }

  function setVariantImage(
    index: number,
    image: ProductVariantConfig['variants'][number]['image']
  ) {
    updateVariant(index, { image });
  }
</script>

<Card id="variants" class="scroll-mt-24 p-6">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 class="text-base font-semibold">Variantes y atributos</h2>
      <p class="mt-1 text-sm text-foreground-muted">
        Cree una familia, defina sus valores y genere la matriz. Proveedores y condiciones se
        heredan del producto padre.
      </p>
    </div>
    {#if editable && stage !== 'variants'}
      <div class="flex gap-2">
        <Button
          size="sm"
          variant="secondary"
          onclick={addAttribute}
          disabled={(variantConfig?.attributes.length ?? 0) >= 5}>Agregar atributo</Button
        >
        <Button
          size="sm"
          onclick={generateCombinations}
          disabled={!variantConfig?.attributes.length}>Generar combinaciones</Button
        >
      </div>
    {/if}
  </div>

  {#if error}<p
      class="mt-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </p>{/if}
  {#if editable && stage !== 'attributes' && !canEditImages}
    <p class="mt-4 text-xs text-foreground-muted">
      Las imágenes de variante se muestran en modo lectura porque falta el permiso <code
        class="rounded bg-surface-muted px-1">products:images</code
      >.
    </p>
  {/if}
  {#if editable && !canEditIdentifiers}
    <p class="mt-4 text-xs text-foreground-muted">
      Los identificadores se muestran en modo lectura porque falta el permiso <code
        class="rounded bg-surface-muted px-1">products:identifiers</code
      >.
    </p>
  {/if}

  {#if stage !== 'variants' && !variantConfig?.attributes.length}
    <div
      class="mt-5 rounded-lg border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
    >
      No hay atributos definidos. Un producto sin variantes seguirá funcionando como producto
      independiente.
    </div>
  {:else if stage !== 'variants' && variantConfig}
    <div class="mt-5 space-y-4">
      {#each variantConfig.attributes as attribute, attributeIndex (attribute._key ?? `attribute-${attributeIndex}`)}
        <div class="rounded-lg border border-border bg-surface-muted/20 p-4">
          <div class="grid gap-3 sm:grid-cols-[1fr_1.5fr_auto]">
            <label class="text-xs font-medium text-foreground-muted"
              >Código
              <input
                class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                value={attribute.code}
                disabled={!editable}
                aria-label={`Código del atributo ${attributeIndex + 1}`}
                oninput={(event) =>
                  updateAttribute(attributeIndex, {
                    code: (event.currentTarget as HTMLInputElement).value
                  })}
              />
            </label>
            <label class="text-xs font-medium text-foreground-muted"
              >Nombre visible
              <input
                class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                value={attribute.name}
                disabled={!editable}
                oninput={(event) =>
                  updateAttribute(attributeIndex, {
                    name: (event.currentTarget as HTMLInputElement).value
                  })}
              />
            </label>
            {#if editable}<Button
                size="sm"
                variant="ghost"
                onclick={() => removeAttribute(attributeIndex)}>Quitar</Button
              >{/if}
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            {#each attribute.values as value, valueIndex (value._key ?? `value-${attributeIndex}-${valueIndex}`)}
              <div
                class="flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1"
              >
                <input
                  class="w-24 bg-transparent text-xs text-foreground outline-none"
                  value={value.code}
                  disabled={!editable}
                  aria-label={`Código de valor ${valueIndex + 1}`}
                  oninput={(event) =>
                    updateValue(attributeIndex, valueIndex, {
                      code: (event.currentTarget as HTMLInputElement).value
                    })}
                />
                <span class="text-foreground-subtle">·</span>
                <input
                  class="w-28 bg-transparent text-xs text-foreground outline-none"
                  value={value.label}
                  disabled={!editable}
                  aria-label={`Etiqueta de valor ${valueIndex + 1}`}
                  oninput={(event) =>
                    updateValue(attributeIndex, valueIndex, {
                      label: (event.currentTarget as HTMLInputElement).value
                    })}
                />
                {#if editable}<button
                    type="button"
                    class="px-1 text-xs text-danger"
                    aria-label="Quitar valor"
                    onclick={() => removeValue(attributeIndex, valueIndex)}>×</button
                  >{/if}
              </div>
            {/each}
            {#if editable}<Button size="sm" variant="ghost" onclick={() => addValue(attributeIndex)}
                >Agregar valor</Button
              >{/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if stage !== 'attributes' && variantConfig?.variants.length}
    <div class="mt-6 overflow-x-auto rounded-lg border border-border">
      <table class="min-w-full text-sm">
        <thead
          class="border-b border-border bg-surface-muted/30 text-left text-xs text-foreground-muted"
        >
          <tr
            ><th class="px-3 py-2">Combinación</th><th class="px-3 py-2">SKU</th><th
              class="px-3 py-2">Nombre</th
            ><th class="px-3 py-2">Estado</th><th class="px-3 py-2">Identificador EAN</th><th
              class="px-3 py-2">Imagen HTTPS</th
            ><th class="px-3 py-2">Acciones</th></tr
          >
        </thead>
        <tbody>
          {#each variantConfig.variants as variant, index (variant.id ?? `variant-${index}`)}
            <tr class="border-b border-border last:border-0">
              <td class="px-3 py-2 text-xs text-foreground-muted"
                >{variant.values
                  .map((value) => `${value.attribute_code}: ${value.value_code}`)
                  .join(' · ')}</td
              >
              <td class="px-3 py-2"
                ><input
                  class="w-36 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
                  value={variant.sku}
                  disabled={!editable}
                  oninput={(event) =>
                    updateVariant(index, { sku: (event.currentTarget as HTMLInputElement).value })}
                /></td
              >
              <td class="px-3 py-2"
                ><input
                  class="w-40 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
                  value={variant.name_override ?? ''}
                  placeholder="Generado"
                  disabled={!editable}
                  oninput={(event) =>
                    updateVariant(index, {
                      name_override: (event.currentTarget as HTMLInputElement).value || null
                    })}
                /></td
              >
              <td class="px-3 py-2"
                ><select
                  class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
                  value={variant.lifecycle_status}
                  disabled={!editable}
                  onchange={(event) =>
                    setVariantStatus(
                      index,
                      (event.currentTarget as HTMLSelectElement)
                        .value as ProductVariantConfig['variants'][number]['lifecycle_status']
                    )}
                  ><option value="draft">Borrador</option><option value="active">Activa</option
                  ><option value="blocked">Bloqueada</option><option value="discontinued"
                    >Descontinuada</option
                  ><option value="retired">Retirada</option></select
                ></td
              >
              <td class="px-3 py-2"
                ><div class="flex gap-1">
                  <select
                    class="w-20 rounded-md border border-border bg-surface px-1 py-1.5 text-xs"
                    value={variant.identifiers[0]?.identifier_type ?? 'ean'}
                    disabled={!editable || !canEditIdentifiers}
                    onchange={(event) =>
                      setVariantIdentifierType(
                        index,
                        (event.currentTarget as HTMLSelectElement)
                          .value as ProductVariantConfig['variants'][number]['identifiers'][number]['identifier_type']
                      )}
                    ><option value="ean">EAN</option><option value="upc">UPC</option><option
                      value="gtin">GTIN</option
                    ><option value="internal">Interno</option><option value="other">Otro</option
                    ></select
                  ><input
                    class="w-28 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
                    value={variant.identifiers[0]?.value ?? ''}
                    placeholder="Opcional"
                    disabled={!editable || !canEditIdentifiers}
                    oninput={(event) =>
                      setVariantIdentifier(index, (event.currentTarget as HTMLInputElement).value)}
                  />
                </div></td
              >
              <td class="min-w-64 px-3 py-2"
                ><ProductVariantImageEditor
                  id={`product-variant-image-${index}`}
                  image={variant.image}
                  onChange={(image) => setVariantImage(index, image)}
                  {companyId}
                  {canUpload}
                  editable={editable && canEditImages}
                /></td
              >
              <td class="whitespace-nowrap px-3 py-2">
                {#if productId && variant.id}
                  <div class="flex flex-wrap gap-2">
                    <a
                      class="text-xs font-medium text-primary hover:underline"
                      href={`/products/${productId}/variants/${variant.id}`}>Ver detalle</a
                    >
                    {#if canEditVariant}
                      <a
                        class="text-xs font-medium text-foreground-muted hover:text-foreground hover:underline"
                        href={`/products/${productId}/variants/${variant.id}/edit`}
                        >Editar variante</a
                      >
                    {/if}
                  </div>
                {:else}
                  <span class="text-xs text-foreground-subtle">—</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="mt-2 text-right text-xs text-foreground-muted">
      {variantConfig.variants.length}/500 variantes
    </p>
  {/if}
</Card>
