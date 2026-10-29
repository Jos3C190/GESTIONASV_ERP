<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type {
    PurchaseConsolidationAwardLine,
    PurchaseConsolidationAwardOffer
  } from '$lib/types/purchase-consolidation';
  import {
    adjudicationQuantityPattern,
    formatDate,
    formatMoney,
    formatQuantity,
    offerKey,
    statusLabel
  } from '../adjudication-formatters';

  interface Props {
    line: PurchaseConsolidationAwardLine;
    offer: PurchaseConsolidationAwardOffer;
    supplierName: string;
    canAward: boolean;
    savingKey: string | null;
    success: { targetId: string; message: string } | null;
    onAward: (quantity: string, reason: string) => Promise<boolean>;
  }

  let { line, offer, supplierName, canAward, savingKey, success, onAward }: Props = $props();
  let quantity = $state('');
  let reason = $state('');
  const key = $derived(offerKey(line.id, offer.quotation_detail_id));

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (await onAward(quantity, reason)) {
      quantity = '';
      reason = '';
    }
  }
</script>

<article class="rounded-xl border border-border bg-surface-muted/20 p-3 sm:p-4">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <p class="font-mono text-xs font-semibold text-primary">
        {offer.quotation_code} · Versión {offer.quotation_version}
      </p>
      <p class="mt-1 font-medium text-foreground">{supplierName}</p>
      <p class="mt-1 text-xs text-foreground-muted">
        {statusLabel(offer.quotation_status)} · Vigencia: {formatDate(offer.valid_until)}
      </p>
    </div>
    <span
      class="rounded-full border border-border px-2.5 py-1 text-xs font-semibold text-foreground"
      >{offer.currency}</span
    >
  </div>

  <dl class="mt-4 grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
    <div>
      <dt class="text-xs text-foreground-muted">Precio unitario</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {formatMoney(offer.unit_price, offer.currency)}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Descuento</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {formatMoney(offer.discount, offer.currency)}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Impuesto</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {formatMoney(offer.tax_amount, offer.currency)} ({formatQuantity(offer.tax_rate)}%)
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Cantidad ofrecida</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {formatQuantity(offer.offered_quantity)}
        {line.unit_name}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Disponible ahora</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {offer.available_quantity === null
          ? 'No indicada'
          : `${formatQuantity(offer.available_quantity)} ${line.unit_name}`}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Ya adjudicado</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {formatQuantity(offer.awarded_quantity)}
        {line.unit_name}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Total de esta línea</dt>
      <dd class="mt-0.5 font-semibold text-foreground">
        {formatMoney(offer.line_total, offer.currency)}
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Entrega</dt>
      <dd class="mt-0.5 font-medium text-foreground">
        {offer.line_delivery_days ?? offer.delivery_days ?? 'No indicada'} días
      </dd>
    </div>
    <div>
      <dt class="text-xs text-foreground-muted">Pago</dt>
      <dd class="mt-0.5 font-medium text-foreground">{offer.payment_terms || 'No indicado'}</dd>
    </div>
  </dl>

  <p class="mt-3 max-w-3xl rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-xs leading-5 text-foreground-muted">
    Máximo que puedes adjudicar aquí: <strong class="text-foreground">{formatQuantity(offer.remaining_offer_quantity)} {line.unit_name}</strong>.
    Este límite considera lo ofrecido, la disponibilidad informada y la demanda pendiente. Si el proveedor no indicó disponibilidad, se toma lo ofrecido.
  </p>

  {#if Number(offer.quotation_expenses_total) > 0}
    <p class="mt-3 rounded-md border border-border px-2.5 py-2 text-xs text-foreground-muted">
      Cargos adicionales de la RFQ: <strong class="text-foreground"
        >{formatMoney(offer.quotation_expenses_total, offer.currency)}</strong
      >. No están asignados a este producto.
    </p>
  {/if}
  {#if offer.notes}<p class="mt-2 text-xs text-foreground-muted">Nota: {offer.notes}</p>{/if}

  {#if offer.can_award && canAward && line.remaining_quantity !== '0' && offer.remaining_offer_quantity !== '0'}
    <form
      class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(7rem,0.7fr)_minmax(12rem,1.3fr)_auto]"
      onsubmit={submit}
    >
      <label class="text-xs font-medium text-foreground-muted">
        Cantidad a adjudicar
        <input
          aria-label={`Cantidad a adjudicar de ${line.product_name} a ${supplierName}`}
          type="text"
          inputmode="decimal"
          pattern={adjudicationQuantityPattern}
          bind:value={quantity}
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          placeholder={`Máx. ${formatQuantity(offer.remaining_offer_quantity)}`}
          required
        />
        <span class="mt-1 block text-[11px] font-normal text-foreground-muted">
          No puede exceder el máximo indicado arriba.
        </span>
      </label>
      <label class="text-xs font-medium text-foreground-muted">
        Motivo de la decisión
        <input
          aria-label={`Motivo de adjudicación de ${line.product_name} a ${supplierName}`}
          bind:value={reason}
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          placeholder="Ej. mejor plazo y precio revisado"
          maxlength="2000"
          required
        />
      </label>
      <div class="flex items-end">
        <Button
          type="submit"
          size="sm"
          disabled={savingKey !== null}
          class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >{savingKey === key ? 'Guardando…' : 'Adjudicar cantidad'}</Button
        >
      </div>
    </form>
  {:else if offer.blocked_reason}
    <p
      class="mt-4 rounded-md border border-warning/20 bg-warning/5 px-3 py-2 text-xs text-foreground-muted"
    >
      {offer.blocked_reason}
    </p>
  {:else if !canAward}
    <p class="mt-4 text-xs text-foreground-muted">
      Tu perfil puede consultar las ofertas, pero no adjudicarlas.
    </p>
  {/if}

  {#if success?.targetId === key}
    <p
      class="mt-3 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success"
      role="status"
      aria-live="polite"
    >
      {success.message}
    </p>
  {/if}
</article>
