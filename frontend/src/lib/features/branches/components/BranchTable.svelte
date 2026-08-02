<script lang="ts">
  /**
   * BranchTable — tabla de sucursales estilo Geist con selección de filas,
   * acento visual, micro-sparklines de ventas y menú Kebab (3 puntos) reutilizable.
   */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { goto } from '$app/navigation';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/types';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
    onSelect: (id: string) => void;
    onEdit?: (branch: Branch) => void;
    onDelete?: (branch: Branch) => void;
  }

  let { branches, selectedId, onSelect, onEdit, onDelete }: Props = $props();

  function handleDetail(branchId: string) {
    goto(`/branches/${branchId}`);
  }

  function handleEdit(branch: Branch) {
    if (onEdit) onEdit(branch);
  }

  function handleDelete(branch: Branch) {
    if (onDelete) {
      onDelete(branch);
    }
  }

  function branchMenuItems(branch: Branch): KebabItem[] {
    return [
      {
        id: 'detail',
        label: 'Ver detalle',
        icon: 'detail',
        onClick: () => handleDetail(branch.id)
      },
      ...(onEdit
        ? [
            {
              id: 'edit',
              label: 'Editar',
              icon: 'edit' as const,
              onClick: () => handleEdit(branch)
            }
          ]
        : []),
      ...(onDelete
        ? [
            {
              id: 'delete',
              label: branch.status === 'inactive' ? 'Activar' : 'Desactivar',
              icon: 'power' as const,
              variant: 'danger' as const,
              onClick: () => handleDelete(branch)
            }
          ]
        : [])
    ];
  }

  // Helper para renderizar el micro-sparkline de ventas
  function getSparklineBars(trend: number[], status: string) {
    if (!trend || trend.length === 0) return [];
    const max = Math.max(...trend, 1);
    const color =
      status === 'active'
        ? 'rgb(var(--success))'
        : status === 'maintenance'
          ? 'rgb(var(--warning))'
          : 'rgb(var(--foreground-subtle))';

    return trend.map((val) => ({
      height: Math.max(Math.round((val / max) * 14), 2),
      color
    }));
  }
</script>

<div class="branch-table-shell relative flex h-full flex-1 flex-col overflow-hidden">
  {#if branches.length === 0}
    <div class="flex min-h-52 flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
      <div
        class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-muted text-foreground-subtle"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1M14 9h1M9 13h1M14 13h1M9 17h6" />
        </svg>
      </div>
      <p class="text-sm font-semibold text-foreground">No hay sucursales para mostrar</p>
      <p class="max-w-xs text-xs text-foreground-subtle">
        Ajusta la búsqueda o los filtros para consultar otros resultados.
      </p>
    </div>
  {:else}
    <div class="desktop-table custom-scrollbar h-full flex-1 overflow-y-auto overflow-x-hidden">
      <table class="w-full table-fixed border-collapse text-sm">
        <colgroup>
          <col class="col-branch" />
          <col class="col-city" />
          <col class="col-manager" />
          <col class="col-status" />
          <col class="col-employees" />
          <col class="col-warehouses" />
          <col class="col-sales" />
          <col class="col-actions" />
        </colgroup>
        <thead class="sticky top-0 z-10 bg-surface-elevated shadow-xs">
          <tr class="border-b border-border bg-surface-muted/50">
            <th
              class="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Sucursal</th
            >
            <th
              class="col-city px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Ciudad</th
            >
            <th
              class="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Encargado</th
            >
            <th
              class="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Estado</th
            >
            <th
              class="col-employees px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Empl.</th
            >
            <th
              class="col-warehouses px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Almacenes</th
            >
            <th
              class="col-sales px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-wider text-foreground-subtle"
              >Ventas mes</th
            >
            <th class="w-11 px-2 py-2.5"><span class="sr-only">Acciones</span></th>
          </tr>
        </thead>
        <tbody>
          {#each branches as branch (branch.id)}
            {@const isSelected = selectedId === branch.id}
            {@const bars = getSparklineBars(branch.trend, branch.status)}

            <tr
              class="group relative h-[62px] cursor-pointer border-b border-l-[3px] border-border/50 transition-colors duration-150 {isSelected
                ? 'border-l-primary bg-primary/10'
                : 'border-l-transparent hover:bg-surface-hover/70'}"
              onclick={() => onSelect(branch.id)}
            >
              <!-- Sucursal (Nombre + Código) -->
              <td class="min-w-0 px-3 py-2.5">
                <div class="flex min-w-0 items-center gap-2.5">
                  <div
                    class="flex h-8 w-8 flex-none items-center justify-center rounded-lg transition-colors {isSelected
                      ? 'bg-primary text-surface'
                      : 'bg-surface-muted text-foreground-subtle group-hover:text-foreground'}"
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
                      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle
                        cx="12"
                        cy="10"
                        r="3"
                      />
                    </svg>
                  </div>
                  <div class="min-w-0 flex-1">
                    <p
                      class="truncate text-[13px] font-bold leading-tight text-foreground"
                      title={branch.name}
                    >
                      {branch.name}
                    </p>
                    <div class="mt-1 flex min-w-0 items-center gap-1.5">
                      <span
                        class="truncate font-mono text-[10px] font-medium leading-tight text-foreground-subtle"
                        >{branch.code}</span
                      >
                      <span class="inline-city text-foreground-subtle" aria-hidden="true">·</span>
                      <span
                        class="inline-city truncate text-[10.5px] text-foreground-muted"
                        title={branch.city}>{branch.city}</span
                      >
                    </div>
                  </div>
                </div>
              </td>

              <!-- Ciudad -->
              <td class="col-city min-w-0 px-3 py-2.5 text-[12px] text-foreground-muted">
                <span class="block truncate" title={branch.city}>{branch.city}</span>
              </td>

              <!-- Encargado -->
              <td class="min-w-0 px-3 py-2.5">
                <div class="flex min-w-0 items-center gap-2">
                  <Avatar initials={branch.managerInitials} size={24} />
                  <span
                    class="block min-w-0 truncate text-[12px] font-medium text-foreground"
                    title={branch.manager}>{branch.manager}</span
                  >
                </div>
              </td>

              <!-- Estado Badge -->
              <td class="px-3 py-2.5">
                <Badge variant={STATUS_MAP[branch.status]?.variant || 'neutral'}>
                  {STATUS_MAP[branch.status]?.label || branch.status}
                </Badge>
              </td>

              <!-- Empleados -->
              <td
                class="col-employees px-3 py-2.5 text-right font-mono text-[12px] font-bold tabular-nums text-foreground"
              >
                {branch.employees}
              </td>

              <!-- Almacenes -->
              <td
                class="col-warehouses px-3 py-2.5 text-right font-mono text-[12px] font-bold tabular-nums text-foreground-muted"
              >
                {branch.warehouses}
              </td>

              <!-- Ventas mes + Micro Sparkline -->
              <td class="col-sales px-3 py-2.5 text-right">
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
                  items={branchMenuItems(branch)}
                  ariaLabel={`Acciones de ${branch.name}`}
                />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="mobile-list custom-scrollbar h-full flex-1 overflow-y-auto p-2">
      <div class="space-y-2">
        {#each branches as branch (branch.id)}
          {@const isSelected = selectedId === branch.id}
          <div
            class="relative overflow-hidden rounded-xl border transition-colors {isSelected
              ? 'border-primary/40 bg-primary/10'
              : 'border-border bg-surface hover:bg-surface-hover'}"
          >
            <button
              type="button"
              class="w-full p-3 pr-12 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              onclick={() => onSelect(branch.id)}
              aria-pressed={isSelected}
            >
              <div class="flex min-w-0 items-start gap-2.5">
                <div
                  class="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg {isSelected
                    ? 'bg-primary text-surface'
                    : 'bg-surface-muted text-foreground-subtle'}"
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    aria-hidden="true"
                  >
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle
                      cx="12"
                      cy="10"
                      r="3"
                    />
                  </svg>
                </div>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[13px] font-semibold text-foreground" title={branch.name}>
                    {branch.name}
                  </p>
                  <p class="mt-0.5 truncate text-[11px] text-foreground-muted" title={branch.city}>
                    <span class="font-mono text-[10px] text-foreground-subtle">{branch.code}</span>
                    <span aria-hidden="true"> · </span>{branch.city}
                  </p>
                </div>
              </div>

              <div
                class="mt-3 flex items-center justify-between gap-3 border-t border-border/60 pt-2.5"
              >
                <div class="flex min-w-0 items-center gap-2">
                  <Avatar initials={branch.managerInitials} size={22} />
                  <span
                    class="truncate text-[11.5px] font-medium text-foreground"
                    title={branch.manager}>{branch.manager}</span
                  >
                </div>
                <div
                  class="flex flex-none items-center gap-2.5 text-[10.5px] text-foreground-muted"
                >
                  <Badge variant={STATUS_MAP[branch.status]?.variant || 'neutral'}>
                    {STATUS_MAP[branch.status]?.label || branch.status}
                  </Badge>
                  <span title={`${branch.employees} empleados`}>{branch.employees} empl.</span>
                  <span title={`${branch.warehouses} almacenes`}>{branch.warehouses} alm.</span>
                </div>
              </div>
            </button>
            <div class="absolute right-2.5 top-2.5">
              <KebabMenu items={branchMenuItems(branch)} ariaLabel={`Acciones de ${branch.name}`} />
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .branch-table-shell {
    container-name: branch-table;
    container-type: inline-size;
  }

  .col-branch {
    width: 29%;
  }

  .col-city {
    width: 13%;
  }

  .col-manager {
    width: 21%;
  }

  .col-status {
    width: 11%;
  }

  .col-employees {
    width: 7%;
  }

  .col-warehouses {
    width: 9%;
  }

  .col-sales {
    width: 6%;
  }

  .col-actions {
    width: 4%;
  }

  .inline-city,
  .mobile-list {
    display: none;
  }

  @container branch-table (max-width: 1050px) {
    .col-sales {
      display: none;
    }

    .col-branch {
      width: 32%;
    }

    .col-city {
      width: 14%;
    }

    .col-manager {
      width: 24%;
    }

    .col-status {
      width: 12%;
    }

    .col-employees {
      width: 8%;
    }

    .col-warehouses {
      width: 6%;
    }
  }

  @container branch-table (max-width: 880px) {
    .col-city {
      display: none;
    }

    .inline-city {
      display: inline;
    }

    .col-branch {
      width: 38%;
    }

    .col-manager {
      width: 28%;
    }

    .col-status {
      width: 14%;
    }

    .col-employees {
      width: 9%;
    }

    .col-warehouses {
      width: 7%;
    }
  }

  @container branch-table (max-width: 720px) {
    .col-warehouses {
      display: none;
    }

    .col-branch {
      width: 43%;
    }

    .col-manager {
      width: 31%;
    }

    .col-status {
      width: 13%;
    }
  }

  @container branch-table (max-width: 620px) {
    .desktop-table {
      display: none;
    }

    .mobile-list {
      display: block;
    }
  }
</style>
