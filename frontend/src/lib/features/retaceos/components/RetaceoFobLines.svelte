<script lang="ts">
  type FobLine = { key: string; label: string; detail?: string; amount: string };

  let { lines, currency }: { lines: FobLine[]; currency: string } = $props();

  function money(amount: string): string {
    const value = Number(amount);
    if (!amount.trim() || !Number.isFinite(value)) return '—';
    return new Intl.NumberFormat('es-SV', { style: 'currency', currency }).format(value);
  }
</script>

<article class="rounded-xl border border-border bg-surface p-4" aria-labelledby="fob-lines-heading">
  <h2 id="fob-lines-heading" class="font-semibold text-foreground">
    FOB por producto (desde la factura)
  </h2>
  <p class="mt-1 max-w-prose text-sm leading-6 text-foreground-muted">
    Es el valor de la factura de compra y no se edita aquí. Con él se reparten el flete y seguro, el
    DAI y los gastos adicionales.
  </p>
  <ul class="mt-3 divide-y divide-border rounded-lg border border-border">
    {#each lines as line (line.key)}
      <li class="flex flex-col gap-1 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div class="min-w-0">
          <p class="break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
            {line.label}
          </p>
          {#if line.detail}<p class="mt-0.5 text-xs text-foreground-muted">{line.detail}</p>{/if}
        </div>
        <p class="shrink-0 text-sm font-semibold tabular-nums text-foreground">
          {money(line.amount)}
        </p>
      </li>
    {/each}
  </ul>
</article>
