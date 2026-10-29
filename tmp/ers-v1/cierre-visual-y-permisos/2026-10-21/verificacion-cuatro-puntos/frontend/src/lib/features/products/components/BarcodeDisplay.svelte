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
    if (!svg || !format || !value.trim()) return;
    renderError = false;
    let cancelled = false;
    void import('jsbarcode')
      .then(({ default: JsBarcode }) => {
        if (cancelled || !svg || !format || !value.trim()) return;
        try {
          JsBarcode(
            svg,
            identifierType === 'internal'
              ? value.trim()
              : value.replace(/[^0-9X]/gi, '').toUpperCase(),
            {
              format,
              displayValue: false,
              margin: 0,
              height: 54,
              width: 1.6,
              lineColor: 'currentColor',
              background: 'transparent'
            }
          );
        } catch {
          renderError = true;
        }
      })
      .catch(() => {
        renderError = true;
      });
    return () => {
      cancelled = true;
    };
  });
</script>

{#if format && !renderError}
  <div
    class="rounded-lg border border-border bg-surface px-3 py-3 text-foreground"
    aria-label={label}
  >
    <svg bind:this={svg} role="img" aria-label={`${label}: ${value}`}></svg>
  </div>
{/if}
