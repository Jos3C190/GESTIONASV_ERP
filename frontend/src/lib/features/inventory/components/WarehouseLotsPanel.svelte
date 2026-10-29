<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '../services';
  import type { InventoryReceiptLot } from '../types';
  import { workspaceField } from '../workspace';
  import { formatMovementDate, formatMovementQuantity as qty } from '../movement-presentation';
  import { physicalKardexHref } from '../kardex';
  let {
    warehouseId,
    canReadPurchases = false
  }: { warehouseId: string; canReadPurchases?: boolean } = $props();
  let q = $state('');
  let applied = $state('');
  let page = $state(1);
  let revision = $state(0);
  let lots = $state<InventoryReceiptLot[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state('');
  $effect(() => {
    const warehouse = warehouseId;
    const number = page;
    const query = applied;
    void revision;
    let active = true;
    loading = true;
    error = '';
    lots = [];
    inventoryApi
      .listReceiptLots({ warehouseId: warehouse, status: 'all', page: number, size: 10, q: query })
      .then((data) => {
        if (active) {
          lots = data.items;
          total = data.total;
        }
      })
      .catch((cause) => {
        if (active)
          error = cause instanceof Error ? cause.message : 'No se pudieron consultar los lotes.';
      })
      .finally(() => {
        if (active) loading = false;
      });
    return () => {
      active = false;
    };
  });
</script>

<section
  class="rounded-xl border border-border bg-surface p-4 sm:p-5"
  aria-label="Lotes de recepción"
>
  <h3 class="font-semibold text-foreground">Lotes de recepción</h3>
  <p class="mt-1 text-sm text-foreground-muted">
    Identifica de qué compra provino cada producto y dónde están sus unidades actuales. Los
    registros sin recepción se conservan en Existencias.
  </p>
  <form
    class="my-4 flex flex-wrap items-end gap-3"
    onsubmit={(event) => {
      event.preventDefault();
      applied = q.trim();
      page = 1;
      revision += 1;
    }}
  >
    <label class="min-w-0 flex-1 text-sm text-foreground-muted"
      >Producto, compra o lote<input
        class={workspaceField}
        bind:value={q}
        maxlength="120"
        placeholder="Ej. Azúcar o COM-00022"
      /></label
    ><Button type="submit" disabled={loading}>Buscar lotes</Button>
  </form>
  {#if loading}<div
      role="status"
      aria-label="Consultando lotes"
      class="skeleton h-36 rounded-lg"
    ></div>
  {:else if error}<div role="alert" class="rounded-lg border border-danger/30 bg-danger/10 p-4">
      <p>{error}</p>
      <Button class="mt-3" variant="secondary" onclick={() => (revision += 1)}>Reintentar</Button>
    </div>
  {:else if !lots.length}<div class="rounded-lg border border-dashed border-border p-8 text-center">
      <p class="font-medium">Sin lotes para esta consulta</p>
      <p class="mt-2 text-sm text-foreground-muted">
        Consulta otro código o revisa las existencias sin recepción vinculada.
      </p>
      <Button
        class="mt-4"
        variant="secondary"
        onclick={() => {
          q = '';
          applied = '';
          revision += 1;
        }}>Mostrar todos</Button
      >
    </div>
  {:else}<div class="space-y-3">
      {#each lots as lot (lot.id)}<details class="group rounded-lg border border-border">
          <summary
            class="cursor-pointer rounded-lg p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            ><span class="font-mono text-sm font-semibold text-foreground">{lot.code}</span><span
              class="mt-1 block text-sm text-foreground-muted"
              >Compra {lot.purchase_code} · {formatMovementDate(lot.received_at)}</span
            ></summary
          >
          <div class="space-y-4 border-t border-border p-4">
            {#if canReadPurchases}<a
                class="text-sm text-primary underline focus-visible:ring-2 focus-visible:ring-primary"
                href={`/purchases/${lot.purchase_id}`}>Abrir compra {lot.purchase_code}</a
              >{/if}{#each lot.lines as line (line.inventory_lot_detail_id)}<div
                class="rounded-lg bg-surface-muted/40 p-4"
              >
                <p class="font-semibold">{line.product_name}</p>
                <p class="mt-1 text-xs text-foreground-muted">
                  {line.product_sku} · Recibido originalmente: {qty(line.accepted_quantity_base)}
                  {line.base_unit_symbol}
                </p>
                <ul class="mt-3 space-y-2">
                  {#each line.handling_units as unit (unit.id)}<li
                      class="flex flex-wrap justify-between gap-2 border-t border-border pt-2 text-sm"
                    >
                      <span class="min-w-0 break-all font-mono">{unit.code}</span><span
                        >{unit.location_code} · {qty(unit.quantity_base)}
                        {line.base_unit_symbol}</span
                      >
                    </li>{/each}{#if !line.handling_units.length}<li
                      class="text-sm text-foreground-muted"
                    >
                      Sin unidades abiertas en esta bodega.
                    </li>{/if}
                </ul>
                <a
                  class="mt-3 inline-block rounded text-sm text-primary underline focus-visible:ring-2 focus-visible:ring-primary"
                  href={physicalKardexHref(warehouseId, line.inventory_item_id)}
                  >Consultar movimientos del producto</a
                >
              </div>{/each}
          </div>
        </details>{/each}
    </div>
    <div
      class="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-foreground-muted"
    >
      <p>{total} lotes · Página {page}</p>
      <div class="flex gap-2">
        <Button variant="secondary" disabled={page === 1} onclick={() => (page -= 1)}
          >Anterior</Button
        ><Button variant="secondary" disabled={page * 10 >= total} onclick={() => (page += 1)}
          >Siguiente</Button
        >
      </div>
    </div>{/if}
</section>
