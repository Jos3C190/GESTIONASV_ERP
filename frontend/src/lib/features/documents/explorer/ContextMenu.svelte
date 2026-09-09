<script lang="ts">
  import { onMount } from 'svelte';
  import type { ExplorerItem } from './types';

  interface Props {
    item: ExplorerItem;
    x: number;
    y: number;
    canRename: boolean;
    canMove: boolean;
    canDelete: boolean;
    canRestore: boolean;
    onopen: () => void;
    onrename: () => void;
    onmove: () => void;
    ondelete: () => void;
    onrestore: () => void;
    onclose: () => void;
  }

  let {
    item,
    x,
    y,
    canRename,
    canMove,
    canDelete,
    canRestore,
    onopen,
    onrename,
    onmove,
    ondelete,
    onrestore,
    onclose
  }: Props = $props();

  let menuElement: HTMLDivElement | undefined;
  let firstAction: HTMLButtonElement | undefined;

  onMount(() => {
    firstAction?.focus();
  });

  function handleMenuKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onclose();
      return;
    }

    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const buttons = Array.from(menuElement?.querySelectorAll('button') ?? []) as HTMLButtonElement[];
    if (!buttons.length) return;
    event.preventDefault();
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? buttons.length - 1
          : (current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next]?.focus();
  }
</script>

<svelte:window
  onkeydown={(event) => event.key === 'Escape' && onclose()}
  onclick={(event) => {
    const target = event.target as HTMLElement;
    if (!target.closest('[data-explorer-context-menu]')) onclose();
  }}
/>

<div
  bind:this={menuElement}
  data-explorer-context-menu
  role="menu"
  tabindex="-1"
  aria-label="Acciones del elemento"
  onkeydown={handleMenuKeydown}
  class="fixed z-[1200] w-56 rounded-xl border border-border bg-surface-elevated p-1.5 shadow-floating"
  style={'left: min(' + x + 'px, calc(100vw - 14rem)); top: min(' + y + 'px, calc(100vh - 17rem));'}
>
  <button
    bind:this={firstAction}
    class="context-action"
    role="menuitem"
    onclick={() => {
      onopen();
      onclose();
    }}
  >
    {item.kind === 'folder' ? 'Abrir carpeta' : 'Abrir o descargar'}
  </button>
  {#if canRename}
    <button
      class="context-action"
      role="menuitem"
      onclick={() => {
        onrename();
        onclose();
      }}>Renombrar</button
    >
  {/if}
  {#if canMove}
    <button
      class="context-action"
      role="menuitem"
      onclick={() => {
        onmove();
        onclose();
      }}>Mover a…</button
    >
  {/if}
  <div class="my-1 border-t border-border"></div>
  {#if item.entry.deleted_at && canRestore}
    <button
      class="context-action text-success"
      role="menuitem"
      onclick={() => {
        onrestore();
        onclose();
      }}>Restaurar</button
    >
  {:else if canDelete}
    <button
      class="context-action text-danger"
      role="menuitem"
      onclick={() => {
        ondelete();
        onclose();
      }}>Enviar a papelera</button
    >
  {/if}
</div>

<style>
  .context-action {
    display: flex;
    min-height: 40px;
    width: 100%;
    align-items: center;
    border-radius: 0.625rem;
    padding: 0 0.75rem;
    text-align: left;
    font-size: 0.8125rem;
    color: rgb(var(--foreground));
  }
  .context-action:hover,
  .context-action:focus-visible {
    background: rgb(var(--surface-hover));
    outline: none;
  }
</style>