<script lang="ts">
  /** Callout — banner informativo reutilizable con icono SVG, texto y botón de cerrar. */

  interface Props {
    variant?: 'info' | 'warning' | 'success';
    dismissible?: boolean;
    children: import('svelte').Snippet;
  }

  let { variant = 'info', dismissible = true, children }: Props = $props();

  let dismissed = $state(false);

  let styles = $derived.by(() => {
    const map = {
      info: { bg: 'rgb(var(--primary) / 0.04)', border: 'rgb(var(--primary) / 0.12)', icon: 'rgb(var(--primary))', iconBg: 'rgb(var(--primary) / 0.1)' },
      warning: { bg: 'rgb(var(--warning) / 0.04)', border: 'rgb(var(--warning) / 0.12)', icon: 'rgb(var(--warning))', iconBg: 'rgb(var(--warning) / 0.1)' },
      success: { bg: 'rgb(var(--success) / 0.04)', border: 'rgb(var(--success) / 0.12)', icon: 'rgb(var(--success))', iconBg: 'rgb(var(--success) / 0.1)' },
    };
    return map[variant];
  });
</script>

{#if !dismissed}
  <div class="mb-5 flex items-center gap-3 rounded-lg border px-3.5 py-2.5" style="background: {styles.bg}; border-color: {styles.border};">
    <div class="flex h-7 w-7 flex-none items-center justify-center rounded-full" style="background: {styles.iconBg};">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="color: {styles.icon};">
        <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
      </svg>
    </div>
    <div class="flex-1 text-[13px]">
      {@render children()}
    </div>
    {#if dismissible}
      <button type="button" onclick={() => (dismissed = true)} class="flex h-6 w-6 flex-none items-center justify-center rounded-md text-foreground-subtle transition-colors hover:bg-surface-hover hover:text-foreground" aria-label="Cerrar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
      </button>
    {/if}
  </div>
{/if}