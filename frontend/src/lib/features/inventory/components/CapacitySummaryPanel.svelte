<script lang="ts">
  import type { CapacityMetric, CapacitySummary } from '../types';
  import { INVENTORY_CAPACITY_STATUS_LABEL } from '../types';

  interface Props {
    summary: CapacitySummary | null;
    loading?: boolean;
    error?: string | null;
  }

  let { summary, loading = false, error = null }: Props = $props();

  function number(value: number | null, unit: string): string {
    if (value == null) return 'Desconocido';
    return `${value.toLocaleString('es-SV', { maximumFractionDigits: 3 })} ${unit}`;
  }

  function percent(value: number | null): string {
    if (value == null) return 'Desconocida';
    return `${value.toLocaleString('es-SV', { maximumFractionDigits: 1 })}%`;
  }

  function width(value: number): number {
    return Math.min(100, Math.max(0, value));
  }

  function progressValue(value: number): number {
    return Math.round(width(value));
  }

  function barClass(value: number): string {
    if (value >= 90) return 'bg-danger';
    if (value >= 80) return 'bg-warning';
    return 'bg-success';
  }
</script>

{#snippet metricCard(title: string, unit: string, metric: CapacityMetric, limiting: boolean)}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-label={`Capacidad por ${title.toLowerCase()}`}
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-xs font-semibold text-foreground">{title}</p>
        <p class="mt-1 text-[11px] text-foreground-muted">
          {limiting ? 'Métrica limitante actual' : 'Control independiente'}
        </p>
      </div>
      {#if limiting}
        <span class="rounded-full bg-warning/15 px-2 py-1 text-[10px] font-semibold text-warning">
          Limitante
        </span>
      {/if}
    </div>

    <div class="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-xs sm:grid-cols-3">
      <div>
        <p class="text-foreground-subtle">Ocupado</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.occupied, unit)}
        </p>
      </div>
      <div>
        <p class="text-foreground-subtle">Reservado</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.reserved, unit)}
        </p>
      </div>
      <div>
        <p class="text-foreground-subtle">Proyectado</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.projected, unit)}
        </p>
      </div>
      <div>
        <p class="text-foreground-subtle">Disponible operativo</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.available, unit)}
        </p>
      </div>
      <div>
        <p class="text-foreground-subtle">Límite operativo</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.operational, unit)}
        </p>
      </div>
      <div>
        <p class="text-foreground-subtle">Límite certificado</p>
        <p class="mt-0.5 font-mono font-semibold text-foreground">
          {number(metric.certified, unit)}
        </p>
      </div>
    </div>

    <div class="mt-4">
      <div class="mb-1.5 flex items-center justify-between text-[11px]">
        <span class="text-foreground-muted">Utilización proyectada</span>
        <span class="font-mono font-semibold text-foreground">{percent(metric.utilizationPct)}</span
        >
      </div>
      {#if metric.utilizationPct == null}
        <div
          class="h-2 rounded-full border border-dashed border-border bg-surface-muted/30"
          role="status"
          aria-label="Utilización proyectada desconocida"
        ></div>
      {:else}
        <div
          class="h-2 overflow-hidden rounded-full bg-surface-muted"
          role="progressbar"
          aria-label={`Utilización proyectada por ${title.toLowerCase()}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={progressValue(metric.utilizationPct)}
          aria-valuetext={percent(metric.utilizationPct)}
        >
          <div
            class={`h-full rounded-full ${barClass(metric.utilizationPct)}`}
            style={`width: ${width(metric.utilizationPct)}%`}
          ></div>
        </div>
      {/if}
    </div>
  </section>
{/snippet}

{#if loading}
  <div class="grid gap-3 md:grid-cols-2" role="status" aria-label="Cargando capacidad física">
    <span class="sr-only">Cargando capacidad física…</span>
    <div class="h-64 rounded-xl skeleton"></div>
    <div class="h-64 rounded-xl skeleton"></div>
  </div>
{:else if error}
  <div
    class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
    role="alert"
  >
    {error}
  </div>
{:else if summary}
  <div class="space-y-3">
    <div
      class="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between {summary.status ===
      'over_certified'
        ? 'border-danger/50 bg-danger/10'
        : 'border-border bg-surface-muted/20'}"
    >
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-sm font-semibold text-foreground">Ocupación física proyectada</h3>
          <span
            class="rounded-full border px-2 py-1 text-[10px] font-semibold {summary.status ===
            'over_certified'
              ? 'border-danger/50 bg-danger/15 text-danger'
              : 'border-border bg-surface text-foreground-muted'}"
          >
            {INVENTORY_CAPACITY_STATUS_LABEL[summary.status]}
          </span>
        </div>
        <p class="mt-1 text-xs text-foreground-muted">
          Ocupado + reservas vigentes; peso y volumen no se promedian.
        </p>
      </div>
      <div class="sm:text-right">
        <p class="font-mono text-lg font-bold text-foreground">
          {percent(summary.effectiveUtilizationPct)}
        </p>
        <p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
          Mayor utilización conocida
        </p>
      </div>
    </div>

    {#if summary.status === 'over_certified'}
      <div
        class="rounded-xl border-2 border-danger bg-danger/15 px-4 py-3 text-danger"
        role="alert"
        aria-live="assertive"
      >
        <p class="text-xs font-bold uppercase tracking-wide">Peligro de seguridad</p>
        <p class="mt-1 text-xs font-medium leading-5">
          La carga proyectada supera un límite certificado. Ninguna excepción operativa autoriza
          este exceso. Detenga nuevos ingresos y ejecute la descarga o reubicación definida por el
          responsable de seguridad.
        </p>
      </div>
    {/if}

    {#if summary.measurementStatus === 'incomplete'}
      <div
        class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning"
        role="status"
      >
        Hay {summary.unmeasuredHandlingUnits} unidad(es) logística(s) y {summary.unmeasuredReservations}
        reserva(s) sin medición completa. Los valores desconocidos no se muestran como cero.
      </div>
    {/if}

    <div class="grid gap-3 md:grid-cols-2">
      {@render metricCard('Peso', 'kg', summary.weight, summary.limitingMetric === 'weight')}
      {@render metricCard(
        'Volumen útil',
        'm³',
        summary.volume,
        summary.limitingMetric === 'volume'
      )}
    </div>
  </div>
{:else}
  <div class="rounded-xl border border-dashed border-border p-6 text-center">
    <p class="text-sm font-medium text-foreground">Capacidad no disponible</p>
    <p class="mt-1 text-xs text-foreground-muted">
      No fue posible cargar la ocupación física del almacén.
    </p>
  </div>
{/if}
