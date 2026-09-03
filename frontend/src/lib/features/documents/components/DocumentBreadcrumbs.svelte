<script lang="ts">
  import type { DocumentBreadcrumbOut } from '$lib/api/client';

  interface Props {
    items: DocumentBreadcrumbOut[];
    current?: string;
  }

  let { items, current }: Props = $props();
</script>

<nav aria-label="Ruta documental" class="mb-4">
  <ol class="flex min-h-11 flex-wrap items-center gap-1 text-xs text-foreground-muted">
    {#each items as item, index (item.href)}
      <li class="flex items-center gap-1">
        {#if index > 0}
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
        {/if}
        <a href={item.href} class="min-h-11 rounded-md px-2 py-1.5 transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
          {item.label}
        </a>
      </li>
    {/each}
    {#if current}
      <li class="flex items-center gap-1">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
        <span aria-current="page" class="flex min-h-11 max-w-[260px] items-center truncate px-2 py-1.5 font-medium text-foreground">{current}</span>
      </li>
    {/if}
  </ol>
</nav>
