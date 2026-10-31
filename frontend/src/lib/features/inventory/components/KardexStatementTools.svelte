<script lang="ts">
  import ReportDownloads from '$lib/components/ui/ReportDownloads.svelte';
  import type { KardexContext } from '../kardex';
  let {
    context,
    path,
    code,
    scope
  }: { context?: KardexContext | null; path: string; code: string; scope: string } = $props();
</script>

<section
  aria-label="Identificación y reportes de la consulta"
  class="space-y-4 rounded-lg border border-border bg-surface-muted/20 p-4"
>
  {#if context}<div class="grid gap-3 text-sm sm:grid-cols-2">
      <div>
        <p class="font-semibold text-foreground">{context.company_name}</p>
        <p class="mt-1 text-xs text-foreground-muted">
          NIT: {context.nit || 'No informado'} · NRC: {context.nrc || 'No informado'}
        </p>
      </div>
      <div>
        <p class="font-medium text-foreground">{context.product_name || 'Todos los productos'}</p>
        <p class="mt-1 text-xs text-foreground-muted">
          {context.sku ? `${context.sku} · ` : ''}{context.base_unit_symbol
            ? `Unidad: ${context.base_unit_symbol}`
            : 'Cada producto conserva su unidad'}
        </p>
      </div>
    </div>{/if}
  <p class="text-xs text-foreground-muted">{scope}</p>
  <ReportDownloads
    {path}
    {code}
    description="Incluye todas las filas del resultado con los filtros aplicados. Máximo 5,000 filas por archivo."
  />
</section>
