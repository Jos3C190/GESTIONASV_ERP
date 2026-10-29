<script lang="ts">
  import { tick, untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import ValuationOpening from '$lib/features/inventory/components/ValuationOpening.svelte';
  import {
    valuationApi,
    valuationKind,
    displayDecimal,
    type ValuationOverview,
    type ValuationEntry
  } from '$lib/features/inventory/valuation';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let data = $state<ValuationOverview | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state(false);
  let search = $state('');
  let page = $state(0);
  let selected = $state('');
  let entries = $state<ValuationEntry[]>([]);
  let ledgerLoading = $state(false);
  let ledgerError = $state<string | null>(null);
  let ledgerPage = $state(0);
  let ledgerHeading = $state<HTMLHeadingElement>();
  let sequence = 0;
  let ledgerSequence = 0;
  const allowed = $derived(
    permissions.hasPermission('inventory:valuation') && branch.accessAllBranches
  );
  const labels = $derived(new Map(data?.items.map((item) => [item.inventory_item_id, item]) ?? []));
  const filtered = $derived(
    (data?.balances ?? []).filter((row) => {
      const item = labels.get(row.inventory_item_id);
      return `${item?.product_name} ${item?.sku}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase());
    })
  );
  const selectedItem = $derived(labels.get(selected));
  function message(cause: unknown) {
    return cause instanceof Error ? cause.message : 'No se pudo consultar la valoración.';
  }

  async function load() {
    const revision = ++sequence;
    ledgerSequence++;
    selected = '';
    entries = [];
    ledgerLoading = false;
    loading = true;
    error = null;
    try {
      const result = await valuationApi.overview();
      if (revision === sequence) {
        data = result;
        page = 0;
      }
    } catch (cause) {
      if (revision === sequence) error = message(cause);
    } finally {
      if (revision === sequence) loading = false;
    }
  }
  async function showLedger(id: string, nextPage = 0, focusEntry?: string) {
    const revision = ++ledgerSequence;
    selected = id;
    entries = [];
    ledgerLoading = true;
    ledgerError = null;
    await tick();
    if (revision !== ledgerSequence) return;
    ledgerHeading?.focus();
    ledgerHeading?.scrollIntoView({ block: 'start' });
    ledgerPage = nextPage;
    try {
      const result = await valuationApi.ledger(id, nextPage * 50);
      if (revision === ledgerSequence) entries = result;
    } catch (cause) {
      if (revision === ledgerSequence) ledgerError = message(cause);
    } finally {
      if (revision === ledgerSequence) ledgerLoading = false;
    }
    if (focusEntry && revision === ledgerSequence) {
      await tick();
      const target = document.getElementById(`valuation-entry-${focusEntry}`);
      target?.focus();
      target?.scrollIntoView({ block: 'center' });
    }
  }
  $effect(() => {
    const id = company.id;
    if (id && allowed)
      untrack(() => {
        data = null;
        success = false;
        void load();
      });
    else {
      sequence++;
      ledgerSequence++;
      data = null;
      loading = false;
    }
  });
</script>

<svelte:head><title>Valoración de inventario | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">Valoración de inventario</h1>
      <p class="mt-2 max-w-3xl text-sm leading-6 text-foreground-muted">
        Promedio por producto de {company.active?.commercial_name ?? 'la empresa'}, compartido entre
        todos sus almacenes. Los traslados internos conservan el valor.
      </p>
    </div>
    {#if data?.setting}<Button variant="secondary" disabled={loading} onclick={() => void load()}
        >Actualizar</Button
      >{/if}
  </header>
  {#if !allowed}
    <section class="rounded-xl border border-border p-6">
      <h2 class="font-semibold">Acceso de valoración requerido</h2>
      <p class="mt-2 text-sm text-foreground-muted">
        Esta consulta reúne todas las sucursales. Solicita el permiso de valoración y alcance
        completo de la empresa.
      </p>
    </section>
  {:else if loading}
    <div role="status" class="space-y-4">
      <p class="text-sm text-foreground-muted">Consultando cantidades y costos…</p>
      <div class="skeleton h-20 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if error}
    <section class="rounded-xl border border-danger/30 bg-danger/5 p-5">
      <p role="alert" class="mb-4 text-sm text-danger">{error}</p>
      <Button variant="secondary" onclick={() => void load()}>Reintentar consulta</Button>
    </section>
  {:else if data}
    {#if success}<p
        role="status"
        class="rounded-lg border border-success/30 bg-success/5 p-4 text-sm text-success"
      >
        Saldo inicial aprobado. Las próximas recepciones registrarán su costo provisional.
      </p>{/if}
    {#if !data.setting}
      <ValuationOpening
        {data}
        onrefresh={(next) => {
          data = next;
        }}
        onapproved={async () => {
          success = true;
          await load();
        }}
      />
    {:else}
      <section
        class="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-surface p-5"
      >
        <div>
          <h2 class="font-semibold">Promedio ponderado activo · {data.setting.currency}</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            Corte aprobado el {new Date(data.setting.opened_at).toLocaleString('es-SV', {
              timeZone: 'America/El_Salvador'
            })}
          </p>
        </div>
        <p class="max-w-lg break-words text-sm">{data.setting.opening_reference}</p>
      </section>
      <section
        class="overflow-hidden rounded-xl border border-border"
        aria-label="Saldos valorados por producto"
      >
        <div class="border-b border-border p-4">
          <label for="valuation-search" class="mb-2 block text-sm font-medium"
            >Buscar producto o SKU</label
          ><input
            id="valuation-search"
            class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary sm:max-w-md"
            bind:value={search}
            oninput={() => (page = 0)}
          />
          <p class="mt-2 text-xs text-foreground-muted">
            {filtered.length} productos · Cantidades en unidad base · Incluye cuarentena y tránsito
          </p>
        </div>
        {#if filtered.length === 0}<div class="p-8">
            <h3 class="font-medium">{search ? 'Sin coincidencias' : 'Sin productos valorados'}</h3>
            <p class="mt-2 text-sm text-foreground-muted">
              {search
                ? 'Prueba con otro nombre o código de producto.'
                : 'Los productos aparecerán al verificar una recepción con costo.'}
            </p>
          </div>
        {:else}<div class="overflow-x-auto">
            <table class="balance-table w-full text-left text-sm">
              <caption class="sr-only"
                >Cantidad base, costo promedio y valor total por producto</caption
              ><thead class="bg-surface text-xs text-foreground-muted"
                ><tr
                  ><th scope="col" class="p-4">Producto</th><th scope="col" class="p-4 text-right"
                    >Cantidad</th
                  ><th scope="col" class="p-4 text-right">Costo promedio</th><th
                    scope="col"
                    class="p-4 text-right">Valor del inventario</th
                  ><th scope="col" class="p-4"><span class="sr-only">Consultar historial</span></th
                  ></tr
                ></thead
              ><tbody class="divide-y divide-border">
                {#each filtered.slice(page * 20, (page + 1) * 20) as row (row.inventory_item_id)}{@const item =
                    labels.get(row.inventory_item_id)}<tr
                    class={selected === row.inventory_item_id ? 'bg-primary/5' : ''}
                    ><th scope="row" class="max-w-xs p-4 font-normal"
                      ><span class="block font-medium">{item?.product_name}</span><span
                        class="text-xs text-foreground-muted">{item?.sku}</span
                      ></th
                    ><td class="p-4 text-right font-mono"
                      ><span class="mb-1 block font-sans text-xs text-foreground-muted sm:hidden"
                        >Cantidad</span
                      >{displayDecimal(row.quantity_base)}
                      {item?.base_unit}</td
                    ><td class="p-4 text-right font-mono"
                      ><span class="mb-1 block font-sans text-xs text-foreground-muted sm:hidden"
                        >Costo promedio · {data.setting.currency}</span
                      >{displayDecimal(row.average_unit_cost)}</td
                    ><td class="p-4 text-right font-mono"
                      ><span class="mb-1 block font-sans text-xs text-foreground-muted sm:hidden"
                        >Valor · {data.setting.currency}</span
                      >{displayDecimal(row.inventory_value)}</td
                    ><td class="p-4"
                      ><Button
                        size="sm"
                        variant="secondary"
                        onclick={() => void showLedger(row.inventory_item_id)}
                        >{selected === row.inventory_item_id
                          ? 'Historial seleccionado'
                          : 'Ver movimientos'}</Button
                      ></td
                    ></tr
                  >{/each}
              </tbody>
            </table>
          </div>{/if}
        {#if filtered.length > 20}<div
            class="flex items-center justify-end gap-3 border-t border-border p-3"
          >
            <Button size="sm" variant="secondary" disabled={page === 0} onclick={() => page--}
              >Anterior</Button
            ><span class="text-sm">Página {page + 1}</span><Button
              size="sm"
              variant="secondary"
              disabled={(page + 1) * 20 >= filtered.length}
              onclick={() => page++}>Siguiente</Button
            >
          </div>{/if}
      </section>
      {#if selected}
        <section
          class="space-y-4 rounded-xl border border-border p-5"
          aria-label="Historial de valoración"
          aria-live="polite"
        >
          <div>
            <h2
              bind:this={ledgerHeading}
              tabindex="-1"
              class="scroll-mt-24 text-lg font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {selectedItem?.product_name}
            </h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Historial de costos · {selectedItem?.sku}. Los ajustes posteriores conservan los
              movimientos originales.
            </p>
          </div>
          {#if ledgerLoading}<p role="status" class="text-sm">Consultando movimientos…</p>
          {:else if ledgerError}<p role="alert" class="text-sm text-danger">{ledgerError}</p>
            <Button variant="secondary" onclick={() => void showLedger(selected, ledgerPage)}
              >Reintentar historial</Button
            >
          {:else}
            {#if entries.length === 0}<p class="text-sm text-foreground-muted">
                No hay más movimientos en esta página.
              </p>{/if}
            {#each entries as entry (entry.id)}
              <article
                id={`valuation-entry-${entry.id}`}
                tabindex="-1"
                class="border-t border-border pt-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 class="text-sm font-semibold">{valuationKind[entry.kind] ?? entry.kind}</h3>
                    <p class="mt-1 break-all text-xs text-foreground-muted">
                      {entry.source_reference}
                    </p>
                  </div>
                  <time class="text-xs text-foreground-muted" datetime={entry.posted_at}
                    >{new Date(entry.posted_at).toLocaleString('es-SV', {
                      timeZone: 'America/El_Salvador'
                    })}</time
                  >
                </div>
                <dl class="mt-3 grid grid-cols-2 gap-3 text-sm lg:grid-cols-5">
                  <div>
                    <dt class="text-xs text-foreground-muted">Cantidad del movimiento</dt>
                    <dd class="mt-1 font-mono">
                      {displayDecimal(entry.quantity_base)}
                      {selectedItem?.base_unit}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-xs text-foreground-muted">Cambio de valor</dt>
                    <dd class="mt-1 font-mono">
                      {data.setting.currency}
                      {displayDecimal(entry.inventory_delta)}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-xs text-foreground-muted">Saldo de cantidad</dt>
                    <dd class="mt-1 font-mono">{displayDecimal(entry.balance_quantity)}</dd>
                  </div>
                  <div>
                    <dt class="text-xs text-foreground-muted">Saldo de valor</dt>
                    <dd class="mt-1 font-mono">
                      {data.setting.currency}
                      {displayDecimal(entry.balance_value)}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-xs text-foreground-muted">Promedio resultante</dt>
                    <dd class="mt-1 font-mono">
                      {data.setting.currency}
                      {displayDecimal(entry.average_unit_cost)}
                    </dd>
                  </div>
                </dl>
                {#if entry.cost_breakdown.length}<details class="mt-3 text-sm">
                    <summary class="cursor-pointer text-primary"
                      >Ver distribución del ajuste</summary
                    >
                    <ul class="mt-2 space-y-2 text-xs text-foreground-muted">
                      {#each entry.cost_breakdown as cost}<li class="break-all">
                          {valuationKind[cost.kind ?? ''] ?? cost.kind} · {cost.source_reference ??
                            'Movimiento de origen'}{#if cost.cost_delta}: ajuste {displayDecimal(
                              cost.cost_delta
                            )}{:else}: crédito {displayDecimal(cost.credit_net ?? '0')}, costo
                            retirado {displayDecimal(cost.inventory_cost ?? '0')}, diferencia {displayDecimal(
                              cost.cost_difference ?? '0'
                            )}{/if}
                          {data.setting.currency}
                          {#if cost.ledger_page !== undefined}
                            <button
                              type="button"
                              class="ml-2 text-primary underline"
                              onclick={() =>
                                void showLedger(selected, Number(cost.ledger_page), cost.event_id)}
                              >Ver movimiento valorado #{cost.sequence}</button
                            >
                          {/if}
                          <span class="mt-1 block text-foreground-muted"
                            >Identificador: {cost.event_id}</span
                          >
                        </li>{/each}
                    </ul>
                  </details>{/if}
              </article>
            {/each}
            <div class="flex items-center justify-end gap-3">
              <Button
                size="sm"
                variant="secondary"
                disabled={ledgerPage === 0}
                onclick={() => void showLedger(selected, ledgerPage - 1)}>Anteriores</Button
              ><span class="text-sm">Página {ledgerPage + 1}</span><Button
                size="sm"
                variant="secondary"
                disabled={entries.length < 50}
                onclick={() => void showLedger(selected, ledgerPage + 1)}>Siguientes</Button
              >
            </div>
          {/if}
        </section>
      {/if}
    {/if}
  {/if}
</main>

<style>
  dd,
  .balance-table td {
    overflow-wrap: anywhere;
  }
  @media (max-width: 639px) {
    .balance-table thead {
      display: none;
    }
    .balance-table tbody {
      display: block;
    }
    .balance-table tr {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      padding: 0.75rem;
    }
    .balance-table th {
      grid-column: 1 / -1;
      max-width: none;
    }
    .balance-table th,
    .balance-table td {
      padding: 0.5rem;
      text-align: left;
    }
    .balance-table td:last-child {
      grid-column: 1 / -1;
    }
  }
</style>
