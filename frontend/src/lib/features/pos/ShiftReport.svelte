<script lang="ts">
  /**
   * Informe del turno en formato de rollo: X mientras el turno sigue (corte sin cerrar) y Z al
   * aprobarse el cierre. Solo se arma con el esperado a la vista (supervisor o turno cerrado).
   */
  import './receipt.css';
  import type { PosShiftDetail, PosShiftTotals } from '#lib/types/pos.ts';
  import { MOVEMENT_KIND, formatDateTime, formatMoney } from './format.ts';

  interface Props {
    detail: PosShiftDetail;
    totals: PosShiftTotals;
    companyName: string;
    printedAt?: Date;
    node?: HTMLElement | null;
  }

  let {
    detail,
    totals,
    companyName,
    printedAt = new Date(),
    node = $bindable(null)
  }: Props = $props();

  const shift = $derived(detail.shift);
  const closed = $derived(shift.status === 'closed');
  const lastClosing = $derived(detail.counts.filter((count) => count.kind === 'closing').at(-1));
  const difference = $derived(
    shift.counted_cash === null ? null : Number(shift.counted_cash) - Number(totals.expected_cash)
  );

  function differenceLabel(value: number): string {
    if (Math.abs(value) < 0.005) return 'Cuadra';
    return value > 0 ? 'Sobrante' : 'Faltante';
  }
</script>

<div class="rc" bind:this={node} data-testid="shift-report">
  <div class="rc-brand">{companyName}</div>
  <div class="rc-center rc-muted">{shift.branch_name}</div>
  <div class="rc-title">{closed ? 'Cierre de caja · Z' : 'Corte de caja · X'}</div>

  <div class="rc-row">
    <span>Caja</span><span>{shift.register_code} · {shift.register_name}</span>
  </div>
  <div class="rc-row"><span>Turno</span><span class="rc-strong">{shift.code}</span></div>
  <div class="rc-row"><span>Cajero</span><span>{shift.cashier.name}</span></div>
  <div class="rc-row"><span>Apertura</span><span>{formatDateTime(shift.opened_at)}</span></div>
  {#if shift.counted_at}
    <div class="rc-row"><span>Conteo</span><span>{formatDateTime(shift.counted_at)}</span></div>
  {/if}
  {#if shift.closed_at}
    <div class="rc-row"><span>Cierre</span><span>{formatDateTime(shift.closed_at)}</span></div>
  {/if}

  <div class="rc-section">Efectivo</div>
  <div class="rc-row">
    <span>Fondo inicial</span><span>{formatMoney(totals.opening_float)}</span>
  </div>
  <div class="rc-row">
    <span>+ Ventas en efectivo</span><span>{formatMoney(totals.cash_sales)}</span>
  </div>
  <div class="rc-row"><span>+ Entradas</span><span>{formatMoney(totals.cash_in)}</span></div>
  <div class="rc-row"><span>− Salidas</span><span>{formatMoney(totals.cash_out)}</span></div>
  <div class="rc-row">
    <span>− Retiros a caja fuerte</span><span>{formatMoney(totals.safe_drops)}</span>
  </div>
  <div class="rc-row"><span>− Reintegros</span><span>{formatMoney(totals.cash_refunds)}</span></div>
  <div class="rc-row rc-total">
    <span>Esperado en gaveta</span><span>{formatMoney(totals.expected_cash)}</span>
  </div>
  {#if shift.counted_cash !== null && difference !== null}
    <div class="rc-row"><span>Contado</span><span>{formatMoney(shift.counted_cash)}</span></div>
    <div class="rc-row rc-strong">
      <span>{differenceLabel(difference)}</span><span>{formatMoney(difference.toFixed(2))}</span>
    </div>
  {/if}

  <div class="rc-section">Tarjeta y transferencia</div>
  <div class="rc-row">
    <span>Tarjeta esperada</span><span>{formatMoney(totals.expected_card)}</span>
  </div>
  {#if shift.declared_card !== null}
    <div class="rc-row">
      <span>Tarjeta según lote</span><span>{formatMoney(shift.declared_card)}</span>
    </div>
  {/if}
  <div class="rc-row">
    <span>Transferencias esperadas</span><span>{formatMoney(totals.expected_transfer)}</span>
  </div>
  {#if shift.declared_transfer !== null}
    <div class="rc-row">
      <span>Transferencias recibidas</span><span>{formatMoney(shift.declared_transfer)}</span>
    </div>
  {/if}

  {#if lastClosing && lastClosing.denominations.length}
    <div class="rc-section">Conteo por denominación</div>
    {#each lastClosing.denominations as line (`${line.form}-${line.denomination}`)}
      <div class="rc-row">
        <span
          >{line.quantity} × {line.form === 'bill' ? 'billete' : 'moneda'}
          {formatMoney(line.denomination)}</span
        ><span>{formatMoney(line.amount)}</span>
      </div>
    {/each}
  {/if}

  {#if detail.movements.length}
    <div class="rc-section">Movimientos</div>
    {#each detail.movements as movement (movement.id)}
      <div class="rc-row">
        <span>{MOVEMENT_KIND[movement.kind].label}</span>
        <span
          >{MOVEMENT_KIND[movement.kind].sign < 0 ? '−' : '+'}{formatMoney(movement.amount)}</span
        >
      </div>
      <div class="rc-note">
        {movement.reason}{movement.authorized_by
          ? ` · autorizó ${movement.authorized_by.name}`
          : ''}
      </div>
    {/each}
  {/if}

  {#if closed}
    <hr class="rc-sep" />
    <div class="rc-row">
      <span>Fondo que queda</span><span>{formatMoney(shift.retained_float)}</span>
    </div>
    <div class="rc-row rc-strong">
      <span>A depositar</span><span
        >{formatMoney(
          (Number(shift.cash_to_deposit ?? 0) + Number(totals.safe_drops)).toFixed(2)
        )}</span
      >
    </div>
    {#if shift.deposit_number}
      <div class="rc-row">
        <span>Depósito</span><span>DEP-{String(shift.deposit_number).padStart(6, '0')}</span>
      </div>
    {/if}
    {#if shift.approved_by}
      <div class="rc-row"><span>Aprobó</span><span>{shift.approved_by.name}</span></div>
    {/if}
    {#if shift.approval_notes}<div class="rc-note">{shift.approval_notes}</div>{/if}
  {/if}

  <div class="rc-sign">
    <div>Cajero</div>
    <div>Supervisor</div>
  </div>
  <div class="rc-center rc-small rc-muted" style="margin-top: 8px">
    Impreso {formatDateTime(printedAt.toISOString())}
  </div>
</div>
