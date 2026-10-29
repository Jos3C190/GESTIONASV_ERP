<script lang="ts">
  import { tick, untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import LocationGridPicker from '$lib/features/locations/components/LocationGridPicker.svelte';
  import { warehouseReceivingApi, type WarehouseReceipt } from '../warehouse-receiving';

  let {
    warehouseId,
    contextKey,
    onregistered
  }: { warehouseId: string; contextKey: string; onregistered?: () => void } = $props();
  let receipts = $state<WarehouseReceipt[]>([]);
  let total = $state(0);
  let currentPage = $state(1);
  let pages = $state(1);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let revision = $state(0);
  let selected = $state<WarehouseReceipt | null>(null);
  let quantities = $state<Record<string, string>>({});
  let destinations = $state<Record<string, string>>({});
  let locations = $state<LocationOut[]>([]);
  let locationPage = $state(0);
  let moreLocations = $state(false);
  let loadingLocations = $state(false);
  let locationError = $state<string | null>(null);
  let saving = $state(false);
  let submitError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let alive = true;
  let queueSequence = 0;
  let selectionSequence = 0;
  let hasAcceptedQuantity = $derived(
    selected?.lines.some((line) => Number(quantities[line.id]) > 0) ?? false
  );

  $effect(() => {
    const warehouse = warehouseId;
    void contextKey;
    const number = currentPage;
    void revision;
    const request = ++queueSequence;
    untrack(() => {
      selectionSequence += 1;
      selected = null;
      loadingLocations = false;
    });
    loading = true;
    error = null;
    void warehouseReceivingApi
      .list(warehouse, number)
      .then((result) => {
        if (request !== queueSequence) return;
        receipts = result.items;
        total = result.meta.total;
        pages = Math.max(1, result.meta.pages);
      })
      .catch((cause) => {
        if (request === queueSequence)
          error =
            cause instanceof Error ? cause.message : 'No se pudieron consultar las recepciones.';
      })
      .finally(() => {
        if (request === queueSequence) loading = false;
      });
    return () => {
      queueSequence += 1;
    };
  });
  $effect(() => {
    void warehouseId;
    void contextKey;
    alive = true;
    return () => {
      alive = false;
      selectionSequence += 1;
    };
  });

  async function loadLocations(reset = false) {
    if (!selected || loadingLocations) return;
    const request = selectionSequence;
    loadingLocations = true;
    locationError = null;
    try {
      const nextPage = reset ? 1 : locationPage + 1;
      const result = await listLocations(warehouseId, {
        page: nextPage,
        size: 100,
        is_active: true,
        lifecycle_status: 'active'
      });
      if (request !== selectionSequence) return;
      const eligible = result.items.filter(
        (location) =>
          location.warehouse_id === warehouseId &&
          location.is_active &&
          location.lifecycle_status === 'active' &&
          location.location_type === 'receiving'
      );
      locations = reset
        ? eligible
        : [
            ...new Map(
              [...locations, ...eligible].map((location) => [location.id, location])
            ).values()
          ];
      locationPage = nextPage;
      moreLocations = result.meta.page < result.meta.pages;
    } catch (cause) {
      if (request === selectionSequence)
        locationError =
          cause instanceof Error ? cause.message : 'No se pudieron consultar las ubicaciones.';
    } finally {
      if (request === selectionSequence) loadingLocations = false;
    }
  }
  async function prepare(receipt: WarehouseReceipt) {
    selectionSequence += 1;
    selected = receipt;
    locations = [];
    locationPage = 0;
    loadingLocations = false;
    submitError = null;
    success = null;
    quantities = Object.fromEntries(receipt.lines.map((line) => [line.id, line.quantity_received]));
    destinations = {};
    void loadLocations(true);
    await tick();
    document.getElementById('receipt-review-heading')?.focus();
  }
  async function cancelPreparation() {
    selectionSequence += 1;
    selected = null;
    loadingLocations = false;
    await tick();
    document.getElementById('receiving-heading')?.focus();
  }
  async function register(event: SubmitEvent) {
    event.preventDefault();
    if (!selected || saving) return;
    const receipt = selected;
    if (
      receipt.lines.some(
        (line) =>
          !quantities[line.id]?.trim() ||
          !Number.isFinite(Number(quantities[line.id])) ||
          Number(quantities[line.id]) < 0 ||
          Number(quantities[line.id]) > Number(line.quantity_received) ||
          (Number(quantities[line.id]) > 0 &&
            !locations.some((location) => location.id === destinations[line.id]))
      )
    ) {
      submitError = 'Revisa las cantidades y selecciona una ubicación para cada cantidad aceptada.';
      return;
    }
    const request = selectionSequence;
    saving = true;
    submitError = null;
    try {
      const verified = await warehouseReceivingApi.verify(
        receipt.id,
        receipt.lines.map((line) => ({
          purchase_detail_id: line.id,
          quantity_accepted: quantities[line.id] ?? '',
          inventory_location_id:
            Number(quantities[line.id]) > 0 ? (destinations[line.id] ?? null) : null
        }))
      );
      if (!alive || request !== selectionSequence) return;
      selected = null;
      success = verified.lines.some((line) => Number(line.quantity_accepted) > 0)
        ? `${receipt.code}: recepción verificada. Continúa con medidas, etiquetas y ubicación.`
        : `${receipt.code}: recepción verificada sin unidades aceptadas. No ingresaron existencias.`;
      currentPage = Math.max(1, Math.min(currentPage, Math.ceil((total - 1) / 10)));
      saving = false;
      revision += 1;
      onregistered?.();
      await tick();
      document.getElementById('receiving-heading')?.focus();
    } catch (cause) {
      if (alive && request === selectionSequence)
        submitError = cause instanceof Error ? cause.message : 'No se pudo registrar la recepción.';
    } finally {
      if (alive && request === selectionSequence) saving = false;
    }
  }
</script>

<section
  class="overflow-hidden rounded-xl border border-border bg-surface"
  aria-labelledby="receiving-heading"
>
  <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5">
    <div>
      <h2
        id="receiving-heading"
        tabindex="-1"
        class="font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
      >
        Recepciones pendientes
      </h2>
      <p class="mt-1 text-sm text-foreground-muted">
        Verifica las cantidades después del cierre de retaceo. Después continúa con medidas, etiquetas y ubicación.
      </p>
    </div>
    <Button
      variant="secondary"
      size="sm"
      disabled={loading || saving}
      onclick={() => (revision += 1)}>Actualizar</Button
    >
  </div>
  <p role="status" class="sr-only">
    {loading ? 'Consultando recepciones…' : `${total} recepciones pendientes.`}
  </p>
  <div class="p-5">
    {#if success}<p
        role="status"
        class="mb-4 rounded-lg border border-success/30 bg-success/5 p-4 text-sm text-success"
      >
        {success}
      </p>{/if}
    {#if loading}<div class="skeleton h-24 rounded-lg"></div>
    {:else if error}<div
        role="alert"
        class="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      >
        {error}<Button class="mt-3" variant="secondary" size="sm" onclick={() => (revision += 1)}
          >Reintentar</Button
        >
      </div>
    {:else if !receipts.length}<div
        class="rounded-lg border border-dashed border-border p-6 text-center"
      >
        <p class="text-sm font-medium text-foreground">No hay recepciones pendientes</p>
        <p class="mt-1 text-xs text-foreground-muted">
          Las compras aparecerán aquí cuando se confirme su documento de recepción.
        </p>
      </div>
    {:else}<ul class="divide-y divide-border">
        {#each receipts as receipt (receipt.id)}<li
            class="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0"
          >
            <div>
              <p class="text-sm font-semibold text-foreground">{receipt.code}</p>
              <p class="mt-1 text-xs text-foreground-muted">
                {receipt.ready
                  ? `${receipt.retaceo_code ?? 'Recepción histórica'} · Lista para verificar`
                  : 'Esperando cierre de retaceo'}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={!receipt.ready || saving}
              onclick={() => void prepare(receipt)}>Verificar recepción</Button
            >
          </li>{/each}
      </ul>{/if}
    <div class="mt-4 flex items-center justify-between gap-3 text-xs text-foreground-muted">
      <p>Página {currentPage} de {pages}</p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || saving || currentPage <= 1}
          onclick={() => (currentPage -= 1)}>Anterior</Button
        ><Button
          variant="secondary"
          size="sm"
          disabled={loading || saving || currentPage >= pages}
          onclick={() => (currentPage += 1)}>Siguiente</Button
        >
      </div>
    </div>
    {#if selected}
      <form
        onsubmit={register}
        class="mt-5 space-y-4 rounded-lg border border-primary/30 bg-primary/5 p-4"
      >
        <h3
          id="receipt-review-heading"
          tabindex="-1"
          class="font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
        >
          Verificar {selected.code}
        </h3>
        <p class="text-xs leading-5 text-foreground-muted">
          Confirma la cantidad física y su destino de cuarentena. Una cantidad menor a la
          documentada registra el resto como rechazado. Solo la cantidad aceptada ingresará a la
          bodega.
        </p>
        {#if locationError}<p role="alert" class="text-sm text-foreground">{locationError}</p>
          <Button
            variant="secondary"
            size="sm"
            disabled={loadingLocations}
            onclick={() => void loadLocations(locationPage === 0)}>Reintentar ubicaciones</Button
          >{/if}
        {#if loadingLocations}<p class="text-sm text-foreground-muted" role="status">
            Cargando ubicaciones activas…
          </p>{:else if !locations.length && !locationError}<div
            class="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-foreground"
            role="status"
          >
            <p>
              No hay ubicaciones activas para recibir la mercancía. Puedes registrar cero unidades
              aceptadas o preparar una ubicación antes de continuar.
            </p>
            <a
              class="mt-2 inline-block rounded underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
              href={`/warehouses/${warehouseId}/locations`}>Revisar ubicaciones de la bodega</a
            ><Button
              class="ml-3"
              size="sm"
              variant="secondary"
              onclick={() => void loadLocations(true)}>Volver a consultar</Button
            >
          </div>{/if}
        {#each selected.lines as line (line.id)}
          <div class="grid gap-4 rounded-lg border border-border bg-surface p-4 lg:grid-cols-2">
            <div class="lg:col-span-2">
              <h4 class="text-sm font-medium text-foreground">{line.product_name}</h4>
              <p class="mt-1 text-xs text-foreground-muted">
                {line.product_sku} · Documentado: {Number(line.quantity_received).toLocaleString(
                  'es-SV'
                )}
                {line.unit_symbol}
              </p>
            </div>
            <label class="block text-sm text-foreground"
              ><span class="mb-1 block">Cantidad aceptada ({line.unit_symbol})</span><input
                type="number"
                min="0"
                max={line.quantity_received}
                step="0.000001"
                required
                value={quantities[line.id]}
                oninput={(event) => (quantities[line.id] = event.currentTarget.value)}
                disabled={saving}
                class="h-10 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              /></label
            >
            <LocationGridPicker
              id={`receipt-location-${line.id}`}
              {locations}
              selectedLocationId={destinations[line.id] ?? ''}
              productName={line.product_name}
              disabled={saving || loadingLocations || Number(quantities[line.id]) === 0}
              hasMoreLocations={moreLocations}
              onselect={(id) => (destinations[line.id] = id)}
            />
          </div>
        {/each}
        {#if moreLocations}<Button
            variant="secondary"
            size="sm"
            disabled={loadingLocations || saving}
            onclick={() => void loadLocations()}
            >{loadingLocations ? 'Cargando…' : 'Cargar más ubicaciones'}</Button
          >{/if}
        {#if submitError}<p
            role="alert"
            class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
          >
            {submitError}
          </p>{/if}
        <div class="flex flex-wrap justify-end gap-3">
          <Button variant="secondary" disabled={saving} onclick={() => void cancelPreparation()}
            >Cancelar</Button
          ><Button
            type="submit"
            disabled={saving ||
              (hasAcceptedQuantity && (loadingLocations || locations.length === 0))}
            >{saving ? 'Registrando…' : 'Confirmar verificación'}</Button
          >
        </div>
      </form>
    {/if}
  </div>
</section>
