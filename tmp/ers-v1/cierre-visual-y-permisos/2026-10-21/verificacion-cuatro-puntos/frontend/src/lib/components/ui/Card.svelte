<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    id?: string;
    title?: string;
    children: Snippet;
    class?: string;
  }

  let { id, title, children, class: className = '' }: Props = $props();
</script>

<div
  {id}
  class={`rounded-2xl border border-border bg-surface-elevated shadow-soft transition-all duration-200 hover-lift ${className}`}
>
  {#if title}
    <div class="border-b border-border px-5 py-3.5">
      <h3 class="text-sm font-semibold text-foreground">{title}</h3>
    </div>
  {/if}
  {@render children()}
</div>
