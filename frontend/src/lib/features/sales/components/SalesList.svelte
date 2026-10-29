<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { branch } from '$lib/stores/branch.svelte';
  import type { Sale } from '$lib/types/sales';

  let items = $state<Sale[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let status = $state('');
  let page = $state(1);
  let pages = $state(1);
  let total = $state(0);
  let generation = 0;
  async function load() {
    const current = ++generation; loading = true; error = null;
    try { const response = await salesApi.sales({ branch_id: branch.id, status: status || undefined, page, size: 20 }); if (generation !== current) return; items = response.items; pages = response.meta.pages; total = response.meta.total; }
    catch (cause) { if (generation === current) error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las ventas.'; }
    finally { if (generation === current) loading = false; }
  }
  onMount(() => void load());
  $effect(() => { const selected = branch.id; const filter = status; void selected; void filter; page = 1; void load(); });
  const names: Record<Sale['status'], string> = { draft: 'Borrador', confirmed: 'Confirmada', cancelled: 'Cancelada' };
</script>

<svelte:head><title>Ventas | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-7xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <header class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p><h1 class="mt-1 text-2xl font-bold text-foreground">Ventas</h1><p class="mt-1 text-sm text-foreground-muted">Documentos comerciales originados desde cotizaciones. Las ventas confirmadas aún no representan una entrega.</p></div><a class="text-sm text-primary hover:underline" href="/sales/quotations">Ver cotizaciones</a></header>
  <section class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"><p class="text-sm text-foreground-muted">{total} venta(s) · {branch.label}</p><label class="text-sm text-foreground-muted">Estado<select class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground" bind:value={status}><option value="">Todos</option><option value="draft">Borrador</option><option value="confirmed">Confirmada</option><option value="cancelled">Cancelada</option></select></label></section>
  {#if error}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}<button class="ml-3 underline" onclick={() => void load()}>Reintentar</button></div>{/if}
  <section class="overflow-hidden rounded-xl border border-border bg-surface">{#if loading}<p class="p-10 text-center text-sm text-foreground-muted">Cargando ventas…</p>{:else if items.length === 0}<div class="p-10 text-center"><p class="font-medium text-foreground">No hay ventas para estos filtros.</p><p class="mt-1 text-sm text-foreground-muted">Confirma una cotización y conviértela para crear una venta en borrador.</p><a class="mt-4 inline-block text-sm text-primary hover:underline" href="/sales/quotations">Ir a cotizaciones</a></div>{:else}<div class="overflow-x-auto"><table class="w-full min-w-[850px] text-left text-sm"><thead class="bg-surface-muted text-xs uppercase text-foreground-muted"><tr><th class="px-4 py-3">Código</th><th class="px-4 py-3">Origen</th><th class="px-4 py-3">Cliente</th><th class="px-4 py-3">Estado comercial</th><th class="px-4 py-3">Entrega</th><th class="px-4 py-3 text-right">Total</th><th class="px-4 py-3"></th></tr></thead><tbody class="divide-y divide-border">{#each items as sale (sale.id)}<tr><td class="px-4 py-3 font-mono text-xs text-primary"><a href={`/sales/${sale.id}`} class="hover:underline">{sale.code}</a></td><td class="px-4 py-3 font-mono text-xs text-foreground-muted"><a href={`/sales/quotations/${sale.quotation_id}`} class="hover:text-primary">{sale.quotation_code}</a></td><td class="px-4 py-3 text-foreground">{sale.customer_name}</td><td class="px-4 py-3 text-foreground">{names[sale.status]}</td><td class="px-4 py-3"><span class="rounded-full bg-warning/10 px-2 py-1 text-xs text-warning">Pendiente de entrega</span></td><td class="px-4 py-3 text-right font-mono text-foreground">USD {Number(sale.total).toFixed(2)}</td><td class="px-4 py-3 text-right"><a href={`/sales/${sale.id}`} class="text-primary hover:underline">Abrir</a></td></tr>{/each}</tbody></table></div>{/if}</section>
  {#if pages > 1}<footer class="flex items-center justify-between text-sm text-foreground-muted"><span>Página {page} de {pages}</span><div class="flex gap-2"><button class="rounded-md border border-border px-3 py-2 disabled:opacity-40" disabled={page <= 1} onclick={() => { page--; void load(); }}>Anterior</button><button class="rounded-md border border-border px-3 py-2 disabled:opacity-40" disabled={page >= pages} onclick={() => { page++; void load(); }}>Siguiente</button></div></footer>{/if}
</main>
