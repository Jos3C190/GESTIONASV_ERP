<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import type { ConsolidationEvent } from '$lib/types/purchase-consolidation';

  let { events }: { events: ConsolidationEvent[] } = $props();

  const actionLabels: Record<string, string> = {
    created: 'Consolidado creado',
    draft_updated: 'Borrador actualizado',
    cancelled: 'Borrador cancelado',
    closed: 'Consolidado cerrado'
  };

  function closureDetails(event: ConsolidationEvent) {
    if (event.action !== 'closed') return null;
    const basis = event.changes['coverage_basis'];
    const uncovered = event.changes['unawarded_lines'];
    if (basis !== 'covered_outside_consolidation' || !Array.isArray(uncovered) || uncovered.length === 0) {
      return 'Toda la demanda quedó adjudicada en este consolidado.';
    }
    const lines = uncovered
      .filter((line): line is Record<string, unknown> => typeof line === 'object' && line !== null)
      .map((line) => `${String(line['product_name'] ?? 'Producto')}: ${String(line['quantity'] ?? '—')} ${String(line['unit_name'] ?? '')}`);
    return `Registrada como cubierta fuera del consolidado: ${lines.join('; ')}.`;
  }

  function formatDate(value: string) {
    return new Intl.DateTimeFormat('es-SV', { timeZone: 'America/El_Salvador', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
  }
</script>

<Card class="overflow-hidden p-0">
  <div class="border-b border-border p-4">
    <h2 class="font-semibold text-foreground">Historial de cambios</h2>
    <p class="mt-1 text-xs text-foreground-muted">Se conserva quién actuó, cuándo y por qué; al cerrar también se registran las cantidades cubiertas fuera del consolidado.</p>
  </div>
  {#if events.length === 0}
    <p class="px-4 py-8 text-sm text-foreground-muted">Aún no hay cambios registrados.</p>
  {:else}
    <ol class="divide-y divide-border" aria-label="Cambios registrados">
      {#each [...events].reverse() as event (event.id)}
        <li class="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-sm font-medium text-foreground">{actionLabels[event.action] ?? event.action}</p>
            <p class="text-xs text-foreground-muted">{event.reason} · Usuario {event.actor_id}</p>
            {#if closureDetails(event)}<p class="text-xs text-foreground-muted">{closureDetails(event)}</p>{/if}
          </div>
          <time class="text-xs text-foreground-muted">{formatDate(event.created_at)}</time>
        </li>
      {/each}
    </ol>
  {/if}
</Card>
