<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { branch } from '$lib/stores/branch.svelte';
  import type { SalesQuotation } from '$lib/types/sales';

  let items = $state<SalesQuotation[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let status = $state('');
  let page = $state(1);
  let pages = $state(1);
  let total = $state(0);
  let generation = 0;

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesApi.quotations({ branch_id: branch.id, status: status || undefined, page, size: 20 });
      if (generation !== current) return;
      items = response.items;
      pages = response.meta.pages;
      total = response.meta.total;
    } catch (cause) {
      if (generation === current) error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las cotizaciones.';
    } finally {
      if (generation === current) loading = false;
    }
  }
  onMount(() => void load());
  $effect(() => { const selected = branch.id; const filter = status; void selected; void filter; page = 1; void load(); });

  const labels: Record<SalesQuotation['status'], string> = { draft: 'Borrador', confirmed: 'Confirmada', cancelled: 'Cancelada', expired: 'Vencida' };
  const badge: Record<SalesQuotation['status'], string> = { draft: 'bg-surface-muted text-foreground-muted', confirmed: 'bg-success/10 text-success', cancelled: 'bg-danger/10 text-danger', expired: 'bg-warning/10 text-warning' };
</script>

<svelte:head><title>Cotizaciones de venta | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-7xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p><h1 class="mt-1 text-2xl font-bold text-foreground">Cotizaciones de venta</h1><p class="mt-1 text-sm text-foreground-muted">Precios comerciales capturados por el usuario. Guardar y confirmar no reserva ni descuenta inventario.</p></div><a class="rounded-md bg-primary px-4 py-2 text-center text-sm font-semibold text-primary-foreground" href="/sales/quotations/new">Nueva cotización</a></header>
  <section class="rounded-xl border border-border bg-surface p-4"><div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p class="text-sm text-foreground-muted">{total} cotización(es) · {branch.label}</p><label class="text-sm text-foreground-muted">Estado<select class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground" bind:value={status}><option value="">Todos</option><option value="draft">Borrador</option><option value="confirmed">Confirmada</option><option value="expired">Vencida</option><option value="cancelled">Cancelada</option></select></label></div></section>
  {#if error}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}<button class="ml-3 underline" onclick={() => void load()}>Reintentar</button></div>{/if}
  <section class="overflow-hidden rounded-xl border border-border bg-surface">{#if loading}<p class="p-10 text-center text-sm text-foreground-muted">Cargando cotizaciones…</p>{:else if items.length === 0}<div class="p-10 text-center"><p class="font-medium text-foreground">No hay cotizaciones para estos filtros.</p><p class="mt-1 text-sm text-foreground-muted">Puedes crear una con un cliente y los productos vendibles configurados.</p></div>{:else}<div class="overflow-x-auto"><table class="w-full min-w-[850px] text-left text-sm"><thead class="bg-surface-muted text-xs uppercase text-foreground-muted"><tr><th class="px-4 py-3">Código</th><th class="px-4 py-3">Cliente</th><th class="px-4 py-3">Fecha / vigencia</th><th class="px-4 py-3">Estado</th><th class="px-4 py-3 text-right">Total</th><th class="px-4 py-3"></th></tr></thead><tbody class="divide-y divide-border">{#each items as quote (quote.id)}<tr><td class="px-4 py-3 font-mono text-xs text-primary"><a href={`/sales/quotations/${quote.id}`} class="hover:underline">{quote.code}</a></td><td class="px-4 py-3 text-foreground"><span class="font-medium">{quote.customer_name}</span><span class="ml-2 font-mono text-xs text-foreground-muted">{quote.customer_code}</span></td><td class="px-4 py-3 text-foreground-muted">{quote.quotation_date}<br /><span class="text-xs">Vence {quote.valid_until}</span></td><td class="px-4 py-3"><span class={`rounded-full px-2 py-1 text-xs ${badge[quote.status]}`}>{labels[quote.status]}</span>{#if quote.converted}<p class="mt-1 text-xs text-primary">Venta {quote.sale_code}</p>{/if}</td><td class="px-4 py-3 text-right font-mono text-foreground">USD {Number(quote.total).toFixed(2)}</td><td class="px-4 py-3 text-right"><a href={`/sales/quotations/${quote.id}`} class="text-primary hover:underline">Abrir</a></td></tr>{/each}</tbody></table></div>{/if}</section>
  {#if pages > 1}<footer class="flex items-center justify-between text-sm text-foreground-muted"><span>Página {page} de {pages}</span><div class="flex gap-2"><button class="rounded-md border border-border px-3 py-2 disabled:opacity-40" disabled={page <= 1} onclick={() => { page--; void load(); }}>Anterior</button><button class="rounded-md border border-border px-3 py-2 disabled:opacity-40" disabled={page >= pages} onclick={() => { page++; void load(); }}>Siguiente</button></div></footer>{/if}
</main>
