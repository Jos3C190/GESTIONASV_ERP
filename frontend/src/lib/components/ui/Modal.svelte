<script lang="ts">
  import type { Snippet } from 'svelte';
  import Button from './Button.svelte';

  interface Props {
    open: boolean;
    title: string;
    onclose?: () => void;
    children: Snippet;
    footer?: Snippet;
    size?: 'sm' | 'md' | 'lg';
  }

  let { open, title, onclose, children, footer, size = 'md' }: Props = $props();

  let sizes: Record<string, string> = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl'
  };

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      e.preventDefault();
      onclose?.();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) onclose?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-[1000] flex items-start justify-center overflow-y-auto p-4 pt-16"
    style="background: rgb(2 6 23 / 0.6); backdrop-filter: blur(8px);"
    role="presentation"
    onclick={handleBackdropClick}
  >
    <div
      class="w-full {sizes[size]} animate-fade-scale rounded-3xl border border-border bg-surface-elevated shadow-floating"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabindex="-1"
    >
      <div class="flex items-center justify-between border-b border-border px-6 py-4">
        <h2 class="text-lg font-bold text-foreground">{title}</h2>
        <button
          type="button"
          onclick={() => onclose?.()}
          class="flex h-8 w-8 items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground"
          aria-label="Cerrar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
      </div>
      <div class="px-6 py-5">
        {@render children()}
      </div>
      {#if footer}
        <div class="flex items-center justify-end gap-2 border-t border-border bg-surface-muted/50 px-6 py-3 rounded-b-3xl">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
