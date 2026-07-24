<script lang="ts">
  /** SummaryTable — tabla resumen con hover sutil, badges de estado, avatares. */

  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';

  interface Row {
    name: string;
    initials: string;
    dept: string;
    status: 'active' | 'inactive' | 'pending' | 'locked';
    createdAt: string;
  }

  interface Props {
    rows: Row[];
  }

  let { rows }: Props = $props();

  let statusMap: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' | 'danger' }> = {
    active: { label: 'Activo', variant: 'success' },
    inactive: { label: 'Inactivo', variant: 'neutral' },
    pending: { label: 'Pendiente', variant: 'warning' },
    locked: { label: 'Bloqueado', variant: 'danger' },
  };
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-border">
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Nombre</th>
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Departamento</th>
        <th class="px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Estado</th>
        <th class="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">Creado</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row.name)}
        <tr class="border-b border-border/50 transition-colors hover:bg-surface-hover/50">
          <td class="px-3 py-2.5">
            <div class="flex items-center gap-2">
              <Avatar initials={row.initials} size={24} />
              <span class="text-[13px] font-medium text-foreground">{row.name}</span>
            </div>
          </td>
          <td class="px-3 py-2.5 text-[13px] text-foreground-muted">{row.dept}</td>
          <td class="px-3 py-2.5">
            <Badge variant={statusMap[row.status]?.variant || 'neutral'}>{statusMap[row.status]?.label || row.status}</Badge>
          </td>
          <td class="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums text-foreground-subtle">{row.createdAt}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>