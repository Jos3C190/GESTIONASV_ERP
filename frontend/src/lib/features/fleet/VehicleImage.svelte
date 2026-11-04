<script lang="ts">
  import { company } from '$lib/stores/company.svelte';
  import BrandedVehicle from './BrandedVehicle.svelte';
  import { BASE_IMAGES, type BaseImage } from './catalog';
  import FleetIcon from './FleetIcon.svelte';
  let {
    image,
    typeName,
    label,
    large = false
  }: { image: BaseImage | null; typeName: string; label: string; large?: boolean } = $props();
  let failed = $state(false);
  $effect(() => {
    if (image) failed = false;
  });
</script>

<div class:large class="vehicle-image">
  {#if failed || !image}
    <div class="image-fallback">
      <FleetIcon name="truck" size={64} /><span>{typeName}</span>
    </div>
  {:else}
    <BrandedVehicle
      src={BASE_IMAGES[image].image}
      alt={label}
      kind={image}
      logo={company.active?.logo ?? null}
      onerror={() => (failed = true)}
    />
  {/if}
</div>

<style>
  .vehicle-image {
    height: 112px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 12px;
  }
  .large {
    height: 185px;
    padding: 5px 14px;
  }
  .image-fallback {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: rgb(var(--foreground-muted));
  }
</style>
