<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { adjustmentInputClass, adjustmentNoticeClass } from '$lib/features/inventory/adjustment-styles';
  import { inventoryApi } from '$lib/features/inventory/services';
  import type { HandlingUnit } from '$lib/features/inventory/types';
  import { inventoryAdjustmentsApi, type AdjustmentDirection, type AdjustmentLineInput, type AdjustmentOptions } from '$lib/features/inventory/adjustments';
  import { inventoryTransfersApi, type InventoryTransfer } from '$lib/features/inventory/transfer-documents';
  import { getWarehouses } from '$lib/services/warehouses';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  type DraftLine = {
    inventory_item_id: string;
    transfer_detail_id?: string;
    direction: AdjustmentDirection;
    quantity_base: string;
    stock_status: 'available' | 'quarantine' | 'damaged' | 'in_transit';
    location_id: string;
    handling_unit_id: string;
    cost_mode: 'none' | 'unit' | 'total';
    cost: string;
    actual_gross_weight_kg: string;
    actual_volume_m3: string;
    units: HandlingUnit[];
    loadingUnits: boolean;
  };

  let { transferId = '', incidentId = '', detailId = '' }: { transferId?: string; incidentId?: string; detailId?: string } = $props();
  const inputClass = adjustmentInputClass;
  const noticeClass = adjustmentNoticeClass;
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/El_Salvador', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const canAdjust = $derived(permissions.hasPermission('inventory:adjust'));
  const canSeeCost = $derived(permissions.hasPermission('inventory:valuation'));
  let warehouses = $state<Warehouse[]>([]);
  let warehouseId = $state('');
  let options = $state<AdjustmentOptions | null>(null);
  let lines = $state<DraftLine[]>([newLine()]);
  let operationalDate = $state(today);
  let accountingDate = $state(today);
  let reason = $state('');
  let documentReference = $state('');
  let notes = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let transfer = $state<InventoryTransfer | null>(null);
  let transferLineId = $state('');
  let transferLocked = $derived(Boolean(transferId));
  let scopeKey = '';
  let loadSequence = 0;
  let optionsSequence = 0;

  function newLine(): DraftLine {
    return {
      inventory_item_id: '', direction: 'increase', quantity_base: '', stock_status: 'quarantine',
      location_id: '', handling_unit_id: '', cost_mode: 'none', cost: '',
      actual_gross_weight_kg: '', actual_volume_m3: '', units: [], loadingUnits: false
    };
  }

  function errorText(cause: unknown): string {
    return cause instanceof Error ? cause.message : 'No se pudo cargar el formulario.';
  }

  async function loadPage() {
    const sequence = ++loadSequence;
    const activeScope = `${company.id ?? ''}:${branch.id ?? ''}`;
    scopeKey = activeScope;
    optionsSequence++;
    loading = true;
    error = null;
    options = null;
    transfer = null;
    lines = [newLine()];
    try {
      const firstPage = await getWarehouses({ branchId: branch.id ?? undefined, page: 1, size: 100, status: 'active' });
      if (sequence !== loadSequence || activeScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      warehouses = firstPage.items.filter((item) => item.status === 'active' && !item.type.toLowerCase().includes('transit'));
      if (transferId && incidentId && detailId) {
        const loadedTransfer = await inventoryTransfersApi.get(transferId);
        if (sequence !== loadSequence || activeScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
        const openIncident = loadedTransfer.incidents.find((item) => item.id === incidentId && item.status === 'open');
        const selectedLine = loadedTransfer.lines.find((item) => item.id === detailId);
        if (loadedTransfer.status !== 'incident' || !openIncident || !selectedLine || Number(selectedLine.quantity_in_transit) <= 0 || !selectedLine.transit_handling_unit_id || !loadedTransfer.vehicle) {
          throw new Error('La incidencia ya no tiene una cantidad en tránsito ajustable. Actualiza el traslado.');
        }
        const vehicles = await inventoryTransfersApi.listVehicles();
        if (sequence !== loadSequence || activeScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
        const vehicle = vehicles.find((item) => item.id === loadedTransfer.vehicle?.id);
        if (!vehicle) throw new Error('No se encontró el vehículo y su bodega de tránsito.');
        const transitUnits = await inventoryApi.listHandlingUnits(vehicle.transit_warehouse_id, {
          inventoryItemId: selectedLine.inventory_item_id,
          stockStatus: 'in_transit'
        });
        if (sequence !== loadSequence || activeScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
        const unit = transitUnits.find((item) => item.id === selectedLine.transit_handling_unit_id);
        if (!unit) throw new Error('La unidad real del traslado ya no está disponible en tránsito.');
        transfer = loadedTransfer;
        transferLineId = selectedLine.id;
        warehouseId = loadedTransfer.origin_warehouse_id;
        lines = [{
          ...newLine(), inventory_item_id: selectedLine.inventory_item_id, direction: 'decrease',
          quantity_base: String(selectedLine.quantity_in_transit), stock_status: 'in_transit',
          location_id: unit.location_id, handling_unit_id: unit.id, transfer_detail_id: selectedLine.id, units: [unit]
        }];
      } else {
        warehouseId = warehouses.find((item) => item.isCentral)?.id ?? warehouses[0]?.id ?? '';
        if (warehouseId) {
          const loadedOptions = await inventoryAdjustmentsApi.options(warehouseId);
          if (sequence !== loadSequence || activeScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
          options = loadedOptions;
        }
      }
    } catch (cause) {
      if (sequence === loadSequence) error = errorText(cause);
    } finally {
      if (sequence === loadSequence) loading = false;
    }
  }

  async function changeWarehouse(nextId: string) {
    const sequence = ++optionsSequence;
    const requestScope = `${company.id ?? ''}:${branch.id ?? ''}`;
    warehouseId = nextId;
    options = null;
    lines = [newLine()];
    if (!nextId) return;
    try {
      const result = await inventoryAdjustmentsApi.options(nextId);
      if (sequence === optionsSequence && requestScope === `${company.id ?? ''}:${branch.id ?? ''}` && warehouseId === nextId) options = result;
    } catch (cause) {
      if (sequence === optionsSequence && requestScope === `${company.id ?? ''}:${branch.id ?? ''}`) error = errorText(cause);
    }
  }

  async function changeItem(index: number, itemId: string) {
    const line = lines[index];
    if (!line) return;
    line.inventory_item_id = itemId;
    line.handling_unit_id = '';
    line.location_id = '';
    line.units = [];
    if (line.direction === 'decrease' && itemId && warehouseId) {
      const requestScope = `${company.id ?? ''}:${branch.id ?? ''}`;
      const requestWarehouse = warehouseId;
      line.loadingUnits = true;
      try {
        const result = (await inventoryApi.listHandlingUnits(requestWarehouse, { inventoryItemId: itemId }))
          .filter((unit) => unit.stock_status !== 'blocked' && unit.stock_status !== 'in_transit' && !unit.closed_at);
        if (requestScope === `${company.id ?? ''}:${branch.id ?? ''}` && warehouseId === requestWarehouse && line.inventory_item_id === itemId && line.direction === 'decrease') line.units = result;
      } catch (cause) {
        if (requestScope === `${company.id ?? ''}:${branch.id ?? ''}` && line.inventory_item_id === itemId) error = errorText(cause);
      } finally {
        if (line.inventory_item_id === itemId) line.loadingUnits = false;
      }
    }
    lines = [...lines];
  }

  async function changeDirection(index: number, direction: AdjustmentDirection) {
    const line = lines[index];
    if (!line) return;
    line.direction = direction;
    line.stock_status = direction === 'increase' ? 'quarantine' : 'available';
    line.handling_unit_id = '';
    line.location_id = '';
    line.cost_mode = 'none';
    line.cost = '';
    line.actual_gross_weight_kg = '';
    line.actual_volume_m3 = '';
    await changeItem(index, line.inventory_item_id);
    lines = [...lines];
  }

  function chooseHandlingUnit(index: number, unitId: string) {
    const line = lines[index];
    const unit = line?.units.find((item) => item.id === unitId);
    if (!line || !unit) return;
    line.handling_unit_id = unit.id;
    line.location_id = unit.location_id;
    line.stock_status = unit.stock_status === 'blocked' || unit.stock_status === 'in_transit' ? 'available' : unit.stock_status;
    line.quantity_base = String(unit.quantity_base);
    lines = [...lines];
  }

  function linePayload(line: DraftLine): AdjustmentLineInput {
    if (line.direction === 'increase') {
      return {
        inventory_item_id: line.inventory_item_id, location_id: line.location_id,
        direction: 'increase', quantity_base: line.quantity_base, stock_status: 'quarantine',
        documented_unit_cost: canSeeCost && line.cost_mode === 'unit' ? line.cost : null,
        documented_total_cost: canSeeCost && line.cost_mode === 'total' ? line.cost : null,
        actual_gross_weight_kg: line.actual_gross_weight_kg,
        actual_volume_m3: line.actual_volume_m3
      };
    }
    return {
      inventory_item_id: line.inventory_item_id, location_id: line.location_id,
      direction: 'decrease', quantity_base: line.quantity_base, stock_status: line.stock_status,
      handling_unit_id: line.handling_unit_id,
      ...(line.transfer_detail_id ? { transfer_detail_id: line.transfer_detail_id } : {})
    };
  }

  async function saveDraft(event: SubmitEvent) {
    event.preventDefault();
    if (!canAdjust || saving || !warehouseId || (!options && !transfer) || lines.length === 0) return;
    error = null;
    notice = null;
    saving = true;
    const submissionScope = scopeKey;
    try {
      const payload = {
        warehouse_id: warehouseId, operational_date: operationalDate, accounting_date: accountingDate,
        reason: reason.trim(), document_reference: documentReference.trim(), notes: notes.trim() || null,
        lines: lines.map(linePayload),
        ...(transfer ? { transfer_id: transfer.id, transfer_incident_id: incidentId } : {})
      };
      const created = await inventoryAdjustmentsApi.create(payload);
      if (submissionScope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      notice = 'Borrador guardado. No se han movido existencias.';
      await goto(`/inventory/adjustments/${created.id}`);
    } catch (cause) {
      if (submissionScope === `${company.id ?? ''}:${branch.id ?? ''}`) error = errorText(cause);
    } finally {
      saving = false;
    }
  }

  onMount(() => { void loadPage(); });
  $effect(() => {
    const currentScope = `${company.id ?? ''}:${branch.id ?? ''}`;
    if (scopeKey && currentScope !== scopeKey) void loadPage();
  });
</script>

<svelte:head><title>Nuevo ajuste de inventario | GestionaSV</title></svelte:head>

<main class="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6">
  <header class="space-y-2">
    <a class="text-sm font-medium text-primary hover:underline" href="/inventory/adjustments">← Ajustes de inventario</a>
    <div><p class="text-xs font-semibold uppercase tracking-wider text-primary">Inventario · control trazable</p><h1 class="mt-1 text-2xl font-semibold text-foreground">Nuevo ajuste</h1><p class="mt-1 max-w-3xl text-sm text-foreground-muted">Guarda un borrador respaldado por documento. La aprobación tampoco mueve existencias; aplicar requiere confirmación aparte.</p></div>
  </header>

  {#if loading}
    <div class="rounded-xl border border-border bg-surface p-6 text-sm text-foreground-muted" role="status">Cargando bodegas e información autorizada…</div>
  {:else if error && !options && !transfer}
    <div class={`${noticeClass} border-danger/30 bg-danger/10`} role="alert">{error}</div>
  {:else if !canAdjust}
    <div class={`${noticeClass} border-warning/30 bg-warning/10`} role="status">Tu perfil puede consultar el módulo, pero no tiene permiso para crear ajustes.</div>
  {:else}
    {#if transfer}
      <section class="rounded-xl border border-warning/30 bg-warning/5 p-4" aria-labelledby="incident-heading">
        <h2 id="incident-heading" class="font-semibold text-foreground">Pérdida vinculada a {transfer.code}</h2>
        <p class="mt-1 text-sm text-foreground-muted">Se ajustará únicamente la cantidad que sigue en tránsito en la incidencia abierta. La cantidad recibida permanece separada.</p>
      </section>
    {/if}

    <form class="space-y-5" onsubmit={saveDraft}>
      <section class="grid gap-4 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Datos del ajuste">
        <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2">Bodega
          <select class={inputClass} value={warehouseId} disabled={transferLocked || saving} onchange={(event) => void changeWarehouse(event.currentTarget.value)} required>
            <option value="">Selecciona una bodega</option>
            {#each warehouses as warehouse (warehouse.id)}<option value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>{/each}
          </select>
          {#if transferLocked}<span class="block text-xs font-normal text-foreground-muted">El ámbito viene del traslado y no se puede cambiar.</span>{/if}
        </label>
        <label class="space-y-1 text-sm font-medium text-foreground">Fecha operativa<input class={inputClass} type="date" bind:value={operationalDate} required /></label>
        <label class="space-y-1 text-sm font-medium text-foreground">Fecha contable<input class={inputClass} type="date" bind:value={accountingDate} required /></label>
        <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2 lg:col-span-2">Motivo<textarea class={`${inputClass} min-h-20`} minlength="5" maxlength="4000" bind:value={reason} required disabled={saving}></textarea></label>
        <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2">Referencia documental<input class={inputClass} maxlength="240" bind:value={documentReference} required placeholder="Acta, reporte o referencia interna" disabled={saving} /></label>
        <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2 lg:col-span-4">Notas<textarea class={`${inputClass} min-h-16`} maxlength="4000" bind:value={notes}></textarea></label>
      </section>

      <section class="space-y-4 rounded-xl border border-border bg-surface p-4" aria-labelledby="lines-heading">
        <div class="flex flex-wrap items-start justify-between gap-3"><div><h2 id="lines-heading" class="text-lg font-semibold text-foreground">Productos y cantidades</h2><p class="text-sm text-foreground-muted">Usa la unidad base registrada. Los costos se escriben como costo unitario o total; el servidor calcula el valor equivalente.</p></div>
          {#if !transferLocked}<Button variant="secondary" onclick={() => lines = [...lines, newLine()]} disabled={!options || saving}>Agregar producto</Button>{/if}
        </div>
        {#if !transferLocked && !options}<div class={`${noticeClass} border-warning/30 bg-warning/10`} role="status">No se pudieron cargar artículos y ubicaciones. Selecciona de nuevo la bodega o reintenta la página.</div>{/if}
        {#each lines as line, index (index)}
          <article class="space-y-4 rounded-xl border border-border p-4">
            <div class="flex items-center justify-between gap-3"><h3 class="font-semibold text-foreground">Producto {index + 1}</h3>{#if !transferLocked && lines.length > 1}<Button variant="ghost" size="sm" onclick={() => lines = lines.filter((_, row) => row !== index)}>Quitar</Button>{/if}</div>
            {#if transferLocked}
              <div class="rounded-lg bg-surface-muted p-3 text-sm"><p class="font-medium text-foreground">{transfer?.lines.find((item) => item.id === transferLineId)?.product_name}</p><p class="mt-1 font-mono text-xs text-foreground-muted">{transfer?.lines.find((item) => item.id === transferLineId)?.sku ?? 'SKU sin registrar'} · {line.units[0]?.code} · {line.units[0]?.lot_code ? `Lote ${line.units[0].lot_code}` : 'Sin lote'}</p><p class="mt-1 text-foreground-muted">Saldo en tránsito: {line.quantity_base} {transfer?.lines.find((item) => item.id === transferLineId)?.base_unit_symbol ?? transfer?.lines.find((item) => item.id === transferLineId)?.base_unit_name ?? 'unidad base'}</p></div>
            {:else}
              <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label class="space-y-1 text-sm font-medium text-foreground lg:col-span-2">Artículo
                  <select class={inputClass} value={line.inventory_item_id} disabled={!options || saving} onchange={(event) => void changeItem(index, event.currentTarget.value)} required><option value="">Selecciona producto</option>{#each options?.items ?? [] as item (item.id)}<option value={item.id}>{item.product_name} · {item.sku ?? 'SKU sin registrar'}</option>{/each}</select>
                </label>
                <label class="space-y-1 text-sm font-medium text-foreground">Dirección
                  <select class={inputClass} value={line.direction} disabled={saving} onchange={(event) => void changeDirection(index, event.currentTarget.value as AdjustmentDirection)}><option value="increase">Entrada positiva</option><option value="decrease">Salida negativa</option></select>
                </label>
                {#if line.direction === 'increase'}
                  <label class="space-y-1 text-sm font-medium text-foreground">Cantidad en unidad base<input class={inputClass} type="number" min="0.000001" step="0.000001" bind:value={line.quantity_base} required /></label>
                  <label class="space-y-1 text-sm font-medium text-foreground">Ubicación de cuarentena<select class={inputClass} bind:value={line.location_id} required><option value="">Selecciona ubicación</option>{#each options?.locations ?? [] as location (location.id)}<option value={location.id}>{location.code} · {location.location_type}</option>{/each}</select></label>
                  <label class="space-y-1 text-sm font-medium text-foreground">Peso bruto (kg)<input class={inputClass} type="number" min="0.000001" step="0.000001" bind:value={line.actual_gross_weight_kg} required /></label>
                  <label class="space-y-1 text-sm font-medium text-foreground">Volumen (m³)<input class={inputClass} type="number" min="0.000001" step="0.000001" bind:value={line.actual_volume_m3} required /></label>
                  {#if canSeeCost}
                    <label class="space-y-1 text-sm font-medium text-foreground">Costo documentado<select class={inputClass} bind:value={line.cost_mode}><option value="none">Sin costo documentado</option><option value="unit">Costo unitario</option><option value="total">Costo total</option></select></label>
                    {#if line.cost_mode !== 'none'}<label class="space-y-1 text-sm font-medium text-foreground">{line.cost_mode === 'unit' ? 'Costo por unidad base' : 'Costo total'}<input class={inputClass} type="number" min="0" step="0.000001" bind:value={line.cost} required /></label>{/if}
                  {/if}
                {:else}
                  <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2">Unidad logística
                    <select class={inputClass} value={line.handling_unit_id} disabled={line.loadingUnits || !line.inventory_item_id || saving} onchange={(event) => chooseHandlingUnit(index, event.currentTarget.value)} required><option value="">{line.loadingUnits ? 'Buscando unidades…' : 'Selecciona unidad existente'}</option>{#each line.units as unit (unit.id)}<option value={unit.id}>{unit.code} · {unit.quantity_base} {options?.items.find((item) => item.id === line.inventory_item_id)?.base_unit_symbol ?? 'base'} · {unit.stock_status} · {unit.lot_code ?? 'sin lote'}</option>{/each}</select>
                  </label>
                  {#if line.handling_unit_id}
                    <label class="space-y-1 text-sm font-medium text-foreground">Cantidad a retirar<input class={inputClass} type="number" min="0.000001" max={line.units.find((unit) => unit.id === line.handling_unit_id)?.quantity_base} step="0.000001" bind:value={line.quantity_base} required /></label>
                    <label class="space-y-1 text-sm font-medium text-foreground">Condición<select class={inputClass} bind:value={line.stock_status}><option value="available">Disponible</option><option value="quarantine">Cuarentena</option><option value="damaged">Dañado</option></select></label>
                  {/if}
                {/if}
              </div>
            {/if}
          </article>
        {/each}
      </section>

      <div class="rounded-xl border border-warning/30 bg-warning/5 p-4 text-sm text-foreground"><p class="font-semibold">Este paso solo guarda un borrador</p><p class="mt-1 text-foreground-muted">Adjunta un comprobante en el detalle, aprueba la versión revisada y aplica el ajuste con confirmación explícita. Abrir o consultar un ajuste nunca mueve inventario.</p></div>
      {#if error}<p class={`${noticeClass} border-danger/30 bg-danger/10`} role="alert">{error}</p>{/if}
      {#if notice}<p class={`${noticeClass} border-success/30 bg-success/10`} role="status">{notice}</p>{/if}
      <div class="flex flex-wrap justify-end gap-2"><Button variant="secondary" onclick={() => void goto('/inventory/adjustments')}>Cancelar</Button><Button type="submit" disabled={saving || !canAdjust || !warehouseId || !reason.trim() || !documentReference.trim() || lines.some((line) => !line.inventory_item_id || !line.location_id || !line.quantity_base || (line.direction === 'decrease' && !line.handling_unit_id))}>{saving ? 'Guardando…' : 'Guardar borrador'}</Button></div>
    </form>
  {/if}
</main>
