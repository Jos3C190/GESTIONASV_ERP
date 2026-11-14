<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { DOCUMENT_ACCEPT } from '$lib/features/documents/document-upload';
  import type { RetaceoDetail, RetaceoCostClass, RetaceoCostDocument } from '$lib/types/retaceo';
  import type { EditableRetaceoCost } from '../retaceo-cost-editor-types';
  import type { PurchaseOrderExpenseType } from '$lib/types/purchase-order';
  import type { ActualPurchaseExpense } from '$lib/features/purchase-orders/actual-expenses';

  type Props = {
    manualEntry?: boolean;
    expenseTypes?: PurchaseOrderExpenseType[];
    actualExpenses?: ActualPurchaseExpense[];
    onExpenseTypeChange?: (value: string) => void;
    onIncurredOnChange?: (value: string) => void;
    onSourceChange?: (value: string) => void;
    cost: EditableRetaceoCost;
    index: number;
    currency: string;
    purchaseLines: RetaceoDetail[];
    quantityStage?: 'recibidas' | 'aceptadas';
    validation: Record<string, string>;
    saving: boolean;
    uploading: boolean;
    deletingDocumentId: string | null;
    downloadingDocumentId: string | null;
    classLabel: (value: RetaceoCostClass) => string;
    formatMoney: (value: string | number, currency: string) => string;
    formatQuantity: (value: string) => string;
    productLabel: (id: number) => string;
    unitLabel: (id: number) => string;
    onExpandedChange: (expanded: boolean) => void;
    onTitleInput: (value: string) => void;
    onClassificationChange: (value: RetaceoCostClass) => void;
    onAmountInput: (value: string) => void;
    onDescriptionInput: (value: string) => void;
    onRemove: () => void;
    onChooseFile: (event: Event) => void | Promise<void>;
    onDownload: (document: RetaceoCostDocument) => void;
    onRemoveDocument: (document: RetaceoCostDocument) => void;
  };

  let {
    manualEntry = false,
    expenseTypes = [],
    actualExpenses = [],
    onExpenseTypeChange,
    onIncurredOnChange,
    onSourceChange,
    cost,
    index,
    currency,
    purchaseLines,
    quantityStage = 'aceptadas',
    validation,
    saving,
    uploading,
    deletingDocumentId,
    downloadingDocumentId,
    classLabel,
    formatMoney,
    formatQuantity,
    productLabel,
    unitLabel,
    onExpandedChange,
    onTitleInput,
    onClassificationChange,
    onAmountInput,
    onDescriptionInput,
    onRemove,
    onChooseFile,
    onDownload,
    onRemoveDocument
  }: Props = $props();
  const fixed = $derived(manualEntry && cost.classification !== 'expense');

  const COST_CLASSES: { value: RetaceoCostClass; label: string }[] = [
    { value: 'freight', label: 'Flete y seguro' },
    { value: 'expense', label: 'Gasto adicional' },
    { value: 'dai', label: 'DAI' }
  ];

  function hasValidationIssue(): boolean {
    return Object.keys(validation).some((key) => key.startsWith(`${cost.key}-`));
  }

  function classTone(value: RetaceoCostClass): string {
    switch (value) {
      case 'freight':
        return 'border-primary/30 bg-primary/10 text-foreground';
      case 'dai':
        return 'border-warning/30 bg-warning/10 text-foreground';
      default:
        return 'border-border bg-surface-muted text-foreground-muted';
    }
  }
</script>

<details
  class="border-b border-border last:border-b-0"
  data-cost-key={cost.key}
  open={cost.expanded}
  ontoggle={(event) => onExpandedChange((event.currentTarget as HTMLDetailsElement).open)}
>
  <summary
    class="group flex cursor-pointer flex-col gap-3 px-4 py-3 hover:bg-surface-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:flex-row sm:items-center sm:justify-between"
  >
    <div class="flex min-w-0 items-start gap-3">
      <span
        class="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-semibold text-foreground"
        aria-hidden="true"
      >
        {String(index + 1).padStart(2, '0')}
      </span>
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span class="max-w-full truncate text-sm font-semibold text-foreground">
            {cost.title.trim() || `Gasto ${index + 1}`}
          </span>
          <span class={`rounded-full border px-2 py-0.5 text-xs ${classTone(cost.classification)}`}>
            {classLabel(cost.classification)}
          </span>
          {#if cost.sourcePurchaseOrderExpenseId}
            <span
              class="rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-xs text-foreground"
            >
              {manualEntry ? 'Bitácora de gastos' : 'De la orden'}
            </span>
          {/if}
          {#if hasValidationIssue()}
            <span
              class="rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-xs font-medium text-foreground"
            >
              Revisar
            </span>
          {/if}
        </div>
        <p class="mt-1 text-xs text-foreground-muted">
          Se reparte según el FOB · {cost.documents.length} comprobante(s)
        </p>
      </div>
    </div>
    <div class="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
      <div class="text-left sm:text-right">
        <p class="text-sm font-semibold text-foreground">
          {cost.amount ? formatMoney(cost.amount, currency) : 'Monto pendiente'}
        </p>
        <p class="mt-0.5 text-xs text-foreground-muted">Monto del gasto</p>
      </div>
      <span class="text-xs font-medium text-primary">
        {cost.expanded ? 'Ocultar' : 'Editar gasto'}
      </span>
    </div>
  </summary>

  <div class="space-y-4 border-t border-border bg-surface-muted/10 p-3 sm:p-4">
    {#if fixed}
      {#if cost.amount.trim() && Number(cost.amount) === 0}
        <p class="text-xs leading-5 text-foreground-muted">
          Importe 0: se excluirá del cálculo al guardar. Los comprobantes se conservan en el
          historial.
        </p>
      {/if}
      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-surface-muted p-3 text-sm"
      >
        <p class="text-foreground-muted">
          Reparto según FOB ·
          <strong class="font-mono text-foreground">{formatMoney(cost.amount, currency)}</strong>
        </p>
        <a
          class="rounded font-medium text-primary underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-primary"
          href={`#fixed-${cost.classification === 'freight' ? 'freight' : 'dai'}`}
          >Editar {classLabel(cost.classification)}</a
        >
      </div>
    {:else}
      <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div
          class={manualEntry
            ? 'grid flex-1 gap-3 sm:grid-cols-2'
            : 'grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(12rem,1.3fr)_minmax(10rem,1fr)_minmax(9rem,.8fr)]'}
        >
          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Concepto</span>
            <input
              id={`${cost.key}-title`}
              type="text"
              maxlength="160"
              value={cost.title}
              oninput={(event) => onTitleInput(event.currentTarget.value)}
              disabled={saving}
              aria-invalid={validation[`${cost.key}-title`] ? 'true' : undefined}
              aria-describedby={validation[`${cost.key}-title`]
                ? `${cost.key}-title-error`
                : undefined}
              class="h-10 w-full rounded-md border border-border-control bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
              placeholder="Ej. Manejo en aduana"
            />
            {#if validation[`${cost.key}-title`]}
              <span id={`${cost.key}-title-error`} class="block text-xs text-foreground">
                {validation[`${cost.key}-title`]}
              </span>
            {/if}
          </label>

          {#if !manualEntry}<label class="space-y-1.5 text-sm font-medium text-foreground">
              <span>Clasificación</span>
              <select
                value={cost.classification}
                onchange={(event) =>
                  onClassificationChange(event.currentTarget.value as RetaceoCostClass)}
                disabled={saving}
                class="h-10 w-full rounded-md border border-border-control bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
              >
                {#each COST_CLASSES as option (option.value)}
                  <option value={option.value}>{option.label}</option>
                {/each}
              </select>
              {#if cost.sourcePurchaseOrderExpenseId}
                <span class="block text-xs text-foreground-muted"
                  >Importado de la orden de compra</span
                >
              {/if}
            </label>{/if}

          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Monto real · {currency}</span>
            <input
              id={`${cost.key}-amount`}
              type="number"
              min="0.000001"
              step="0.000001"
              value={cost.amount}
              oninput={(event) => onAmountInput(event.currentTarget.value)}
              disabled={saving}
              aria-invalid={validation[`${cost.key}-amount`] ? 'true' : undefined}
              aria-describedby={validation[`${cost.key}-amount`]
                ? `${cost.key}-amount-error`
                : undefined}
              class="h-10 w-full rounded-md border border-border-control bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
              placeholder="0.00"
            />
            {#if validation[`${cost.key}-amount`]}
              <span id={`${cost.key}-amount-error`} class="block text-xs text-foreground">
                {validation[`${cost.key}-amount`]}
              </span>
            {/if}
          </label>
        </div>

        {#if !fixed && (!cost.sourcePurchaseOrderExpenseId || manualEntry)}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onclick={onRemove}
            disabled={saving || uploading}
          >
            Quitar
          </Button>
        {/if}
      </div>

      {#if manualEntry && !fixed}
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="space-y-1.5 text-sm font-medium text-foreground"
            ><span>Categoría del gasto adicional</span>
            <select
              id={`${cost.key}-category`}
              required
              value={cost.expenseTypeId ?? ''}
              disabled={saving}
              onchange={(event) => onExpenseTypeChange?.(event.currentTarget.value)}
              aria-invalid={!!validation[`${cost.key}-category`]}
              aria-describedby={validation[`${cost.key}-category`]
                ? `${cost.key}-category-error`
                : undefined}
              class="h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
              ><option value="">Selecciona una categoría</option
              >{#each expenseTypes as option (option.id)}<option value={option.id}
                  >{option.name}</option
                >{/each}</select
            >
            {#if validation[`${cost.key}-category`]}<span
                id={`${cost.key}-category-error`}
                role="alert"
                class="block text-xs text-danger">{validation[`${cost.key}-category`]}</span
              >{/if}
          </label>
          <label class="space-y-1.5 text-sm font-medium text-foreground"
            ><span>Fecha del gasto</span><input
              id={`${cost.key}-date`}
              type="date"
              required
              value={cost.incurredOn ?? ''}
              disabled={saving}
              oninput={(event) => onIncurredOnChange?.(event.currentTarget.value)}
              aria-invalid={!!validation[`${cost.key}-date`]}
              aria-describedby={validation[`${cost.key}-date`]
                ? `${cost.key}-date-error`
                : undefined}
              class="h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
            />{#if validation[`${cost.key}-date`]}<span
                id={`${cost.key}-date-error`}
                role="alert"
                class="block text-xs text-danger">{validation[`${cost.key}-date`]}</span
              >{/if}</label
          >
          <label class="space-y-1.5 text-sm font-medium text-foreground sm:col-span-2"
            ><span>Gasto real relacionado (opcional)</span><select
              value={cost.sourcePurchaseOrderExpenseId ?? ''}
              disabled={saving || !!cost.id}
              onchange={(event) => onSourceChange?.(event.currentTarget.value)}
              class="h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
              ><option value="">Gasto capturado directamente en retaceo</option
              >{#each actualExpenses as source (source.id)}<option value={source.id}
                  >{source.reference} · {source.description} · {source.incurred_on
                    .split('-')
                    .reverse()
                    .join('/')} · {formatMoney(source.amount, currency)}</option
                >{/each}</select
            ><span class="block text-xs leading-5 text-foreground-muted"
              >Elige la referencia antes de guardar. Captura monto, categoría y fecha manualmente;
              se validan contra la bitácora y se vinculan sus comprobantes.</span
            ></label
          >
        </div>
      {/if}

      <label class="block space-y-1.5 text-sm font-medium text-foreground">
        <span>Descripción o referencia</span>
        <textarea
          id={`${cost.key}-description`}
          required={manualEntry && !fixed}
          rows="2"
          maxlength="4000"
          value={cost.description}
          oninput={(event) => onDescriptionInput(event.currentTarget.value)}
          disabled={saving}
          aria-invalid={Boolean(validation[`${cost.key}-description`])}
          aria-describedby={validation[`${cost.key}-description`]
            ? `${cost.key}-description-error`
            : undefined}
          class="w-full rounded-md border border-border-control bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
          placeholder="Factura, referencia del proveedor u observaciones del gasto"
        ></textarea>
        {#if validation[`${cost.key}-description`]}<span
            id={`${cost.key}-description-error`}
            role="alert"
            class="block text-xs text-danger">{validation[`${cost.key}-description`]}</span
          >{/if}
      </label>
    {/if}
    <section class="border-t border-border pt-4">
      <div class="border-b border-border bg-surface-muted/50 px-3 py-3">
        <h3 class="text-base font-semibold text-foreground">Reparto por producto</h3>
        <p class="mt-1 text-sm leading-5 text-foreground-muted">
          Este importe se reparte automáticamente entre los productos según su FOB.
        </p>
      </div>
      <ul class="divide-y divide-border" aria-label="Reparto por producto">
        {#each purchaseLines as line (line.purchase_detail_id)}
          <li
            class="grid gap-1 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-foreground">
                {productLabel(line.product_id)}
              </p>
              <p class="mt-1 text-sm text-foreground-muted">
                {unitLabel(line.unit_id)} · {formatQuantity(line.quantity)}
                {quantityStage}
              </p>
            </div>
            <p class="text-sm font-semibold tabular-nums text-foreground">
              {formatMoney(cost.allocations[line.purchase_detail_id] ?? '0', currency)}
            </p>
          </li>
        {/each}
      </ul>
    </section>
    <section class="border-t border-border pt-4">
      <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {uploading ? `Adjuntando comprobante a ${cost.title || 'el gasto'}.` : ''}
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 class="flex flex-wrap items-center gap-2 text-base font-semibold text-foreground">
            Comprobantes (opcional)
            <span
              class="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted"
            >
              {cost.documents.length}
            </span>
          </h3>
          <p class="mt-1 text-sm leading-5 text-foreground-muted">
            Puedes adjuntar una factura, recibo u otro respaldo. No es obligatorio para calcular.
          </p>
        </div>
        {#if cost.id}
          <label
            class="relative inline-flex h-9 items-center justify-center whitespace-nowrap rounded-lg border border-border-control bg-surface-elevated px-3.5 text-sm font-medium text-foreground shadow-soft transition-colors hover:bg-surface-hover focus-within:ring-2 focus-within:ring-foreground focus-within:ring-offset-2 focus-within:ring-offset-surface"
            class:pointer-events-none={uploading || saving || deletingDocumentId !== null}
            class:opacity-40={uploading || saving || deletingDocumentId !== null}
          >
            <span aria-hidden="true">{uploading ? 'Adjuntando…' : 'Adjuntar documento'}</span>
            <input
              class="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
              type="file"
              accept={DOCUMENT_ACCEPT}
              disabled={uploading || saving || deletingDocumentId !== null}
              aria-label={`Adjuntar comprobante a ${cost.title || 'gasto'}`}
              onchange={onChooseFile}
            />
          </label>
        {:else}
          <span class="text-sm text-foreground-muted">Guarda el borrador para adjuntar.</span>
        {/if}
      </div>

      {#if cost.documents.length === 0}
        <p
          class="mt-3 rounded-lg border border-dashed border-border px-3 py-3 text-sm text-foreground-muted"
        >
          Sin comprobantes adjuntos. Puedes calcular el retaceo sin archivos.
        </p>
      {:else}
        <ul
          class="mt-3 divide-y divide-border rounded-lg border border-border bg-surface"
          aria-label={`Comprobantes adjuntos: ${cost.documents.length}`}
        >
          {#each cost.documents as document (document.id)}
            <li
              class="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
            >
              <div class="min-w-0">
                <p class="break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
                  {document.file_name}
                </p>
                <p class="mt-1 break-words text-sm text-foreground-muted">
                  {document.uploaded_at ? 'Comprobante cargado' : 'Carga pendiente'}
                  {#if document.status}
                    · {(
                      {
                        pending: 'Pendiente',
                        uploading: 'Cargando',
                        uploaded: 'Cargado',
                        ready: 'Disponible',
                        active: 'Activo',
                        validated: 'Validado',
                        failed: 'Carga fallida',
                        rejected: 'Rechazado',
                        archived: 'Archivado',
                        deleted: 'Retirado',
                        quarantined: 'En revisión'
                      } as Record<string, string>
                    )[document.status] ?? 'En revisión'}{/if}
                </p>
              </div>
              {#if cost.id}
                <div class="flex flex-wrap gap-2 sm:justify-end">
                  <Button
                    size="sm"
                    variant="secondary"
                    class="shrink-0"
                    disabled={downloadingDocumentId !== null || !document.uploaded_at}
                    onclick={() => onDownload(document)}
                  >
                    {downloadingDocumentId === document.id ? 'Preparando…' : 'Descargar'}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    class="shrink-0"
                    disabled={saving ||
                      uploading ||
                      downloadingDocumentId !== null ||
                      deletingDocumentId !== null}
                    onclick={() => onRemoveDocument(document)}
                  >
                    {deletingDocumentId === document.id ? 'Quitando…' : 'Quitar'}
                  </Button>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
</details>
