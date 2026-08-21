<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '../services';
  import {
    PACKAGING_TYPE_LABEL,
    type InventoryItem,
    type PackagingCreateInput,
    type PackagingDefinition,
    type PackagingType
  } from '../types';

  interface UnitOption {
    id: number;
    label: string;
  }

  interface Props {
    productId?: number;
    variantId?: string;
    defaultBaseUnitId: number;
    unitOptions: UnitOption[];
    canManage?: boolean;
  }

  let { productId, variantId, defaultBaseUnitId, unitOptions, canManage = false }: Props = $props();

  let item = $state<InventoryItem | null>(null);
  let definitions = $state<PackagingDefinition[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let formOpen = $state(false);
  let baseUnitId = $state(0);
  let supersedesId = $state<string | null>(null);
  let code = $state('');
  let name = $state('');
  let packagingType = $state<PackagingType>('box');
  let baseQuantity = $state<number | undefined>(1);
  let grossWeightKg = $state<number | undefined>(undefined);
  let lengthM = $state<number | undefined>(undefined);
  let widthM = $state<number | undefined>(undefined);
  let heightM = $state<number | undefined>(undefined);
  let volumeM3 = $state<number | undefined>(undefined);
  let stackable = $state(true);
  let maxStack = $state<number | undefined>(undefined);

  const inputClass =
    'mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  function numeric(value: number | undefined): number | null {
    return value != null && Number.isFinite(value) && value > 0 ? value : null;
  }

  function unitName(id: number): string {
    return unitOptions.find((unit) => unit.id === id)?.label ?? `Unidad #${id}`;
  }

  function hasValidTarget(): boolean {
    const hasProduct = productId != null;
    const hasVariant = variantId != null && variantId.trim().length > 0;
    if (hasProduct === hasVariant) return false;
    return (
      !hasProduct || (typeof productId === 'number' && Number.isInteger(productId) && productId > 0)
    );
  }

  function resetForm() {
    supersedesId = null;
    code = '';
    name = '';
    packagingType = 'box';
    baseQuantity = 1;
    grossWeightKg = undefined;
    lengthM = undefined;
    widthM = undefined;
    heightM = undefined;
    volumeM3 = undefined;
    stackable = true;
    maxStack = undefined;
  }

  async function load() {
    loading = true;
    error = null;
    success = null;
    if (!hasValidTarget()) {
      item = null;
      definitions = [];
      error = 'La configuración de inventario debe señalar un producto o una variante válida.';
      loading = false;
      return;
    }
    try {
      item = await inventoryApi.getItemByTarget({ productId, variantId });
      definitions = item ? await inventoryApi.listPackaging(item.id) : [];
      if (item) baseUnitId = item.base_unit_id;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudieron cargar las presentaciones.';
    } finally {
      loading = false;
    }
  }

  async function activateInventory() {
    if (!baseUnitId || !hasValidTarget()) return;
    saving = true;
    error = null;
    success = null;
    try {
      item = await inventoryApi.createItem({
        ...(productId != null ? { product_id: productId } : {}),
        ...(variantId ? { variant_id: variantId } : {}),
        base_unit_id: baseUnitId
      });
      definitions = [];
      success = 'Identidad de inventario creada. Ahora puede registrar sus presentaciones.';
      formOpen = true;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo activar el inventario.';
    } finally {
      saving = false;
    }
  }

  function startVersion(definition: PackagingDefinition) {
    supersedesId = definition.id;
    code = definition.code;
    name = definition.name;
    packagingType = definition.packaging_type;
    baseQuantity = definition.base_quantity;
    grossWeightKg = definition.gross_weight_kg ?? undefined;
    lengthM = definition.length_m ?? undefined;
    widthM = definition.width_m ?? undefined;
    heightM = definition.height_m ?? undefined;
    volumeM3 = definition.volume_m3 ?? undefined;
    stackable = definition.stackable;
    maxStack = definition.max_stack ?? undefined;
    formOpen = true;
    error = null;
    success = null;
  }

  async function saveDefinition(event: SubmitEvent) {
    event.preventDefault();
    if (!item) return;
    error = null;
    success = null;

    const quantity = numeric(baseQuantity);
    const dimensions = [numeric(lengthM), numeric(widthM), numeric(heightM)];
    const dimensionsPresent = dimensions.filter((value) => value != null).length;
    const normalizedCode = code.trim().toUpperCase();
    const normalizedName = name.trim();
    const parsedMaxStack = maxStack ?? null;
    if (!normalizedCode || normalizedName.length < 2 || quantity == null) {
      error = 'Complete código, nombre y cantidad contenida con valores válidos.';
      return;
    }
    if (!/^[A-Z0-9._-]+$/.test(normalizedCode)) {
      error = 'El código solo puede contener letras, números, punto, guion y guion bajo.';
      return;
    }
    if (dimensionsPresent !== 0 && dimensionsPresent !== 3) {
      error = 'Largo, ancho y alto deben registrarse juntos.';
      return;
    }
    if (
      stackable &&
      parsedMaxStack != null &&
      (!Number.isInteger(parsedMaxStack) || parsedMaxStack < 1)
    ) {
      error = 'El máximo de apilado debe ser un número entero mayor que cero.';
      return;
    }

    const body: PackagingCreateInput = {
      code: normalizedCode,
      name: normalizedName,
      packaging_type: packagingType,
      base_quantity: quantity,
      measures: {
        gross_weight_kg: numeric(grossWeightKg),
        length_m: dimensions[0],
        width_m: dimensions[1],
        height_m: dimensions[2],
        volume_m3: numeric(volumeM3)
      },
      stackable,
      max_stack: stackable ? parsedMaxStack : null,
      supersedes_id: supersedesId
    };

    saving = true;
    try {
      await inventoryApi.createPackaging(item.id, body);
      definitions = await inventoryApi.listPackaging(item.id);
      success = supersedesId ? 'Nueva versión registrada.' : 'Presentación registrada.';
      resetForm();
      formOpen = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo guardar la presentación.';
    } finally {
      saving = false;
    }
  }

  async function deactivate(definition: PackagingDefinition) {
    if (!item || !window.confirm(`¿Desactivar la presentación ${definition.name}?`)) return;
    saving = true;
    error = null;
    success = null;
    try {
      await inventoryApi.deactivatePackaging(item.id, definition.id);
      definitions = await inventoryApi.listPackaging(item.id);
      success = 'Presentación desactivada sin eliminar su historial.';
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo desactivar la presentación.';
    } finally {
      saving = false;
    }
  }

  $effect(() => {
    void productId;
    void variantId;
    baseUnitId = defaultBaseUnitId;
    void load();
  });
</script>

<div class="space-y-4" aria-busy={loading || saving}>
  <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">
          Empaques y presentaciones de inventario
        </h3>
        <span class="rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning"
          >Empaque</span
        >
      </div>
      <p class="mt-1 text-xs text-foreground-muted">
        Define el empaque completo con el que se recibe, almacena y mueve el producto. Estas medidas
        son independientes de las medidas de la unidad base.
      </p>
    </div>
    {#if item && canManage}
      <Button
        size="sm"
        variant="secondary"
        onclick={() => {
          resetForm();
          formOpen = !formOpen;
        }}
      >
        {formOpen ? 'Cerrar formulario' : 'Nueva presentación'}
      </Button>
    {/if}
  </div>

  <div
    class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-xs text-foreground-muted"
  >
    <p class="font-semibold text-warning">Medidas del empaque completo</p>
    <p class="mt-1">
      Registre aquí el peso y volumen del saco, caja, paquete o bulto cerrado. Para calcular la
      capacidad se utiliza esta medida o la medición real de la unidad logística recibida; no se
      suma con la medida de la unidad base.
    </p>
  </div>

  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if success}
    <div
      class="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success"
      role="status"
    >
      {success}
    </div>
  {/if}

  {#if loading}
    <div class="h-28 rounded-xl skeleton" role="status">
      <span class="sr-only">Cargando presentaciones de inventario…</span>
    </div>
  {:else if !item}
    <div class="rounded-xl border border-dashed border-border p-5">
      <p class="text-sm font-medium text-foreground">Inventario aún no habilitado</p>
      <p class="mt-1 text-xs text-foreground-muted">
        Seleccione la unidad base que representará las existencias. No podrá mezclar el producto
        padre con sus variantes.
      </p>
      {#if canManage}
        <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
          <label class="flex-1 text-xs text-foreground-muted">
            Unidad base
            <select class={inputClass} bind:value={baseUnitId}>
              {#each unitOptions as unit (unit.id)}
                <option value={unit.id}>{unit.label}</option>
              {/each}
            </select>
          </label>
          <Button size="sm" onclick={activateInventory} disabled={saving || !baseUnitId}>
            {saving ? 'Activando…' : 'Habilitar inventario'}
          </Button>
        </div>
      {/if}
    </div>
  {:else}
    <div
      class="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-surface-muted/30 px-3 py-2 text-xs text-foreground-muted"
    >
      <span
        >Unidad base: <strong class="text-foreground">{unitName(item.base_unit_id)}</strong></span
      >
      <span
        >{definitions.filter((definition) => definition.is_current && definition.is_active).length} presentación(es)
        vigente(s)</span
      >
    </div>

    {#if formOpen && canManage}
      <form
        class="rounded-xl border border-border bg-surface-muted/15 p-4"
        onsubmit={saveDefinition}
      >
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label class="text-xs text-foreground-muted"
            >Código
            <input
              class={inputClass}
              bind:value={code}
              minlength="1"
              maxlength="60"
              pattern="[A-Za-z0-9._-]+"
              disabled={supersedesId != null}
              required
            />
          </label>
          <label class="text-xs text-foreground-muted sm:col-span-2"
            >Nombre
            <input class={inputClass} bind:value={name} minlength="2" maxlength="120" required />
          </label>
          <label class="text-xs text-foreground-muted"
            >Tipo
            <select class={inputClass} bind:value={packagingType}>
              {#each Object.entries(PACKAGING_TYPE_LABEL) as [value, label]}
                <option {value}>{label}</option>
              {/each}
            </select>
          </label>
          <label class="text-xs text-foreground-muted"
            >Cantidad base contenida por empaque
            <input
              class={inputClass}
              type="number"
              min="0.000001"
              step="any"
              bind:value={baseQuantity}
              required
            />
          </label>
          <label class="text-xs text-foreground-muted"
            >Peso bruto del empaque completo (kg)
            <input
              class={inputClass}
              type="number"
              min="0.000001"
              step="any"
              bind:value={grossWeightKg}
            />
          </label>
          <label class="text-xs text-foreground-muted"
            >Volumen del empaque completo (m³)
            <input
              class={inputClass}
              type="number"
              min="0.000001"
              step="any"
              bind:value={volumeM3}
            />
          </label>
          <label class="text-xs text-foreground-muted"
            >Largo exterior del empaque (m)
            <input
              class={inputClass}
              type="number"
              min="0.000001"
              step="any"
              bind:value={lengthM}
            />
          </label>
          <label class="text-xs text-foreground-muted"
            >Ancho exterior del empaque (m)
            <input class={inputClass} type="number" min="0.000001" step="any" bind:value={widthM} />
          </label>
          <label class="text-xs text-foreground-muted"
            >Alto exterior del empaque (m)
            <input
              class={inputClass}
              type="number"
              min="0.000001"
              step="any"
              bind:value={heightM}
            />
          </label>
          <label
            class="flex items-center gap-2 self-end rounded-lg border border-border px-3 py-2 text-xs text-foreground"
          >
            <input type="checkbox" bind:checked={stackable} /> Apilable
          </label>
          {#if stackable}
            <label class="text-xs text-foreground-muted"
              >Máximo de apilado
              <input class={inputClass} type="number" min="1" step="1" bind:value={maxStack} />
            </label>
          {/if}
        </div>
        <p class="mt-3 text-[11px] text-foreground-muted">
          Si faltan peso o volumen del empaque, la mercancía solo podrá recibirse en cuarentena
          hasta ser medida.
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onclick={() => {
              resetForm();
              formOpen = false;
            }}>Cancelar</Button
          >
          <Button type="submit" size="sm" disabled={saving}
            >{saving ? 'Guardando…' : supersedesId ? 'Crear versión' : 'Guardar'}</Button
          >
        </div>
      </form>
    {/if}

    {#if definitions.length}
      <div class="overflow-x-auto rounded-xl border border-border">
        <table class="w-full min-w-[760px] text-xs">
          <caption class="sr-only">Presentaciones y medidas físicas del inventario</caption>
          <thead class="border-b border-border bg-surface-muted/30 text-left text-foreground-muted">
            <tr
              ><th scope="col" class="px-3 py-2">Presentación</th><th scope="col" class="px-3 py-2"
                >Conversión</th
              ><th scope="col" class="px-3 py-2">Peso del empaque</th><th
                scope="col"
                class="px-3 py-2">Volumen del empaque</th
              ><th scope="col" class="px-3 py-2">Versión</th><th scope="col" class="px-3 py-2"
                >Estado</th
              >{#if canManage}<th scope="col" class="px-3 py-2">Acciones</th>{/if}</tr
            >
          </thead>
          <tbody class="divide-y divide-border">
            {#each definitions as definition (definition.id)}
              <tr class:opacity-60={!definition.is_active}>
                <td class="px-3 py-2"
                  ><p class="font-medium text-foreground">{definition.name}</p>
                  <p class="font-mono text-[10px] text-foreground-muted">
                    {definition.code} · {PACKAGING_TYPE_LABEL[definition.packaging_type]}
                  </p></td
                >
                <td class="px-3 py-2 text-foreground-muted"
                  >{definition.base_quantity.toLocaleString('es-SV')}
                  {unitName(item.base_unit_id)}</td
                >
                <td class="px-3 py-2 font-mono text-foreground"
                  >{definition.gross_weight_kg == null
                    ? 'Sin medir'
                    : `${definition.gross_weight_kg.toLocaleString('es-SV')} kg`}</td
                >
                <td class="px-3 py-2 font-mono text-foreground"
                  >{definition.volume_m3 == null
                    ? 'Sin medir'
                    : `${definition.volume_m3.toLocaleString('es-SV')} m³`}</td
                >
                <td class="px-3 py-2 font-mono text-foreground">v{definition.version}</td>
                <td class="px-3 py-2 text-foreground-muted"
                  >{definition.is_current && definition.is_active
                    ? 'Vigente'
                    : definition.is_active
                      ? 'Histórica'
                      : 'Inactiva'}</td
                >
                {#if canManage}
                  <td class="whitespace-nowrap px-3 py-2">
                    {#if definition.is_current && definition.is_active}
                      <button
                        class="mr-3 font-medium text-primary hover:underline disabled:opacity-40"
                        type="button"
                        disabled={saving}
                        aria-label={`Crear nueva versión de ${definition.name}`}
                        onclick={() => startVersion(definition)}>Nueva versión</button
                      >
                      <button
                        class="font-medium text-danger hover:underline disabled:opacity-40"
                        type="button"
                        disabled={saving}
                        aria-label={`Desactivar ${definition.name}`}
                        onclick={() => void deactivate(definition)}>Desactivar</button
                      >
                    {/if}
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div
        class="rounded-xl border border-dashed border-border p-5 text-center text-xs text-foreground-muted"
      >
        No hay presentaciones registradas.
      </div>
    {/if}
  {/if}
</div>
