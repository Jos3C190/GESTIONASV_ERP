<script lang="ts">
  import { onMount } from 'svelte';
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

  const MIN_TILE_WIDTH = 168;
  const GRID_GAP = 16;

  let gridElement = $state<HTMLDivElement | undefined>(undefined);
  let gridColumns = $state(1);

  const rows = $derived.by(() => {
    const result: ExplorerItem[][] = [];
    for (let index = 0; index < items.length; index += gridColumns) {
      result.push(items.slice(index, index + gridColumns));
    }
    return result;
  });

  onMount(() => {
    const updateColumns = (width: number) => {
      gridColumns = Math.max(1, Math.floor((width + GRID_GAP) / (MIN_TILE_WIDTH + GRID_GAP)));
    };
    if (!gridElement) return;
    updateColumns(gridElement.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => updateColumns(entry?.contentRect.width ?? 0));
    observer.observe(gridElement);
    return () => observer.disconnect();
  });
</script>

<div
  bind:this={gridElement}
  class="explorer-grid {rootDropActive ? 'explorer-root-drop-target' : ''}"
  role="grid"
  tabindex="-1"
  aria-multiselectable="true"
  aria-colcount={gridColumns}
  aria-label="Contenido de la carpeta"
  aria-rowcount={rows.length}
  ondragover={onrootdragover}
  ondrop={onrootdrop}
>
  {#each rows as row, rowIndex (row[0]?.id ?? rowIndex)}
    <div
      role="row"
      aria-rowindex={rowIndex + 1}
      class="explorer-grid-row"
      style={`--explorer-grid-columns: ${gridColumns}`}
    >
      {#each row as item, index (item.id)}
        <Item
          {item}
          selected={selectedIds.has(item.id)}
          dropTarget={dropTargetId === item.id}
          compact
          {canRename}
          {canMove}
          {canDelete}
          {canRestore}
          tabIndex={focusedItemId ? (focusedItemId === item.id ? 0 : -1) : index === 0 && rowIndex === 0 ? 0 : -1}
          position={rowIndex * gridColumns + index + 1}
          setSize={items.length}
          semantics="gridcell"
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
  {/each}
</div>

<style>
  .explorer-grid { display: grid; gap: var(--explorer-space-3); }
  .explorer-grid-row { display: grid; grid-template-columns: repeat(var(--explorer-grid-columns), minmax(0, 1fr)); gap: var(--explorer-space-3); }
  .explorer-root-drop-target { outline: 2px dashed rgb(var(--primary) / 0.55); outline-offset: 3px; }
</style>