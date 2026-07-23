<script lang="ts">
  // MOCKUP — Sucursales. Datos simulados, sin llamadas a la API.
  // El mapa de OSM es real (iframe). La tabla y el detalle son mock.
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { BRANCHES, type Branch } from '$lib/features/branches/mock-data';
  import BranchTable from '$lib/features/branches/components/BranchTable.svelte';
  import BranchMap from '$lib/features/branches/components/BranchMap.svelte';
  import BranchDetail from '$lib/features/branches/components/BranchDetail.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  let showMap = $state(true);
  let selectedId = $state<string | null>(null);

  let filteredBranches = $derived.by(() => {
    const q = globalSearch.query.toLowerCase().trim();
    if (!q) return BRANCHES;
    return BRANCHES.filter(b =>
      b.name.toLowerCase().includes(q) ||
      b.code.toLowerCase().includes(q) ||
      b.city.toLowerCase().includes(q) ||
      b.manager.toLowerCase().includes(q)
    );
  });

  let selectedBranch = $derived(
    selectedId ? BRANCHES.find(b => b.id === selectedId) ?? null : null
  );

  function onSelect(id: string) {
    selectedId = selectedId === id ? null : id;
  }
</script>

<svelte:head><title>Sucursales — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{filteredBranches.length} sucursal(es)</p>
    <div class="flex items-center gap-2">
      <!-- Toggle mapa -->
      <button
        type="button"
        onclick={() => (showMap = !showMap)}
        class="flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] font-medium text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:shadow-glow"
        aria-label="Mostrar/ocultar mapa"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class={showMap ? 'text-primary' : 'text-foreground-subtle'}>
          <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" /><line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
        </svg>
        {showMap ? 'Ocultar mapa' : 'Mostrar mapa'}
      </button>
      <Button size="sm">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Crear
      </Button>
    </div>
  </div>

  <!-- Layout: tabla + (mapa | detalle) -->
  <div class="grid gap-4 {showMap ? 'lg:grid-cols-3' : 'lg:grid-cols-2'}">
    <!-- Tabla -->
    <div class="{showMap ? 'lg:col-span-2' : 'lg:col-span-1'}">
      <Card class="overflow-hidden p-0">
        <BranchTable branches={filteredBranches} {selectedId} onSelect={onSelect} />
      </Card>
    </div>

    <!-- Mapa o detalle -->
    {#if showMap}
      <div class="lg:col-span-1 flex flex-col gap-4">
        <Card class="h-[340px] overflow-hidden p-1">
          <BranchMap branches={filteredBranches} {selectedId} />
        </Card>
        <Card class="p-5">
          <BranchDetail branch={selectedBranch} />
        </Card>
      </div>
    {:else}
      <div class="lg:col-span-1">
        <Card class="p-5">
          <BranchDetail branch={selectedBranch} />
        </Card>
      </div>
    {/if}
  </div>
</div>