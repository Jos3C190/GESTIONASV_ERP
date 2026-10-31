<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import QRCode from 'qrcode';
  import JsBarcode from 'jsbarcode';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '../services';
  import type { HandlingUnit, InventoryLabelPreview } from '../types';

  interface Props {
    unit: HandlingUnit | null;
    canVerify?: boolean;
    contextKey?: string;
    onclose?: () => void;
    onconfirmed?: (handlingUnitId: string) => void;
  }

  const inputClass =
    'mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

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
  };
  let labelPrintAttempts = new Map<string, LabelPrintAttempt>();
  let qrPreviewSequence = 0;
  let labelPreviewSequence = 0;
  let dialogSessionSequence = 0;
  let placementOperationSequence = 0;
  let dialogContextKey = $state<string | null>(null);
  let mounted = true;

  onDestroy(() => {
    mounted = false;
    dialogSessionSequence += 1;
    placementOperationSequence += 1;
  });

  $effect(() => {
    const element = barcodeSvg;
    const preview = labelPreview;
    barcodeReady = false;
    barcodeProductCode = null;
    if (!element || !preview) return;
    try {
      JsBarcode(element, preview.product_internal_code, {
        format: 'CODE128',
        displayValue: true,
        height: 52,
        width: 2,
        margin: 4,
        fontSize: 14,
        textMargin: 2
      });
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
        const generatedQr = await QRCode.toDataURL(
          new URL(traceHref, window.location.origin).toString(),
          { width: 512, margin: 2, errorCorrectionLevel: 'M' }
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
      const generatedQr = await QRCode.toDataURL(new URL(href, window.location.origin).toString(), {
        width: 512,
        margin: 2,
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
    if (!unit || !canVerify || revokingTraceLinks) return;
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

  function escapeHtml(value: string): string {
    return value.replace(/[&<>"']/g, (character) => {
      const replacements: Record<string, string> = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      };
      return replacements[character] ?? character;
    });
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
    const barcode = barcodeSvg;
    if (!qrDataUrl || !unit || !preview || !barcode || !canVerify) return;
    if (
      qrPreviewUnitId !== unit.id ||
      labelPreviewUnitId !== unit.id ||
      preview.handling_unit_id !== unit.id ||
      preview.handling_unit_code !== unit.code ||
      barcodeProductCode !== preview.product_internal_code
    ) {
      labelPreviewError =
        'La etiqueta cambió de unidad. Actualice la vista previa antes de imprimir.';
      if (labelPreviewUnitId !== unit.id) void retryLabelPreview();
      if (qrPreviewUnitId !== unit.id) void retryQrGeneration();
      return;
    }
    const session = dialogSessionSequence;
    const operationContext = contextKey;
    const copies = Number(labelCopies);
    if (!Number.isInteger(copies) || copies < 1 || copies > 100) {
      labelPreviewError = 'Indique entre 1 y 100 copias.';
      return;
    }
    const printWindow = window.open('', '_blank', 'width=420,height=520');
    if (!printWindow) {
      labelPreviewError =
        'El navegador bloqueó la ventana de impresión. Permita ventanas emergentes e inténtelo otra vez.';
      return;
    }
    printWindow.opener = null;
    const reason: 'initial' | 'reprint' = preview.has_initial_print ? 'reprint' : 'initial';
    const printDate = todayInElSalvador();
    const attemptIdentity = JSON.stringify([unit.id, copies, reason, printDate]);
    const reusableAttempt = labelPrintAttempts.get(attemptIdentity);
    const attempt: LabelPrintAttempt = reusableAttempt
      ? reusableAttempt
      : { unitId: unit.id, key: crypto.randomUUID(), copies, reason, printDate };
    labelPrintAttempts.set(attemptIdentity, attempt);
    labelRecording = true;
    labelPreviewError = null;

    try {
      const recorded = await inventoryApi.recordInventoryLabelPrint({
        idempotency_key: attempt.key,
        handling_unit_id: unit.id,
        quantity_printed: copies,
        print_date: printDate,
        reason
      });
      if (
        !mounted ||
        session !== dialogSessionSequence ||
        selectedQrUnit?.id !== unit.id ||
        contextKey !== operationContext
      ) {
        printWindow.close();
        return;
      }
      labelPrintAttempts.delete(attemptIdentity);
      labelPreview = {
        ...preview,
        has_initial_print: true,
        print_count: preview.print_count + recorded.quantity_printed,
        label_print_id: recorded.id
      };
      labelPlacementMessage = null;
      labelPlacementError = null;

      const safeCode = escapeHtml(preview.product_internal_code);
      const safeName = escapeHtml(preview.product_name);
      const safeUnitCode = escapeHtml(unit.code);
      const safeReceiptLot = escapeHtml(preview.receipt_lot_code);
      const safeManufacturerLot = preview.manufacturer_lot_code
        ? escapeHtml(preview.manufacturer_lot_code)
        : 'No informado';
      const safeUnitSymbol = escapeHtml(preview.base_unit_symbol);
      const safePresentation = preview.presentation_equivalence
        ? `<p><strong>Presentación:</strong> ${escapeHtml(preview.presentation_equivalence)}</p>`
        : '';
      const safeExpiry = preview.expiry_date
        ? `<p><strong>Vence:</strong> ${escapeHtml(preview.expiry_date)}</p>`
        : '';
      const labelPages = Array.from(
        { length: copies },
        () => `
        <article class="label">
          <header><strong>GestionaSV · Inventario</strong><span>${safeUnitCode}</span></header>
          <h1>${safeName}</h1>
          <div class="barcode">${barcode.outerHTML}</div>
          <p class="sku">${safeCode}</p>
          <dl>
            <div><dt>Lote de recepción</dt><dd>${safeReceiptLot}</dd></div>
            <div><dt>Lote de fabricante</dt><dd>${safeManufacturerLot}</dd></div>
            <div><dt>Recibido</dt><dd>${escapeHtml(preview.received_on)}</dd></div>
            <div><dt>Cantidad HU</dt><dd>${escapeHtml(preview.quantity_base)} ${safeUnitSymbol}</dd></div>
          </dl>
          ${safePresentation}
          ${safeExpiry}
          <div class="trace"><img src="${qrDataUrl}" alt="QR público de trazabilidad" /><span><strong>QR público</strong><br />Origen y movimientos<br />Sin iniciar sesión</span></div>
        </article>`
      ).join('');

      printWindow.document.open();
      printWindow.document.write(`<!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Etiqueta ${safeCode} · ${safeUnitCode}</title>
            <style>
              @page { size: 100mm 125mm; margin: 0; }
              * { box-sizing: border-box; }
              body { margin: 0; color: #111; font-family: Arial, sans-serif; }
              .label { width: 100mm; min-height: 125mm; padding: 5mm; page-break-after: always; break-after: page; }
              .label:last-child { page-break-after: auto; break-after: auto; }
              header { display:flex; justify-content:space-between; gap:3mm; font-size:8pt; border-bottom:1px solid #aaa; padding-bottom:2mm; }
              header span { font-family:monospace; }
              h1 { font-size:12pt; line-height:1.2; margin:3mm 0 1mm; overflow-wrap:anywhere; }
              .barcode { display:flex; justify-content:center; min-height:19mm; }
              .barcode svg { max-width:88mm; max-height:22mm; }
              .sku { margin:0; text-align:center; font:700 9pt monospace; }
              dl { display:grid; grid-template-columns:1fr 1fr; gap:2mm; margin:3mm 0; }
              dl div { border:1px solid #bbb; padding:1.5mm; min-width:0; }
              dt { color:#555; font-size:7pt; }
              dd { overflow-wrap:anywhere; margin:1mm 0 0; font-size:8pt; font-weight:700; }
              p { font-size:8pt; margin:1mm 0; }
              .trace { display:flex; align-items:center; gap:3mm; border-top:1px solid #aaa; margin-top:3mm; padding-top:2mm; }
              .trace img { width:24mm; height:24mm; }
              .trace span { font-size:7pt; line-height:1.2; overflow-wrap:anywhere; }
            </style>
          </head>
          <body>${labelPages}</body>
        </html>`);
      printWindow.document.close();
      printWindow.addEventListener('afterprint', () => printWindow.close(), { once: true });
      printWindow.setTimeout(() => printWindow.print(), 250);
    } catch (cause) {
      printWindow.close();
      if (mounted && session === dialogSessionSequence && contextKey === operationContext) {
        labelPreviewError =
          cause instanceof Error
            ? cause.message
            : 'No se pudo registrar o preparar la impresión de la etiqueta.';
      }
    } finally {
      if (mounted && session === dialogSessionSequence && contextKey === operationContext) {
        labelRecording = false;
      }
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
  class="qr-dialog max-h-[90dvh] w-[min(94vw,30rem)] overflow-y-auto overscroll-contain rounded-2xl border border-border bg-surface p-0 text-foreground shadow-2xl backdrop:bg-black/70"
  aria-labelledby="handling-unit-qr-title"
  onclose={handleNativeDialogClose}
  oncancel={handleNativeDialogCancel}
  onclick={(event) => {
    if (event.target === qrDialog) closeQrDialog();
  }}
>
  {#if selectedQrUnit}
    <div class="p-5 sm:p-6">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-primary">
            Etiqueta de inventario
          </p>
          <h2 id="handling-unit-qr-title" class="mt-1 text-lg font-semibold">
            {selectedQrUnit.code}
          </h2>
          <p class="mt-2 max-w-xl text-sm leading-6 text-foreground-muted">
            El QR abre la ficha pública de origen y movimientos de esta unidad sin pedir inicio de
            sesión.
          </p>
          <p class="mt-1 max-w-xl text-xs leading-5 text-foreground-muted">
            Un lector USB tipo teclado solo escribe la dirección. Para abrirla, use la cámara del
            teléfono o «Abrir ficha» en este navegador. Si la aplicación usa localhost, solo podrá
            abrirse desde esta computadora; otros dispositivos necesitan una dirección de red
            accesible.
          </p>
        </div>
        <button
          type="button"
          class="qr-label-close inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border text-foreground-muted hover:bg-surface-hover hover:text-foreground"
          aria-label="Cerrar código QR"
          disabled={labelRecording}
          onclick={closeQrDialog}
        >
          ×
        </button>
      </div>

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

      {#if canVerify}
        <section
          class="mt-4 rounded-xl border border-primary/30 bg-primary/5 p-4"
          aria-label="Vista previa de etiqueta"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold text-foreground">Etiqueta para la unidad</h3>
              <p class="mt-1 text-xs text-foreground-muted">
                El código de barras contiene el código interno del producto; el QR enlaza a la ficha
                pública de trazabilidad.
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
              class="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
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
            <div class="mt-3 rounded-lg border border-gray-200 bg-white p-3 text-black">
              <div
                class="flex flex-wrap items-start justify-between gap-2 border-b border-gray-200 pb-2"
              >
                <div>
                  <p class="text-xs font-semibold uppercase tracking-wide">
                    GestionaSV · Inventario
                  </p>
                  <p class="mt-1 text-sm font-semibold">{labelPreview.product_name}</p>
                </div>
                <span class="font-mono text-xs">{selectedQrUnit.code}</span>
              </div>
              <svg
                bind:this={barcodeSvg}
                class="mx-auto mt-2 max-w-full"
                aria-label={`Código de barras ${labelPreview.product_internal_code}`}
              ></svg>
              {#if barcodeError}
                <p class="text-center text-xs text-red-700" role="alert">{barcodeError}</p>
              {/if}
              <p class="text-center font-mono text-xs font-semibold">
                {labelPreview.product_internal_code}
              </p>
              <dl class="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div class="rounded border border-gray-200 p-2">
                  <dt class="text-gray-600">Lote de recepción</dt>
                  <dd class="mt-0.5 break-all font-semibold">{labelPreview.receipt_lot_code}</dd>
                </div>
                <div class="rounded border border-gray-200 p-2">
                  <dt class="text-gray-600">Lote del fabricante</dt>
                  <dd class="mt-0.5 break-all font-semibold">
                    {labelPreview.manufacturer_lot_code ?? 'No informado'}
                  </dd>
                </div>
                <div class="rounded border border-gray-200 p-2">
                  <dt class="text-gray-600">Fecha de recepción</dt>
                  <dd class="mt-0.5 font-semibold">{labelPreview.received_on}</dd>
                </div>
                <div class="rounded border border-gray-200 p-2">
                  <dt class="text-gray-600">Cantidad de la unidad</dt>
                  <dd class="mt-0.5 font-semibold">
                    {labelPreview.quantity_base}
                    {labelPreview.base_unit_symbol}
                  </dd>
                </div>
                {#if labelPreview.presentation_equivalence}
                  <div class="col-span-2 rounded border border-gray-200 p-2">
                    <dt class="text-gray-600">Presentación y equivalencia</dt>
                    <dd class="mt-0.5 font-semibold">{labelPreview.presentation_equivalence}</dd>
                  </div>
                {/if}
                {#if labelPreview.expiry_date}
                  <div class="rounded border border-gray-200 p-2">
                    <dt class="text-gray-600">Vencimiento</dt>
                    <dd class="mt-0.5 font-semibold">{labelPreview.expiry_date}</dd>
                  </div>
                {/if}
              </dl>
            </div>
            <div class="mt-3 flex flex-wrap items-end justify-between gap-3">
              <label
                class="text-xs font-medium text-foreground-muted"
                for="handling-unit-label-copies"
              >
                Copias (1–100)
                <input
                  id="handling-unit-label-copies"
                  class={inputClass}
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  inputmode="numeric"
                  bind:value={labelCopies}
                  disabled={labelRecording}
                  oninput={() => {
                    labelPreviewError = null;
                  }}
                />
              </label>
              <span class="text-[11px] text-foreground-muted"
                >Se registra cada impresión; no modifica existencias.</span
              >
            </div>
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
              <p class="mt-2 text-xs text-danger" role="alert">{labelPlacementError}</p>
            {/if}
            {#if !barcodeReady && !barcodeError}
              <p class="mt-2 text-xs text-foreground-muted" role="status">
                Preparando código de barras…
              </p>
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

      <div class="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          class="qr-label-close inline-flex h-9 items-center justify-center rounded-lg border border-border px-3 text-sm text-foreground hover:bg-surface-hover"
          onclick={closeQrDialog}
        >
          Cerrar
        </button>
        {#if qrDataUrl}
          <a
            class="inline-flex h-9 items-center justify-center rounded-lg border border-border px-3 text-sm text-foreground hover:bg-surface-hover"
            href={publicTraceHref ?? '/inventory/trace'}
            target="_blank"
            rel="noopener"
          >
            Abrir ficha
          </a>
          {#if canVerify}
            <Button
              type="button"
              disabled={!labelPreview ||
                labelPreviewLoading ||
                labelRecording ||
                !barcodeReady ||
                Boolean(barcodeError)}
              onclick={() => void printHandlingUnitLabel()}
            >
              {labelRecording
                ? 'Registrando…'
                : labelPreview?.has_initial_print
                  ? 'Reimprimir etiqueta'
                  : 'Imprimir etiqueta'}
            </Button>
          {/if}
        {/if}
      </div>

      {#if revocationMessage}
        <p
          class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success"
          role="status"
        >
          {revocationMessage}
        </p>
      {/if}
      {#if revocationError}
        <p
          class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
          role="alert"
        >
          {revocationError}
        </p>
      {/if}
      {#if canVerify && publicTraceHref}
        {#if revocationConfirmOpen}
          <div
            class="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4"
            role="alertdialog"
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
                type="button"
                class="inline-flex h-9 items-center rounded-lg border border-border px-3 text-sm text-foreground hover:bg-surface-hover"
                disabled={revokingTraceLinks}
                onclick={() => (revocationConfirmOpen = false)}>Cancelar</button
              >
              <Button
                type="button"
                variant="danger"
                disabled={revokingTraceLinks}
                onclick={() => void revokePublicTraceLinks()}
              >
                {revokingTraceLinks ? 'Invalidando…' : 'Invalidar enlaces'}
              </Button>
            </div>
          </div>
        {:else}
          <div class="mt-3 flex justify-end">
            <button
              type="button"
              class="inline-flex h-8 items-center rounded-lg px-2 text-xs text-foreground-muted hover:text-danger"
              onclick={() => {
                revocationMessage = null;
                revocationError = null;
                revocationConfirmOpen = true;
              }}>Invalidar enlaces públicos</button
            >
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</dialog>
