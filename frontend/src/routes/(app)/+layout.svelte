<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';
  import { session } from '$lib/stores/session.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { routeTitle } from '$lib/stores/route-titles';
  import { api } from '$lib/api/client';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/ui/Sidebar.svelte';
  import ThemeToggle from '$lib/components/ui/ThemeToggle.svelte';
  import UserMenu from '$lib/components/ui/UserMenu.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { clearPrivateQueryCache } from '$lib/services/query-client';

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();

  let sidebarCollapsed = $state(false);
  let mobileOpen = $state(false);
  let loading = $state(false);
  let searchInput = $state(globalSearch.query);
  let contextLoading = $state(!branch.ready);
  let contextError = $state<string | null>(null);
  let companyLogoFailed = $state(false);

  const SEARCHABLE_ROUTES = [
    '/users',
    '/employees',
    '/roles',
    '/departments',
    '/audit-log',
    '/branches',
    '/warehouses',
    '/warehouse-categories'
  ];

  let showSearch = $derived(SEARCHABLE_ROUTES.includes(page.url.pathname));
  let title = $derived(routeTitle(page.url.pathname));

  async function handleLogout() {
    loading = true;
    try {
      await api.auth.logout();
    } catch {
      /* ignore */
    } finally {
      await clearPrivateQueryCache();
      session.clear();
      permissions.clear();
      loading = false;
      window.location.href = '/login';
    }
  }

  function closeMobile() {
    mobileOpen = false;
  }

  function onSearchInput(e: Event) {
    const v = (e.target as HTMLInputElement).value;
    searchInput = v;
    globalSearch.setDebounced(v, 300);
  }

  async function refreshActiveCompany() {
    const activeId = company.id;
    if (!activeId) return;

    try {
      const current = await api.companies.get(activeId);
      if (company.id !== activeId) return;
      company.select({
        id: current.id,
        name: current.name,
        commercial_name: current.commercial_name,
        logo: current.logo
      });
    } catch {
      // El contexto guardado sigue siendo válido aunque la información visual no se pueda refrescar.
    }
  }

  $effect(() => {
    const _path = page.url.pathname;
    globalSearch.clear();
    searchInput = '';
  });

  $effect(() => {
    const _logo = company.active?.logo;
    companyLogoFailed = false;
  });

  onMount(async () => {
    void refreshActiveCompany();
    if (!company.id || branch.ready) {
      contextLoading = false;
      return;
    }
    try {
      const context = await api.operationalContext.get(company.id);
      branch.configure(context);
      if (!context.access_all_branches && context.branches.length === 0) {
        contextError = 'No tiene sucursales autorizadas en esta empresa.';
      }
    } catch (error) {
      contextError =
        error instanceof Error ? error.message : 'No se pudo cargar el contexto de sucursal.';
    } finally {
      contextLoading = false;
    }
  });
</script>

<div class="fixed inset-0 flex overflow-hidden bg-surface">
  <div class="hidden md:flex">
    <Sidebar collapsed={sidebarCollapsed} />
  </div>

  {#if mobileOpen}
    <div class="fixed inset-0 z-40 md:hidden">
      <div class="absolute inset-0 bg-black/50" onclick={closeMobile} role="presentation"></div>
      <div class="absolute left-0 top-0 h-full animate-slide-in">
        <Sidebar onNavigate={closeMobile} />
      </div>
    </div>
  {/if}

  <div class="flex flex-1 flex-col overflow-hidden">
    <header
      class="flex h-14 flex-none items-center justify-between gap-3 border-b border-border bg-surface px-4 md:px-6"
    >
      <!-- Left: menu + collapse + breadcrumb + search -->
      <div class="flex flex-1 items-center gap-2">
        <button
          type="button"
          onclick={() => (mobileOpen = true)}
          class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground md:hidden"
          aria-label="Abrir menú"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            ><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line
              x1="3"
              y1="18"
              x2="21"
              y2="18"
            /></svg
          >
        </button>
        <button
          type="button"
          onclick={() => (sidebarCollapsed = !sidebarCollapsed)}
          class="hidden h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground md:flex"
          aria-label="Colapsar sidebar"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            class="transition-transform duration-200 {sidebarCollapsed ? 'rotate-180' : ''}"
            ><polyline points="15 18 9 12 15 6" /></svg
          >
        </button>

        {#if title}
          <span class="hidden text-[15px] font-semibold text-foreground sm:block">{title}</span>
        {/if}

        {#if showSearch}
          <div class="relative ml-2 flex-1 max-w-xs">
            <svg
              class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-foreground-subtle"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg
            >
            <input
              type="text"
              value={searchInput}
              oninput={onSearchInput}
              placeholder="Buscar..."
              class="h-8 w-full rounded-md border border-border bg-surface-muted pl-8 pr-3 text-[13px] text-foreground placeholder:text-foreground-subtle focus:border-primary focus:bg-surface focus:shadow-glow focus:outline-none"
            />
          </div>
        {/if}
      </div>

      <!-- Right -->
      <div class="flex flex-none items-center gap-2">
        <button
          type="button"
          onclick={() => goto('/companies')}
          class="flex h-9 max-w-56 items-center gap-2 rounded-lg border border-border bg-surface-muted p-1.5 text-left transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary sm:px-2"
          aria-label="Cambiar empresa"
        >
          <span
            class="flex h-6 w-6 flex-none items-center justify-center overflow-hidden rounded-md bg-primary/10 text-xs font-bold text-primary"
          >
            {#if company.active?.logo && !companyLogoFailed}
              <img
                src={company.active.logo}
                alt=""
                class="h-full w-full object-contain"
                onerror={() => (companyLogoFailed = true)}
              />
            {:else}
              {company.active?.commercial_name.slice(0, 1).toUpperCase() ?? 'E'}
            {/if}
          </span>
          <span class="hidden truncate text-xs font-semibold text-foreground lg:block"
            >{company.active?.commercial_name ?? 'Seleccionar empresa'}</span
          >
          <svg
            class="hidden text-foreground-subtle sm:block"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"><path d="m9 18 6-6-6-6" /></svg
          >
        </button>
        <ThemeToggle />
        <UserMenu user={session.user} {loading} onLogout={handleLogout} />
      </div>
    </header>

    <main class="min-h-0 flex-1 overflow-y-auto" data-app-scroll-container>
      {#if contextLoading}
        <div class="p-6" aria-label="Cargando contexto operativo">
          <div class="h-24 rounded-xl border border-border skeleton"></div>
        </div>
      {:else if contextError}
        <div
          class="m-6 rounded-xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger"
          role="alert"
        >
          <p class="font-semibold">No se puede abrir el panel</p>
          <p class="mt-1">{contextError}</p>
          <div class="mt-4">
            <Button variant="secondary" size="sm" onclick={() => goto('/companies')}
              >Cambiar empresa</Button
            >
          </div>
        </div>
      {:else}
        {#key `${company.id ?? 'none'}:${branch.id ?? 'all'}`}
          {@render children()}
        {/key}
      {/if}
    </main>
  </div>
</div>
