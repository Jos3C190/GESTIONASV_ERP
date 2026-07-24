<script lang="ts">
  /**
   * KebabMenu — Componente de menú contextual de 3 puntos (⋮) estilo Geist.
   * Posicionado vía portal fijo antirecorte con detección de clics externos.
   */

  export interface KebabItem {
    id: string;
    label: string;
    icon?: 'detail' | 'edit' | 'delete' | 'custom';
    variant?: 'default' | 'danger';
    onClick: () => void;
  }

  interface Props {
    items: KebabItem[];
    ariaLabel?: string;
    orientation?: 'vertical' | 'horizontal';
  }

  let { items, ariaLabel = 'Más opciones', orientation = 'vertical' }: Props = $props();

  let isOpen = $state(false);
  let menuPos = $state<{ top: number; left: number }>({ top: 0, left: 0 });
  let triggerBtn = $state<HTMLElement | null>(null);
  let menuEl = $state<HTMLElement | null>(null);

  function toggleMenu(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();

    if (isOpen) {
      isOpen = false;
      return;
    }

    const button = e.currentTarget as HTMLElement;
    triggerBtn = button;
    const rect = button.getBoundingClientRect();
    const dropdownHeight = items.length * 36 + 16;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < dropdownHeight + 12;

    menuPos = {
      top: openUp ? rect.top - dropdownHeight - 4 : rect.bottom + 4,
      left: rect.right - 150,
    };
    isOpen = true;
  }

  function closeMenu() {
    isOpen = false;
  }

  function handleItemClick(e: MouseEvent, item: KebabItem) {
    e.preventDefault();
    e.stopPropagation();
    closeMenu();
    item.onClick();
  }

  $effect(() => {
    if (!isOpen) return;

    function handlePointerDown(e: MouseEvent) {
      const target = e.target as Node | null;
      if (!target) return;
      if (menuEl && menuEl.contains(target)) return;
      if (triggerBtn && triggerBtn.contains(target)) return;
      closeMenu();
    }

    function handleKeydown(e: KeyboardEvent) {
      if (e.key === 'Escape') closeMenu();
    }

    const timer = setTimeout(() => {
      document.addEventListener('pointerdown', handlePointerDown);
      window.addEventListener('scroll', closeMenu, true);
    }, 0);

    window.addEventListener('resize', closeMenu);
    window.addEventListener('keydown', handleKeydown);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('scroll', closeMenu, true);
      window.removeEventListener('resize', closeMenu);
      window.removeEventListener('keydown', handleKeydown);
    };
  });

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return {
      destroy() {
        if (node.parentNode) {
          node.parentNode.removeChild(node);
        }
      }
    };
  }
</script>

<div class="inline-block" onclick={(e) => e.stopPropagation()}>
  <button
    type="button"
    bind:this={triggerBtn}
    onclick={toggleMenu}
    class="flex h-7 w-7 items-center justify-center rounded-lg text-foreground-subtle transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary {isOpen ? 'bg-surface-hover text-foreground' : ''}"
    aria-label={ariaLabel}
    aria-haspopup="true"
    aria-expanded={isOpen}
  >
    {#if orientation === 'vertical'}
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>
      </svg>
    {:else}
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
      </svg>
    {/if}
  </button>
</div>

{#if isOpen}
  <div
    use:portal
    bind:this={menuEl}
    class="fixed z-50 min-w-[150px] animate-fade-scale rounded-xl border border-border bg-surface-elevated p-1 shadow-lifted text-left"
    style="top: {menuPos.top}px; left: {menuPos.left}px;"
    role="menu"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
  >
    {#each items as item (item.id)}
      <button
        type="button"
        onclick={(e) => handleItemClick(e, item)}
        class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors {item.variant === 'danger' ? 'text-danger hover:bg-danger/10' : 'text-foreground hover:bg-surface-hover'}"
        role="menuitem"
      >
        {#if item.icon === 'detail'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary flex-none">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        {:else if item.icon === 'edit'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-foreground-muted flex-none">
            <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
          </svg>
        {:else if item.icon === 'delete'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="flex-none">
            <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
          </svg>
        {/if}
        {item.label}
      </button>
    {/each}
  </div>
{/if}
