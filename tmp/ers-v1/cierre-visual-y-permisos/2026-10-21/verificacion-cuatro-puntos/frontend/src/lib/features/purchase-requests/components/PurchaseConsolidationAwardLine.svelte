<script lang="ts">
  import type {
    PurchaseConsolidationAwardDecision,
    PurchaseConsolidationAwardLine as AwardLine,
    PurchaseConsolidationAwardOffer
  } from '$lib/types/purchase-consolidation';
  import PurchaseConsolidationAwardHistory from './PurchaseConsolidationAwardHistory.svelte';
  import PurchaseConsolidationAwardOfferCard from './PurchaseConsolidationAwardOfferCard.svelte';
  import { formatMoney, formatQuantity, statusLabel } from '../adjudication-formatters';

  interface Props {
    line: AwardLine;
    supplierNames: Record<number, string>;
    actorNames: Record<string, string>;
    canAward: boolean;
    savingKey: string | null;
    success: { targetId: string; message: string } | null;
    onAward: (
      line: AwardLine,
      offer: PurchaseConsolidationAwardOffer,
      quantity: string,
      reason: string
    ) => Promise<boolean>;
    onRevoke: (decision: PurchaseConsolidationAwardDecision, reason: string) => Promise<boolean>;
  }

  let { line, supplierNames, actorNames, canAward, savingKey, success, onAward, onRevoke }: Props =
    $props();
</script>

<section class="p-4 sm:p-5" aria-labelledby={`award-line-${line.id}`}>
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <p class="font-mono text-xs text-foreground-muted">{line.product_sku}</p>
      <h3 id={`award-line-${line.id}`} class="mt-1 font-semibold text-foreground">
        {line.product_name}
      </h3>
    </div>
    <div class="grid grid-cols-1 gap-2 text-left text-xs sm:grid-cols-3 sm:gap-5 sm:text-right">
      <div>
        <span class="block text-foreground-muted">Demanda</span><strong
          class="mt-1 inline-block text-foreground"
          >{formatQuantity(line.demand_quantity)} {line.unit_name}</strong
        >
      </div>
      <div>
        <span class="block text-foreground-muted">Adjudicada</span><strong
          class="mt-1 inline-block text-foreground"
          >{formatQuantity(line.awarded_quantity)} {line.unit_name}</strong
        >
      </div>
      <div>
        <span class="block text-foreground-muted">Pendiente</span><strong
          class="mt-1 inline-block text-primary"
          >{formatQuantity(line.remaining_quantity)} {line.unit_name}</strong
        >
      </div>
    </div>
  </div>

  {#if line.offers.length === 0}
    <div
      class="mt-4 rounded-lg border border-border bg-surface-muted/40 p-3 text-sm text-foreground-muted"
    >
      Aún no hay respuestas de proveedor para este producto.
    </div>
  {:else}
    {#if line.offers.length > 1}
      <div class="mt-4 hidden xl:block">
        <h4 class="text-sm font-semibold text-foreground">Comparación rápida</h4>
        <div class="mt-2 overflow-x-auto rounded-lg border border-border">
          <table class="w-full min-w-[980px] text-left text-xs">
            <caption class="sr-only"
              >Comparación de las ofertas para {line.product_name}; los importes conservan la moneda
              de cada proveedor.</caption
            >
            <thead class="bg-surface-muted/40 text-foreground-muted">
              <tr>
                <th scope="col" class="px-3 py-2 font-medium">Proveedor</th>
                <th scope="col" class="px-3 py-2 font-medium">Estado</th>
                <th scope="col" class="px-3 py-2 font-medium">Moneda</th>
                <th scope="col" class="px-3 py-2 font-medium">Ofrecido / disponible</th>
                <th scope="col" class="px-3 py-2 font-medium">Precio unitario</th>
                <th scope="col" class="px-3 py-2 font-medium">Descuento</th>
                <th scope="col" class="px-3 py-2 font-medium">Impuesto</th>
                <th scope="col" class="px-3 py-2 font-medium">Entrega</th>
                <th scope="col" class="px-3 py-2 font-medium">Pago</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each line.offers as offer (offer.quotation_detail_id)}
                <tr>
                  <th scope="row" class="max-w-48 px-3 py-2 font-medium text-foreground"
                    >{supplierNames[offer.supplier_id] ?? `Proveedor #${offer.supplier_id}`}</th
                  >
                  <td class="px-3 py-2 text-foreground-muted"
                    >{statusLabel(offer.quotation_status)}</td
                  >
                  <td class="px-3 py-2 font-semibold text-foreground">{offer.currency}</td>
                  <td class="whitespace-nowrap px-3 py-2 text-foreground"
                    >{formatQuantity(offer.offered_quantity)} / {formatQuantity(
                      offer.available_quantity
                    )}
                    {line.unit_name}</td
                  >
                  <td class="whitespace-nowrap px-3 py-2 text-foreground"
                    >{formatMoney(offer.unit_price, offer.currency)}</td
                  >
                  <td class="whitespace-nowrap px-3 py-2 text-foreground"
                    >{formatMoney(offer.discount, offer.currency)}</td
                  >
                  <td class="whitespace-nowrap px-3 py-2 text-foreground"
                    >{formatMoney(offer.tax_amount, offer.currency)}</td
                  >
                  <td class="whitespace-nowrap px-3 py-2 text-foreground"
                    >{offer.line_delivery_days ?? offer.delivery_days ?? '—'} días</td
                  >
                  <td class="max-w-40 px-3 py-2 text-foreground"
                    >{offer.payment_terms || 'No indicado'}</td
                  >
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <div class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
      {#each line.offers as offer (offer.quotation_detail_id)}
        <PurchaseConsolidationAwardOfferCard
          {line}
          {offer}
          supplierName={supplierNames[offer.supplier_id] ?? `Proveedor #${offer.supplier_id}`}
          {canAward}
          {savingKey}
          {success}
          onAward={(quantity, reason) => onAward(line, offer, quantity, reason)}
        />
      {/each}
    </div>
  {/if}

  <PurchaseConsolidationAwardHistory
    {line}
    {supplierNames}
    {actorNames}
    {canAward}
    {savingKey}
    {success}
    {onRevoke}
  />
</section>
