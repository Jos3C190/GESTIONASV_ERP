<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import {
    DELIVERY_MODE_LABELS,
    DELIVERY_PROGRESS_LABELS,
    ORDER_STATUS_BADGES,
    ORDER_STATUS_FILTERS,
    ORDER_STATUS_LABELS,
    formatDay,
    formatMoney
  } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { Sale } from '#lib/types/sales.ts';

  let items = $state<Sale[]>([]);
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
      const response = await salesApi.sales({
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
      if (generation === current) {
        error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los pedidos.';
      }
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

<svelte:head><title>Pedidos de venta | GestionaSV</title></svelte:head>

<div class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold text-foreground">Pedidos de venta</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Compromisos de entrega con el cliente. Confirmar un pedido aparta sus existencias en la
        sucursal.
      </p>
    </div>
    <div class="flex gap-2">
      <a
        class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
        href="/sales/quotations">Cotizaciones</a
      >
      {#if permissions.hasPermission('sales:manage')}
        <a
          class="rounded-md bg-primary px-4 py-2 text-center text-sm font-semibold text-primary-foreground"
          href="/sales/new">Nuevo pedido</a
        >
      {/if}
    </div>
  </header>

  <section
    class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
  >
    <p class="text-sm text-foreground-muted">{total} pedido(s) · {branch.label}</p>
    <label class="text-sm text-foreground-muted"
      >Estado<select
        class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground"
        bind:value={status}
      >
        {#each ORDER_STATUS_FILTERS as option (option.value)}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select></label
    >
  </section>

  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}<button class="ml-3 underline" onclick={() => void load()}>Reintentar</button>
    </div>
  {/if}

  <section class="overflow-hidden rounded-xl border border-border bg-surface">
    {#if loading}
      <div class="space-y-2 p-4" aria-busy="true">
        <div class="skeleton h-9 w-full rounded-md"></div>
        <div class="skeleton h-9 w-full rounded-md"></div>
        <div class="skeleton h-9 w-full rounded-md"></div>
      </div>
    {:else if items.length === 0}
      <div class="flex flex-col items-center gap-2 p-10 text-center">
        <span
          class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-lg text-foreground-muted"
          aria-hidden="true">∅</span
        >
        <p class="font-medium text-foreground">No hay pedidos para estos filtros.</p>
        <p class="text-sm text-foreground-muted">
          Crea uno directo o desde una cotización aceptada.
        </p>
        {#if permissions.hasPermission('sales:manage')}
          <a
            class="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            href="/sales/new">Nuevo pedido</a
          >
        {/if}
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[900px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr>
              <th class="px-4 py-3">Código</th>
              <th class="px-4 py-3">Cliente</th>
              <th class="px-4 py-3">Entrega</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3 text-right">Total</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each items as sale (sale.id)}
              <tr>
                <td class="px-4 py-3 font-mono text-xs text-primary">
                  <a href={`/sales/${sale.id}`} class="hover:underline">{sale.code}</a>
                  {#if sale.quotation_code}
                    <p class="text-foreground-muted">{sale.quotation_code}</p>
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground">
                  <span class="font-medium">{sale.customer_name}</span>
                  <span class="ml-2 font-mono text-xs text-foreground-muted"
                    >{sale.customer_code}</span
                  >
                </td>
                <td class="px-4 py-3 text-foreground-muted">
                  {formatDay(sale.promised_date)}
                  <p class="text-xs">{DELIVERY_MODE_LABELS[sale.delivery_mode]}</p>
                </td>
                <td class="px-4 py-3">
                  <span class={`rounded-full px-2 py-1 text-xs ${ORDER_STATUS_BADGES[sale.status]}`}
                    >{ORDER_STATUS_LABELS[sale.status]}</span
                  >
                  {#if sale.status === 'confirmed'}
                    <p class="mt-1 text-xs text-foreground-muted">
                      {DELIVERY_PROGRESS_LABELS[sale.delivery_progress]}
                    </p>
                  {/if}
                </td>
                <td class="px-4 py-3 text-right font-mono text-foreground"
                  >{formatMoney(sale.total)}</td
                >
                <td class="px-4 py-3 text-right">
                  <a href={`/sales/${sale.id}`} class="text-primary hover:underline">Abrir</a>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

  {#if pages > 1}
    <footer class="flex items-center justify-between text-sm text-foreground-muted">
      <span>Página {page} de {pages}</span>
      <div class="flex gap-2">
        <button
          class="rounded-md border border-border px-3 py-2 disabled:opacity-40"
          disabled={page <= 1}
          onclick={() => {
            page--;
            void load();
          }}>Anterior</button
        >
        <button
          class="rounded-md border border-border px-3 py-2 disabled:opacity-40"
          disabled={page >= pages}
          onclick={() => {
            page++;
            void load();
          }}>Siguiente</button
        >
      </div>
    </footer>
  {/if}
</div>
