<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { adjustmentInputClass, adjustmentNoticeClass } from '$lib/features/inventory/adjustment-styles';
  import { inventoryAdjustmentsApi, type AdjustmentLineInput, type InventoryAdjustment } from '$lib/features/inventory/adjustments';
  import { DOCUMENT_ACCEPT, DOCUMENT_MAX_BYTES, documentContentType, isSupportedDocumentFile } from '$lib/features/documents/document-upload';
  import { openResolvedDocumentInBrowser } from '$lib/features/documents/open-document';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let { data }: { data: { adjustmentId: string } } = $props();
  const canManage = $derived(permissions.hasPermission('inventory:adjust'));
  const canApprove = $derived(permissions.hasPermission('inventory:adjust_approve'));
  const canSeeCost = $derived(permissions.hasPermission('inventory:valuation'));
  const statusText: Record<string, string> = { draft: 'Borrador', approved: 'Aprobado', applied: 'Aplicado', cancelled: 'Cancelado' };
  let adjustment = $state<InventoryAdjustment | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let showEdit = $state(false);
  let editReason = $state('');
  let editReference = $state('');
  let editNotes = $state('');
  let editOperationalDate = $state('');
  let editAccountingDate = $state('');
  let editRevocationReason = $state('');
  let editQuantities = $state<Record<string, string>>({});
  let cancelReason = $state('');
  let showCancel = $state(false);
  let showCorrection = $state(false);
  let correctionReason = $state('');
  let correctionReference = $state('');
  let correctionDate = $state(new Intl.DateTimeFormat('en-CA', { timeZone: 'America/El_Salvador', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  let applyDialog = $state<HTMLDialogElement | null>(null);
  let applyReturnFocus: HTMLElement | null = null;
  let appliedScope = '';
  let loadedAdjustmentId = '';
  let sequence = 0;

  function errorText(cause: unknown) { return cause instanceof Error ? cause.message : 'No se pudo completar la acción.'; }
  function mayHaveCommitted(cause: unknown) {
    if (cause && typeof cause === 'object' && 'status' in cause) {
      const status = Number((cause as { status?: unknown }).status);
      return status === 0 || status === 408 || status === 429 || status >= 500;
    }
    return true;
  }
  function formatDate(value: string) { return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'America/El_Salvador' }).format(new Date(`${value.slice(0, 10)}T12:00:00-06:00`)); }
  function statusClass(value: string) {
    if (value === 'applied') return 'border-success/30 bg-success/10 text-success';
    if (value === 'approved') return 'border-primary/30 bg-primary/10 text-primary';
    if (value === 'cancelled') return 'border-danger/30 bg-danger/10 text-danger';
    return 'border-warning/30 bg-warning/10 text-warning';
  }

  async function load() {
    const current = ++sequence;
    const adjustmentId = data.adjustmentId;
    const scope = `${company.id ?? ''}:${branch.id ?? ''}`;
    appliedScope = scope;
    loadedAdjustmentId = adjustmentId;
    loading = true;
    error = null;
    try {
      const result = await inventoryAdjustmentsApi.get(adjustmentId);
      if (current !== sequence || scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      adjustment = result;
    } catch (cause) {
      if (current === sequence) error = errorText(cause);
    } finally {
      if (current === sequence) loading = false;
    }
  }

  function edit() {
    if (!adjustment) return;
    editReason = adjustment.reason;
    editReference = adjustment.document_reference;
    editNotes = adjustment.notes ?? '';
    editOperationalDate = adjustment.operational_date;
    editAccountingDate = adjustment.accounting_date;
    editRevocationReason = '';
    editQuantities = Object.fromEntries(adjustment.lines.map((line) => [line.id, line.quantity_base]));
    showEdit = true;
    notice = null;
    error = null;
  }

  function editableLines(): AdjustmentLineInput[] {
    if (!adjustment) return [];
    return adjustment.lines.map((line) => ({
      inventory_item_id: line.inventory_item_id,
      location_id: line.location_id,
      direction: line.direction,
      quantity_base: editQuantities[line.id] ?? line.quantity_base,
      stock_status: line.stock_status,
      inventory_lot_detail_id: line.inventory_lot_detail_id,
      handling_unit_id: line.handling_unit_id,
      packaging_definition_id: line.packaging_definition_id,
      documented_unit_cost: canSeeCost ? line.documented_unit_cost : null,
      documented_total_cost: canSeeCost ? line.documented_total_cost : null,
      actual_gross_weight_kg: line.actual_gross_weight_kg,
      actual_volume_m3: line.actual_volume_m3,
      transfer_detail_id: line.transfer_detail_id
    }));
  }

  async function saveEdit(event: SubmitEvent) {
    event.preventDefault();
    if (!adjustment || busy) return;
    busy = true;
    error = null;
    notice = null;
    const scope = appliedScope;
    try {
      const result = await inventoryAdjustmentsApi.update(adjustment.id, {
        warehouse_id: adjustment.warehouse_id,
        operational_date: editOperationalDate,
        accounting_date: editAccountingDate,
        reason: editReason.trim(),
        document_reference: editReference.trim(),
        notes: editNotes.trim() || null,
        lines: editableLines(),
        ...(adjustment.status === 'approved' ? { approval_revocation_reason: editRevocationReason.trim() } : {})
      });
      if (scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      adjustment = result;
      showEdit = false;
      notice = result.status === 'draft' ? 'Cambios guardados en borrador. La aprobación anterior fue revocada; vuelve a aprobar la versión actual.' : 'Borrador actualizado.';
    } catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  async function uploadFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file || !adjustment || adjustment.status !== 'draft' || busy) return;
    if (!isSupportedDocumentFile(file, DOCUMENT_MAX_BYTES)) {
      error = 'Selecciona un archivo permitido de hasta 50 MB.';
      return;
    }
    error = null;
    notice = null;
    busy = true;
    try {
      const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
      const checksum = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
      const ticket = await inventoryAdjustmentsApi.initiateDocument(adjustment.id, {
        file_name: file.name, content_type: documentContentType(file), size_bytes: file.size, checksum_sha256: checksum
      });
      const response = await fetch(ticket.upload_url, { method: ticket.method, headers: ticket.required_headers, body: file, credentials: 'omit' });
      if (!response.ok) throw new Error('El almacenamiento seguro rechazó la carga. Puedes reintentar el archivo.');
      adjustment = await inventoryAdjustmentsApi.completeDocument(adjustment.id, ticket.document_id);
      notice = 'Comprobante cargado y validado. Se conserva vinculado a este ajuste.';
    } catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  async function openDocument(documentId: string) {
    if (!adjustment || busy) return;
    error = null;
    try {
      await openResolvedDocumentInBrowser(async () => (await inventoryAdjustmentsApi.downloadDocument(adjustment!.id, documentId)).url);
    } catch (cause) { error = errorText(cause); }
  }

  async function detachDocument(documentId: string) {
    if (!adjustment || adjustment.status !== 'draft' || busy) return;
    busy = true;
    error = null;
    try { adjustment = await inventoryAdjustmentsApi.detachDocument(adjustment.id, documentId); notice = 'El documento se retiró del borrador y quedó en su historial.'; }
    catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  async function approve() {
    if (!adjustment || adjustment.status !== 'draft' || !canApprove || busy) return;
    busy = true; error = null; notice = null;
    try { adjustment = await inventoryAdjustmentsApi.approve(adjustment.id, adjustment.version); notice = 'Ajuste aprobado. Las existencias siguen sin cambios.'; }
    catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  async function cancel() {
    if (!adjustment || !cancelReason.trim() || busy) return;
    busy = true; error = null; notice = null;
    try { adjustment = await inventoryAdjustmentsApi.cancel(adjustment.id, cancelReason.trim()); showCancel = false; notice = 'Ajuste cancelado; no se movieron existencias.'; }
    catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  function openApplyDialog(event: MouseEvent) {
    if (!adjustment || adjustment.status !== 'approved' || !canApprove || busy) return;
    applyReturnFocus = event.currentTarget as HTMLElement;
    applyDialog?.showModal();
  }
  function closeApplyDialog() { applyDialog?.close(); applyReturnFocus?.focus(); }
  async function apply() {
    if (!adjustment || busy) return;
    busy = true; error = null; notice = null;
    const scope = appliedScope;
    try {
      const result = await inventoryAdjustmentsApi.apply(adjustment.id);
      if (scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
      adjustment = result;
      closeApplyDialog();
      notice = 'Ajuste aplicado. Consulta su movimiento en Kardex; las entradas nuevas permanecen en cuarentena y siguen la revisión normal de unidad y etiqueta.';
    } catch (cause) {
      const failure = errorText(cause);
      if (!mayHaveCommitted(cause)) {
        error = failure;
      } else {
        try {
          const current = await inventoryAdjustmentsApi.get(adjustment.id);
          if (scope !== `${company.id ?? ''}:${branch.id ?? ''}`) return;
          adjustment = current;
          if (current.status === 'applied') {
            closeApplyDialog();
            notice = 'La respuesta se interrumpió, pero la consulta confirmó que el ajuste ya se aplicó. No lo vuelvas a aplicar.';
          } else {
            error = `${failure} Se consultó el estado: ${statusText[current.status] ?? current.status}. La clave de reintento se conserva; si sigue aprobado, reintenta sin cambiar el ajuste.`;
          }
        } catch {
          error = `${failure} No se pudo confirmar el estado actual. Actualiza la página antes de decidir si reintentas.`;
        }
      }
    }
    finally { busy = false; }
  }

  async function createCorrection(event: SubmitEvent) {
    event.preventDefault();
    if (!adjustment || !correctionReason.trim() || !correctionReference.trim() || busy) return;
    busy = true; error = null; notice = null;
    try {
      const created = await inventoryAdjustmentsApi.correction(adjustment.id, {
        operational_date: correctionDate, accounting_date: correctionDate,
        reason: correctionReason.trim(), document_reference: correctionReference.trim()
      });
      await goto(`/inventory/adjustments/${created.id}`);
    } catch (cause) { error = errorText(cause); }
    finally { busy = false; }
  }

  $effect(() => {
    const scope = `${company.id ?? ''}:${branch.id ?? ''}`;
    if (appliedScope !== scope || loadedAdjustmentId !== data.adjustmentId) void load();
  });
</script>

<svelte:head><title>{adjustment ? `${adjustment.code} | Ajuste de inventario` : 'Detalle de ajuste'} | GestionaSV</title></svelte:head>

<main class="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6">
  <header class="space-y-2"><a class="text-sm font-medium text-primary hover:underline" href="/inventory/adjustments">← Ajustes de inventario</a>{#if adjustment}<div class="flex flex-wrap items-start justify-between gap-4"><div><p class="text-xs font-semibold uppercase tracking-wider text-primary">Ajuste de inventario</p><h1 class="mt-1 text-2xl font-semibold text-foreground">{adjustment.code}</h1><p class="mt-1 text-sm text-foreground-muted">{adjustment.warehouse_name} · Operativa {formatDate(adjustment.operational_date)} · Contable {formatDate(adjustment.accounting_date)}</p></div><span class={`rounded-full border px-3 py-1.5 text-sm font-medium ${statusClass(adjustment.status)}`}>{statusText[adjustment.status]}</span></div>{/if}</header>
  {#if loading}<div class="rounded-xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted" role="status">Cargando el documento y su historial…</div>
  {:else if error && !adjustment}<div class={`${adjustmentNoticeClass} border-danger/30 bg-danger/10`} role="alert">{error}</div>
  {:else if adjustment}
    {#if adjustment.transfer_id}<section class="rounded-xl border border-warning/30 bg-warning/5 p-4"><h2 class="font-semibold text-foreground">Ajuste de faltante de traslado</h2><p class="mt-1 text-sm text-foreground-muted">El vínculo apunta al traslado y su incidencia. Solo la cantidad no recibida puede registrarse como salida; nunca se suma a la recepción.</p><a class="mt-2 inline-block text-sm font-medium text-primary hover:underline" href="/transfers">Abrir traslados</a></section>{/if}
    <section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <article class="rounded-xl border border-border bg-surface p-4"><p class="text-xs font-semibold uppercase text-foreground-muted">Bodega</p><p class="mt-2 font-semibold text-foreground">{adjustment.warehouse_name}</p></article>
      <article class="rounded-xl border border-border bg-surface p-4"><p class="text-xs font-semibold uppercase text-foreground-muted">Motivo</p><p class="mt-2 font-medium text-foreground">{adjustment.reason}</p></article>
      <article class="rounded-xl border border-border bg-surface p-4"><p class="text-xs font-semibold uppercase text-foreground-muted">Referencia</p><p class="mt-2 font-mono text-sm text-foreground">{adjustment.document_reference}</p></article>
      <article class="rounded-xl border border-border bg-surface p-4"><p class="text-xs font-semibold uppercase text-foreground-muted">Aprobación</p><p class="mt-2 text-sm text-foreground">{adjustment.approved_at ? `Aprobado ${formatDate(adjustment.approved_at)}` : 'Pendiente'}</p><p class="mt-1 text-xs text-foreground-muted">Versión actual {adjustment.version}{adjustment.approved_version ? ` · aprobada ${adjustment.approved_version}` : ''}</p></article>
    </section>

    {#if showEdit}
      <form class="grid gap-4 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2" onsubmit={saveEdit}>
        <div class="sm:col-span-2"><h2 class="text-lg font-semibold text-foreground">Editar contenido del borrador</h2><p class="mt-1 text-sm text-foreground-muted">La operación física no cambia en este paso. Si el ajuste estaba aprobado, la aprobación se revoca y tendrás que aprobar otra vez.</p></div>
        <label class="space-y-1 text-sm font-medium text-foreground">Fecha operativa<input class={adjustmentInputClass} type="date" bind:value={editOperationalDate} required /></label>
        <label class="space-y-1 text-sm font-medium text-foreground">Fecha contable<input class={adjustmentInputClass} type="date" bind:value={editAccountingDate} required /></label>
        <label class="space-y-1 text-sm font-medium text-foreground">Motivo<textarea class={`${adjustmentInputClass} min-h-20`} minlength="5" bind:value={editReason} required></textarea></label>
        <label class="space-y-1 text-sm font-medium text-foreground">Referencia documental<input class={adjustmentInputClass} maxlength="240" bind:value={editReference} required /></label>
        <label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2">Notas<textarea class={`${adjustmentInputClass} min-h-16`} bind:value={editNotes}></textarea></label>
        {#each adjustment.lines as line (line.id)}<label class="space-y-1 text-sm font-medium text-foreground">Cantidad · {line.product_name}<input class={adjustmentInputClass} type="number" min="0.000001" step="0.000001" bind:value={editQuantities[line.id]} required /></label>{/each}
        {#if adjustment.status === 'approved'}<label class="space-y-1 text-sm font-medium text-foreground sm:col-span-2">Motivo para revocar la aprobación<input class={adjustmentInputClass} minlength="5" maxlength="1000" bind:value={editRevocationReason} required /></label>{/if}
        <div class="flex flex-wrap justify-end gap-2 sm:col-span-2"><Button variant="secondary" onclick={() => showEdit = false}>Volver</Button><Button type="submit" disabled={busy || !editReason.trim() || !editReference.trim() || adjustment.status === 'approved' && editRevocationReason.trim().length < 5}>{busy ? 'Guardando…' : adjustment.status === 'approved' ? 'Revocar y guardar borrador' : 'Guardar cambios'}</Button></div>
      </form>
    {/if}

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-labelledby="lines-heading"><div><h2 id="lines-heading" class="text-lg font-semibold text-foreground">Detalle del ajuste</h2><p class="text-sm text-foreground-muted">Las cantidades se expresan en unidad base. Las salidas usan el costo promedio vigente al aplicar.</p></div>
      {#each adjustment.lines as line (line.id)}
        <article class="rounded-xl border border-border p-4"><div class="flex flex-wrap items-start justify-between gap-3"><div><h3 class="font-semibold text-foreground">{line.product_name}</h3><p class="mt-1 font-mono text-xs text-foreground-muted">{line.sku ?? 'SKU sin registrar'} · {line.base_unit_name}{line.base_unit_symbol ? ` (${line.base_unit_symbol})` : ''}</p><p class="mt-1 text-sm text-foreground-muted">Ubicación {line.location_code ?? 'sin código'} · {line.handling_unit_code ? `Unidad ${line.handling_unit_code}` : line.inventory_lot_detail_id ? 'Lote existente' : 'Unidad nueva'}</p></div><span class={`rounded-full px-3 py-1 text-xs font-semibold ${line.direction === 'increase' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>{line.direction === 'increase' ? 'Entrada' : 'Salida'} · {line.direction === 'increase' ? '+' : '−'}{line.quantity_base} {line.base_unit_symbol ?? line.base_unit_name}</span></div>
          <div class="mt-3 grid gap-2 border-t border-border pt-3 text-sm sm:grid-cols-2 lg:grid-cols-4"><p><span class="text-foreground-muted">Condición: </span><span class="text-foreground">{line.stock_status === 'in_transit' ? 'En tránsito' : line.stock_status === 'quarantine' ? 'Cuarentena' : line.stock_status === 'damaged' ? 'Dañado' : 'Disponible'}</span></p><p><span class="text-foreground-muted">Lote: </span><span class="text-foreground">{line.inventory_lot_detail_id ?? 'Sin lote asociado'}</span></p>{#if canSeeCost && line.direction === 'increase'}<p><span class="text-foreground-muted">Costo unitario documentado: </span><span class="text-foreground">{line.documented_unit_cost ?? 'Sin costo documentado'}</span></p><p><span class="text-foreground-muted">Costo total documentado: </span><span class="text-foreground">{line.documented_total_cost ?? 'Sin costo documentado'}</span></p>{/if}</div>
          {#if line.movement_id && adjustment.status === 'applied'}<a class="mt-3 inline-flex text-sm font-medium text-primary hover:underline" href={`/inventory/kardex?warehouse_id=${encodeURIComponent(line.warehouse_id)}&inventory_item_id=${encodeURIComponent(line.inventory_item_id)}&product_name=${encodeURIComponent(line.product_name)}&period_from=${encodeURIComponent(adjustment.operational_date)}&period_to=${encodeURIComponent(adjustment.operational_date)}&source_reference=${encodeURIComponent(`adjustment:${adjustment.code}:${line.line_number}`)}`}>Ver movimiento exacto en Kardex →</a>{/if}
        </article>
      {/each}
    </section>

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-labelledby="documents-heading"><div class="flex flex-wrap items-start justify-between gap-3"><div><h2 id="documents-heading" class="text-lg font-semibold text-foreground">Comprobantes</h2><p class="text-sm text-foreground-muted">La aprobación requiere al menos un archivo cargado, activo y validado.</p></div>{#if adjustment.status === 'draft' && canManage}<div><input bind:this={fileInput} class="sr-only" type="file" accept={DOCUMENT_ACCEPT} onchange={uploadFile} /><Button variant="secondary" disabled={busy} onclick={() => fileInput?.click()}>Adjuntar archivo</Button></div>{/if}</div>
      {#if adjustment.documents.length === 0}<p class="rounded-lg bg-surface-muted p-4 text-sm text-foreground-muted">Todavía no hay comprobantes asociados. El ajuste no se puede aprobar hasta cargar uno.</p>{:else}<div class="space-y-2">{#each adjustment.documents as document (document.document_id)}<article class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3"><div><p class="font-medium text-foreground">{document.original_filename}</p><p class="mt-1 text-xs text-foreground-muted">{document.active ? 'Vinculado' : 'Retirado del borrador'} · {document.technical_status} · {document.upload_completed ? 'Carga completada' : 'Carga pendiente'}</p><p class="mt-1 break-all font-mono text-[11px] text-foreground-subtle">SHA-256 {document.checksum_sha256}</p></div><div class="flex gap-2">{#if document.active && document.upload_completed && document.technical_status === 'active'}<Button size="sm" variant="secondary" onclick={() => void openDocument(document.document_id)}>Abrir</Button>{/if}{#if adjustment.status === 'draft' && document.active && canManage}<Button size="sm" variant="ghost" disabled={busy} onclick={() => void detachDocument(document.document_id)}>Quitar</Button>{/if}</div></article>{/each}</div>{/if}
    </section>

    {#if showCancel && (adjustment.status === 'draft' || adjustment.status === 'approved')}
      <form class="space-y-3 rounded-xl border border-danger/30 bg-danger/5 p-4" onsubmit={(event) => { event.preventDefault(); void cancel(); }}><label class="block space-y-1 text-sm font-medium text-foreground">Motivo de cancelación<input class={adjustmentInputClass} minlength="5" maxlength="1000" bind:value={cancelReason} required /></label><div class="flex justify-end gap-2"><Button variant="secondary" onclick={() => showCancel = false}>Volver</Button><Button variant="danger" type="submit" disabled={busy || cancelReason.trim().length < 5}>Confirmar cancelación</Button></div></form>
    {/if}

    {#if showCorrection && adjustment.status === 'applied'}
      <form class="grid gap-3 rounded-xl border border-warning/30 bg-warning/5 p-4 sm:grid-cols-2" onsubmit={createCorrection}><div class="sm:col-span-2"><h2 class="font-semibold text-foreground">Crear corrección vinculada</h2><p class="mt-1 text-sm text-foreground-muted">El sistema solo admite la corrección de una salida ordinaria de una línea cuando no hay operaciones físicas o valorizadas posteriores. El movimiento original se conserva.</p></div><label class="space-y-1 text-sm font-medium text-foreground">Motivo<input class={adjustmentInputClass} minlength="5" bind:value={correctionReason} required /></label><label class="space-y-1 text-sm font-medium text-foreground">Referencia documental<input class={adjustmentInputClass} maxlength="240" bind:value={correctionReference} required /></label><label class="space-y-1 text-sm font-medium text-foreground">Fecha operativa y contable<input class={adjustmentInputClass} type="date" bind:value={correctionDate} required /></label><div class="flex items-end justify-end gap-2"><Button variant="secondary" onclick={() => showCorrection = false}>Cancelar</Button><Button type="submit" disabled={busy}>Crear borrador de corrección</Button></div></form>
    {/if}

    <section class="rounded-xl border border-border bg-surface p-4"><h2 class="text-lg font-semibold text-foreground">Historial</h2><ol class="mt-3 space-y-3">{#each adjustment.events as event, index (index)}<li class="flex gap-3"><span class="mt-1 size-2 shrink-0 rounded-full bg-primary"></span><div><p class="font-medium text-foreground">{event.action.replaceAll('_', ' ')}</p><p class="text-xs text-foreground-muted">{new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.occurred_at))} · Versión {event.version}{event.reason ? ` · ${event.reason}` : ''}</p></div></li>{/each}</ol></section>

    {#if error}<p class={`${adjustmentNoticeClass} border-danger/30 bg-danger/10`} role="alert">{error}</p>{/if}{#if notice}<p class={`${adjustmentNoticeClass} border-success/30 bg-success/10`} role="status">{notice}</p>{/if}

    <section class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4"><p class="max-w-2xl text-sm text-foreground-muted">{#if adjustment.status === 'draft'}Adjunta soporte y revisa el contenido antes de aprobar. No se ha movido inventario.{:else if adjustment.status === 'approved'}Aprobado. Aplicar es el único paso que registra movimientos y valores.{:else if adjustment.status === 'applied'}Aplicado y consultable en Kardex. Las nuevas entradas siguen en cuarentena.{:else}Cancelado. El historial permanece disponible.{/if}</p><div class="flex flex-wrap gap-2">
      {#if (adjustment.status === 'draft' || adjustment.status === 'approved') && canManage && !adjustment.transfer_id && !adjustment.correction_of_id}<Button variant="secondary" disabled={busy} onclick={edit}>{adjustment.status === 'approved' ? 'Revocar y editar' : 'Editar borrador'}</Button>{/if}
      {#if (adjustment.status === 'draft' || adjustment.status === 'approved') && canManage}<Button variant="danger" disabled={busy} onclick={() => showCancel = !showCancel}>Cancelar ajuste</Button>{/if}
      {#if adjustment.status === 'draft'}{#if canApprove}<Button disabled={busy || !adjustment.documents.some((document) => document.active && document.upload_completed && document.technical_status === 'active') || adjustment.lines.length === 0} onclick={() => void approve()}>{busy ? 'Procesando…' : 'Aprobar versión actual'}</Button>{:else}<Button variant="secondary" disabled>Requiere permiso de aprobación</Button>{/if}{/if}
      {#if adjustment.status === 'approved'}{#if canApprove}<Button disabled={busy} onclick={openApplyDialog}>Aplicar ajuste…</Button>{:else}<Button variant="secondary" disabled>Requiere permiso de aprobación y aplicación</Button>{/if}{/if}
      {#if adjustment.status === 'applied' && canManage && !adjustment.transfer_id}<Button variant="secondary" onclick={() => showCorrection = !showCorrection}>Corregir movimiento…</Button>{/if}
    </div></section>
  {/if}
</main>

<dialog bind:this={applyDialog} class="fixed inset-0 m-0 h-full max-h-full w-full max-w-none overflow-y-auto border-0 bg-transparent p-4 text-foreground backdrop:bg-black/60" aria-labelledby="apply-adjustment-heading" oncancel={(event) => { event.preventDefault(); closeApplyDialog(); }}>
  {#if adjustment}<div class="grid min-h-full place-items-center"><div class="w-full max-w-2xl space-y-4 rounded-2xl border border-border bg-surface p-5 shadow-2xl"><div><h2 id="apply-adjustment-heading" class="text-lg font-semibold text-foreground">Confirmar aplicación</h2><p class="mt-1 text-sm text-foreground-muted">Esta acción crea movimientos físicos y de valoración. No se puede cancelar después de aplicar.</p></div><div class="space-y-2 rounded-xl bg-surface-muted p-4">{#each adjustment.lines as line (line.id)}<p class="text-sm text-foreground"><strong>{line.product_name}</strong> · {line.location_code ?? 'ubicación'} · {line.direction === 'increase' ? 'Entrada +' : 'Salida −'}{line.quantity_base} {line.base_unit_symbol ?? line.base_unit_name}</p>{/each}</div><p class="text-sm text-foreground-muted">La cantidad negativa se valida contra la unidad existente y el saldo actual. Las entradas nuevas quedan en cuarentena para revisión de medidas y etiqueta.</p><div class="flex justify-end gap-2"><Button variant="secondary" onclick={closeApplyDialog}>Revisar</Button><Button variant="danger" disabled={busy} onclick={() => void apply()}>{busy ? 'Aplicando…' : 'Aplicar ajuste ahora'}</Button></div></div></div>{/if}
</dialog>
