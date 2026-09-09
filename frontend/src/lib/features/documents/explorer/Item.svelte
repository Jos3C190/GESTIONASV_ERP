<script lang="ts">
  import { activationForClick } from './interaction';
  import type { ExplorerItem } from './types';

  interface Props {
    item: ExplorerItem;
    selected: boolean;
    compact?: boolean;
    canRename: boolean;
    canMove: boolean;
    canDelete: boolean;
    canRestore: boolean;
    dropTarget?: boolean;
    onselect: (item: ExplorerItem, event: MouseEvent) => void;
    onopen: (item: ExplorerItem) => void;
    oncontextmenu: (item: ExplorerItem, event: MouseEvent | PointerEvent) => void;
    ondragstart: (item: ExplorerItem, event: DragEvent) => void;
    ondragend: () => void;
    ondragover: (item: ExplorerItem, event: DragEvent) => void;
    ondrop: (item: ExplorerItem, event: DragEvent) => void;
    onkeydown: (item: ExplorerItem, event: KeyboardEvent) => void;
  }

  let {
    item,
    selected,
    compact = false,
    canRename: _canRename,
    canMove,
    canDelete: _canDelete,
    canRestore: _canRestore,
    dropTarget = false,
    onselect,
    onopen,
    oncontextmenu,
    ondragstart,
    ondragend,
    ondragover,
    ondrop,
    onkeydown
  }: Props = $props();

  let lastPointer = $state<'mouse' | 'touch'>('mouse');
  let longPress: ReturnType<typeof setTimeout> | null = null;
  let longPressHandled = $state(false);

  const document = $derived(item.kind === 'file' ? item.document : null);
  const extension = $derived(document?.extension?.replace('.', '').toUpperCase() ?? '');

  function formatSize(bytes: number): string {
    if (!bytes) return '—';
    return bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(bytes / 1024))} KB`
      : `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function formatUpdated(value: string | null): string {
    return value
      ? new Date(value).toLocaleDateString('es-SV', { day: '2-digit', month: 'short', year: 'numeric' })
      : '—';
  }

  function statusLabel(value: string | undefined): string {
    return (
      {
        active: 'Activo',
        current: 'Vigente',
        processing: 'Procesando',
        deleted: 'En papelera',
        quarantined: 'Cuarentena',
        rejected: 'Rechazado'
      }[value ?? ''] ?? value ?? ''
    );
  }

  function handleClick(event: MouseEvent) {
    if (longPressHandled) {
      longPressHandled = false;
      event.preventDefault();
      return;
    }
    const pointer = lastPointer;
    if (activationForClick(event.detail, pointer) === 'open') onopen(item);
    else onselect(item, event);
  }

  function beginLongPress(event: PointerEvent) {
    lastPointer = event.pointerType === 'touch' ? 'touch' : 'mouse';
    if (lastPointer !== 'touch') return;
    longPressHandled = false;
    longPress = setTimeout(() => {
      event.preventDefault();
      longPressHandled = true;
      oncontextmenu(item, event);
      longPress = null;
    }, 520);
  }

  function clearLongPress() {
    if (longPress) clearTimeout(longPress);
    longPress = null;
  }

  function openMenu(event: MouseEvent) {
    event.stopPropagation();
    event.preventDefault();
    oncontextmenu(item, event);
  }

  function handleDragOver(event: DragEvent) {
    if (item.kind !== 'folder') return;
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    ondragover(item, event);
  }

  function handleDrop(event: DragEvent) {
    if (item.kind !== 'folder') return;
    event.preventDefault();
    event.stopPropagation();
    ondrop(item, event);
  }
</script>

<div
  role="listitem"
  class="explorer-item group {selected ? 'explorer-item-selected' : ''} {dropTarget
    ? 'explorer-item-drop-target'
    : ''} {compact ? 'explorer-item-compact' : ''}"
  ondragover={handleDragOver}
  ondrop={handleDrop}
>
  <button
    type="button"
    class="explorer-item-main"
    aria-label={`${item.name}, ${item.kind === 'folder' ? 'carpeta' : extension || 'archivo'}`}
    aria-pressed={selected}
    draggable={canMove}
    onpointerdown={beginLongPress}
    onpointerup={clearLongPress}
    onpointercancel={clearLongPress}
    onpointerleave={clearLongPress}
    onclick={handleClick}
    onkeydown={(event) => onkeydown(item, event)}
    oncontextmenu={(event) => {
      event.preventDefault();
      oncontextmenu(item, event);
    }}
    ondragstart={(event) => {
      event.stopPropagation();
      ondragstart(item, event);
    }}
    ondragend={ondragend}
  >
    <span
      class="entry-icon {item.kind === 'folder'
        ? 'entry-icon-folder'
        : document?.extension === '.pdf'
          ? 'entry-icon-pdf'
          : 'entry-icon-file'}"
      aria-hidden="true"
    >
      {#if item.kind === 'folder'}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M3.5 9h17" />
        </svg>
      {:else}
        <span class="text-[10px] font-bold">{extension || 'FILE'}</span>
      {/if}
    </span>
    <span class="min-w-0 flex-1">
      <span class="block truncate text-sm font-medium text-foreground" title={item.name}>{item.name}</span>
      <span class="mt-0.5 block truncate text-xs text-foreground-muted" title={item.kind === 'file' ? document?.original_filename : undefined}>
        {#if item.kind === 'folder'}
          Carpeta · Suelta aquí para mover elementos
        {:else}
          {document?.category_name ?? 'Sin categoría'} · {statusLabel(document?.business_status)}
        {/if}
      </span>
    </span>
    <span class="hidden min-w-[112px] text-xs text-foreground-muted sm:block">
      {item.kind === 'folder' ? 'Carpeta' : extension || 'Archivo'}
    </span>
    <span class="hidden min-w-[144px] text-xs tabular-nums text-foreground-muted md:block">{formatUpdated(item.updatedAt)}</span>
    <span class="hidden min-w-[88px] text-right text-xs tabular-nums text-foreground-muted lg:block">
      {item.kind === 'folder' ? '—' : formatSize(document?.size_bytes ?? 0)}
    </span>
  </button>

  <button
    type="button"
    class="kebab min-h-11 min-w-11 rounded-lg text-lg text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground"
    aria-haspopup="menu"
    aria-label={`Más acciones para ${item.name}`}
    onclick={openMenu}>⋯</button
  >
</div>

<style>
  .explorer-item {
    display: flex;
    min-height: 58px;
    align-items: center;
    gap: 0.25rem;
    border-bottom: 1px solid rgb(var(--border));
    padding: 0.25rem 0.5rem 0.25rem 0.875rem;
    user-select: none;
    transition: background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
  }
  .explorer-item:last-child { border-bottom: 0; }
  .explorer-item:hover { background: rgb(var(--surface-hover) / 0.65); }
  .explorer-item-selected { background: rgb(var(--primary) / 0.09); box-shadow: inset 2px 0 0 rgb(var(--primary)); }
  .explorer-item-drop-target { background: rgb(var(--primary) / 0.13); box-shadow: inset 3px 0 0 rgb(var(--primary)), inset 0 0 0 1px rgb(var(--primary) / 0.32); }
  .explorer-item-main {
    display: flex;
    min-width: 0;
    min-height: 50px;
    flex: 1;
    align-items: center;
    gap: 1rem;
    border: 0;
    background: transparent;
    padding: 0;
    text-align: left;
    color: inherit;
    cursor: default;
  }
  .explorer-item-main:focus-visible { position: relative; z-index: 1; outline: 2px solid rgb(var(--primary)); outline-offset: -2px; border-radius: 0.5rem; }
  .entry-icon { display: inline-flex; height: 34px; width: 34px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 0.625rem; }
  .entry-icon-folder { background: rgb(var(--warning) / 0.16); color: rgb(var(--warning)); }
  .entry-icon-file { background: rgb(var(--foreground-muted) / 0.12); color: rgb(var(--foreground-muted)); }
  .entry-icon-pdf { background: rgb(var(--danger) / 0.12); color: rgb(var(--danger)); }
  .explorer-item-compact { position: relative; min-height: 154px; display: block; border-bottom: 0; padding: 1rem; }
  .explorer-item-compact .explorer-item-main { min-height: 132px; flex-direction: column; align-items: stretch; gap: 0.625rem; }
  .explorer-item-compact .explorer-item-main > span { display: block; min-width: 0; }
  .explorer-item-compact .explorer-item-main > span:first-child { height: 48px; width: 48px; }
  .explorer-item-compact .explorer-item-main > span:nth-of-type(2) { width: 100%; }
  .explorer-item-compact .explorer-item-main > span:nth-of-type(n + 3) { display: block; }
  .explorer-item-compact .kebab { position: absolute; right: 0.5rem; top: 0.5rem; }
  @media (max-width: 640px) {
    .explorer-item { min-height: 64px; padding-left: 0.625rem; }
    .entry-icon { height: 40px; width: 40px; }
    .explorer-item-main { min-height: 56px; gap: 0.625rem; }
  }
  @media (prefers-reduced-motion: reduce) { .explorer-item, .kebab { transition: none; } }
</style>