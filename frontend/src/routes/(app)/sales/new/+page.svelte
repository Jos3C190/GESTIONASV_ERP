<script lang="ts">
  import { page } from '$app/state';
  import SalesDocumentEditor from '#lib/features/sales/components/SalesDocumentEditor.svelte';

  // «Cambiar por otro producto» desde una devolución aceptada (V8b1).
  const exchange = $derived.by(() => {
    const params = page.url.searchParams;
    const returnId = params.get('exchange_return');
    const customerId = params.get('customer');
    const branchId = params.get('branch');
    if (!returnId || !customerId || !branchId) return null;
    return { returnId, customerId, branchId, code: params.get('code') ?? '' };
  });
</script>

<SalesDocumentEditor kind="order" {exchange} />
