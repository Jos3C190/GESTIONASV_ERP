<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { DOCUMENT_ACCEPT } from '$lib/features/documents/document-upload';
  import type { RetaceoDetail, RetaceoCostClass, RetaceoCostDocument } from '$lib/types/retaceo';
  import type { EditableRetaceoCost } from '../retaceo-cost-editor-types';

  type Props = {
    cost: EditableRetaceoCost;
    index: number;
    currency: string;
    purchaseLines: RetaceoDetail[];
    validation: Record<string, string>;
    saving: boolean;
    uploading: boolean;
    deletingDocumentId: string | null;
    downloadingDocumentId: string | null;
    allocatedAmount: number;
    remainingAmount: number;
    allocatedPercent: number;
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
    onAllocationInput: (purchaseDetailId: string, value: string) => void;
    onRemove: () => void;
    onChooseFile: (event: Event) => void | Promise<void>;
    onDownload: (document: RetaceoCostDocument) => void;
    onRemoveDocument: (document: RetaceoCostDocument) => void;
  };

  let {
    cost,
    index,
    currency,
    purchaseLines,
    validation,
    saving,
    uploading,
    deletingDocumentId,
    downloadingDocumentId,
    allocatedAmount,
    remainingAmount,
    allocatedPercent,
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
    onAllocationInput,
    onRemove,
    onChooseFile,
    onDownload,
    onRemoveDocument
  }: Props = $props();

  const COST_CLASSES: { value: RetaceoCostClass; label: string }[] = [
    { value: 'freight', label: 'Flete' },
    { value: 'expense', label: 'Otro gasto' },
    { value: 'dai', label: 'DAI' },
    { value: 'import_vat', label: 'IVA de importación' }
  ];

  function hasValidationIssue(): boolean {
    return Object.keys(validation).some((key) => key.startsWith(`${cost.key}-`));
  }

  function classTone(value: RetaceoCostClass): string {
    switch (value) {
      case 'freight':
        return 'border-info/30 bg-info/10 text-info';
      case 'dai':
        return 'border-warning/30 bg-warning/10 text-warning';
      case 'import_vat':
        return 'border-primary/30 bg-primary/10 text-primary';
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
        class="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 font-mono text-xs font-semibold text-primary"
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
              class="rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-xs text-primary"
            >
              De la orden
            </span>
          {/if}
          {#if hasValidationIssue()}
            <span
              class="rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger"
            >
              Revisar
            </span>
          {/if}
        </div>
        <p class="mt-1 text-xs text-foreground-muted">
          {#if cost.classification === 'import_vat'}
            IVA informativo · {cost.documents.length} comprobante(s)
          {:else}
            Asignado {formatMoney(allocatedAmount, currency)} · Pendiente
            {formatMoney(remainingAmount, currency)} · {cost.documents.length} comprobante(s)
          {/if}
        </p>
      </div>
    </div>
    <div class="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
      <div class="text-left sm:text-right">
        <p class="text-sm font-semibold text-foreground">
          {cost.amount ? formatMoney(cost.amount, currency) : 'Monto pendiente'}
        </p>
        <p class="mt-0.5 text-xs text-foreground-muted">
          {cost.classification === 'import_vat' ? 'Importe informativo' : 'Monto del gasto'}
        </p>
      </div>
      <span class="text-xs font-medium text-primary">
        {cost.expanded ? 'Ocultar' : 'Editar gasto'}
      </span>
    </div>
  </summary>

  <div class="space-y-4 border-t border-border bg-surface-muted/10 p-3 sm:p-4">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div
        class="grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(12rem,1.3fr)_minmax(10rem,1fr)_minmax(9rem,.8fr)]"
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
            class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
            placeholder="Ej. Flete internacional"
          />
          {#if validation[`${cost.key}-title`]}
            <span id={`${cost.key}-title-error`} class="block text-xs text-danger">
              {validation[`${cost.key}-title`]}
            </span>
          {/if}
        </label>

        <label class="space-y-1.5 text-sm font-medium text-foreground">
          <span>Clasificación</span>
          <select
            value={cost.classification}
            onchange={(event) =>
              onClassificationChange(event.currentTarget.value as RetaceoCostClass)}
            disabled={saving}
            class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
          >
            {#each COST_CLASSES as option (option.value)}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
          {#if cost.sourcePurchaseOrderExpenseId}
            <span class="block text-xs text-foreground-muted">Importado de la orden de compra</span>
          {/if}
        </label>

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
            class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
            placeholder="0.00"
          />
          {#if validation[`${cost.key}-amount`]}
            <span id={`${cost.key}-amount-error`} class="block text-xs text-danger">
              {validation[`${cost.key}-amount`]}
            </span>
          {/if}
        </label>
      </div>

      {#if !cost.sourcePurchaseOrderExpenseId}
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

    <label class="block space-y-1.5 text-sm font-medium text-foreground">
      <span>Descripción o referencia</span>
      <textarea
        rows="2"
        maxlength="4000"
        value={cost.description}
        oninput={(event) => onDescriptionInput(event.currentTarget.value)}
        disabled={saving}
        class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
        placeholder="Factura, referencia del proveedor u observaciones del gasto"
      ></textarea>
    </label>

    {#if cost.classification === 'import_vat'}
      <div
        class="rounded-lg border border-info/20 bg-info/5 px-3 py-3 text-sm text-foreground-muted"
      >
        IVA informativo: no se distribuye entre los productos ni se suma al costo aterrizado.
      </div>
    {:else}
      <section class="border-t border-border pt-4">
        <div
          class="flex flex-col gap-2 border-b border-border bg-surface-muted/50 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h3 class="text-base font-semibold text-foreground">Distribución por producto</h3>
            <p class="mt-1 text-sm leading-5 text-foreground-muted">
              Asigna este gasto entre las líneas aceptadas de la recepción.
            </p>
          </div>
          <p class="text-sm font-medium text-foreground">
            Distribuido {formatMoney(allocatedAmount, currency)}
            <span class={remainingAmount < -0.000001 ? 'text-danger' : 'text-foreground-muted'}>
              · Pendiente {formatMoney(remainingAmount, currency)}
            </span>
          </p>
        </div>

        <div
          class="h-1.5 bg-surface-muted"
          role="meter"
          aria-label={`Porcentaje distribuido de ${cost.title || 'gasto'}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={allocatedPercent}
          aria-valuetext={`${Math.round(allocatedPercent)}% distribuido`}
        >
          <div
            class={`h-full rounded-r-full transition-[width] duration-200 motion-reduce:transition-none ${remainingAmount < -0.000001 ? 'bg-danger' : 'bg-primary'}`}
            style:width={`${allocatedPercent}%`}
          ></div>
        </div>

        <div class="divide-y divide-border">
          {#each purchaseLines as line (line.purchase_detail_id)}
            <div
              class="grid gap-3 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,14rem)] sm:items-center"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-foreground">
                  {productLabel(line.product_id)}
                </p>
                <p class="mt-1 text-sm text-foreground-muted">
                  {unitLabel(line.unit_id)} · {formatQuantity(line.quantity)} aceptado(s)
                </p>
              </div>
              <label class="space-y-1 text-sm font-medium text-foreground-muted">
                <span>Monto asignado · {currency}</span>
                <input
                  type="number"
                  min="0"
                  step="0.000001"
                  value={cost.allocations[line.purchase_detail_id] ?? '0'}
                  oninput={(event) =>
                    onAllocationInput(line.purchase_detail_id, event.currentTarget.value)}
                  disabled={saving}
                  aria-label={`Monto de ${classLabel(cost.classification)} asignado a ${productLabel(line.product_id)}`}
                  aria-invalid={validation[`${cost.key}-allocation`] ? 'true' : undefined}
                  aria-describedby={validation[`${cost.key}-allocation`]
                    ? `${cost.key}-allocation-error`
                    : undefined}
                  class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
                />
              </label>
            </div>
          {/each}
        </div>
        {#if validation[`${cost.key}-allocation`]}
          <p
            id={`${cost.key}-allocation-error`}
            class="border-t border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {validation[`${cost.key}-allocation`]}
          </p>
        {/if}
      </section>
    {/if}

    <section class="border-t border-border pt-4">
      <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {uploading ? `Adjuntando comprobante a ${cost.title || 'el gasto'}.` : ''}
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 class="flex flex-wrap items-center gap-2 text-base font-semibold text-foreground">
            Comprobantes
            <span
              class="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted"
            >
              {cost.documents.length}
            </span>
          </h3>
          <p class="mt-1 text-sm leading-5 text-foreground-muted">
            Factura, recibo u otro documento de respaldo.
          </p>
        </div>
        {#if cost.id}
          <label
            class="relative inline-flex h-9 items-center justify-center whitespace-nowrap rounded-lg border border-border bg-surface-elevated px-3.5 text-sm font-medium text-foreground shadow-soft transition-all hover:border-border-strong hover:bg-surface-hover focus-within:shadow-glow"
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
          Sin comprobantes. Se requiere al menos uno para calcular este retaceo.
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
                    · {document.status}{/if}
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
