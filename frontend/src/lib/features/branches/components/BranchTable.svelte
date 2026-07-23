<script lang="ts">
  /** BranchTable — tabla de sucursales estilo Geist con selección de filas. */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/mock-data';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
    onSelect: (id: string) => void;
  }

  let { branches, selectedId, onSelect }: Props = $props();
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-border">
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Sucursal</th>
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Ciudad</th>
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Encargado</th>
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Estado</th>
        <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Empl.</th>
        <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Almacenes</th>
        <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Ventas mes</th>
      </tr>
    </thead>
    <tbody>
      {#each branches as branch (branch.id)}
        <tr
          class="cursor-pointer border-b border-border/50 transition-colors {selectedId === branch.id ? 'bg-surface-hover' : 'hover:bg-surface-hover/50'}"
          onclick={() => onSelect(branch.id)}
        >
          <td class="px-3 py-2.5">
            <div class="flex items-center gap-2">
              <div class="flex h-8 w-8 flex-none items-center justify-center rounded-lg {selectedId === branch.id ? 'bg-primary/15' : 'bg-surface-muted'}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class={selectedId === branch.id ? 'text-primary' : 'text-foreground-subtle'}>
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
                </svg>
              </div>
              <div>
                <p class="text-[13px] font-medium text-foreground">{branch.name}</p>
                <p class="font-mono text-[10px] text-foreground-subtle">{branch.code}</p>
              </div>
            </div>
          </td>
          <td class="px-3 py-2.5 text-[13px] text-foreground-muted">{branch.city}</td>
          <td class="px-3 py-2.5">
            <div class="flex items-center gap-1.5">
              <Avatar initials={branch.managerInitials} size={22} />
              <span class="text-[12px] text-foreground-muted">{branch.manager}</span>
            </div>
          </td>
          <td class="px-3 py-2.5">
            <Badge variant={STATUS_MAP[branch.status].variant}>{STATUS_MAP[branch.status].label}</Badge>
          </td>
          <td class="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums text-foreground">{branch.employees}</td>
          <td class="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums text-foreground-muted">{branch.warehouses}</td>
          <td class="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums text-foreground">
            {branch.salesThisMonth > 0 ? `$${branch.salesThisMonth.toLocaleString()}` : '—'}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>