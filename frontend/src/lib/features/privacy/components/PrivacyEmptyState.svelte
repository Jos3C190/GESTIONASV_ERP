<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    icon,
    message,
    detail = '',
    action
  }: { icon: string; message: string; detail?: string; action?: Snippet } = $props();
</script>

<div class="flex flex-col items-center gap-3 px-6 py-10 text-center">
  <span
    class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
    aria-hidden="true"
  >
    <svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d={icon} stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </span>
  <div>
    <p class="text-sm font-semibold text-foreground">{message}</p>
    {#if detail}<p class="mt-1 max-w-md text-sm text-foreground-muted">{detail}</p>{/if}
  </div>
  {#if action}{@render action()}{/if}
</div>
