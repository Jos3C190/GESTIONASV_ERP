<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchasesApi } from '$lib/api/purchases';
  import LocationGridPicker from '$lib/features/locations/components/LocationGridPicker.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import type { Purchase } from '$lib/types/purchase';

  let {
    purchase,
    productLabels,
    unitLabels,
    onupdated,
    oncancel
  }: {
    purchase: Purchase;
    productLabels: Map<number, string>;
    unitLabels: Map<number, string>;
    onupdated: (purchase: Purchase) => void;
    oncancel: () => void;
  } = $props();

  interface ReceiptSplit {
    key: string;
    quantity: string;
    locationId: string;
  }

  let locations = $state<LocationOut[]>([]);
  let splits = $state<Record<string, ReceiptSplit[]>>({});
  let nextSplitKey = 1;
  let loading = $state(true);
  let loadingMore = $state(false);
  let pageNumber = $state(1);
  let hasMoreLocations = $state(false);
  let loadMoreError = $state<string | null>(null);
  let saving = $state(false);
  let locationError = $state<string | null>(null);
  let submitError = $state<string | null>(null);

  let hasAcceptedQuantity = $derived(
    Object.values(splits).some((parts) => parts.some((part) => Number(part.quantity) > 0))
  );
  let splitCount = $derived(
    Object.values(splits).reduce((total, parts) => total + parts.length, 0)
  );

  let validationError = $derived.by(() => {
    if (splitCount > 200) {
      return 'La recepción admite hasta 200 unidades separadas por registro.';
    }
    for (const detail of purchase.details) {
      const parts = splits[detail.id] ?? [];
      if (parts.length === 0) return 'Cada producto debe tener al menos una unidad de recepción.';
      const counted = Number(detail.quantity_received);
      let accepted = 0;
      for (const part of parts) {
        if (!part.quantity.trim()) return 'Indica la cantidad aceptada para cada unidad separada.';
        const quantity = Number(part.quantity);
        if (!Number.isFinite(quantity) || quantity < 0) {
          return 'Cada cantidad aceptada debe ser cero o mayor.';
        }
        accepted += quantity;
        if (quantity > 0 && !part.locationId) {
          return 'Selecciona una ubicación para cada unidad que vas a aceptar.';
        }
        if (quantity === 0 && part.locationId) {
          return 'Quita la ubicación de una unidad cuya cantidad aceptada sea cero.';
        }
      }
      if (accepted > counted) {
        return 'La suma aceptada no puede superar la cantidad contada.';
      }
      const positiveLocations = new Set(
        parts.filter((part) => Number(part.quantity) > 0).map((part) => part.locationId)
      );
      if (positiveLocations.size > 1) {
        return 'Las unidades separadas deben recibirse inicialmente en la misma ubicación de la bodega madre.';
      }
    }
    return null;
  });

  function makeSplit(quantity: string, locationId = ''): ReceiptSplit {
    return { key: `receipt-split-${nextSplitKey++}`, quantity, locationId };
  }

  function updateSplit(detailId: string, splitKey: string, changes: Partial<ReceiptSplit>) {
    splits = {
      ...splits,
      [detailId]: (splits[detailId] ?? []).map((part) => {
        if (part.key !== splitKey) return part;
        const updated = { ...part, ...changes };
        if (Number(updated.quantity) === 0) updated.locationId = '';
        return updated;
      })
    };
    submitError = null;
  }

  function addSplit(detailId: string) {
    splits = {
      ...splits,
      [detailId]: [...(splits[detailId] ?? []), makeSplit('')]
    };
    submitError = null;
  }

  function removeSplit(detailId: string, splitKey: string) {
    const parts = splits[detailId] ?? [];
    if (parts.length <= 1) return;
    splits = { ...splits, [detailId]: parts.filter((part) => part.key !== splitKey) };
    submitError = null;
  }

  function acceptedFor(detailId: string): number {
    return (splits[detailId] ?? []).reduce(
      (total, part) => total + (Number(part.quantity) || 0),
      0
    );
  }

  function productLabel(id: number): string {
    return productLabels.get(id) ?? `Producto #${id}`;
  }

  function unitLabel(id: number): string {
    return unitLabels.get(id) ?? `Unidad #${id}`;
  }

  function formatQuantity(value: string | number): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return String(value);
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(quantity);
  }

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo cargar la ubicación del almacén.';
  }

  async function loadLocations() {
    loading = true;
    locationError = null;
    try {
      const result = await listLocations(purchase.warehouse_id, {
        page: 1,
        size: 200,
        is_active: true,
        lifecycle_status: 'active'
      });
      locations = result.items.filter(
        (location) =>
          location.warehouse_id === purchase.warehouse_id &&
          location.is_active &&
          location.lifecycle_status === 'active'
      );
      pageNumber = result.meta.page;
      hasMoreLocations = result.meta.page < result.meta.pages;
      if (locations.length === 0) {
        if (!hasMoreLocations) {
          locationError =
            'El almacén no tiene ubicaciones activas disponibles para esta recepción.';
        }
      }
    } catch (cause: unknown) {
      locationError = errorMessage(cause);
    } finally {
      loading = false;
    }
  }

  async function loadMoreLocations() {
    if (loadingMore || !hasMoreLocations) return;
    loadingMore = true;
    loadMoreError = null;
    try {
      const nextPage = pageNumber + 1;
      const result = await listLocations(purchase.warehouse_id, {
        page: nextPage,
        size: 200,
        is_active: true,
        lifecycle_status: 'active'
      });
      const activeLocations = result.items.filter(
        (location) =>
          location.warehouse_id === purchase.warehouse_id &&
          location.is_active &&
          location.lifecycle_status === 'active'
      );
      const knownIds = new Set(locations.map((location) => location.id));
      locations = [
        ...locations,
        ...activeLocations.filter((location) => !knownIds.has(location.id))
      ];
      pageNumber = result.meta.page;
      hasMoreLocations = result.meta.page < result.meta.pages;
    } catch (cause: unknown) {
      loadMoreError = errorMessage(cause);
    } finally {
      loadingMore = false;
    }
  }

  async function verify() {
    if (saving || validationError || loading || (locationError && hasAcceptedQuantity)) return;
    saving = true;
    submitError = null;
    try {
      const updated = await purchasesApi.verify(purchase.id, {
        lines: purchase.details.flatMap((detail) =>
          (splits[detail.id] ?? []).map((part) => {
            const quantity = Number(part.quantity);
            return {
              purchase_detail_id: detail.id,
              quantity_accepted: quantity,
              inventory_location_id: quantity > 0 ? part.locationId : null
            };
          })
        )
      });
      onupdated(updated);
    } catch (cause: unknown) {
      submitError = errorMessage(cause);
    } finally {
      saving = false;
    }
  }

  onMount(() => {
    splits = Object.fromEntries(
      purchase.details.map((detail) => [detail.id, [makeSplit(detail.quantity_received)]])
    );
    void loadLocations();
  });
</script>

<form
  class="mt-4 space-y-4 rounded-xl border border-border bg-surface-muted p-4"
  aria-label="Verificar cantidades aceptadas"
  onsubmit={(event) => {
    event.preventDefault();
    void verify();
  }}
>
  <div class="mx-auto w-full max-w-7xl">
    <h3 class="font-semibold text-foreground">Verificación física</h3>
    <p class="mt-1 text-sm text-foreground-muted">
      Confirma lo aceptado y asigna su ubicación. Las cantidades aceptadas ingresan primero en
      cuarentena; no quedan disponibles hasta completar su revisión física.
    </p>
    <p class="mt-2 max-w-4xl text-xs leading-relaxed text-foreground-muted">
      Cada fila crea una unidad logística independiente en la bodega madre. Si parte de la compra se
      quedará como reserva y otra parte se enviará a sucursales, sepárala aquí; luego podrás
      trasladar la unidad completa que corresponda. Todas las unidades del mismo producto se reciben
      en la misma ubicación.
    </p>
    <details class="mt-2 text-xs text-foreground-muted">
      <summary
        class="w-fit cursor-pointer select-none rounded-md text-primary underline decoration-dotted underline-offset-2"
      >
        ¿Qué significa «cuarentena»?
      </summary>
      <p class="mt-2 max-w-3xl leading-relaxed">
        Es mercancía recibida que queda separada mientras se revisa. Todavía no se puede usar ni
        despachar; al terminar la inspección, se libera o se registra con la condición que
        corresponda.
      </p>
    </details>
    <details class="mt-2 text-xs text-foreground-muted">
      <summary
        class="w-fit cursor-pointer select-none rounded-md text-primary underline decoration-dotted underline-offset-2"
      >
        ⓘ Cómo leer la ubicación
      </summary>
      <p class="mt-2 max-w-3xl leading-relaxed">
        Cada opción es una ubicación existente del almacén. Después del código, la ruta abreviada
        sigue este orden: área, pasillo, rack o estante, nivel y posición; los campos vacíos se
        omiten. Después de elegirla verás el desglose completo con el nombre de cada dato.
        Selecciona una ubicación completa; el sistema no combina esos datos por separado y solo
        ofrece ubicaciones activas.
      </p>
    </details>
    {#if hasMoreLocations}
      <Button
        size="sm"
        variant="secondary"
        class="mt-3"
        disabled={loadingMore}
        onclick={() => void loadMoreLocations()}
      >
        {loadingMore ? 'Cargando ubicaciones…' : 'Cargar más ubicaciones'}
      </Button>
    {/if}
    {#if loadMoreError}
      <p class="mt-2 text-sm text-danger" role="alert">{loadMoreError}</p>
    {/if}
  </div>

  {#if loading}
    <p class="mx-auto w-full max-w-7xl text-sm text-foreground-muted">
      Cargando ubicaciones del almacén…
    </p>
  {:else}
    <div class="mx-auto w-full max-w-7xl space-y-3">
      {#each purchase.details as detail (detail.id)}
        <fieldset class="space-y-3 rounded-lg border border-border bg-surface p-3">
          <legend class="sr-only">{productLabel(detail.product_id)}</legend>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="font-medium text-foreground">{productLabel(detail.product_id)}</p>
              <p class="mt-1 text-xs text-foreground-muted">
                {unitLabel(detail.unit_id)} · Contado: {formatQuantity(detail.quantity_received)}
              </p>
            </div>
            <div class="text-right text-xs text-foreground-muted">
              Aceptado: <span class="font-semibold text-foreground"
                >{formatQuantity(acceptedFor(detail.id))}</span
              >
              <span class="mx-1">·</span>
              Rechazado: {formatQuantity(
                Math.max(Number(detail.quantity_received) - acceptedFor(detail.id), 0)
              )}
            </div>
          </div>

          {#each splits[detail.id] ?? [] as part, index (part.key)}
            <div
              class="grid gap-3 rounded-lg border border-border/70 bg-surface-muted/30 p-3 md:grid-cols-[minmax(12rem,0.7fr)_minmax(16rem,1.3fr)_auto] md:items-end"
            >
              <label class="block text-sm" for={`accepted-${detail.id}-${part.key}`}>
                <span class="font-medium text-foreground"
                  >Unidad separada {index + 1} · cantidad aceptada</span
                >
                <input
                  id={`accepted-${detail.id}-${part.key}`}
                  type="number"
                  min="0"
                  max={Number(detail.quantity_received)}
                  step="0.000001"
                  inputmode="decimal"
                  class="mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-foreground"
                  value={part.quantity}
                  oninput={(event) =>
                    updateSplit(detail.id, part.key, { quantity: event.currentTarget.value })}
                  disabled={saving}
                  required
                />
              </label>

              <LocationGridPicker
                id={`${detail.id}-${part.key}`}
                {locations}
                selectedLocationId={part.locationId}
                productName={productLabel(detail.product_id)}
                disabled={saving || Number(part.quantity) === 0 || locations.length === 0}
                {hasMoreLocations}
                onselect={(locationId) => updateSplit(detail.id, part.key, { locationId })}
              />

              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={saving || (splits[detail.id]?.length ?? 0) <= 1}
                onclick={() => removeSplit(detail.id, part.key)}
              >
                Quitar unidad
              </Button>
            </div>
          {/each}
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={saving || splitCount >= 200}
            onclick={() => addSplit(detail.id)}
          >
            + Agregar unidad separada
          </Button>
        </fieldset>
      {/each}
    </div>
  {/if}

  {#if locationError || submitError}
    <div
      class="mx-auto w-full max-w-7xl rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {submitError ?? locationError}
    </div>
  {/if}
  {#if locationError && !hasAcceptedQuantity && !submitError}
    <p class="mx-auto w-full max-w-7xl text-sm text-foreground-muted" role="status">
      No se requiere ubicación si rechazas todas las cantidades; las líneas aceptadas sí necesitan
      una ubicación.
    </p>
  {/if}
  {#if validationError && !loading && !locationError && !submitError}
    <p class="mx-auto w-full max-w-7xl text-sm text-warning" role="status">{validationError}</p>
  {/if}

  <div class="mx-auto flex w-full max-w-7xl flex-wrap justify-end gap-2">
    <Button variant="secondary" disabled={saving} onclick={oncancel}>Cancelar</Button>
    <Button
      type="submit"
      variant="success"
      disabled={saving ||
        loading ||
        Boolean(validationError) ||
        Boolean(submitError) ||
        (Boolean(locationError) && hasAcceptedQuantity)}
    >
      {saving ? 'Verificando…' : 'Verificar y registrar en inventario'}
    </Button>
  </div>
</form>
