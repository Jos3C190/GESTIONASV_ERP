<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import type { TransferRouteType } from '$lib/features/inventory/transfer-documents';
  import { transferRouteLabel } from '$lib/features/inventory/transfer-operations';

  let { route }: { route: TransferRouteType } = $props();

  // The usual route stays neutral so the two that need attention stand out.
  const variant = $derived(
    route === 'branch_to_branch'
      ? ('primary' as const)
      : route === 'branch_to_central'
        ? ('warning' as const)
        : ('neutral' as const)
  );
</script>

<span data-route={route}><Badge {variant}>{transferRouteLabel(route)}</Badge></span>
