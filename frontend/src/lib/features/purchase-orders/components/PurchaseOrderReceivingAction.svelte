<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseOrder } from '$lib/types/purchase-order';

  let { order }: { order: PurchaseOrder } = $props();

  let canCreateReceipt = $derived(
    (order.status === 'sent' || order.status === 'partially_received') &&
      permissions.hasPermission('purchases:read') &&
      permissions.hasPermission('purchases:manage')
  );

  function openReceiving() {
    void goto(`/purchases/new?order_id=${order.id}`);
  }
</script>

{#if canCreateReceipt}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-label="Recepción de orden de compra"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Recepción</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Registra una recepción total o parcial utilizando las cantidades pendientes de la orden.
        </p>
      </div>

      <Button onclick={openReceiving}>Registrar recepción</Button>
    </div>
  </section>
{/if}
