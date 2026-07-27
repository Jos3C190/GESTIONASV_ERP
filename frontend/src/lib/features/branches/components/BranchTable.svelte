<script lang="ts">
  /**
   * BranchTable — tabla de sucursales estilo Geist con selección de filas,
   * acento visual, micro-sparklines de ventas y menú Kebab (3 puntos) reutilizable.
   */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/mock-data';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
    onSelect: (id: string) => void;
    onEdit?: (branch: Branch) => void;
    onDelete?: (branch: Branch) => void;
  }

  let { branches, selectedId, onSelect, onEdit, onDelete }: Props = $props();

  function handleDetail(branchId: string) {
    onSelect(branchId);
  }

  function handleEdit(branch: Branch) {
    if (onEdit) {
      onEdit(branch);
    } else {
      alert(`Editar "${branch.name}" (Acción de ejemplo)`);
    }
  }

  function handleDelete(branch: Branch) {
    if (onDelete) {
      onDelete(branch);
    } else {
      if (confirm(`¿Estás seguro de eliminar la sucursal "${branch.name}"?`)) {
        alert(`Sucursal "${branch.name}" eliminada.`);
      }
    }
  }

  // Helper para renderizar el micro-sparkline de ventas
  function getSparklineBars(trend: number[], status: string) {
    if (!trend || trend.length === 0) return [];
    const max = Math.max(...trend, 1);
    const color = status === 'active'
      ? 'rgb(var(--success))'
      : status === 'maintenance'
      ? 'rgb(var(--warning))'
      : 'rgb(var(--foreground-subtle))';

    return trend.map(val => ({
      height: Math.max(Math.round((val / max) * 14), 2),
      color,
    }));
  }
</script>

<div class="relative flex-1 h-full overflow-y-auto overflow-x-auto custom-scrollbar">
  <table class="w-full text-sm border-collapse">
    <thead class="sticky top-0 z-10 bg-surface-elevated shadow-xs">
      <tr class="border-b border-border bg-surface-muted/50">
        <th class="px-3.5 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Sucursal</th>
        <th class="px-3.5 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Ciudad</th>
        <th class="px-3.5 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Encargado</th>
        <th class="px-3.5 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Estado</th>
        <th class="px-3.5 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Empl.</th>
        <th class="px-3.5 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Almacenes</th>
        <th class="px-3.5 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Ventas mes</th>
        <th class="px-2 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-foreground-subtle w-11"></th>
      </tr>
    </thead>
    <tbody>
      {#each branches as branch (branch.id)}
        {@const isSelected = selectedId === branch.id}
        {@const bars = getSparklineBars(branch.trend, branch.status)}

        <tr
          class="group relative cursor-pointer border-b border-border/50 transition-colors duration-150 border-l-4 {isSelected ? 'border-l-primary bg-primary/10' : 'border-l-transparent hover:bg-surface-hover/70'}"
          onclick={() => onSelect(branch.id)}
        >
          <!-- Sucursal (Nombre + Código) -->
          <td class="px-3.5 py-2.5">
            <div class="flex items-center gap-2.5">
              <div class="flex h-8 w-8 flex-none items-center justify-center rounded-lg transition-colors {isSelected ? 'bg-primary text-surface' : 'bg-surface-muted text-foreground-subtle group-hover:text-foreground'}">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
                </svg>
              </div>
              <div class="min-w-0">
                <p class="text-[13px] font-bold leading-tight text-foreground truncate">{branch.name}</p>
                <p class="font-mono text-[10.5px] font-medium leading-tight text-foreground-subtle mt-0.5">{branch.code}</p>
              </div>
            </div>
          </td>

          <!-- Ciudad -->
          <td class="px-3.5 py-2.5 text-[12.5px] text-foreground-muted">{branch.city}</td>

          <!-- Encargado -->
          <td class="px-3.5 py-2.5">
            <div class="flex items-center gap-2">
              <Avatar initials={branch.managerInitials} size={24} />
              <span class="text-[12px] font-medium text-foreground">{branch.manager}</span>
            </div>
          </td>

          <!-- Estado Badge -->
          <td class="px-3.5 py-2.5">
            <Badge variant={STATUS_MAP[branch.status]?.variant || 'neutral'}>
              {STATUS_MAP[branch.status]?.label || branch.status}
            </Badge>
          </td>

          <!-- Empleados -->
          <td class="px-3.5 py-2.5 text-right font-mono text-[12px] font-bold tabular-nums text-foreground">
            {branch.employees}
          </td>

          <!-- Almacenes -->
          <td class="px-3.5 py-2.5 text-right font-mono text-[12px] font-bold tabular-nums text-foreground-muted">
            {branch.warehouses}
          </td>

          <!-- Ventas mes + Micro Sparkline -->
          <td class="px-3.5 py-2.5 text-right">
            {#if branch.salesThisMonth > 0}
              <div class="inline-flex items-center justify-end gap-2">
                <span class="font-mono text-[12px] font-bold tabular-nums text-foreground">
                  ${branch.salesThisMonth.toLocaleString()}
                </span>
                <!-- Sparkline en mini barras -->
                <div class="flex items-end gap-0.5 h-4 flex-none" aria-hidden="true">
                  {#each bars as bar}
                    <div
                      class="w-0.5 rounded-xs transition-all duration-300"
                      style="height: {bar.height}px; background-color: {bar.color};"
                    ></div>
                  {/each}
                </div>
              </div>
            {:else}
              <span class="font-mono text-[12px] text-foreground-subtle">—</span>
            {/if}
          </td>

          <!-- Acciones (Menú Kebab 3 puntos reutilizable) -->
          <td class="px-2 py-2.5 text-center">
            <KebabMenu
              items={[
                {
                  id: 'detail',
                  label: 'Ver detalle',
                  icon: 'detail',
                  onClick: () => handleDetail(branch.id),
                },
                {
                  id: 'edit',
                  label: 'Editar',
                  icon: 'edit',
                  onClick: () => handleEdit(branch),
                },
                {
                  id: 'delete',
                  label: 'Eliminar',
                  icon: 'delete',
                  variant: 'danger',
                  onClick: () => handleDelete(branch),
                },
              ]}
            />
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>