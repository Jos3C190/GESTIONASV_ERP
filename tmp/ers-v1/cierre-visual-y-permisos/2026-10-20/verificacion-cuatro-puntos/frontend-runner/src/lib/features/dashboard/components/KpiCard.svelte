<script lang="ts">
  /** KpiCard — tarjeta de KPI con sparkline SVG suave, icono tintado semántico,
   * y TrendBadge con tres estados: positivo (verde), negativo (rojo), neutro (gris). */

  interface Props {
    label: string;
    value: number;
    prefix?: string;
    suffix?: string;
    change: number;
    sparkline: number[];
    icon: string;
  }

  let { label, value, prefix = '', suffix = '', change, sparkline, icon }: Props = $props();

  // Estado de tendencia: positivo, negativo, o neutro (0% o ~0%)
  let trendState = $derived.by(() => {
    if (Math.abs(change) < 0.1) return 'neutral';
    return change > 0 ? 'positive' : 'negative';
  });

  let trendColorRgb = $derived(trendState === 'positive' ? '0 168 107' : trendState === 'negative' ? '239 68 68' : '100 116 139');
  let trendBg = $derived(trendState === 'positive' ? 'badge-success' : trendState === 'negative' ? 'badge-danger' : 'badge-neutral');

  // Sparkline: Catmull-Rom suave + gradiente del color de tendencia
  const SW = 80;
  const SH = 24;

  let sparkPath = $derived.by(() => {
    const max = Math.max(...sparkline);
    const min = Math.min(...sparkline);
    const range = max - min || 1;
    const step = SW / (sparkline.length - 1);
    const pts = sparkline.map((v, i) => [i * step, SH - ((v - min) / range) * SH] as [number, number]);
    if (pts.length < 2) return '';
    let path = `M${pts[0]![0].toFixed(1)},${pts[0]![1].toFixed(1)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i]!;
      const p1 = pts[i]!;
      const p2 = pts[i + 1]!;
      const p3 = pts[i + 2] || p2;
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      path += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
    }
    return path;
  });

  let sparkArea = $derived(`${sparkPath} L${SW},${SH} L0,${SH} Z`);
  let sparkId = $derived(`spark-${label.replace(/\s/g, '')}`);
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-5 transition-all duration-150 hover-lift">
  <div class="flex items-start justify-between">
    <div>
      <p class="text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">{label}</p>
      <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">
        {prefix}{value.toLocaleString()}{suffix}
      </p>
    </div>
    <!-- Icono tintado semántico, no gris plano -->
    <div class="flex h-8 w-8 flex-none items-center justify-center rounded-lg" style="background: rgb({trendState === 'positive' ? '0 168 107' : trendState === 'negative' ? '239 68 68' : '100 116 139'} / 0.1);">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="color: rgb({trendColorRgb});"><path d={icon} /></svg>
    </div>
  </div>

  <div class="mt-3 flex items-end justify-between gap-2">
    <!-- TrendBadge: positivo/negativo/neutro -->
    <div class="flex items-center gap-1.5">
      <span class="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-semibold {trendBg}">
        {#if trendState === 'positive'}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M7 17L17 7M17 7H8M17 7v9" /></svg>
          {change}%
        {:else if trendState === 'negative'}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M17 7L7 17M7 17h9M7 17V8" /></svg>
          {Math.abs(change)}%
        {:else}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M5 12h14" /></svg>
          sin cambios
        {/if}
      </span>
      {#if trendState !== 'neutral'}
        <span class="text-[11px] text-foreground-subtle">vs. mes anterior</span>
      {/if}
    </div>

    <!-- Sparkline suave con gradiente del color de tendencia -->
    <svg width={SW} height={SH} viewBox={`0 0 ${SW} ${SH}`} class="flex-none" aria-hidden="true">
      <defs>
        <linearGradient id={sparkId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color={`rgb(${trendColorRgb})`} stop-opacity="0.25" />
          <stop offset="100%" stop-color={`rgb(${trendColorRgb})`} stop-opacity="0" />
        </linearGradient>
      </defs>
      <path d={sparkArea} fill={`url(#${sparkId})`} />
      <path d={sparkPath} fill="none" stroke={`rgb(${trendColorRgb})`} stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </div>
</div>