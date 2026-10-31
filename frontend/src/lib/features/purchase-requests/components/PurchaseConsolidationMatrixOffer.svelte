<script lang="ts">
  import type {
    PurchaseConsolidationAwardLine,
    PurchaseConsolidationAwardOffer
  } from '$lib/types/purchase-consolidation';
  import { formatDate, formatMoney, formatQuantity, statusLabel } from '../adjudication-formatters';

  let {
    line,
    offer,
    supplierName,
    onInspect
  }: {
    line: PurchaseConsolidationAwardLine;
    offer: PurchaseConsolidationAwardOffer;
    supplierName: string;
    onInspect: () => void;
  } = $props();
  const hasQuantity = $derived(
    offer.offered_quantity !== null && Number(offer.offered_quantity) > 0
  );
</script>

<article
  aria-label={`${offer.quotation_code}, versión ${offer.quotation_version}, ${line.product_name}, ${supplierName}`}
>
  <p class="font-mono text-xs font-medium text-foreground">
    {offer.quotation_code} · v{offer.quotation_version}
  </p>
  <p class="mt-1 text-xs text-foreground-muted">{statusLabel(offer.quotation_status)}</p>
  {#if hasQuantity}
    <p class="mt-3 font-semibold tabular-nums text-foreground">
      {formatMoney(offer.unit_price, offer.currency)}<span
        class="block text-xs font-normal text-foreground-muted">por {line.unit_name}</span
      >
    </p>
  {:else}
    <p class="mt-3 font-medium text-foreground">Sin cantidad ofrecida</p>
  {/if}
  <dl class="mt-3 space-y-2 text-xs">
    <div class="flex flex-wrap justify-between gap-x-2">
      <dt class="text-foreground-muted">Ofrecido</dt>
      <dd class="font-medium tabular-nums text-foreground">
        {offer.offered_quantity === null
          ? 'No indicada'
          : `${formatQuantity(offer.offered_quantity)} ${line.unit_name}`}
      </dd>
    </div>
    <div class="flex flex-wrap justify-between gap-x-2">
      <dt class="text-foreground-muted">Disponible</dt>
      <dd class="font-medium tabular-nums text-foreground">
        {offer.available_quantity === null
          ? 'No indicada'
          : `${formatQuantity(offer.available_quantity)} ${line.unit_name}`}
      </dd>
    </div>
    <div class="flex flex-wrap justify-between gap-x-2">
      <dt class="text-foreground-muted">Entrega</dt>
      <dd class="font-medium text-foreground">
        {(offer.line_delivery_days ?? offer.delivery_days) === null
          ? 'No indicada'
          : `${offer.line_delivery_days ?? offer.delivery_days} días`}
      </dd>
    </div>
    {#if hasQuantity}
      <div class="border-t border-border pt-2">
        <dt class="text-foreground-muted">
          Total cotizado · {formatQuantity(offer.offered_quantity)}
          {line.unit_name}
        </dt>
        <dd class="mt-1 font-semibold tabular-nums text-foreground">
          {formatMoney(offer.line_total, offer.currency)}
        </dd>
      </div>
    {/if}
  </dl>
  {#if Number(offer.awarded_quantity) > 0}
    <p
      class="mt-3 rounded-md border border-primary/30 bg-primary/5 px-2 py-1.5 text-xs font-medium text-foreground"
    >
      Adjudicado: {formatQuantity(offer.awarded_quantity)}
      {line.unit_name}
    </p>
  {/if}
  {#if offer.blocked_reason}
    <p class="mt-3 border-l-2 border-border pl-2 text-xs leading-5 text-foreground-muted">
      {offer.blocked_reason}
    </p>
  {/if}
  <details class="mt-3 text-xs">
    <summary
      class="min-h-9 cursor-pointer py-2 font-medium text-foreground underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >Descuento, impuestos y condiciones</summary
    >
    <dl class="mt-2 space-y-3 border-l border-border pl-3">
      <div>
        <dt class="text-foreground-muted">Descuento de la línea</dt>
        <dd class="mt-0.5 text-foreground">{formatMoney(offer.discount, offer.currency)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Impuesto de la línea</dt>
        <dd class="mt-0.5 text-foreground">
          {formatMoney(offer.tax_amount, offer.currency)} ({formatQuantity(offer.tax_rate)}%)
        </dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Vigencia</dt>
        <dd class="mt-0.5 text-foreground">{formatDate(offer.valid_until)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Pago</dt>
        <dd class="mt-0.5 text-foreground">{offer.payment_terms || 'No indicado'}</dd>
      </div>
      {#if Number(offer.quotation_expenses_total) > 0}
        <div>
          <dt class="text-foreground-muted">Cargos compartidos de la cotización</dt>
          <dd class="mt-0.5 text-foreground">
            {formatMoney(offer.quotation_expenses_total, offer.currency)}. Pendientes de asignar a
            productos; no están sumados al total de esta línea.
          </dd>
        </div>
      {/if}
      {#if offer.notes}<div>
          <dt class="text-foreground-muted">Observaciones</dt>
          <dd class="mt-0.5 whitespace-pre-wrap text-foreground">{offer.notes}</dd>
        </div>{/if}
    </dl>
  </details>
  <button
    type="button"
    onclick={onInspect}
    aria-label={`Ver oferta ${offer.quotation_code} de ${supplierName} para ${line.product_name}`}
    class="mt-3 min-h-11 w-full rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >Ver oferta</button
  >
</article>
