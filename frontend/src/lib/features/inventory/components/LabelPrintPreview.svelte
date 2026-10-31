<script lang="ts">
  import {
    assertLabelDocumentFits,
    LABEL_CONTENT_NAMES,
    prepareLabelPrintWindow
  } from '../label-printing';
  import type { InventoryLabelLayout } from '../types';
  let {
    html,
    layout,
    onissue
  }: {
    html: string;
    layout: InventoryLabelLayout;
    onissue: (issue: string | null, source: string) => void;
  } = $props();
  let availableWidth = $state(0);
  let opening = $state(false);
  let openError = $state<string | null>(null);
  let rawWidth = $derived((layout.width_mm * 96) / 25.4);
  let rawHeight = $derived((layout.height_mm * 96) / 25.4);
  let scale = $derived(
    Math.max(
      0.1,
      Math.min(
        3,
        (availableWidth || 320) / rawWidth,
        (availableWidth > 400 ? 520 : 360) / rawHeight
      )
    )
  );

  async function openActualSize() {
    if (opening) return;
    openError = null;
    const target = window.open('', '_blank', 'width=800,height=800');
    if (!target) {
      openError = 'Permite ventanas emergentes para abrir la vista a tamaño real.';
      return;
    }
    target.opener = null;
    opening = true;
    try {
      await prepareLabelPrintWindow(target, html);
      target.focus();
    } catch (cause) {
      target.close();
      openError = cause instanceof Error ? cause.message : 'No se pudo abrir la vista previa.';
    } finally {
      opening = false;
    }
  }

  async function loaded(event: Event) {
    const iframe = event.currentTarget as HTMLIFrameElement;
    const source = html;
    const document = iframe.contentDocument;
    try {
      if (!document) throw new Error('No se pudo revisar el tamaño de impresión.');
      await document.fonts?.ready;
      await Promise.all(Array.from(document.images, (image) => image.decode()));
      if (html !== source || iframe.contentDocument !== document || !iframe.isConnected) return;
      assertLabelDocumentFits(document);
      onissue(null, source);
    } catch (cause) {
      if (html === source && iframe.contentDocument === document && iframe.isConnected) {
        onissue(
          cause instanceof Error ? cause.message : 'No se pudo preparar la vista previa.',
          source
        );
      }
    }
  }
</script>

<figure class="mt-4 rounded-xl border border-border bg-surface-muted/40 p-3">
  <figcaption class="mb-3 flex flex-wrap justify-between gap-1 text-xs text-foreground-muted">
    <span>Vista previa · {LABEL_CONTENT_NAMES[layout.content]}</span>
    <span class="font-mono text-foreground">{layout.width_mm} × {layout.height_mm} mm</span>
  </figcaption>
  <div bind:clientWidth={availableWidth} class="flex justify-center">
    <div
      class="relative shrink-0 bg-white shadow-sm"
      style:width={`${rawWidth * scale}px`}
      style:height={`${rawHeight * scale}px`}
    >
      <iframe
        title={`Vista previa de impresión ${layout.width_mm} por ${layout.height_mm} milímetros`}
        srcdoc={html}
        sandbox="allow-same-origin"
        onload={loaded}
        class="absolute left-0 top-0 origin-top-left border-0"
        scrolling="no"
        style:width={`${rawWidth}px`}
        style:height={`${rawHeight}px`}
        style:transform={`scale(${scale})`}
      ></iframe>
    </div>
  </div>
  <p class="mt-3 text-xs text-foreground-muted">
    Vista ajustada a la pantalla; el papel conserva las medidas indicadas.
  </p>
  <button
    type="button"
    class="mt-2 min-h-11 rounded-lg border border-border-control bg-surface px-3 py-2 text-sm text-foreground hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
    disabled={opening}
    onclick={() => void openActualSize()}
    >{opening ? 'Abriendo…' : 'Abrir vista a tamaño real'}</button
  >
  {#if openError}<p class="mt-2 text-xs text-danger" role="alert">{openError}</p>{/if}
</figure>
