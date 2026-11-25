<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalBooksApi } from '#lib/api/fiscal-books.ts';
  import {
    DOCUMENT_TYPES,
    PURCHASE_CLASSES,
    RENTA_FIELDS,
    SUPPLIER_ID_LABELS
  } from '#lib/features/fiscal-books/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type {
    PurchaseDocumentClass,
    PurchaseDocumentType,
    PurchaseFiscal,
    PurchaseFiscalInput,
    RentaPurchase,
    SupplierIdType
  } from '#lib/types/fiscal-books.ts';

  let {
    purchaseId,
    canManage,
    onSaved
  }: {
    purchaseId: string;
    canManage: boolean;
    onSaved?: (purchase: PurchaseFiscal) => void;
  } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let purchase = $state<PurchaseFiscal | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let editing = $state(false);
  let busy = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  let issuedOn = $state('');
  let documentClass = $state<PurchaseDocumentClass>(4);
  let documentType = $state<PurchaseDocumentType>('03');
  let number = $state('');
  let controlNumber = $state('');
  let seal = $state('');
  let supplierName = $state('');
  let supplierIdType = $state<SupplierIdType>('nit');
  let supplierId = $state('');
  let renta = $state<RentaPurchase>({ operation: 1, classification: 1, sector: 2, cost_type: 5 });

  const types = $derived(
    PURCHASE_CLASSES.find((item) => item.value === documentClass)?.types ?? []
  );
  const isDte = $derived(documentClass === 4);
  const complete = $derived(
    Boolean(issuedOn && number.trim() && supplierName.trim() && supplierId.trim()) &&
      (!isDte || Boolean(controlNumber.trim() && seal.trim()))
  );

  function fill(view: PurchaseFiscal) {
    const recorded = view.recorded;
    issuedOn = recorded?.issued_on ?? view.invoice_date ?? '';
    documentClass = recorded?.document_class ?? 4;
    documentType = recorded?.document_type ?? '03';
    number = recorded?.number ?? '';
    controlNumber = recorded?.control_number ?? '';
    seal = recorded?.seal ?? '';
    supplierName = recorded?.supplier_name ?? view.supplier_name;
    const known = (['nit', 'nrc', 'dui'] as SupplierIdType[]).find(
      (kind) => view.supplier_ids[kind]
    );
    supplierIdType = recorded?.supplier_id_type ?? known ?? 'nit';
    supplierId = recorded?.supplier_id ?? (known ? (view.supplier_ids[known] ?? '') : '');
    renta = { ...(recorded?.renta ?? view.renta_defaults) };
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      purchase = await fiscalBooksApi.purchase(purchaseId);
      fill(purchase);
    } catch (cause) {
      loadError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudo cargar el documento del proveedor.';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  function changeClass(value: PurchaseDocumentClass) {
    documentClass = value;
    const allowed = PURCHASE_CLASSES.find((item) => item.value === value)?.types ?? [];
    if (!allowed.includes(documentType)) documentType = allowed[0] ?? '03';
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (!complete || busy) return;
    busy = true;
    formError = null;
    notice = null;
    const payload: PurchaseFiscalInput = {
      issued_on: issuedOn,
      document_class: documentClass,
      document_type: documentType,
      number: number.trim(),
      control_number: isDte ? controlNumber.trim() : null,
      seal: isDte ? seal.trim() : null,
      supplier_name: supplierName.trim(),
      supplier_id_type: supplierIdType,
      supplier_id: supplierId.trim(),
      renta
    };
    try {
      purchase = await fiscalBooksApi.recordPurchase(purchaseId, payload);
      fill(purchase);
      editing = false;
      notice = 'Se guardó el documento del proveedor; la compra ya entra al libro de compras.';
      onSaved?.(purchase);
    } catch (cause) {
      formError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudo guardar el documento del proveedor.';
    } finally {
      busy = false;
    }
  }
</script>

<section
  class="space-y-4 rounded-xl border border-border bg-surface p-4"
  aria-label="Documento del proveedor"
>
  <div>
    <h2 class="font-semibold text-foreground">Documento del proveedor</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      El crédito fiscal, la nota o la declaración de mercancías que respalda la compra. Con él, la
      compra entra al libro de compras y al anexo 3 del F-07 del mes de su fecha.
    </p>
  </div>

  {#if loading}
    <div class="space-y-2" aria-hidden="true">
      <div class="skeleton h-4 w-2/3 rounded"></div>
      <div class="skeleton h-10 w-full rounded"></div>
    </div>
  {:else if loadError}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      role="alert"
    >
      {loadError}
    </div>
  {:else if purchase}
    {#if notice}
      <p class="text-sm text-success" role="status">{notice}</p>
    {/if}
    <dl class="grid grid-cols-3 gap-3 text-sm">
      <div>
        <dt class="text-foreground-muted">Gravado</dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">{formatMoney(purchase.taxed)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Exento</dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">
          {formatMoney(purchase.exempt)}
        </dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Crédito fiscal</dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">{formatMoney(purchase.vat)}</dd>
      </div>
    </dl>

    {#if purchase.recorded && !editing}
      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-foreground-muted">Documento</dt>
          <dd class="mt-1 text-foreground">
            {DOCUMENT_TYPES[purchase.recorded.document_type]} · {purchase.recorded.number}
          </dd>
        </div>
        <div>
          <dt class="text-foreground-muted">Fecha</dt>
          <dd class="mt-1 text-foreground">{formatDay(purchase.recorded.issued_on)}</dd>
        </div>
        <div>
          <dt class="text-foreground-muted">Proveedor</dt>
          <dd class="mt-1 text-foreground">
            {purchase.recorded.supplier_name} · {purchase.recorded.supplier_id_type.toUpperCase()}
            {purchase.recorded.supplier_id}
          </dd>
        </div>
        {#if purchase.recorded.control_number}
          <div>
            <dt class="text-foreground-muted">Número de control</dt>
            <dd class="mt-1 break-all text-foreground">{purchase.recorded.control_number}</dd>
          </div>
        {/if}
      </dl>
      {#if canManage}
        <Button variant="secondary" size="sm" onclick={() => (editing = true)}>
          Corregir documento
        </Button>
      {/if}
    {:else if !canManage}
      <p class="text-sm text-foreground-muted">
        Esta compra todavía no tiene registrado el documento del proveedor.
      </p>
    {:else}
      <form class="space-y-4" onsubmit={save}>
        <div class="grid gap-3 sm:grid-cols-3">
          <label class="space-y-1 text-sm text-foreground-muted"
            >Clase de documento
            <select
              class={inputClass}
              value={documentClass}
              onchange={(event) =>
                changeClass(Number(event.currentTarget.value) as PurchaseDocumentClass)}
            >
              {#each PURCHASE_CLASSES as item (item.value)}
                <option value={item.value}>{item.label}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Tipo de documento
            <select class={inputClass} bind:value={documentType}>
              {#each types as code (code)}
                <option value={code}>{DOCUMENT_TYPES[code]}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Fecha del documento
            <input class={inputClass} type="date" bind:value={issuedOn} required />
          </label>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="space-y-1 text-sm text-foreground-muted"
            >{isDte ? 'Código de generación' : 'Número del documento'}
            <input
              class={inputClass}
              bind:value={number}
              maxlength="100"
              placeholder={isDte ? '6C7EF177-8C52-41EF-B073-B2968DA0652C' : '145501'}
              required
            />
          </label>
          {#if isDte}
            <label class="space-y-1 text-sm text-foreground-muted"
              >Número de control
              <input
                class={inputClass}
                bind:value={controlNumber}
                maxlength="31"
                placeholder="DTE-03-M001P001-000000000000001"
                required
              />
            </label>
            <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
              >Sello de recepción
              <input class={inputClass} bind:value={seal} maxlength="100" required />
            </label>
          {/if}
        </div>
        <div class="grid gap-3 sm:grid-cols-3">
          <label class="space-y-1 text-sm text-foreground-muted sm:col-span-3"
            >Nombre del proveedor en el documento
            <input class={inputClass} bind:value={supplierName} maxlength="250" required />
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Identificación
            <select class={inputClass} bind:value={supplierIdType}>
              {#each Object.entries(SUPPLIER_ID_LABELS) as [value, label] (value)}
                <option {value}>{label}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
            >Número de identificación
            <input class={inputClass} bind:value={supplierId} maxlength="20" required />
          </label>
        </div>
        <fieldset class="grid gap-3 sm:grid-cols-2">
          <legend class="mb-2 text-sm font-medium text-foreground">Clasificación de renta</legend>
          {#each RENTA_FIELDS as field (field.key)}
            <label class="space-y-1 text-sm text-foreground-muted"
              >{field.label}
              <select
                class={inputClass}
                value={renta[field.key]}
                onchange={(event) =>
                  (renta = { ...renta, [field.key]: Number(event.currentTarget.value) })}
              >
                {#each Object.entries(field.options) as [value, label] (value)}
                  <option {value}>{value} · {label}</option>
                {/each}
              </select>
            </label>
          {/each}
        </fieldset>
        {#if formError}
          <div
            class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
            role="alert"
          >
            {formError}
          </div>
        {/if}
        <div class="flex flex-wrap gap-2">
          <Button type="submit" disabled={!complete || busy}>
            {busy ? 'Guardando…' : 'Guardar documento'}
          </Button>
          {#if purchase.recorded}
            <Button
              variant="ghost"
              onclick={() => {
                if (purchase) fill(purchase);
                editing = false;
              }}>Cancelar</Button
            >
          {/if}
        </div>
      </form>
    {/if}
  {/if}
</section>
