<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import type { Sale } from '$lib/types/sales';
  import SalesDeliveryPanel from './SalesDeliveryPanel.svelte';
  import SalesReturnsPanel from './SalesReturnsPanel.svelte';

  let { id }: { id: string } = $props();
  let sale = $state<Sale | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let cancelReason = $state('');
  let quantities = $state<Record<string, string>>({});
  let prices = $state<Record<string, string>>({});
  let notes = $state('');
  let generation = 0;
  let pendingConfirmation: (() => Promise<void>) | null = null;
  onDestroy(() => {
    generation++;
    if (pendingConfirmation && confirmation.current?.execute === pendingConfirmation) confirmation.cancel();
  });

  function normalizedDecimal(value: unknown): string {
    return String(value).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  }

  function draftHasUnsavedChanges(): boolean {
    return sale?.status === 'draft' && (
      notes !== (sale.notes ?? '') || sale.lines.some((line) =>
        normalizedDecimal(quantities[line.source_quotation_line_id]) !== normalizedDecimal(line.quantity) ||
        normalizedDecimal(prices[line.source_quotation_line_id]) !== normalizedDecimal(line.unit_price)
      )
    );
  }
  const hasUnsavedChanges = $derived(draftHasUnsavedChanges());

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesApi.sale(id);
      if (generation !== current) return;
      sale = response;
      quantities = Object.fromEntries(response.lines.map((line) => [line.source_quotation_line_id, line.quantity]));
      prices = Object.fromEntries(response.lines.map((line) => [line.source_quotation_line_id, line.unit_price]));
      notes = response.notes ?? '';
    } catch (cause) {
      if (generation === current) error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la venta.';
    } finally {
      if (generation === current) loading = false;
    }
  }

  onMount(() => void load());

  async function saveDraft(event: SubmitEvent) {
    event.preventDefault();
    if (!sale) return;
    saving = true;
    error = null;
    try {
      sale = await salesApi.updateSale(sale.id, {
        expected_version: sale.version,
        notes: notes || null,
        lines: sale.lines.map((line) => ({
          source_quotation_line_id: line.source_quotation_line_id,
          quantity: quantities[line.source_quotation_line_id] ?? line.quantity,
          unit_price: prices[line.source_quotation_line_id] ?? line.unit_price
        }))
      });
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar la venta. Recarga para revisar su versión.';
    } finally {
      saving = false;
    }
  }

  async function confirm() {
    if (busy || saving) return;
    if (hasUnsavedChanges) {
      error = 'Guarda los cambios del borrador antes de confirmar la venta.';
      return;
    }
    if (!sale || confirmation.open) return;
    const document = sale;
    pendingConfirmation = async () => {
      if (!sale || sale.id !== document.id || sale.version !== document.version || sale.status !== 'draft' || draftHasUnsavedChanges()) {
        throw new Error('El borrador cambió. Guarda y revisa antes de confirmar.');
      }
      busy = true;
      error = null;
      try { sale = await salesApi.confirmSale(document.id, document.version); }
      catch (cause) { throw new Error(cause instanceof HttpError ? cause.message : 'No se pudo confirmar la venta.'); }
      finally { busy = false; }
    };
    confirmation.request({ kind: 'confirm', title: `Confirmar ${document.code}`, resourceName: document.code,
      description: 'Se fijarán los términos comerciales. La entrega se prepara por separado; confirmar no descuenta inventario.',
      confirmLabel: 'Confirmar venta ahora', execute: pendingConfirmation });
  }

  async function cancel() {
    if (!sale || !cancelReason.trim()) {
      error = 'Escribe un motivo para cancelar.';
      return;
    }
    busy = true;
    error = null;
    try {
      sale = await salesApi.cancelSale(sale.id, sale.version, cancelReason);
      cancelReason = '';
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo cancelar la venta.';
    } finally {
      busy = false;
    }
  }

  const statusNames: Record<Sale['status'], string> = { draft: 'Borrador', confirmed: 'Confirmada', cancelled: 'Cancelada' };
  const deliveryStatusNames: Record<Sale['delivery_progress'], string> = {
    pending: 'Pendiente',
    partial: 'Parcialmente entregada',
    complete: 'Entregada'
  };
</script>

<svelte:head><title>Venta | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-6xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <a class="text-sm text-primary hover:underline" href="/sales">← Ventas</a>
  {#if error}
    <div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground" role="alert">
      {error}<button class="ml-3 underline" onclick={() => void load()}>Recargar</button>
    </div>
  {/if}
  {#if loading}
    <section class="rounded-xl border border-border bg-surface p-10 text-center text-sm text-foreground-muted">Cargando venta…</section>
  {:else if sale}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Venta · {sale.code}</p>
        <h1 class="mt-1 text-2xl font-bold text-foreground">{sale.customer_name}</h1>
        <p class="mt-1 text-sm text-foreground-muted">Origen: <a class="font-mono text-primary hover:underline" href={`/sales/quotations/${sale.quotation_id}`}>{sale.quotation_code}</a></p>
      </div>
      <span class="w-fit rounded-full bg-surface-muted px-3 py-1 text-sm text-foreground">{statusNames[sale.status]}</span>
    </header>

    <section class="grid gap-3 sm:grid-cols-3">
      <div class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Estado comercial</p>
        <p class="mt-2 font-semibold text-foreground">{statusNames[sale.status]} · revisión {sale.version}</p>
        <p class="text-xs text-foreground-muted">{sale.currency}</p>
      </div>
      <div class={`rounded-xl border p-4 ${sale.delivery_progress === 'complete' ? 'border-success/30 bg-success/5' : sale.delivery_progress === 'partial' ? 'border-primary/30 bg-primary/5' : 'border-warning/30 bg-warning/5'}`}>
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Estado de entrega</p>
        <p class="mt-2 font-semibold text-foreground">{deliveryStatusNames[sale.delivery_progress]}</p>
        <p class="text-xs text-foreground-muted">El detalle se muestra por renglón en unidad base.</p>
      </div>
      <div class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs uppercase tracking-wide text-foreground-muted">Total comercial</p>
        <p class="mt-2 font-mono text-xl font-bold text-foreground">USD {Number(sale.total).toFixed(2)}</p>
        <p class="text-xs text-foreground-muted">Sin impuestos ni descuentos.</p>
      </div>
    </section>

    <form class="overflow-hidden rounded-xl border border-border bg-surface" onsubmit={saveDraft}>
      <div class="border-b border-border p-4">
        <h2 class="font-semibold text-foreground">Renglones de la venta</h2>
        <p class="mt-1 text-xs text-foreground-muted">El documento conserva el origen de la cotización. No se muestran costos de inventario.</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[900px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr><th class="px-4 py-3">Producto</th><th class="px-4 py-3">Unidad</th><th class="w-36 px-4 py-3">Cantidad</th><th class="w-40 px-4 py-3">Precio USD</th><th class="px-4 py-3 text-right">Renglón</th><th class="px-4 py-3 text-right">Entregado base</th><th class="px-4 py-3 text-right">Pendiente base</th></tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each sale.lines as line (line.id)}
              <tr>
                <td class="px-4 py-3"><p class="font-medium text-foreground">{line.product_name}</p><p class="font-mono text-xs text-foreground-muted">{line.product_sku}</p></td>
                <td class="px-4 py-3 text-foreground">{formatUnitLabel(line.unit_name)}<p class="text-xs text-foreground-muted">× {line.unit_factor} {formatUnitLabel(line.base_unit_name)}</p></td>
                <td class="px-4 py-3"><input aria-label={`Cantidad de ${line.product_name}`} class="h-9 w-full rounded-md border border-border bg-background px-2 text-foreground disabled:opacity-60" type="number" min="0.000001" step="0.000001" bind:value={quantities[line.source_quotation_line_id]} disabled={sale.status !== 'draft' || !permissions.hasPermission('sales:manage')} /></td>
                <td class="px-4 py-3"><input aria-label={`Precio de ${line.product_name}`} class="h-9 w-full rounded-md border border-border bg-background px-2 text-foreground disabled:opacity-60" type="number" min="0" step="0.000001" bind:value={prices[line.source_quotation_line_id]} disabled={sale.status !== 'draft' || !permissions.hasPermission('sales:manage')} /></td>
                <td class="px-4 py-3 text-right font-mono text-foreground">USD {Number(line.line_total).toFixed(2)}</td>
                <td class="px-4 py-3 text-right font-mono text-foreground-muted">{line.quantity_delivered_base} {formatUnitLabel(line.base_unit_name)}</td>
                <td class="px-4 py-3 text-right font-mono text-foreground-muted">{line.quantity_pending_base} {formatUnitLabel(line.base_unit_name)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="grid gap-4 border-t border-border p-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <label class="text-sm text-foreground-muted">Notas<input bind:value={notes} disabled={sale.status !== 'draft' || !permissions.hasPermission('sales:manage')} maxlength="4000" class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground disabled:opacity-60" /></label>
        <div class="text-right">
          <p class="font-mono text-lg font-semibold text-foreground">USD {Number(sale.total).toFixed(2)}</p>
          {#if sale.status === 'draft' && permissions.hasPermission('sales:manage')}<button type="submit" class="mt-2 rounded-md border border-border px-4 py-2 text-sm text-foreground disabled:opacity-50" disabled={saving}>{saving ? 'Guardando…' : 'Guardar borrador'}</button>{/if}
        </div>
      </div>
    </form>

    <SalesDeliveryPanel {sale} onChanged={load} />
    <SalesReturnsPanel {sale} onChanged={load} />

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4">
      <div class="flex flex-wrap gap-2">
        {#if sale.status === 'draft' && permissions.hasPermission('sales:confirm')}
          <button class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy || saving || hasUnsavedChanges} onclick={() => void confirm()}>{busy ? 'Procesando…' : 'Confirmar venta'}</button>
        {/if}
      </div>
      {#if hasUnsavedChanges}<p class="text-sm text-warning" role="status">Guarda los cambios del borrador antes de confirmar la venta.</p>{/if}
      {#if sale.status !== 'cancelled' && permissions.hasPermission('sales:cancel')}
        <form class="flex flex-col gap-2 border-t border-border pt-3 sm:flex-row" onsubmit={(event) => { event.preventDefault(); void cancel(); }}>
          <label class="sr-only" for="sale-cancel-reason">Motivo de cancelación</label>
          <input id="sale-cancel-reason" class="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={cancelReason} placeholder="Motivo para cancelar la venta" maxlength="1000" />
          <button class="rounded-md border border-danger/30 px-4 py-2 text-sm text-danger disabled:opacity-50" disabled={busy || !cancelReason.trim()}>Cancelar venta</button>
        </form>
      {/if}
      <p class="text-xs text-foreground-muted">La venta confirmada conserva sus términos; cada entrega registra una salida física separada. Una venta con entrega confirmada no se puede cancelar: debe gestionarse mediante el flujo de devoluciones.</p>
    </section>
  {/if}
</main>
