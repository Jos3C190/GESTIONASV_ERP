<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import type { CapacitySummary } from '../types';

  interface Props {
    summary: CapacitySummary | null;
    loading?: boolean;
    error?: string | null;
  }

  let { summary, loading = false, error = null }: Props = $props();

  function value(amount: number | null, unit: string): string {
    return amount == null
      ? 'Desconocido'
      : `${amount.toLocaleString('es-SV', { maximumFractionDigits: 3 })} ${unit}`;
  }

  function percent(amount: number | null): string {
    return amount == null
      ? 'Desconocida'
      : `${amount.toLocaleString('es-SV', { maximumFractionDigits: 1 })}%`;
  }

  function scopeLabel(scopeType: string): string {
    if (scopeType === 'location') return 'Ubicación';
    if (scopeType === 'capacity_group') return 'Estructura compartida';
    return 'Almacén';
  }
</script>

{#if loading}
  <div class="space-y-2" role="status" aria-label="Cargando ruta de capacidad">
    {#each Array(3) as _}<div class="skeleton h-24 rounded-xl"></div>{/each}
  </div>
{:else if error}
  <div
    class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-xs text-danger"
    role="alert"
  >
    {error}
  </div>
{:else if summary && summary.scopePath.length > 0}
  <div class="space-y-2" aria-label="Ruta de capacidad aplicable">
    {#each summary.scopePath as scope, index (scope.scopeId)}
      <article
        class="rounded-xl border p-3 {summary.limitingScope?.scopeId === scope.scopeId
          ? 'border-warning/50 bg-warning/5'
          : 'border-border bg-surface'}"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle">
            {index + 1}. {scopeLabel(scope.scopeType)}
          </span>
          <span class="font-mono text-xs font-semibold text-foreground">{scope.code}</span>
          <span class="text-xs text-foreground-muted">{scope.name}</span>
          {#if summary.limitingScope?.scopeId === scope.scopeId}
            <Badge variant="warning">Cuello de botella</Badge>
          {/if}
          {#if scope.measurementStatus === 'incomplete'}
            <Badge variant="warning">Medición incompleta</Badge>
          {/if}
        </div>
        <div class="mt-2 grid gap-2 text-xs sm:grid-cols-2">
          <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
            <p class="font-semibold text-foreground">
              Peso · {percent(scope.weight.utilizationPct)}
            </p>
            <p class="mt-1 text-foreground-muted">
              Ocupado {value(scope.weight.occupied, 'kg')} · reservado
              {value(scope.weight.reserved, 'kg')}
            </p>
            <p class="mt-0.5 text-foreground-muted">
              Proyectado {value(scope.weight.projected, 'kg')} / operativo
              {value(scope.weight.operational, 'kg')}
            </p>
          </div>
          <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
            <p class="font-semibold text-foreground">
              Volumen · {percent(scope.volume.utilizationPct)}
            </p>
            <p class="mt-1 text-foreground-muted">
              Ocupado {value(scope.volume.occupied, 'm³')} · reservado
              {value(scope.volume.reserved, 'm³')}
            </p>
            <p class="mt-0.5 text-foreground-muted">
              Proyectado {value(scope.volume.projected, 'm³')} / operativo
              {value(scope.volume.operational, 'm³')}
            </p>
          </div>
        </div>
      </article>
    {/each}
    {#if summary.scopePath.some((scope) => scope.measurementStatus === 'incomplete')}
      <p class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
        No se declara un cuello de botella definitivo mientras algún alcance tenga mediciones
        desconocidas.
      </p>
    {/if}
  </div>
{:else}
  <p class="rounded-xl border border-dashed border-border px-4 py-3 text-xs text-foreground-muted">
    La ruta de ocupación estará disponible cuando la ubicación haya sido guardada.
  </p>
{/if}
