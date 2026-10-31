<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import type { ConsolidationLine, PurchaseConsolidationInventorySnapshot } from '$lib/types/purchase-consolidation';

  interface Props {
    lines: ConsolidationLine[];
    snapshot: PurchaseConsolidationInventorySnapshot | null;
    warehouseId: string;
    savedWarehouseId: string;
    warehouseName: string | null;
    loading: boolean;
    onRefresh: () => Promise<void>;
  }

  let { lines, snapshot, warehouseId, savedWarehouseId, warehouseName, loading, onRefresh }: Props = $props();

  function formatDate(value: string) {
    return new Intl.DateTimeFormat('es-SV', { timeZone: 'America/El_Salvador', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
  }

  function formatQuantity(value: string | number) {
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
  }
</script>

<Card class="mb-4 p-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h2 class="font-semibold text-foreground">Existencias actuales en bodega central</h2>
      <p class="mt-1 text-xs text-foreground-muted">Consulta puntual de Inventario. Las cantidades se muestran en la unidad base del producto.</p>
    </div>
    <Button size="sm" variant="secondary" disabled={!warehouseId || warehouseId !== savedWarehouseId || loading} onclick={onRefresh}>
      {loading ? 'Consultando…' : 'Consultar / actualizar'}
    </Button>
  </div>

  {#if !warehouseId}
    <p class="mt-3 text-sm text-foreground-muted">Selecciona una bodega central para consultar sus saldos.</p>
  {:else if warehouseId !== savedWarehouseId}
    <p class="mt-3 text-sm text-warning">Guarda primero el cambio de bodega central para consultar el destino correcto.</p>
  {:else if snapshot}
    <p class="mt-3 text-xs text-foreground-muted">
      Bodega: {warehouseName ?? 'Bodega central'} · Consultado {formatDate(snapshot.checked_at)}.
      No se convierten unidades y no se descuentan reservas de demanda ni órdenes de compra.
    </p>
    {#if snapshot.items.length === 0}
      <p class="mt-3 rounded-lg border border-border bg-surface-muted px-4 py-6 text-center text-sm text-foreground-muted" role="status">No hay existencias registradas para los productos de este consolidado en esta bodega.</p>
    {:else}
      <div class="mt-3 hidden overflow-x-auto rounded-lg border border-border lg:block">
        <table class="w-full min-w-[850px] text-xs">
          <thead class="bg-surface-muted text-left text-foreground-muted">
            <tr>
              <th scope="col" class="px-3 py-2">Producto</th><th scope="col" class="px-3 py-2">Unidad base</th>
              <th scope="col" class="px-3 py-2 text-right">Disponible</th><th scope="col" class="px-3 py-2 text-right">En tránsito</th>
              <th scope="col" class="px-3 py-2 text-right">Cuarentena</th><th scope="col" class="px-3 py-2 text-right">Bloqueado</th>
              <th scope="col" class="px-3 py-2 text-right">Dañado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each lines as line (line.id)}
              {@const stock = snapshot.items.find((entry) => entry.product_id === line.product_id)}
              <tr>
                <td class="px-3 py-2 font-medium text-foreground">{line.product_sku} · {line.product_name}</td>
                {#if stock?.inventory_item_id}
                  <td class="px-3 py-2 text-foreground-muted">{stock.base_unit_name ?? `Unidad ${stock.base_unit_id}`}</td>
                  <td class="px-3 py-2 text-right font-mono">{formatQuantity(stock.available_quantity)}</td>
                  <td class="px-3 py-2 text-right font-mono">{formatQuantity(stock.in_transit_quantity)}</td>
                  <td class="px-3 py-2 text-right font-mono">{formatQuantity(stock.quarantine_quantity)}</td>
                  <td class="px-3 py-2 text-right font-mono">{formatQuantity(stock.blocked_quantity)}</td>
                  <td class="px-3 py-2 text-right font-mono">{formatQuantity(stock.damaged_quantity)}</td>
                {:else}
                  <td colspan="6" class="px-3 py-2 text-warning">
                    No está vinculado a un artículo activo de Inventario; por eso no se puede consultar su saldo en esta bodega.
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <ul class="mt-3 space-y-2 lg:hidden">
        {#each lines as line (line.id)}
          {@const stock = snapshot.items.find((entry) => entry.product_id === line.product_id)}
          <li class="rounded-lg border border-border p-3">
            <p class="text-sm font-medium text-foreground">{line.product_sku} · {line.product_name}</p>
            {#if stock?.inventory_item_id}
              <p class="mt-1 text-xs text-foreground-muted">Unidad base: {stock.base_unit_name ?? `Unidad ${stock.base_unit_id}`}</p>
              <dl class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                <div><dt class="text-foreground-muted">Disponible</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(stock.available_quantity)}</dd></div>
                <div><dt class="text-foreground-muted">En tránsito</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(stock.in_transit_quantity)}</dd></div>
                <div><dt class="text-foreground-muted">Cuarentena</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(stock.quarantine_quantity)}</dd></div>
                <div><dt class="text-foreground-muted">Bloqueado</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(stock.blocked_quantity)}</dd></div>
                <div><dt class="text-foreground-muted">Dañado</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(stock.damaged_quantity)}</dd></div>
              </dl>
            {:else}
              <p class="mt-2 text-xs text-warning" role="status">
                Este producto no está vinculado a un artículo activo de Inventario. Sin esa vinculación no se puede consultar su saldo en esta bodega.
              </p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {:else}
    <p class="mt-3 text-sm text-foreground-muted">Consulta las existencias cuando las necesites para planificar el borrador.</p>
  {/if}
</Card>
