<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { customersApi } from '$lib/api/customers';
  import {
    CUSTOMER_TYPE_LABELS,
    RECEIVABLE_DOCUMENT_LABELS,
    formatDocument
  } from '$lib/features/customers/labels';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Customer, CustomerType } from '$lib/types/customer';

  const SIZE = 20;
  const controlClass =
    'h-11 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let customers = $state<Customer[]>([]);
  let total = $state(0);
  let pages = $state(1);
  let page = $state(1);
  let search = $state('');
  let type = $state<CustomerType | ''>('');
  let status = $state<'active' | 'inactive' | 'all'>('active');
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  let requestId = 0;

  const canRead = $derived(permissions.hasPermission('sales_customers:read'));
  const canManage = $derived(permissions.hasPermission('sales_customers:manage'));

  async function load() {
    const current = ++requestId;
    loading = true;
    loadError = null;
    try {
      const response = await customersApi.list({
        search,
        customer_type: type,
        active: status === 'all' ? null : status === 'active',
        page,
        size: SIZE
      });
      if (current !== requestId) return;
      customers = response.items;
      total = response.meta.total;
      pages = Math.max(response.meta.pages, 1);
    } catch (cause) {
      if (current !== requestId) return;
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar los clientes.';
    } finally {
      if (current === requestId) loading = false;
    }
  }

  function refilter() {
    page = 1;
    void load();
  }

  function onSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(refilter, 300);
  }

  function goTo(next: number) {
    page = next;
    void load();
  }

  onMount(() => {
    if (canRead) void load();
    else loading = false;
    return () => clearTimeout(searchTimer);
  });
</script>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar los clientes.
  </div>
{:else}
  <div class="space-y-5">
    <header class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
        <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
          Clientes
        </h1>
        <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
          Identidad fiscal, dirección y condiciones de cada cliente. De estos datos depende qué
          documento se le puede emitir.
        </p>
      </div>
      {#if canManage}
        <a
          href="/customers/new"
          class="inline-flex h-11 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          Nuevo cliente
        </a>
      {/if}
    </header>

    <section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
      <div class="grid gap-2 border-b border-border p-4 sm:grid-cols-[1fr_auto_auto]">
        <label class="sr-only" for="customer-search">Buscar cliente</label>
        <input
          id="customer-search"
          bind:value={search}
          oninput={onSearch}
          placeholder="Buscar por nombre, código, NIT, DUI o NRC…"
          class={controlClass}
        />
        <label class="sr-only" for="customer-type">Tipo de cliente</label>
        <select id="customer-type" bind:value={type} onchange={refilter} class={controlClass}>
          <option value="">Todos los tipos</option>
          {#each Object.entries(CUSTOMER_TYPE_LABELS) as [value, label] (value)}
            <option {value}>{label}</option>
          {/each}
        </select>
        <label class="sr-only" for="customer-status">Estado</label>
        <select id="customer-status" bind:value={status} onchange={refilter} class={controlClass}>
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
          <option value="all">Todos</option>
        </select>
      </div>

      {#if loading}
        <div class="space-y-3 p-4" aria-busy="true">
          <p class="sr-only" role="status">Cargando clientes…</p>
          {#each [1, 2, 3] as row (row)}
            <div
              class="skeleton h-14 rounded-lg motion-reduce:animate-none"
              aria-hidden="true"
            ></div>
          {/each}
        </div>
      {:else if loadError}
        <div
          class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
          role="alert"
        >
          <span>{loadError}</span>
          <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
        </div>
      {:else if customers.length === 0}
        <div class="px-6 py-14 text-center">
          <div
            class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted"
            aria-hidden="true"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
            >
              <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <p class="mt-3 text-sm font-semibold text-foreground">
            {search || type || status !== 'active' ? 'Sin resultados' : 'Aún no hay clientes'}
          </p>
          <p class="mt-1 text-sm text-foreground-muted">
            {search || type || status !== 'active'
              ? 'Prueba otra búsqueda o cambia los filtros.'
              : 'Registra a tus clientes con sus datos fiscales para facturarles.'}
          </p>
          {#if canManage && !search && !type && status === 'active'}
            <a
              href="/customers/new"
              class="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground"
            >
              Registrar el primero
            </a>
          {/if}
        </div>
      {:else}
        <div class="hidden overflow-x-auto lg:block">
          <table class="w-full min-w-[760px] text-sm">
            <thead class="bg-surface-muted text-xs text-foreground-muted">
              <tr>
                <th class="p-3 text-left font-medium">Cliente</th>
                <th class="p-3 text-left font-medium">Tipo</th>
                <th class="p-3 text-left font-medium">Documento</th>
                <th class="p-3 text-left font-medium">Puede recibir</th>
                <th class="p-3 text-left font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {#each customers as customer (customer.id)}
                <tr class="border-t border-border transition-colors hover:bg-surface-muted/40">
                  <td class="p-3">
                    <a
                      href="/customers/{customer.id}"
                      class="font-medium text-foreground hover:text-primary"
                    >
                      {customer.name}
                    </a>
                    <p class="font-mono text-xs text-foreground-muted">{customer.code}</p>
                  </td>
                  <td class="p-3 text-foreground-muted"
                    >{CUSTOMER_TYPE_LABELS[customer.customer_type]}</td
                  >
                  <td class="p-3 font-mono text-xs text-foreground-muted">
                    {formatDocument(customer.document_type, customer.document_number)}
                  </td>
                  <td class="p-3">
                    <div class="flex flex-wrap gap-1">
                      {#each customer.receivable_documents as code (code)}
                        <Badge variant={code === '03' ? 'success' : 'neutral'}>
                          {RECEIVABLE_DOCUMENT_LABELS[code] ?? code}
                        </Badge>
                      {/each}
                    </div>
                  </td>
                  <td class="p-3">
                    <Badge variant={customer.is_active ? 'success' : 'neutral'}>
                      {customer.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <ul class="divide-y divide-border lg:hidden">
          {#each customers as customer (customer.id)}
            <li>
              <a
                href="/customers/{customer.id}"
                class="block space-y-2 p-4 hover:bg-surface-muted/40"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="break-words font-medium text-foreground">{customer.name}</p>
                    <p class="text-xs text-foreground-muted">
                      {customer.code} · {CUSTOMER_TYPE_LABELS[customer.customer_type]}
                    </p>
                  </div>
                  <Badge variant={customer.is_active ? 'success' : 'neutral'}>
                    {customer.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each customer.receivable_documents as code (code)}
                    <Badge variant={code === '03' ? 'success' : 'neutral'}>
                      {RECEIVABLE_DOCUMENT_LABELS[code] ?? code}
                    </Badge>
                  {/each}
                </div>
              </a>
            </li>
          {/each}
        </ul>
        {#if pages > 1}
          <nav
            class="flex items-center justify-between border-t border-border p-3 text-sm text-foreground-muted"
            aria-label="Paginación de clientes"
          >
            <span>{total} clientes · página {page} de {pages}</span>
            <div class="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onclick={() => goTo(page - 1)}
              >
                Anterior
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= pages}
                onclick={() => goTo(page + 1)}
              >
                Siguiente
              </Button>
            </div>
          </nav>
        {/if}
      {/if}
    </section>
  </div>
{/if}
