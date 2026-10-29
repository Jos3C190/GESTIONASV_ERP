<script lang="ts">
  import { barcodeFormat } from '$lib/features/products/identifiers';
  import type { ProductIdentifierType } from '$lib/types/catalog';

  interface Props {
    identifierType: ProductIdentifierType;
    value: string;
    label?: string;
  }

  let { identifierType, value, label = 'Código de barras' }: Props = $props();
  let svg = $state<SVGSVGElement>();
  let renderError = $state(false);
  let format = $derived(barcodeFormat(identifierType, value));

  $effect(() => {
    const element = svg;
    const currentFormat = format;
    const currentValue =
      identifierType === 'internal' ? value.trim() : value.replace(/[^0-9X]/gi, '').toUpperCase();
    if (!element || !currentFormat || !currentValue) return;
    renderError = false;
    let cancelled = false;
    void import('jsbarcode')
      .then(({ default: JsBarcode }) => {
        if (cancelled) return;
        try {
          JsBarcode(element, currentValue, {
            format: currentFormat,
            displayValue: false,
            margin: 10,
            height: 54,
            width: 1.6,
            lineColor: '#000000',
            background: '#ffffff'
          });
        } catch {
          renderError = true;
        }
      })
      .catch(() => {
        if (!cancelled) renderError = true;
      });
    return () => {
      cancelled = true;
    };
  });
</script>

{#if format}
  <div
    class="overflow-x-auto rounded-lg border border-border bg-white px-3 py-3 text-black"
    aria-label={label}
  >
    <svg bind:this={svg} class:hidden={renderError} role="img" aria-label={`${label}: ${value}`}
    ></svg>
    {#if renderError}
      <p class="text-sm" role="status">
        No se pudo generar el código de barras. Revisa el identificador del producto.
      </p>
    {/if}
  </div>
{/if}
