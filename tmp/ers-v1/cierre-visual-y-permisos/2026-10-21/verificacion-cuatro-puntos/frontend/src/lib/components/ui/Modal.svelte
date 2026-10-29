<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    title: string;
    onclose?: () => void;
    children?: Snippet;
    footer?: Snippet;
    size?: 'sm' | 'md' | 'lg';
    inline?: boolean;
    preventClose?: boolean;
    mobileFullScreen?: boolean;
  }

  let { open, title, onclose, children, footer, size = 'md', inline = false, preventClose = false, mobileFullScreen = false }: Props = $props();
  let dialogEl = $state<HTMLDivElement | null>(null);
  let returnFocus = $state<HTMLElement | null>(null);

  let sizes: Record<string, string> = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl'
  };

  function focusableElements(): HTMLElement[] {
    if (!dialogEl) return [];
    return Array.from(
      dialogEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!open || inline) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      if (!preventClose) onclose?.();
      return;
    }
    if (e.key !== 'Tab') return;
    const focusable = focusableElements();
    if (!focusable.length) {
      e.preventDefault();
      dialogEl?.focus();
      return;
    }
    const first = focusable[0]!;
    const last = focusable[focusable.length - 1]!;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  $effect(() => {
    if (inline) return;
    if (open) {
      returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      requestAnimationFrame(() => {
        const first = dialogEl?.querySelector<HTMLElement>('[autofocus], input, button, [tabindex]:not([tabindex="-1"])');
        (first ?? dialogEl)?.focus();
      });
    } else if (returnFocus) {
      const focusTarget = returnFocus;
      returnFocus = null;
      requestAnimationFrame(() => focusTarget.focus());
    }
  });

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !preventClose) onclose?.();
  }

  function setGlobalChromeInert(next: boolean) {
    if (typeof document === 'undefined') return;
    const elements = Array.from(document.querySelectorAll<HTMLElement>('[data-app-global-chrome]'));
    for (const element of elements) {
      element.inert = next;
      if (next) element.setAttribute('aria-hidden', 'true');
      else element.removeAttribute('aria-hidden');
    }
  }

  $effect(() => {
    if (inline) return;
    if (open) {
      setGlobalChromeInert(true);
      return () => setGlobalChromeInert(false);
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if inline || open}
  <div
    class={inline
      ? 'w-full'
      : 'fixed inset-0 z-[1000] flex items-start justify-center overflow-y-auto p-4 pt-16'}
    style={inline ? undefined : 'background: rgb(2 6 23 / 0.6); backdrop-filter: blur(8px);'}
    class:modal-mobile-backdrop={mobileFullScreen}
    role="presentation"
    onclick={inline ? undefined : handleBackdropClick}
  >
    <div
      class="w-full {inline
        ? 'rounded-2xl border border-border bg-surface-elevated shadow-soft'
        : `${sizes[size]} animate-fade-scale rounded-3xl border border-border bg-surface-elevated shadow-floating`}"
      class:modal-mobile-fullscreen={mobileFullScreen}
      role={inline ? 'region' : 'dialog'}
      bind:this={dialogEl}
      aria-modal={inline ? undefined : 'true'}
      aria-labelledby="modal-title"
      tabindex="-1"
    >
      <div class="flex items-center justify-between border-b border-border px-6 py-4">
        <h2 id="modal-title" class="text-lg font-bold text-foreground">{title}</h2>
        <button
          type="button"
          onclick={() => { if (!preventClose) onclose?.(); }}
          disabled={preventClose}
          aria-disabled={preventClose}
          class="flex h-11 w-11 items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Cerrar"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            ><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg
          >
        </button>
      </div>
      <div class="px-6 py-5">
        {@render children?.()}
      </div>
      {#if footer}
        <div
          class="flex items-center justify-end gap-2 border-t border-border bg-surface-muted/50 px-6 py-3 rounded-b-3xl"
        >
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
<style>
  @media (max-width: 640px) {
    .modal-mobile-backdrop { padding: 0; }
    .modal-mobile-fullscreen {
      display: flex;
      min-height: 100dvh;
      max-height: 100dvh;
      flex-direction: column;
      border-radius: 0;
    }
    .modal-mobile-fullscreen > div:nth-child(2) {
      flex: 1 1 auto;
      overflow-y: auto;
    }
  }
</style>
