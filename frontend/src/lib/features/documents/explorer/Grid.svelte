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
    onkeydown
  }: Props = $props();
</script>

<div
  class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 {rootDropActive ? 'explorer-root-drop-target' : ''}"
  role="list"
  aria-label="Contenido de la carpeta"
  ondragover={onrootdragover}
  ondrop={onrootdrop}
>
  {#each items as item (item.id)}
    <div class="overflow-hidden rounded-xl border border-border bg-surface-elevated shadow-sm">
      <Item
        {item}
        selected={selectedIds.has(item.id)}
        dropTarget={dropTargetId === item.id}
        compact
        {canRename}
        {canMove}
        {canDelete}
        {canRestore}
        {onselect}
        {onopen}
        {oncontextmenu}
        {ondragstart}
        {ondragend}
        {ondragover}
        {ondrop}
        {onkeydown}
      />
    </div>
  {/each}
</div>
<style>
  .explorer-root-drop-target { outline: 2px dashed rgb(var(--primary) / 0.55); outline-offset: 3px; }
</style>