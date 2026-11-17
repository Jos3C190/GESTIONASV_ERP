<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import {
    STATUS_FILTERS,
    formatDay,
    formatMoney,
    statusBadge,
    statusLabel
  } from '#lib/features/sales/quotation-labels.ts';
  import type { SalesQuotation } from '#lib/types/sales.ts';

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
      const response = await salesApi.quotations({
        branch_id: branch.id,
        status: status || undefined,
        page,
        size: 20
      });
      if (generation !== current) return;
      items = response.items;
      pages = response.meta.pages;
      total = response.meta.total;
    } catch (cause) {
      if (generation === current)
        error =
          cause instanceof HttpError ? cause.message : 'No se pudieron cargar las cotizaciones.';
    } finally {
      if (generation === current) loading = false;
    }
  }
  onMount(() => void load());
  $effect(() => {
    const selected = branch.id;
    const filter = status;
    void selected;
    void filter;
    page = 1;
    void load();
  });
</script>

<svelte:head><title>Cotizaciones de venta | GestionaSV</title></svelte:head>
<div class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold text-foreground">Cotizaciones de venta</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Precio de lista, descuentos, impuestos y autorización. Cotizar no reserva ni descuenta
        inventario.
      </p>
    </div>
    <a
      class="rounded-md bg-primary px-4 py-2 text-center text-sm font-semibold text-primary-foreground"
      href="/sales/quotations/new">Nueva cotización</a
    >
  </header>
  <section class="rounded-xl border border-border bg-surface p-4">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-sm text-foreground-muted">{total} cotización(es) · {branch.label}</p>
      <label class="text-sm text-foreground-muted"
        >Estado<select
          class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground"
          bind:value={status}
          >{#each STATUS_FILTERS as option (option.value)}<option value={option.value}
              >{option.label}</option
            >{/each}</select
        ></label
      >
    </div>
  </section>
  {#if error}<div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}<button class="ml-3 underline" onclick={() => void load()}>Reintentar</button>
    </div>{/if}
  <section class="overflow-hidden rounded-xl border border-border bg-surface">
    {#if loading}<div class="space-y-2 p-4" aria-busy="true">
        <div class="skeleton h-9 w-full rounded-md"></div>
        <div class="skeleton h-9 w-full rounded-md"></div>
        <div class="skeleton h-9 w-full rounded-md"></div>
      </div>{:else if items.length === 0}<div
        class="flex flex-col items-center gap-2 p-10 text-center"
      >
        <span
          class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-lg text-foreground-muted"
          aria-hidden="true">∅</span
        >
        <p class="font-medium text-foreground">No hay cotizaciones para estos filtros.</p>
        <p class="text-sm text-foreground-muted">
          Crea una con un cliente y los productos de la lista de precios.
        </p>
        <a
          class="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          href="/sales/quotations/new">Nueva cotización</a
        >
      </div>{:else}<div class="overflow-x-auto">
        <table class="w-full min-w-[850px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted"
            ><tr
              ><th class="px-4 py-3">Código</th><th class="px-4 py-3">Cliente</th><th
                class="px-4 py-3">Fecha / vigencia</th
              ><th class="px-4 py-3">Estado</th><th class="px-4 py-3 text-right">Total</th><th
                class="px-4 py-3"
              ></th></tr
            ></thead
          ><tbody class="divide-y divide-border"
            >{#each items as quote (quote.id)}<tr
                ><td class="px-4 py-3 font-mono text-xs text-primary"
                  ><a href={`/sales/quotations/${quote.id}`} class="hover:underline">{quote.code}</a
                  ></td
                ><td class="px-4 py-3 text-foreground"
                  ><span class="font-medium">{quote.customer_name}</span><span
                    class="ml-2 font-mono text-xs text-foreground-muted">{quote.customer_code}</span
                  ></td
                ><td class="px-4 py-3 text-foreground-muted"
                  >{formatDay(quote.quotation_date)}<br /><span class="text-xs"
                    >Vence {formatDay(quote.valid_until)}</span
                  ></td
                ><td class="px-4 py-3"
                  ><span class={`rounded-full px-2 py-1 text-xs ${statusBadge(quote)}`}
                    >{statusLabel(quote)}</span
                  >{#if quote.sale_code}<p class="mt-1 text-xs text-primary">
                      Venta {quote.sale_code}
                    </p>{/if}</td
                ><td class="px-4 py-3 text-right font-mono text-foreground"
                  >{formatMoney(quote.total)}</td
                ><td class="px-4 py-3 text-right"
                  ><a href={`/sales/quotations/${quote.id}`} class="text-primary hover:underline"
                    >Abrir</a
                  ></td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>{/if}
  </section>
  {#if pages > 1}<footer class="flex items-center justify-between text-sm text-foreground-muted">
      <span>Página {page} de {pages}</span>
      <div class="flex gap-2">
        <button
          class="rounded-md border border-border px-3 py-2 disabled:opacity-40"
          disabled={page <= 1}
          onclick={() => {
            page--;
            void load();
          }}>Anterior</button
        ><button
          class="rounded-md border border-border px-3 py-2 disabled:opacity-40"
          disabled={page >= pages}
          onclick={() => {
            page++;
            void load();
          }}>Siguiente</button
        >
      </div>
    </footer>{/if}
</div>
