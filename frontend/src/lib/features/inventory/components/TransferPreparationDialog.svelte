<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    open,
    busy = false,
    onclose,
    children
  }: {
    open: boolean;
    busy?: boolean;
    onclose: () => void;
    children: Snippet;
  } = $props();
  let dialog = $state<HTMLDialogElement | null>(null);

  $effect(() => {
    const element = dialog;
    if (!element) return;
    if (open && !element.open) {
      element.showModal();
      element.querySelector<HTMLElement>('#preparation-heading')?.focus();
    } else if (!open && element.open) {
      element.close();
    }
  });
</script>

<dialog
  bind:this={dialog}
  class="m-auto max-h-[90dvh] w-[min(96vw,64rem)] max-w-none overflow-y-auto overscroll-contain rounded-2xl border border-border bg-surface p-0 text-foreground shadow-floating backdrop:bg-black/70"
  aria-labelledby="preparation-heading"
  aria-describedby="preparation-description"
  aria-busy={busy}
  oncancel={(event) => {
    event.preventDefault();
    if (!busy) onclose();
  }}
  onclose={() => {
    if (open && !dialog?.open && !busy) onclose();
  }}
>
  {#if open}{@render children()}{/if}
</dialog>
