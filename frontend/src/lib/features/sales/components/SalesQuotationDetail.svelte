<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError, apiDownload } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import { formatUnitLabel } from '#lib/features/sales/unit-label.ts';
  import {
    DOCUMENT_LABELS,
    TREATMENT_LABELS,
    formatDay,
    formatMoney,
    formatPercent,
    formatQuantity,
    formatUnitPrice,
    statusBadge,
    statusLabel
  } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import { customersApi } from '#lib/api/customers.ts';
  import { todayInElSalvador } from '#lib/features/price-lists/labels.ts';
  import type { DeliveryAddress } from '#lib/types/customer.ts';
  import type { SalesQuotation } from '#lib/types/sales.ts';

  type Action = 'issue' | 'authorize' | 'return' | 'accept' | 'reject' | 'cancel';

  let { id }: { id: string } = $props();
  let quote = $state<SalesQuotation | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let text = $state('');
  let pending = $state<Action | null>(null);
  let generation = 0;
  onDestroy(() => generation++);

  const branchName = $derived(
    quote ? (branch.branches.find((item) => item.id === quote?.branch_id)?.name ?? '') : ''
  );
  const can = (code: string) => permissions.hasPermission(code);

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesApi.quotation(id);
      if (generation === current) quote = response;
    } catch (cause) {
      if (generation === current) {
        error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la cotización.';
      }
    } finally {
      if (generation === current) loading = false;
    }
  }
  onMount(() => void load());

  const prompts: Record<
    'authorize' | 'return' | 'reject' | 'cancel',
    { label: string; required: boolean; button: string }
  > = {
    authorize: {
      label: 'Nota de la autorización (opcional)',
      required: false,
      button: 'Autorizar y emitir'
    },
    return: { label: 'Qué debe corregirse', required: true, button: 'Devolver a borrador' },
    reject: { label: 'Por qué la rechazó el cliente', required: true, button: 'Registrar rechazo' },
    cancel: { label: 'Motivo de la cancelación', required: true, button: 'Cancelar cotización' }
  };

  async function run(action: Action) {
    if (!quote || busy) return;
    const prompt = action === 'issue' || action === 'accept' ? null : prompts[action];
    if (prompt?.required && text.trim().length < 3) {
      error = `${prompt.label}: escribe al menos 3 caracteres.`;
      return;
    }
    busy = true;
    error = null;
    try {
      quote = await salesApi.quotationAction(quote.id, action, {
        expected_version: quote.version,
        ...(action === 'authorize' ? { note: text.trim() || null } : {}),
        ...(prompt?.required ? { reason: text.trim() } : {})
      });
      text = '';
      pending = null;
    } catch (cause) {
      error =
        cause instanceof HttpError ? cause.message : 'No se pudo completar la acción. Recarga.';
    } finally {
      busy = false;
    }
  }

  let ordering = $state(false);
  let promisedDate = $state(todayInElSalvador());
  let deliveryMode = $state<'pickup' | 'delivery'>('pickup');
  let addressId = $state('');
  let addresses = $state<DeliveryAddress[]>([]);

  async function startOrder() {
    if (!quote) return;
    ordering = true;
    try {
      const customer = await customersApi.get(quote.customer_id);
      addresses = customer.delivery_addresses.filter((item) => item.is_active);
    } catch {
      addresses = [];
    }
  }

  async function createOrder(event: SubmitEvent) {
    event.preventDefault();
    if (!quote) return;
    busy = true;
    error = null;
    const storageKey = `sales-order-from:${quote.id}`;
    let key = sessionStorage.getItem(storageKey);
    if (!key) {
      key = crypto.randomUUID();
      sessionStorage.setItem(storageKey, key);
    }
    try {
      const order = await salesApi.orderFromQuotation(
        quote.id,
        {
          promised_date: promisedDate,
          delivery_mode: deliveryMode,
          delivery_address_id: deliveryMode === 'delivery' ? addressId : null
        },
        key
      );
      sessionStorage.removeItem(storageKey);
      await goto(`/sales/${order.id}`);
    } catch (cause) {
      error =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudo crear el pedido. Puedes reintentar.';
    } finally {
      busy = false;
    }
  }

  async function openPdf() {
    if (!quote) return;
    error = null;
    try {
      const blob = await apiDownload(salesApi.quotationPdfPath(quote.id));
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo generar el PDF.';
    }
  }
</script>

<svelte:head
  ><title>{quote ? `Cotización ${quote.code}` : 'Cotización de venta'} | GestionaSV</title
  ></svelte:head
>

<div class="space-y-5">
  <a class="text-sm text-primary hover:underline" href="/sales/quotations"
    >← Cotizaciones de venta</a
  >
  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
      <button class="ml-3 underline" onclick={() => void load()}>Recargar</button>
    </div>
  {/if}

  {#if loading}
    <section class="space-y-3 rounded-xl border border-border bg-surface p-5" aria-busy="true">
      <div class="skeleton h-8 w-1/3 rounded-md"></div>
      <div class="skeleton h-24 w-full rounded-md"></div>
      <div class="skeleton h-40 w-full rounded-md"></div>
    </section>
  {:else if quote}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">
          Cotización · {quote.code} · {DOCUMENT_LABELS[quote.document_type]}
        </p>
        <h1 class="mt-1 text-2xl font-bold text-foreground">{quote.customer_name}</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {quote.customer_code} · {formatDay(quote.quotation_date)} · válida hasta {formatDay(
            quote.valid_until
          )}
          {#if branchName}· {branchName}{/if}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class={`w-fit rounded-full px-3 py-1 text-sm ${statusBadge(quote)}`}
          >{statusLabel(quote)}</span
        >
        <button
          class="rounded-md border border-border px-3 py-1.5 text-sm text-foreground"
          onclick={() => void openPdf()}
        >
          Ver PDF
        </button>
      </div>
    </header>

    {#if quote.status === 'pending_authorization'}
      <section
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
      >
        <p class="font-semibold">Espera autorización</p>
        <ul class="mt-1 list-disc pl-5">
          {#each quote.authorization_reasons as reason (reason.code)}<li>
              {reason.message}
            </li>{/each}
        </ul>
      </section>
    {:else if quote.status === 'draft' && quote.authorization_note}
      <section
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
      >
        Devuelta por quien autoriza: {quote.authorization_note}
      </section>
    {/if}
    {#if quote.expired}
      <section
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
      >
        La vigencia pasó: ya no se puede aceptar. Puedes registrar el rechazo o cancelarla.
      </section>
    {/if}

    <section class="overflow-hidden rounded-xl border border-border bg-surface">
      <div class="border-b border-border p-4">
        <h2 class="font-semibold text-foreground">Productos</h2>
        <p class="mt-1 text-xs text-foreground-muted">
          Lista: {quote.price_list_name ?? 'sin lista'} · precios {quote.prices_include_vat
            ? 'con'
            : 'sin'} IVA. Los precios y costos quedaron guardados al calcular.
        </p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[780px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr>
              <th class="px-4 py-3">Producto</th>
              <th class="px-4 py-3">Cantidad</th>
              <th class="px-4 py-3 text-right">Precio</th>
              <th class="px-4 py-3 text-right">Descuento</th>
              {#if quote.costs_visible}<th class="px-4 py-3 text-right">Costo / margen</th>{/if}
              <th class="px-4 py-3 text-right">Total</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each quote.lines as line (line.line_number)}
              <tr>
                <td class="px-4 py-3">
                  <p class="font-medium text-foreground">{line.product_name}</p>
                  <p class="font-mono text-xs text-foreground-muted">
                    {line.product_sku}{line.tax_treatment !== 'taxed'
                      ? ` · ${TREATMENT_LABELS[line.tax_treatment]}`
                      : ''}
                  </p>
                  {#each line.authorization_reasons as reason (reason.code)}
                    <p class="text-xs text-warning">{reason.message}</p>
                  {/each}
                </td>
                <td class="px-4 py-3 text-foreground"
                  >{formatQuantity(line.quantity)} {formatUnitLabel(line.unit_name)}</td
                >
                <td class="px-4 py-3 text-right font-mono text-foreground">
                  {formatUnitPrice(line.document_unit_price)}
                  {#if line.price_overridden}
                    <p class="text-xs text-warning">
                      Manual · lista {formatUnitPrice(line.list_price)}
                    </p>
                  {/if}
                </td>
                <td class="px-4 py-3 text-right font-mono text-foreground">
                  {Number(line.discount_percent) > 0 ? formatPercent(line.discount_percent) : '—'}
                </td>
                {#if quote.costs_visible}
                  <td class="px-4 py-3 text-right font-mono text-foreground-muted">
                    {formatUnitPrice(line.cost)} · {formatPercent(line.margin_percent)}
                  </td>
                {/if}
                <td class="px-4 py-3 text-right font-mono font-semibold text-foreground"
                  >{formatMoney(line.line_total)}</td
                >
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <dl
        class="grid gap-x-6 gap-y-1 border-t border-border p-4 text-sm sm:ml-auto sm:max-w-sm sm:grid-cols-[1fr_auto]"
      >
        <dt class="text-foreground-muted">Ventas gravadas</dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(quote.total_taxed)}</dd>
        {#if Number(quote.total_exempt) > 0}
          <dt class="text-foreground-muted">Ventas exentas</dt>
          <dd class="text-right font-mono text-foreground">{formatMoney(quote.total_exempt)}</dd>
        {/if}
        {#if Number(quote.total_not_subject) > 0}
          <dt class="text-foreground-muted">Ventas no sujetas</dt>
          <dd class="text-right font-mono text-foreground">
            {formatMoney(quote.total_not_subject)}
          </dd>
        {/if}
        <dt class="text-foreground-muted">
          Descuentos{Number(quote.global_discount_percent) > 0
            ? ` (global ${formatPercent(quote.global_discount_percent)})`
            : ''}
        </dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(quote.total_discount)}</dd>
        <dt class="text-foreground-muted">
          {quote.document_type === '03' ? 'IVA 13 %' : 'IVA incluido'}
        </dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(quote.vat)}</dd>
        {#if Number(quote.vat_perceived) > 0}
          <dt class="text-foreground-muted">IVA percibido</dt>
          <dd class="text-right font-mono text-foreground">{formatMoney(quote.vat_perceived)}</dd>
        {/if}
        {#if Number(quote.vat_withheld) > 0}
          <dt class="text-foreground-muted">IVA retenido</dt>
          <dd class="text-right font-mono text-foreground">−{formatMoney(quote.vat_withheld)}</dd>
        {/if}
        <dt class="border-t border-border pt-1 font-semibold text-foreground">Total</dt>
        <dd
          class="border-t border-border pt-1 text-right font-mono text-lg font-bold text-foreground"
        >
          {formatMoney(quote.total)}
        </dd>
      </dl>
      <p class="px-4 pb-4 text-right text-xs text-foreground-muted">{quote.total_in_words}</p>
    </section>

    {#if quote.notes}
      <section class="rounded-xl border border-border bg-surface p-4">
        <h2 class="font-semibold text-foreground">Notas</h2>
        <p class="mt-2 whitespace-pre-wrap text-sm text-foreground-muted">{quote.notes}</p>
      </section>
    {/if}

    <section class="rounded-xl border border-border bg-surface p-4 text-sm text-foreground-muted">
      <h2 class="font-semibold text-foreground">Historial</h2>
      <ul class="mt-2 space-y-1">
        <li>Creada por {quote.created_by_name ?? '—'}</li>
        {#if quote.authorized_at}<li>
            Autorizada por {quote.authorized_by_name} el {formatDay(
              quote.authorized_at
            )}{quote.authorization_note ? ` · ${quote.authorization_note}` : ''}
          </li>{/if}
        {#if quote.issued_at}<li>
            Emitida por {quote.issued_by_name} el {formatDay(quote.issued_at)}
          </li>{/if}
        {#if quote.customer_response_at}
          <li>
            {quote.status === 'rejected' ? 'Rechazo registrado' : 'Aceptación registrada'} por {quote.customer_response_by_name}
            el {formatDay(quote.customer_response_at)}{quote.rejection_reason
              ? ` · ${quote.rejection_reason}`
              : ''}
          </li>
        {/if}
        {#if quote.cancelled_at}<li>
            Cancelada por {quote.cancelled_by_name} el {formatDay(quote.cancelled_at)} · {quote.cancellation_reason}
          </li>{/if}
      </ul>
      {#if quote.sale_id}
        <p class="mt-3 text-foreground">
          Generó el pedido <a
            class="font-semibold text-primary hover:underline"
            href={`/sales/${quote.sale_id}`}>{quote.sale_code}</a
          >.
        </p>
      {/if}
    </section>

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4">
      <div class="flex flex-wrap gap-2">
        {#if quote.status === 'draft'}
          {#if can('sales_quotations:manage')}
            <a
              class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
              href={`/sales/quotations/${quote.id}/edit`}>Editar borrador</a
            >
          {/if}
          {#if can('sales_quotations:confirm')}
            <button
              class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              disabled={busy}
              onclick={() => void run('issue')}
            >
              {quote.requires_authorization ? 'Enviar a autorización' : 'Emitir cotización'}
            </button>
          {/if}
        {/if}
        {#if quote.status === 'pending_authorization' && can('sales_discounts:authorize')}
          <button
            class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onclick={() => (pending = 'authorize')}>Autorizar</button
          >
          <button
            class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
            onclick={() => (pending = 'return')}>Devolver a borrador</button
          >
        {/if}
        {#if quote.status === 'issued' && can('sales_quotations:confirm')}
          {#if !quote.expired}
            <button
              class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              disabled={busy}
              onclick={() => void run('accept')}>El cliente aceptó</button
            >
          {/if}
          <button
            class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
            onclick={() => (pending = 'reject')}>El cliente rechazó</button
          >
        {/if}
        {#if quote.status === 'accepted' && !quote.sale_id && can('sales_quotations:convert')}
          <button
            class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={busy}
            onclick={() => void startOrder()}
          >
            Crear pedido
          </button>
        {/if}
        {#if ['draft', 'pending_authorization', 'issued', 'accepted'].includes(quote.status) && !quote.sale_id && can('sales_quotations:confirm')}
          <button
            class="rounded-md border border-danger/30 px-4 py-2 text-sm text-danger"
            onclick={() => (pending = 'cancel')}>Cancelar</button
          >
        {/if}
      </div>
      {#if ordering && quote.status === 'accepted' && !quote.sale_id}
        <form
          class="grid gap-3 border-t border-border pt-3 sm:grid-cols-[auto_auto_1fr_auto] sm:items-end"
          onsubmit={createOrder}
        >
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
              Dirección
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
            </label>
          {:else}
            <span></span>
          {/if}
          <button
            class="h-10 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={busy}
          >
            {busy ? 'Creando…' : 'Crear pedido en borrador'}
          </button>
        </form>
      {/if}
      {#if pending && pending !== 'issue' && pending !== 'accept'}
        {@const prompt = prompts[pending]}
        <form
          class="flex flex-col gap-2 border-t border-border pt-3 sm:flex-row"
          onsubmit={(event) => {
            event.preventDefault();
            if (pending) void run(pending);
          }}
        >
          <label class="sr-only" for="quote-action-text">{prompt.label}</label>
          <input
            id="quote-action-text"
            class="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground"
            bind:value={text}
            placeholder={prompt.label}
            maxlength="1000"
          />
          <button
            class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={busy || (prompt.required && text.trim().length < 3)}>{prompt.button}</button
          >
          <button
            type="button"
            class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
            onclick={() => {
              pending = null;
              text = '';
            }}>Volver</button
          >
        </form>
      {/if}
    </section>
  {/if}
</div>
