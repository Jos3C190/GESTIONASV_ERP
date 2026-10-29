<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';

  interface Props {
    title: string;
    description: string;
    actionLabel?: string;
    onaction?: () => void;
    secondaryLabel?: string;
    onsecondary?: () => void;
  }

  let { title, description, actionLabel, onaction, secondaryLabel, onsecondary }: Props = $props();
</script>

<div
  class="rounded-2xl border border-dashed border-border bg-surface-elevated px-6 py-16 text-center"
>
  <div
    class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"
    aria-hidden="true"
  >
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
      <path d="M3.5 9h17" />
    </svg>
  </div>
  <h2 class="mt-4 text-sm font-semibold text-foreground">{title}</h2>
  <p class="mx-auto mt-1 max-w-md text-sm text-foreground-muted">{description}</p>
  {#if (actionLabel && onaction) || (secondaryLabel && onsecondary)}
    <div class="mt-5 flex flex-wrap justify-center gap-2">
      {#if actionLabel && onaction}
        <Button class="min-h-11" onclick={onaction}>{actionLabel}</Button>
      {/if}
      {#if secondaryLabel && onsecondary}
        <Button class="min-h-11" variant="secondary" onclick={onsecondary}>{secondaryLabel}</Button>
      {/if}
    </div>
  {/if}
</div>