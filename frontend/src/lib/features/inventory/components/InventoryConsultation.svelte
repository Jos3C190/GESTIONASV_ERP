<script lang="ts">
  import WarehouseStockPanel from './WarehouseStockPanel.svelte';
  import WarehouseLocationMap from './WarehouseLocationMap.svelte';
  import WarehouseLotsPanel from './WarehouseLotsPanel.svelte';
  import ProductStockOpening from './ProductStockOpening.svelte';
  import HandlingUnitsPanel from './HandlingUnitsPanel.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  let {
    warehouseId,
    warehouseName,
    contextKey,
    canOpen = false,
    canReadPurchases = false,
    canVerify = false,
    canRelease = false,
    canReadRetaceos = false,
    canVerifyRetaceos = false,
    canTransfer = false
  }: {
    warehouseId: string;
    warehouseName: string;
    contextKey: string;
    canOpen?: boolean;
    canReadPurchases?: boolean;
    canVerify?: boolean;
    canRelease?: boolean;
    canReadRetaceos?: boolean;
    canVerifyRetaceos?: boolean;
    canTransfer?: boolean;
  } = $props();
  let section = $state('stock');
  let locationId = $state('');
  let revision = $state(0);
  const tabs = [
    { id: 'stock', label: 'Por ubicación' },
    { id: 'units', label: 'Unidades' },
    { id: 'lots', label: 'Lotes' },
    { id: 'locations', label: 'Mapa de bodega' }
  ];
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <nav class="flex flex-wrap gap-1" aria-label="Consultas de inventario">
      {#each tabs as tab}<button
          type="button"
          aria-current={section === tab.id ? 'page' : undefined}
          class="min-h-11 rounded-lg px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {section ===
          tab.id
            ? 'bg-surface-muted font-semibold text-foreground'
            : 'text-foreground-muted hover:bg-surface-hover'}"
          onclick={() => {
            section = tab.id;
            locationId = '';
          }}>{tab.label}</button
        >{/each}
    </nav>
    {#if canOpen}<Button variant="secondary" onclick={() => (section = 'opening')}
        >Registrar saldo inicial</Button
      >{/if}
  </div>
  {#key `${warehouseId}:${contextKey}:${revision}`}
    {#if section === 'stock'}<WarehouseStockPanel
        {warehouseId}
        onlocation={(id) => {
          locationId = id;
          section = 'locations';
        }}
      />
    {:else if section === 'units'}<HandlingUnitsPanel
        {warehouseId}
        {contextKey}
        {canVerify}
        {canRelease}
        {canReadRetaceos}
        {canVerifyRetaceos}
        {canTransfer}
        canPrepareSplit={canTransfer}
      />
    {:else if section === 'lots'}<WarehouseLotsPanel {warehouseId} {canReadPurchases} />
    {:else if section === 'locations'}<WarehouseLocationMap
        {warehouseId}
        initialLocationId={locationId}
      />
    {:else if section === 'opening' && canOpen}<ProductStockOpening
        {warehouseId}
        {warehouseName}
        onregistered={() => {
          /* The form keeps its confirmation visible until the user changes tabs. */
        }}
      />{/if}
  {/key}
</div>
