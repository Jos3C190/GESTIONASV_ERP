<script lang="ts">
  import { page } from '$app/state';
  import { NAV_GROUPS, type NavItem } from '$lib/navigation';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { session } from '$lib/stores/session.svelte';

  interface Props {
    collapsed?: boolean;
    onNavigate?: () => void;
  }

  let { collapsed = false, onNavigate }: Props = $props();

  // MOCKUP: sucursales — reemplazar por llamada a la API cuando exista el módulo
  const sucursales = [
    { id: 'all', name: 'Todas' },
    { id: 'central', name: 'Matriz Central' },
    { id: 'norte', name: 'Sucursal Norte' },
    { id: 'sur', name: 'Sucursal Sur' },
    { id: 'occidente', name: 'Sucursal Occidente' },
  ];
  let sucursalSel = $state('all');
  let sucursalOpen = $state(false);
  let sucursalWrap: HTMLElement | null = $state(null);

  // Cerrar el dropdown al hacer clic fuera
  $effect(() => {
    if (!sucursalOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (sucursalWrap && !sucursalWrap.contains(e.target as Node)) {
        sucursalOpen = false;
      }
    }
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  });

  function isVisible(item: NavItem): boolean {
    if (!item.requiredPermission) return true;
    return permissions.hasPermission(item.requiredPermission);
  }

  function isActive(route: string): boolean {
    return page.url.pathname === route;
  }

  function handleClick() {
    onNavigate?.();
  }
</script>

<aside
  class="flex h-full flex-col border-r border-border bg-surface transition-all duration-200 {collapsed ? 'w-[52px]' : 'w-60'}"
  role="navigation"
  aria-label="Navegación principal"
>
  <!-- Brand + sucursal selector -->
  <div class="flex h-14 flex-none items-center gap-2.5 border-b border-border px-4 {collapsed ? 'justify-center' : ''}">
    <div class="flex h-7 w-7 flex-none items-center justify-center rounded-md bg-foreground text-surface">
      <span class="text-xs font-bold">E</span>
    </div>
    {#if !collapsed}
      <div class="flex min-w-0 flex-1 items-center justify-between gap-2">
        <span class="truncate text-sm font-semibold text-foreground">ERP System</span>
        <!-- Sucursal selector — MOCKUP: sera conectado a la API cuando exista el modulo de sucursales -->
        <div class="relative" bind:this={ sucursalWrap }>
          <button
            type="button"
            onclick={() => (sucursalOpen = !sucursalOpen)}
            class="flex items-center gap-1.5 rounded-md border border-border bg-surface-muted px-2 py-1 text-[11px] font-medium text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:shadow-glow"
            aria-label="Cambiar sucursal"
            aria-expanded={sucursalOpen}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none text-foreground-subtle">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
            </svg>
            <span class="truncate max-w-[70px]">{sucursales.find(s => s.id === sucursalSel)?.name ?? '—'}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none text-foreground-subtle transition-transform {sucursalOpen ? 'rotate-180' : ''}"><polyline points="6 9 12 15 18 9" /></svg>
          </button>

          {#if sucursalOpen}
            <div class="absolute right-0 top-full z-50 mt-1 w-48 animate-fade-scale rounded-lg border border-border bg-surface-elevated shadow-lifted">
              <p class="px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-foreground-subtle border-b border-border">Sucursales</p>
              {#each sucursales as s (s.id)}
                <button
                  type="button"
                  onclick={() => { sucursalSel = s.id; sucursalOpen = false; }}
                  class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] transition-colors hover:bg-surface-hover {sucursalSel === s.id ? 'text-primary font-medium' : 'text-foreground'}"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none {sucursalSel === s.id ? 'opacity-100' : 'opacity-0'}"><polyline points="20 6 9 17 4 12" /></svg>
                  <span class="flex-1 truncate">{s.name}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Nav -->
  <nav class="flex-1 overflow-y-auto py-2 {collapsed ? 'px-1.5' : 'px-2'}">
    {#each NAV_GROUPS as group, gi (group.label)}
      {#if group.items.some(isVisible)}
        {#if collapsed}
          {#if gi > 0}<div class="mx-1 my-2 border-t border-border"></div>{/if}
        {:else}
          <p class="px-3 pt-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">{group.label}</p>
        {/if}
        {#each group.items as item (item.route)}
          {#if isVisible(item)}
            <a
              href={item.route}
              onclick={handleClick}
              class="group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors duration-150 {isActive(item.route) ? 'bg-surface-hover font-medium text-foreground' : 'text-foreground-muted hover:bg-surface-hover/60 hover:text-foreground'} {collapsed ? 'justify-center' : ''}"
              title={collapsed ? item.label : ''}
              aria-current={isActive(item.route) ? 'page' : undefined}
            >
              {#if isActive(item.route) && !collapsed}
                <div class="absolute left-0 top-1/2 h-4 -translate-y-1/2 w-0.5 rounded-r bg-foreground"></div>
              {/if}
              <svg class="flex-none {isActive(item.route) ? 'text-foreground' : 'text-foreground-subtle'}" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d={item.icon} />
              </svg>
              {#if !collapsed}
                <span class="truncate flex-1">{item.label}</span>
                {#if !item.implemented}
                  <span class="flex-none text-[10px] text-foreground-subtle">·</span>
                {/if}
              {/if}
            </a>
          {/if}
        {/each}
      {/if}
    {/each}
  </nav>

  <!-- User -->
  {#if !collapsed}
    <div class="flex-none border-t border-border px-3 py-2.5">
      <div class="flex items-center gap-2.5 rounded-md px-1.5 py-1">
        <div class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-foreground-muted/15 text-xs font-medium text-foreground-muted">
          {session.user?.username?.[0]?.toUpperCase() ?? '?'}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs font-medium text-foreground">{session.user?.username ?? '...'}</p>
          <p class="truncate text-[11px] text-foreground-subtle">{session.user?.is_superuser ? 'Super Admin' : 'Usuario'}</p>
        </div>
      </div>
    </div>
  {/if}
</aside>