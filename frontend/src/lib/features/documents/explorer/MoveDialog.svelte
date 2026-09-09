<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import type { ExplorerItem } from './types';

  interface FolderOption {
    id: string;
    name: string;
    parentId: string | null;
  }
  interface Props {
    item: ExplorerItem;
    folders: FolderOption[];
    saving?: boolean;
    onclose: () => void;
    onconfirm: (folderId: string | null) => void;
  }

  let { item, folders, saving = false, onclose, onconfirm }: Props = $props();
  let destination = $state('');
  let appliedId = $state('');

  $effect(() => {
    if (appliedId !== item.id) {
      appliedId = item.id;
      destination = item.entry.parent_id ?? '';
    }
  });

  function isDescendant(folderId: string, sourceId: string): boolean {
    let current = folders.find((folder) => folder.id === folderId);
    const visited = new Set<string>();
    while (current?.parentId && !visited.has(current.id)) {
      if (current.parentId === sourceId) return true;
      visited.add(current.id);
      current = folders.find((folder) => folder.id === current?.parentId);
    }
    return false;
  }
</script>

<Modal open={true} title={`Mover ${item.kind === 'folder' ? 'carpeta' : 'archivo'}`} {onclose}>
  <form
    class="space-y-4"
    onsubmit={(event) => {
      event.preventDefault();
      if (!saving) onconfirm(destination || null);
    }}
  >
    <label class="block text-sm font-medium text-foreground" for="explorer-move">Destino</label>
    <select
      id="explorer-move"
      bind:value={destination}
      class="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
    >
      <option value="">Documentos generales</option>
      {#each folders.filter((folder) => folder.id !== item.id && !(item.kind === 'folder' && isDescendant(folder.id, item.id))) as folder (folder.id)}
        <option value={folder.id}>{folder.name}</option>
      {/each}
    </select>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button variant="ghost" type="button" onclick={onclose}>Cancelar</Button>
      <Button type="submit" disabled={saving || (destination || null) === item.entry.parent_id}>{saving ? 'Moviendo…' : 'Mover aquí'}</Button>
    </div>
  </form>
</Modal>
