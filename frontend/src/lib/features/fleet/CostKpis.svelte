<script lang="ts">
  import { formatMoney } from './catalog';

  // Sin datos se muestra "—": un $0.00 mientras carga o tras un fallo se leería como real.
  let {
    totals,
    detail,
    busy = false
  }: {
    totals: { total: string; fuel: string; maintenance: string; other: string } | null;
    detail?: string;
    busy?: boolean;
  } = $props();
</script>

<div class="kpis" class:busy aria-busy={busy}>
  <div class="tile total">
    <span>Costo total</span>
    <strong>{formatMoney(totals?.total)}</strong>
    {#if detail}<small>{detail}</small>{/if}
  </div>
  <div class="tile"><span>Combustible</span><strong>{formatMoney(totals?.fuel)}</strong></div>
  <div class="tile">
    <span>Mantenimiento</span><strong>{formatMoney(totals?.maintenance)}</strong>
  </div>
  <div class="tile"><span>Otros costos</span><strong>{formatMoney(totals?.other)}</strong></div>
</div>

<style>
  .kpis {
    display: grid;
    gap: 8px;
    transition: opacity 150ms ease;
  }
  .busy {
    opacity: 0.55;
  }
  .tile {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    min-width: 0;
    padding: 10px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .total {
    display: grid;
    gap: 4px;
    padding: 14px;
  }
  span,
  small {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  strong {
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .total strong {
    font-size: 24px;
  }
  @media (min-width: 640px) {
    .kpis {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .tile {
      display: grid;
      align-content: start;
      gap: 4px;
      padding: 14px 16px;
    }
    .total {
      grid-column: 1 / -1;
    }
    strong {
      font-size: 18px;
    }
  }
  @media (min-width: 1100px) {
    .kpis {
      grid-template-columns: 1.6fr repeat(3, minmax(0, 1fr));
    }
    .total {
      grid-column: auto;
    }
  }
</style>
