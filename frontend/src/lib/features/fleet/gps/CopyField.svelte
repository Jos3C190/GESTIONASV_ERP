<script lang="ts">
  import FleetIcon from '../FleetIcon.svelte';

  let { label, value, hint = '' }: { label: string; value: string; hint?: string } = $props();

  let copied = $state(false);
  let failed = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function copy() {
    clearTimeout(timer);
    failed = false;
    try {
      await navigator.clipboard.writeText(value);
      copied = true;
      timer = setTimeout(() => (copied = false), 2000);
    } catch {
      // Sin HTTPS el navegador puede negar el portapapeles; el valor sigue seleccionable.
      copied = false;
      failed = true;
    }
  }

  $effect(() => () => clearTimeout(timer));
</script>

<div class="field">
  <div class="text">
    <span class="label">{label}</span>
    <code>{value}</code>
    {#if hint}<span class="hint">{hint}</span>{/if}
    {#if failed}
      <span class="hint">No se pudo copiar. Selecciona el texto o escríbelo.</span>
    {/if}
  </div>
  <button type="button" class:copied onclick={copy} aria-label={`Copiar ${label}`}>
    <FleetIcon name={copied ? 'check' : 'copy'} size={16} />
    <span class="action">{copied ? 'Copiado' : 'Copiar'}</span>
  </button>
  <span class="sr-only" role="status"
    >{copied ? `${label} copiado` : failed ? 'No se pudo copiar' : ''}</span
  >
</div>

<style>
  .field {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
  }
  .text {
    display: flex;
    min-width: 0;
    flex: 1;
    flex-direction: column;
    gap: 2px;
  }
  .label,
  .hint {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  /* En pantalla angosta queda solo el ícono: así la dirección no se parte a la mitad. */
  .action {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  @media (min-width: 480px) {
    .action {
      position: static;
      width: auto;
      height: auto;
      clip-path: none;
    }
  }
  code {
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
    overflow-wrap: anywhere;
    user-select: all;
  }
  button {
    display: inline-flex;
    min-width: 44px;
    min-height: 44px;
    flex: none;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface));
    font-size: 14px;
    font-weight: 500;
  }
  button:hover {
    background: rgb(var(--surface-hover));
  }
  button:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  button.copied {
    border-color: rgb(var(--success) / 50%);
    color: rgb(var(--success));
  }
</style>
