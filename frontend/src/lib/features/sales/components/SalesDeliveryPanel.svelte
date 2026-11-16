<script lang="ts">
  import { onDestroy } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import type { Sale, SalesDelivery, SalesDeliveryStockLine } from '$lib/types/sales';

  let { sale, onChanged }: { sale: Sale; onChanged: () => Promise<void> } = $props();
  let deliveries = $state<SalesDelivery[]>([]);
  let stockOptions = $state<SalesDeliveryStockLine[]>([]);
  let selectedByLine = $state<Record<string, string[]>>({});
  let deliveryNotes = $state('');
  let cancelReason = $state('');
  let editingDeliveryId = $state<string | null>(null);
  let preparing = $state(false);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let stockError = $state<string | null>(null);
  let generation = 0;
  let pendingConfirmation: (() => Promise<void>) | null = null;
  onDestroy(() => {
    generation++;
    if (pendingConfirmation && confirmation.current?.execute === pendingConfirmation) confirmation.cancel();
  });
  let previousBranchId = branch.id;
  let previousSaleState = '';
  const canRead = $derived(permissions.hasPermission('sales_deliveries:read'));
  const canPrepare = $derived(permissions.hasPermission('sales_deliveries:manage'));
  const canConfirm = $derived(permissions.hasPermission('sales_deliveries:confirm'));
  const canCancel = $derived(permissions.hasPermission('sales_deliveries:cancel'));
  const createStorageKey = $derived(`sales-delivery-create:${sale.id}:${branch.id ?? 'all'}`);

  interface PendingCreate {
    key: string;
    assignments: Array<{ sale_line_id: string; handling_unit_id: string }>;
    notes: string | null;
  }

  let pendingCreate = $state<PendingCreate | null>(null);

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    stockError = null;
    try {
      const [deliveriesResult, stockResult] = await Promise.allSettled([
        canRead ? salesApi.deliveriesForSale(sale.id) : Promise.resolve([]),
        canPrepare && sale.status === 'confirmed' ? salesApi.deliveryStock(sale.id) : Promise.resolve([])
      ]);
      if (generation !== current) return;
      if (deliveriesResult.status === 'fulfilled') {
        deliveries = deliveriesResult.value;
      } else {
        deliveries = [];
        error = deliveriesResult.reason instanceof HttpError
          ? deliveriesResult.reason.message
          : 'No se pudieron cargar las entregas.';
      }
      if (stockResult.status === 'fulfilled') {
        stockOptions = stockResult.value;
      } else {
        stockOptions = [];
        stockError = stockResult.reason instanceof HttpError
          ? stockResult.reason.message
          : 'No se pudo consultar la disponibilidad.';
      }
      const stored = sessionStorage.getItem(createStorageKey);
      pendingCreate = stored ? (JSON.parse(stored) as PendingCreate) : null;
      if (pendingCreate) {
        selectedByLine = pendingCreate.assignments.reduce<Record<string, string[]>>((result, item) => {
          result[item.sale_line_id] ??= [];
          (result[item.sale_line_id] ??= []).push(item.handling_unit_id);
          return result;
        }, {});
        deliveryNotes = pendingCreate.notes ?? '';
      }
      if (editingDeliveryId) {
        const currentDraft = deliveries.find((item) => item.id === editingDeliveryId && item.status === 'draft');
        if (currentDraft) applyDraft(currentDraft);
        else editingDeliveryId = null;
      }
    } catch (cause) {
      if (generation === current) {
        error = cause instanceof HttpError ? cause.message : 'No se pudo recuperar el estado de la entrega.';
      }
    } finally {
      if (generation === current) loading = false;
    }
  }

  $effect(() => {
    const contextId = branch.id;
    const saleState = `${sale.id}:${sale.status}`;
    if (contextId !== previousBranchId || saleState !== previousSaleState) {
      previousBranchId = contextId;
      previousSaleState = saleState;
      selectedByLine = {};
      editingDeliveryId = null;
      pendingCreate = null;
      deliveryNotes = '';
      void load();
    }
  });

  function assignmentsFromSelection() {
    return Object.entries(selectedByLine).flatMap(([sale_line_id, ids]) =>
      ids.map((handling_unit_id) => ({ sale_line_id, handling_unit_id }))
    );
  }

  function selectionFingerprint(assignments: Array<{ sale_line_id: string; handling_unit_id: string }>) {
    return JSON.stringify(assignments.map((item) => `${item.sale_line_id}:${item.handling_unit_id}`).sort());
  }

  function hasUnsavedChanges(delivery: SalesDelivery) {
    if (editingDeliveryId !== delivery.id) return false;
    const savedAssignments = delivery.lines.flatMap((line) => line.allocations.map((allocation) => ({
      sale_line_id: line.sale_line_id, handling_unit_id: allocation.handling_unit_id
    })));
    return deliveryNotes !== (delivery.notes ?? '')
      || selectionFingerprint(assignmentsFromSelection()) !== selectionFingerprint(savedAssignments);
  }

  function selectedQuantity(line: SalesDeliveryStockLine) {
    const ids = new Set(selectedByLine[line.sale_line_id] ?? []);
    return line.units
      .filter((unit) => ids.has(unit.handling_unit_id))
      .reduce((total, unit) => total + Number(unit.quantity_base), 0);
  }

  function toggleUnit(lineId: string, unitId: string, checked: boolean) {
    if (pendingCreate || busy) return;
    const current = selectedByLine[lineId] ?? [];
    selectedByLine = {
      ...selectedByLine,
      [lineId]: checked ? [...new Set([...current, unitId])] : current.filter((id) => id !== unitId)
    };
  }

  function applyDraft(delivery: SalesDelivery) {
    editingDeliveryId = delivery.id;
    deliveryNotes = delivery.notes ?? '';
    selectedByLine = delivery.lines.reduce<Record<string, string[]>>((result, line) => {
      result[line.sale_line_id] = line.allocations.map((allocation) => allocation.handling_unit_id);
      return result;
    }, {});
    error = null;
  }

  function stopEditing() {
    editingDeliveryId = null;
    preparing = false;
    selectedByLine = {};
    deliveryNotes = '';
    error = null;
  }

  async function saveDraft() {
    if (!sale || busy) return;
    const assignments = assignmentsFromSelection();
    if (!assignments.length) {
      error = 'Selecciona al menos una unidad logística completa.';
      return;
    }
    busy = true;
    error = null;
    try {
      if (editingDeliveryId) {
        const draft = deliveries.find((item) => item.id === editingDeliveryId);
        if (!draft) throw new Error('El borrador ya no está disponible. Recarga la venta.');
        await salesApi.updateDelivery(editingDeliveryId, {
          expected_version: draft.version,
          notes: deliveryNotes || null,
          assignments
        });
      } else {
        if (!pendingCreate) {
          pendingCreate = {
            key: crypto.randomUUID(),
            assignments,
            notes: deliveryNotes || null
          };
          sessionStorage.setItem(createStorageKey, JSON.stringify(pendingCreate));
        }
        const created = await salesApi.createDelivery(sale.id, {
          notes: pendingCreate.notes,
          assignments: pendingCreate.assignments
        }, pendingCreate.key);
        sessionStorage.removeItem(createStorageKey);
        pendingCreate = null;
        editingDeliveryId = created.id;
      }
      await load();
    } catch (cause) {
      if (pendingCreate && cause instanceof HttpError && [400, 403, 404, 409, 422].includes(cause.status)) {
        sessionStorage.removeItem(createStorageKey);
        pendingCreate = null;
      }
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar el borrador. Recarga para revisar su estado.';
    } finally {
      busy = false;
    }
  }

  function confirmationCommand(delivery: SalesDelivery) {
    const key = `sales-delivery-confirm:${sale.id}:${delivery.id}:${branch.id ?? 'all'}`;
    const stored = sessionStorage.getItem(key);
    if (stored) {
      const previous = JSON.parse(stored) as { idempotencyKey: string; version: number };
      if (previous.version === delivery.version) return { storageKey: key, ...previous };
    }
    const command = { storageKey: key, idempotencyKey: crypto.randomUUID(), version: delivery.version };
    sessionStorage.setItem(key, JSON.stringify(command));
    return command;
  }

  async function confirmDelivery(delivery: SalesDelivery) {
    if (busy) return;
    if (hasUnsavedChanges(delivery)) {
      error = 'Guarda los cambios de la entrega antes de confirmar su salida.';
      return;
    }
    if (confirmation.open) return;
    pendingConfirmation = async () => {
      const current = deliveries.find((item) => item.id === delivery.id);
      if (!current || current.version !== delivery.version || current.status !== 'draft' || hasUnsavedChanges(current)) {
        throw new Error('El borrador cambió. Guarda y revisa la entrega antes de confirmar.');
      }
      busy = true;
      error = null;
      try {
        const command = confirmationCommand(delivery);
        await salesApi.confirmDelivery(delivery.id, command.version, command.idempotencyKey);
        sessionStorage.removeItem(command.storageKey);
        editingDeliveryId = null;
        selectedByLine = {};
        await Promise.all([load(), onChanged()]);
      } catch (cause) {
        throw new Error(cause instanceof HttpError ? cause.message : 'No se confirmó la entrega. Recarga para recuperar el mismo resultado antes de volver a intentar.');
      } finally {
        busy = false;
      }
    };
    confirmation.request({ kind: 'confirm', title: `Confirmar ${delivery.code}`, resourceName: delivery.code,
      description: `Se descontarán las unidades completas seleccionadas de la sucursal ${branch.branches.find((item) => item.id === sale.branch_id)?.name ?? 'del documento'}. La salida quedará registrada en el Kardex.`,
      confirmLabel: 'Confirmar entrega ahora', execute: pendingConfirmation });
  }

  async function cancelDelivery(delivery: SalesDelivery) {
    if (!cancelReason.trim()) {
      error = 'Escribe el motivo para cancelar el borrador.';
      return;
    }
    busy = true;
    error = null;
    try {
      await salesApi.cancelDelivery(delivery.id, delivery.version, cancelReason);
      cancelReason = '';
      if (editingDeliveryId === delivery.id) stopEditing();
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo cancelar el borrador.';
    } finally {
      busy = false;
    }
  }

  const statusNames: Record<SalesDelivery['status'], string> = {
    draft: 'Borrador',
    confirmed: 'Confirmada',
    cancelled: 'Cancelada'
  };
</script>

{#if sale.status !== 'confirmed'}
  <section class="rounded-xl border border-border bg-surface p-4">
    <h2 class="font-semibold text-foreground">Entregas</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      {sale.status === 'draft' ? 'Confirma la venta antes de preparar una entrega.' : 'Una venta cancelada no admite nuevas entregas.'}
    </p>
  </section>
{:else if canRead || canPrepare}
  <section class="space-y-4 rounded-xl border border-border bg-surface p-4 sm:p-5" aria-labelledby="delivery-title">
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 id="delivery-title" class="font-semibold text-foreground">Entregas de la venta</h2>
        <p class="mt-1 text-sm text-foreground-muted">Las unidades se descuentan al confirmar. Cada asignación mueve una caja o unidad logística completa.</p>
      </div>
      {#if canPrepare && sale.delivery_progress !== 'complete' && !editingDeliveryId && !pendingCreate}
        <button class="rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground disabled:opacity-50" disabled={loading || busy} onclick={() => { selectedByLine = {}; deliveryNotes = ''; error = null; preparing = true; }}>
          Preparar entrega
        </button>
      {/if}
    </header>

    {#if error}
      <div class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-foreground" role="alert">
        {error}
        <button class="ml-2 underline" onclick={() => void load()}>Recargar</button>
      </div>
    {/if}

    {#if loading}
      <p class="rounded-lg border border-border px-4 py-5 text-center text-sm text-foreground-muted">Consultando unidades disponibles y entregas registradas…</p>
    {:else}
      {#if canPrepare && (preparing || editingDeliveryId || pendingCreate || Object.values(selectedByLine).some((ids) => ids.length > 0))}
        <div class="space-y-4 rounded-lg border border-primary/30 bg-primary/5 p-4">
          <div>
            <h3 class="font-medium text-foreground">{editingDeliveryId ? 'Editar borrador' : pendingCreate ? 'Recuperar borrador de entrega' : `Nueva entrega · ${sale.code}`}</h3>
            <p class="mt-1 text-sm text-foreground-muted">Si necesitas entregar una parte de una caja, fracciona la unidad en almacén y completa allí la revisión de medidas y etiqueta antes de asignarla.</p>
          </div>
          {#if pendingCreate}
            <p class="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-foreground" role="status">Se conserva la misma selección y clave para recuperar el borrador sin duplicarlo.</p>
          {/if}
          {#if stockError}
            <div class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-foreground" role="alert">No se pudo consultar disponibilidad: {stockError}</div>
          {:else if stockOptions.length === 0}
            <p class="rounded-md border border-border px-3 py-3 text-sm text-foreground-muted">No hay cantidades pendientes para entregar.</p>
          {:else}
            <div class="space-y-3">
              {#each stockOptions as line (line.sale_line_id)}
                <section class="overflow-hidden rounded-lg border border-border bg-surface">
                  <div class="flex flex-col gap-1 border-b border-border px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <div><p class="font-medium text-foreground">{line.product_name}</p><p class="font-mono text-xs text-foreground-muted">{line.product_sku} · {formatUnitLabel(line.unit_name)}</p></div>
                    <div class="text-sm text-foreground-muted">Pendiente: <strong class="font-mono text-foreground">{line.quantity_pending_base} {formatUnitLabel(line.base_unit_name)}</strong> · Seleccionado: <strong class="font-mono text-foreground">{selectedQuantity(line)} {formatUnitLabel(line.base_unit_name)}</strong></div>
                  </div>
                  {#if line.units.length === 0}
                    <p class="px-3 py-4 text-sm text-foreground-muted">No hay unidades disponibles de este producto en la sucursal de la venta.</p>
                  {:else}
                    <ul class="divide-y divide-border">
                      {#each line.units as unit (unit.handling_unit_id)}
                        <li class="flex gap-3 px-3 py-3">
                          <input type="checkbox" class="mt-1 h-4 w-4 accent-primary" aria-label={`Seleccionar unidad ${unit.code}`} checked={(selectedByLine[line.sale_line_id] ?? []).includes(unit.handling_unit_id)} disabled={busy || !!pendingCreate} onchange={(event) => toggleUnit(line.sale_line_id, unit.handling_unit_id, event.currentTarget.checked)} />
                          <div class="min-w-0 flex-1">
                            <p class="font-mono text-sm font-semibold text-foreground">{unit.code}</p>
                            <p class="text-sm text-foreground">{unit.quantity_base} {formatUnitLabel(unit.base_unit_name)}</p>
                            <p class="text-xs text-foreground-muted">{unit.warehouse_name} · {unit.location_code}{unit.lot_code ? ` · Lote ${unit.lot_code}` : ''}{unit.expiry_date ? ` · Vence ${unit.expiry_date}` : ''}</p>
                          </div>
                          <span class="self-center rounded-full bg-success/10 px-2 py-1 text-xs text-success">Disponible</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </section>
              {/each}
            </div>
          {/if}
          {#if canPrepare}
            <label class="block text-sm text-foreground-muted">Notas de entrega<textarea bind:value={deliveryNotes} rows="2" maxlength="4000" disabled={busy || !!pendingCreate} class="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground disabled:opacity-60"></textarea></label>
            <div class="flex flex-wrap gap-2">
              <button class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy || loading || !assignmentsFromSelection().length} onclick={() => void saveDraft()}>{busy ? 'Guardando…' : pendingCreate ? 'Reintentar creación' : editingDeliveryId ? 'Guardar cambios' : 'Crear borrador'}</button>
              {#if editingDeliveryId || preparing}<button class="rounded-md border border-border px-4 py-2 text-sm text-foreground" disabled={busy} onclick={stopEditing}>Cerrar preparación</button>{/if}
            </div>
          {/if}
        </div>
      {/if}

      {#if deliveries.length === 0}
        <p class="rounded-lg border border-dashed border-border px-4 py-5 text-center text-sm text-foreground-muted">Todavía no se han preparado entregas para esta venta.</p>
      {:else}
        <div class="space-y-3">
          {#each deliveries as delivery (delivery.id)}
            <article class="rounded-lg border border-border p-4">
              <header class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div><p class="font-mono font-semibold text-foreground">{delivery.code}</p><p class="mt-1 text-xs text-foreground-muted">{new Date(delivery.created_at).toLocaleString()}</p></div>
                <span class={`w-fit rounded-full px-2.5 py-1 text-xs ${delivery.status === 'confirmed' ? 'bg-success/10 text-success' : delivery.status === 'draft' ? 'bg-warning/10 text-warning' : 'bg-surface-muted text-foreground-muted'}`}>{statusNames[delivery.status]}</span>
              </header>
              <ul class="mt-3 divide-y divide-border rounded-md border border-border">
                {#each delivery.lines as line (line.id)}
                  <li class="px-3 py-2">
                    <p class="font-medium text-foreground">{line.product_name} <span class="font-mono text-sm">· {line.quantity_base} {formatUnitLabel(line.base_unit_name)}</span></p>
                    <ul class="mt-1 space-y-1 text-xs text-foreground-muted">
                      {#each line.allocations as allocation (allocation.id)}
                        <li>{allocation.handling_unit_code ?? allocation.handling_unit_id} · {allocation.quantity_base} {formatUnitLabel(line.base_unit_name)}{allocation.lot_code ? ` · Lote ${allocation.lot_code}` : ''}{#if allocation.movement_id} · Movimiento <span class="font-mono">{allocation.movement_id}</span>{/if}</li>
                      {/each}
                    </ul>
                  </li>
                {/each}
              </ul>
              {#if delivery.notes}<p class="mt-2 text-sm text-foreground-muted">{delivery.notes}</p>{/if}
              {#if delivery.status === 'draft'}
                <div class="mt-3 flex flex-col gap-2 border-t border-border pt-3 sm:flex-row sm:items-center">
                  {#if canPrepare}<button class="rounded-md border border-border px-3 py-2 text-sm text-foreground" disabled={busy} onclick={() => applyDraft(delivery)}>Editar selección</button>{/if}
                  {#if canConfirm}<button class="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy || !delivery.lines.length || hasUnsavedChanges(delivery)} onclick={() => void confirmDelivery(delivery)}>{busy ? 'Confirmando…' : 'Confirmar entrega'}</button>{/if}
                  {#if canCancel}<form class="flex min-w-0 flex-1 gap-2" onsubmit={(event) => { event.preventDefault(); void cancelDelivery(delivery); }}><label class="sr-only" for={`cancel-delivery-${delivery.id}`}>Motivo de cancelación</label><input id={`cancel-delivery-${delivery.id}`} bind:value={cancelReason} maxlength="1000" placeholder="Motivo para cancelar borrador" class="h-9 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-sm text-foreground" /><button class="rounded-md border border-danger/30 px-3 py-2 text-sm text-danger disabled:opacity-50" disabled={busy || !cancelReason.trim()}>Cancelar</button></form>{/if}
                </div>
                {#if hasUnsavedChanges(delivery)}<p class="mt-2 text-sm text-foreground" role="status">Guarda los cambios de la entrega antes de confirmar su salida.</p>{/if}
              {:else if delivery.status === 'confirmed'}
                <p class="mt-3 border-t border-border pt-3 text-sm text-success">Entrega confirmada. El inventario y su valoración quedaron registrados en el Kardex.</p>
              {:else if delivery.cancellation_reason}
                <p class="mt-2 text-sm text-foreground-muted">Motivo de cancelación: {delivery.cancellation_reason}</p>
              {/if}
            </article>
          {/each}
        </div>
      {/if}
    {/if}
  </section>
{/if}
