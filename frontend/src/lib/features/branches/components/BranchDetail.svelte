<script lang="ts">
  /** BranchDetail — panel lateral con información detallada de la sucursal seleccionada. */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/mock-data';

  interface Props {
    branch: Branch | null;
  }

  let { branch }: Props = $props();

  // Mini sparkline mock de ventas (5 puntos)
  const SPARK = [120, 180, 150, 210, 195];
  const SW = 120;
  const SH = 28;
  let sparkPath = $derived.by(() => {
    const max = Math.max(...SPARK);
    const min = Math.min(...SPARK);
    const range = max - min || 1;
    const step = SW / (SPARK.length - 1);
    return SPARK.map((v, i) => {
      const x = i * step;
      const y = SH - ((v - min) / range) * SH;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  });
</script>

{#if branch}
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-start gap-3">
      <div class="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-primary/10">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-primary">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h3 class="truncate text-sm font-bold text-foreground">{branch.name}</h3>
          <Badge variant={STATUS_MAP[branch.status].variant}>{STATUS_MAP[branch.status].label}</Badge>
        </div>
        <p class="font-mono text-[10px] text-foreground-subtle">{branch.code}</p>
      </div>
    </div>

    <!-- KPIs internos -->
    <div class="grid grid-cols-3 gap-2">
      <div class="rounded-lg border border-border bg-surface-muted/50 px-2.5 py-2">
        <p class="text-[10px] text-foreground-subtle">Empleados</p>
        <p class="font-mono text-base font-bold tabular-nums text-foreground">{branch.employees}</p>
      </div>
      <div class="rounded-lg border border-border bg-surface-muted/50 px-2.5 py-2">
        <p class="text-[10px] text-foreground-subtle">Almacenes</p>
        <p class="font-mono text-base font-bold tabular-nums text-foreground">{branch.warehouses}</p>
      </div>
      <div class="rounded-lg border border-border bg-surface-muted/50 px-2.5 py-2">
        <p class="text-[10px] text-foreground-subtle">Ventas</p>
        <p class="font-mono text-base font-bold tabular-nums text-foreground">{branch.salesThisMonth > 0 ? `$${(branch.salesThisMonth / 1000).toFixed(1)}k` : '—'}</p>
      </div>
    </div>

    <!-- Sparkline -->
    {#if branch.salesThisMonth > 0}
      <div>
        <p class="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Tendencia de ventas</p>
        <svg width={SW} height={SH} viewBox={`0 0 ${SW} ${SH}`} aria-hidden="true">
          <defs>
            <linearGradient id="branch-spark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="rgb(var(--primary))" stop-opacity="0.2" />
              <stop offset="100%" stop-color="rgb(var(--primary))" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path d={`${sparkPath} L${SW},${SH} L0,${SH} Z`} fill="url(#branch-spark)" />
          <path d={sparkPath} fill="none" stroke="rgb(var(--primary))" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </div>
    {/if}

    <!-- Info -->
    <div class="space-y-2.5 border-t border-border pt-3">
      <div class="flex items-start gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="mt-0.5 flex-none text-foreground-subtle">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Dirección</p>
          <p class="text-[13px] text-foreground">{branch.address}</p>
          <p class="text-[12px] text-foreground-muted">{branch.city}</p>
        </div>
      </div>
      <div class="flex items-start gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="mt-0.5 flex-none text-foreground-subtle">
          <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Teléfono</p>
          <p class="font-mono text-[13px] text-foreground">{branch.phone}</p>
        </div>
      </div>
      <div class="flex items-start gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="mt-0.5 flex-none text-foreground-subtle">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Encargado</p>
          <div class="mt-0.5 flex items-center gap-1.5">
            <Avatar initials={branch.managerInitials} size={22} />
            <span class="text-[13px] text-foreground">{branch.manager}</span>
          </div>
        </div>
      </div>
      <div class="flex items-start gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="mt-0.5 flex-none text-foreground-subtle">
          <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Inaugurada</p>
          <p class="text-[13px] text-foreground">{branch.openedAt}</p>
        </div>
      </div>
      <div class="flex items-start gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="mt-0.5 flex-none text-foreground-subtle">
          <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Coordenadas</p>
          <p class="font-mono text-[12px] text-foreground">{branch.lat.toFixed(4)}, {branch.lng.toFixed(4)}</p>
        </div>
      </div>
    </div>
  </div>
{:else}
  <div class="flex flex-col items-center justify-center py-12 text-center">
    <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-muted">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-foreground-subtle">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
      </svg>
    </div>
    <p class="text-sm text-foreground-muted">Selecciona una sucursal para ver sus detalles</p>
  </div>
{/if}