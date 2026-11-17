<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import { customersApi } from '#lib/api/customers.ts';
  import { formatUnitLabel } from '#lib/features/sales/unit-label.ts';
  import {
    DOCUMENT_LABELS,
    SOURCE_LABELS,
    formatMoney,
    formatPercent,
    formatQuantity,
    formatUnitPrice
  } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { Customer } from '#lib/types/customer.ts';
  import { todayInElSalvador } from '#lib/features/price-lists/labels.ts';
  import type {
    OrderDraftInput,
    QuotationDraftInput,
    Sale,
    SalesCatalogItem,
    SalesQuotation
  } from '#lib/types/sales.ts';

  type DraftLine = {
    key: string;
    option: SalesCatalogItem | null;
    unitId: number | null;
    quantity: string;
    discount: string;
    manualPrice: string;
  };

  /** Editor común: cotización (V2d) o pedido (V2e). */
  let {
    kind = 'quotation',
    documentId = null
  }: { kind?: 'quotation' | 'order'; documentId?: string | null } = $props();
  const isOrder = $derived(kind === 'order');
  const noun = $derived(kind === 'order' ? 'pedido' : 'cotización');
  const listPath = $derived(kind === 'order' ? '/sales' : '/sales/quotations');

  let customers = $state<Customer[]>([]);
  let catalog = $state<SalesCatalogItem[]>([]);
  let branches = $state(branch.branches.filter((item) => item.is_active));
  let branchId = $state(branch.id ?? '');
  let customerId = $state('');
  let documentType = $state<'' | '01' | '03'>('');
  let validUntil = $state('');
  let globalDiscount = $state('0');
  let notes = $state('');
  let lines = $state<DraftLine[]>([newLine()]);
  let validityDays = $state<number | null>(null);
  let promisedDate = $state(todayInElSalvador());
  let deliveryMode = $state<'pickup' | 'delivery'>('pickup');
  let addressId = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let original = $state<SalesQuotation | Sale | null>(null);
  let preview = $state<SalesQuotation | Sale | null>(null);
  let previewError = $state<string | null>(null);
  let calculating = $state(false);
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const canOverride = $derived(permissions.hasPermission('sales_prices:override'));
  const customer = $derived(customers.find((item) => item.id === customerId) ?? null);
  const addresses = $derived((customer?.delivery_addresses ?? []).filter((item) => item.is_active));
  const documents = $derived(
    (customer?.receivable_documents ?? ['01']).filter(
      (code): code is '01' | '03' => code === '01' || code === '03'
    )
  );

  function newLine(): DraftLine {
    return {
      key: crypto.randomUUID(),
      option: null,
      unitId: null,
      quantity: '1',
      discount: '',
      manualPrice: ''
    };
  }

  function message(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError || cause instanceof Error) return cause.message;
    return fallback;
  }

  onMount(async () => {
    try {
      if (!branchId && branches.length === 1) branchId = branches[0]?.id ?? '';
      const [customerPage, items] = await Promise.all([
        customersApi.list({ active: true, size: 100 }),
        salesApi.catalog()
      ]);
      customers = customerPage.items;
      catalog = items;
      if (!isOrder) {
        validityDays = (await salesApi.quotationSettings()).quotation_validity_days;
      }
      if (documentId) {
        const document = isOrder
          ? await salesApi.sale(documentId)
          : await salesApi.quotation(documentId);
        if (document.status !== 'draft') throw new Error(`Este ${noun} ya no admite edición.`);
        original = document;
        branchId = document.branch_id;
        customerId = document.customer_id;
        documentType = document.document_type;
        globalDiscount = document.global_discount_percent;
        notes = document.notes ?? '';
        if ('valid_until' in document) validUntil = document.valid_until;
        if ('promised_date' in document) {
          promisedDate = document.promised_date;
          deliveryMode = document.delivery_mode;
          addressId = document.delivery_address_id ?? '';
        }
        lines = document.lines.map((line) => ({
          key: line.id ?? crypto.randomUUID(),
          option:
            catalog.find(
              (item) => item.product_id === line.product_id && item.variant_id === line.variant_id
            ) ?? null,
          unitId: line.unit_id,
          quantity: line.quantity,
          discount: line.discount_percent,
          manualPrice: line.price_overridden ? line.unit_price : ''
        }));
        if (lines.some((line) => !line.option)) {
          throw new Error(`Un producto de este ${noun} ya no está disponible para la venta.`);
        }
      }
    } catch (cause) {
      error = message(cause, 'No se pudieron preparar los datos.');
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    generation++;
    if (timer) clearTimeout(timer);
  });

  function payload(): QuotationDraftInput | OrderDraftInput | null {
    if (!branchId || !customerId) return null;
    if (isOrder && (!promisedDate || (deliveryMode === 'delivery' && !addressId))) return null;
    const items = [];
    for (const line of lines) {
      if (!line.option || !line.unitId || !(Number(line.quantity) > 0)) return null;
      items.push({
        product_id: line.option.product_id,
        variant_id: line.option.variant_id,
        unit_id: line.unitId,
        quantity: line.quantity,
        discount_percent: line.discount === '' ? null : line.discount,
        manual_price: line.manualPrice === '' ? null : line.manualPrice
      });
    }
    const common = {
      branch_id: branchId,
      customer_id: customerId,
      document_type: documentType || null,
      global_discount_percent: globalDiscount === '' ? '0' : globalDiscount,
      notes: notes.trim() || null,
      lines: items
    };
    if (isOrder) {
      return {
        ...common,
        promised_date: promisedDate,
        delivery_mode: deliveryMode,
        delivery_address_id: deliveryMode === 'delivery' ? addressId : null
      };
    }
    return { ...common, valid_until: validUntil || null };
  }

  // Recalcula en el servidor cuando algo cambia; descarta respuestas viejas.
  $effect(() => {
    const body = payload();
    const snapshot = JSON.stringify(body);
    if (timer) clearTimeout(timer);
    if (loading || !body) {
      preview = null;
      previewError = null;
      return;
    }
    const current = ++generation;
    timer = setTimeout(async () => {
      calculating = true;
      try {
        const result = isOrder
          ? await salesApi.previewOrder(JSON.parse(snapshot))
          : await salesApi.previewQuotation(JSON.parse(snapshot));
        if (current !== generation) return;
        preview = result;
        previewError = null;
      } catch (cause) {
        if (current !== generation) return;
        preview = null;
        previewError = message(cause, `No se pudo calcular el ${noun}.`);
      } finally {
        if (current === generation) calculating = false;
      }
    }, 400);
  });

  function setOption(line: DraftLine, value: string) {
    const option =
      catalog.find((item) => `${item.product_id}:${item.variant_id ?? ''}` === value) ?? null;
    line.option = option;
    line.unitId = option?.base_unit_id ?? null;
  }

  function removeLine(key: string) {
    if (lines.length > 1) lines = lines.filter((line) => line.key !== key);
  }

  function idempotencyKey(body: object): string {
    const storageKey = `sales-${kind}-create-pending`;
    const fingerprint = JSON.stringify(body);
    try {
      const previous = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null') as {
        fingerprint: string;
        key: string;
      } | null;
      if (previous?.fingerprint === fingerprint) return previous.key;
    } catch {
      /* se reemplaza un estado local inválido */
    }
    const key = crypto.randomUUID();
    sessionStorage.setItem(storageKey, JSON.stringify({ fingerprint, key }));
    return key;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    const body = payload();
    if (!body) {
      error = 'Elige cliente, sucursal y, en cada renglón, producto, unidad y cantidad.';
      return;
    }
    error = null;
    saving = true;
    try {
      let saved: { id: string };
      if (isOrder) {
        const order = body as OrderDraftInput;
        saved =
          documentId && original
            ? await salesApi.updateOrder(documentId, {
                ...order,
                expected_version: original.version
              })
            : await salesApi.createOrder(order, idempotencyKey(order));
      } else {
        const quote = body as QuotationDraftInput;
        saved =
          documentId && original
            ? await salesApi.updateQuotation(documentId, {
                ...quote,
                expected_version: original.version
              })
            : await salesApi.createQuotation(quote, idempotencyKey(quote));
      }
      sessionStorage.removeItem(`sales-${kind}-create-pending`);
      await goto(`${listPath}/${saved.id}`);
    } catch (cause) {
      error = message(cause, `No se pudo guardar el ${noun}.`);
    } finally {
      saving = false;
    }
  }

  function previewLine(index: number) {
    return preview?.lines[index] ?? null;
  }

  function availableOf(index: number): string | null {
    const line = preview?.lines[index];
    return line && 'available_base' in line ? line.available_base : null;
  }

  const title = $derived(
    documentId ? `Editar ${original?.code ?? noun}` : isOrder ? 'Nuevo pedido' : 'Nueva cotización'
  );
</script>

<svelte:head>
  <title>{title} | GestionaSV</title>
</svelte:head>

<div class="space-y-5">
  <a class="text-sm text-primary hover:underline" href={listPath}
    >← {isOrder ? 'Pedidos de venta' : 'Cotizaciones de venta'}</a
  >
  <header>
    <p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas · USD</p>
    <h1 class="mt-1 text-2xl font-bold text-foreground">
      {title}
    </h1>
    <p class="mt-1 text-sm text-foreground-muted">
      El precio sale de la lista del cliente. Los descuentos, impuestos y totales los calcula el
      servidor mientras editas.
      {isOrder
        ? 'Las existencias se apartan al confirmar el pedido.'
        : 'Cotizar no reserva existencias.'}
    </p>
  </header>

  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  {#if loading}
    <section class="space-y-3 rounded-xl border border-border bg-surface p-5" aria-busy="true">
      <div class="skeleton h-10 w-full rounded-md"></div>
      <div class="skeleton h-24 w-full rounded-md"></div>
      <div class="skeleton h-10 w-1/2 rounded-md"></div>
    </section>
  {:else}
    <form class="space-y-5" onsubmit={save}>
      <section
        class="grid gap-4 rounded-xl border border-border bg-surface p-5 sm:grid-cols-2 lg:grid-cols-3"
      >
        <label class="text-sm text-foreground-muted">
          Cliente
          <select
            class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
            value={customerId}
            onchange={(event) => {
              customerId = event.currentTarget.value;
              documentType = '';
            }}
            required
          >
            <option value="">Selecciona un cliente</option>
            {#each customers as item (item.id)}
              <option value={item.id}>{item.code} · {item.name}</option>
            {/each}
          </select>
          {#if customer?.price_list_name}
            <span class="mt-1 block text-xs">Lista: {customer.price_list_name}</span>
          {/if}
        </label>
        <label class="text-sm text-foreground-muted">
          Sucursal
          <select
            class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
            bind:value={branchId}
            required
          >
            <option value="">Selecciona una sucursal</option>
            {#each branches as item (item.id)}
              <option value={item.id}>{item.name}{item.code ? ` · ${item.code}` : ''}</option>
            {/each}
          </select>
        </label>
        <label class="text-sm text-foreground-muted">
          Documento a emitir
          <select
            class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
            bind:value={documentType}
          >
            <option value="">Según el cliente</option>
            {#each documents as code (code)}
              <option value={code}>{DOCUMENT_LABELS[code]}</option>
            {/each}
          </select>
        </label>
        {#if isOrder}
          <label class="text-sm text-foreground-muted">
            Fecha comprometida
            <input
              class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
              type="date"
              min={todayInElSalvador()}
              bind:value={promisedDate}
              required
            />
          </label>
          <label class="text-sm text-foreground-muted">
            Entrega
            <select
              class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
              bind:value={deliveryMode}
            >
              <option value="pickup">Retiro en sucursal</option>
              <option value="delivery">Entrega a domicilio</option>
            </select>
          </label>
          {#if deliveryMode === 'delivery'}
            <label class="text-sm text-foreground-muted">
              Dirección de entrega
              <select
                class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
                bind:value={addressId}
                required
              >
                <option value="">Selecciona una dirección</option>
                {#each addresses as item (item.id)}
                  <option value={item.id}>{item.label} · {item.address_line}</option>
                {/each}
              </select>
              {#if customer && addresses.length === 0}
                <span class="mt-1 block text-xs text-warning"
                  >El cliente no tiene direcciones de entrega. Agrégalas en su ficha.</span
                >
              {/if}
            </label>
          {/if}
        {:else}
          <label class="text-sm text-foreground-muted">
            Válida hasta
            <input
              class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
              type="date"
              bind:value={validUntil}
            />
            {#if !validUntil && validityDays}
              <span class="mt-1 block text-xs">Vacío: {validityDays} días desde hoy.</span>
            {/if}
          </label>
        {/if}
        <label class="text-sm text-foreground-muted">
          Descuento global (%)
          <input
            class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
            type="number"
            min="0"
            max="100"
            step="any"
            bind:value={globalDiscount}
          />
        </label>
        <label class="text-sm text-foreground-muted">
          Notas para el cliente (opcional)
          <input
            class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground"
            maxlength="4000"
            bind:value={notes}
          />
        </label>
      </section>

      <section class="overflow-hidden rounded-xl border border-border bg-surface">
        <div class="flex items-center justify-between gap-3 border-b border-border p-4">
          <div>
            <h2 class="font-semibold text-foreground">Productos</h2>
            <p class="mt-1 text-xs text-foreground-muted">
              Deja el descuento vacío para aplicar el sugerido (cliente o volumen).
            </p>
          </div>
          <button
            type="button"
            class="rounded-md border border-border px-3 py-2 text-sm text-foreground"
            onclick={() => (lines = [...lines, newLine()])}
          >
            Agregar producto
          </button>
        </div>
        {#if catalog.length === 0}
          <div class="flex flex-col items-center gap-2 p-8 text-center">
            <span
              class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
              aria-hidden="true">∅</span
            >
            <p class="text-sm text-foreground-muted">
              No hay productos vendibles con unidad e inventario configurados.
            </p>
            <a class="text-sm text-primary hover:underline" href="/products">Revisar productos</a>
          </div>
        {/if}
        <div class="divide-y divide-border">
          {#each lines as line, index (line.key)}
            {@const result = previewLine(index)}
            <div class="space-y-2 p-4">
              <div
                class="grid gap-3 md:items-end {canOverride
                  ? 'md:grid-cols-[minmax(200px,2fr)_minmax(150px,1.2fr)_100px_110px_130px_auto]'
                  : 'md:grid-cols-[minmax(200px,2fr)_minmax(150px,1.2fr)_100px_110px_auto]'}"
              >
                <label class="text-xs font-medium text-foreground-muted">
                  Producto
                  <select
                    class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                    value={line.option
                      ? `${line.option.product_id}:${line.option.variant_id ?? ''}`
                      : ''}
                    onchange={(event) => setOption(line, event.currentTarget.value)}
                    required
                  >
                    <option value="">Selecciona producto</option>
                    {#each catalog as item (`${item.product_id}:${item.variant_id ?? ''}`)}
                      <option value={`${item.product_id}:${item.variant_id ?? ''}`}
                        >{item.sku} · {item.name}</option
                      >
                    {/each}
                  </select>
                </label>
                <label class="text-xs font-medium text-foreground-muted">
                  Unidad
                  <select
                    class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                    bind:value={line.unitId}
                    disabled={!line.option}
                    required
                  >
                    <option value={null}>Selecciona unidad</option>
                    {#each line.option?.units ?? [] as unit (unit.unit_id)}
                      <option value={unit.unit_id}>{formatUnitLabel(unit.name)}</option>
                    {/each}
                  </select>
                </label>
                <label class="text-xs font-medium text-foreground-muted">
                  Cantidad
                  <input
                    class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                    type="number"
                    min="0"
                    step="any"
                    bind:value={line.quantity}
                    required
                  />
                </label>
                <label class="text-xs font-medium text-foreground-muted">
                  Descuento (%)
                  <input
                    class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                    type="number"
                    min="0"
                    max="100"
                    step="any"
                    placeholder={result
                      ? Number(result.suggested_discount_percent).toFixed(2)
                      : '0'}
                    bind:value={line.discount}
                  />
                </label>
                {#if canOverride}
                  <label class="text-xs font-medium text-foreground-muted">
                    Precio manual
                    <input
                      class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                      type="number"
                      min="0"
                      step="any"
                      placeholder="De la lista"
                      bind:value={line.manualPrice}
                    />
                  </label>
                {/if}
                <button
                  type="button"
                  class="h-10 rounded-md border border-border px-3 text-sm text-foreground-muted disabled:opacity-30"
                  aria-label={`Quitar producto ${index + 1}`}
                  disabled={lines.length <= 1}
                  onclick={() => removeLine(line.key)}
                >
                  Quitar
                </button>
              </div>
              {#if result}
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground-muted">
                  <span>Lista: {formatUnitPrice(result.list_price)}</span>
                  {#if result.price_overridden}<span class="text-warning"
                      >Precio manual: {formatUnitPrice(result.unit_price)}</span
                    >{/if}
                  <span>Descuento: {formatPercent(result.discount_percent)}</span>
                  {#if Number(result.suggested_discount_percent) > 0}
                    <span
                      >{SOURCE_LABELS[result.suggested_discount_source]}: {formatPercent(
                        result.suggested_discount_percent
                      )}</span
                    >
                  {/if}
                  {#if availableOf(index) !== null}
                    <span
                      class={Number(availableOf(index)) < Number(result.quantity_base)
                        ? 'text-warning'
                        : ''}
                      >Disponible en la sucursal: {formatQuantity(availableOf(index) ?? '0')}
                      {formatUnitLabel(result.base_unit_name)}</span
                    >
                  {/if}
                  {#if preview?.costs_visible && result.margin_percent !== null}
                    <span>Margen: {formatPercent(result.margin_percent)}</span>
                  {/if}
                  <span class="ml-auto font-mono font-semibold text-foreground"
                    >{formatMoney(result.line_total)}</span
                  >
                </div>
                {#each result.authorization_reasons as reason (reason.code)}
                  <p class="text-xs text-warning">{reason.message}</p>
                {/each}
              {/if}
            </div>
          {/each}
        </div>
      </section>

      <section class="rounded-xl border border-border bg-surface p-5" aria-live="polite">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-foreground">Resumen</h2>
          {#if calculating}<span class="text-xs text-foreground-muted">Calculando…</span>{/if}
        </div>
        {#if previewError}
          <div
            class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
          >
            {previewError}
          </div>
        {:else if preview}
          {#if preview.requires_authorization}
            <div
              class="mt-3 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
            >
              Al emitirla quedará <strong>Por autorizar</strong>:
              {preview.authorization_reasons
                .map((reason) => reason.message.toLowerCase())
                .join(' ')}
            </div>
          {/if}
          <dl
            class="mt-3 grid gap-x-6 gap-y-1 text-sm sm:ml-auto sm:max-w-sm sm:grid-cols-[1fr_auto]"
          >
            <dt class="text-foreground-muted">Documento</dt>
            <dd class="text-right text-foreground">{DOCUMENT_LABELS[preview.document_type]}</dd>
            <dt class="text-foreground-muted">Ventas gravadas</dt>
            <dd class="text-right font-mono text-foreground">{formatMoney(preview.total_taxed)}</dd>
            {#if Number(preview.total_exempt) > 0}
              <dt class="text-foreground-muted">Ventas exentas</dt>
              <dd class="text-right font-mono text-foreground">
                {formatMoney(preview.total_exempt)}
              </dd>
            {/if}
            {#if Number(preview.total_not_subject) > 0}
              <dt class="text-foreground-muted">Ventas no sujetas</dt>
              <dd class="text-right font-mono text-foreground">
                {formatMoney(preview.total_not_subject)}
              </dd>
            {/if}
            <dt class="text-foreground-muted">Descuentos</dt>
            <dd class="text-right font-mono text-foreground">
              {formatMoney(preview.total_discount)}
            </dd>
            <dt class="text-foreground-muted">
              {preview.document_type === '03' ? 'IVA 13 %' : 'IVA incluido'}
            </dt>
            <dd class="text-right font-mono text-foreground">{formatMoney(preview.vat)}</dd>
            {#if Number(preview.vat_perceived) > 0}
              <dt class="text-foreground-muted">IVA percibido</dt>
              <dd class="text-right font-mono text-foreground">
                {formatMoney(preview.vat_perceived)}
              </dd>
            {/if}
            {#if Number(preview.vat_withheld) > 0}
              <dt class="text-foreground-muted">IVA retenido</dt>
              <dd class="text-right font-mono text-foreground">
                −{formatMoney(preview.vat_withheld)}
              </dd>
            {/if}
            <dt class="border-t border-border pt-1 font-semibold text-foreground">Total</dt>
            <dd
              class="border-t border-border pt-1 text-right font-mono text-lg font-bold text-foreground"
            >
              {formatMoney(preview.total)}
            </dd>
          </dl>
          <p class="mt-2 text-right text-xs text-foreground-muted">{preview.total_in_words}</p>
        {:else}
          <p class="mt-3 text-sm text-foreground-muted">
            Elige cliente, sucursal y productos para ver precios, impuestos y total.
          </p>
        {/if}
      </section>

      <div class="flex flex-wrap justify-end gap-2">
        <a
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
          href={documentId ? `${listPath}/${documentId}` : listPath}
        >
          Cancelar
        </a>
        <button
          class="rounded-md bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={saving || customers.length === 0 || catalog.length === 0}
        >
          {saving ? 'Guardando…' : 'Guardar borrador'}
        </button>
      </div>
    </form>
  {/if}
</div>
