<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/state';
  import { catalogApi } from '$lib/api/catalog';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PackagingManager from '$lib/features/inventory/components/PackagingManager.svelte';
  import ProductVariantImageEditor from '$lib/features/products/components/ProductVariantImageEditor.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type {
    Product,
    ProductIdentifier,
    ProductVariant,
    ProductVariantImageDraft,
    ProductVariantUpdateInput,
    Unit
  } from '$lib/types/catalog';

  type VariantStatus = ProductVariant['lifecycle_status'];
  type IdentifierType = ProductIdentifier['identifier_type'];

  interface IdentifierForm {
    _key: string;
    id?: string;
    identifier_type: IdentifierType;
    value: string;
    is_primary: boolean;
  }

  interface FormState {
    sku: string;
    name_override: string | null;
    lifecycle_status: VariantStatus;
    identifiers: IdentifierForm[];
    image: ProductVariantImageDraft | null;
  }

  interface UnitLoadResult {
    data: Unit[];
    error: string | null;
  }

  const statusOptions: { value: VariantStatus; label: string }[] = [
    { value: 'draft', label: 'Borrador' },
    { value: 'active', label: 'Activa' },
    { value: 'blocked', label: 'Bloqueada' },
    { value: 'discontinued', label: 'Descontinuada' },
    { value: 'retired', label: 'Retirada' }
  ];

  let productId = $derived(Number(page.params.id));
  let variantId = $derived((page.params as { variantId?: string }).variantId ?? '');
  let product = $state<Product | null>(null);
  let variant = $state<ProductVariant | null>(null);
  let units = $state<Unit[]>([]);
  let form = $state<FormState>({
    sku: '',
    name_override: null,
    lifecycle_status: 'draft',
    identifiers: [],
    image: null
  });
  let baseline = $state<FormState | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let inventoryUnitsError = $state<string | null>(null);
  let conflict = $state(false);
  let pendingTarget = $state<string | null>(null);
  let bypassNavigationGuard = $state(false);
  let keySequence = 0;

  let canEditVariant = $derived(permissions.hasPermission('products:variants'));
  let canEditIdentifiers = $derived(permissions.hasPermission('products:identifiers'));
  let canEditImages = $derived(permissions.hasPermission('products:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));
  let parentIsActive = $derived(product?.lifecycle_status === 'active');
  let dirty = $derived(
    !loading && baseline !== null && JSON.stringify(form) !== JSON.stringify(baseline)
  );

  function newKey() {
    keySequence += 1;
    return `identifier-${keySequence}`;
  }

  function toForm(value: ProductVariant): FormState {
    return {
      sku: value.sku,
      name_override: value.name_override ?? null,
      lifecycle_status: value.lifecycle_status,
      identifiers: value.identifiers.map((identifier) => ({
        _key: newKey(),
        id: identifier.id,
        identifier_type: identifier.identifier_type,
        value: identifier.value,
        is_primary: identifier.is_primary
      })),
      image: value.image
        ? {
            source_type: value.image.source_type,
            url: value.image.url,
            media_asset_id: value.image.media_asset_id ?? null,
            alt_text: value.image.alt_text ?? null
          }
        : null
    };
  }

  // `form` is a Svelte 5 reactive proxy; cloning its fields explicitly avoids
  // DataCloneError from structuredClone while keeping the baseline immutable.
  function cloneForm(value: FormState): FormState {
    return {
      sku: value.sku,
      name_override: value.name_override,
      lifecycle_status: value.lifecycle_status,
      identifiers: value.identifiers.map((identifier) => ({ ...identifier })),
      image: value.image ? { ...value.image } : null
    };
  }

  async function load() {
    if (!Number.isInteger(productId) || productId < 1 || !variantId) {
      error = 'La variante solicitada no es válida.';
      loading = false;
      return;
    }
    loading = true;
    error = null;
    inventoryUnitsError = null;
    conflict = false;
    try {
      const unitsRequest: Promise<UnitLoadResult> = permissions.hasPermission('inventory:read')
        ? catalogApi
            .listUnits(true)
            .then((data) => ({ data, error: null }))
            .catch(() => ({
              data: [],
              error: 'No se pudo cargar el catálogo de unidades para las presentaciones.'
            }))
        : Promise.resolve({ data: [], error: null });
      const [loadedProduct, loadedVariant, unitResult] = await Promise.all([
        catalogApi.getProduct(productId),
        catalogApi.getProductVariant(productId, variantId),
        unitsRequest
      ]);
      product = loadedProduct;
      variant = loadedVariant;
      units = unitResult.data;
      inventoryUnitsError = unitResult.error;
      form = toForm(loadedVariant);
      baseline = cloneForm(form);
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la variante.';
    } finally {
      loading = false;
    }
  }

  function setStatus(next: VariantStatus) {
    if (!variant || !canEditVariant) return;
    if (next === 'active' && !parentIsActive) {
      error = 'El producto padre debe estar activo antes de activar esta variante.';
      return;
    }
    if (next === 'retired' && variant.lifecycle_status !== 'retired') {
      if (!window.confirm('¿Retirar esta variante? Su SKU e historial se conservarán.')) return;
    }
    if (next === 'active' && variant.lifecycle_status === 'retired') {
      if (
        !window.confirm(
          '¿Reactivar esta variante? Verifique que el producto padre esté listo para operar.'
        )
      )
        return;
    }
    form = { ...form, lifecycle_status: next };
    error = null;
  }

  function updateIdentifier(index: number, patch: Partial<IdentifierForm>) {
    if (!canEditIdentifiers) return;
    const current = form.identifiers[index];
    if (!current) return;
    let next = form.identifiers.map((item, itemIndex) =>
      itemIndex === index ? { ...item, ...patch } : item
    );
    if (patch.is_primary) {
      next = next.map((item, itemIndex) =>
        item.identifier_type === (patch.identifier_type ?? current.identifier_type) &&
        itemIndex !== index
          ? { ...item, is_primary: false }
          : item
      );
    }
    form = { ...form, identifiers: next };
  }

  function addIdentifier() {
    if (!canEditIdentifiers || form.identifiers.length >= 20) return;
    form = {
      ...form,
      identifiers: [
        ...form.identifiers,
        { _key: newKey(), identifier_type: 'internal', value: '', is_primary: false }
      ]
    };
  }

  function removeIdentifier(index: number) {
    if (!canEditIdentifiers) return;
    form = { ...form, identifiers: form.identifiers.filter((_, itemIndex) => itemIndex !== index) };
  }

  function imageSnapshot(image: ProductVariantImageDraft | null) {
    return JSON.stringify(image);
  }

  function buildPayload(): ProductVariantUpdateInput | null {
    if (!variant || !baseline) return null;
    const payload: ProductVariantUpdateInput = {
      expected_updated_at: variant.updated_at ?? ''
    };
    let changed = false;
    if (canEditVariant && form.sku !== baseline.sku) {
      payload.sku = form.sku;
      changed = true;
    }
    if (canEditVariant && form.name_override !== baseline.name_override) {
      payload.name_override = form.name_override;
      changed = true;
    }
    if (canEditVariant && form.lifecycle_status !== baseline.lifecycle_status) {
      payload.lifecycle_status = form.lifecycle_status;
      changed = true;
    }
    if (
      canEditIdentifiers &&
      JSON.stringify(form.identifiers) !== JSON.stringify(baseline.identifiers)
    ) {
      payload.identifiers = form.identifiers.map(({ _key, ...identifier }) => identifier);
      changed = true;
    }
    if (canEditImages && imageSnapshot(form.image) !== imageSnapshot(baseline.image)) {
      payload.image = form.image;
      changed = true;
    }
    return changed ? payload : null;
  }

  async function save() {
    if (!variant || saving) return;
    const payload = buildPayload();
    if (!payload) {
      error = 'No hay cambios para guardar.';
      return;
    }
    if (!payload.sku?.trim() && 'sku' in payload) {
      error = 'El SKU es obligatorio.';
      return;
    }
    if (payload.expected_updated_at === '') {
      error = 'No se pudo determinar la versión actual de la variante. Recargue la página.';
      return;
    }
    saving = true;
    error = null;
    conflict = false;
    try {
      const updated = await catalogApi.updateProductVariant(productId, variantId, payload);
      variant = updated;
      form = toForm(updated);
      baseline = cloneForm(form);
      await goto(`/products/${productId}`);
    } catch (err: unknown) {
      if (err instanceof HttpError && err.status === 409) {
        conflict = true;
        error = null;
      } else {
        error = err instanceof HttpError ? err.message : 'No se pudo guardar la variante.';
      }
    } finally {
      saving = false;
    }
  }

  function requestLeave(target: string) {
    if (!dirty || saving) {
      void goto(target);
      return;
    }
    pendingTarget = target;
  }

  function discardAndLeave() {
    const target = pendingTarget ?? `/products/${productId}`;
    pendingTarget = null;
    // The navigation guard must allow this intentional discard through once.
    bypassNavigationGuard = true;
    void goto(target);
  }

  beforeNavigate((navigation) => {
    if (bypassNavigationGuard) {
      bypassNavigationGuard = false;
      return;
    }
    if (dirty && !saving) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? `/products/${productId}`;
    }
  });

  $effect(() => {
    if (productId && variantId) void load();
  });
</script>

<svelte:head>
  <title
    >{variant ? `Editar ${variant.display_name} — Productos` : 'Editar variante — Productos'}</title
  >
</svelte:head>

<div class="p-6 md:p-8">
  <header class="mx-auto mb-6 flex max-w-[1280px] flex-wrap items-start justify-between gap-4">
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
        >
          <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
        </svg>
      </button>
      <div class="min-w-0">
        <p class="text-xs font-medium uppercase tracking-wider text-foreground-subtle">Productos</p>
        <h1 class="mt-1 text-2xl font-bold text-foreground">Editar variante</h1>
        <p class="mt-1 text-sm text-foreground-muted">{product?.name ?? 'Variante del producto'}</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      {#if dirty}<span
          class="rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning"
          >Cambios sin guardar</span
        >{/if}
      <Button
        variant="secondary"
        size="sm"
        onclick={() => requestLeave(`/products/${productId}`)}>Cancelar</Button
      >
      <Button
        size="sm"
        onclick={save}
        disabled={saving ||
          loading ||
          !dirty ||
          (!canEditVariant && !canEditIdentifiers && !canEditImages)}
      >
        {saving ? 'Guardando…' : 'Guardar cambios'}
      </Button>
    </div>
  </header>

  {#if pendingTarget}
    <div
      class="mx-auto mb-5 flex max-w-[1280px] flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm"
      role="alert"
    >
      <span class="flex-1">Hay cambios sin guardar. ¿Desea descartarlos?</span>
      <Button size="sm" variant="secondary" onclick={() => (pendingTarget = null)}
        >Continuar editando</Button
      >
      <Button size="sm" onclick={discardAndLeave}>Descartar cambios</Button>
    </div>
  {/if}

  {#if loading}
    <div class="mx-auto max-w-[1280px] space-y-5">
      <div class="h-24 rounded-2xl skeleton"></div>
      <div class="h-[520px] rounded-2xl skeleton"></div>
    </div>
  {:else if error && !variant}
    <div
      class="mx-auto max-w-[1280px] rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if variant && product}
    <main class="mx-auto max-w-[1280px] space-y-5">
      <Card class="p-5">
        <div class="flex flex-wrap items-start gap-4">
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
              <h2 class="font-semibold text-foreground">{variant.display_name}</h2>
              <Badge variant="primary">Variante</Badge>
            </div>
            <p class="mt-1 font-mono text-xs text-foreground-muted">
              {product.name} · {product.sku}
            </p>
          </div>
          <div class="text-right">
            <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
              Última actualización
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              {variant.updated_at ? new Date(variant.updated_at).toLocaleString('es-SV') : '—'}
            </p>
          </div>
        </div>
        <div class="mt-4 flex flex-wrap gap-2" aria-label="Combinación de atributos">
          {#each variant.values as value (value.attribute_code)}<span
              class="rounded-full border border-border bg-surface-muted/30 px-3 py-1.5 text-xs text-foreground-muted"
              >{value.attribute_code}: <strong class="text-foreground">{value.label}</strong></span
            >{/each}
        </div>
        <p
          class="mt-4 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-foreground-muted"
        >
          La combinación es parte de la identidad de la variante y no se modifica aquí. Para
          cambiarla, gestione la familia y retire la combinación anterior conservando su historial.
        </p>
      </Card>

      {#if error}<div
          class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
          role="alert"
        >
          {error}
        </div>{/if}
      {#if conflict}<div
          class="flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-foreground"
        >
          <span class="flex-1"
            >La variante cambió mientras la editaba. Sus cambios siguen visibles; recargue para
            comparar la versión actual.</span
          ><Button size="sm" variant="secondary" onclick={load}>Recargar datos</Button>
        </div>{/if}

      <Card class="p-6">
        <div class="mb-5">
          <h2 class="text-base font-semibold text-foreground">Identidad de la variante</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            Corrija la referencia operativa sin alterar la combinación ni los datos heredados.
          </p>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <label class="text-sm font-medium text-foreground"
            >SKU <span class="text-danger">*</span><input
              class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 font-mono text-sm text-foreground"
              value={form.sku}
              disabled={!canEditVariant}
              oninput={(event) =>
                (form = { ...form, sku: (event.currentTarget as HTMLInputElement).value })}
            /></label
          >
          <label class="text-sm font-medium text-foreground"
            >Nombre personalizado <span class="font-normal text-foreground-subtle">(opcional)</span
            ><input
              class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground"
              value={form.name_override ?? ''}
              placeholder={variant.display_name}
              disabled={!canEditVariant}
              oninput={(event) =>
                (form = {
                  ...form,
                  name_override: (event.currentTarget as HTMLInputElement).value || null
                })}
            /></label
          >
        </div>
        <p class="mt-3 text-xs text-foreground-muted">
          Nombre mostrado si está vacío: <strong class="text-foreground"
            >{variant.display_name}</strong
          >
        </p>
      </Card>

      <Card class="p-6">
        <div class="mb-5">
          <h2 class="text-base font-semibold text-foreground">Estado operativo</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            Una variante activa solo puede operar dentro de un producto padre activo.
          </p>
        </div>
        <label class="block max-w-md text-sm font-medium text-foreground"
          >Estado<select
            class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground"
            value={form.lifecycle_status}
            disabled={!canEditVariant}
            onchange={(event) =>
              setStatus((event.currentTarget as HTMLSelectElement).value as VariantStatus)}
            >{#each statusOptions as option (option.value)}<option
                value={option.value}
                disabled={option.value === 'active' && !parentIsActive}>{option.label}</option
              >{/each}</select
          ></label
        >
        {#if !parentIsActive}<p class="mt-3 text-xs text-warning">
            El producto padre no está activo; la variante no puede activarse hasta corregir el
            estado del padre.
          </p>{/if}
      </Card>

      <Card class="p-6">
        <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-foreground">Identificadores</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Códigos de escaneo o referencia únicos en la empresa.
            </p>
          </div>
          {#if canEditIdentifiers}<Button
              size="sm"
              variant="secondary"
              onclick={addIdentifier}
              disabled={form.identifiers.length >= 20}>Agregar identificador</Button
            >{/if}
        </div>
        {#if !canEditIdentifiers}<p
            class="mb-4 rounded-lg border border-border bg-surface-muted/20 p-3 text-xs text-foreground-muted"
          >
            Modo lectura: necesita <code class="rounded bg-surface-muted px-1"
              >products:identifiers</code
            > para modificar estos códigos.
          </p>{/if}
        {#if form.identifiers.length}
          <div class="space-y-3">
            {#each form.identifiers as identifier, index (identifier._key)}<div
                class="grid gap-3 rounded-lg border border-border p-3 md:grid-cols-[180px_1fr_auto_auto] md:items-end"
              >
                <label class="text-xs font-medium text-foreground-muted"
                  >Tipo<select
                    class="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-2 text-sm text-foreground"
                    value={identifier.identifier_type}
                    disabled={!canEditIdentifiers}
                    onchange={(event) =>
                      updateIdentifier(index, {
                        identifier_type: (event.currentTarget as HTMLSelectElement)
                          .value as IdentifierType
                      })}
                    ><option value="ean">EAN</option><option value="upc">UPC</option><option
                      value="gtin">GTIN</option
                    ><option value="internal">Interno</option><option value="other">Otro</option
                    ></select
                  ></label
                ><label class="text-xs font-medium text-foreground-muted"
                  >Valor<input
                    class="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-2 text-sm text-foreground"
                    value={identifier.value}
                    disabled={!canEditIdentifiers}
                    oninput={(event) =>
                      updateIdentifier(index, {
                        value: (event.currentTarget as HTMLInputElement).value
                      })}
                  /></label
                ><label class="flex items-center gap-2 pb-2 text-xs text-foreground"
                  ><input
                    type="checkbox"
                    checked={identifier.is_primary}
                    disabled={!canEditIdentifiers}
                    onchange={(event) =>
                      updateIdentifier(index, {
                        is_primary: (event.currentTarget as HTMLInputElement).checked
                      })}
                  /> Principal</label
                >{#if canEditIdentifiers}<button
                    type="button"
                    class="pb-2 text-xs text-danger hover:underline"
                    onclick={() => removeIdentifier(index)}>Eliminar</button
                  >{/if}
              </div>{/each}
          </div>
        {:else}<div
            class="rounded-lg border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
          >
            No hay identificadores registrados.
          </div>{/if}
      </Card>

      <Card class="p-6">
        <div class="mb-5">
          <h2 class="text-base font-semibold text-foreground">Imagen principal</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            La imagen pertenece a esta variante; proveedores y datos de compra se heredan del
            producto padre.
          </p>
        </div>
        <ProductVariantImageEditor
          id="variant-image"
          bind:image={form.image}
          companyId={company.id ?? ''}
          canUpload={canUploadImages}
          editable={canEditImages}
        />
        {#if !canEditImages}<p class="mt-3 text-xs text-foreground-muted">
            Modo lectura: necesita <code class="rounded bg-surface-muted px-1">products:images</code
            > para modificar la imagen.
          </p>{/if}
      </Card>

      {#if product.product_kind === 'goods' && permissions.hasPermission('inventory:read')}
        <Card class="p-6">
          {#if inventoryUnitsError}
            <div
              class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
              role="alert"
            >
              {inventoryUnitsError}
            </div>
          {:else}
            <PackagingManager
              variantId={variant.id}
              defaultBaseUnitId={product.sale_unit}
              unitOptions={units.map((unit) => ({ id: unit.id_unit, label: unit.name }))}
              canManage={permissions.hasPermission('inventory:manage_packaging')}
            />
          {/if}
        </Card>
      {/if}

      <Card class="p-5"
        ><div class="flex items-start gap-3">
          <span class="mt-0.5 text-primary" aria-hidden="true">ⓘ</span>
          <div>
            <h2 class="text-sm font-semibold text-foreground">Datos heredados</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Categoría, unidades, proveedores, condiciones de compra, dimensiones y almacenamiento
              se administran desde el producto padre.
            </p>
          </div>
        </div></Card
      >
    </main>
  {/if}
</div>
