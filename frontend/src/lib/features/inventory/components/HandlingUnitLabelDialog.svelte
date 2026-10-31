<script lang="ts">
  import { onDestroy, tick, untrack } from 'svelte';
  import QRCode from 'qrcode';
  import JsBarcode from 'jsbarcode';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '../services';
  import type { HandlingUnit, InventoryLabelPreview, InventoryLabelLayout } from '../types';
  import LabelPrintSettings from './LabelPrintSettings.svelte';
  import LabelPrintPreview from './LabelPrintPreview.svelte';
  import {
    DEFAULT_LABEL_LAYOUT,
    buildLabelPrintDocument,
    labelDataFromSnapshot,
    labelCopiesIssue,
    labelLayoutIssue,
    prepareLabelPrintWindow
  } from '../label-printing';

  interface Props {
    unit: HandlingUnit | null;
    canVerify?: boolean;
    contextKey?: string;
    onclose?: () => void;
    onconfirmed?: (handlingUnitId: string) => void;
  }

  let { unit, canVerify = false, contextKey = '', onclose, onconfirmed }: Props = $props();
  let qrDialog = $state<HTMLDialogElement | null>(null);
  let selectedQrUnit = $state<HandlingUnit | null>(null);
  let qrDataUrl = $state<string | null>(null);
  let publicTraceHref = $state<string | null>(null);
  let qrError = $state<string | null>(null);
  let qrGenerating = $state(false);
  let labelPreview = $state<InventoryLabelPreview | null>(null);
  let labelPreviewLoading = $state(false);
  let labelPreviewError = $state<string | null>(null);
  let labelPreviewRetryable = $state(true);
  let barcodeError = $state<string | null>(null);
  let barcodeSvg = $state<SVGSVGElement | null>(null);
  let barcodeReady = $state(false);
  let barcodeMarkup = $state<string | null>(null);
  let qrModules = $state<number | null>(null);
  let labelLayout = $state<InventoryLabelLayout>({ ...DEFAULT_LABEL_LAYOUT });
  let labelPrintError = $state<string | null>(null);
  let labelPrintNeedsRefresh = $state(false);
  let labelNotes = $state('');
  let previewFitError = $state<string | null>(null);
  let checkedPreviewHtml = $state<string | null>(null);
  let layoutIssue = $derived(
    labelPreview
      ? labelLayoutIssue(labelLayout, labelPreview.product_internal_code, qrModules)
      : null
  );
  let printDocument = $derived.by(() => {
    if (!labelPreview || layoutIssue) return { html: null, error: null };
    if (labelLayout.content !== 'qr' && (!barcodeReady || !barcodeMarkup))
      return { html: null, error: null };
    if (labelLayout.content !== 'barcode' && !qrDataUrl) return { html: null, error: null };
    try {
      return {
        html: buildLabelPrintDocument(
          { ...labelPreview, notes: labelNotes },
          labelLayout,
          qrDataUrl,
          barcodeMarkup
        ),
        error: null
      };
    } catch (cause) {
      return {
        html: null,
        error: cause instanceof Error ? cause.message : 'No se pudo preparar la etiqueta.'
      };
    }
  });
  let labelPrintHtml = $derived(printDocument.html);
  let labelCopies = $state('1');
  let labelRecording = $state(false);
  let labelPlacementConfirming = $state(false);
  let qrPreviewUnitId: string | null = null;
  let labelPreviewUnitId: string | null = null;
  let barcodeProductCode: string | null = null;
  let labelPlacementMessage = $state<string | null>(null);
  let labelPlacementError = $state<string | null>(null);
  type LabelConfirmationAttempt = {
    unitId: string;
    printId: string;
    key: string;
  };
  let labelConfirmationAttempts = new Map<string, LabelConfirmationAttempt>();
  let revocationConfirmOpen = $state(false);
  let revokingTraceLinks = $state(false);
  let revocationMessage = $state<string | null>(null);
  let revocationError = $state<string | null>(null);
  type LabelPrintAttempt = {
    unitId: string;
    key: string;
    copies: number;
    reason: 'initial' | 'reprint';
    printDate: string;
    layout: InventoryLabelLayout;
    notes: string | null;
  };
  let labelPrintAttempts = new Map<string, LabelPrintAttempt>();
  let qrPreviewSequence = 0;
  let labelPreviewSequence = 0;
  let dialogSessionSequence = 0;
  let placementOperationSequence = 0;
  let dialogContextKey = $state<string | null>(null);
  let mounted = true;

  $effect(() => {
    void labelPrintHtml;
    previewFitError = null;
    checkedPreviewHtml = null;
  });

  onDestroy(() => {
    mounted = false;
    dialogSessionSequence += 1;
    placementOperationSequence += 1;
  });

  $effect(() => {
    const element = barcodeSvg;
    const preview = labelPreview;
    barcodeReady = false;
    barcodeMarkup = null;
    barcodeProductCode = null;
    if (!element || !preview) return;
    try {
      JsBarcode(element, preview.product_internal_code, {
        format: 'CODE128B',
        displayValue: false,
        height: 52,
        width: 2,
        margin: 4,
        marginLeft: 20,
        marginRight: 20,
        fontSize: 14,
        textMargin: 2
      });
      element.setAttribute('preserveAspectRatio', 'none');
      barcodeMarkup = element.outerHTML;
      barcodeError = null;
      barcodeProductCode = preview.product_internal_code;
      barcodeReady = true;
    } catch {
      barcodeProductCode = null;
      barcodeError = 'El código interno no se puede representar en un código de barras.';
    }
  });

  async function showHandlingUnitQr(unit: HandlingUnit) {
    const sequence = ++qrPreviewSequence;
    const previewSequence = ++labelPreviewSequence;
    dialogSessionSequence += 1;
    placementOperationSequence += 1;
    selectedQrUnit = unit;
    dialogContextKey = contextKey;
    qrDataUrl = null;
    qrModules = null;
    publicTraceHref = null;
    qrPreviewUnitId = null;
    qrError = null;
    qrGenerating = true;
    labelPreview = null;
    labelPreviewUnitId = null;
    barcodeProductCode = null;
    labelPreviewError = null;
    labelPreviewRetryable = true;
    barcodeError = null;
    labelCopies = '1';
    labelNotes = '';
    labelPrintError = null;
    labelPrintNeedsRefresh = false;
    labelPlacementMessage = null;
    labelPlacementError = null;
    labelPlacementConfirming = false;
    labelRecording = false;
    revokingTraceLinks = false;
    revocationConfirmOpen = false;
    revocationMessage = null;
    revocationError = null;
    labelPreviewLoading = canVerify;
    if (qrDialog && !qrDialog.open) {
      try {
        qrDialog.showModal();
      } catch {
        qrDialog.setAttribute('open', '');
      }
    }
    void (async () => {
      try {
        const capability = await inventoryApi.createTraceCapability(unit.id);
        if (sequence !== qrPreviewSequence) return;
        const traceHref = `/inventory/trace#${encodeURIComponent(capability.token)}`;
        publicTraceHref = traceHref;
        qrModules = QRCode.create(new URL(traceHref, window.location.origin).toString(), {
          errorCorrectionLevel: 'M'
        }).modules.size;
        const generatedQr = await QRCode.toDataURL(
          new URL(traceHref, window.location.origin).toString(),
          { width: 512, margin: 4, errorCorrectionLevel: 'M' }
        );
        if (sequence === qrPreviewSequence) {
          qrDataUrl = generatedQr;
          qrPreviewUnitId = unit.id;
        }
      } catch (cause) {
        if (sequence === qrPreviewSequence) {
          qrError =
            cause instanceof Error
              ? cause.message
              : 'No se pudo crear el enlace público de trazabilidad.';
        }
      } finally {
        if (sequence === qrPreviewSequence) qrGenerating = false;
      }
    })();

    if (canVerify) {
      void inventoryApi
        .previewInventoryLabel({ handling_unit_id: unit.id })
        .then((preview) => {
          if (previewSequence === labelPreviewSequence && preview.handling_unit_id === unit.id) {
            labelPreview = preview;
            labelPreviewUnitId = unit.id;
          }
        })
        .catch((cause) => {
          if (previewSequence === labelPreviewSequence) {
            labelPreviewError =
              cause instanceof Error
                ? cause.message
                : 'No se pudo cargar la ficha de impresión de esta unidad.';
            labelPreviewRetryable = !(
              cause instanceof HttpError && cause.code === 'inventory_label_receipt_lot_required'
            );
          }
        })
        .finally(() => {
          if (previewSequence === labelPreviewSequence) labelPreviewLoading = false;
        });
    }
  }

  function closeQrDialog() {
    qrPreviewSequence += 1;
    labelPreviewSequence += 1;
    dialogSessionSequence += 1;
    placementOperationSequence += 1;
    if (qrDialog?.open) qrDialog.close();
    dialogContextKey = null;
    selectedQrUnit = null;
    qrDataUrl = null;
    publicTraceHref = null;
    qrPreviewUnitId = null;
    qrError = null;
    labelPreview = null;
    labelPreviewUnitId = null;
    barcodeProductCode = null;
    labelRecording = false;
    labelPlacementConfirming = false;
    labelPreviewError = null;
    labelPreviewRetryable = true;
    barcodeError = null;
    barcodeReady = false;
    labelPlacementMessage = null;
    labelPlacementError = null;
    revocationConfirmOpen = false;
    onclose?.();
  }

  function handleNativeDialogClose() {
    if (!selectedQrUnit) return;
    qrPreviewSequence += 1;
    labelPreviewSequence += 1;
    dialogSessionSequence += 1;
    placementOperationSequence += 1;
    dialogContextKey = null;
    selectedQrUnit = null;
    qrDataUrl = null;
    publicTraceHref = null;
    qrPreviewUnitId = null;
    qrError = null;
    qrGenerating = false;
    labelPreview = null;
    labelPreviewUnitId = null;
    barcodeProductCode = null;
    labelRecording = false;
    labelPlacementConfirming = false;
    labelPreviewLoading = false;
    labelPreviewError = null;
    barcodeError = null;
    barcodeReady = false;
    labelPlacementMessage = null;
    labelPlacementError = null;
    revocationConfirmOpen = false;
    onclose?.();
  }

  function handleNativeDialogCancel(event: Event) {
    if (labelRecording) event.preventDefault();
    else if (revocationConfirmOpen && !revokingTraceLinks) {
      event.preventDefault();
      void cancelRevocationConfirmation();
    }
  }

  async function openRevocationConfirmation() {
    const session = dialogSessionSequence;
    revocationMessage = null;
    revocationError = null;
    revocationConfirmOpen = true;
    await tick();
    if (mounted && session === dialogSessionSequence)
      document.getElementById('qr-revoke-cancel')?.focus();
  }

  async function cancelRevocationConfirmation() {
    const session = dialogSessionSequence;
    revocationConfirmOpen = false;
    await tick();
    if (mounted && session === dialogSessionSequence)
      document.getElementById('qr-revoke-trigger')?.focus();
  }

  async function retryQrGeneration() {
    const unit = selectedQrUnit;
    const href = publicTraceHref;
    if (!unit || qrGenerating) return;
    if (!href) {
      void showHandlingUnitQr(unit);
      return;
    }

    const sequence = qrPreviewSequence;
    qrGenerating = true;
    qrError = null;
    qrDataUrl = null;
    try {
      qrModules = QRCode.create(new URL(href, window.location.origin).toString(), {
        errorCorrectionLevel: 'M'
      }).modules.size;
      const generatedQr = await QRCode.toDataURL(new URL(href, window.location.origin).toString(), {
        width: 512,
        margin: 4,
        errorCorrectionLevel: 'M'
      });
      if (sequence === qrPreviewSequence) qrDataUrl = generatedQr;
      if (sequence === qrPreviewSequence) qrPreviewUnitId = unit.id;
    } catch (cause) {
      if (sequence === qrPreviewSequence) {
        qrError =
          cause instanceof Error ? cause.message : 'No se pudo generar el código QR de la ficha.';
      }
    } finally {
      if (sequence === qrPreviewSequence) qrGenerating = false;
    }
  }

  async function retryLabelPreview() {
    if (!selectedQrUnit || !canVerify || labelPreviewLoading) return;
    const unit = selectedQrUnit;
    const sequence = ++labelPreviewSequence;
    labelPreviewLoading = true;
    labelPreviewError = null;
    barcodeError = null;
    try {
      const preview = await inventoryApi.previewInventoryLabel({ handling_unit_id: unit.id });
      if (sequence === labelPreviewSequence && preview.handling_unit_id === unit.id) {
        labelPreview = preview;
        labelPreviewUnitId = unit.id;
      }
    } catch (cause) {
      if (sequence === labelPreviewSequence) {
        labelPreviewError =
          cause instanceof Error
            ? cause.message
            : 'No se pudo cargar la ficha de impresión de esta unidad.';
        labelPreviewRetryable = !(
          cause instanceof HttpError && cause.code === 'inventory_label_receipt_lot_required'
        );
      }
    } finally {
      if (sequence === labelPreviewSequence) labelPreviewLoading = false;
    }
  }

  async function revokePublicTraceLinks() {
    const unit = selectedQrUnit;
    if (!unit || !canVerify || revokingTraceLinks || labelRecording) return;
    const session = dialogSessionSequence;
    const operationContext = contextKey;
    revokingTraceLinks = true;
    revocationError = null;
    try {
      const result = await inventoryApi.revokeTraceCapabilities(unit.id);
      if (
        !mounted ||
        session !== dialogSessionSequence ||
        selectedQrUnit?.id !== unit.id ||
        dialogContextKey !== operationContext ||
        contextKey !== operationContext
      ) {
        return;
      }
      publicTraceHref = null;
      qrDataUrl = null;
      revocationConfirmOpen = false;
      revocationMessage = result.revoked_count
        ? `Se invalidaron ${result.revoked_count} enlace(s) QR. Las etiquetas impresas con esos enlaces ya no abrirán la ficha.`
        : 'No había enlaces QR activos para invalidar.';
      await tick();
      if (mounted && session === dialogSessionSequence)
        document.getElementById('qr-revocation-result')?.focus();
    } catch (cause) {
      if (
        mounted &&
        session === dialogSessionSequence &&
        selectedQrUnit?.id === unit.id &&
        dialogContextKey === operationContext &&
        contextKey === operationContext
      ) {
        revocationError =
          cause instanceof Error ? cause.message : 'No se pudieron invalidar los enlaces QR.';
      }
    } finally {
      if (
        mounted &&
        session === dialogSessionSequence &&
        selectedQrUnit?.id === unit.id &&
        dialogContextKey === operationContext &&
        contextKey === operationContext
      ) {
        revokingTraceLinks = false;
      }
    }
  }

  function todayInElSalvador(): string {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    const part = (type: string) => parts.find((candidate) => candidate.type === type)?.value ?? '';
    return `${part('year')}-${part('month')}-${part('day')}`;
  }

  async function printHandlingUnitLabel() {
    const unit = selectedQrUnit;
    const preview = labelPreview;
    const layout = { ...labelLayout };
    const notes = labelNotes.trim() || null;
    const qr = qrDataUrl;
    const barcode = barcodeMarkup;
    const needsQr = layout.content !== 'barcode';
    const needsBarcode = layout.content !== 'qr';
    if (
      !unit ||
      !preview ||
      !canVerify ||
      labelRecording ||
      labelPlacementConfirming ||
      revokingTraceLinks
    )
      return;
    if (
      labelPreviewUnitId !== unit.id ||
      preview.handling_unit_id !== unit.id ||
      preview.handling_unit_code !== unit.code ||
      (needsQr && (qrPreviewUnitId !== unit.id || !qr)) ||
      (needsBarcode &&
        (!barcodeReady || !barcode || barcodeProductCode !== preview.product_internal_code))
    ) {
      labelPrintError = 'Actualiza la vista previa antes de imprimir esta unidad.';
      labelPrintNeedsRefresh = true;
      return;
    }
    const issue = labelLayoutIssue(layout, preview.product_internal_code, qrModules);
    if (issue || previewFitError || !labelPrintHtml || checkedPreviewHtml !== labelPrintHtml) {
      labelPrintError =
        issue ?? previewFitError ?? 'Espera a que termine de prepararse la vista previa.';
      return;
    }
    const copies = Number(labelCopies);
    if (labelCopiesIssue(labelCopies)) {
      document.getElementById('handling-unit-label-copies')?.focus();
      return;
    }
    const printWindow = window.open('', '_blank', 'width=520,height=640');
    if (!printWindow) {
      labelPrintError =
        'El navegador bloqueó la ventana de impresión. Permite ventanas emergentes e inténtalo otra vez.';
      return;
    }
    printWindow.opener = null;
    const session = dialogSessionSequence;
    const operationContext = contextKey;
    const isCurrent = () =>
      mounted &&
      session === dialogSessionSequence &&
      selectedQrUnit?.id === unit.id &&
      dialogContextKey === operationContext &&
      contextKey === operationContext;
    const reason: 'initial' | 'reprint' = preview.has_initial_print ? 'reprint' : 'initial';
    const printDate = todayInElSalvador();
    const attemptIdentity = JSON.stringify([unit.id, copies, reason, printDate, layout, notes]);
    const attempt = labelPrintAttempts.get(attemptIdentity) ?? {
      unitId: unit.id,
      key: crypto.randomUUID(),
      copies,
      reason,
      printDate,
      layout,
      notes
    };
    labelRecording = true;
    labelPrintError = null;
    labelPrintNeedsRefresh = false;
    let printRegistered = false;
    try {
      // Check the physical layout before recording an attempt or opening the print dialog.
      await prepareLabelPrintWindow(
        printWindow,
        buildLabelPrintDocument({ ...preview, notes }, layout, qr, barcode, copies)
      );
      if (!isCurrent()) {
        printWindow.close();
        return;
      }
      labelPrintAttempts.set(attemptIdentity, attempt);
      const recorded = await inventoryApi.recordInventoryLabelPrint({
        idempotency_key: attempt.key,
        handling_unit_id: unit.id,
        quantity_printed: copies,
        print_date: printDate,
        reason,
        layout: attempt.layout,
        notes: attempt.notes
      });
      printRegistered = true;
      if (!isCurrent()) {
        printWindow.close();
        return;
      }
      labelPrintAttempts.delete(attemptIdentity);
      const snapshot = labelDataFromSnapshot(recorded.label_snapshot);
      if (
        snapshot.handling_unit_code !== unit.code ||
        recorded.label_snapshot.label_revision !== preview.label_revision ||
        snapshot.quantity_base !== preview.quantity_base ||
        snapshot.product_internal_code !== preview.product_internal_code
      ) {
        labelPrintNeedsRefresh = true;
        throw new Error(
          'Los datos de la unidad cambiaron. Actualiza la vista previa antes de reimprimir.'
        );
      }
      labelPreview = {
        ...preview,
        ...snapshot,
        has_initial_print: true,
        print_count: preview.print_count + recorded.quantity_printed,
        label_print_id: recorded.id
      };
      labelPlacementMessage = null;
      labelPlacementError = null;
      // Print the data acknowledged by the server, retaining the selected paper and content.
      await prepareLabelPrintWindow(
        printWindow,
        buildLabelPrintDocument(snapshot, layout, qr, barcode, copies)
      );
      if (!isCurrent()) {
        printWindow.close();
        return;
      }
      printWindow.addEventListener('afterprint', () => printWindow.close(), { once: true });
      printWindow.focus();
      printWindow.print();
    } catch (cause) {
      printWindow.close();
      if (isCurrent()) {
        if (cause instanceof HttpError && cause.status === 409) labelPrintNeedsRefresh = true;
        const message =
          cause instanceof Error ? cause.message : 'No se pudo preparar la impresión.';
        labelPrintError = printRegistered
          ? `La solicitud quedó registrada, pero no se pudo abrir la impresión. ${message}`
          : message;
      }
    } finally {
      if (isCurrent()) labelRecording = false;
    }
  }
  async function confirmLabelPlacement() {
    const unit = selectedQrUnit;
    const preview = labelPreview;
    const printId = preview?.label_print_id;
    if (
      !unit ||
      !preview?.label_confirmation_required ||
      preview.label_confirmed ||
      !printId ||
      labelPlacementConfirming
    ) {
      return;
    }
    const attemptIdentity = JSON.stringify([unit.id, printId]);
    const attempt = labelConfirmationAttempts.get(attemptIdentity) ?? {
      unitId: unit.id,
      printId,
      key: crypto.randomUUID()
    };
    labelConfirmationAttempts.set(attemptIdentity, attempt);
    const session = dialogSessionSequence;
    const operation = ++placementOperationSequence;
    const operationContext = contextKey;
    const notifyParent = onconfirmed;
    labelPlacementConfirming = true;
    labelPlacementError = null;
    labelPlacementMessage = null;
    try {
      await inventoryApi.confirmInventoryLabelPlacement({
        idempotency_key: attempt.key,
        handling_unit_id: unit.id,
        handling_unit_code: preview.handling_unit_code ?? unit.code,
        label_print_id: printId
      });
      labelConfirmationAttempts.delete(attemptIdentity);
      if (mounted && contextKey === operationContext) notifyParent?.(unit.id);
      if (
        mounted &&
        session === dialogSessionSequence &&
        operation === placementOperationSequence &&
        selectedQrUnit?.id === unit.id &&
        dialogContextKey === operationContext &&
        contextKey === operationContext &&
        labelPreview?.handling_unit_id === unit.id &&
        labelPreview.label_print_id === printId
      ) {
        labelPreview = { ...preview, label_confirmed: true };
        labelPlacementMessage =
          'Colocación de etiqueta confirmada. La unidad sigue en cuarentena hasta asignarla a una ubicación válida.';
      }
    } catch (cause) {
      if (
        mounted &&
        session === dialogSessionSequence &&
        operation === placementOperationSequence &&
        selectedQrUnit?.id === unit.id &&
        dialogContextKey === operationContext &&
        contextKey === operationContext
      ) {
        labelPlacementError =
          cause instanceof Error
            ? cause.message
            : 'No se pudo confirmar la colocación de la etiqueta.';
      }
    } finally {
      if (
        mounted &&
        session === dialogSessionSequence &&
        operation === placementOperationSequence &&
        selectedQrUnit?.id === unit.id &&
        dialogContextKey === operationContext &&
        contextKey === operationContext
      ) {
        labelPlacementConfirming = false;
      }
    }
  }

  $effect(() => {
    const nextUnit = unit;
    const nextContextKey = contextKey;
    untrack(() => {
      if (nextUnit) {
        if (selectedQrUnit?.id !== nextUnit.id || dialogContextKey !== nextContextKey) {
          void showHandlingUnitQr(nextUnit);
        }
      } else if (selectedQrUnit) {
        closeQrDialog();
      }
    });
  });
</script>

<dialog
  bind:this={qrDialog}
  class="qr-dialog max-h-[90dvh] w-[min(94vw,64rem)] overflow-y-auto overscroll-contain rounded-2xl border border-border bg-surface p-0 text-foreground shadow-2xl backdrop:bg-black/70"
  aria-labelledby="handling-unit-qr-title"
  onclose={handleNativeDialogClose}
  oncancel={handleNativeDialogCancel}
  onclick={(event) => {
    if (event.target === qrDialog && !labelRecording) closeQrDialog();
  }}
>
  {#if selectedQrUnit}
    <div class="p-5 sm:p-6">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-primary">
            Etiqueta de inventario
          </p>
          <h2 id="handling-unit-qr-title" class="mt-1 break-all text-lg font-semibold">
            {selectedQrUnit.code}
          </h2>
          {#if canVerify && labelLayout.content === 'barcode'}
            <p class="mt-2 max-w-xl text-sm leading-6 text-foreground-muted">
              Code 128 identifica el producto mediante su código interno. El lote y la fecha
              permiten distinguir las recepciones.
            </p>
          {:else}
            <p class="mt-2 max-w-xl text-sm leading-6 text-foreground-muted">
              El QR permite consultar el origen y los movimientos de esta unidad.
            </p>
            <details class="mt-2 max-w-xl text-xs leading-5 text-foreground-muted">
              <summary
                class="cursor-pointer rounded text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                >Cómo abrir el QR</summary
              >
              <p class="mt-1">
                Usa la cámara del teléfono o «Abrir ficha»; no necesitas iniciar sesión. Un lector
                USB tipo teclado solo escribe la dirección. Los enlaces con localhost funcionan en
                esta computadora; para otros dispositivos se necesita una dirección de red
                accesible.
              </p>
            </details>
          {/if}
        </div>
        <button
          type="button"
          class="qr-label-close inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border text-foreground-muted hover:bg-surface-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="Cerrar etiqueta de inventario"
          disabled={labelRecording}
          onclick={closeQrDialog}
        >
          ×
        </button>
      </div>

      {#if !canVerify}
        <div
          class="mt-5 flex flex-col items-center rounded-xl border border-border bg-white p-5 text-center text-black"
        >
          {#if qrGenerating}
            <div class="grid h-52 w-52 place-items-center text-sm text-gray-500" role="status">
              Generando QR…
            </div>
          {:else if qrError}
            <div class="flex min-h-52 flex-col items-center justify-center gap-3 px-4 text-center">
              <p class="text-sm text-red-700" role="alert">{qrError}</p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={qrGenerating}
                onclick={() => void retryQrGeneration()}
              >
                Reintentar QR
              </Button>
            </div>
          {:else if qrDataUrl}
            <img class="h-52 w-52" src={qrDataUrl} alt={`Código QR para ${selectedQrUnit.code}`} />
            <p class="mt-3 font-mono text-base font-bold">{selectedQrUnit.code}</p>
            <p class="mt-1 text-xs">QR público · consulta de origen y movimientos</p>
          {/if}
        </div>
      {/if}

      {#if canVerify}
        <section
          class="mt-4 rounded-xl border border-primary/30 bg-primary/5 p-4"
          aria-label="Vista previa de etiqueta"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold text-foreground">Etiqueta para la unidad</h3>
              <p class="mt-1 text-xs text-foreground-muted">
                Elige el contenido, el papel y la cantidad de copias.
              </p>
            </div>
            {#if labelPreview}
              <Badge variant={labelPreview.has_initial_print ? 'neutral' : 'success'}>
                {labelPreview.has_initial_print
                  ? `${labelPreview.print_count} copias registradas`
                  : 'Sin impresión previa'}
              </Badge>
            {/if}
          </div>

          {#if labelPreviewLoading}
            <p class="mt-3 text-xs text-foreground-muted" role="status">
              Cargando datos de etiqueta…
            </p>
          {:else if labelPreviewError}
            <div
              class="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-foreground"
              role="alert"
            >
              <span>{labelPreviewError}</span>
              {#if labelPreviewRetryable}
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onclick={() => void retryLabelPreview()}
                >
                  Reintentar
                </Button>
              {/if}
            </div>
          {:else if labelPreview}
            <p class="mt-3 text-sm font-semibold text-foreground">{labelPreview.product_name}</p>
            <p class="mt-0.5 font-mono text-xs text-foreground-muted">
              {labelPreview.product_internal_code}
            </p>
            <div class="hidden" aria-hidden="true"><svg bind:this={barcodeSvg}></svg></div>
            <div class="mt-4 grid gap-5 lg:grid-cols-2 lg:items-start">
              <div class="min-w-0">
                <LabelPrintSettings
                  layout={labelLayout}
                  copies={labelCopies}
                  disabled={labelRecording || labelPlacementConfirming}
                  onlayout={(layout) => {
                    labelLayout = layout;
                    labelPrintError = null;
                  }}
                  oncopies={(copies) => {
                    labelCopies = copies;
                    labelPrintError = null;
                  }}
                />
                <label class="mt-3 block text-xs font-medium text-foreground" for="hu-label-notes">
                  Observaciones de la etiqueta <span class="text-foreground-muted">(opcional)</span>
                  <textarea
                    id="hu-label-notes"
                    class="mt-1 w-full rounded-lg border border-border-control bg-surface px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                    rows="2"
                    maxlength="160"
                    bind:value={labelNotes}
                    disabled={labelRecording || labelPlacementConfirming}
                    placeholder="Indicaciones de manejo, si las necesitas"
                  ></textarea>
                </label>
              </div>
              <div class="min-w-0">
                {#if layoutIssue || printDocument.error}
                  <p
                    class="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-foreground"
                    role="alert"
                  >
                    {layoutIssue ?? printDocument.error}
                  </p>
                {:else if labelLayout.content !== 'qr' && barcodeError}
                  <p class="mt-3 text-xs text-foreground" role="alert">
                    {barcodeError} Elige una viñeta QR.
                  </p>
                {:else if labelLayout.content !== 'barcode' && qrError}
                  <div
                    class="mt-3 space-y-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-foreground"
                    role="alert"
                  >
                    <p>{qrError}</p>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={qrGenerating || labelRecording}
                      onclick={() => void retryQrGeneration()}>Reintentar QR</Button
                    >
                  </div>
                {:else if labelLayout.content !== 'barcode' && !qrGenerating && !qrDataUrl}
                  <div class="mt-3 space-y-2 text-xs text-foreground-muted" role="status">
                    <p>Genera un nuevo QR para imprimir la ficha de esta unidad.</p>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={labelRecording}
                      onclick={() => void retryQrGeneration()}>Generar nuevo QR</Button
                    >
                  </div>
                {:else if labelPrintHtml}
                  <LabelPrintPreview
                    html={labelPrintHtml}
                    layout={labelLayout}
                    onissue={(issue, source) => {
                      if (source === labelPrintHtml) {
                        previewFitError = issue;
                        checkedPreviewHtml = source;
                      }
                    }}
                  />
                {:else}
                  <p class="mt-3 text-xs text-foreground-muted" role="status">
                    Preparando vista previa…
                  </p>
                {/if}
                {#if previewFitError}
                  <p
                    class="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-foreground"
                    role="alert"
                  >
                    {previewFitError}
                  </p>
                {/if}
                {#if labelPrintError}
                  <div
                    class="mt-3 space-y-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-foreground"
                    role="alert"
                  >
                    <p>{labelPrintError}</p>
                    {#if labelPrintNeedsRefresh}<Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={labelRecording}
                        onclick={() => {
                          labelPrintError = null;
                          void retryLabelPreview();
                        }}>Actualizar datos de etiqueta</Button
                      >{/if}
                  </div>
                {/if}
              </div>
            </div>
            <p class="mt-3 text-xs leading-5 text-foreground-muted">
              Se registra cada solicitud de impresión; no modifica existencias. Cerrar o cancelar la
              ventana de impresión no confirma que la etiqueta se haya colocado.
            </p>
            {#if labelPreview.label_confirmation_required}
              <div class="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3">
                {#if labelPreview.label_confirmed}
                  <p class="text-xs font-medium text-success" role="status">
                    Etiqueta vigente confirmada como colocada.
                  </p>
                {:else if labelPreview.label_print_id}
                  <p class="text-xs text-foreground-muted">
                    Confirma esto solo después de colocar físicamente la etiqueta de esta unidad. La
                    impresión registrada por sí sola no la libera.
                  </p>
                  <Button
                    class="mt-2"
                    type="button"
                    variant="secondary"
                    disabled={labelPlacementConfirming || labelRecording}
                    onclick={() => void confirmLabelPlacement()}
                  >
                    {labelPlacementConfirming ? 'Confirmando…' : 'Confirmar etiqueta colocada'}
                  </Button>
                {:else}
                  <p class="text-xs text-foreground-muted">
                    Primero registra la impresión de la etiqueta vigente; luego confirma su
                    colocación física.
                  </p>
                {/if}
              </div>
            {/if}
            {#if labelPlacementMessage}
              <p class="mt-2 text-xs text-success" role="status">{labelPlacementMessage}</p>
            {/if}
            {#if labelPlacementError}
              <p class="mt-2 text-xs text-foreground" role="alert">{labelPlacementError}</p>
            {/if}
          {/if}
        </section>
      {:else}
        <p
          class="mt-4 rounded-lg border border-border bg-surface-muted/25 px-3 py-2 text-xs text-foreground-muted"
        >
          Puedes consultar el QR. Para imprimir y registrar etiquetas se requiere el permiso de
          recepción de inventario.
        </p>
      {/if}

      <div
        class="sticky bottom-0 z-10 mt-5 flex flex-wrap justify-end gap-2 border-t border-border bg-surface py-3"
      >
        <button
          type="button"
          class="qr-label-close inline-flex h-11 items-center justify-center rounded-lg border border-border px-3 text-sm text-foreground hover:bg-surface-hover disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-primary"
          disabled={labelRecording}
          onclick={closeQrDialog}>Cerrar</button
        >
        {#if qrDataUrl}
          <a
            class="inline-flex h-11 items-center justify-center rounded-lg border border-border px-3 text-sm text-foreground hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-primary"
            href={publicTraceHref ?? '/inventory/trace'}
            target="_blank"
            rel="noopener">Abrir ficha</a
          >
        {/if}
        {#if canVerify}
          <Button
            type="button"
            class="min-h-11"
            disabled={!labelPreview ||
              labelPreviewLoading ||
              labelRecording ||
              labelPlacementConfirming ||
              revokingTraceLinks ||
              !labelPrintHtml ||
              checkedPreviewHtml !== labelPrintHtml ||
              Boolean(previewFitError) ||
              Boolean(labelCopiesIssue(labelCopies)) ||
              Boolean(layoutIssue)}
            onclick={() => void printHandlingUnitLabel()}
          >
            {labelRecording
              ? 'Preparando impresión…'
              : labelPreview?.has_initial_print
                ? 'Reimprimir etiqueta'
                : 'Imprimir etiqueta'}
          </Button>
        {/if}
      </div>
      {#if revocationMessage}
        <p
          id="qr-revocation-result"
          tabindex="-1"
          class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success"
          role="status"
        >
          {revocationMessage}
        </p>
      {/if}
      {#if revocationError}
        <p
          class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-foreground"
          role="alert"
        >
          {revocationError}
        </p>
      {/if}
      {#if canVerify && publicTraceHref}
        {#if revocationConfirmOpen}
          <div
            class="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4"
            role="group"
            aria-labelledby="qr-revoke-title"
            aria-describedby="qr-revoke-description"
          >
            <h3 id="qr-revoke-title" class="text-sm font-semibold text-foreground">
              ¿Invalidar todos los QR de esta unidad?
            </h3>
            <p id="qr-revoke-description" class="mt-1 text-xs text-foreground-muted">
              Las etiquetas anteriores dejarán de abrir la ficha. Tendrá que imprimir una nueva
              etiqueta para generar otro enlace.
            </p>
            <div class="mt-3 flex justify-end gap-2">
              <button
                id="qr-revoke-cancel"
                type="button"
                class="inline-flex h-11 items-center rounded-lg border border-border-control px-3 text-sm text-foreground hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-primary"
                disabled={revokingTraceLinks || labelRecording}
                onclick={() => void cancelRevocationConfirmation()}>Cancelar</button
              >
              <Button
                type="button"
                variant="danger"
                disabled={revokingTraceLinks || labelRecording}
                onclick={() => void revokePublicTraceLinks()}
              >
                {revokingTraceLinks ? 'Invalidando…' : 'Invalidar enlaces'}
              </Button>
            </div>
          </div>
        {:else}
          <div class="mt-3 flex justify-end">
            <button
              id="qr-revoke-trigger"
              type="button"
              class="inline-flex min-h-11 items-center rounded-lg px-2 text-xs text-foreground-muted hover:text-danger focus-visible:ring-2 focus-visible:ring-primary"
              disabled={labelRecording}
              onclick={() => void openRevocationConfirmation()}>Invalidar enlaces públicos</button
            >
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</dialog>
