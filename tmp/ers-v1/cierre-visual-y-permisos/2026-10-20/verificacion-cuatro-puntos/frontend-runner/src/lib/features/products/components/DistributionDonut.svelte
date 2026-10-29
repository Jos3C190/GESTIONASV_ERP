<script lang="ts">
  import type { ProductDistributionItem } from '$lib/api/catalog';

  interface Props {
    title: string;
    description: string;
    data: ProductDistributionItem[];
    onselect?: (id: number) => void;
    class?: string;
  }

  let { title, description, data, onselect, class: className = '' }: Props = $props();
  const palette = [
    '0 112 243',
    '59 130 246',
    '14 165 233',
    '100 116 139',
    '148 163 184',
    '34 197 94',
    '245 158 11'
  ];
  const size = 124;
  const stroke = 14;
  const radius = size / 2 - stroke / 2 - 5;
  const circumference = 2 * Math.PI * radius;

  let total = $derived(data.reduce((sum, item) => sum + item.value, 0));
  let segments = $derived.by(() => {
    let offset = 0;
    return data.map((item, index) => {
      const fraction = total > 0 ? item.value / total : 0;
      const dash = Math.max(fraction * circumference - 0.04 * radius, 0);
      const segment = {
        ...item,
        color: palette[index % palette.length],
        dash,
        gap: circumference - dash,
        offset: -offset,
        percent: total > 0 ? Math.round(fraction * 100) : 0
      };
      offset += dash + 0.04 * radius;
      return segment;
    });
  });

  function choose(item: ProductDistributionItem) {
    if (item.filterable && item.id != null) onselect?.(item.id);
  }
</script>

<div
  class={`flex h-full min-h-0 flex-col rounded-2xl border border-border bg-surface-elevated p-4 shadow-soft transition-all duration-200 hover-lift ${className}`}
>
  <div class="mb-3">
    <h2 class="text-sm font-semibold text-foreground">{title}</h2>
    <p class="mt-0.5 text-xs text-foreground-muted">{description}</p>
  </div>
  {#if total === 0}
    <div
      class="flex min-h-[132px] flex-1 items-center justify-center rounded-lg border border-dashed border-border text-xs text-foreground-muted"
    >
      Sin datos para este filtro
    </div>
  {:else}
    <div class="flex min-h-[132px] flex-1 items-center gap-3">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${title}: ${total} productos distribuidos en ${data.length} grupos`}
        class="flex-none"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--surface-muted))"
          stroke-width={stroke}
        />
        {#each segments as segment (segment.id ?? segment.label)}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={`rgb(${segment.color})`}
            stroke-width={stroke}
            stroke-dasharray={`${segment.dash} ${segment.gap}`}
            stroke-dashoffset={segment.offset}
            stroke-linecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        {/each}
        <text
          x={size / 2}
          y={size / 2 - 2}
          text-anchor="middle"
          fill="rgb(var(--foreground))"
          style="font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums;"
          >{total}</text
        >
        <text
          x={size / 2}
          y={size / 2 + 13}
          text-anchor="middle"
          fill="rgb(var(--foreground-subtle))"
          style="font-size: 8px; text-transform: uppercase; letter-spacing: 0.06em;">productos</text
        >
      </svg>
      <div class="min-w-0 flex-1 space-y-1.5">
        {#each segments as segment (segment.id ?? segment.label)}
          {#if segment.filterable}<button
              type="button"
              class="flex w-full items-center gap-2 rounded-md px-1 py-1 text-left hover:bg-surface-hover focus:outline-none focus:ring-1 focus:ring-primary"
              onclick={() => choose(segment)}
              title={`Filtrar por ${segment.label}`}
              ><span
                class="h-2.5 w-2.5 flex-none rounded-sm"
                style={`background: rgb(${segment.color});`}
              ></span><span class="min-w-0 flex-1 truncate text-xs text-foreground"
                >{segment.label}</span
              ><span class="font-mono text-xs tabular-nums text-foreground-muted"
                >{segment.value}</span
              ></button
            >{:else}<div class="flex items-center gap-2 px-1 py-1">
              <span
                class="h-2.5 w-2.5 flex-none rounded-sm"
                style={`background: rgb(${segment.color});`}
              ></span>
              <span class="min-w-0 flex-1 truncate text-xs text-foreground-muted"
                >{segment.label}</span
              >
              <span class="font-mono text-xs tabular-nums text-foreground-muted"
                >{segment.value}</span
              >
            </div>{/if}
        {/each}
      </div>
    </div>
  {/if}
</div>
