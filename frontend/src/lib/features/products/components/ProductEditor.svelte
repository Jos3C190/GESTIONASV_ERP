<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { onMount, tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import type {
    Category,
    Product,
    ProductImageDraft,
    ProductSupplierDraft,
    SubCategory,
    Unit
  } from '$lib/types/catalog';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import EditorSectionNav from '$lib/components/editor/EditorSectionNav.svelte';
  import ProductImagesEditor from './ProductImagesEditor.svelte';
  import ProductSuppliersEditor from './ProductSuppliersEditor.svelte';
  import type { DimensionUnit, WeightUnit } from '$lib/features/products/measurements';
  import {
    calculateProductVolume,
    DIMENSION_UNITS,
    formatProductDimensions,
    WEIGHT_UNITS
  } from '$lib/features/products/measurements';

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
    dimension_length: string;
    dimension_width: string;
    dimension_height: string;
    dimension_unit: DimensionUnit;
    weight: string;
    weight_unit: WeightUnit;
    presentation: string;
    description: string;
    product_kind: 'goods' | 'service';
    lifecycle_status: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
    can_purchase: boolean;
    can_sell: boolean;
    sales_name: string;
    internal_name: string;
    document_name: string;
    sales_description: string;
    purchase_description: string;
    internal_notes: string;
    keywords: string;
    storage_condition: 'ambient' | 'cool' | 'refrigerated' | 'frozen' | 'dry' | 'other' | '';
    storage_temperature_min_c: string;
    storage_temperature_max_c: string;
    storage_humidity_max_percent: string;
    is_fragile: boolean;
    keep_dry: boolean;
    keep_upright: boolean;
    stackable: boolean;
    max_stack_height: string;
    handling_notes: string;
    is_active: boolean;
    images: ProductImageDraft[];
    supplier_links: ProductSupplierDraft[];
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
    dimension_length: '',
    dimension_width: '',
    dimension_height: '',
    dimension_unit: 'cm',
    weight: '',
    weight_unit: 'kg',
    presentation: '',
    description: '',
    product_kind: 'goods',
    lifecycle_status: 'active',
    can_purchase: true,
    can_sell: true,
    sales_name: '',
    internal_name: '',
    document_name: '',
    sales_description: '',
    purchase_description: '',
    internal_notes: '',
    keywords: '',
    storage_condition: '',
    storage_temperature_min_c: '',
    storage_temperature_max_c: '',
    storage_humidity_max_percent: '',
    is_fragile: false,
    keep_dry: false,
    keep_upright: false,
    stackable: true,
    max_stack_height: '',
    handling_notes: '',
    is_active: true,
    images: [],
    supplier_links: []
  });

  const sections = [
    ['general', 'Identidad del producto'],
    ['classification', 'Clasificación y unidades'],
    ['identifiers', 'Códigos y presentación'],
    ['master', 'Información comercial'],
    ['storage', 'Almacenamiento'],
    ['suppliers', 'Proveedores'],
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
  let canEditSuppliers = $derived(permissions.hasPermission('products:suppliers'));
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
  const dimensionOptions = DIMENSION_UNITS.map((item) => ({
    value: item.value,
    label: item.label
  }));
  const weightOptions = WEIGHT_UNITS.map((item) => ({ value: item.value, label: item.label }));
  const dimensionSummary = $derived(
    formatProductDimensions(
      form.dimension_length ? Number(form.dimension_length) : null,
      form.dimension_width ? Number(form.dimension_width) : null,
      form.dimension_height ? Number(form.dimension_height) : null,
      form.dimension_unit
    )
  );
  const volume = $derived(
    calculateProductVolume(
      form.dimension_length ? Number(form.dimension_length) : null,
      form.dimension_width ? Number(form.dimension_width) : null,
      form.dimension_height ? Number(form.dimension_height) : null,
      form.dimension_unit
    )
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
      dimension_length: product.dimension_length != null ? String(product.dimension_length) : '',
      dimension_width: product.dimension_width != null ? String(product.dimension_width) : '',
      dimension_height: product.dimension_height != null ? String(product.dimension_height) : '',
      dimension_unit: product.dimension_unit ?? 'cm',
      weight: product.weight != null ? String(product.weight) : '',
      weight_unit: product.weight_unit ?? 'kg',
      presentation: product.presentation ?? '',
      description: product.description ?? '',
      product_kind: product.product_kind ?? 'goods',
      lifecycle_status: product.lifecycle_status ?? (product.is_active ? 'active' : 'blocked'),
      can_purchase: product.can_purchase ?? true,
      can_sell: product.can_sell ?? true,
      sales_name: product.sales_name ?? '',
      internal_name: product.internal_name ?? '',
      document_name: product.document_name ?? '',
      sales_description: product.sales_description ?? '',
      purchase_description: product.purchase_description ?? '',
      internal_notes: product.internal_notes ?? '',
      keywords: (product.keywords ?? []).join(', '),
      storage_condition: product.storage_condition ?? '',
      storage_temperature_min_c:
        product.storage_temperature_min_c != null ? String(product.storage_temperature_min_c) : '',
      storage_temperature_max_c:
        product.storage_temperature_max_c != null ? String(product.storage_temperature_max_c) : '',
      storage_humidity_max_percent:
        product.storage_humidity_max_percent != null
          ? String(product.storage_humidity_max_percent)
          : '',
      is_fragile: product.is_fragile ?? false,
      keep_dry: product.keep_dry ?? false,
      keep_upright: product.keep_upright ?? false,
      stackable: product.stackable ?? true,
      max_stack_height: product.max_stack_height != null ? String(product.max_stack_height) : '',
      handling_notes: product.handling_notes ?? '',
      is_active: product.is_active,
      images: (product.images ?? []).map((image) => ({
        id: image.id,
        source_type: image.source_type,
        url: image.url,
        media_asset_id: image.media_asset_id ?? null,
        alt_text: image.alt_text ?? '',
        position: image.position,
        is_cover: image.is_cover
      })),
      supplier_links: (product.supplier_links ?? []).map((relation) => ({
        id: relation.id,
        supplier_id: relation.supplier_id,
        supplier_product_code: relation.supplier_product_code ?? '',
        unit_cost: relation.unit_cost ?? null,
        currency_code: relation.currency_code ?? null,
        minimum_order_qty: relation.minimum_order_qty ?? null,
        order_multiple: relation.order_multiple ?? null,
        lead_time_days: relation.lead_time_days ?? null,
        is_preferred: relation.is_preferred,
        status: relation.status,
        valid_from: relation.valid_from ?? null,
        valid_until: relation.valid_until ?? null,
        notes: relation.notes ?? null
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
    const dimensionValues = [form.dimension_length, form.dimension_width, form.dimension_height];
    if (
      dimensionValues.some(
        (value) => value !== '' && (!Number.isFinite(Number(value)) || Number(value) < 0)
      )
    ) {
      next.dimensions = 'Las dimensiones deben ser números no negativos.';
    }
    if (dimensionValues.some(Boolean) && !form.dimension_unit) {
      next.dimensions = 'Seleccione la unidad de dimensión.';
    }
    if (form.weight !== '' && (!Number.isFinite(Number(form.weight)) || Number(form.weight) < 0)) {
      next.weight = 'El peso debe ser un número no negativo.';
    }
    if (form.weight !== '' && !form.weight_unit) next.weight = 'Seleccione la unidad de peso.';
    if (
      form.product_kind === 'service' &&
      (form.storage_condition ||
        form.storage_temperature_min_c ||
        form.storage_temperature_max_c ||
        form.storage_humidity_max_percent ||
        form.max_stack_height ||
        form.is_fragile ||
        form.keep_dry ||
        form.keep_upright)
    ) {
      next.storage = 'Los datos de almacenamiento solo aplican a bienes físicos.';
    }
    if (
      form.storage_temperature_min_c !== '' &&
      form.storage_temperature_max_c !== '' &&
      Number(form.storage_temperature_min_c) > Number(form.storage_temperature_max_c)
    ) {
      next.storage = 'La temperatura mínima no puede superar la máxima.';
    }
    if (canEditSuppliers) {
      const supplierIds = form.supplier_links.map((relation) => relation.supplier_id);
      if (supplierIds.some((supplierId) => !Number.isInteger(supplierId) || supplierId < 1)) {
        next.suppliers = 'Seleccione un proveedor para cada relación.';
      } else if (new Set(supplierIds).size !== supplierIds.length) {
        next.suppliers = 'Un proveedor no puede repetirse en el mismo producto.';
      } else if (form.supplier_links.filter((relation) => relation.is_preferred).length > 1) {
        next.suppliers = 'Solo puede existir un proveedor preferido.';
      } else if (
        !form.can_purchase &&
        form.supplier_links.some((relation) => relation.status === 'active')
      ) {
        next.suppliers = 'Un producto que no se compra no puede tener relaciones activas.';
      } else if (
        form.supplier_links.some(
          (relation) => relation.unit_cost != null && !relation.currency_code
        )
      ) {
        next.suppliers = 'Cada costo unitario requiere una moneda.';
      }
    }
    if (!galleryValid)
      next.gallery = 'Revise las imágenes: URL HTTPS válida, asset cargado y una portada.';
    errors = next;
    if (Object.keys(next).length) {
      scrollToSection(
        next.suppliers
          ? 'suppliers'
          : next.gallery
            ? 'gallery'
            : next.dimensions || next.weight
              ? 'identifiers'
              : next.storage
                ? 'storage'
                : next.category_id
                  ? 'classification'
                  : 'general'
      );
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
      dimension_length: form.dimension_length === '' ? null : Number(form.dimension_length),
      dimension_width: form.dimension_width === '' ? null : Number(form.dimension_width),
      dimension_height: form.dimension_height === '' ? null : Number(form.dimension_height),
      dimension_unit:
        form.dimension_length || form.dimension_width || form.dimension_height
          ? form.dimension_unit
          : null,
      weight: form.weight === '' ? null : Number(form.weight),
      weight_unit: form.weight === '' ? null : form.weight_unit,
      presentation: form.presentation.trim(),
      description: form.description.trim(),
      product_kind: form.product_kind,
      lifecycle_status: form.lifecycle_status,
      can_purchase: form.can_purchase,
      can_sell: form.can_sell,
      sales_name: form.sales_name.trim(),
      internal_name: form.internal_name.trim(),
      document_name: form.document_name.trim(),
      sales_description: form.sales_description.trim(),
      purchase_description: form.purchase_description.trim(),
      internal_notes: form.internal_notes.trim(),
      keywords: form.keywords
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      storage_condition: form.storage_condition || null,
      storage_temperature_min_c:
        form.storage_temperature_min_c === '' ? null : Number(form.storage_temperature_min_c),
      storage_temperature_max_c:
        form.storage_temperature_max_c === '' ? null : Number(form.storage_temperature_max_c),
      storage_humidity_max_percent:
        form.storage_humidity_max_percent === '' ? null : Number(form.storage_humidity_max_percent),
      is_fragile: form.is_fragile,
      keep_dry: form.keep_dry,
      keep_upright: form.keep_upright,
      stackable: form.stackable,
      max_stack_height: form.max_stack_height === '' ? null : Number(form.max_stack_height),
      handling_notes: form.handling_notes.trim(),
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
        if (canEditSuppliers) {
          await catalogApi.replaceProductSuppliers(productId, form.supplier_links);
        }
        initialSnapshot = JSON.stringify(form);
        await goto(`/products/${productId}`);
      } else {
        const created = await catalogApi.createProduct(payload());
        if (canEditSuppliers && form.supplier_links.length) {
          await catalogApi.replaceProductSuppliers(created.id_product, form.supplier_links);
        }
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
            <p class="-mt-2 text-xs text-foreground-muted sm:col-span-2 lg:col-span-3">
              Use este campo para tamaños comerciales como S, M o XL. Para combinaciones como color
              o talla use Variantes y atributos.
            </p>
            <FormField
              id="product-dimension-length"
              label="Largo"
              type="number"
              min="0"
              step="0.001"
              bind:value={form.dimension_length}
              error={errors.dimensions}
              placeholder="Ej. 20"
            />
            <FormField
              id="product-dimension-width"
              label="Ancho"
              type="number"
              min="0"
              step="0.001"
              bind:value={form.dimension_width}
              placeholder="Ej. 30"
            />
            <FormField
              id="product-dimension-height"
              label="Alto"
              type="number"
              min="0"
              step="0.001"
              bind:value={form.dimension_height}
              placeholder="Ej. 10"
            />
            <SmartSelect
              id="product-dimension-unit"
              label="Unidad de dimensión"
              bind:value={form.dimension_unit}
              error={errors.dimensions}
              options={dimensionOptions}
            />
            <FormField
              id="product-weight"
              label="Peso"
              type="number"
              min="0"
              step="0.001"
              bind:value={form.weight}
              error={errors.weight}
              placeholder="Ej. 2.5"
            />
            <SmartSelect
              id="product-weight-unit"
              label="Unidad de peso"
              bind:value={form.weight_unit}
              error={errors.weight}
              options={weightOptions}
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
            <div
              class="rounded-lg border border-border bg-surface-muted p-3 text-sm sm:col-span-2 lg:col-span-3"
            >
              <div class="flex flex-wrap gap-x-8 gap-y-2">
                <div>
                  <span class="text-foreground-muted">Resumen dimensional</span>
                  <p class="font-medium text-foreground">{dimensionSummary ?? 'No indicado'}</p>
                </div>
                <div>
                  <span class="text-foreground-muted">Volumen</span>
                  <p class="font-medium text-foreground">
                    {volume != null ? `${volume.toFixed(6)} m³` : 'No calculable'}
                  </p>
                </div>
              </div>
              <p class="mt-2 text-xs text-foreground-muted">
                El volumen se calcula automáticamente cuando se completan largo, ancho y alto.
              </p>
            </div>
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

        <Card id="master" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Información comercial</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Nombres y descripciones adaptados a cada operación del ERP.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="product-sales-name"
              label="Nombre de venta"
              bind:value={form.sales_name}
              placeholder="Nombre que verá el cliente"
            />
            <FormField
              id="product-internal-name"
              label="Nombre interno"
              bind:value={form.internal_name}
              placeholder="Referencia operativa"
            />
            <FormField
              id="product-document-name"
              label="Nombre para documentos"
              bind:value={form.document_name}
              placeholder="Nombre corto para facturas"
            />
            <FormField
              id="product-keywords"
              label="Palabras clave"
              bind:value={form.keywords}
              placeholder="harina, trigo, repostería"
            />
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.can_purchase}
                class="rounded border-border text-primary"
              /> Se puede comprar</label
            >
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.can_sell}
                class="rounded border-border text-primary"
              /> Se puede vender</label
            >
            <SmartSelect
              id="product-kind"
              label="Tipo de producto"
              bind:value={form.product_kind}
              options={[
                { value: 'goods', label: 'Bien físico' },
                { value: 'service', label: 'Servicio' }
              ]}
            />
            <SmartSelect
              id="product-status"
              label="Estado"
              bind:value={form.lifecycle_status}
              options={[
                { value: 'draft', label: 'Borrador' },
                { value: 'active', label: 'Activo' },
                { value: 'blocked', label: 'Bloqueado' },
                { value: 'discontinued', label: 'Descontinuado' },
                { value: 'retired', label: 'Retirado' }
              ]}
            />
            <div class="sm:col-span-2">
              <label
                for="product-sales-description"
                class="mb-1 block text-sm font-medium text-foreground"
                >Descripción para ventas</label
              >
              <textarea
                id="product-sales-description"
                bind:value={form.sales_description}
                rows="3"
                maxlength="4000"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted"
                placeholder="Descripción comercial para clientes."
              ></textarea>
            </div>
            <div class="sm:col-span-2">
              <label
                for="product-purchase-description"
                class="mb-1 block text-sm font-medium text-foreground"
                >Descripción para compras</label
              >
              <textarea
                id="product-purchase-description"
                bind:value={form.purchase_description}
                rows="3"
                maxlength="4000"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted"
                placeholder="Información útil para abastecimiento."
              ></textarea>
            </div>
            <div class="sm:col-span-2">
              <label
                for="product-internal-notes"
                class="mb-1 block text-sm font-medium text-foreground">Notas internas</label
              >
              <textarea
                id="product-internal-notes"
                bind:value={form.internal_notes}
                rows="3"
                maxlength="4000"
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted"
                placeholder="Notas que no se muestran al cliente."
              ></textarea>
            </div>
          </div>
        </Card>

        <Card id="storage" class="scroll-mt-24 p-6">
          <h2 class="mb-1 text-base font-semibold">Almacenamiento y manipulación</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Reglas operativas para bienes físicos; no aplican a servicios.
          </p>
          {#if errors.storage}<p
              class="mb-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
              role="alert"
            >
              {errors.storage}
            </p>{/if}
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SmartSelect
              id="product-storage-condition"
              label="Condición de almacenamiento"
              bind:value={form.storage_condition}
              options={[
                { value: '', label: 'No especificada' },
                { value: 'ambient', label: 'Ambiente' },
                { value: 'cool', label: 'Fresco' },
                { value: 'refrigerated', label: 'Refrigerado' },
                { value: 'frozen', label: 'Congelado' },
                { value: 'dry', label: 'Seco' },
                { value: 'other', label: 'Otra' }
              ]}
              disabled={form.product_kind === 'service'}
            />
            <FormField
              id="product-temp-min"
              label="Temperatura mínima (°C)"
              type="number"
              step="0.01"
              bind:value={form.storage_temperature_min_c}
              disabled={form.product_kind === 'service'}
            />
            <FormField
              id="product-temp-max"
              label="Temperatura máxima (°C)"
              type="number"
              step="0.01"
              bind:value={form.storage_temperature_max_c}
              disabled={form.product_kind === 'service'}
            />
            <FormField
              id="product-humidity"
              label="Humedad máxima (%)"
              type="number"
              min="0"
              max="100"
              step="0.01"
              bind:value={form.storage_humidity_max_percent}
              disabled={form.product_kind === 'service'}
            />
            <FormField
              id="product-stack-height"
              label="Altura máxima de apilado"
              type="number"
              min="0"
              step="0.01"
              bind:value={form.max_stack_height}
              disabled={form.product_kind === 'service'}
            />
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.is_fragile}
                disabled={form.product_kind === 'service'}
                class="rounded border-border text-primary"
              /> Frágil</label
            >
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.keep_dry}
                disabled={form.product_kind === 'service'}
                class="rounded border-border text-primary"
              /> Mantener seco</label
            >
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.keep_upright}
                disabled={form.product_kind === 'service'}
                class="rounded border-border text-primary"
              /> Mantener vertical</label
            >
            <label class="flex items-center gap-2 text-sm font-medium text-foreground"
              ><input
                type="checkbox"
                bind:checked={form.stackable}
                disabled={form.product_kind === 'service'}
                class="rounded border-border text-primary"
              /> Apilable</label
            >
            <div class="sm:col-span-2 lg:col-span-3">
              <label
                for="product-handling-notes"
                class="mb-1 block text-sm font-medium text-foreground">Notas de manipulación</label
              >
              <textarea
                id="product-handling-notes"
                bind:value={form.handling_notes}
                rows="3"
                maxlength="4000"
                disabled={form.product_kind === 'service'}
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted"
                placeholder="Indicaciones para traslado y almacenamiento."
              ></textarea>
            </div>
          </div>
        </Card>

        <Card id="suppliers" class="scroll-mt-24 p-6">
          <ProductSuppliersEditor
            bind:relations={form.supplier_links}
            editable={canEditSuppliers}
          />
          {#if errors.suppliers}
            <p
              class="mt-3 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
              role="alert"
            >
              {errors.suppliers}
            </p>
          {/if}
          {#if !canEditSuppliers}
            <p class="mt-3 text-xs text-foreground-muted">
              Puede consultar los proveedores vinculados, pero necesita el permiso
              <code class="rounded bg-surface-muted px-1">products:suppliers</code> para modificarlos.
            </p>
          {/if}
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
