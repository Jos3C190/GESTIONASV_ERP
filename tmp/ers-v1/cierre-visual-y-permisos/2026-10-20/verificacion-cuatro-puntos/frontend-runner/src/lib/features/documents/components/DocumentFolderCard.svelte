<script lang="ts">
  import type { DocumentFolderOut } from '$lib/api/client';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import { initialsOf } from '$lib/features/employees/avatar';

  interface Props {
    folder: DocumentFolderOut;
    href: string;
  }

  let { folder, href }: Props = $props();

  function formatDate(value: string | null): string {
    return value
      ? new Date(value).toLocaleDateString('es-SV', { day: 'numeric', month: 'short' })
      : 'Sin archivos';
  }

  function employeeInitials(): string {
    const parts = folder.name.trim().split(/\s+/);
    return initialsOf(parts[0] ?? '', parts.slice(1).join(' '));
  }

  function statusLabel(status: string | null): string {
    return (
      {
        activo: 'Activo',
        inactivo: 'Inactivo',
        vacaciones: 'Vacaciones',
        baja: 'Baja'
      }[status ?? ''] ?? status ?? ''
    );
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key !== ' ') return;
    event.preventDefault();
    (event.currentTarget as HTMLAnchorElement).click();
  }
</script>

<a
  {href}
  onkeydown={handleKeydown}
  class="group block min-h-[148px] rounded-2xl border border-border bg-surface-elevated p-4 shadow-soft transition duration-200 hover:-translate-y-px hover:border-border-strong hover:shadow-lifted focus-visible:relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
  aria-label={`Abrir carpeta ${folder.name}`}
>
  <div class="flex items-start gap-3">
    {#if folder.kind === 'employee'}
      <Avatar initials={employeeInitials()} size={42} alt={folder.name} />
    {:else}
      <span
        class="folder-icon flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
        aria-hidden="true"
      >
        <svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
          <path d="M3.5 9h17" />
        </svg>
      </span>
    {/if}
    <div class="min-w-0 flex-1">
      <div class="flex items-start justify-between gap-2">
        <h2 class="truncate text-[13px] font-semibold text-foreground">{folder.name}</h2>
        <svg class="mt-0.5 shrink-0 text-foreground-subtle transition-transform duration-200 group-hover:translate-x-0.5" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
      </div>
      {#if folder.kind === 'employee'}
        <p class="mt-1 truncate text-[11px] text-foreground-muted">
          {folder.employee_code ?? 'Sin código'}
          {#if folder.employee_status} · {statusLabel(folder.employee_status)}{/if}
        </p>
      {:else if folder.kind === 'category'}
        <p class="mt-1 truncate text-[11px] text-foreground-muted">Categoría documental</p>
      {:else}
        <p class="mt-1 truncate text-[11px] text-foreground-muted">
          {folder.module === 'employees' ? 'Expedientes laborales' : 'Documentos de la empresa'}
        </p>
      {/if}
    </div>
  </div>

  <div class="mt-5 flex items-end justify-between gap-3 text-[11px] text-foreground-muted">
    <div>
      <p class="font-mono tabular-nums text-foreground">{folder.document_count}</p>
      <p>{folder.document_count === 1 ? 'documento' : 'documentos'}</p>
    </div>
    <div class="text-right">
      {#if folder.active_count > 0}<p class="font-mono tabular-nums text-success">{folder.active_count} vigentes</p>{/if}
      <p>Actualizado {formatDate(folder.latest_document_at)}</p>
    </div>
  </div>
</a>

<style>
  .folder-icon {
    position: relative;
    transition: background-color 180ms ease, color 180ms ease;
  }

  .folder-icon::before {
    position: absolute;
    top: 7px;
    left: 8px;
    width: 10px;
    height: 3px;
    border-radius: 999px;
    background: currentColor;
    content: '';
    opacity: 0.45;
    transform-origin: left center;
    transition: transform 180ms ease;
  }

  .group:hover .folder-icon::before,
  .group:focus-visible .folder-icon::before {
    transform: scaleX(1.18);
  }

  @media (prefers-reduced-motion: reduce) {
    .folder-icon,
    .folder-icon::before,
    svg {
      transition: none !important;
    }
  }
</style>
