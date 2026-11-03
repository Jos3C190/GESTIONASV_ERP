<script lang="ts">
  import { fleetApi, type FleetSupplier } from './api';

  // Elegir un proveedor o escribir el nombre de uno ocasional: una llanta en la carretera
  // no merece darlo de alta en Compras.
  let {
    id,
    label,
    supplierId = $bindable(''),
    text = $bindable('')
  }: { id: string; label: string; supplierId?: string; text?: string } = $props();

  let suppliers = $state<FleetSupplier[]>([]);
  let loaded = $state(false);

  $effect(() => {
    void load();
  });

  // Uno que ya no está activo, o una carga fallida, no deja un select vacío sin salida.
  $effect(() => {
    if (loaded && supplierId && !suppliers.some((item) => String(item.id) === supplierId)) {
      supplierId = '';
    }
  });

  async function load() {
    try {
      suppliers = await fleetApi.suppliers();
    } catch {
      suppliers = [];
    }
    loaded = true;
  }
</script>

<div class="field">
  <label for={id}>{label}</label>
  {#if suppliers.length}
    <select {id} bind:value={supplierId}>
      <option value="">Otro (escribir el nombre)</option>
      {#each suppliers as supplier (supplier.id)}
        <option value={String(supplier.id)}>{supplier.name}</option>
      {/each}
    </select>
  {/if}
  {#if !supplierId || !suppliers.length}
    <input
      id={suppliers.length ? `${id}-text` : id}
      aria-label={suppliers.length ? `${label}: nombre` : undefined}
      bind:value={text}
      maxlength="160"
      placeholder="Nombre"
    />
  {/if}
</div>

<style>
  .field {
    display: grid;
    align-content: start;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
  }
  input,
  select {
    width: 100%;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 400;
  }
  @media (min-width: 768px) {
    input,
    select {
      min-height: 38px;
      font-size: 13px;
    }
  }
</style>
