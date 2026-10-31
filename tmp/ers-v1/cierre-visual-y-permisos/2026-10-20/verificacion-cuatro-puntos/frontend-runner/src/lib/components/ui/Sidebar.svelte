<script lang="ts">
  import { page } from '$app/state';
  import { NAV_GROUPS, type NavItem } from '$lib/navigation';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { api } from '$lib/api/client';
  import { clearPrivateQueryCache } from '$lib/services/query-client';

  interface Props {
    collapsed?: boolean;
    onNavigate?: () => void;
  }

  let { collapsed = false, onNavigate }: Props = $props();
  let switchingBranch = $state(false);
  let branchError = $state<string | null>(null);

  function isVisible(item: NavItem): boolean {
    if (item.requiredPermissions?.length) {
      return permissions.hasAnyPermission(item.requiredPermissions);
    }
    if (!item.requiredPermission) return true;
    return permissions.hasPermission(item.requiredPermission);
  }

  function isActive(route: string): boolean {
    return page.url.pathname === route ||
      (route === '/documents' && page.url.pathname.startsWith('/documents/'));
  }

  function handleClick() {
    onNavigate?.();
  }

  async function changeBranch(event: Event) {
    const value = (event.currentTarget as HTMLSelectElement).value;
    const branchId = value === '__all__' ? null : value;
    if (!company.id) return;
    switchingBranch = true;
    branchError = null;
    try {
      await api.operationalContext.select(company.id, branchId);
      await clearPrivateQueryCache();
      branch.select(branchId);
    } catch (error) {
      branchError = error instanceof Error ? error.message : 'No se pudo cambiar la sucursal.';
    } finally {
      switchingBranch = false;
    }
  }
</script>

<aside
  class="flex h-full flex-col border-r border-border bg-surface transition-all duration-200 {collapsed
    ? 'w-[52px]'
    : 'w-60'}"
  role="navigation"
  aria-label="Navegación principal"
>
  <!-- Sucursal operativa: la empresa se cambia desde la barra superior. -->
  <div class="relative flex min-h-14 flex-none items-center border-b border-border px-3 py-2">
    {#if collapsed}
      <div
        class="mx-auto flex h-7 w-7 flex-none items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary"
        title={branch.label}
      >
        {branch.active?.name.slice(0, 1).toUpperCase() ?? 'T'}
      </div>
    {:else}
      <div class="w-full min-w-0">
        <label
          for="operational-branch"
          class="mb-1 block truncate text-[10px] font-semibold uppercase tracking-wide text-foreground-muted"
          >Sucursal operativa</label
        >
        <div class="relative">
          <svg
            class="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-primary"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
            ><path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h.01M15 10h.01M9 14h.01M15 14h.01" /></svg
          >
          <select
            id="operational-branch"
            value={branch.id ?? '__all__'}
            onchange={changeBranch}
            disabled={switchingBranch || !branch.ready}
            class="h-8 w-full appearance-none truncate rounded-md border border-border bg-surface-muted pl-7 pr-7 text-xs font-semibold text-foreground outline-none transition-colors hover:bg-surface-hover focus:border-primary focus:shadow-glow disabled:opacity-60"
          >
            {#if branch.accessAllBranches}<option value="__all__">Todas las sucursales</option>{/if}
            {#each branch.branches as item (item.id)}
              <option value={item.id}>{item.name}</option>
            {/each}
          </select>
          <svg
            class="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-foreground-muted"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg
          >
        </div>
        {#if branchError}<p class="mt-1 truncate text-[10px] text-danger" title={branchError}>
            {branchError}
          </p>{/if}
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
          <p
            class="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-foreground-muted/90"
          >
            {group.label}
          </p>
        {/if}
        {#each group.items as item (item.route)}
          {#if isVisible(item)}
            <a
              href={item.route}
              onclick={handleClick}
              class="group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors duration-150 {isActive(
                item.route
              )
                ? 'bg-surface-hover font-medium text-foreground'
                : 'text-foreground/80 hover:bg-surface-hover/70 hover:text-foreground'} {collapsed
                ? 'justify-center'
                : ''}"
              title={collapsed ? item.label : ''}
              aria-current={isActive(item.route) ? 'page' : undefined}
            >
              {#if isActive(item.route) && !collapsed}
                <div
                  class="absolute left-0 top-1/2 h-4 -translate-y-1/2 w-0.5 rounded-r bg-foreground"
                ></div>
              {/if}
              <svg
                class="flex-none {isActive(item.route)
                  ? 'text-foreground'
                  : 'text-foreground-muted group-hover:text-foreground'}"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.85"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d={item.icon} />
              </svg>
              {#if !collapsed}
                <span class="truncate flex-1">{item.label}</span>
                {#if !item.implemented}
                  <span class="flex-none text-[10px] text-foreground-muted">·</span>
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
        <div
          class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-foreground/10 text-xs font-semibold text-foreground"
        >
          {session.user?.username?.[0]?.toUpperCase() ?? '?'}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs font-semibold text-foreground">
            {session.user?.username ?? '...'}
          </p>
          <p class="truncate text-[11px] font-medium text-foreground-muted">
            {session.user?.is_superuser ? 'Super Admin' : 'Usuario'}
          </p>
        </div>
      </div>
    </div>
  {/if}
</aside>
