<script lang="ts">
  interface Props {
    area?: string | null;
    aisle: string;
    rack: string;
    level: string;
    position: string;
    compact?: boolean;
  }

  let { area, aisle, rack, level, position, compact = false }: Props = $props();
  let parts = $derived(
    [
      area ? { label: 'Área', value: area } : null,
      { label: 'Pasillo', value: aisle },
      { label: 'Rack', value: rack },
      { label: 'Nivel', value: level },
      { label: 'Posición', value: position }
    ].filter((part): part is { label: string; value: string } => Boolean(part?.value))
  );
</script>

<div
  class="flex flex-wrap items-center gap-1 {compact ? 'text-xs' : 'text-sm'}"
  aria-label="Ruta física"
>
  {#each parts as part, index}
    <span class="inline-flex items-center gap-1">
      {#if index > 0}<span class="text-foreground-subtle" aria-hidden="true">›</span>{/if}
      <span class="text-foreground-muted">{part.value}</span>
    </span>
  {/each}
</div>
