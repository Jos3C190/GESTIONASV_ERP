<script lang="ts">
  interface Props {
    manufacturerLot: string | null | undefined;
    receiptLot: string | null | undefined;
    receiptLotHeader: string | null | undefined;
  }

  let { manufacturerLot, receiptLot, receiptLotHeader }: Props = $props();
</script>

<div class="mt-1 space-y-1 text-sm font-medium text-foreground">
  {#if manufacturerLot}<p class="break-all">Fabricante: {manufacturerLot}</p>{/if}
  {#if receiptLot}<p class="break-all">Recepción: {receiptLot}</p>{/if}
  {#if receiptLotHeader && receiptLotHeader !== receiptLot}
    <p class="break-all">Recepción agrupada: {receiptLotHeader}</p>
  {/if}
  {#if !manufacturerLot && !receiptLot && !receiptLotHeader}
    <p>Sin lote registrado</p>
  {/if}
</div>
