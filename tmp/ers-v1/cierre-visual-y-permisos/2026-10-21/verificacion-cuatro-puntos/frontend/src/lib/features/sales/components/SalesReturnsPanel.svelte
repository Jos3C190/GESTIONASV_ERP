<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import { scaledQuantity } from '$lib/features/inventory/transfer-operations';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Sale, SalesReturn, SalesReturnCondition, SalesReturnableAllocation } from '$lib/types/sales';

  let { sale, onChanged }: { sale: Sale; onChanged: () => void } = $props();
  let allocations = $state<SalesReturnableAllocation[]>([]);
  let returns = $state<SalesReturn[]>([]);
  let quantities = $state<Record<string, string>>({});
  let reasons = $state<Record<string, string>>({});
  let conditions = $state<Record<string, SalesReturnCondition>>({});
  let decisions = $state<Record<string, 'accepted' | 'rejected'>>({});
  let decisionQuantities = $state<Record<string, string>>({});
  let decisionReasons = $state<Record<string, string>>({});
  let decisionConditions = $state<Record<string, SalesReturnCondition>>({});
  let notes = $state('');
  type EvidenceDocument = Awaited<ReturnType<typeof api.documents.list>>['items'][number];
  let selectedEvidenceDocuments = $state<EvidenceDocument[]>([]);
  const selectedEvidenceIds = $derived(selectedEvidenceDocuments.map((document) => document.id));
  let evidenceDocuments = $state<Awaited<ReturnType<typeof api.documents.list>>['items']>([]);
  let evidenceSearch = $state('');
  let evidencePickerOpen = $state(false);
  let loadingEvidence = $state(false);
  let evidenceError = $state<string | null>(null);
  let evidencePage = $state(1);
  let evidencePages = $state(1);
  let evidenceSearchGeneration = 0;
  let cancelReasons = $state<Record<string, string>>({});
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let generation = 0;
  onDestroy(() => { generation++; evidenceSearchGeneration++; });
  const idempotencyAttempts = new Map<string, { fingerprint: string; key: string }>();

  const canRead = $derived(permissions.hasPermission('sales_returns:read'));
  const canManage = $derived(permissions.hasPermission('sales_returns:manage'));
  const canReadEvidence = $derived(permissions.hasPermission('documents:read'));
  const canReceive = $derived(permissions.hasPermission('sales_returns:receive'));
  const canResolve = $derived(permissions.hasPermission('sales_returns:resolve'));
  const canCancel = $derived(permissions.hasPermission('sales_returns:cancel'));
  const eligible = $derived(sale.status === 'confirmed' && sale.delivery_progress !== 'pending');

  const statusNames: Record<SalesReturn['status'], string> = {
    draft: 'Borrador',
    received: 'Recibida · pendiente de revisión',
    under_review: 'En revisión parcial',
    accepted: 'Aceptada',
    rejected: 'Rechazada',
    mixed: 'Mixta',
    cancelled: 'Cancelada'
  };

  function conditionName(value: SalesReturnCondition): string {
    return ({ resalable: 'Apta para reventa', damaged: 'Dañada', wrong_item: 'Producto incorrecto', other: 'Otra condición' })[value];
  }

  function idempotencyKey(action: string, payload: unknown): string {
    const fingerprint = JSON.stringify(payload);
    const storageKey = `sales-return-command:${sale.id}:${action}`;
    let previous = idempotencyAttempts.get(action);
    if (!previous) {
      const stored = sessionStorage.getItem(storageKey);
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as { fingerprint?: unknown; key?: unknown };
          if (typeof parsed.fingerprint === 'string' && typeof parsed.key === 'string') {
            previous = { fingerprint: parsed.fingerprint, key: parsed.key };
          }
        } catch {
          sessionStorage.removeItem(storageKey);
        }
      }
    }
    if (previous?.fingerprint === fingerprint) return previous.key;
    const key = `${action}:${crypto.randomUUID()}`;
    idempotencyAttempts.set(action, { fingerprint, key });
    sessionStorage.setItem(storageKey, JSON.stringify({ fingerprint, key }));
    return key;
  }

  function clearIdempotencyKey(action: string) {
    idempotencyAttempts.delete(action);
    sessionStorage.removeItem(`sales-return-command:${sale.id}:${action}`);
  }

  function outcomeMayBeUncertain(cause: unknown): boolean {
    if (!(cause instanceof HttpError)) return true;
    return cause.status === 408 || cause.status === 429 || cause.status >= 500;
  }

  async function reconcileUncertainOutcome(message: string) {
    error = message;
    await load();
    error = error ? `${message} ${error}` : message;
  }

  async function searchEvidence() {
    const current = ++evidenceSearchGeneration;
    loadingEvidence = true;
    evidenceError = null;
    try {
      const result = await api.documents.list({
        module: 'general',
        status: 'active',
        search: evidenceSearch.trim() || undefined,
        page: evidencePage,
        size: 20
      });
      if (evidenceSearchGeneration !== current) return;
      evidenceDocuments = result.items.filter(
        (document) => document.module === 'general' && document.business_status === 'active' && document.is_current
      );
      evidencePages = Math.max(result.meta.pages, 1);
    } catch (cause) {
      if (evidenceSearchGeneration !== current) return;
      evidenceError = cause instanceof HttpError ? cause.message : 'No se pudieron buscar documentos vigentes.';
    } finally {
      if (evidenceSearchGeneration === current) loadingEvidence = false;
    }
  }

  async function toggleEvidencePicker() {
    evidencePickerOpen = !evidencePickerOpen;
    if (evidencePickerOpen && evidenceDocuments.length === 0) {
      evidencePage = 1;
      await searchEvidence();
    }
  }

  function toggleEvidence(document: EvidenceDocument, checked: boolean) {
    if (checked) {
      if (selectedEvidenceDocuments.length >= 20) {
        evidenceError = 'Puedes vincular hasta 20 documentos a una devolución.';
        return;
      }
      if (!selectedEvidenceIds.includes(document.id)) {
        selectedEvidenceDocuments = [...selectedEvidenceDocuments, document];
      }
    } else {
      selectedEvidenceDocuments = selectedEvidenceDocuments.filter((selected) => selected.id !== document.id);
      evidenceError = null;
    }
  }

  function removeEvidence(documentId: string) {
    selectedEvidenceDocuments = selectedEvidenceDocuments.filter((document) => document.id !== documentId);
    evidenceError = null;
  }

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const [available, documents] = await Promise.all([
        canManage && eligible ? salesApi.returnableAllocations(sale.id) : Promise.resolve([]),
        canRead && eligible ? salesApi.returnsForSale(sale.id) : Promise.resolve([])
      ]);
      if (generation !== current) return;
      allocations = available;
      returns = documents;
      quantities = Object.fromEntries(available.map((item) => [item.delivery_allocation_id, quantities[item.delivery_allocation_id] ?? '']));
      reasons = Object.fromEntries(available.map((item) => [item.delivery_allocation_id, reasons[item.delivery_allocation_id] ?? '']));
      conditions = Object.fromEntries(available.map((item) => [item.delivery_allocation_id, conditions[item.delivery_allocation_id] ?? 'resalable']));
      for (const document of documents) {
        for (const line of document.lines) {
          decisionQuantities[line.id] ??= line.quantity_pending_base;
          decisionReasons[line.id] ??= 'Revisión física de la devolución';
          decisionConditions[line.id] ??= line.declared_condition === 'resalable' ? 'resalable' : line.declared_condition;
          decisions[line.id] ??= line.declared_condition === 'resalable' ? 'accepted' : 'rejected';
        }
      }
    } catch (cause) {
      if (generation === current) error = cause instanceof HttpError ? cause.message : 'No se pudo cargar el flujo de devoluciones.';
    } finally {
      if (generation === current) loading = false;
    }
  }

  onMount(() => void load());

  async function createDraft(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    notice = null;
    const selected = allocations.filter((row) => Number(quantities[row.delivery_allocation_id] ?? 0) > 0);
    if (!selected.length) {
      error = 'Indica una cantidad mayor que cero en al menos una unidad entregada.';
      return;
    }
    if (selected.some((row) => !reasons[row.delivery_allocation_id]?.trim())) {
      error = 'Escribe el motivo para cada producto seleccionado.';
      return;
    }
    busy = true;
    error = null;
    try {
      const payload = {
        notes: notes.trim() || null,
        document_ids: selectedEvidenceIds,
        lines: selected.map((row) => ({
          delivery_allocation_id: row.delivery_allocation_id,
          quantity_base: String(quantities[row.delivery_allocation_id] ?? '0'),
          reason: (reasons[row.delivery_allocation_id] ?? '').trim(),
          declared_condition: conditions[row.delivery_allocation_id] ?? 'resalable'
        }))
      };
      const created = await salesApi.createReturn(sale.id, payload, idempotencyKey('create', payload));
      clearIdempotencyKey('create');
      for (const row of selected) {
        quantities[row.delivery_allocation_id] = '';
        reasons[row.delivery_allocation_id] = '';
        conditions[row.delivery_allocation_id] = 'resalable';
      }
      notes = '';
      selectedEvidenceDocuments = [];
      notice = `Se creó el borrador ${created.code}. La cantidad quedó reservada; el inventario no cambia hasta aceptar producto revisado.`;
      await load();
    } catch (cause) {
      const message = cause instanceof HttpError ? cause.message : 'No se pudo guardar el borrador.';
      if (outcomeMayBeUncertain(cause)) {
        await reconcileUncertainOutcome(`${message} Se consultó de nuevo el estado antes de reintentar.`);
      } else {
        error = message;
      }
    } finally {
      busy = false;
    }
  }

  async function receive(document: SalesReturn) {
    if (busy) return;
    busy = true;
    error = null;
    notice = null;
    try {
      await salesApi.receiveReturn(document.id, idempotencyKey(`receive:${document.id}`, document.id));
      clearIdempotencyKey(`receive:${document.id}`);
      notice = `Se registró la recepción física de ${document.code}. El inventario sigue sin cambios mientras se revisa.`;
      await load();
      onChanged();
    } catch (cause) {
      const message = cause instanceof HttpError ? cause.message : 'No se pudo registrar la recepción documental.';
      if (outcomeMayBeUncertain(cause)) {
        await reconcileUncertainOutcome(`${message} Se consultó de nuevo el estado antes de reintentar.`);
      } else {
        error = message;
      }
    } finally {
      busy = false;
    }
  }

  async function resolve(document: SalesReturn, lineId: string) {
    if (busy) return;
    const line = document.lines.find((item) => item.id === lineId);
    if (!line) return;
    const quantity = decisionQuantities[lineId] ?? '';
    const parsedQuantity = scaledQuantity(quantity);
    const pendingQuantity = scaledQuantity(line.quantity_pending_base);
    if (parsedQuantity == null || pendingQuantity == null || parsedQuantity <= 0n || parsedQuantity > pendingQuantity) {
      error = 'La cantidad a resolver debe ser positiva, no superar el pendiente y tener hasta seis decimales.';
      return;
    }
    const decision = decisions[lineId] ?? 'rejected';
    const condition = decisionConditions[lineId] ?? 'other';
    const reason = decisionReasons[lineId]?.trim() ?? '';
    if (reason.length < 3) {
      error = 'Escribe el resultado de la revisión con al menos tres caracteres.';
      return;
    }
    busy = true;
    error = null;
    notice = null;
    try {
      const payload = { lines: [{
        return_line_id: lineId,
        decision,
        quantity_base: String(quantity),
        condition,
        reason
      }] };
      const actionKey = `resolve:${document.id}:${lineId}`;
      await salesApi.resolveReturn(document.id, payload, idempotencyKey(actionKey, payload));
      clearIdempotencyKey(actionKey);
      notice = decision === 'accepted'
        ? `La cantidad aceptada de ${line.product_name} quedó en cuarentena para continuar su revisión.`
        : `La cantidad de ${line.product_name} quedó rechazada y no volvió al inventario.`;
      await load();
      onChanged();
    } catch (cause) {
      const message = cause instanceof HttpError ? cause.message : 'No se pudo registrar la decisión.';
      if (outcomeMayBeUncertain(cause)) {
        await reconcileUncertainOutcome(`${message} Se consultó de nuevo el estado antes de reintentar.`);
      } else {
        error = message;
      }
    } finally {
      busy = false;
    }
  }

  async function cancel(document: SalesReturn) {
    if (busy) return;
    const reason = cancelReasons[document.id]?.trim();
    if (!reason) {
      error = 'Escribe por qué se cancela el borrador.';
      return;
    }
    busy = true;
    error = null;
    notice = null;
    try {
      const actionKey = `cancel:${document.id}`;
      await salesApi.cancelReturn(document.id, reason, idempotencyKey(actionKey, reason));
      clearIdempotencyKey(actionKey);
      notice = `Se canceló el borrador ${document.code}. No se modificó el inventario.`;
      await load();
    } catch (cause) {
      const message = cause instanceof HttpError ? cause.message : 'No se pudo cancelar el borrador.';
      if (outcomeMayBeUncertain(cause)) {
        await reconcileUncertainOutcome(`${message} Se consultó de nuevo el estado antes de reintentar.`);
      } else {
        error = message;
      }
    } finally {
      busy = false;
    }
  }
</script>

{#if eligible && (canRead || canManage)}
  <section class="space-y-4 rounded-xl border border-border bg-surface p-4 sm:p-5" aria-labelledby="sales-returns-heading" aria-busy={loading || busy}>
    <header class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 id="sales-returns-heading" class="text-lg font-semibold text-foreground">Devoluciones de esta venta</h2>
        <p class="mt-1 max-w-3xl text-sm text-foreground-muted">Se devuelven unidades de una entrega confirmada. Registrar la recepción no cambia el inventario; solo lo aceptado vuelve a entrar, en cuarentena y al costo de su salida original.</p>
      </div>
      <button class="w-fit rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50" onclick={() => { notice = null; void load(); }} disabled={loading || busy}>Actualizar</button>
    </header>

    {#if error}
      <div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground" role="alert">{error}</div>
    {/if}
    {#if notice}
      <div class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status" aria-live="polite" aria-atomic="true">{notice}</div>
    {/if}

    {#if loading}
      <div class="space-y-3 rounded-lg border border-border bg-surface-muted p-4" role="status" aria-live="polite" aria-label="Cargando devoluciones">
        <div class="skeleton h-5 w-48 rounded"></div><div class="skeleton h-16 rounded"></div>
      </div>
    {:else}
      {#if canManage}
        <form class="space-y-4 rounded-lg border border-border bg-surface-muted/40 p-4" onsubmit={createDraft}>
          <div>
            <h3 class="font-medium text-foreground">Registrar productos devueltos</h3>
            <p class="mt-1 text-xs text-foreground-muted">Selecciona la caja o unidad que se entregó, indica cuánto devuelve el cliente y explica el motivo. La cantidad se reserva mientras se revisa y se expresa en la unidad de inventario del producto (por ejemplo, cajas, kg o litros).</p>
          </div>
          {#if allocations.some((row) => Number(row.quantity_returnable_base) > 0)}
            <div class="space-y-3">
              {#each allocations.filter((row) => Number(row.quantity_returnable_base) > 0) as row (row.delivery_allocation_id)}
                <div class="grid gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-[minmax(0,1.7fr)_minmax(7rem,.6fr)_minmax(10rem,1fr)_minmax(10rem,1fr)] sm:items-end">
                  <div class="min-w-0">
                    <p class="font-medium text-foreground">{row.product_name}</p>
                    <p class="font-mono text-xs text-foreground-muted">{row.product_sku} · {row.handling_unit_code ?? 'Unidad original'} · entrega {row.delivery_code}</p>
                    <p class="mt-1 text-xs text-foreground-muted">Entregado {row.quantity_delivered_base} {formatUnitLabel(row.base_unit_name)} · aceptado {row.quantity_returned_base} · reservado {row.quantity_reserved_base} · quedan {row.quantity_returnable_base} {formatUnitLabel(row.base_unit_name)}</p>
                    {#if row.lot_code}<p class="text-xs text-foreground-muted">Lote {row.lot_code}</p>{/if}
                  </div>
                  <label class="text-xs text-foreground-muted">Cantidad devuelta ({formatUnitLabel(row.base_unit_name)})
                    <input aria-label={`Cantidad devuelta de ${row.product_name}`} class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" type="number" min="0" max={row.quantity_returnable_base} step="0.000001" bind:value={quantities[row.delivery_allocation_id]} />
                  </label>
                  <label class="text-xs text-foreground-muted">Condición declarada
                    <select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={conditions[row.delivery_allocation_id]}>
                      <option value="resalable">Aparentemente apta</option><option value="damaged">Dañada</option><option value="wrong_item">Producto incorrecto</option><option value="other">Otra condición</option>
                    </select>
                  </label>
                  <label class="text-xs text-foreground-muted">Motivo
                    <input aria-label={`Motivo de devolución de ${row.product_name}`} class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={reasons[row.delivery_allocation_id]} maxlength="500" placeholder="Describe el motivo" />
                  </label>
                </div>
              {/each}
            </div>
          {:else}
            <div class="rounded-lg border border-border bg-surface p-4 text-sm text-foreground-muted">No hay cantidades pendientes de devolución para las entregas de esta venta.</div>
          {/if}
          {#if allocations.length > 0}
            <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label class="min-w-0 flex-1 text-xs text-foreground-muted">Notas del documento
                <input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={notes} maxlength="4000" placeholder="Opcional" />
              </label>
              {#if canReadEvidence}
                <div class="min-w-0 flex-1 space-y-2 text-xs text-foreground-muted">
                  <p class="font-medium text-foreground">Evidencia documental (opcional)</p>
                  <button type="button" class="rounded-md border border-border px-3 py-2 text-sm text-foreground" onclick={() => void toggleEvidencePicker()} aria-expanded={evidencePickerOpen} aria-controls="sales-return-evidence-picker">
                    {evidencePickerOpen ? 'Ocultar documentos' : `Buscar documentos${selectedEvidenceIds.length ? ` · ${selectedEvidenceIds.length} seleccionados` : ''}`}
                  </button>
                  {#if selectedEvidenceIds.length > 0}
                    <div class="space-y-1" role="status" aria-live="polite" aria-label="Evidencia seleccionada">
                      <p>{selectedEvidenceIds.length} documento(s) se vincularán a esta devolución:</p>
                      <ul class="space-y-1">
                        {#each selectedEvidenceDocuments as document (document.id)}
                          <li class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface px-2 py-1.5">
                            <span class="min-w-0 break-words text-foreground">{document.title} · {document.original_filename}</span>
                            <button type="button" class="rounded px-2 py-1 text-primary hover:bg-surface-hover" aria-label={`Quitar evidencia ${document.title}`} onclick={() => removeEvidence(document.id)}>Quitar</button>
                          </li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                  {#if evidencePickerOpen}
                    <div id="sales-return-evidence-picker" class="space-y-2 rounded-lg border border-border bg-surface p-3" aria-busy={loadingEvidence}>
                      <div class="flex flex-col gap-2 sm:flex-row">
                        <label class="sr-only" for="sales-return-evidence-search">Buscar evidencia por nombre o referencia</label>
                        <input id="sales-return-evidence-search" class="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={evidenceSearch} placeholder="Nombre, referencia o archivo" onkeydown={(event) => { if (event.key === 'Enter') { event.preventDefault(); evidencePage = 1; void searchEvidence(); } }} />
                        <button type="button" class="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50" onclick={() => { evidencePage = 1; void searchEvidence(); }} disabled={loadingEvidence}>Buscar</button>
                      </div>
                      {#if evidenceError}<p role="alert" class="text-danger">{evidenceError}</p>{/if}
                      {#if loadingEvidence}<p role="status" aria-live="polite">Buscando documentos…</p>
                      {:else if evidenceDocuments.length === 0}<p>No hay documentos generales vigentes para esta búsqueda. Primero <a class="text-primary underline" href="/documents/general" target="_blank" rel="noreferrer">carga la evidencia en Documentos · General</a>.</p>
                      {:else}
                        <ul class="max-h-52 space-y-2 overflow-y-auto" aria-label="Documentos generales disponibles">
                          {#each evidenceDocuments as document (document.id)}
                            <li>
                              <label class="flex cursor-pointer items-start gap-2 rounded-md border border-border p-2 hover:bg-surface-hover">
                                <input type="checkbox" class="mt-0.5" aria-label={`Adjuntar evidencia ${document.title}`} checked={selectedEvidenceIds.includes(document.id)} onchange={(event) => toggleEvidence(document, event.currentTarget.checked)} />
                                <span class="min-w-0"><span class="block font-medium text-foreground">{document.title}</span><span class="block break-words">{document.original_filename}{document.reference_code ? ` · ${document.reference_code}` : ''}</span></span>
                              </label>
                            </li>
                          {/each}
                        </ul>
                        {#if evidencePages > 1}
                          <div class="flex items-center justify-between">
                            <button type="button" class="rounded-md border border-border px-3 py-1.5 disabled:opacity-50" onclick={() => { evidencePage = Math.max(1, evidencePage - 1); void searchEvidence(); }} disabled={loadingEvidence || evidencePage <= 1}>Anterior</button>
                            <span>Página {evidencePage} de {evidencePages}</span>
                            <button type="button" class="rounded-md border border-border px-3 py-1.5 disabled:opacity-50" onclick={() => { evidencePage = Math.min(evidencePages, evidencePage + 1); void searchEvidence(); }} disabled={loadingEvidence || evidencePage >= evidencePages}>Siguiente</button>
                          </div>
                        {/if}
                      {/if}
                    </div>
                  {/if}
                </div>
              {/if}
              <button class="rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={busy || !allocations.some((row) => Number(row.quantity_returnable_base) > 0)}>{busy ? 'Guardando…' : 'Crear borrador'}</button>
            </div>
          {/if}
        </form>
      {/if}

      {#if canRead}
        {#if returns.length === 0}
          <div class="rounded-lg border border-border bg-surface-muted/30 p-5 text-sm text-foreground-muted">Todavía no hay devoluciones de esta venta.</div>
        {:else}
          <div class="space-y-3">
            {#each returns as document (document.id)}
              <article class="overflow-hidden rounded-lg border border-border">
                <header class="flex flex-col gap-2 border-b border-border bg-surface-muted/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div><p class="font-mono text-sm font-semibold text-foreground">{document.code}</p><p class="text-xs text-foreground-muted">Creada {new Date(document.created_at).toLocaleString('es-SV')}</p></div>
                  <span class="w-fit rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-foreground">{statusNames[document.status]}</span>
                </header>
                <div class="divide-y divide-border">
                  {#if document.evidence.length > 0}
                    <div class="space-y-2 border-b border-border bg-surface-muted/20 px-4 py-3">
                      <p class="text-xs font-semibold text-foreground">Evidencia vinculada</p>
                      {#each document.evidence as file (file.document_id)}
                        <p class="text-xs text-foreground-muted">{file.title} · {file.file_name} · ID <span class="font-mono">{file.document_id}</span></p>
                      {/each}
                    </div>
                  {/if}
                  {#each document.lines as line (line.id)}
                    <div class="space-y-3 p-4">
                      <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div><p class="font-medium text-foreground">{line.product_name} <span class="font-mono text-xs text-foreground-muted">({line.product_sku})</span></p><p class="text-xs text-foreground-muted">Entrega {line.delivery_code} · recibido {line.quantity_received_base} {formatUnitLabel(line.base_unit_name)} · devuelto aceptado {line.quantity_accepted_base} · rechazado {line.quantity_rejected_base} · pendiente {line.quantity_pending_base} {formatUnitLabel(line.base_unit_name)}</p><p class="mt-1 text-xs text-foreground-muted">Motivo: {line.reason} · condición declarada: {conditionName(line.declared_condition)}</p></div>
                      </div>
                      {#if document.status === 'draft' && canCancel}
                        <div class="flex flex-col gap-2 sm:flex-row">
                          <input aria-label={`Motivo de cancelación de ${document.code}`} class="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={cancelReasons[document.id]} placeholder="Motivo para cancelar el borrador" maxlength="500" />
                          <button class="rounded-md border border-danger/30 px-3 py-2 text-sm text-danger disabled:opacity-50" onclick={() => void cancel(document)} disabled={busy}>Cancelar borrador</button>
                        </div>
                      {/if}
                      {#if document.status === 'draft' && canReceive}
                        <button class="rounded-md border border-primary/30 px-3 py-2 text-sm font-medium text-primary disabled:opacity-50" onclick={() => void receive(document)} disabled={busy}>Registrar recepción física</button>
                      {/if}
                      {#if ['received','under_review'].includes(document.status) && canResolve && Number(line.quantity_pending_base) > 0}
                        <div class="grid gap-3 rounded-lg border border-warning/30 bg-warning/5 p-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
                          <label class="text-xs text-foreground-muted">Cantidad a resolver
                            <input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" type="number" min="0.000001" max={line.quantity_pending_base} step="0.000001" bind:value={decisionQuantities[line.id]} />
                          </label>
                          <label class="text-xs text-foreground-muted">Resultado
                            <select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" value={decisions[line.id]} onchange={(event) => { decisions[line.id] = event.currentTarget.value as 'accepted' | 'rejected'; }}><option value="accepted">Aceptar apta para reventa</option><option value="rejected">Rechazar · no vuelve al stock</option></select>
                          </label>
                          <label class="text-xs text-foreground-muted">Condición revisada
                            <select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={decisionConditions[line.id]}><option value="resalable">Apta para reventa</option><option value="damaged">Dañada</option><option value="wrong_item">Producto incorrecto</option><option value="other">Otra condición</option></select>
                          </label>
                          <label class="text-xs text-foreground-muted lg:col-span-2">Motivo de la revisión
                            <input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={decisionReasons[line.id]} maxlength="500" />
                          </label>
                          <div class="sm:col-span-2 lg:col-span-5">
                            <button class="rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50" onclick={() => void resolve(document, line.id)} disabled={busy}>Registrar decisión de esta cantidad</button>
                            <p class="mt-2 text-xs text-foreground-muted">La aceptación crea una unidad en cuarentena, vinculada a la entrega original. Después continúa la revisión normal de medidas y etiqueta; el rechazo no crea inventario.</p>
                          </div>
                        </div>
                      {/if}
                      {#if line.events.length > 0}
                        <ul class="space-y-2 text-xs text-foreground-muted" aria-label="Historial de revisión">
                          {#each line.events as event (event.id)}
                            <li class="rounded-md bg-surface-muted/50 px-3 py-2"><span class="font-medium text-foreground">{event.decision === 'accepted' ? 'Aceptada · ingresó en cuarentena' : 'Rechazada'}</span> · {event.quantity_base} · {conditionName(event.condition)} · {event.reason}{#if event.movement_id} · movimiento <span class="font-mono">{event.movement_id}</span>{/if}</li>
                          {/each}
                        </ul>
                      {/if}
                    </div>
                  {/each}
                </div>
              </article>
            {/each}
          </div>
        {/if}
      {/if}
    {/if}
  </section>
{/if}
