<script lang="ts">
  /**
   * KebabMenu — Componente de menú contextual de 3 puntos (⋮) estilo Geist.
   * Posicionado vía portal fijo antirecorte con detección de clics externos.
   */

  export interface KebabItem {
    id: string;
    label: string;
    icon?: 'detail' | 'edit' | 'delete' | 'link' | 'unlink' | 'key' | 'unlock' | 'power' | 'custom';
    variant?: 'default' | 'danger';
    onClick: () => void;
  }

  interface Props {
    items: KebabItem[];
    ariaLabel?: string;
    orientation?: 'vertical' | 'horizontal';
    triggerClass?: string;
  }

  let {
    items,
    ariaLabel = 'Más opciones',
    orientation = 'vertical',
    triggerClass = ''
  }: Props = $props();

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
      left: rect.right - 150
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

<div class="inline-block">
  <button
    type="button"
    bind:this={triggerBtn}
    onclick={toggleMenu}
    class="flex h-7 w-7 items-center justify-center rounded-lg text-foreground-subtle transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary {isOpen
      ? 'bg-surface-hover text-foreground'
      : ''} {triggerClass}"
    aria-label={ariaLabel}
    aria-haspopup="true"
    aria-expanded={isOpen}
  >
    {#if orientation === 'vertical'}
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="12" r="1" /><circle cx="12" cy="5" r="1" /><circle
          cx="12"
          cy="19"
          r="1"
        />
      </svg>
    {:else}
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle
          cx="5"
          cy="12"
          r="1"
        />
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
  >
    {#each items as item (item.id)}
      <button
        type="button"
        onclick={(e) => handleItemClick(e, item)}
        class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors {item.variant ===
        'danger'
          ? 'text-danger hover:bg-danger/10'
          : 'text-foreground hover:bg-surface-hover'}"
        role="menuitem"
      >
        {#if item.icon === 'detail'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class="text-primary flex-none"
          >
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle
              cx="12"
              cy="12"
              r="3"
            />
          </svg>
        {:else if item.icon === 'edit'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class="text-foreground-muted flex-none"
          >
            <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
          </svg>
        {:else if item.icon === 'delete'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class="flex-none"
          >
            <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path
              d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"
            />
          </svg>
        {:else if item.icon === 'link'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-success flex-none"
          >
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path
              d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
            />
          </svg>
        {:else if item.icon === 'unlink'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-warning flex-none"
          >
            <path d="M9 17H7A5 5 0 0 1 7 7h2" /><path d="M15 7h2a5 5 0 0 1 0 10h-2" /><line
              x1="8"
              y1="12"
              x2="16"
              y2="12"
            />
          </svg>
        {:else if item.icon === 'key'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-warning flex-none"
          >
            <path
              d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4.1a1 1 0 0 0-1.4 0l-2.1 2.1a1 1 0 0 0 0 1.3Z"
            /><path d="m15.5 7.5-3 3" /><circle cx="7.5" cy="16.5" r="4.5" />
          </svg>
        {:else if item.icon === 'unlock'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-success flex-none"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path
              d="M7 11V7a5 5 0 0 1 9.9-1"
            />
          </svg>
        {:else if item.icon === 'power'}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="flex-none"
          >
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0" /><line x1="12" y1="2" x2="12" y2="12" />
          </svg>
        {/if}
        {item.label}
      </button>
    {/each}
  </div>
{/if}
