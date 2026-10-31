<script lang="ts">
  import { tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import AdjustmentProductPicker from './AdjustmentProductPicker.svelte';
  import type { AdjustmentItemOption } from '../adjustments';
  import { workspaceApi, workspaceField } from '../workspace';
  import { decimalMicros, fromMicros } from '../valuation';
  import { physicalKardexHref } from '../kardex';
  let {
    warehouseId,
    warehouseName,
    onregistered
  }: { warehouseId: string; warehouseName: string; onregistered: () => void } = $props();
  let item = $state<AdjustmentItemOption | null>(null);
  let locations = $state<LocationOut[]>([]);
  let location = $state('');
  let quantity = $state('');
  let cost = $state('');
  let weight = $state('');
  let volume = $state('');
  let date = $state(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(new Date())
  );
  let reason = $state('');
  let reference = $state('');
  let lot = $state('');
  let expiry = $state('');
  let loading = $state(true);
  let locationError = $state('');
  let locationPage = $state(1);
  let locationPages = $state(1);
  let error = $state('');
  let saving = $state(false);
  let success = $state('');
  let reviewed = $state<Record<string, unknown> | null>(null);
  let attempt: { fingerprint: string; key: string } | null = null;
  let total = $derived.by(() => {
    try {
      return fromMicros((decimalMicros(quantity) * decimalMicros(cost) + 500000n) / 1000000n);
    } catch {
      return null;
    }
  });
  async function loadLocations(reset = false) {
    loading = true;
    locationError = '';
    try {
      const data = await listLocations(warehouseId, {
        page: reset ? 1 : locationPage + 1,
        size: 100,
        is_active: true,
        lifecycle_status: 'active'
      });
      const eligible = data.items.filter((row) => row.storage_eligible);
      locations = reset ? eligible : [...locations, ...eligible];
      locationPage = data.meta.page;
      locationPages = data.meta.pages;
    } catch (cause) {
      locationError =
        cause instanceof Error ? cause.message : 'No se pudieron consultar las ubicaciones.';
    } finally {
      loading = false;
    }
  }
  $effect(() => {
    void warehouseId;
    void loadLocations(true);
  });
  async function focusControl(id: string) {
    await tick();
    document.getElementById(id)?.focus();
  }
  function review(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    success = '';
    try {
      if (
        !item ||
        !location ||
        !total ||
        decimalMicros(quantity) <= 0n ||
        decimalMicros(weight) <= 0n ||
        decimalMicros(volume) <= 0n
      )
        throw new Error('Selecciona producto y ubicación; revisa cantidad y medidas físicas.');
      reviewed = {
        warehouse_id: warehouseId,
        inventory_item_id: item.id,
        location_id: location,
        quantity_base: quantity.replace(',', '.'),
        unit_cost: cost.replace(',', '.'),
        gross_weight_kg: weight.replace(',', '.'),
        volume_m3: volume.replace(',', '.'),
        operational_date: date,
        document_reference: reference.trim(),
        reason: reason.trim(),
        lot_code: lot.trim() || null,
        expiry_date: expiry || null
      };
      void focusControl('opening-review-heading');
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Revisa los datos.';
    }
  }
  async function register() {
    if (!reviewed || saving) return;
    const fingerprint = JSON.stringify(reviewed);
    if (!attempt || attempt.fingerprint !== fingerprint)
      attempt = { fingerprint, key: crypto.randomUUID() };
    saving = true;
    error = '';
    try {
      const result = await workspaceApi.opening({ ...reviewed, idempotency_key: attempt.key });
      success = result.source_reference;
      reviewed = null;
      onregistered();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'No se pudo registrar el saldo inicial.';
    } finally {
      saving = false;
    }
  }
</script>

<section
  class="rounded-xl border border-border bg-surface p-4 sm:p-5"
  aria-label="Registrar saldo inicial"
>
  <h3 class="text-lg font-semibold">Registrar saldo inicial</h3>
  {#if !reviewed}<p class="mt-2 max-w-3xl text-sm leading-6 text-foreground-muted">
      Para incorporar existencias contadas al iniciar un producto en el sistema. Solo se admite
      antes de cualquier movimiento o unidad en preparación de ese producto en la empresa. Para
      cambios posteriores utiliza un ajuste documentado.
    </p>{/if}
  {#if success}<div
      role="status"
      class="mt-4 rounded-lg border border-success/30 bg-success/10 p-4"
    >
      <p class="font-semibold">Saldo inicial registrado: {success}</p>
      <p class="mt-1 text-sm">
        La cantidad y el costo ya forman parte del inventario y de su historial.
      </p>
      {#if item}<a
          class="mt-3 inline-block text-sm underline"
          href={physicalKardexHref(warehouseId, item.id)}>Ver primer movimiento</a
        >{/if}
    </div>
  {:else}<form class="mt-5 space-y-4" onsubmit={review}>
      <fieldset disabled={saving || reviewed !== null} hidden={reviewed !== null} class="space-y-4">
        <div>
          <AdjustmentProductPicker
            id="opening-product"
            {warehouseId}
            {warehouseName}
            selected={item}
            onselect={(value) => (item = value)}
            searchItems={workspaceApi.searchItems}
            purpose="el saldo inicial"
          />
        </div>
        {#if locationError}<p
            role="alert"
            class="rounded-lg border border-danger/30 bg-danger/10 p-3"
          >
            {locationError}
          </p>
          <Button type="button" variant="secondary" onclick={() => loadLocations(true)}
            >Reintentar ubicaciones</Button
          >{/if}
        <label class="block text-sm font-medium"
          >Ubicación de almacenamiento<select
            class={workspaceField}
            value={location}
            onchange={(event) => (location = event.currentTarget.value)}
            required
            disabled={loading}
            ><option value=""
              >{loading ? 'Consultando espacios…' : 'Selecciona una ubicación'}</option
            >{#each locations as row (row.id)}<option value={row.id}>{row.code}</option
              >{/each}</select
          ></label
        >
        {#if locationPage < locationPages}<Button
            type="button"
            variant="secondary"
            disabled={loading}
            onclick={() => loadLocations()}>Cargar más ubicaciones</Button
          >{/if}
        {#if !loading && !locationError && !locations.length && locationPage >= locationPages}<div
            class="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm"
          >
            <p>
              No hay ubicaciones de almacenamiento habilitadas. Revisa los espacios de la bodega
              antes de registrar el saldo inicial.
            </p>
            <Button
              type="button"
              variant="secondary"
              class="mt-3"
              onclick={() => loadLocations(true)}>Volver a consultar ubicaciones</Button
            >
          </div>{/if}
        <div class="grid gap-4 sm:grid-cols-2">
          <label class="text-sm font-medium"
            >Cantidad ({item?.base_unit_symbol ?? 'unidad base'})<input
              class={workspaceField}
              bind:value={quantity}
              inputmode="decimal"
              required
            /></label
          ><label class="text-sm font-medium"
            >Costo unitario<input
              class={workspaceField}
              bind:value={cost}
              inputmode="decimal"
              required
            /></label
          ><label class="text-sm font-medium"
            >Peso bruto total (kg)<input
              class={workspaceField}
              bind:value={weight}
              inputmode="decimal"
              required
            /></label
          ><label class="text-sm font-medium"
            >Volumen total (m³)<input
              class={workspaceField}
              bind:value={volume}
              inputmode="decimal"
              required
            /></label
          ><label class="text-sm font-medium"
            >Fecha del saldo inicial<input
              class={workspaceField}
              type="date"
              bind:value={date}
              required
            /></label
          ><label class="text-sm font-medium"
            >Referencia del acta o documento<input
              class={workspaceField}
              bind:value={reference}
              minlength="3"
              maxlength="60"
              required
            /></label
          ><label class="text-sm font-medium"
            >Lote de fabricante (opcional)<input
              class={workspaceField}
              bind:value={lot}
              maxlength="120"
            /></label
          ><label class="text-sm font-medium"
            >Vencimiento (si aplica)<input
              class={workspaceField}
              type="date"
              bind:value={expiry}
            /></label
          >
        </div>
        <label class="block text-sm font-medium"
          >Motivo y respaldo del conteo<textarea
            class={workspaceField}
            bind:value={reason}
            minlength="5"
            maxlength="500"
            required
            placeholder="Ej. Conteo físico inicial según acta…"
          ></textarea></label
        >
      </fieldset>
      {#if !reviewed}<div class="rounded-lg bg-surface-muted/50 p-4">
          <p class="text-sm text-foreground-muted">
            Valor inicial en la moneda configurada para valoración
          </p>
          <p class="mt-1 text-xl font-semibold tabular-nums">
            {total === null
              ? 'Completa cantidad y costo'
              : Number(total).toLocaleString('es-SV', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 6
                })}
          </p>
        </div>{/if}
      {#if reviewed}<div
          role="region"
          aria-labelledby="opening-review-heading"
          class="rounded-lg border border-warning/30 bg-warning/5 p-4"
        >
          <h4
            id="opening-review-heading"
            tabindex="-1"
            class="rounded font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Revisa antes de registrar
          </h4>
          <dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div class="col-span-2">
              <dt class="text-foreground-muted">Producto</dt>
              <dd class="mt-1 font-semibold">{item?.product_name}</dd>
              <dd class="font-mono text-xs text-foreground-muted">{item?.sku}</dd>
            </div>
            <div class="col-span-2">
              <dt class="text-foreground-muted">Bodega y ubicación</dt>
              <dd class="mt-1 break-words">
                {warehouseName} · {locations.find((row) => row.id === location)?.code}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Cantidad</dt>
              <dd class="mt-1 font-semibold tabular-nums">{quantity} {item?.base_unit_symbol}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Costo unitario</dt>
              <dd class="mt-1 tabular-nums">{cost}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Valor inicial</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums">
                {Number(total).toLocaleString('es-SV', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 6
                })}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Fecha</dt>
              <dd class="mt-1">{date.split('-').reverse().join('/')}</dd>
            </div>
            <div class="col-span-2">
              <dt class="text-foreground-muted">Peso y volumen totales</dt>
              <dd class="mt-1">{weight} kg · {volume} m³</dd>
            </div>
            {#if lot || expiry}<div class="col-span-2">
                <dt class="text-foreground-muted">Lote y vencimiento</dt>
                <dd class="mt-1 break-words">
                  {lot || 'Sin lote de fabricante'} · {expiry
                    ? expiry.split('-').reverse().join('/')
                    : 'Sin vencimiento'}
                </dd>
              </div>{/if}
            <div class="col-span-2">
              <dt class="text-foreground-muted">Documento y motivo</dt>
              <dd class="mt-1 break-words">{reference} · {reason}</dd>
            </div>
          </dl>
          <p class="mt-4 text-sm text-foreground-muted">
            Importes en la moneda configurada para valoración. La confirmación crea una entrada
            histórica y actualiza las existencias.
          </p>
          <div class="mt-4 flex flex-wrap gap-3">
            <Button type="button" disabled={saving} onclick={register}
              >{saving ? 'Registrando…' : 'Confirmar saldo inicial'}</Button
            ><Button
              type="button"
              variant="secondary"
              disabled={saving}
              onclick={() => {
                reviewed = null;
                error = '';
                void focusControl('opening-product');
              }}>Volver a revisar</Button
            >
          </div>
        </div>{:else}<Button type="submit" disabled={loading || !locations.length}
          >Revisar saldo inicial</Button
        >{/if}
      {#if error}<p
          role="alert"
          class="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm"
        >
          {error}
        </p>{/if}
    </form>{/if}
</section>
