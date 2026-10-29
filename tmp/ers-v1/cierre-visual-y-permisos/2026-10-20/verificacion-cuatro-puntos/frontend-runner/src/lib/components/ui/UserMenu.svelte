<script lang="ts">
  import { tick } from 'svelte';
  import type { CurrentUser } from '$lib/stores/session.svelte';
  import Avatar from './Avatar.svelte';

  interface Props {
    user: CurrentUser | null;
    loading?: boolean;
    onLogout: () => void | Promise<void>;
  }

  let { user, loading = false, onLogout }: Props = $props();

  let open = $state(false);
  let root = $state<HTMLElement | null>(null);
  let trigger = $state<HTMLButtonElement | null>(null);
  let menu = $state<HTMLElement | null>(null);

  let displayName = $derived(user?.username || 'Usuario');
  let initials = $derived.by(() => {
    const parts = displayName.trim().split(/\s+/).filter(Boolean);
    if (parts.length > 1) return `${parts[0]?.[0] ?? ''}${parts.at(-1)?.[0] ?? ''}`;
    return displayName.slice(0, 2);
  });
  let accountType = $derived(user?.is_superuser ? 'Superadministrador' : 'Usuario');

  async function toggle() {
    open = !open;
    if (open) {
      await tick();
      menu?.focus();
    }
  }

  async function logout() {
    open = false;
    await onLogout();
  }

  $effect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node | null;
      if (target && root && !root.contains(target)) open = false;
    }

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        open = false;
        trigger?.focus();
      }
    }

    document.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('keydown', handleKeydown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<div class="relative" bind:this={root}>
  <button
    type="button"
    bind:this={trigger}
    onclick={toggle}
    class="flex h-9 items-center gap-2 rounded-lg border border-transparent px-1.5 text-left transition-colors hover:border-border hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
    aria-label={`Abrir menú de cuenta de ${displayName}`}
    aria-haspopup="menu"
    aria-expanded={open}
  >
    <Avatar {initials} size={28} alt={displayName} />
    <svg
      class="hidden text-foreground-subtle transition-transform sm:block {open ? 'rotate-180' : ''}"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  </button>

  {#if open}
    <div
      bind:this={menu}
      class="absolute right-0 top-[calc(100%+8px)] z-50 w-64 origin-top-right animate-fade-scale rounded-xl border border-border bg-surface-elevated p-1.5 shadow-lifted"
      role="menu"
      tabindex="-1"
      aria-label="Menú de cuenta"
    >
      <div class="flex items-center gap-3 px-2.5 py-2.5">
        <Avatar {initials} size={36} alt={displayName} />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-semibold text-foreground">{displayName}</p>
          <p class="truncate text-xs text-foreground-muted">{user?.email ?? 'Sin correo'}</p>
          <p class="mt-0.5 text-[11px] text-foreground-subtle">{accountType}</p>
        </div>
      </div>

      <div class="my-1 h-px bg-border"></div>

      <button
        type="button"
        disabled
        class="flex w-full cursor-not-allowed items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-foreground-subtle opacity-70"
        role="menuitem"
        title="Configuración estará disponible próximamente"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" />
          <path d="M12 2v4" />
          <path d="m7.8 7.8-2.9-2.9" />
          <path d="M2 12h4" />
          <path d="m7.8 16.2-2.9 2.9" />
          <path d="M12 18v4" />
          <path d="m16.2 16.2 2.9 2.9" />
          <path d="M18 12h4" />
          <path d="m16.2 7.8 2.9-2.9" />
        </svg>
        <span>Configuración</span>
        <span class="ml-auto rounded-full bg-surface-muted px-1.5 py-0.5 text-[10px]"
          >Próximamente</span
        >
      </button>

      <div class="my-1 h-px bg-border"></div>

      <button
        type="button"
        onclick={logout}
        disabled={loading}
        class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-danger transition-colors hover:bg-danger/10 disabled:cursor-wait disabled:opacity-60"
        role="menuitem"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <path d="m16 17 5-5-5-5" />
          <path d="M21 12H9" />
        </svg>
        {loading ? 'Cerrando sesión…' : 'Cerrar sesión'}
      </button>
    </div>
  {/if}
</div>
