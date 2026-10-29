<script lang="ts">
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
    <img
      src={vehicleImage(vehicle)}
      alt={`${vehicle.model}, vehículo ${vehicle.id}`}
      width="720"
      height="440"
      loading="lazy"
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
  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
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
