<script lang="ts">
  /** Tabs — pestañas minimalistas con indicador animado estilo Vercel/Geist. */

  import type { Snippet } from 'svelte';

  export interface TabItem {
    id: string;
    label: string;
    icon?: string;
  }

  interface Props {
    items: TabItem[];
    active: string;
    sticky?: boolean;
  }

  let { items, active = $bindable(), sticky = false }: Props = $props();

  function setActive(id: string) {
    active = id;
    if (typeof window !== 'undefined') {
      history.replaceState(null, '', `#${id}`);
    }
  }

  $effect(() => {
    if (typeof window === 'undefined') return;
    const hash = window.location.hash.replace('#', '');
    if (hash && items.some((i) => i.id === hash)) {
      active = hash;
    }
    function onHashChange() {
      const h = window.location.hash.replace('#', '');
      if (h && items.some((i) => i.id === h)) active = h;
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  });
</script>

<div class="{sticky ? 'sticky top-0 z-50 bg-surface/95 backdrop-blur-md border-b border-border shadow-xs' : ''}">
  <div role="tablist" class="flex items-center gap-1 overflow-x-auto {sticky ? 'px-6 md:px-8 pt-3 pb-0 -mx-6 md:-mx-8 px-6 md:px-8' : 'border-b border-border'}">
    {#each items as item (item.id)}
      {@const isActive = active === item.id}
      <button
        type="button"
        role="tab"
        aria-selected={isActive}
        aria-controls="tab-panel-{item.id}"
        id="tab-{item.id}"
        onclick={() => setActive(item.id)}
        class="group relative flex flex-none items-center gap-2 px-4 py-2.5 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded-t-md
          {isActive ? 'text-foreground' : 'text-foreground-muted hover:text-foreground'}"
      >
        {#if item.icon}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="transition-colors {isActive ? 'text-primary' : 'text-foreground-subtle group-hover:text-foreground-muted'}" aria-hidden="true">
            {#if item.icon === 'building'}
              <path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4"/><path d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01"/>
            {:else if item.icon === 'map'}
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
            {:else if item.icon === 'gallery'}
              <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>
            {:else if item.icon === 'description'}
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>
            {:else if item.icon === 'overview'}
              <rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>
            {:else if item.icon === 'inventory'}
              <path d="M20 7l-8-4-8 4m16 0v10l-8 4m8-14L12 11M4 7v10l8 4m0-14L4 7m8 4v10"/>
            {:else if item.icon === 'operations'}
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
            {:else if item.icon === 'security'}
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            {:else if item.icon === 'history'}
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            {/if}
          </svg>
        {/if}
        <span>{item.label}</span>
        <span
          class="pointer-events-none absolute inset-x-3 bottom-0 h-0.5 rounded-full transition-all duration-300 ease-out
            {isActive ? 'bg-foreground opacity-100 scale-x-100' : 'bg-transparent opacity-0 scale-x-50'}"
        ></span>
      </button>
    {/each}
  </div>
</div>