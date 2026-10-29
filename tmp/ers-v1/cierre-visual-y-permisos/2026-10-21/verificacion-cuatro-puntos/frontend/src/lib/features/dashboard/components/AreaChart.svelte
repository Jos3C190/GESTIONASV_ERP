<script lang="ts">
  /** AreaChart — gráfico de área SVG responsivo con curva suave (Catmull-Rom),
   * ticks Y bonitos, gradiente real, crosshair + tooltip, animación al montar. */

  interface Props {
    data: { date: string; value: number }[];
    label: string;
    height?: number;
  }

  let { data, label, height = 200 }: Props = $props();

  let hovered = $state<number | null>(null);
  let containerEl: HTMLElement | null = $state(null);
  let containerW = $state(600);
  let animated = $state(false);

  let H = $derived(height);
  const PAD = { top: 12, right: 12, bottom: 28, left: 40 };

  // Medir ancho real del contenedor
  $effect(() => {
    if (!containerEl) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        containerW = Math.max(e.contentRect.width, 200);
      }
    });
    ro.observe(containerEl);
    return () => ro.disconnect();
  });

  let W = $derived(containerW);
  let chartW = $derived(W - PAD.left - PAD.right);
  let chartH = $derived(H - PAD.top - PAD.bottom);

  function niceTicks(min: number, max: number, count: number): number[] {
    const range = max - min;
    if (range === 0) return [min];
    const rawStep = range / count;
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const normalized = rawStep / magnitude;
    let step: number;
    if (normalized < 1.5) step = 1 * magnitude;
    else if (normalized < 3) step = 2 * magnitude;
    else if (normalized < 7) step = 5 * magnitude;
    else step = 10 * magnitude;
    const niceMin = Math.floor(min / step) * step;
    const niceMax = Math.ceil(max / step) * step;
    const ticks: number[] = [];
    for (let v = niceMin; v <= niceMax; v += step) ticks.push(v);
    return ticks;
  }

  let dataMin = $derived(Math.min(...data.map(d => d.value)));
  let dataMax = $derived(Math.max(...data.map(d => d.value)));
  let ticks = $derived(niceTicks(dataMin * 0.9, dataMax * 1.1, 4));
  let yMin = $derived(ticks[0] ?? 0);
  let yMax = $derived(ticks[ticks.length - 1] ?? 0);
  let yRange = $derived((yMax ?? 0) - (yMin ?? 0) || 1);

  let stepX = $derived(chartW / Math.max(data.length - 1, 1));

  function x(i: number): number { return PAD.left + i * stepX; }
  function y(v: number): number { return PAD.top + chartH - ((v - yMin) / yRange) * chartH; }

  let linePath = $derived.by(() => {
    const pts = data.map((d, i) => [x(i), y(d.value)] as [number, number]);
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

  let areaPath = $derived(`${linePath} L${x(data.length - 1)},${PAD.top + chartH} L${x(0)},${PAD.top + chartH} Z`);

  let xLabels = $derived.by(() => {
    const n = data.length;
    const indices = n <= 7 ? data.map((_, i) => i) : [0, Math.floor(n / 4), Math.floor(n / 2), Math.floor(n * 3 / 4), n - 1];
    return indices.map(i => ({
      x: x(i),
      label: new Date(data[i]?.date ?? '').toLocaleDateString('es-SV', { day: '2-digit', month: 'short' }),
    }));
  });

  function onMove(e: MouseEvent) {
    if (!containerEl) return;
    const rect = containerEl.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const idx = Math.round((mouseX - PAD.left) / stepX);
    hovered = Math.max(0, Math.min(data.length - 1, idx));
  }

  let hoverX = $derived(hovered !== null ? x(hovered) : 0);
  let hoverY = $derived(hovered !== null ? y(data[hovered]?.value ?? 0) : 0);

  let prefersReduced = $state(false);
  $effect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    prefersReduced = mq.matches;
    const fn = () => (prefersReduced = mq.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  });

  let pathLength = $derived(linePath ? 2000 : 0);
  $effect(() => {
    if (prefersReduced) { animated = true; return; }
    animated = false;
    let frame = 0;
    frame = requestAnimationFrame(() => {
      const start = performance.now();
      const dur = 700;
      function tick(now: number) {
        const p = Math.min((now - start) / dur, 1);
        animated = p >= 1;
        if (p < 1) frame = requestAnimationFrame(tick);
      }
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  });

  let strokeDashoffset = $derived(prefersReduced ? 0 : (animated ? 0 : pathLength));
</script>

<div class="relative w-full" bind:this={containerEl} onmousemove={onMove} onmouseleave={() => hovered = null} role="figure" aria-label="{label}: tendencia de {data.length} días, valores entre {Math.round(yMin ?? 0)} y {Math.round(yMax ?? 0)}">
  <svg viewBox={`0 0 ${W} ${H}`} class="w-full" style="height: {H}px; display: block;" aria-hidden="true">
    <defs>
      <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="rgb(var(--primary))" stop-opacity="0.22" />
        <stop offset="60%" stop-color="rgb(var(--primary))" stop-opacity="0.06" />
        <stop offset="100%" stop-color="rgb(var(--primary))" stop-opacity="0" />
      </linearGradient>
    </defs>

    {#each ticks as t, i (i)}
      <line x1={PAD.left} y1={y(t)} x2={PAD.left + chartW} y2={y(t)} stroke="rgb(var(--foreground))" stroke-width="1" stroke-opacity="0.06" />
      <text x={PAD.left - 8} y={y(t) + 3} text-anchor="end" fill="rgb(var(--foreground-subtle))" style="font-size: 10px; font-variant-numeric: tabular-nums;">{Math.round(t)}</text>
    {/each}

    <path d={areaPath} fill="url(#area-fill)" />

    <path
      d={linePath}
      fill="none"
      stroke="rgb(var(--primary))"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-dasharray={pathLength}
      stroke-dashoffset={strokeDashoffset}
    />

    {#each xLabels as xl (xl.label)}
      <text x={xl.x} y={H - 8} text-anchor="middle" fill="rgb(var(--foreground-subtle))" style="font-size: 10px;">{xl.label}</text>
    {/each}

    {#if hovered !== null}
      <line x1={hoverX} y1={PAD.top} x2={hoverX} y2={PAD.top + chartH} stroke="rgb(var(--primary))" stroke-width="1" stroke-opacity="0.4" stroke-dasharray="3,3" />
      <circle cx={hoverX} cy={hoverY} r="4" fill="rgb(var(--primary))" stroke="rgb(var(--surface-elevated))" stroke-width="2" />
    {/if}
  </svg>

  {#if hovered !== null}
    <div class="pointer-events-none absolute z-10 rounded-lg border border-border bg-surface-elevated px-3 py-2 shadow-lifted" style="left: {hoverX}px; top: {hoverY}px; transform: translate(-50%, -130%);">
      <p class="text-[10px] text-foreground-subtle">{new Date(data[hovered]?.date ?? '').toLocaleDateString('es-SV', { day: 'numeric', month: 'short' })}</p>
      <p class="font-mono text-sm font-bold tabular-nums text-foreground">{data[hovered]?.value.toLocaleString() ?? ''}</p>
    </div>
  {/if}
</div>
