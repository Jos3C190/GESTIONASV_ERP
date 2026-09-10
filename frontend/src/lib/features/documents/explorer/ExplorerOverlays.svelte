<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import DocumentUploadQueue from '$lib/features/documents/components/DocumentUploadQueue.svelte';
  import DocumentFolderImportDialog from '$lib/features/documents/import/DocumentFolderImportDialog.svelte';
  import type { DocumentCategoryOut } from '$lib/api/client';
  import ContextMenu from './ContextMenu.svelte';
  import MoveDialog from './MoveDialog.svelte';
  import RenameDialog from './RenameDialog.svelte';
  import type { ExplorerItem } from './types';

  interface FolderOption {
    id: string;
    name: string;
    parentId: string | null;
  }
  interface ContextState {
    item: ExplorerItem;
    x: number;
    y: number;
  }
  interface Props {
    context: ContextState | null;
    renameItem: ExplorerItem | null;
    moveItem: ExplorerItem | null;
    deleteConfirmItem: ExplorerItem | null;
    createOpen: boolean;
    createName: string;
    createSaving: boolean;
    createAttempted: boolean;
    uploadOpen: boolean;
    folderImportOpen: boolean;
    folderImportBusy: boolean;
    folderId: string | null;
    folders: FolderOption[];
    categories: DocumentCategoryOut[];
    mutationBusy: boolean;
    canFolder: boolean;
    canRenameFiles: boolean;
    canMove: boolean;
    canDeleteFiles: boolean;
    canRestore: boolean;
    onopen: (item: ExplorerItem) => void;
    onrename: (item: ExplorerItem) => void;
    onmove: (item: ExplorerItem) => void;
    ondelete: (item: ExplorerItem) => void;
    onrestore: (item: ExplorerItem) => void;
    oncontextclose: () => void;
    onrenameclose: () => void;
    onrenameconfirm: (name: string) => void | Promise<void>;
    onmoveclose: () => void;
    onmoveconfirm: (folderId: string | null) => void | Promise<void>;
    ondeleteclose: () => void;
    ondeleteconfirm: () => void | Promise<void>;
    oncreateclose: () => void;
    oncreateNameChange: (value: string) => void;
    oncreateAttempted: () => void;
    oncreate: () => void | Promise<void>;
    onuploadclose: () => void;
    onuploadfinished: () => void | Promise<void>;
    onfolderimportclose: () => void;
    onfolderimportbusy: (busy: boolean) => void;
    onfolderimportfinished: (rootEntryId: string | null) => void | Promise<void>;
  }

  let {
    context,
    renameItem,
    moveItem,
    deleteConfirmItem,
    createOpen,
    createName,
    createSaving,
    createAttempted,
    uploadOpen,
    folderImportOpen,
    folderImportBusy,
    folderId,
    folders,
    categories,
    mutationBusy,
    canFolder,
    canRenameFiles,
    canMove,
    canDeleteFiles,
    canRestore,
    onopen,
    onrename,
    onmove,
    ondelete,
    onrestore,
    oncontextclose,
    onrenameclose,
    onrenameconfirm,
    onmoveclose,
    onmoveconfirm,
    ondeleteclose,
    ondeleteconfirm,
    oncreateclose,
    oncreateNameChange,
    oncreateAttempted,
    oncreate,
    onuploadclose,
    onuploadfinished,
    onfolderimportclose,
    onfolderimportbusy,
    onfolderimportfinished
  }: Props = $props();
</script>

{#if context}
  <ContextMenu
    item={context.item}
    x={context.x}
    y={context.y}
    canRename={context.item.kind === 'folder' ? canFolder : canRenameFiles}
    {canMove}
    canDelete={context.item.kind === 'folder' ? canFolder : canDeleteFiles}
    {canRestore}
    onopen={() => { onopen(context!.item); }}
    onrename={() => { onrename(context!.item); }}
    onmove={() => { onmove(context!.item); }}
    ondelete={() => { ondelete(context!.item); }}
    onrestore={() => { onrestore(context!.item); }}
    onclose={oncontextclose}
  />
{/if}

{#if renameItem}
  <RenameDialog
    item={renameItem}
    saving={mutationBusy}
    onclose={onrenameclose}
    onconfirm={onrenameconfirm}
  />
{/if}

{#if moveItem}
  <MoveDialog
    item={moveItem}
    {folders}
    saving={mutationBusy}
    onclose={onmoveclose}
    onconfirm={onmoveconfirm}
  />
{/if}

{#if createOpen}
  <Modal open={true} title="Nueva carpeta" onclose={oncreateclose}>
    {#snippet children()}
      <form
        class="space-y-4"
        onsubmit={(event) => {
          event.preventDefault();
          void oncreate();
        }}
      >
        <label class="block text-sm font-medium text-foreground" for="new-general-folder">Nombre de la carpeta</label>
        <input
          id="new-general-folder"
          value={createName}
          maxlength="200"
          aria-invalid={createAttempted && !createName.trim()}
          aria-describedby={createAttempted && !createName.trim() ? 'new-general-folder-error' : undefined}
          oninput={(event) => oncreateNameChange((event.currentTarget as HTMLInputElement).value)}
          onblur={oncreateAttempted}
          class="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        {#if createAttempted && !createName.trim()}
          <p id="new-general-folder-error" class="mt-1 text-xs text-danger" role="alert">Escribe un nombre para la carpeta.</p>
        {/if}
        <div class="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" type="button" onclick={oncreateclose}>Cancelar</Button>
          <Button type="submit" disabled={createSaving || !createName.trim()}>{createSaving ? 'Creando…' : 'Crear carpeta'}</Button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if deleteConfirmItem}
  <Modal open={true} title="Enviar a la Papelera" onclose={ondeleteclose}>
    {#snippet children()}
      <div class="space-y-4">
        <p class="text-sm leading-6 text-foreground-muted">
          ¿Quieres enviar <strong class="font-semibold text-foreground">«{deleteConfirmItem.name}»</strong>
          a la Papelera? {deleteConfirmItem.kind === 'folder'
            ? 'Se incluirá todo su contenido y podrás restaurarlo como un árbol completo.'
            : 'El documento y sus versiones se conservarán para restaurarlo después.'}
        </p>
        <div class="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" type="button" onclick={ondeleteclose}>Cancelar</Button>
          <Button variant="danger" type="button" disabled={mutationBusy} onclick={() => void ondeleteconfirm()}>
            {mutationBusy ? 'Enviando…' : 'Enviar a la Papelera'}
          </Button>
        </div>
      </div>
    {/snippet}
  </Modal>
{/if}

{#if uploadOpen}
  <Modal open={true} title="Cargar documentos" size="lg" onclose={onuploadclose}>
    {#snippet children()}
      <DocumentUploadQueue
        {categories}
        {folderId}
        onclose={onuploadclose}
        onfinished={onuploadfinished}
      />
    {/snippet}
  </Modal>
{/if}

{#if folderImportOpen}
  <Modal open={true} title="Importar carpeta" size="lg" onclose={onfolderimportclose} preventClose={folderImportBusy} mobileFullScreen>
    {#snippet children()}
      <DocumentFolderImportDialog
        {categories}
        parentId={folderId}
        onclose={onfolderimportclose}
        onfinished={onfolderimportfinished}
        onbusychange={onfolderimportbusy}
      />
    {/snippet}
  </Modal>
{/if}
