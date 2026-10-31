<script lang="ts">
  import Item from './Item.svelte';
  import type { ExplorerItem } from './types';

  interface Props {
    items: ExplorerItem[];
    selectedIds: Set<string>;
    canRename: boolean;
    canMove: boolean;
    canDelete: boolean;
    canRestore: boolean;
    dropTargetId: string | null;
    rootDropActive: boolean;
    onselect: (item: ExplorerItem, event: MouseEvent) => void;
    onopen: (item: ExplorerItem) => void;
    oncontextmenu: (item: ExplorerItem, event: MouseEvent | PointerEvent) => void;
    ondragstart: (item: ExplorerItem, event: DragEvent) => void;
    ondragend: () => void;
    ondragover: (item: ExplorerItem, event: DragEvent) => void;
    ondrop: (item: ExplorerItem, event: DragEvent) => void;
    onrootdragover: (event: DragEvent) => void;
    onrootdrop: (event: DragEvent) => void;
    onkeydown: (item: ExplorerItem, event: KeyboardEvent) => void;
    contextItemId: string | null;
    focusedItemId: string | null;
  }

  let {
    items,
    selectedIds,
    canRename,
    canMove,
    canDelete,
    canRestore,
    dropTargetId,
    rootDropActive,
    onselect,
    onopen,
    oncontextmenu,
    ondragstart,
    ondragend,
    ondragover,
    ondrop,
    onrootdragover,
    onrootdrop,
    onkeydown,
    contextItemId,
    focusedItemId
  }: Props = $props();
</script>

<div
  class="explorer-list overflow-hidden rounded-xl border border-border bg-surface-elevated {rootDropActive ? 'explorer-root-drop-target' : ''}"
  role="list"
  aria-label="Contenido de la carpeta"
  ondragover={onrootdragover}
  ondrop={onrootdrop}
>
  <div class="explorer-list-header" aria-hidden="true">
    <span aria-hidden="true"></span>
    <span>Nombre</span>
    <span>Tipo</span>
    <span>Modificado</span>
    <span class="text-right">Tamaño</span>
    <span aria-hidden="true"></span>
  </div>
  <div class="explorer-list-content">
  {#each items as item, index (item.id)}
    <Item
      {item}
      selected={selectedIds.has(item.id)}
      dropTarget={dropTargetId === item.id}
      {canRename}
      {canMove}
      {canDelete}
      {canRestore}
      tabIndex={focusedItemId ? (focusedItemId === item.id ? 0 : -1) : index === 0 ? 0 : -1}
      position={index + 1}
      setSize={items.length}
      {onselect}
      {onopen}
      {oncontextmenu}
      {ondragstart}
      {ondragend}
      {ondragover}
      {ondrop}
      {onkeydown}
    contextOpen={contextItemId === item.id}
    />
  {/each}
  </div>
</div>
<style>
  .explorer-list-header {
    border-bottom: 1px solid rgb(var(--border));
    background: rgb(var(--surface-muted) / 0.42);
    display: grid;
    min-height: 2.5rem;
    grid-template-columns: 34px minmax(0, 1fr) 112px 144px 88px 44px;
    align-items: center;
    gap: var(--explorer-space-2);
    padding: 0 0.5rem 0 0.875rem;
    color: rgb(var(--foreground-subtle));
    font-size: 0.75rem;
    font-weight: 650;
    letter-spacing: 0.01em;
  }
  .explorer-root-drop-target { outline: 2px dashed rgb(var(--primary) / 0.55); outline-offset: 3px; }
  @media (max-width: 767px) { .explorer-list-header { display: none; } }
</style>