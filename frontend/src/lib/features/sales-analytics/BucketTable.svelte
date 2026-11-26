<script lang="ts">
  import { formatMoney, formatPercent } from '#lib/features/sales-analytics/format.ts';
  import type { AnalysisBucket } from '#lib/types/sales-analytics.ts';

  let {
    title,
    rows,
    costs,
    goals = false,
    quantity = false,
    empty = 'Sin ventas en el rango.'
  }: {
    title: string;
    rows: AnalysisBucket[];
    costs: boolean;
    goals?: boolean;
    quantity?: boolean;
    empty?: string;
  } = $props();

  const head = 'px-3 py-2 text-left text-xs font-medium uppercase text-foreground-muted';
  const cell = 'px-3 py-2 text-right tabular-nums';
</script>

<section class="overflow-x-auto rounded-xl border border-border bg-surface" aria-label={title}>
  <h2 class="px-4 pt-3 text-sm font-semibold text-foreground">{title}</h2>
  {#if rows.length === 0}
    <p class="p-4 text-sm text-foreground-muted">{empty}</p>
  {:else}
    <table class="mt-2 min-w-full text-sm">
      <thead class="bg-surface-muted">
        <tr>
          <th class={head}>Nombre</th>
          {#if quantity}<th class="{head} text-right">Cantidad</th>{/if}
          <th class="{head} text-right">Documentos</th>
          <th class="{head} text-right">Venta sin IVA</th>
          {#if costs}<th class="{head} text-right">Margen</th>{/if}
          {#if goals}<th class="{head} text-right">Meta</th>{/if}
        </tr>
      </thead>
      <tbody class="divide-y divide-border">
        {#each rows as row (row.key)}
          <tr>
            <td class="px-3 py-2 text-foreground">{row.label}</td>
            {#if quantity}<td class={cell}>{Number(row.quantity).toLocaleString('es-SV')}</td>{/if}
            <td class={cell}>{row.documents}</td>
            <td class="{cell} font-medium text-foreground">{formatMoney(row.net_sales)}</td>
            {#if costs}
              <td class={cell}
                >{formatMoney(row.margin)}
                <span class="block text-xs text-foreground-muted"
                  >{formatPercent(row.margin_percent)}</span
                ></td
              >
            {/if}
            {#if goals}
              <td class="{cell} min-w-40">
                {#if row.goal}
                  <span class="text-xs text-foreground-muted">{formatMoney(row.goal)}</span>
                  <div
                    class="mt-1 h-2 rounded-full bg-surface-muted"
                    role="progressbar"
                    aria-label="Avance de la meta de {row.label}"
                    aria-valuenow={Number(row.goal_percent ?? 0)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      class="h-2 rounded-full {Number(row.goal_percent) >= 100
                        ? 'bg-success'
                        : 'bg-primary'}"
                      style="width: {Math.min(Number(row.goal_percent ?? 0), 100)}%"
                    ></div>
                  </div>
                  <span class="text-xs text-foreground">{formatPercent(row.goal_percent)}</span>
                {:else}
                  <span class="text-xs text-foreground-muted">Sin meta</span>
                {/if}
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>
