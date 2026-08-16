<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { onMount, tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, Product, ProductImageDraft, SubCategory, Unit } from '$lib/types/catalog';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import EditorSectionNav from '$lib/components/editor/EditorSectionNav.svelte';
  import ProductImagesEditor from './ProductImagesEditor.svelte';

  interface Props {
    mode: 'create' | 'edit';
    productId?: number;
  }

  type ProductForm = {
    sku: string;
    name: string;
    category_id: string;
    sub_category_id: string;
    purchase_unit: string;
    sale_unit: string;
    original_code: string;
    internal_code: string;
    size: string;
    dimensions: string;
    presentation: string;
    description: string;
    is_active: boolean;
    images: ProductImageDraft[];
  };

  let { mode, productId }: Props = $props();
  const emptyForm = (): ProductForm => ({
    sku: '',
    name: '',
    category_id: '',
    sub_category_id: '',
    purchase_unit: '',
    sale_unit: '',
    original_code: '',
    internal_code: '',
    size: '',
    dimensions: '',
    presentation: '',
    description: '',
    is_active: true,
    images: []
  });

  const sections = [
    ['general', 'Identidad del producto'],
    ['classification', 'Clasificación y unidades'],
    ['identifiers', 'Códigos y presentación'],
    ['gallery', 'Galería de imágenes'],
    ['review', 'Revisión']
  ] as const;

  let form = $state<ProductForm>(emptyForm());
  let categories = $state<Category[]>([]);
  let subCategories = $state<SubCategory[]>([]);
  let units = $state<Unit[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let errors = $state<Record<string, string>>({});
  let initialSnapshot = $state('');
  let pendingTarget = $state<string | null>(null);
  let activeSection = $state('general');
  let editorHeader: HTMLElement;

  let canManage = $derived(permissions.hasPermission('products:manage'));
  let canEditImages = $derived(permissions.hasPermission('products:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));
  let dirty = $derived(!loading && initialSnapshot !== JSON.stringify(form));
  let filteredSubCategories = $derived(
    form.category_id
      ? subCategories.filter((item) => String(item.id_category) === form.category_id)
      : []
  );
  let galleryValid = $derived(
    !canEditImages ||
      (form.images.length <= 20 &&
        form.images.every((image) => {
          if (!image.url.trim()) return false;
          if (image.source_type === 'cloudinary') return Boolean(image.media_asset_id);
          try {
            const parsed = new URL(image.url.trim());
            return parsed.protocol === 'https:' && !parsed.username && !parsed.password;
          } catch {
            return false;
          }
        }) &&
        new Set(form.images.map((image) => image.url.trim().toLocaleLowerCase()).filter(Boolean))
          .size === form.images.length &&
        (form.images.length === 0 || form.images.filter((image) => image.is_cover).length === 1))
  );

  const categoryOptions = $derived(
    categories.map((item) => ({ value: String(item.id_category), label: item.name }))
  );
  const subCategoryOptions = $derived(
    filteredSubCategories.map((item) => ({ value: String(item.id_sub_category), label: item.name }))
  );
  const unitOptions = $derived(
    units.map((item) => ({ value: String(item.id_unit), label: `${item.name} (${item.symbol})` }))
  );

  function fromProduct(product: Product) {
    form = {
      ...emptyForm(),
      sku: product.sku,
      name: product.name,
      category_id: String(product.id_category),
      sub_category_id: product.id_sub_category ? String(product.id_sub_category) : '',
      purchase_unit: String(product.purchase_unit),
      sale_unit: String(product.sale_unit),
      original_code: product.original_code ?? '',
      internal_code: product.internal_code ?? '',
      size: product.size ?? '',
      dimensions: product.dimensions ?? '',
      presentation: product.presentation ?? '',
      description: product.description ?? '',
      is_active: product.is_active,
      images: (product.images ?? []).map((image) => ({
        id: image.id,
        source_type: image.source_type,
        url: image.url,
        media_asset_id: image.media_asset_id ?? null,
        alt_text: image.alt_text ?? '',
        position: image.position,
        is_cover: image.is_cover
      }))
    };
  }

  function scrollToSection(id: string, behavior: ScrollBehavior = 'smooth') {
    const target = document.getElementById(id);
    const scrollContainer = target?.closest<HTMLElement>('[data-app-scroll-container]');
    if (!target || !scrollContainer) return;
    const containerRect = scrollContainer.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offset = (editorHeader?.offsetHeight ?? 0) + 16;
    const requestedTop = scrollContainer.scrollTop + targetRect.top - containerRect.top - offset;
    const maximumTop = Math.max(scrollContainer.scrollHeight - scrollContainer.clientHeight, 0);
    activeSection = id;
    scrollContainer.scrollTo({
      top: Math.min(Math.max(requestedTop, 0), maximumTop),
      behavior
    });
    history.replaceState(
      history.state,
      '',
      `${window.location.pathname}${window.location.search}#${id}`
    );
  }

  async function load() {
    loading = true;
    error = null;
    try {
      const [categoryData, subCategoryData, unitData] = await Promise.all([
        catalogApi.listCategories(true),
        catalogApi.listSubCategories(undefined, true),
        catalogApi.listUnits(true)
      ]);
      categories = categoryData;
      subCategories = subCategoryData;
      units = unitData;
      if (mode === 'edit') {
        if (!productId || productId < 1) throw new Error('Producto no válido.');
        fromProduct(await catalogApi.getProduct(productId));
      } else {
        form.category_id = categories[0] ? String(categories[0].id_category) : '';
        form.purchase_unit = units[0] ? String(units[0].id_unit) : '';
        form.sale_unit = units[0] ? String(units[0].id_unit) : '';
      }
      initialSnapshot = JSON.stringify(form);
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo cargar el editor.';
    } finally {
      loading = false;
    }
  }

  function validate() {
    const next: Record<string, string> = {};
    if (form.sku.trim().length < 1) next.sku = 'Ingrese el SKU del producto.';
    if (form.name.trim().length < 2) next.name = 'Ingrese el nombre del producto.';
    if (!form.category_id) next.category_id = 'Seleccione una categoría.';
    if (!form.purchase_unit) next.purchase_unit = 'Seleccione la unidad de compra.';
    if (!form.sale_unit) next.sale_unit = 'Seleccione la unidad de venta.';
    if (!galleryValid)
      next.gallery = 'Revise las imágenes: URL HTTPS válida, asset cargado y una portada.';
    errors = next;
    if (Object.keys(next).length) {
      scrollToSection(next.gallery ? 'gallery' : next.category_id ? 'classification' : 'general');
      return false;
    }
    return true;
  }

  function payload() {
    const data = {
      id_category: Number(form.category_id),
      id_sub_category: form.sub_category_id ? Number(form.sub_category_id) : null,
      sku: form.sku.trim(),
      name: form.name.trim(),
      purchase_unit: Number(form.purchase_unit),
      sale_unit: Number(form.sale_unit),
      original_code: form.original_code.trim(),
      internal_code: form.internal_code.trim(),
      size: form.size.trim(),
      dimensions: form.dimensions.trim(),
      presentation: form.presentation.trim(),
      description: form.description.trim(),
      ...(mode === 'edit' ? { is_active: form.is_active } : {}),
      ...(canEditImages ? { images: form.images.filter((image) => image.url.trim()) } : {})
    };
    return data;
  }

  async function save() {
    if (!canManage) {
      error = 'No tiene permisos para gestionar productos.';
      return;
    }
    if (!validate()) return;
    saving = true;
    error = null;
    try {
      if (mode === 'edit' && productId) {
        await catalogApi.updateProduct(productId, payload());
        initialSnapshot = JSON.stringify(form);
        await goto(`/products/${productId}`);
      } else {
        const created = await catalogApi.createProduct(payload());
        await goto(`/products/${created.id_product}`);
      }
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo guardar el producto.';
    } finally {
      saving = false;
    }
  }

  function requestLeave(target: string) {
    if (dirty) {
      pendingTarget = target;
      return;
    }
    void goto(target);
  }

  beforeNavigate((navigation) => {
    const from = navigation.from?.url;
    const to = navigation.to?.url;
    const hashOnly =
      from &&
      to &&
      from.pathname === to.pathname &&
      from.search === to.search &&
      from.hash !== to.hash;
    if (hashOnly) return;
    if (dirty && !saving && navigation.to?.url.pathname !== pendingTarget) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? '/products';
    }
  });

  onMount(() => {
    void load().then(async () => {
      await tick();
      const initialSection = window.location.hash.slice(1);
      if (sections.some(([id]) => id === initialSection)) scrollToSection(initialSection, 'auto');
    });
  });
</script>

<svelte:head>
  <title>{mode === 'create' ? 'Nuevo producto' : 'Editar producto'} — GestionaSV</title>
</svelte:head>

<div class="min-h-full bg-background px-6 pb-6 md:px-8 md:pb-8">
  <header
    bind:this={editorHeader}
    class="sticky top-0 z-30 mb-6 flex items-center gap-3 border-b border-border bg-background/95 pb-3 pt-6 backdrop-blur md:pt-8"
  >
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver"
      onclick={() =>
        requestLeave(mode === 'edit' && productId ? `/products/${productId}` : '/products')}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
      >
    </button>
    <div class="min-w-0 flex-1">
      <h1 class="text-xl font-bold text-foreground">
        {mode === 'create' ? 'Nuevo producto' : 'Editar producto'}
      </h1>
      <p class="text-sm text-foreground-muted">
        {mode === 'create'
          ? 'Registra un producto completo en el catálogo.'
          : 'Actualiza la información comercial y visual del producto.'}
      </p>
    </div>
    <div class="flex shrink-0 items-center gap-2">
      {#if dirty}<span
          class="hidden rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning sm:inline"
          >Cambios sin guardar</span
        >{/if}
      <Button
        variant="secondary"
        size="sm"
        onclick={() =>
          requestLeave(mode === 'edit' && productId ? `/products/${productId}` : '/products')}
        >Cancelar</Button
      >
      <Button size="sm" onclick={save} disabled={saving || loading || !canManage}
        >{saving ? 'Guardando…' : mode === 'create' ? 'Crear producto' : 'Guardar cambios'}</Button
      >
    </div>
  </header>

  {#if pendingTarget}
    <div
      class="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm"
    >
      <span class="flex-1">Hay cambios sin guardar. ¿Desea descartarlos?</span>
      <Button size="sm" variant="secondary" onclick={() => (pendingTarget = null)}
        >Continuar editando</Button
      >
      <Button
        size="sm"
        onclick={() => {
          const target = pendingTarget!;
          initialSnapshot = JSON.stringify(form);
          pendingTarget = null;
          void goto(target);
        }}>Descartar cambios</Button
      >
    </div>
  {/if}
  {#if error}<div
      class="mb-5 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}

  {#if loading}
    <div class="grid gap-4 lg:grid-cols-[220px_1fr]">
      <div class="h-72 rounded-xl skeleton"></div>
      <div class="h-[620px] rounded-xl skeleton"></div>
    </div>
  {:else}
    <div class="mx-auto grid max-w-[1280px] gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <EditorSectionNav {sections} {activeSection} onselect={scrollToSection} />
      <main class="min-w-0 space-y-6">
        <Card id="general" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Identidad del producto</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Los datos con los que el equipo identifica y busca el producto.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="product-sku"
              label="SKU"
              bind:value={form.sku}
              error={errors.sku}
              required
              placeholder="Ej. HAR-001"
            />
            <FormField
              id="product-name"
              label="Nombre del producto"
              bind:value={form.name}
              error={errors.name}
              required
              placeholder="Ej. Harina de trigo"
            />
          </div>
        </Card>

        <Card id="classification" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Clasificación y unidades</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Organiza el catálogo y define cómo se compra y vende.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <SmartSelect
              id="product-category"
              label="Categoría"
              bind:value={form.category_id}
              error={errors.category_id}
              required
              options={categoryOptions}
            />
            <SmartSelect
              id="product-subcategory"
              label="Subcategoría"
              bind:value={form.sub_category_id}
              options={subCategoryOptions}
              disabled={!form.category_id}
              placeholder="Sin subcategoría"
            />
            <SmartSelect
              id="product-purchase-unit"
              label="Unidad de compra"
              bind:value={form.purchase_unit}
              error={errors.purchase_unit}
              required
              options={unitOptions}
            />
            <SmartSelect
              id="product-sale-unit"
              label="Unidad de venta"
              bind:value={form.sale_unit}
              error={errors.sale_unit}
              required
              options={unitOptions}
            />
          </div>
        </Card>

        <Card id="identifiers" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Códigos y presentación</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Referencias internas, dimensiones y descripción comercial.
          </p>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField
              id="product-original"
              label="Código original"
              bind:value={form.original_code}
              placeholder="Código del fabricante"
            />
            <FormField
              id="product-internal"
              label="Código interno"
              bind:value={form.internal_code}
              placeholder="Referencia interna"
            />
            <FormField
              id="product-size"
              label="Tamaño"
              bind:value={form.size}
              placeholder="Ej. Mediano"
            />
            <FormField
              id="product-dimensions"
              label="Dimensiones"
              bind:value={form.dimensions}
              placeholder="Ej. 20 × 30 cm"
            />
            <FormField
              id="product-presentation"
              label="Presentación"
              bind:value={form.presentation}
              placeholder="Ej. Caja de 12 unidades"
            />
            {#if mode === 'edit'}
              <label
                class="flex items-center gap-2 self-end pb-2 text-sm font-medium text-foreground"
                ><input
                  type="checkbox"
                  bind:checked={form.is_active}
                  class="rounded border-border text-primary"
                /> Producto activo</label
              >
            {/if}
            <div class="sm:col-span-2 lg:col-span-3">
              <label
                for="product-description"
                class="mb-1 block text-sm font-medium text-foreground">Descripción</label
              >
              <textarea
                id="product-description"
                bind:value={form.description}
                rows="5"
                maxlength="4000"
                placeholder="Describe características, uso y recomendaciones."
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              ></textarea>
            </div>
          </div>
        </Card>

        <Card id="gallery" class="scroll-mt-24 p-6">
          <ProductImagesEditor
            bind:images={form.images}
            companyId={company.id ?? ''}
            editable={canEditImages}
            canUpload={canUploadImages}
          />
          {#if errors.gallery}<p class="mt-3 text-xs text-danger" role="alert">
              {errors.gallery}
            </p>{/if}
        </Card>

        <Card id="review" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Revisión</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Verifica los datos antes de guardar el producto.
          </p>
          <dl class="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-foreground-muted">Producto</dt>
              <dd class="font-medium text-foreground">{form.sku || '—'} · {form.name || '—'}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Clasificación</dt>
              <dd class="font-medium text-foreground">
                {categories.find((item) => String(item.id_category) === form.category_id)?.name ??
                  '—'}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Unidades</dt>
              <dd class="font-medium text-foreground">
                {units.find((item) => String(item.id_unit) === form.purchase_unit)?.name ?? '—'} / {units.find(
                  (item) => String(item.id_unit) === form.sale_unit
                )?.name ?? '—'}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Galería</dt>
              <dd class="font-medium text-foreground">
                {form.images.length} imagen(es){#if !canEditImages}
                  · solo lectura{/if}
              </dd>
            </div>
          </dl>
        </Card>
      </main>
    </div>
  {/if}
</div>
