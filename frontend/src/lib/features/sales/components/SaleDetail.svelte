<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import { RESPONSIBLE_DOCUMENT_LABELS, isSealed } from '#lib/features/sales/fiscal-labels.ts';
  import { formatUnitLabel } from '#lib/features/sales/unit-label.ts';
  import {
    DELIVERY_MODE_LABELS,
    DELIVERY_PROGRESS_LABELS,
    DOCUMENT_LABELS,
    ORDER_STATUS_BADGES,
    ORDER_STATUS_LABELS,
    formatDay,
    formatMoney,
    formatPercent,
    formatQuantity,
    formatUnitPrice,
    paymentLabel
  } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { Sale } from '#lib/types/sales.ts';
  import type { FiscalDocument } from '#lib/types/sales-invoices.ts';
  import SalesDeliveryPanel from './SalesDeliveryPanel.svelte';
  import SalesInvoicePanel from './SalesInvoicePanel.svelte';
  import SalesReturnsPanel from './SalesReturnsPanel.svelte';

  type Action = 'confirm' | 'authorize' | 'return' | 'cancel';

  let { id }: { id: string } = $props();
  let sale = $state<Sale | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let text = $state('');
  let pending = $state<Exclude<Action, 'confirm'> | null>(null);
  let invoicedDocument = $state<FiscalDocument | null>(null);
  const invoiced = $derived(invoicedDocument !== null);
  let requesterName = $state('');
  let requesterType = $state('13');
  let requesterNumber = $state('');
  let notice = $state<string | null>(null);
  let generation = 0;
  onDestroy(() => generation++);

  const can = (code: string) => permissions.hasPermission(code);
  const branchName = $derived(
    sale ? (branch.branches.find((item) => item.id === sale?.branch_id)?.name ?? '') : ''
  );
  const prompts: Record<
    Exclude<Action, 'confirm'>,
    { label: string; required: boolean; button: string }
  > = {
    authorize: {
      label: 'Nota de la autorización (opcional)',
      required: false,
      button: 'Autorizar y confirmar'
    },
    return: { label: 'Qué debe corregirse', required: true, button: 'Devolver a borrador' },
    cancel: { label: 'Motivo de la cancelación', required: true, button: 'Cancelar pedido' }
  };

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesApi.sale(id);
      if (generation === current) sale = response;
    } catch (cause) {
      if (generation === current) {
        error = cause instanceof HttpError ? cause.message : 'No se pudo cargar el pedido.';
      }
    } finally {
      if (generation === current) loading = false;
    }
  }
  onMount(() => void load());

  async function run(action: Action) {
    if (!sale || busy) return;
    const prompt = action === 'confirm' ? null : prompts[action];
    if (prompt?.required && text.trim().length < 3) {
      error = `${prompt.label}: escribe al menos 3 caracteres.`;
      return;
    }
    busy = true;
    error = null;
    try {
      if (action === 'cancel' && invoicedDocument) {
        // Pedido facturado (V4b): se anula el documento y el pedido se cancela al aceptarse.
        await salesInvoicesApi.invalidate(invoicedDocument.id, {
          reason: text.trim(),
          requester: {
            name: requesterName,
            document_type: requesterType,
            document_number: requesterNumber
          },
          cancel_order: true
        });
        notice =
          'Se pidió la anulación del documento a Hacienda. El pedido se cancela cuando la acepte.';
        text = '';
        pending = null;
        return;
      }
      sale = await salesApi.orderAction(sale.id, action, {
        expected_version: sale.version,
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
</script>

<svelte:head
  ><title>{sale ? `Pedido ${sale.code}` : 'Pedido de venta'} | GestionaSV</title></svelte:head
>

<div class="space-y-5">
  <a class="text-sm text-primary hover:underline" href="/sales">← Pedidos de venta</a>
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
  {:else if sale}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">
          Pedido · {sale.code} · {DOCUMENT_LABELS[sale.document_type]}
        </p>
        <h1 class="mt-1 text-2xl font-bold text-foreground">{sale.customer_name}</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {sale.customer_code}{branchName ? ` · ${branchName}` : ''}
          {#if sale.quotation_id}
            · Origen:
            <a
              class="font-mono text-primary hover:underline"
              href={`/sales/quotations/${sale.quotation_id}`}>{sale.quotation_code}</a
            >
          {/if}
        </p>
      </div>
      <span class={`w-fit rounded-full px-3 py-1 text-sm ${ORDER_STATUS_BADGES[sale.status]}`}
        >{ORDER_STATUS_LABELS[sale.status]}</span
      >
    </header>

    {#if sale.status === 'pending_authorization'}
      <section
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
      >
        <p class="font-semibold">Espera autorización</p>
        <ul class="mt-1 list-disc pl-5">
          {#each sale.authorization_reasons as reason (reason.code)}<li>{reason.message}</li>{/each}
        </ul>
      </section>
    {:else if sale.status === 'draft' && sale.authorization_note && !sale.authorized_at}
      <section
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
      >
        Devuelto por quien autoriza: {sale.authorization_note}
      </section>
    {/if}

    <section class="grid gap-3 sm:grid-cols-3">
      <div class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Entrega comprometida</p>
        <p class="mt-2 font-semibold text-foreground">{formatDay(sale.promised_date)}</p>
        <p class="text-xs text-foreground-muted">
          {DELIVERY_MODE_LABELS[sale.delivery_mode]}{sale.delivery_address_text
            ? ` · ${sale.delivery_address_text}`
            : ''}
        </p>
      </div>
      <div class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Avance de entrega</p>
        <p class="mt-2 font-semibold text-foreground">
          {DELIVERY_PROGRESS_LABELS[sale.delivery_progress]}
        </p>
        <p class="text-xs text-foreground-muted">
          {sale.status === 'confirmed'
            ? 'Lo pendiente queda apartado en la sucursal.'
            : 'Se aparta al confirmar el pedido.'}
        </p>
      </div>
      <div class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Total</p>
        <p class="mt-2 font-mono text-xl font-bold text-foreground">{formatMoney(sale.total)}</p>
        <p class="text-xs text-foreground-muted">{paymentLabel(sale)}</p>
      </div>
    </section>

    <section class="overflow-hidden rounded-xl border border-border bg-surface">
      <div class="border-b border-border p-4">
        <h2 class="font-semibold text-foreground">Productos</h2>
        <p class="mt-1 text-xs text-foreground-muted">
          Lista: {sale.price_list_name ?? 'sin lista'} · precios {sale.prices_include_vat
            ? 'con'
            : 'sin'} IVA. Cantidades entregadas y pendientes en unidad base.
        </p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[860px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr>
              <th class="px-4 py-3">Producto</th>
              <th class="px-4 py-3">Cantidad</th>
              <th class="px-4 py-3 text-right">Precio</th>
              <th class="px-4 py-3 text-right">Descuento</th>
              {#if sale.costs_visible}<th class="px-4 py-3 text-right">Costo / margen</th>{/if}
              <th class="px-4 py-3 text-right">Total</th>
              <th class="px-4 py-3 text-right">Entregado / pendiente</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each sale.lines as line (line.id)}
              <tr>
                <td class="px-4 py-3">
                  <p class="font-medium text-foreground">{line.product_name}</p>
                  <p class="font-mono text-xs text-foreground-muted">{line.product_sku}</p>
                  {#if line.available_base !== null && Number(line.available_base) < Number(line.quantity_base)}
                    <p class="text-xs text-warning">
                      Disponible en la sucursal: {formatQuantity(line.available_base)}
                      {formatUnitLabel(line.base_unit_name)}
                    </p>
                  {/if}
                  {#each line.authorization_reasons as reason (reason.code)}
                    <p class="text-xs text-warning">{reason.message}</p>
                  {/each}
                </td>
                <td class="px-4 py-3 text-foreground"
                  >{formatQuantity(line.quantity)} {formatUnitLabel(line.unit_name)}</td
                >
                <td class="px-4 py-3 text-right font-mono text-foreground">
                  {formatUnitPrice(line.document_unit_price)}
                  {#if line.price_overridden}<p class="text-xs text-warning">Manual</p>{/if}
                </td>
                <td class="px-4 py-3 text-right font-mono text-foreground">
                  {Number(line.discount_percent) > 0 ? formatPercent(line.discount_percent) : '—'}
                </td>
                {#if sale.costs_visible}
                  <td class="px-4 py-3 text-right font-mono text-foreground-muted">
                    {formatUnitPrice(line.cost)} · {formatPercent(line.margin_percent)}
                  </td>
                {/if}
                <td class="px-4 py-3 text-right font-mono font-semibold text-foreground"
                  >{formatMoney(line.line_total)}</td
                >
                <td class="px-4 py-3 text-right font-mono text-foreground-muted">
                  {formatQuantity(line.quantity_delivered_base)} / {formatQuantity(
                    line.quantity_pending_base
                  )}
                  {formatUnitLabel(line.base_unit_name)}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <dl
        class="grid gap-x-6 gap-y-1 border-t border-border p-4 text-sm sm:ml-auto sm:max-w-sm sm:grid-cols-[1fr_auto]"
      >
        <dt class="text-foreground-muted">Ventas gravadas</dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(sale.total_taxed)}</dd>
        {#if Number(sale.total_exempt) > 0}
          <dt class="text-foreground-muted">Ventas exentas</dt>
          <dd class="text-right font-mono text-foreground">{formatMoney(sale.total_exempt)}</dd>
        {/if}
        <dt class="text-foreground-muted">Descuentos</dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(sale.total_discount)}</dd>
        <dt class="text-foreground-muted">
          {sale.document_type === '03' ? 'IVA 13 %' : 'IVA incluido'}
        </dt>
        <dd class="text-right font-mono text-foreground">{formatMoney(sale.vat)}</dd>
        {#if Number(sale.vat_perceived) > 0}
          <dt class="text-foreground-muted">IVA percibido</dt>
          <dd class="text-right font-mono text-foreground">{formatMoney(sale.vat_perceived)}</dd>
        {/if}
        {#if Number(sale.vat_withheld) > 0}
          <dt class="text-foreground-muted">IVA retenido</dt>
          <dd class="text-right font-mono text-foreground">−{formatMoney(sale.vat_withheld)}</dd>
        {/if}
        <dt class="border-t border-border pt-1 font-semibold text-foreground">Total</dt>
        <dd
          class="border-t border-border pt-1 text-right font-mono text-lg font-bold text-foreground"
        >
          {formatMoney(sale.total)}
        </dd>
      </dl>
      <p class="px-4 pb-4 text-right text-xs text-foreground-muted">{sale.total_in_words}</p>
    </section>

    {#if sale.notes}
      <section class="rounded-xl border border-border bg-surface p-4">
        <h2 class="font-semibold text-foreground">Notas</h2>
        <p class="mt-2 whitespace-pre-wrap text-sm text-foreground-muted">{sale.notes}</p>
      </section>
    {/if}

    {#if sale.status === 'confirmed'}
      {#if can('sales_invoices:read')}
        <SalesInvoicePanel {sale} onInvoiced={(value) => (invoicedDocument = value)} />
      {/if}
      <SalesDeliveryPanel {sale} onChanged={load} />
      <SalesReturnsPanel {sale} onChanged={load} />
    {/if}

    <section class="rounded-xl border border-border bg-surface p-4 text-sm text-foreground-muted">
      <h2 class="font-semibold text-foreground">Historial</h2>
      <ul class="mt-2 space-y-1">
        <li>Creado por {sale.created_by_name ?? '—'}</li>
        {#if sale.authorized_at}
          <li>
            Autorizado por {sale.authorized_by_name} el {formatDay(
              sale.authorized_at
            )}{sale.authorization_note ? ` · ${sale.authorization_note}` : ''}
          </li>
        {/if}
        {#if sale.confirmed_at}
          <li>Confirmado por {sale.confirmed_by_name} el {formatDay(sale.confirmed_at)}</li>
        {/if}
        {#if sale.cancelled_at}
          <li>
            Cancelado por {sale.cancelled_by_name} el {formatDay(sale.cancelled_at)} · {sale.cancellation_reason}
          </li>
        {/if}
      </ul>
    </section>

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4">
      <div class="flex flex-wrap gap-2">
        {#if sale.status === 'draft'}
          {#if can('sales:manage')}
            <a
              class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
              href={`/sales/${sale.id}/edit`}>Editar borrador</a
            >
          {/if}
          {#if can('sales:confirm')}
            <button
              class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              disabled={busy}
              onclick={() => void run('confirm')}
            >
              {busy ? 'Procesando…' : 'Confirmar y apartar'}
            </button>
          {/if}
        {/if}
        {#if sale.status === 'pending_authorization' && can('sales_discounts:authorize')}
          <button
            class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onclick={() => (pending = 'authorize')}>Autorizar</button
          >
          <button
            class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
            onclick={() => (pending = 'return')}>Devolver a borrador</button
          >
        {/if}
        {#if sale.status !== 'cancelled' && sale.delivery_progress === 'pending' && can('sales:cancel') && (!invoiced || (invoicedDocument && isSealed(invoicedDocument) && !invoicedDocument.superseded_by_id && can('sales_invoices:invalidate')))}
          <button
            class="rounded-md border border-danger/30 px-4 py-2 text-sm text-danger"
            onclick={() => (pending = 'cancel')}>Cancelar pedido</button
          >
        {/if}
      </div>
      {#if pending === 'cancel' && invoicedDocument}
        <div class="space-y-3 border-t border-border pt-3">
          <p class="text-sm text-foreground">
            El pedido está facturado: se anulará su documento ante Hacienda (se rescinde la
            operación) y el pedido se cancelará cuando Hacienda lo acepte.
          </p>
          <div class="grid gap-3 sm:grid-cols-3">
            <label class="space-y-1 text-sm text-foreground-muted sm:col-span-3"
              >Nombre del solicitante
              <input
                class="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                maxlength="100"
                bind:value={requesterName}
              />
            </label>
            <label class="space-y-1 text-sm text-foreground-muted"
              >Documento
              <select
                class="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                value={requesterType}
                onchange={(event) => (requesterType = event.currentTarget.value)}
              >
                {#each Object.entries(RESPONSIBLE_DOCUMENT_LABELS) as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
            </label>
            <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
              >Número de documento del solicitante
              <input
                class="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground"
                maxlength="25"
                bind:value={requesterNumber}
              />
            </label>
          </div>
        </div>
      {/if}
      {#if notice}
        <p class="text-sm text-success" aria-live="polite">{notice}</p>
      {/if}
      {#if pending}
        {@const prompt = prompts[pending]}
        <form
          class="flex flex-col gap-2 border-t border-border pt-3 sm:flex-row"
          onsubmit={(event) => {
            event.preventDefault();
            if (pending) void run(pending);
          }}
        >
          <label class="sr-only" for="order-action-text">{prompt.label}</label>
          <input
            id="order-action-text"
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
      <p class="text-xs text-foreground-muted">
        Confirmar aparta las existencias de la sucursal; cancelar las libera. Un pedido con entregas
        ya no se cancela: se gestiona con devoluciones. Cancelar uno facturado anula su documento
        ante Hacienda.
      </p>
    </section>
  {/if}
</div>
