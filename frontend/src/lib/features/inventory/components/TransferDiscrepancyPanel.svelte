<script lang="ts">
  import { tick } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import type { PackagingDefinition } from '$lib/features/inventory/types';
  import type {
    InventoryTransfer,
    TransferDiscrepancy
  } from '$lib/features/inventory/transfer-documents';
  import {
    businessToday,
    damageTypeLabel,
    discrepancyKindLabel,
    discrepancyResolutionLabel,
    discrepancyStatusLabel,
    discrepancySummary,
    displayLocationCode,
    formatQuantity,
    isDiscrepancyActive,
    quantityString,
    type DiscrepancyAdjustmentForm,
    type DiscrepancyRequest
  } from '$lib/features/inventory/transfer-operations';

  type Action = DiscrepancyRequest['action'];
  interface LocationChoice {
    id: string;
    code: string;
    location_type: string;
  }

  interface Props {
    transfer: InventoryTransfer;
    /** inventory:receive */
    canReceive: boolean;
    /** inventory:adjust */
    canAdjust: boolean;
    /** inventory:adjust_approve */
    canApproveAdjust: boolean;
    /** inventory:valuation: only they may document a cost for a surplus. */
    canSeeCost?: boolean;
    /** The person covers the branch the goods left from. */
    canAccessOrigin: boolean;
    /** The person covers the branch the goods arrived at. */
    canAccessDestination: boolean;
    busy?: boolean;
    /** Quarantine locations of the destination warehouse, to release damaged goods elsewhere. */
    locations?: LocationChoice[];
    formatDate: (value: string | null | undefined) => string;
    /** Runs the request; resolves to an error message, or null when it went through. */
    onRun: (request: DiscrepancyRequest) => Promise<string | null>;
  }

  let {
    transfer,
    canReceive,
    canAdjust,
    canApproveAdjust,
    canSeeCost = false,
    canAccessOrigin,
    canAccessDestination,
    busy = false,
    locations = [],
    formatDate,
    onRun
  }: Props = $props();

  const MIN_NOTES = 5;
  const MIN_CLAIM = 3;

  let active = $state<{ id: string; action: Action } | null>(null);
  let notes = $state('');
  let claimReference = $state('');
  let locationId = $state('');
  let form = $state<DiscrepancyAdjustmentForm>(emptyForm());
  let packagingChoices = $state<PackagingDefinition[]>([]);
  let packagingState = $state<'idle' | 'loading' | 'error'>('idle');
  let formError = $state<string | null>(null);
  // The field a validation problem belongs to ('' for a failure of the whole request).
  let errorField = $state('');
  let staleNotice = $state<string | null>(null);
  let submitting = $state(false);
  let returnFocusId = '';

  const rows = $derived(transfer.discrepancies);
  const underReview = $derived(transfer.status === 'discrepancy');
  const summary = $derived(discrepancySummary(rows));
  const originCountPending = $derived(
    canAccessOrigin &&
      canAdjust &&
      rows.some((item) => item.origin_count_required && item.origin_counted_at == null)
  );
  const originName = $derived(transfer.origin_branch_name ?? transfer.origin_warehouse_name);
  const lockedOut = $derived(busy || submitting);
  // Adjustments cannot be applied until the company's opening valuation is approved.
  const valuationReady = $derived(transfer.valuation_ready !== false);
  const valuationNoteNeeded = $derived(
    !valuationReady && rows.some((item) => availableActions(item).includes('adjust'))
  );

  function emptyForm(): DiscrepancyAdjustmentForm {
    const today = businessToday();
    return {
      operationalDate: today,
      accountingDate: today,
      reason: '',
      documentReference: '',
      notes: '',
      packaging: 'source',
      packagingId: '',
      weightKg: '',
      volumeM3: '',
      costMode: 'none',
      cost: ''
    };
  }

  function badgeVariant(
    item: TransferDiscrepancy
  ): 'success' | 'warning' | 'danger' | 'neutral' | 'primary' {
    if (item.status === 'resolved') return 'success';
    if (item.status === 'cancelled') return 'neutral';
    if (item.status === 'in_claim') return 'primary';
    return 'warning';
  }

  function kindVariant(kind: TransferDiscrepancy['kind']): 'warning' | 'danger' | 'primary' {
    return kind === 'damage' ? 'danger' : kind === 'surplus' ? 'primary' : 'warning';
  }

  function hasActiveAdjustment(item: TransferDiscrepancy): boolean {
    return item.adjustment != null && item.adjustment.status !== 'cancelled';
  }

  function openerId(item: TransferDiscrepancy, action: Action): string {
    return `disc-${item.id}-${action}`;
  }

  async function open(item: TransferDiscrepancy, action: Action) {
    returnFocusId = openerId(item, action);
    active = { id: item.id, action };
    notes = '';
    claimReference = '';
    locationId = '';
    formError = null;
    errorField = '';
    staleNotice = null;
    form = emptyForm();
    if (action === 'adjust') {
      form.reason =
        item.kind === 'surplus'
          ? `Ingreso del sobrante del traslado ${transfer.code}`
          : `Baja por ${item.kind === 'damage' ? 'avería' : 'faltante'} del traslado ${transfer.code}`;
      if (item.kind === 'surplus') void loadPackaging(item);
    }
    await tick();
    document.getElementById(`disc-${item.id}-field`)?.focus();
  }

  async function close() {
    active = null;
    formError = null;
    errorField = '';
    await tick();
    document.getElementById(returnFocusId)?.focus();
  }

  async function loadPackaging(item: TransferDiscrepancy) {
    const itemId = transfer.lines.find(
      (line) => line.id === item.transfer_detail_id
    )?.inventory_item_id;
    packagingChoices = [];
    if (!itemId) return;
    packagingState = 'loading';
    try {
      const all = await inventoryApi.listPackaging(itemId);
      packagingChoices = all.filter((choice) => choice.is_active && choice.is_current);
      packagingState = 'idle';
    } catch {
      packagingState = 'error';
    }
  }

  type Problem = { field: string; message: string };

  function validate(item: TransferDiscrepancy, action: Action): Problem | null {
    if (action === 'claim' && claimReference.trim().length < MIN_CLAIM)
      return {
        field: 'field',
        message: `Indica la referencia del reclamo (mínimo ${MIN_CLAIM} caracteres).`
      };
    if (action === 'adjust') {
      if (form.reason.trim().length < MIN_NOTES)
        return {
          field: 'field',
          message: `Indica el motivo del ajuste (mínimo ${MIN_NOTES} caracteres).`
        };
      if (!form.documentReference.trim())
        return { field: 'doc', message: 'Indica la referencia del documento de respaldo.' };
      if (!form.operationalDate) return { field: 'op', message: 'Indica la fecha operativa.' };
      if (!form.accountingDate) return { field: 'acc', message: 'Indica la fecha contable.' };
      if (item.kind === 'surplus') {
        if (form.packaging === 'definition' && !form.packagingId)
          return { field: 'pack', message: 'Elige el empaque del sobrante.' };
        if (form.packaging === 'measures') {
          if (!quantityString(form.weightKg))
            return { field: 'kg', message: 'Indica el peso bruto (kg) del sobrante.' };
          if (!quantityString(form.volumeM3))
            return { field: 'm3', message: 'Indica el volumen (m³) del sobrante.' };
        }
        if (canSeeCost && form.costMode !== 'none') {
          const cost = Number(form.cost);
          if (form.cost.trim() === '' || !Number.isFinite(cost) || cost < 0)
            return {
              field: 'cost',
              message: 'Indica un costo igual o mayor que cero, o elige «Sin costo documentado».'
            };
        }
      }
      return null;
    }
    if (action !== 'claim' && notes.trim().length < MIN_NOTES)
      return {
        field: 'field',
        message: `Escribe una nota de al menos ${MIN_NOTES} caracteres.`
      };
    return null;
  }

  function invalidFor(key: string): 'true' | undefined {
    return errorField === key && formError ? 'true' : undefined;
  }

  function describedBy(itemId: string, key: string): string | undefined {
    return errorField === key && formError ? `disc-${itemId}-${key}-error` : undefined;
  }

  async function submit(event: SubmitEvent, item: TransferDiscrepancy, action: Action) {
    event.preventDefault();
    if (lockedOut) return;
    const problem = validate(item, action);
    if (problem) {
      formError = problem.message;
      errorField = problem.field;
      await tick();
      document.getElementById(`disc-${item.id}-${problem.field}`)?.focus();
      return;
    }
    formError = null;
    errorField = '';
    let request: DiscrepancyRequest;
    if (action === 'claim')
      request = { action, discrepancy: item, claimReference: claimReference.trim() };
    else if (action === 'release')
      request = { action, discrepancy: item, notes: notes.trim(), locationId };
    else if (action === 'adjust') request = { action, discrepancy: item, form: { ...form } };
    else request = { action, discrepancy: item, notes: notes.trim() };
    submitting = true;
    let failure: string | null;
    try {
      failure = await onRun(request);
    } finally {
      submitting = false;
    }
    if (failure) {
      formError = failure;
      errorField = '';
    }
    // The buttons are enabled again, so focus can go back to the one that opened the form.
    else if (action !== 'adjust') await close();
  }

  const OPENER_LABEL: Record<Action, string> = {
    adjust: 'Preparar ajuste',
    claim: 'Registrar reclamo',
    release: 'Liberar a cuarentena',
    found: 'Llegó la mercadería',
    dismiss: 'Descartar sobrante',
    'origin-count': 'Registrar conteo en origen'
  };
  const SUBMIT_LABEL: Record<Action, string> = {
    adjust: 'Crear borrador del ajuste',
    claim: 'Guardar reclamo',
    release: 'Confirmar liberación',
    found: 'Confirmar que llegó',
    dismiss: 'Confirmar descarte',
    'origin-count': 'Guardar conteo'
  };

  function availableActions(item: TransferDiscrepancy): Action[] {
    if (!isDiscrepancyActive(item)) return [];
    const result: Action[] = [];
    if (item.kind === 'shortage') {
      if (canAdjust && (canAccessOrigin || canAccessDestination) && !hasActiveAdjustment(item))
        result.push('adjust');
      if (canReceive && canAccessDestination && !hasActiveAdjustment(item)) result.push('found');
    } else if (item.kind === 'damage') {
      if (canAdjust && canAccessDestination && !hasActiveAdjustment(item)) result.push('adjust');
      // With an adjustment in progress, the goods can only leave through it.
      if (canApproveAdjust && canAccessDestination && !hasActiveAdjustment(item)) {
        if (item.status === 'open') result.push('claim');
        result.push('release');
      }
    } else {
      if (canAdjust && canAccessDestination && !hasActiveAdjustment(item)) result.push('adjust');
      if (canApproveAdjust && canAccessDestination && !hasActiveAdjustment(item))
        result.push('dismiss');
    }
    return result;
  }

  function needsOriginCount(item: TransferDiscrepancy): boolean {
    return (
      item.origin_count_required && item.origin_counted_at == null && canAdjust && canAccessOrigin
    );
  }

  // The transfer was refreshed behind an open form (e.g. after a 409): if the row can no longer
  // take that action, the form closes and says why instead of failing again.
  $effect(() => {
    const current = active;
    if (!current || submitting) return;
    const item = rows.find((row) => row.id === current.id);
    const stillValid =
      item != null &&
      (current.action === 'origin-count'
        ? needsOriginCount(item)
        : availableActions(item).includes(current.action));
    if (stillValid) return;
    staleNotice = `${formError ? `${formError} ` : ''}Se actualizó el traslado: esta diferencia ya no admite esa acción.`;
    active = null;
    formError = null;
    errorField = '';
  });

  function quantityLine(item: TransferDiscrepancy): string {
    const base = `${formatQuantity(item.quantity)} ${item.base_unit_symbol ?? 'base'}`;
    return item.kind === 'damage' && item.damage_type
      ? `${base} · ${damageTypeLabel(item.damage_type)}`
      : base;
  }

  function openerLabel(item: TransferDiscrepancy, action: Action): string {
    if (action !== 'adjust') return OPENER_LABEL[action];
    return item.kind === 'surplus' ? 'Preparar ajuste de ingreso' : 'Preparar ajuste de baja';
  }
</script>

{#snippet fieldError(itemId: string, key: string)}
  {#if errorField === key && formError}
    <p id="disc-{itemId}-{key}-error" class="text-sm text-danger" role="alert">{formError}</p>
  {/if}
{/snippet}

{#if rows.length > 0}
  <section class="space-y-3" aria-labelledby="transfer-discrepancies-title">
    <header class="space-y-1">
      <h3 id="transfer-discrepancies-title" class="font-semibold text-foreground">
        Diferencias de la recepción
      </h3>
      {#if summary}<p class="text-sm text-foreground-muted">{summary}</p>{/if}
    </header>

    {#if underReview}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p>Con discrepancia: resuelve cada diferencia para cerrar el traslado.</p>
      </Callout>
    {/if}
    {#if staleNotice}
      <p
        class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
        role="status"
      >
        {staleNotice}
      </p>
    {/if}
    {#if valuationNoteNeeded}
      <p id="disc-valuation-note" class="text-sm text-foreground">
        Primero aprueba el saldo inicial de valuación de la empresa para poder aplicar ajustes.
        {#if canSeeCost}
          <a
            class="font-medium text-primary underline underline-offset-2"
            href="/inventory/valuation">Ir a valuación</a
          >
        {/if}
      </p>
    {/if}
    {#if originCountPending}
      <Callout variant="info" dismissible={false} class="mb-0">
        <p>
          Conteo pendiente en origen: cuenta las existencias de {originName} y registra el resultado en
          cada diferencia con «Registrar conteo en origen». No impide cerrar el traslado.
        </p>
      </Callout>
    {/if}

    <ul class="space-y-3">
      {#each rows as item (item.id)}
        {@const actions = availableActions(item)}
        {@const count = needsOriginCount(item)}
        {@const unit = item.base_unit_symbol ?? 'base'}
        <li>
          <article
            class="space-y-2 rounded-xl border border-border bg-surface p-3 sm:p-4"
            aria-labelledby="disc-{item.id}-title"
          >
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div class="min-w-0 space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <Badge variant={kindVariant(item.kind)}>{discrepancyKindLabel(item.kind)}</Badge>
                  <p id="disc-{item.id}-title" class="font-medium text-foreground">
                    {item.product_name}
                  </p>
                </div>
                <p class="text-sm text-foreground">{quantityLine(item)}</p>
              </div>
              <Badge variant={badgeVariant(item)}>
                {item.status === 'resolved' || item.status === 'cancelled'
                  ? discrepancyResolutionLabel(item.kind, item.resolution)
                  : discrepancyStatusLabel(item.status)}
              </Badge>
            </div>

            <p class="text-sm text-foreground-muted">{item.notes}</p>
            <p class="break-words text-xs text-foreground-muted">
              {item.sku ?? 'SKU sin registrar'}
              {#if item.location_code}· Ubicación {displayLocationCode(item.location_code)}{/if}
              {#if item.handling_unit_code}· Unidad {item.handling_unit_code}{/if}
              {#if item.evidence_reference}· Evidencia {item.evidence_reference}{/if}
              · Registrada {formatDate(item.opened_at)}{item.opened_by_name
                ? ` por ${item.opened_by_name}`
                : ''}
            </p>

            {#if item.status === 'in_claim'}
              <p class="text-xs text-foreground">
                En reclamo{item.claim_reference ? `: ${item.claim_reference}` : ''}. La mercancía
                sigue como avería hasta liberarla o darla de baja; no impide cerrar el traslado.
              </p>
            {/if}
            {#if item.adjustment}
              <p class="text-xs text-foreground-muted">
                Ajuste vinculado:
                <a
                  class="font-medium text-primary underline underline-offset-2"
                  href="/inventory/adjustments/{encodeURIComponent(item.adjustment.id)}"
                  >{item.adjustment.code}</a
                >
              </p>
            {/if}
            {#if item.resolved_at}
              <p class="text-xs text-foreground-muted">
                {discrepancyResolutionLabel(item.kind, item.resolution)} el {formatDate(
                  item.resolved_at
                )}{item.resolved_by_name
                  ? ` por ${item.resolved_by_name}`
                  : ''}{item.resolution_notes ? `: ${item.resolution_notes}` : ''}
              </p>
            {/if}
            {#if item.origin_count_required}
              {#if item.origin_counted_at}
                <p class="text-xs text-foreground-muted">
                  Conteo en origen registrado el {formatDate(
                    item.origin_counted_at
                  )}{item.origin_counted_by_name
                    ? ` por ${item.origin_counted_by_name}`
                    : ''}{item.origin_count_notes ? `: ${item.origin_count_notes}` : ''}
                </p>
              {:else}
                <p><Badge variant="warning">Conteo pendiente en origen</Badge></p>
              {/if}
            {/if}

            {#if actions.length || count}
              <div class="flex flex-wrap gap-2 pt-1">
                {#each actions as action (action)}
                  <Button
                    id={openerId(item, action)}
                    size="sm"
                    variant={action === 'adjust' ? 'primary' : 'secondary'}
                    disabled={lockedOut || (action === 'adjust' && !valuationReady)}
                    describedby={action === 'adjust' && !valuationReady
                      ? 'disc-valuation-note'
                      : undefined}
                    onclick={() => void open(item, action)}>{openerLabel(item, action)}</Button
                  >
                {/each}
                {#if count}
                  <Button
                    id={openerId(item, 'origin-count')}
                    size="sm"
                    variant="secondary"
                    disabled={lockedOut}
                    onclick={() => void open(item, 'origin-count')}
                    >{OPENER_LABEL['origin-count']}</Button
                  >
                {/if}
              </div>
            {:else if isDiscrepancyActive(item) && hasActiveAdjustment(item)}
              <p class="text-xs text-foreground-muted">
                Hay un ajuste en curso para esta diferencia. Termínalo o cancélalo desde el ajuste
                antes de resolverla de otra forma.
              </p>
            {:else if isDiscrepancyActive(item)}
              <p class="text-xs text-foreground-muted">
                {item.kind === 'shortage'
                  ? 'Este faltante lo resuelve quien tenga permiso de ajustes y acceso a la sucursal de origen o de destino.'
                  : 'Esta diferencia la resuelve quien tenga permiso de ajustes y acceso a la sucursal de destino.'}
              </p>
            {/if}

            {#if active && active.id === item.id}
              {@const action = active.action}
              <!-- Escape from any field closes the form; the keydown listens for its bubbling. -->
              <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
              <form
                class="space-y-3 rounded-xl border border-border bg-surface-muted/40 p-3 sm:p-4"
                aria-label={action === 'adjust' ? openerLabel(item, action) : OPENER_LABEL[action]}
                onsubmit={(event) => void submit(event, item, action)}
                onkeydown={(event) => {
                  if (event.key === 'Escape') {
                    event.stopPropagation();
                    void close();
                  }
                }}
                novalidate
              >
                {#if action === 'claim'}
                  <div class="space-y-1">
                    <label
                      class="block text-sm font-medium text-foreground"
                      for="disc-{item.id}-field">Referencia del reclamo</label
                    >
                    <input
                      id="disc-{item.id}-field"
                      class="field-control"
                      maxlength="500"
                      placeholder="Número de reclamo con el transportista o el proveedor"
                      aria-invalid={invalidFor('field')}
                      aria-describedby={describedBy(item.id, 'field')}
                      bind:value={claimReference}
                    />
                    {@render fieldError(item.id, 'field')}
                    <p class="text-xs text-foreground-muted">
                      La mercancía sigue como avería mientras dura el reclamo y puedes liberarla o
                      darla de baja después.
                    </p>
                  </div>
                {:else if action === 'adjust'}
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="space-y-1 sm:col-span-2">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-field">Motivo del ajuste</label
                      >
                      <textarea
                        id="disc-{item.id}-field"
                        class="field-control min-h-[72px]"
                        maxlength="4000"
                        aria-invalid={invalidFor('field')}
                        aria-describedby={describedBy(item.id, 'field')}
                        bind:value={form.reason}
                      ></textarea>
                      {@render fieldError(item.id, 'field')}
                    </div>
                    <div class="space-y-1 sm:col-span-2">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-doc">Documento de respaldo (referencia)</label
                      >
                      <input
                        id="disc-{item.id}-doc"
                        class="field-control"
                        maxlength="240"
                        placeholder="Acta, informe o número de documento"
                        aria-invalid={invalidFor('doc')}
                        aria-describedby={describedBy(item.id, 'doc')}
                        bind:value={form.documentReference}
                      />
                      {@render fieldError(item.id, 'doc')}
                    </div>
                    <div class="space-y-1">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-op">Fecha operativa</label
                      >
                      <input
                        id="disc-{item.id}-op"
                        class="field-control"
                        type="date"
                        aria-invalid={invalidFor('op')}
                        aria-describedby={describedBy(item.id, 'op')}
                        bind:value={form.operationalDate}
                      />
                      {@render fieldError(item.id, 'op')}
                    </div>
                    <div class="space-y-1">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-acc">Fecha contable</label
                      >
                      <input
                        id="disc-{item.id}-acc"
                        class="field-control"
                        type="date"
                        aria-invalid={invalidFor('acc')}
                        aria-describedby={describedBy(item.id, 'acc')}
                        bind:value={form.accountingDate}
                      />
                      {@render fieldError(item.id, 'acc')}
                    </div>
                    {#if item.kind === 'surplus'}
                      <fieldset class="space-y-2 sm:col-span-2">
                        <legend class="text-sm font-medium text-foreground"
                          >Empaque del sobrante</legend
                        >
                        <label class="flex items-start gap-2 text-sm text-foreground">
                          <input
                            type="radio"
                            class="mt-1"
                            value="source"
                            checked={form.packaging === 'source'}
                            onchange={() => (form.packaging = 'source')}
                          />
                          <span>Igual que la unidad de origen (recomendado)</span>
                        </label>
                        <label class="flex items-start gap-2 text-sm text-foreground">
                          <input
                            type="radio"
                            class="mt-1"
                            value="definition"
                            checked={form.packaging === 'definition'}
                            onchange={() => (form.packaging = 'definition')}
                          />
                          <span>Elegir un empaque del producto</span>
                        </label>
                        <label class="flex items-start gap-2 text-sm text-foreground">
                          <input
                            type="radio"
                            class="mt-1"
                            value="measures"
                            checked={form.packaging === 'measures'}
                            onchange={() => (form.packaging = 'measures')}
                          />
                          <span>Indicar peso y volumen reales</span>
                        </label>
                      </fieldset>
                      {#if form.packaging === 'definition'}
                        <div class="space-y-1 sm:col-span-2">
                          <label
                            class="block text-sm font-medium text-foreground"
                            for="disc-{item.id}-pack">Empaque</label
                          >
                          <select
                            id="disc-{item.id}-pack"
                            class="field-control"
                            value={form.packagingId}
                            aria-invalid={invalidFor('pack')}
                            aria-describedby={describedBy(item.id, 'pack')}
                            onchange={(event) => (form.packagingId = event.currentTarget.value)}
                          >
                            <option value=""
                              >{packagingState === 'loading'
                                ? 'Buscando empaques…'
                                : 'Elige un empaque'}</option
                            >
                            {#each packagingChoices as choice (choice.id)}
                              <option value={choice.id}
                                >{choice.name} · {choice.code} · {formatQuantity(
                                  choice.base_quantity
                                )}
                                {unit}</option
                              >
                            {/each}
                          </select>
                          {@render fieldError(item.id, 'pack')}
                          {#if packagingState === 'error'}
                            <p class="text-xs text-danger">
                              No se pudieron consultar los empaques. Puedes indicar peso y volumen.
                            </p>
                          {/if}
                        </div>
                      {:else if form.packaging === 'measures'}
                        <div class="space-y-1">
                          <label
                            class="block text-sm font-medium text-foreground"
                            for="disc-{item.id}-kg">Peso bruto (kg)</label
                          >
                          <input
                            id="disc-{item.id}-kg"
                            class="field-control"
                            type="number"
                            min="0.000001"
                            step="0.000001"
                            value={form.weightKg}
                            aria-invalid={invalidFor('kg')}
                            aria-describedby={describedBy(item.id, 'kg')}
                            oninput={(event) => (form.weightKg = event.currentTarget.value)}
                          />
                          {@render fieldError(item.id, 'kg')}
                        </div>
                        <div class="space-y-1">
                          <label
                            class="block text-sm font-medium text-foreground"
                            for="disc-{item.id}-m3">Volumen (m³)</label
                          >
                          <input
                            id="disc-{item.id}-m3"
                            class="field-control"
                            type="number"
                            min="0.000001"
                            step="0.000001"
                            value={form.volumeM3}
                            aria-invalid={invalidFor('m3')}
                            aria-describedby={describedBy(item.id, 'm3')}
                            oninput={(event) => (form.volumeM3 = event.currentTarget.value)}
                          />
                          {@render fieldError(item.id, 'm3')}
                        </div>
                      {/if}
                      {#if canSeeCost}
                        <div class="space-y-1">
                          <label
                            class="block text-sm font-medium text-foreground"
                            for="disc-{item.id}-costmode">Costo documentado</label
                          >
                          <select
                            id="disc-{item.id}-costmode"
                            class="field-control"
                            value={form.costMode}
                            onchange={(event) =>
                              (form.costMode = event.currentTarget
                                .value as DiscrepancyAdjustmentForm['costMode'])}
                          >
                            <option value="none">Sin costo documentado (costo promedio)</option>
                            <option value="unit">Costo unitario</option>
                            <option value="total">Costo total</option>
                          </select>
                        </div>
                        {#if form.costMode !== 'none'}
                          <div class="space-y-1">
                            <label
                              class="block text-sm font-medium text-foreground"
                              for="disc-{item.id}-cost"
                              >{form.costMode === 'unit'
                                ? 'Costo por unidad base'
                                : 'Costo total'}</label
                            >
                            <input
                              id="disc-{item.id}-cost"
                              class="field-control"
                              type="number"
                              min="0"
                              step="0.000001"
                              value={form.cost}
                              aria-invalid={invalidFor('cost')}
                              aria-describedby={describedBy(item.id, 'cost')}
                              oninput={(event) => (form.cost = event.currentTarget.value)}
                            />
                            {@render fieldError(item.id, 'cost')}
                          </div>
                        {/if}
                      {/if}
                    {/if}
                    <div class="space-y-1 sm:col-span-2">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-notes">Notas (opcional)</label
                      >
                      <textarea
                        id="disc-{item.id}-notes"
                        class="field-control min-h-14"
                        maxlength="4000"
                        bind:value={form.notes}
                      ></textarea>
                    </div>
                  </div>
                  <p class="text-xs text-foreground-muted">
                    Se crea un borrador. Después adjuntas la evidencia y lo apruebas en el ajuste;
                    el inventario cambia hasta aplicarlo.
                  </p>
                {:else}
                  <div class="space-y-1">
                    <label
                      class="block text-sm font-medium text-foreground"
                      for="disc-{item.id}-field"
                      >{action === 'release'
                        ? 'Resultado de la inspección'
                        : action === 'origin-count'
                          ? 'Resultado del conteo en origen'
                          : action === 'found'
                            ? 'Cómo llegó o dónde se encontró'
                            : 'Por qué se descarta'}</label
                    >
                    <textarea
                      id="disc-{item.id}-field"
                      class="field-control min-h-[72px]"
                      maxlength="4000"
                      aria-invalid={invalidFor('field')}
                      aria-describedby={describedBy(item.id, 'field')}
                      bind:value={notes}
                    ></textarea>
                    {@render fieldError(item.id, 'field')}
                  </div>
                  {#if action === 'release'}
                    <div class="space-y-1">
                      <label
                        class="block text-sm font-medium text-foreground"
                        for="disc-{item.id}-loc">Ubicación de cuarentena (opcional)</label
                      >
                      <select
                        id="disc-{item.id}-loc"
                        class="field-control"
                        value={locationId}
                        onchange={(event) => (locationId = event.currentTarget.value)}
                      >
                        <option value=""
                          >{item.location_code
                            ? `La misma ubicación (${displayLocationCode(item.location_code)})`
                            : 'La misma ubicación'}</option
                        >
                        {#each locations as location (location.id)}
                          <option value={location.id}
                            >{location.code} · {location.location_type}</option
                          >
                        {/each}
                      </select>
                      <p class="text-xs text-foreground-muted">
                        Si una parte quedó inservible, libera todo a cuarentena y da de baja esa
                        parte con un ajuste ordinario.
                      </p>
                    </div>
                  {/if}
                {/if}

                {#if formError && errorField === ''}
                  <p class="text-sm text-danger" role="alert">{formError}</p>
                {/if}
                <div class="flex flex-wrap justify-end gap-2">
                  <Button variant="secondary" disabled={submitting} onclick={() => void close()}
                    >Volver</Button
                  >
                  <Button type="submit" disabled={lockedOut}
                    >{submitting ? 'Guardando…' : SUBMIT_LABEL[action]}</Button
                  >
                </div>
              </form>
            {/if}
          </article>
        </li>
      {/each}
    </ul>
  </section>
{/if}
