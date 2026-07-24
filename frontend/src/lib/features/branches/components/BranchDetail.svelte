<script lang="ts">
  /**
   * BranchDetail — panel horizontal ancho de 3 secciones que muestra el detalle
   * de la sucursal seleccionada (Identidad, Métricas/Tendencia, Información de contacto).
   */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/mock-data';

  interface Props {
    branch: Branch | null;
  }

  let { branch }: Props = $props();

  // Gráfica SVG de tendencia de ventas (Smooth Line Sparkline)
  const SW = 280;
  const SH = 42;

  let sparkPath = $derived.by(() => {
    if (!branch?.trend || branch.trend.length === 0) return '';
    const trend = branch.trend;
    const max = Math.max(...trend, 1);
    const min = Math.min(...trend);
    const range = max - min || 1;
    const step = SW / (trend.length - 1);

    return trend.map((v, i) => {
      const x = i * step;
      const y = SH - 4 - ((v - min) / range) * (SH - 8);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  });

  let strokeColor = $derived.by(() => {
    if (!branch) return 'rgb(var(--primary))';
    if (branch.status === 'active') return '#0070F3';
    if (branch.status === 'maintenance') return '#F59E0B';
    return '#64748B';
  });
</script>

{#if branch}
  <!-- Grid Horizontal de 3 Secciones (Apilable en pantallas angostas <900px) -->
  <div class="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border/60">

    <!-- Sección 1: Identidad de la Sucursal -->
    <div class="p-3.5 md:p-4 flex flex-col justify-between gap-2.5">
      <div>
        <div class="flex items-start gap-2.5">
          <div class="flex h-9 w-9 flex-none items-center justify-center rounded-xl bg-primary/10 text-primary shadow-xs">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-bold text-foreground truncate">{branch.name}</h3>
              <Badge variant={STATUS_MAP[branch.status].variant}>
                {STATUS_MAP[branch.status].label}
              </Badge>
            </div>
            <p class="font-mono text-[10.5px] font-medium text-foreground-subtle mt-0.5">{branch.code}</p>
          </div>
        </div>
      </div>

      <!-- Encargado -->
      <div class="flex items-center gap-2 rounded-lg border border-border/50 bg-surface-muted/30 p-2">
        <Avatar initials={branch.managerInitials} size={26} />
        <div class="min-w-0 flex-1">
          <p class="text-xs font-semibold text-foreground truncate">{branch.manager}</p>
          <p class="text-[10px] font-medium text-foreground-subtle">Encargado de sucursal</p>
        </div>
      </div>
    </div>

    <!-- Sección 2: Métricas & Tendencia de Ventas -->
    <div class="p-3.5 md:p-4 flex flex-col justify-between gap-2.5">
      <!-- 3 Stat-Boxes en Fila -->
      <div class="grid grid-cols-3 gap-1.5">
        <div class="rounded-lg border border-border bg-surface-muted/40 p-1.5 text-center">
          <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">Empleados</p>
          <p class="font-mono text-sm font-bold tabular-nums text-foreground mt-0.5">{branch.employees}</p>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/40 p-1.5 text-center">
          <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">Almacenes</p>
          <p class="font-mono text-sm font-bold tabular-nums text-foreground mt-0.5">{branch.warehouses}</p>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/40 p-1.5 text-center">
          <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">Ventas</p>
          <p class="font-mono text-sm font-bold tabular-nums text-foreground mt-0.5">
            {branch.salesThisMonth > 0 ? `$${(branch.salesThisMonth / 1000).toFixed(1)}k` : '—'}
          </p>
        </div>
      </div>

      <!-- Sparkline de Tendencia de Ventas -->
      <div>
        <div class="flex items-center justify-between text-[9.5px] font-bold uppercase tracking-wider text-foreground-subtle mb-0.5">
          <span>Tendencia de ventas</span>
          {#if branch.salesThisMonth > 0}
            <span class="font-mono text-primary font-semibold">${branch.salesThisMonth.toLocaleString()}</span>
          {/if}
        </div>
        {#if branch.salesThisMonth > 0 && sparkPath}
          <div class="w-full overflow-hidden rounded-md bg-surface-muted/20 p-1">
            <svg width="100%" height={SH} viewBox={`0 0 ${SW} ${SH}`} preserveAspectRatio="none" aria-hidden="true">
              <path d={sparkPath} fill="none" stroke={strokeColor} stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
        {:else}
          <div class="flex h-8 w-full items-center justify-center rounded-md bg-surface-muted/20 text-xs text-foreground-subtle">
            Sin registro de ventas
          </div>
        {/if}
      </div>
    </div>

    <!-- Sección 3: Información de Contacto & Ubicación -->
    <div class="p-3.5 md:p-4 flex flex-col justify-between gap-1.5 text-xs">
      <!-- Dirección -->
      <div class="flex items-start gap-2.5">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mt-0.5 flex-none text-foreground-subtle">
          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[9.5px] font-bold uppercase tracking-wider text-foreground-subtle">Dirección</p>
          <p class="font-medium text-foreground text-[12.5px] truncate">{branch.address}</p>
          <p class="text-foreground-subtle text-[11px]">{branch.city}</p>
        </div>
      </div>

      <!-- Teléfono & Inauguración -->
      <div class="grid grid-cols-2 gap-2 pt-1 border-t border-border/40">
        <div class="flex items-start gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mt-0.5 flex-none text-foreground-subtle">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
          </svg>
          <div class="min-w-0 flex-1">
            <p class="text-[9.5px] font-bold uppercase tracking-wider text-foreground-subtle">Teléfono</p>
            <p class="font-mono font-medium text-foreground text-[11.5px]">{branch.phone}</p>
          </div>
        </div>

        <div class="flex items-start gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mt-0.5 flex-none text-foreground-subtle">
            <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          <div class="min-w-0 flex-1">
            <p class="text-[9.5px] font-bold uppercase tracking-wider text-foreground-subtle">Inaugurada</p>
            <p class="font-medium text-foreground text-[11.5px]">{branch.openedAt}</p>
          </div>
        </div>
      </div>

      <!-- Coordenadas -->
      <div class="flex items-center gap-2 pt-1 border-t border-border/40">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="flex-none text-foreground-subtle">
          <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
        <p class="text-[9.5px] font-bold uppercase tracking-wider text-foreground-subtle flex-none">Coordenadas:</p>
        <p class="font-mono text-[11px] font-semibold text-foreground truncate">{branch.lat.toFixed(4)}, {branch.lng.toFixed(4)}</p>
      </div>
    </div>

  </div>
{:else}
  <div class="flex flex-col items-center justify-center p-8 text-center">
    <div class="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-surface-muted text-foreground-subtle">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
      </svg>
    </div>
    <p class="text-xs font-medium text-foreground-muted">Selecciona una sucursal en la tabla o el mapa para explorar su información en detalle</p>
  </div>
{/if}