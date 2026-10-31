<script lang="ts">
  import { untrack } from 'svelte';
  import type { InventoryLabelLayout } from '$lib/features/inventory/types';
  let {
    html,
    layout,
    onissue
  }: {
    html: string;
    layout: InventoryLabelLayout;
    onissue: (issue: string | null, source: string) => void;
  } = $props();
  // The DOM emulator has no physical millimetres. Browser QA covers fit checking.
  $effect(() => {
    const current = html;
    queueMicrotask(() => untrack(() => onissue(null, current)));
  });
</script>

<iframe
  title={`Vista previa de impresión ${layout.width_mm} por ${layout.height_mm} milímetros`}
  srcdoc={html}
  onload={() => onissue(null, html)}
  style="width:100%;height:360px;border:0"
  sandbox="allow-same-origin"
></iframe>
