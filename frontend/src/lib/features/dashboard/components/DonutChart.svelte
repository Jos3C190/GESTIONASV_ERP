<script lang="ts">
  /** DonutChart — dona SVG con paleta categórica propia, padAngle + cornerRadius,
   * leyenda alineada en dos columnas (cantidad + porcentaje). */

  interface Props {
    data: { label: string; value: number }[];
    size?: number;
  }

  let { data, size = 140 }: Props = $props();

  const MAX_VISIBLE_CATEGORIES = 7;

  let compactData = $derived.by(() => {
    const ordered = [...data].sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, 'es'));
    if (ordered.length <= MAX_VISIBLE_CATEGORIES) return ordered;
    const visible = ordered.slice(0, MAX_VISIBLE_CATEGORIES);
    const remaining = ordered.slice(MAX_VISIBLE_CATEGORIES);
    return [
      ...visible,
      {
        label: `Otros (${remaining.length})`,
        value: remaining.reduce((sum, item) => sum + item.value, 0)
      }
    ];
  });

  // Paleta categórica propia: derivada del azul de acento, variando luminosidad.
  // Documentada en docs/design-system.md como "paleta categórica de gráficos".
  const CHART_PALETTE = [
    '0 112 243',    // primary blue
    '59 130 246',   // blue-400
    '14 165 233',   // sky-500
    '100 116 139',  // slate-500 (neutro)
    '148 163 184',  // slate-400 (neutro claro)
  ];

  let colored = $derived(compactData.map((d, i) => ({ ...d, color: CHART_PALETTE[i % CHART_PALETTE.length] })));

  let total = $derived(colored.reduce((s, d) => s + d.value, 0) || 1);
  let stroke = 14;
  let radius = $derived(size / 2 - stroke / 2 - 6);
  let circumference = $derived(2 * Math.PI * radius);
  let padAngle = 0.04; // radianes entre segmentos
  let padLength = $derived(padAngle * radius);

  let segments = $derived.by(() => {
    let offset = 0;
    return colored.map(d => {
      const fraction = d.value / total;
      const dash = Math.max(fraction * circumference - padLength, 0);
      const seg = {
        ...d,
        dash,
        gap: circumference - dash,
        offset: -offset,
        percent: Math.round(fraction * 100),
      };
      offset += dash + padLength;
      return seg;
    });
  });
</script>

<div class="flex min-h-[140px] items-center gap-5">
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} class="flex-none" aria-label="Distribución por departamento, {total} empleados en {colored.length} departamentos">
    <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgb(var(--surface-muted))" stroke-width={stroke} />
    {#each segments as seg (seg.label)}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={`rgb(${seg.color})`}
        stroke-width={stroke}
        stroke-dasharray={`${seg.dash} ${seg.gap}`}
        stroke-dashoffset={seg.offset}
        stroke-linecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style="transition: stroke-dasharray 0.4s ease;"
      />
    {/each}
    <text x={size / 2} y={size / 2 - 2} text-anchor="middle" fill="rgb(var(--foreground))" style="font-size: 20px; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums;">{total}</text>
    <text x={size / 2} y={size / 2 + 14} text-anchor="middle" fill="rgb(var(--foreground-subtle))" style="font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em;">total</text>
  </svg>

  <div class="min-w-0 flex-1 space-y-2">
    {#each segments as seg (seg.label)}
      <div class="flex items-center gap-2.5">
        <span class="h-2.5 w-2.5 flex-none rounded-sm" style="background: rgb({seg.color});"></span>
        <span class="flex-1 truncate text-[13px] text-foreground">{seg.label}</span>
        <span class="w-8 text-right font-mono text-[13px] font-medium tabular-nums text-foreground">{seg.value}</span>
        <span class="w-9 text-right font-mono text-[12px] tabular-nums text-foreground-subtle">{seg.percent}%</span>
      </div>
    {/each}
  </div>
</div>
