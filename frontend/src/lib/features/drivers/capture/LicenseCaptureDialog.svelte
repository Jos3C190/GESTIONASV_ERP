<script lang="ts">
  import CaptureDialog from '$lib/features/document-capture/CaptureDialog.svelte';
  import type { Driver } from '../api';
  import { licenseCaptureConfig } from './license-config';

  let {
    open = $bindable(false),
    driver,
    onconfirmed
  }: { open?: boolean; driver: Driver; onconfirmed: (driver: Driver) => void } = $props();

  const config = $derived(licenseCaptureConfig(driver.id));
</script>

<CaptureDialog bind:open {config} {onconfirmed} />
