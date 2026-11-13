<script lang="ts">
  import TransferDispatchPanel from '$lib/features/inventory/components/TransferDispatchPanel.svelte';
  import type {
    DispatchSelection,
    InventoryTransfer
  } from '$lib/features/inventory/transfer-documents';

  /** Test host: reports every selection the panel binds, as the page does. */
  let {
    transfer,
    onSelection
  }: { transfer: InventoryTransfer; onSelection: (value: DispatchSelection) => void } = $props();

  let selection = $state<DispatchSelection>({
    vehicleId: '',
    driverId: '',
    overrideReason: '',
    substitutionCode: '',
    substitutionReason: '',
    ready: false,
    label: ''
  });

  $effect(() => {
    onSelection($state.snapshot(selection) as DispatchSelection);
  });
</script>

<TransferDispatchPanel {transfer} disabled={false} bind:selection />
