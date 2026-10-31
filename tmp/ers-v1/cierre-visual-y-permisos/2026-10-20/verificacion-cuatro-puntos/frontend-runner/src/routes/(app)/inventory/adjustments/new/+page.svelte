<script lang="ts">
  import { page } from '$app/state';
  import AdjustmentDraftEditor from '$lib/features/inventory/components/AdjustmentDraftEditor.svelte';
  let transferId = $derived(page.url.searchParams.get('transfer_id') ?? '');
  let incidentId = $derived(page.url.searchParams.get('incident_id') ?? '');
  let detailId = $derived(page.url.searchParams.get('detail_id') ?? '');
</script>

<AdjustmentDraftEditor {transferId} {incidentId} {detailId} />
