<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import type { SalesQuotation } from '$lib/types/sales';

  let { id }: { id: string } = $props();
  let quote = $state<SalesQuotation | null>(null);
  let branchName = $derived(
    quote ? branch.branches.find((item) => item.id === quote?.branch_id)?.name ?? 'Sucursal autorizada' : ''
  );
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let reason = $state('');
  let generation = 0;
  let pendingConfirmation: (() => Promise<void>) | null = null;
  onDestroy(() => {
    generation++;
    if (pendingConfirmation && confirmation.current?.execute === pendingConfirmation) confirmation.cancel();
  });

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try { const response = await salesApi.quotation(id); if (generation === current) quote = response; }
    catch (cause) { if (generation === current) error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la cotización.'; }
    finally { if (generation === current) loading = false; }
  }
  onMount(() => void load());

  async function confirm() {
    if (!quote || busy || confirmation.open) return;
    const document = quote;
    pendingConfirmation = async () => {
      if (!quote || quote.id !== document.id || quote.version !== document.version || quote.status !== 'draft') {
        throw new Error('El documento cambió. Recarga antes de confirmar.');
      }
      busy = true; error = null;
      try { quote = await salesApi.confirmQuotation(document.id, document.version); }
      catch (cause) { throw new Error(cause instanceof HttpError ? cause.message : 'No se pudo confirmar. Recarga el documento.'); }
      finally { busy = false; }
    };
    confirmation.request({ kind: 'confirm', title: `Confirmar ${document.code}`, resourceName: document.code,
      description: 'La cotización quedará congelada. Esta confirmación no reserva ni descuenta inventario.',
      confirmLabel: 'Confirmar cotización ahora', execute: pendingConfirmation });
  }
  async function convert() {
    if (!quote || quote.converted) return;
    busy = true; error = null;
    const storageKey = `sales-convert:${quote.id}`;
    let key = sessionStorage.getItem(storageKey);
    if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(storageKey, key); }
    try {
      const sale = await salesApi.convertQuotation(quote.id, quote.version, key);
      await goto(`/sales/${sale.id}`);
    } catch (cause) { error = cause instanceof HttpError ? cause.message : 'No se pudo convertir. Puedes reintentar sin duplicar la venta.'; }
    finally { busy = false; }
  }
  async function cancel() {
    if (!quote || !reason.trim()) { error = 'Escribe el motivo de cancelación.'; return; }
    busy = true; error = null;
    try { quote = await salesApi.cancelQuotation(quote.id, quote.version, reason); reason = ''; }
    catch (cause) { error = cause instanceof HttpError ? cause.message : 'No se pudo cancelar la cotización.'; }
    finally { busy = false; }
  }

  const statusNames: Record<SalesQuotation['status'], string> = { draft: 'Borrador', confirmed: 'Confirmada', cancelled: 'Cancelada', expired: 'Vencida' };
</script>

<svelte:head><title>Cotización de venta | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-6xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <a class="text-sm text-primary hover:underline" href="/sales/quotations">← Cotizaciones de venta</a>
  {#if error}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}<button class="ml-3 underline" onclick={() => void load()}>Recargar</button></div>{/if}
  {#if loading}<section class="rounded-xl border border-border bg-surface p-10 text-center text-sm text-foreground-muted">Cargando cotización…</section>{:else if quote}<header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p class="text-xs font-semibold uppercase tracking-widest text-primary">Cotización de venta · {quote.code}</p><h1 class="mt-1 text-2xl font-bold text-foreground">{quote.customer_name}</h1><p class="mt-1 text-sm text-foreground-muted">{quote.customer_code} · {quote.quotation_date} · válida hasta {quote.valid_until}</p></div><span class="w-fit rounded-full bg-surface-muted px-3 py-1 text-sm text-foreground">{statusNames[quote.status]}</span></header>
    <section class="grid gap-3 sm:grid-cols-3"><div class="rounded-xl border border-border bg-surface p-4"><p class="text-xs uppercase tracking-wide text-foreground-muted">Estado comercial</p><p class="mt-2 font-semibold text-foreground">{statusNames[quote.status]}</p><p class="text-xs text-foreground-muted">Revisión {quote.version} · {quote.currency}</p></div><div class="rounded-xl border border-border bg-surface p-4"><p class="text-xs uppercase tracking-wide text-foreground-muted">Sucursal</p><p class="mt-2 font-semibold text-foreground">{branchName}</p><p class="text-xs text-foreground-muted">{quote.converted ? `Convertida a ${quote.sale_code}` : 'Sin conversión'}</p></div><div class="rounded-xl border border-border bg-surface p-4"><p class="text-xs uppercase tracking-wide text-foreground-muted">Total comercial</p><p class="mt-2 font-mono text-xl font-bold text-foreground">USD {Number(quote.total).toFixed(2)}</p><p class="text-xs text-foreground-muted">No incluye impuestos ni descuentos.</p></div></section>
    <section class="overflow-hidden rounded-xl border border-border bg-surface"><div class="border-b border-border p-4"><h2 class="font-semibold text-foreground">Renglones</h2><p class="mt-1 text-xs text-foreground-muted">Cantidades y unidad quedan congeladas al confirmar.</p></div><div class="overflow-x-auto"><table class="w-full min-w-[750px] text-left text-sm"><thead class="bg-surface-muted text-xs uppercase text-foreground-muted"><tr><th class="px-4 py-3">Producto</th><th class="px-4 py-3">Cantidad y unidad</th><th class="px-4 py-3 text-right">Precio unitario</th><th class="px-4 py-3 text-right">Total</th></tr></thead><tbody class="divide-y divide-border">{#each quote.lines as line (line.id)}<tr><td class="px-4 py-3"><p class="font-medium text-foreground">{line.product_name}</p><p class="font-mono text-xs text-foreground-muted">{line.product_sku}</p></td><td class="px-4 py-3 text-foreground">{line.quantity} {formatUnitLabel(line.unit_name)}<p class="text-xs text-foreground-muted">≈ {line.quantity_base} {formatUnitLabel(line.base_unit_name)}</p></td><td class="px-4 py-3 text-right font-mono text-foreground">USD {Number(line.unit_price).toFixed(6)}</td><td class="px-4 py-3 text-right font-mono font-semibold text-foreground">USD {Number(line.line_total).toFixed(2)}</td></tr>{/each}</tbody></table></div><div class="flex justify-end border-t border-border p-4"><p class="text-lg font-semibold text-foreground">Total: USD {Number(quote.total).toFixed(2)}</p></div></section>
    {#if quote.notes}<section class="rounded-xl border border-border bg-surface p-4"><h2 class="font-semibold text-foreground">Notas</h2><p class="mt-2 whitespace-pre-wrap text-sm text-foreground-muted">{quote.notes}</p></section>{/if}
    {#if quote.converted && quote.sale_id}<section class="rounded-xl border border-primary/30 bg-primary/5 p-4"><p class="text-sm text-foreground">Esta cotización ya generó la venta <a class="font-semibold text-primary hover:underline" href={`/sales/${quote.sale_id}`}>{quote.sale_code}</a>. La venta conserva su propio estado e historial.</p></section>{/if}
    <section class="space-y-3 rounded-xl border border-border bg-surface p-4"><div class="flex flex-wrap gap-2">{#if quote.status === 'draft' && !quote.converted}{#if permissions.hasPermission('sales_quotations:manage')}<a class="rounded-md border border-border px-4 py-2 text-sm text-foreground" href={`/sales/quotations/${quote.id}/edit`}>Editar borrador</a>{/if}{#if permissions.hasPermission('sales_quotations:confirm')}<button class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy} onclick={() => void confirm()}>{busy ? 'Procesando…' : 'Confirmar cotización'}</button>{/if}{/if}{#if quote.status === 'confirmed' && !quote.converted && permissions.hasPermission('sales_quotations:convert')}<button class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy} onclick={() => void convert()}>{busy ? 'Convirtiendo…' : 'Crear venta en borrador'}</button>{/if}</div>
      {#if quote.status !== 'cancelled' && !quote.converted && permissions.hasPermission('sales_quotations:confirm')}<form class="flex flex-col gap-2 border-t border-border pt-3 sm:flex-row" onsubmit={(event) => { event.preventDefault(); void cancel(); }}><label class="sr-only" for="quote-cancel-reason">Motivo de cancelación</label><input id="quote-cancel-reason" class="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={reason} placeholder="Motivo para cancelar la cotización" maxlength="1000" /><button class="rounded-md border border-danger/30 px-4 py-2 text-sm text-danger disabled:opacity-50" disabled={busy || !reason.trim()}>Cancelar cotización</button></form>{/if}
      <p class="text-xs text-foreground-muted">La conversión es única e idempotente. No hay acción de entrega en esta etapa; las ventas confirmadas quedan pendientes de entrega.</p>
    </section>
  {/if}
</main>
