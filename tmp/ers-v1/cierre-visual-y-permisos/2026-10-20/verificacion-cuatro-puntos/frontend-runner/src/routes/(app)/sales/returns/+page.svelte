<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { branch } from '$lib/stores/branch.svelte';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import type { SalesReturn, SalesReturnStatus } from '$lib/types/sales';

  let items = $state<SalesReturn[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let search = $state('');
  let status = $state<SalesReturnStatus | ''>('');
  let generation = 0;

  const statusNames: Record<SalesReturnStatus, string> = {
    draft: 'Borrador',
    received: 'Recibida · pendiente de revisión',
    under_review: 'En revisión parcial',
    accepted: 'Aceptada',
    rejected: 'Rechazada',
    mixed: 'Mixta',
    cancelled: 'Cancelada'
  };

  const statusStyles: Record<SalesReturnStatus, string> = {
    draft: 'border-border bg-background text-foreground-muted',
    received: 'border-warning/30 bg-warning/10 text-warning',
    under_review: 'border-primary/30 bg-primary/10 text-primary',
    accepted: 'border-success/30 bg-success/10 text-success',
    rejected: 'border-danger/30 bg-danger/10 text-danger',
    mixed: 'border-primary/30 bg-primary/10 text-primary',
    cancelled: 'border-border bg-background text-foreground-muted'
  };

  const filteredItems = $derived.by(() => {
    const term = search.trim().toLocaleLowerCase('es-SV');
    return items.filter((item) => {
      if (status && item.status !== status) return false;
      if (!term) return true;
      return [item.code, ...item.lines.flatMap((line) => [line.product_name, line.product_sku, line.delivery_code])]
        .some((value) => value.toLocaleLowerCase('es-SV').includes(term));
    });
  });
  const hasActiveFilters = $derived(search.trim().length > 0 || status !== '');

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    items = [];
    try {
      const result = await salesApi.returns();
      if (generation === current) items = result;
    } catch (cause) {
      if (generation === current) {
        error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las devoluciones.';
      }
    } finally {
      if (generation === current) loading = false;
    }
  }

  $effect(() => {
    const selectedBranch = branch.id;
    void selectedBranch;
    void load();
  });

  function formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  }

</script>

<svelte:head><title>Devoluciones | GestionaSV</title></svelte:head>

<main class="mx-auto max-w-7xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p>
      <h1 class="mt-1 text-2xl font-bold text-foreground">Devoluciones</h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">Consulta las devoluciones de la sucursal seleccionada y abre la venta de origen para recibir, revisar, aceptar o rechazar sus productos.</p>
    </div>
    <a class="w-fit rounded-md border border-border px-3 py-2 text-sm text-foreground hover:bg-surface-hover" href="/sales">Ver ventas</a>
  </header>

  <section class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-end sm:justify-between" aria-label="Filtros de devoluciones">
    <label class="min-w-0 flex-1 text-sm text-foreground-muted">Buscar devolución, producto o entrega
      <input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" bind:value={search} placeholder="Ej. DEV-…, café, SKU o entrega" />
    </label>
    <label class="text-sm text-foreground-muted">Estado
      <select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground sm:min-w-64" bind:value={status}>
        <option value="">Todos los estados</option>
        {#each Object.entries(statusNames) as [value, label]}
          <option {value}>{label}</option>
        {/each}
      </select>
    </label>
    <p
      class={`w-fit rounded-full border px-3 py-1.5 text-sm ${hasActiveFilters ? 'border-primary/30 bg-primary/10 font-medium text-primary' : 'border-border bg-background text-foreground-muted'}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {#if hasActiveFilters}
        Filtros aplicados · {filteredItems.length} de {items.length} resultados
      {:else}
        {filteredItems.length} de {items.length} · {branch.label}
      {/if}
    </p>
  </section>

  {#if loading}
    <div class="rounded-xl border border-border bg-surface p-10 text-center text-sm text-foreground-muted" role="status" aria-live="polite">Cargando devoluciones…</div>
  {:else if error}
    <div class="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between" role="alert">
      <span>{error}</span>
      <button class="w-fit rounded-md border border-danger/30 px-3 py-2 font-medium" onclick={() => void load()}>Reintentar</button>
    </div>
  {:else if filteredItems.length === 0}
    <section class="rounded-xl border border-border bg-surface p-8 text-center sm:p-12">
      <h2 class="font-semibold text-foreground">{items.length === 0 ? 'Todavía no hay devoluciones' : 'No hay resultados para estos filtros'}</h2>
      <p class="mx-auto mt-2 max-w-xl text-sm text-foreground-muted">{items.length === 0 ? 'Registra una devolución desde una venta con entrega confirmada. Después podrás darle seguimiento aquí.' : 'Prueba otro código, producto o estado.'}</p>
      {#if items.length === 0}<a class="mt-4 inline-block rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground" href="/sales">Ir a ventas</a>{/if}
    </section>
  {:else}
    <section class="space-y-3" aria-label="Devoluciones registradas">
      {#each filteredItems as item (item.id)}
        <article class="rounded-xl border border-border bg-surface p-4 sm:p-5">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 space-y-1">
              <p class="font-mono text-sm font-semibold text-primary">{item.code}</p>
              <p class="text-xs text-foreground-muted">Registrada {formatDate(item.created_at)}</p>
              <div class="flex flex-wrap gap-2 pt-1" aria-label="Productos devueltos">
                {#each item.lines as line (line.id)}
                  <span class="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground">{line.product_name} · {line.product_sku} · {line.quantity_received_base} {formatUnitLabel(line.base_unit_name)}</span>
                {/each}
              </div>
              <p class="pt-1 text-xs text-foreground-muted">{item.lines.length} línea(s) · entrega {item.lines.map((line) => line.delivery_code).filter((value, index, all) => all.indexOf(value) === index).join(', ')}</p>
            </div>
            <span class={`w-fit shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold ${statusStyles[item.status]}`}>{statusNames[item.status]}</span>
          </div>
          <footer class="mt-4 flex flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
            <p class="text-xs text-foreground-muted">Venta de origen asociada</p>
            <a class="w-fit rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90" href={`/sales/${item.sale_id}#sales-returns-heading`}>Abrir venta y gestionar</a>
          </footer>
        </article>
      {/each}
    </section>
  {/if}
</main>
