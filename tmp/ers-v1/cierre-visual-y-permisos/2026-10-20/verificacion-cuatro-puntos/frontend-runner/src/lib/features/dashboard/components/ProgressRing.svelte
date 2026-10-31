<script lang="ts">
  /** ProgressRing — anillo de progreso SVG con color dinámico según umbral.
   * >70% verde, 40-70% ámbar, <40% rojo. */

  interface Props {
    value: number; // 0-100
    size?: number;
    label: string;
  }

  let { value, size = 120, label }: Props = $props();

  let stroke = 8;
  let radius = $derived(size / 2 - stroke / 2 - 4);
  let circumference = $derived(2 * Math.PI * radius);
  let dash = $derived((value / 100) * circumference);

  let colorRgb = $derived.by(() => {
    if (value > 70) return '0 168 107';
    if (value >= 40) return '237 151 39';
    return '239 68 68';
  });
</script>

<div class="flex flex-col items-center">
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label="{label}: {value}%">
    <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgb(var(--border))" stroke-width={stroke} />
    <circle
      cx={size / 2}
      cy={size / 2}
      r={radius}
      fill="none"
        stroke={`rgb(${colorRgb})`}
      stroke-width={stroke}
      stroke-dasharray={`${dash} ${circumference}`}
      stroke-dashoffset={circumference / 4}
      stroke-linecap="round"
      transform={`rotate(-90 ${size / 2} ${size / 2})`}
      style="transition: stroke-dasharray 0.3s ease;"
    />
    <text x={size / 2} y={size / 2 + 2} text-anchor="middle" class="fill-foreground font-mono" style="font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums;">{value}%</text>
  </svg>
  <p class="mt-2 text-[11px] text-foreground-subtle">{label}</p>
</div>