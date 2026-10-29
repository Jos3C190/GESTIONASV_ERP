<script lang="ts">
  import { company } from '$lib/stores/company.svelte';
  import BrandedVehicle from './BrandedVehicle.svelte';
  import FleetIcon from './FleetIcon.svelte';
  import { vehicleImage, type FleetVehicle } from './mock-data';
  let { vehicle, large = false }: { vehicle: FleetVehicle; large?: boolean } = $props();
  let failed = $state(false);
  $effect(() => {
    if (vehicle.id) failed = false;
  });
</script>

<div class:large class="vehicle-image">
  {#if failed}
    <div class="image-fallback">
      <FleetIcon name="truck" size={64} /><span>{vehicle.model}</span>
    </div>
  {:else}
    <BrandedVehicle
      src={vehicleImage(vehicle)}
      alt={`${vehicle.model}, vehículo ${vehicle.id}`}
      kind={vehicle.kind}
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
    font-size: 12px;
  }
  @media (max-width: 640px) {
    .vehicle-image {
      height: 120px;
    }
  }
</style>
