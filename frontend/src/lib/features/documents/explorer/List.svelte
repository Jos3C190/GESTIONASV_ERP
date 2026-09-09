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
  class="explorer-list overflow-hidden rounded-xl border border-border bg-surface-elevated {rootDropActive ? 'explorer-root-drop-target' : ''}"
  role="list"
  aria-label="Contenido de la carpeta"
  ondragover={onrootdragover}
  ondrop={onrootdrop}
>
  <div class="explorer-list-header hidden min-h-10 items-center gap-4 border-b border-border bg-surface-muted/55 px-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-foreground-subtle sm:flex">
    <span class="min-w-0 flex-1">Nombre</span>
    <span class="min-w-[112px]">Tipo</span>
    <span class="min-w-[144px]">Modificado</span>
    <span class="min-w-[88px] text-right">Tamaño</span>
    <span class="min-w-11"></span>
  </div>
  {#each items as item (item.id)}
    <Item
      {item}
      selected={selectedIds.has(item.id)}
      dropTarget={dropTargetId === item.id}
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
  {/each}
</div>
<style>
  .explorer-root-drop-target { outline: 2px dashed rgb(var(--primary) / 0.55); outline-offset: 3px; }
</style>