<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import AsyncSmartSelect, {
    type AsyncSmartOption
  } from '$lib/components/ui/AsyncSmartSelect.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { customersApi } from '$lib/api/customers';
  import { fiscalApi } from '$lib/api/fiscal';
  import CustomerDeliveryAddresses from '$lib/features/customers/components/CustomerDeliveryAddresses.svelte';
  import GeographyFields from '$lib/features/customers/components/GeographyFields.svelte';
  import {
    CUSTOMER_TYPE_LABELS,
    DOCUMENTS_BY_TYPE,
    IDENTITY_DOCUMENT_LABELS,
    RECEIVABLE_DOCUMENT_LABELS,
    customerToInput,
    emptyCustomerInput,
    switchCustomerType
  } from '$lib/features/customers/labels';
  import { PERSON_TYPE_LABELS, TAXPAYER_CATEGORY_LABELS } from '$lib/features/fiscal/labels';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Customer, CustomerInput, CustomerType } from '$lib/types/customer';

  let { customerId = null }: { customerId?: string | null } = $props();

  const TYPES: CustomerType[] = ['final_consumer', 'taxpayer', 'foreign'];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let customer = $state<Customer | null>(null);
  let form = $state<CustomerInput>(emptyCustomerInput());
  let code = $state('');
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let saved = $state<string | null>(null);
  let geographyKey = $state(0);

  const canManage = $derived(permissions.hasPermission('sales_customers:manage'));
  const editable = $derived(canManage && !customer?.is_generic);
  const isTaxpayer = $derived(form.customer_type === 'taxpayer');
  const isForeign = $derived(form.customer_type === 'foreign');

  function text(value: string | null): string {
    return value ?? '';
  }

  function nullable(value: string): string | null {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  async function load() {
    if (!customerId) return;
    loading = true;
    loadError = null;
    try {
      customer = await customersApi.get(customerId);
      form = customerToInput(customer);
      geographyKey += 1;
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo cargar el cliente.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (customerId) void load();
    else loading = false;
  });

  function changeType(type: CustomerType) {
    form = switchCustomerType(form, type);
    geographyKey += 1;
  }

  async function searchCatalog(catalog: string, query: string): Promise<AsyncSmartOption[]> {
    const items = await fiscalApi.catalog(catalog, { search: query.trim(), limit: 30 });
    return items.map((item) => ({ value: item.code, label: `${item.code} · ${item.name}` }));
  }

  async function searchSellers(query: string): Promise<AsyncSmartOption[]> {
    const items = await customersApi.sellerOptions(query);
    return items.map((item) => ({
      value: item.id,
      label: item.name,
      description: [item.code, item.position].filter(Boolean).join(' · ')
    }));
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!editable) return;
    saving = true;
    formError = null;
    saved = null;
    try {
      if (customer) {
        customer = await customersApi.update(customer.id, form);
        form = customerToInput(customer);
        saved = 'Se guardaron los cambios del cliente.';
      } else {
        const created = await customersApi.create({ ...form, code: nullable(code) });
        await goto(`/customers/${created.id}`, { replaceState: true });
      }
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar el cliente.';
    } finally {
      saving = false;
    }
  }

  function toggleActive() {
    if (!customer) return;
    const current = customer;
    const activating = !current.is_active;
    confirmation.request({
      kind: activating ? 'restore' : 'deactivate',
      title: activating ? 'Reactivar cliente' : 'Desactivar cliente',
      description: activating
        ? 'Volverá a estar disponible para cotizaciones y ventas.'
        : 'No se le podrá vender ni cotizar. Sus documentos anteriores se conservan.',
      resourceName: current.name,
      confirmLabel: activating ? 'Reactivar' : 'Desactivar',
      execute: async () => {
        customer = await customersApi.setActive(current.id, activating);
      }
    });
  }
</script>

<svelte:head>
  <title>{customer ? customer.name : 'Nuevo cliente'} | GestionaSV</title>
</svelte:head>

<div class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div class="min-w-0">
      <a href="/customers" class="text-xs font-semibold uppercase tracking-wider text-primary">
        ← Clientes
      </a>
      <h1 class="mt-1 break-words text-2xl font-bold tracking-tight text-foreground">
        {customer ? customer.name : 'Nuevo cliente'}
      </h1>
      {#if customer}
        <p class="font-mono text-xs text-foreground-muted">{customer.code}</p>
      {/if}
    </div>
    {#if customer && editable}
      <Button variant={customer.is_active ? 'ghost' : 'secondary'} onclick={toggleActive}>
        {customer.is_active ? 'Desactivar' : 'Reactivar'}
      </Button>
    {/if}
  </header>

  {#if loading}
    <div class="space-y-3" aria-busy="true">
      <p class="sr-only" role="status">Cargando el cliente…</p>
      <div class="skeleton h-28 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
      <div class="skeleton h-72 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else}
    {#if customer}
      <section
        class="rounded-xl border border-border bg-surface-elevated p-4"
        aria-label="Documentos que puede recibir"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-sm font-medium text-foreground">Puede recibir:</span>
          {#each customer.receivable_documents as doc (doc)}
            <Badge variant={doc === '03' ? 'success' : 'neutral'}>
              {RECEIVABLE_DOCUMENT_LABELS[doc] ?? doc}
            </Badge>
          {/each}
          {#if !customer.is_active}<Badge variant="danger">Inactivo</Badge>{/if}
        </div>
        {#if customer.customer_type === 'taxpayer' && customer.tax_credit_missing.length > 0}
          <div class="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
            <p class="font-medium text-foreground">Para emitirle crédito fiscal falta:</p>
            <ul class="mt-1 list-disc pl-5 text-foreground-muted">
              {#each customer.tax_credit_missing as reason (reason)}
                <li>{reason}</li>
              {/each}
            </ul>
          </div>
        {/if}
        {#if customer.is_generic}
          <p class="mt-3 text-sm text-foreground-muted">
            Cliente genérico de la sucursal para ventas de mostrador sin identificar. Sus datos no
            se editan.
          </p>
        {/if}
      </section>
    {/if}

    {#if saved}
      <p
        class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success"
        role="status"
      >
        {saved}
      </p>
    {/if}

    <form class="space-y-5" onsubmit={submit}>
      {#if formError}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {formError}
        </p>
      {/if}

      <fieldset
        class="space-y-4 rounded-xl border border-border bg-surface-elevated p-4"
        disabled={!editable}
      >
        <legend class="px-1 text-sm font-semibold text-foreground">Identidad fiscal</legend>
        <div class="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Tipo de cliente">
          {#each TYPES as type (type)}
            <label
              class="flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm {form.customer_type ===
              type
                ? 'border-primary bg-primary/5'
                : 'border-border hover:bg-surface-muted/50'}"
            >
              <input
                type="radio"
                name="customer-type"
                aria-label={CUSTOMER_TYPE_LABELS[type]}
                checked={form.customer_type === type}
                onchange={() => changeType(type)}
              />
              {CUSTOMER_TYPE_LABELS[type]}
            </label>
          {/each}
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          {#if !customer}
            <div>
              <label for="customer-code" class={labelClass}>Código</label>
              <input
                id="customer-code"
                bind:value={code}
                maxlength="40"
                placeholder="Se asigna solo si lo dejas vacío"
                class="{inputClass} uppercase"
              />
            </div>
          {/if}
          <div class={customer ? 'md:col-span-2' : ''}>
            <label for="customer-name" class={labelClass}>Nombre o razón social</label>
            <input
              id="customer-name"
              bind:value={form.name}
              required
              minlength="2"
              maxlength="200"
              class={inputClass}
            />
          </div>
          <div>
            <label for="customer-commercial" class={labelClass}>Nombre comercial</label>
            <input
              id="customer-commercial"
              value={text(form.commercial_name)}
              oninput={(e) => (form.commercial_name = nullable(e.currentTarget.value))}
              maxlength="200"
              class={inputClass}
            />
          </div>
          <div>
            <label for="customer-person" class={labelClass}>Tipo de persona</label>
            <select id="customer-person" bind:value={form.person_type} class={inputClass}>
              {#each Object.entries(PERSON_TYPE_LABELS) as [value, label] (value)}
                <option {value}>{label}</option>
              {/each}
            </select>
          </div>
          {#if isTaxpayer}
            <div>
              <label for="customer-category" class={labelClass}>Categoría de contribuyente</label>
              <select id="customer-category" bind:value={form.taxpayer_category} class={inputClass}>
                {#each Object.entries(TAXPAYER_CATEGORY_LABELS) as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
            </div>
          {/if}
          <div>
            <label for="customer-document-type" class={labelClass}>Documento de identidad</label>
            <select
              id="customer-document-type"
              value={form.document_type ?? ''}
              onchange={(e) => {
                const next = e.currentTarget.value;
                form.document_type = next ? (next as CustomerInput['document_type']) : null;
                if (!next) form.document_number = null;
              }}
              class={inputClass}
            >
              <option value="">{isTaxpayer ? 'Selecciona…' : 'Sin documento'}</option>
              {#each DOCUMENTS_BY_TYPE[form.customer_type] as doc (doc)}
                <option value={doc}>{IDENTITY_DOCUMENT_LABELS[doc]}</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="customer-document-number" class={labelClass}>Número de documento</label>
            <input
              id="customer-document-number"
              value={text(form.document_number)}
              oninput={(e) => (form.document_number = nullable(e.currentTarget.value))}
              disabled={!form.document_type}
              required={Boolean(form.document_type)}
              maxlength="30"
              placeholder={form.document_type === '36' ? '0614-010101-101-1' : ''}
              class="{inputClass} font-mono"
            />
          </div>
          {#if !isForeign}
            <div>
              <label for="customer-nrc" class={labelClass}>NRC</label>
              <input
                id="customer-nrc"
                value={text(form.nrc)}
                oninput={(e) => (form.nrc = nullable(e.currentTarget.value))}
                maxlength="12"
                placeholder="123456-7"
                class="{inputClass} font-mono"
              />
            </div>
          {/if}
          <div class="md:col-span-2">
            <AsyncSmartSelect
              id="customer-activity"
              label="Actividad económica"
              value={form.activity_code ?? ''}
              selectedLabel={customer?.activity_code &&
              customer.activity_code === form.activity_code
                ? `${customer.activity_code} · ${customer.activity_name ?? ''}`
                : (form.activity_code ?? '')}
              placeholder="Buscar en el catálogo de Hacienda…"
              disabled={!editable}
              onselect={(value) => (form.activity_code = value || null)}
              loadOptions={(query) => searchCatalog('CAT-019', query)}
            />
          </div>
          {#if isTaxpayer}
            <label class="flex min-h-11 items-center gap-2 text-sm text-foreground md:col-span-2">
              <input type="checkbox" bind:checked={form.is_withholding_agent} />
              Es agente de retención de IVA (retiene el 1 % al pagar)
            </label>
          {/if}
        </div>
      </fieldset>

      <fieldset
        class="space-y-4 rounded-xl border border-border bg-surface-elevated p-4"
        disabled={!editable}
      >
        <legend class="px-1 text-sm font-semibold text-foreground">Dirección</legend>
        {#if isForeign}
          <AsyncSmartSelect
            id="customer-country"
            label="País"
            value={form.country_code ?? ''}
            selectedLabel={customer?.country_code && customer.country_code === form.country_code
              ? `${customer.country_code} · ${customer.country_name ?? ''}`
              : (form.country_code ?? '')}
            placeholder="Buscar país…"
            disabled={!editable}
            onselect={(value) => (form.country_code = value || null)}
            loadOptions={(query) => searchCatalog('CAT-020', query)}
          />
        {:else}
          {#key geographyKey}
            <GeographyFields
              idPrefix="customer"
              value={form.geography}
              disabled={!editable}
              required={isTaxpayer}
              onchange={(value) => (form.geography = value)}
            />
          {/key}
        {/if}
        <div>
          <label for="customer-address" class={labelClass}>
            {isForeign ? 'Dirección en el extranjero' : 'Dirección (calle, número, colonia)'}
          </label>
          <input
            id="customer-address"
            value={text(form.address_line)}
            oninput={(e) => (form.address_line = nullable(e.currentTarget.value))}
            maxlength="200"
            class={inputClass}
          />
        </div>
      </fieldset>

      <fieldset
        class="grid gap-4 rounded-xl border border-border bg-surface-elevated p-4 md:grid-cols-2"
        disabled={!editable}
      >
        <legend class="px-1 text-sm font-semibold text-foreground">Contacto y condiciones</legend>
        <div>
          <label for="customer-email" class={labelClass}>Correo para recibir documentos</label>
          <input
            id="customer-email"
            type="email"
            value={text(form.email)}
            oninput={(e) => (form.email = nullable(e.currentTarget.value))}
            maxlength="100"
            class={inputClass}
          />
        </div>
        <div>
          <label for="customer-phone" class={labelClass}>Teléfono</label>
          <input
            id="customer-phone"
            value={text(form.phone)}
            oninput={(e) => (form.phone = nullable(e.currentTarget.value))}
            maxlength="30"
            class={inputClass}
          />
        </div>
        <div>
          <label for="customer-credit-days" class={labelClass}>Plazo de crédito (días)</label>
          <input
            id="customer-credit-days"
            type="number"
            min="0"
            max="365"
            step="1"
            bind:value={form.credit_days}
            class={inputClass}
          />
          <p class="mt-1 text-xs text-foreground-muted">0 significa venta de contado.</p>
        </div>
        <div class="md:col-span-2">
          <AsyncSmartSelect
            id="customer-seller"
            label="Vendedor asignado"
            value={form.seller_employee_id ?? ''}
            selectedLabel={customer?.seller_employee_id &&
            customer.seller_employee_id === form.seller_employee_id
              ? (customer.seller_name ?? '')
              : ''}
            placeholder="Buscar empleado por nombre o código…"
            disabled={!editable}
            onselect={(value) => (form.seller_employee_id = value || null)}
            loadOptions={searchSellers}
          />
        </div>
        <div>
          <label for="customer-credit-limit" class={labelClass}>Límite de crédito (USD)</label>
          <input
            id="customer-credit-limit"
            type="number"
            min="0"
            step="0.01"
            value={text(form.credit_limit)}
            oninput={(e) => (form.credit_limit = nullable(e.currentTarget.value))}
            placeholder="Sin límite"
            class={inputClass}
          />
        </div>
      </fieldset>

      {#if editable}
        <div class="flex justify-end gap-2">
          <a
            href="/customers"
            class="inline-flex h-11 items-center rounded-md px-4 text-sm text-foreground hover:bg-surface-muted"
          >
            Cancelar
          </a>
          <Button type="submit" disabled={saving}>
            {saving ? 'Guardando…' : customer ? 'Guardar cambios' : 'Registrar cliente'}
          </Button>
        </div>
      {/if}
    </form>

    {#if customer && !customer.is_generic}
      <CustomerDeliveryAddresses
        customerId={customer.id}
        addresses={customer.delivery_addresses}
        canManage={editable}
        onchange={() => void load()}
      />
    {/if}
  {/if}
</div>
