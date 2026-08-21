<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/state';
  import { catalogApi } from '$lib/api/catalog';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import ProductCombinationSelector from '$lib/features/products/components/ProductCombinationSelector.svelte';
  import ProductVariantsEditor from '$lib/features/products/components/ProductVariantsEditor.svelte';
  import {
    normalizeVariantToken,
    cartesianCombinationCount,
    productToVariantConfig,
    toVariantConfigPayload,
    variantCombinationKey
  } from '$lib/features/products/variant-config';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Product, ProductVariantConfig, ProductVariantDraft } from '$lib/types/catalog';

  type Step = 1 | 2 | 3;
  type GenerationMode = 'all' | 'selected';

  let productId = $derived(Number(page.params.id));
  let product = $state<Product | null>(null);
  let config = $state<ProductVariantConfig>({ attributes: [], variants: [] });
  let loading = $state(true);
  let saving = $state(false);
  let validating = $state(false);
  let error = $state<string | null>(null);
  let fieldError = $state<string | null>(null);
  let preview = $state<{ attribute_count: number; variant_count: number } | null>(null);
  let previewFingerprint = $state('');
  let candidates = $state<ProductVariantDraft[]>([]);
  let selectedKeys = $state<string[]>([]);
  let existingKeys = $state<string[]>([]);
  let existingVariants = $state<ProductVariantDraft[]>([]);
  let generationMode = $state<GenerationMode>('all');
  let manualMode = $state(false);
  let manualValues = $state<Record<string, string>>({});
  let acknowledgeRetirements = $state(false);
  let applyingSelection = $state(false);
  let initialSnapshot = $state('');
  let initialSelectionSnapshot = $state('');
  let pendingTarget = $state<string | null>(null);
  let step = $state<Step>(1);

  let canEditVariants = $derived(permissions.hasPermission('products:variants'));
  let canEditImages = $derived(permissions.hasPermission('products:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));
  let canEditIdentifiers = $derived(permissions.hasPermission('products:identifiers'));
  let canEditVariant = $derived(canEditVariants || canEditIdentifiers || canEditImages);
  let dirty = $derived(
    !loading &&
      (initialSnapshot !== JSON.stringify(config) ||
        (candidates.length > 0 && initialSelectionSnapshot !== selectionFingerprint(selectedKeys)))
  );
  let readOnly = $derived(!canEditVariants);
  let retirementCount = $derived(existingKeys.filter((key) => !selectedKeys.includes(key)).length);
  let potentialCombinationCount = $derived(cartesianCombinationCount(config));

  function configFingerprint(value: ProductVariantConfig) {
    return JSON.stringify(
      value.attributes.map((attribute) => ({
        code: normalizeVariantToken(attribute.code),
        values: attribute.values.map((item) => normalizeVariantToken(item.code)).sort()
      }))
    );
  }

  function selectionFingerprint(keys: string[]) {
    return JSON.stringify([...keys].sort());
  }

  function attributeValidation(value: ProductVariantConfig): string | null {
    if (!value.attributes.length) return 'Agregue al menos un atributo para crear la familia.';
    if (value.attributes.length > 5) return 'Una familia admite como máximo 5 atributos.';
    const attributeCodes = value.attributes.map((attribute) =>
      normalizeVariantToken(attribute.code)
    );
    if (attributeCodes.some((code) => !code)) return 'Cada atributo necesita un código válido.';
    if (new Set(attributeCodes).size !== attributeCodes.length)
      return 'No puede repetir códigos de atributos.';
    for (const [index, attribute] of value.attributes.entries()) {
      if (!attribute.name.trim()) return `Ingrese el nombre del atributo ${index + 1}.`;
      if (!attribute.values.length) return `Agregue al menos un valor a “${attribute.name}”.`;
      const valueCodes = attribute.values.map((item) => normalizeVariantToken(item.code));
      if (valueCodes.some((code) => !code))
        return `Cada valor de “${attribute.name}” necesita un código válido.`;
      if (new Set(valueCodes).size !== valueCodes.length)
        return `No puede repetir valores dentro de “${attribute.name}”.`;
    }
    return null;
  }

  function finalValidation(value: ProductVariantConfig): string | null {
    const attributeError = attributeValidation(value);
    if (attributeError) return attributeError;
    if (!value.variants.length) return 'Genere al menos una combinación antes de guardar.';
    if (value.variants.length > 500) return 'La matriz supera el límite de 500 variantes.';
    const skus = value.variants.map((variant) => variant.sku.trim().toLocaleLowerCase());
    if (skus.some((sku) => !sku)) return 'Cada variante debe tener un SKU.';
    if (new Set(skus).size !== skus.length) return 'No puede repetir el SKU de una variante.';
    const expected = new Set(
      value.attributes.map((attribute) => normalizeVariantToken(attribute.code))
    );
    for (const variant of value.variants) {
      const pairs = variant.values.map(
        (item) =>
          `${normalizeVariantToken(item.attribute_code)}:${normalizeVariantToken(item.value_code)}`
      );
      const attributeCodes = variant.values.map((item) =>
        normalizeVariantToken(item.attribute_code)
      );
      if (
        new Set(attributeCodes).size !== attributeCodes.length ||
        new Set(attributeCodes).size !== expected.size ||
        !attributeCodes.every((code) => expected.has(code))
      ) {
        return `La combinación del SKU “${variant.sku || 'sin SKU'}” no contiene exactamente todos los atributos.`;
      }
      if (pairs.some((pair) => pair.endsWith(':')))
        return 'Cada combinación debe seleccionar valores válidos.';
    }
    return null;
  }

  async function handleGenerate(nextConfig: ProductVariantConfig) {
    fieldError = attributeValidation(nextConfig);
    if (fieldError) return;
    validating = true;
    error = null;
    preview = null;
    if (generationMode === 'selected' && !nextConfig.variants.length) {
      candidates = [];
      selectedKeys = [];
      manualMode = true;
      manualValues = {};
      acknowledgeRetirements = existingKeys.length === 0;
      preview = { attribute_count: nextConfig.attributes.length, variant_count: 0 };
      previewFingerprint = configFingerprint(nextConfig);
      step = 2;
      validating = false;
      return;
    }
    try {
      const result = await catalogApi.previewProductVariants(
        productId,
        toVariantConfigPayload(nextConfig)
      );
      preview = { attribute_count: result.attribute_count, variant_count: result.variant_count };
      candidates = nextConfig.variants.map((variant) => ({
        ...variant,
        values: variant.values.map((value) => ({ ...value }))
      }));
      manualMode = generationMode === 'selected' && candidates.length === 0;
      manualValues = {};
      selectedKeys = candidates.map(variantCombinationKey);
      const missingExisting = existingKeys.filter((key) => !selectedKeys.includes(key));
      acknowledgeRetirements = missingExisting.length === 0;
      previewFingerprint = configFingerprint(nextConfig);
      step = 2;
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : 'No se pudieron validar las combinaciones.';
    } finally {
      validating = false;
    }
  }

  async function reviewSelected() {
    if (!preview || !candidates.length) return;
    if (!selectedKeys.length) {
      fieldError = 'Seleccione al menos una combinación para continuar.';
      return;
    }
    applyingSelection = true;
    fieldError = null;
    error = null;
    const selected = candidates.filter((variant) =>
      selectedKeys.includes(variantCombinationKey(variant))
    );
    const nextConfig: ProductVariantConfig = { ...config, variants: selected };
    try {
      const result = await catalogApi.previewProductVariants(
        productId,
        toVariantConfigPayload(nextConfig)
      );
      config = nextConfig;
      preview = { attribute_count: result.attribute_count, variant_count: result.variant_count };
      previewFingerprint = configFingerprint(nextConfig);
      step = 3;
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : 'No se pudo validar la selección.';
    } finally {
      applyingSelection = false;
    }
  }

  function addManualCombination() {
    if (!manualMode || !canEditVariants) return;
    if (candidates.length >= 500) {
      fieldError = 'Una familia admite como máximo 500 variantes.';
      return;
    }
    const values = config.attributes.map((attribute) => ({
      attribute_code: attribute.code,
      value_code: manualValues[attribute.code] ?? ''
    }));
    if (values.some((value) => !value.value_code)) {
      fieldError = 'Seleccione un valor para cada atributo antes de agregar la combinación.';
      return;
    }
    const key = variantCombinationKey({ values });
    if (candidates.some((variant) => variantCombinationKey(variant) === key)) {
      fieldError = 'Esa combinación ya está incluida.';
      return;
    }
    const existing = existingVariants.find((variant) => variantCombinationKey(variant) === key);
    const suffix = values.map((value) => value.value_code.toUpperCase()).join('-');
    const nextVariant: ProductVariantDraft = existing ?? {
      id: null,
      sku: [product?.sku ?? '', suffix].filter(Boolean).join('-'),
      name_override: null,
      lifecycle_status: 'draft',
      values,
      identifiers: [],
      image: null
    };
    candidates = [...candidates, nextVariant];
    selectedKeys = [...selectedKeys, key];
    fieldError = null;
  }

  function mergeEditedVariantsIntoCandidates() {
    if (!candidates.length || !config.variants.length) return;
    const edited = new Map(
      config.variants.map((variant) => [variantCombinationKey(variant), variant])
    );
    candidates = candidates.map((variant) => edited.get(variantCombinationKey(variant)) ?? variant);
  }

  function openStep(next: Step) {
    if (readOnly) return;
    if (next === 2 && !preview) return;
    if (next === 2 && step === 3) mergeEditedVariantsIntoCandidates();
    if (next === 3) {
      void reviewSelected();
      return;
    }
    step = next;
    fieldError = null;
  }

  function requestLeave(target: string) {
    if (!dirty || saving) {
      void goto(target);
      return;
    }
    pendingTarget = target;
  }

  function cancelPendingLeave() {
    pendingTarget = null;
  }

  function discardAndLeave() {
    if (!pendingTarget) return;
    const target = pendingTarget;
    initialSnapshot = JSON.stringify(config);
    initialSelectionSnapshot = selectionFingerprint(selectedKeys);
    pendingTarget = null;
    void goto(target);
  }

  async function load() {
    if (!Number.isInteger(productId) || productId < 1) {
      error = 'Producto no válido.';
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      product = await catalogApi.getProduct(productId);
      const loadedConfig = productToVariantConfig(product) ?? { attributes: [], variants: [] };
      config = loadedConfig;
      candidates = [];
      selectedKeys = [];
      existingKeys = loadedConfig.variants.map(variantCombinationKey);
      existingVariants = loadedConfig.variants.map((variant) => ({ ...variant }));
      manualMode = false;
      manualValues = {};
      acknowledgeRetirements = true;
      initialSnapshot = JSON.stringify(config);
      initialSelectionSnapshot = selectionFingerprint(existingKeys);
      step = 1;
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la configuración.';
    } finally {
      loading = false;
    }
  }

  async function save() {
    if (!canEditVariants || saving) return;
    fieldError = finalValidation(config);
    if (fieldError) return;
    if (retirementCount > 0 && !acknowledgeRetirements) {
      fieldError = `Confirme el retiro de ${retirementCount} combinación(es) existente(s) antes de guardar.`;
      return;
    }
    saving = true;
    error = null;
    try {
      await catalogApi.replaceProductVariantConfig(productId, toVariantConfigPayload(config));
      initialSnapshot = JSON.stringify(config);
      await goto(`/products/${productId}`);
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : 'No se pudieron guardar las variantes.';
    } finally {
      saving = false;
    }
  }

  beforeNavigate((navigation) => {
    if (dirty && !saving && navigation.to?.url.pathname !== pendingTarget) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? `/products/${productId}`;
    }
  });

  $effect(() => {
    if (productId) void load();
  });

  $effect(() => {
    const fingerprint = configFingerprint(config);
    if (previewFingerprint && fingerprint !== previewFingerprint && step > 1) {
      preview = null;
      candidates = [];
      selectedKeys = [];
      manualMode = false;
      manualValues = {};
      acknowledgeRetirements = false;
      step = 1;
    }
  });
</script>

<svelte:head>
  <title
    >{product
      ? `Variantes de ${product.name} — Productos`
      : 'Variantes del producto — GestionaSV'}</title
  >
</svelte:head>

<div class="p-6 md:p-8">
  <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
    <div class="flex min-w-0 items-start gap-3">
      <button
        type="button"
        class="mt-1 flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
        aria-label="Volver al producto"
        onclick={() => requestLeave(`/products/${productId}`)}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
          ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
        >
      </button>
      <div class="min-w-0">
        <p class="text-xs font-medium uppercase tracking-wider text-foreground-subtle">Productos</p>
        <h1 class="mt-1 text-2xl font-bold text-foreground">Variantes y atributos</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {product?.name ?? 'Configura la familia del producto'}
        </p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      {#if dirty}<span
          class="rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning"
          >Cambios sin guardar</span
        >{/if}
      <Button variant="secondary" size="sm" onclick={() => requestLeave(`/products/${productId}`)}
        >Cancelar</Button
      >
      {#if canEditVariants && step === 3}<Button
          size="sm"
          onclick={save}
          disabled={saving || loading}>{saving ? 'Guardando…' : 'Guardar variantes'}</Button
        >{/if}
    </div>
  </header>

  {#if pendingTarget}
    <div
      class="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm"
      role="alert"
    >
      <span class="flex-1">Hay cambios sin guardar. ¿Desea descartarlos?</span>
      <Button size="sm" variant="secondary" onclick={cancelPendingLeave}>Continuar editando</Button>
      <Button size="sm" onclick={discardAndLeave}>Descartar cambios</Button>
    </div>
  {/if}

  {#if loading}
    <div class="space-y-5">
      <div class="h-28 rounded-2xl skeleton"></div>
      <div class="h-[520px] rounded-2xl skeleton"></div>
    </div>
  {:else if error && !product}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if product}
    <div class="mx-auto max-w-[1280px] space-y-5">
      <Card class="p-5">
        <div class="flex flex-wrap items-center gap-4">
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary"
            aria-hidden="true"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              ><path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z" /><path
                d="m4 7.5 8 4.5 8-4.5M12 12v9"
              /></svg
            >
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="font-semibold text-foreground">{product.name}</h2>
              <Badge variant={product.variant_mode === 'template' ? 'primary' : 'neutral'}
                >{product.variant_mode === 'template' ? 'Familia' : 'Producto independiente'}</Badge
              >
            </div>
            <p class="mt-1 font-mono text-xs text-foreground-muted">{product.sku}</p>
          </div>
          <div class="text-right">
            <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
              Variantes
            </p>
            <p class="font-mono text-2xl font-bold tabular-nums text-foreground">
              {product.variant_count ?? product.variants?.length ?? 0}
            </p>
          </div>
        </div>
        <p
          class="mt-4 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-foreground-muted"
        >
          Las variantes heredan categoría, unidades, proveedores, condiciones e información del
          producto padre. Aquí solo se definen sus atributos, SKU e identidad propia.
        </p>
      </Card>

      {#if readOnly}
        <Card class="p-5"
          ><div class="flex items-start gap-3">
            <span class="mt-0.5 text-warning" aria-hidden="true">ⓘ</span>
            <div>
              <h2 class="text-sm font-semibold text-foreground">Modo lectura</h2>
              <p class="mt-1 text-sm text-foreground-muted">
                Puede consultar la familia, pero necesita el permiso <code
                  class="rounded bg-surface-muted px-1">products:variants</code
                > para modificarla.
              </p>
            </div>
          </div></Card
        >
        <ProductVariantsEditor
          bind:variantConfig={config}
          companyId={company.id ?? ''}
          {productId}
          canUpload={canUploadImages}
          {canEditImages}
          {canEditIdentifiers}
          {canEditVariant}
          editable={false}
          stage="all"
        />
      {:else}
        <nav aria-label="Progreso de configuración" class="grid gap-2 sm:grid-cols-3">
          <button
            type="button"
            class:border-primary={step === 1}
            class="rounded-xl border border-border bg-surface p-3 text-left hover:border-border-strong"
            onclick={() => openStep(1)}
            ><span class="text-xs font-medium text-primary">Paso 1</span><span
              class="mt-1 block text-sm font-semibold text-foreground">Atributos</span
            ><span class="mt-1 block text-xs text-foreground-muted">Define valores permitidos</span
            ></button
          >
          <button
            type="button"
            class:border-primary={step === 2}
            class="rounded-xl border border-border bg-surface p-3 text-left hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!preview}
            onclick={() => openStep(2)}
            ><span class="text-xs font-medium text-primary">Paso 2</span><span
              class="mt-1 block text-sm font-semibold text-foreground">Combinaciones</span
            ><span class="mt-1 block text-xs text-foreground-muted"
              >Valida la matriz antes de editarla</span
            ></button
          >
          <button
            type="button"
            class:border-primary={step === 3}
            class="rounded-xl border border-border bg-surface p-3 text-left hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!preview}
            onclick={() => openStep(3)}
            ><span class="text-xs font-medium text-primary">Paso 3</span><span
              class="mt-1 block text-sm font-semibold text-foreground">Revisión</span
            ><span class="mt-1 block text-xs text-foreground-muted">Confirma SKU e identidad</span
            ></button
          >
        </nav>

        {#if error}<div
            class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
            role="alert"
          >
            {error}
          </div>{/if}
        {#if fieldError}<div
            class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
            role="alert"
          >
            {fieldError}
          </div>{/if}

        {#if step === 1}
          <Card class="p-5">
            <div>
              <h2 class="text-base font-semibold text-foreground">
                Cómo desea crear las combinaciones
              </h2>
              <p class="mt-1 text-sm text-foreground-muted">
                Puede crear la matriz completa o revisar cada combinación y conservar únicamente las
                presentaciones que realmente ofrece.
              </p>
            </div>
            <div
              class="mt-4 grid gap-3 sm:grid-cols-2"
              role="radiogroup"
              aria-label="Modo de generación"
            >
              <label
                class={`cursor-pointer rounded-xl border p-4 transition-colors ${generationMode === 'all' ? 'border-primary bg-primary/5' : 'border-border bg-surface'}`}
              >
                <input class="sr-only" type="radio" value="all" bind:group={generationMode} />
                <span class="block text-sm font-semibold text-foreground">Matriz completa</span>
                <span class="mt-1 block text-xs text-foreground-muted">
                  Incluye todas las combinaciones posibles. Ideal cuando cada color, talla o
                  presentación está disponible.
                </span>
              </label>
              <label
                class={`cursor-pointer rounded-xl border p-4 transition-colors ${generationMode === 'selected' ? 'border-primary bg-primary/5' : 'border-border bg-surface'}`}
              >
                <input class="sr-only" type="radio" value="selected" bind:group={generationMode} />
                <span class="block text-sm font-semibold text-foreground"
                  >Solo combinaciones seleccionadas</span
                >
                <span class="mt-1 block text-xs text-foreground-muted">
                  Propone la matriz y permite excluir combinaciones que no existen o no se venden.
                </span>
              </label>
            </div>
          </Card>
          <ProductVariantsEditor
            bind:variantConfig={config}
            companyId={company.id ?? ''}
            {productId}
            baseSku={product.sku}
            canUpload={canUploadImages}
            {canEditImages}
            {canEditIdentifiers}
            {canEditVariant}
            editable={canEditVariants}
            {generationMode}
            stage="attributes"
            onGenerate={handleGenerate}
          />
          {#if validating}<p class="text-center text-xs text-foreground-muted" role="status">
              Validando combinaciones…
            </p>{/if}
        {:else if step === 2 && preview}
          {#if manualMode}
            <Card class="p-5">
              <div class="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 class="text-base font-semibold text-foreground">
                    Matriz grande: agregue solo lo que existe
                  </h2>
                  <p class="mt-1 text-sm text-foreground-muted">
                    La matriz potencial tiene {potentialCombinationCount} combinaciones y supera el límite
                    de 500. En lugar de crear una matriz enorme, agregue únicamente las combinaciones
                    válidas para su operación.
                  </p>
                </div>
                <Badge variant="warning">Selección manual</Badge>
              </div>
              <div class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {#each config.attributes as attribute (attribute._key ?? attribute.code)}
                  <label class="text-xs font-medium text-foreground-muted">
                    {attribute.name}
                    <select
                      class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
                      value={manualValues[attribute.code] ?? ''}
                      onchange={(event) => {
                        manualValues = {
                          ...manualValues,
                          [attribute.code]: (event.currentTarget as HTMLSelectElement).value
                        };
                      }}
                    >
                      <option value="">Seleccionar…</option>
                      {#each attribute.values as value (value._key ?? value.code)}
                        <option value={value.code}>{value.label} ({value.code})</option>
                      {/each}
                    </select>
                  </label>
                {/each}
              </div>
              <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p class="text-xs text-foreground-muted">
                  {candidates.length}/500 combinaciones agregadas. Se conservará el SKU de una
                  combinación histórica si vuelve a incluirla.
                </p>
                <Button onclick={addManualCombination} disabled={!canEditVariants}
                  >Agregar combinación</Button
                >
              </div>
            </Card>
          {/if}
          {#if candidates.length}
            <ProductCombinationSelector
              {candidates}
              {selectedKeys}
              {existingKeys}
              attributes={config.attributes}
              editable={canEditVariants && generationMode === 'selected'}
              selectionMode={generationMode}
              onChange={(keys) => {
                selectedKeys = keys;
                acknowledgeRetirements = existingKeys.every((key) => keys.includes(key));
              }}
            />
          {/if}
          <Card class="p-5">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 class="text-base font-semibold text-foreground">
                  {generationMode === 'all'
                    ? 'Revisión de la matriz completa'
                    : 'Revisión de la selección'}
                </h2>
                <p class="mt-1 text-sm text-foreground-muted">
                  {#if manualMode}
                    Agregue combinaciones y revise la selección antes de enviarla al servidor. Se
                    guardarán únicamente las {selectedKeys.length} seleccionadas.
                  {:else if generationMode === 'all'}
                    El servidor validó {candidates.length} combinaciones. Se incluirán todas en la familia.
                  {:else}
                    El servidor validó {candidates.length} combinaciones posibles. Se guardarán únicamente
                    las {selectedKeys.length} seleccionadas.
                  {/if}
                </p>
              </div>
              <Badge variant={selectedKeys.length ? 'success' : 'warning'}>
                {selectedKeys.length}
                {generationMode === 'all' ? 'incluidas' : 'seleccionadas'}
              </Badge>
            </div>
            {#if retirementCount > 0}
              <label
                class="mt-4 flex items-start gap-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm"
              >
                <input class="mt-0.5" type="checkbox" bind:checked={acknowledgeRetirements} />
                <span>
                  Confirmo retirar {retirementCount} combinación(es) existentes que no están en la selección.
                  Su SKU y trazabilidad se conservarán; no se borrarán físicamente.
                </span>
              </label>
            {/if}
            <div class="mt-5 flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onclick={() => openStep(1)}>Volver a atributos</Button>
              <Button
                onclick={() => reviewSelected()}
                disabled={!selectedKeys.length || applyingSelection}
              >
                {applyingSelection
                  ? 'Validando…'
                  : generationMode === 'all'
                    ? 'Continuar con la matriz'
                    : 'Revisar variantes'}
              </Button>
            </div>
          </Card>
        {:else if step === 3}
          <ProductVariantsEditor
            bind:variantConfig={config}
            companyId={company.id ?? ''}
            {productId}
            baseSku={product.sku}
            canUpload={canUploadImages}
            {canEditImages}
            {canEditIdentifiers}
            {canEditVariant}
            editable={canEditVariants}
            stage="variants"
          />
          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="text-xs text-foreground-muted">
              {config.variants.length} variante(s) listas. Los cambios se guardarán en una sola operación.
            </p>
            <div class="flex gap-2">
              <Button variant="secondary" onclick={() => openStep(2)}>Volver a validación</Button
              ><Button onclick={save} disabled={saving || finalValidation(config) !== null}
                >{saving ? 'Guardando…' : 'Guardar variantes'}</Button
              >
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>
