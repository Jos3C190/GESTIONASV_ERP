<script lang="ts">
  import VehicleForm from '$lib/features/fleet/VehicleForm.svelte';
</script>

<svelte:head><title>Nuevo vehículo — GestionaSV</title></svelte:head>

<div class="page">
  <a class="back" href="/fleet">← Flota</a>
  <h1>Nuevo vehículo</h1>
  <p>Al registrarlo queda disponible en su sucursal base y habilitado para traslados.</p>
  <VehicleForm mode="create" />
</div>

<style>
  .page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 22px 30px;
  }
  .back {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  h1 {
    margin-top: 8px;
    font-size: 26px;
    font-weight: 650;
    letter-spacing: -0.8px;
  }
  p {
    margin: 6px 0 18px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
</style>
