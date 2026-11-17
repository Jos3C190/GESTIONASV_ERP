<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { contingenciesApi } from '#lib/api/sales-contingencies.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import {
    FISCAL_STATUS_BADGES,
    FISCAL_STATUS_FILTERS,
    FISCAL_STATUS_LABELS
  } from '#lib/features/sales/fiscal-labels.ts';
  import { DOCUMENT_LABELS, formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import type { FiscalDocument } from '#lib/types/sales-invoices.ts';

  let items = $state<FiscalDocument[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let status = $state('');
  let documentType = $state('');
  let search = $state('');
  let page = $state(1);
  let pages = $state(1);
  let total = $state(0);
  let generation = 0;
  let inContingency = $state<string[]>([]);
  let debounce: ReturnType<typeof setTimeout> | null = null;
  onDestroy(() => {
    generation++;
    if (debounce) clearTimeout(debounce);
  });

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesInvoicesApi.list({
        branch_id: branch.id,
        status: status || undefined,
        document_type: documentType || undefined,
        q: search,
        page,
        size: 20
      });
      if (current !== generation) return;
      items = response.items;
      pages = response.pages;
      total = response.total;
    } catch (cause) {
      if (current === generation) {
        error =
          cause instanceof HttpError
            ? cause.message
            : 'No se pudieron cargar los documentos fiscales.';
      }
    } finally {
      if (current === generation) loading = false;
    }
  }

  async function loadContingency() {
    try {
      const overview = await contingenciesApi.overview();
      inContingency = overview.windows
        .filter((item) => item.status === 'ACTIVA')
        .map((item) => item.branch_name ?? item.establishment_code ?? '');
    } catch {
      // El aviso es informativo: sin él la bandeja sigue funcionando.
      inContingency = [];
    }
  }

  $effect(() => {
    void loadContingency();
  });

  $effect(() => {
    void branch.id;
    untrack(() => {
      page = 1;
      void load();
    });
  });

  function filter(apply: () => void) {
    apply();
    page = 1;
    void load();
  }

  function onSearch() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      page = 1;
      void load();
    }, 300);
  }
</script>

<svelte:head><title>Documentos fiscales | GestionaSV</title></svelte:head>

<div class="space-y-5">
  <header>
    <p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p>
    <h1 class="page-title-echo mt-1 text-2xl font-bold text-foreground">Documentos fiscales</h1>
    <p class="mt-1 text-sm text-foreground-muted">
      Facturas y comprobantes de crédito fiscal emitidos desde los pedidos, con su número de
      control, su JSON y su PDF.
    </p>
  </header>

  {#if inContingency.length > 0}
    <div
      class="flex flex-col gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning sm:flex-row sm:items-center sm:justify-between"
      role="status"
    >
      <span
        >En contingencia: {inContingency.join(', ')}. Los documentos se generan sin conexión con
        Hacienda y se transmiten al cerrarla.</span
      >
      <a class="font-medium underline" href="/sales/contingencies">Ver contingencia</a>
    </div>
  {/if}

  <section
    class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 lg:flex-row lg:items-center lg:justify-between"
  >
    <p class="text-sm text-foreground-muted">{total} documento(s) · {branch.label}</p>
    <div class="flex flex-col gap-2 sm:flex-row">
      <label class="sr-only" for="fiscal-search">Buscar</label>
      <input
        id="fiscal-search"
        class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground sm:w-72"
        placeholder="Número de control, pedido o cliente"
        maxlength="80"
        bind:value={search}
        oninput={onSearch}
      />
      <label class="text-sm text-foreground-muted"
        >Tipo<select
          class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground"
          value={documentType}
          onchange={(event) => filter(() => (documentType = event.currentTarget.value))}
        >
          <option value="">Todos</option>
          <option value="01">Factura</option>
          <option value="03">Crédito fiscal</option>
        </select></label
      >
      <label class="text-sm text-foreground-muted"
        >Estado<select
          class="ml-2 h-9 rounded-md border border-border bg-background px-3 text-foreground"
          value={status}
          onchange={(event) => filter(() => (status = event.currentTarget.value))}
        >
          {#each FISCAL_STATUS_FILTERS as option (option.value)}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select></label
      >
    </div>
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
        <p class="font-medium text-foreground">No hay documentos fiscales para estos filtros.</p>
        <p class="text-sm text-foreground-muted">
          Se factura desde un pedido confirmado, con la acción «Facturar».
        </p>
        <a
          class="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          href="/sales">Ir a pedidos</a
        >
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[900px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr>
              <th class="px-4 py-3">Número de control</th>
              <th class="px-4 py-3">Tipo</th>
              <th class="px-4 py-3">Pedido y cliente</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3">Fecha</th>
              <th class="px-4 py-3 text-right">Total</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each items as item (item.id)}
              <tr>
                <td class="px-4 py-3 font-mono text-xs text-foreground"
                  >{item.control_number ?? '—'}</td
                >
                <td class="px-4 py-3 text-foreground">{DOCUMENT_LABELS[item.document_type]}</td>
                <td class="px-4 py-3">
                  <a
                    class="font-mono text-xs text-primary hover:underline"
                    href={`/sales/${item.sale_id}`}>{item.sale_code}</a
                  >
                  <p class="text-foreground">{item.customer_name}</p>
                </td>
                <td class="px-4 py-3">
                  <span
                    class={`rounded-full px-2 py-1 text-xs ${FISCAL_STATUS_BADGES[item.status]}`}
                    >{FISCAL_STATUS_LABELS[item.status]}</span
                  >
                </td>
                <td class="px-4 py-3 text-foreground-muted"
                  >{formatDay(item.issued_at ?? item.created_at)}</td
                >
                <td class="px-4 py-3 text-right font-mono text-foreground"
                  >{formatMoney(item.total)}</td
                >
                <td class="px-4 py-3 text-right">
                  <a
                    href={`/sales/fiscal-documents/${item.id}`}
                    class="text-primary hover:underline">Abrir</a
                  >
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
