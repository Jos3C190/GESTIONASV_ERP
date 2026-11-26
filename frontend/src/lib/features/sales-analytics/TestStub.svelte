<script lang="ts">
  /** Sustituto de gráficos en las pruebas (jsdom no mide el SVG). */
  let { label = '' }: { label?: string; data?: unknown; height?: number } = $props();
</script>

<div data-testid="chart">{label}</div>
