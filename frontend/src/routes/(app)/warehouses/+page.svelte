<script lang="ts">
  // MOCKUP — Almacenes. Datos simulados, sin llamadas a la API.
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import {
    WAREHOUSES, STATUS_MAP, utilizationPct, utilizationColor,
    type Warehouse,
  } from '$lib/features/warehouses/mock-data';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  let branchFilter = $state('');

  let filtered = $derived.by(() => {
    const q = globalSearch.query.toLowerCase().trim();
    let result = WAREHOUSES;
    if (q) {
      result = result.filter(w =>
        w.name.toLowerCase().includes(q) ||
        w.code.toLowerCase().includes(q) ||
        w.branchName.toLowerCase().includes(q)
      );
    }
    if (branchFilter) result = result.filter(w => w.branchId === branchFilter);
    return result;
  });

  let branches = $derived(
    Array.from(
      new Map(WAREHOUSES.map(w => [w.branchId, { id: w.branchId, name: w.branchName }])).values()
    )
  );
</script>

<svelte:head><title>Almacenes — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{filtered.length} almacén(es)</p>
    <div class="flex items-center gap-2">
      <select bind:value={branchFilter} class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none">
        <option value="">Todas las sucursales</option>
        {#each branches as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
      </select>
      <Button size="sm">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Crear
      </Button>
    </div>
  </div>

  <!-- KPIs de capacidad -->
  <div class="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
    {#each [
      { label: 'Capacidad total', value: WAREHOUSES.reduce((s, w) => s + w.capacity, 0), suffix: ' u' },
      { label: 'Ocupado', value: WAREHOUSES.reduce((s, w) => s + w.used, 0), suffix: ' u' },
      { label: 'Productos', value: WAREHOUSES.reduce((s, w) => s + w.products, 0), suffix: '' },
      { label: 'Almacenes activos', value: WAREHOUSES.filter(w => w.status === 'active').length, suffix: '' },
    ] as kpi (kpi.label)}
      <div class="rounded-xl border border-border bg-surface-elevated p-5">
        <p class="text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">{kpi.label}</p>
        <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">{kpi.value.toLocaleString()}{kpi.suffix}</p>
      </div>
    {/each}
  </div>

  <!-- Tabla -->
  <Card class="overflow-hidden p-0">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border">
            <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Almacén</th>
            <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Sucursal</th>
            <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Ubicación</th>
            <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Estado</th>
            <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Capacidad</th>
            <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Productos</th>
            <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Últ. movimiento</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as wh (wh.id)}
            <tr class="border-b border-border/50 transition-colors hover:bg-surface-hover/50">
              <td class="px-3 py-2.5">
                <div class="flex items-center gap-2">
                  <div class="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-surface-muted">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-foreground-subtle">
                      <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-[13px] font-medium text-foreground">{wh.name}</p>
                    <p class="font-mono text-[10px] text-foreground-subtle">{wh.code}</p>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2.5 text-[13px] text-foreground-muted">{wh.branchName}</td>
              <td class="px-3 py-2.5 text-[13px] text-foreground-muted">{wh.location}</td>
              <td class="px-3 py-2.5">
                <Badge variant={STATUS_MAP[wh.status].variant}>{STATUS_MAP[wh.status].label}</Badge>
              </td>
              <td class="px-3 py-2.5">
                {@render UtilizationBar(wh)}
              </td>
              <td class="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums text-foreground">{wh.products.toLocaleString()}</td>
              <td class="px-3 py-2.5 text-right text-[12px] text-foreground-subtle">{wh.lastMovement}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </Card>
</div>

{#snippet UtilizationBar(wh: Warehouse)}
  {@const pct = utilizationPct(wh)}
  {@const color = utilizationColor(pct)}
  <div class="flex items-center gap-2">
    <div class="flex-1">
      <div class="h-1.5 w-24 overflow-hidden rounded-full bg-surface-muted">
        <div class="h-full rounded-full transition-all" style="width: {pct}%; background: rgb({color});"></div>
      </div>
    </div>
    <span class="font-mono text-[11px] tabular-nums text-foreground-muted">{wh.used.toLocaleString()}/{wh.capacity.toLocaleString()}</span>
    <span class="font-mono text-[11px] tabular-nums font-medium" style="color: rgb({color});">{pct}%</span>
  </div>
{/snippet}