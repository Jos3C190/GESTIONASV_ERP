<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import type { LayoutData } from './$types';
  import ConfirmActionDialog from '$lib/components/ui/ConfirmActionDialog.svelte';

  interface Props {
    children: Snippet;
    data: LayoutData;
  }

  let { children }: Props = $props();
</script>

<svelte:head>
  <title>ERP System</title>
  <meta name="description" content="ERP System — panel de gestión empresarial." />
</svelte:head>

{@render children()}
<ConfirmActionDialog />
