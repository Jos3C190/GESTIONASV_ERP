<script lang="ts">
  import { activationForClick } from './interaction';
  import EntryArtwork from './EntryArtwork.svelte';
  import { documentFileTone } from './file-types';
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
    contextOpen?: boolean;
    tabIndex?: number;
    position?: number;
    setSize?: number;
    semantics?: 'option' | 'gridcell';
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
    onkeydown,
    contextOpen = false,
    tabIndex = 0,
    position = 1,
    setSize = 1,
    semantics = 'option'
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

  function openMenu(event: MouseEvent | KeyboardEvent) {
    event.stopPropagation();
    event.preventDefault();
    if (event instanceof MouseEvent) {
      oncontextmenu(item, event);
      return;
    }
    const target = event.currentTarget as HTMLElement | null;
    const bounds = target?.getBoundingClientRect();
    oncontextmenu(
      item,
      new MouseEvent('contextmenu', {
        bubbles: true,
        cancelable: true,
        clientX: bounds?.right ?? 0,
        clientY: bounds?.bottom ?? 0
      })
    );
  }

  function handleDragOver(event: DragEvent) {
    if (item.kind !== 'folder') {
      event.stopPropagation();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    ondragover(item, event);
  }

  function handleDrop(event: DragEvent) {
    if (item.kind !== 'folder') {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    ondrop(item, event);
  }
</script>

<div
  role={semantics === 'gridcell' ? 'gridcell' : 'listitem'}
  aria-selected={semantics === 'gridcell' ? selected : undefined}
  aria-posinset={position}
  aria-setsize={setSize}
  data-explorer-item-id={item.id}
  class="explorer-item group {selected ? 'explorer-item-selected' : ''} {dropTarget
    ? 'explorer-item-drop-target'
    : ''} {compact ? 'explorer-item-compact' : ''}"
  ondragover={handleDragOver}
  ondrop={handleDrop}
>
  {#if compact}
    <span class="tile-selection-indicator" aria-hidden="true">
      {#if selected}
        <svg viewBox="0 0 16 16" fill="none">
          <path d="m4 8.2 2.3 2.3L12 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      {/if}
    </span>
  {/if}
  <button
    type="button"
    aria-pressed={selected}
    class="explorer-item-main"
    aria-label={item.name + ', ' + (item.kind === 'folder' ? 'carpeta' : extension || 'archivo') + ', ' + (item.kind === 'folder' ? 'modificada ' + formatUpdated(item.updatedAt) : statusLabel(document?.business_status) + ', ' + formatSize(document?.size_bytes ?? 0) + ', modificada ' + formatUpdated(item.updatedAt))}
    tabindex={tabIndex}
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
    {#if compact}
      <span class="tile-artwork">
        <EntryArtwork kind={item.kind} extension={document?.extension} />
      </span>
    {:else}
      <span
        class="entry-icon {item.kind === 'folder'
          ? 'entry-icon-folder'
          : 'entry-icon-' + documentFileTone(document?.extension)}"
        aria-hidden="true"
      >
        {#if item.kind === 'folder'}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M3.5 9h17" />
          </svg>
        {:else}
          <span class="entry-file-label text-[10px] font-bold">{extension || 'FILE'}</span>
        {/if}
      </span>
    {/if}
    <span class="entry-copy min-w-0 flex-1">
      <span class="entry-name block truncate text-sm font-medium text-foreground" title={item.name}>{item.name}</span>
      {#if !compact}
        <span class="entry-metadata mt-0.5 block truncate text-xs text-foreground-muted" title={item.kind === 'file' ? document?.original_filename : undefined}>
          {#if item.kind === 'folder'}
            Carpeta
          {:else}
            {document?.category_name ?? 'Sin categoría'} · {statusLabel(document?.business_status)}
          {/if}
        </span>
      {/if}
    </span>
    {#if !compact}
      <span class="entry-type hidden min-w-[112px] text-xs text-foreground-muted sm:block">
        {item.kind === 'folder' ? 'Carpeta' : extension || 'Archivo'}
      </span>
      <span class="entry-updated hidden min-w-[144px] text-xs tabular-nums text-foreground-muted md:block">{formatUpdated(item.updatedAt)}</span>
      <span class="entry-size hidden min-w-[88px] text-right text-xs tabular-nums text-foreground-muted lg:block">
        {item.kind === 'folder' ? '—' : formatSize(document?.size_bytes ?? 0)}
      </span>
    {/if}
  </button>

  <button
    type="button"
    class="kebab min-h-11 min-w-11 rounded-lg text-lg text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground"
    aria-haspopup="menu"
    aria-expanded={contextOpen}
    aria-controls={contextOpen ? 'explorer-menu-' + item.id : undefined}
    aria-label={'Más acciones para ' + item.name}
    tabindex="-1"
    onkeydown={(event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openMenu(event);
      }
    }}
    onclick={openMenu}>⋯</button>
</div>

<style>
  .explorer-item {
    display: flex;
    min-height: 58px;
    align-items: center;
    gap: var(--explorer-space-1);
    border-bottom: 1px solid rgb(var(--border));
    padding: var(--explorer-space-1) var(--explorer-space-1) var(--explorer-space-1) var(--explorer-space-3);
    user-select: none;
    transition: background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
  }
  .explorer-item:last-child { border-bottom: 0; }
  .explorer-item:hover { background: rgb(var(--surface-hover) / 0.65); }
  .explorer-item-selected { background: rgb(var(--primary) / 0.09); box-shadow: inset 2px 0 0 rgb(var(--primary)); }
  .explorer-item-drop-target { background: rgb(var(--primary) / 0.13); box-shadow: inset 3px 0 0 rgb(var(--primary)), inset 0 0 0 1px rgb(var(--primary) / 0.32); }
  .explorer-item-main {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr) 112px 144px 88px;
    min-width: 0;
    min-height: 50px;
    flex: 1;
    align-items: center;
    gap: var(--explorer-space-2);
    border: 0;
    background: transparent;
    padding: 0;
    text-align: left;
    color: inherit;
    cursor: pointer;
  }
  .explorer-item-main:focus-visible { position: relative; z-index: 1; outline: 2px solid rgb(var(--primary)); outline-offset: -2px; border-radius: var(--explorer-radius-sm); }
  .kebab:focus-visible { outline: 2px solid rgb(var(--primary)); outline-offset: 2px; color: rgb(var(--foreground)); }
  .entry-icon, .tile-artwork { grid-column: 1; }
  .entry-copy { grid-column: 2; }
  .entry-type { grid-column: 3; }
  .entry-updated { grid-column: 4; }
  .entry-size { grid-column: 5; }  .entry-icon { display: inline-flex; height: 34px; width: 34px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: var(--explorer-radius-md); }
  .entry-icon-folder { background: rgb(var(--warning) / 0.16); color: rgb(var(--warning)); }
  .entry-icon-file { background: rgb(var(--foreground-muted) / 0.12); color: rgb(var(--foreground-muted)); }
  .entry-icon-pdf { background: rgb(var(--danger) / 0.12); color: rgb(var(--danger)); }
  .entry-icon-doc { background: rgb(var(--primary) / 0.14); color: rgb(var(--primary)); }
  .entry-icon-sheet { background: rgb(var(--success) / 0.14); color: rgb(var(--success)); }
  .entry-icon-slides { background: rgb(var(--warning) / 0.16); color: rgb(var(--warning)); }
  .entry-icon-archive { background: rgb(var(--accent) / 0.16); color: rgb(var(--accent)); }
  .entry-icon-text { background: rgb(var(--foreground-muted) / 0.14); color: rgb(var(--foreground)); }
  .entry-icon-image { background: rgb(var(--accent) / 0.12); color: rgb(var(--accent)); }
  .explorer-item-compact {
    position: relative;
    min-height: 164px;
    display: block;
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-md);
    background: rgb(var(--surface-elevated));
    box-shadow: var(--shadow-sm);
    padding: 0;
    transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease, box-shadow 140ms ease;
  }
  .explorer-item-compact:hover {
    transform: translateY(-2px);
    border-color: rgb(var(--border-strong));
    background: rgb(var(--surface-hover));
    box-shadow: var(--shadow-md);
  }
  .explorer-item-compact:focus-within {
    border-color: rgb(var(--border-strong));
    background: rgb(var(--surface-hover));
  }
  .explorer-item-compact.explorer-item-selected {
    border-color: rgb(var(--primary) / 0.78);
    background: rgb(var(--primary) / 0.1);
    box-shadow: 0 0 0 1px rgb(var(--primary) / 0.12), var(--shadow-sm);
  }
  .explorer-item-compact .explorer-item-main {
    display: flex;
    width: 100%;
    min-height: 162px;
    box-sizing: border-box;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    gap: var(--explorer-space-2);
    padding: 26px var(--explorer-space-2) 18px;
    text-align: center;
  }
  .explorer-item-compact .explorer-item-main > span { display: block; min-width: 0; width: 100%; }
  .explorer-item-compact .explorer-item-main > .tile-artwork {
    display: flex;
    height: 82px;
    width: 88px;
    flex: 0 0 82px;
    align-items: center;
    justify-content: center;
    align-self: center;
    margin-inline: auto;
  }
  .explorer-item-compact .entry-copy {
    width: 100%;
    align-self: stretch;
    text-align: center;
  }
  .explorer-item-compact .entry-name {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    white-space: normal;
    font-size: 0.8125rem;
    font-weight: 500;
    line-height: 1.35;
  }
  .explorer-item-compact .entry-metadata,
  .explorer-item-compact .entry-type,
  .explorer-item-compact .entry-updated,
  .explorer-item-compact .entry-size { display: none; }
  .explorer-item-compact .kebab {
    position: absolute;
    z-index: 2;
    top: 5px;
    right: 4px;
    opacity: 0.78;
    font-size: 1.2rem;
    transition: opacity 120ms ease, background-color 120ms ease, color 120ms ease;
  }
  .explorer-item-compact:hover .kebab,
  .explorer-item-compact:focus-within .kebab { opacity: 1; }
  .tile-selection-indicator {
    position: absolute;
    z-index: 2;
    top: 13px;
    left: 13px;
    display: inline-flex;
    height: 18px;
    width: 18px;
    align-items: center;
    justify-content: center;
    border: 1px solid rgb(var(--foreground-muted) / 0.9);
    border-radius: 999px;
    background: rgb(var(--surface-elevated));
    color: white;
    transition: border-color 120ms ease, background-color 120ms ease, box-shadow 120ms ease;
  }
  .tile-selection-indicator svg { height: 13px; width: 13px; }
  .explorer-item-selected .tile-selection-indicator {
    border-color: rgb(var(--primary));
    background: rgb(var(--primary));
    box-shadow: 0 0 0 3px rgb(var(--primary) / 0.12);
  }
  @media (max-width: 767px) {
    .explorer-item { min-height: 64px; padding-left: 0.625rem; }
    .explorer-item-compact { padding-left: 0; }
    .entry-icon { height: 40px; width: 40px; }
    .explorer-item-main { grid-template-columns: 40px minmax(0, 1fr); min-height: 56px; gap: 0.625rem; }
    .explorer-item-main > span:nth-child(n + 3) { display: none !important; }
  }
  @media (max-width: 767px) { .explorer-item-compact .kebab { opacity: 1; } }
  @media (max-width: 430px) {
    .explorer-item-compact { min-height: 154px; }
    .explorer-item-compact .explorer-item-main { min-height: 152px; padding: 24px 10px 14px; }
    .explorer-item-compact .explorer-item-main > .tile-artwork { height: 70px; width: 76px; flex-basis: 70px; }
  }
  @media (prefers-reduced-motion: reduce) { .explorer-item, .kebab, .explorer-item-compact { transition: none; } }
</style>