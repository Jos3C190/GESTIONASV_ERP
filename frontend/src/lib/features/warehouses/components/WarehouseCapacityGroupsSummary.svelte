<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import {
    getCapacityConfigurationDiagnostics,
    listCapacityGroups
  } from '../capacity-groups.service';
  import type {
    CapacityConfigurationIssue,
    WarehouseCapacityGroup
  } from '../capacity-groups.types';

  interface Props {
    warehouseId: string;
    canViewLocations?: boolean;
  }

  let { warehouseId, canViewLocations = false }: Props = $props();

  let groups = $state<WarehouseCapacityGroup[]>([]);
  let issues = $state<CapacityConfigurationIssue[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let loadedWarehouseId = $state('');

  let activeCount = $derived(groups.filter((group) => group.isActive).length);
  let inactiveCount = $derived(groups.length - activeCount);

  $effect(() => {
    if (!warehouseId || loadedWarehouseId === warehouseId) return;
    loadedWarehouseId = warehouseId;
    void loadSummary(warehouseId);
  });

  async function loadSummary(requestedWarehouseId = warehouseId) {
    loading = true;
    error = null;
    try {
      const [loadedGroups, diagnostics] = await Promise.all([
        listCapacityGroups(requestedWarehouseId),
        getCapacityConfigurationDiagnostics(requestedWarehouseId)
      ]);
      if (requestedWarehouseId !== warehouseId) return;
      groups = loadedGroups;
      issues = diagnostics.issues;
    } catch (cause) {
      if (requestedWarehouseId === warehouseId) {
        error =
          cause instanceof HttpError
            ? cause.message
            : 'No se pudo cargar el resumen de estructuras y límites.';
      }
    } finally {
      if (requestedWarehouseId === warehouseId) loading = false;
    }
  }
</script>

<Card class="overflow-hidden">
  <div class="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
    <div class="min-w-0">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">Estructuras y límites compartidos</h3>
        {#if !loading}
          <Badge variant="neutral">{activeCount} activas</Badge>
          {#if inactiveCount > 0}<Badge variant="neutral">{inactiveCount} inactivas</Badge>{/if}
        {/if}
      </div>
      <p class="mt-1 max-w-2xl text-xs leading-5 text-foreground-muted">
        Las estructuras agrupan ubicaciones que comparten límites físicos. La mercancía siempre se
        guarda en una ubicación.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2 sm:shrink-0">
      <a
        href={`/warehouses/${warehouseId}/structures`}
        class="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border bg-surface-elevated px-3 text-xs font-medium text-foreground shadow-soft transition-colors hover:border-border-strong hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
      >
        Ver estructuras y límites
      </a>
      {#if canViewLocations}<a
          href={`/warehouses/${warehouseId}/locations`}
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border bg-surface-elevated px-3 text-xs font-medium text-foreground shadow-soft transition-colors hover:border-border-strong hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          Ver ubicaciones
        </a>{/if}
    </div>
  </div>

  <div class="border-t border-border px-5 py-4">
    {#if loading}
      <div class="grid gap-3 sm:grid-cols-3" aria-label="Cargando resumen de estructuras">
        {#each Array(3) as _}
          <div class="h-16 rounded-lg skeleton"></div>
        {/each}
      </div>
    {:else if error}
      <div
        class="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        role="alert"
      >
        <p class="text-xs text-danger">{error}</p>
        <Button variant="secondary" size="sm" onclick={() => void loadSummary()}>Reintentar</Button>
      </div>
    {:else}
      <div class="grid gap-3 sm:grid-cols-3">
        <div class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2.5">
          <p class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle">
            Estructuras activas
          </p>
          <p class="mt-1 font-mono text-lg font-semibold text-foreground">{activeCount}</p>
          <p class="text-[11px] text-foreground-muted">Disponibles para nuevas asignaciones</p>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2.5">
          <p class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle">
            Estructuras inactivas
          </p>
          <p class="mt-1 font-mono text-lg font-semibold text-foreground">{inactiveCount}</p>
          <p class="text-[11px] text-foreground-muted">Conservadas para consulta histórica</p>
        </div>
        <div
          class="rounded-lg border px-3 py-2.5 {issues.length > 0
            ? 'border-warning/30 bg-warning/10'
            : 'border-success/20 bg-success/5'}"
        >
          <p
            class="text-[10px] font-bold uppercase tracking-wide {issues.length > 0
              ? 'text-warning'
              : 'text-foreground-subtle'}"
          >
            Avisos de configuración
          </p>
          <p
            class="mt-1 font-mono text-lg font-semibold {issues.length > 0
              ? 'text-warning'
              : 'text-foreground'}"
          >
            {issues.length}
          </p>
          <p class="text-[11px] {issues.length > 0 ? 'text-warning/90' : 'text-foreground-muted'}">
            {issues.length > 0 ? 'Revisar antes de cambiar límites' : 'Sin incidencias detectadas'}
          </p>
        </div>
      </div>
    {/if}
  </div>
</Card>
