<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import type { ExplorerItem } from './types';

  interface Props {
    item: ExplorerItem;
    saving?: boolean;
    onclose: () => void;
    onconfirm: (name: string) => void;
  }

  let { item, saving = false, onclose, onconfirm }: Props = $props();
  let name = $state('');
  let appliedId = $state('');
  let nameInput: HTMLInputElement | undefined;
  onMount(() => {
    nameInput?.focus();
    nameInput?.select();
  });

  $effect(() => {
    if (appliedId !== item.id) {
      appliedId = item.id;
      name = item.name;
    }
  });

  function submit() {
    const clean = name.trim();
    if (clean && !saving) onconfirm(clean);
  }
</script>

<Modal open={true} title={`Renombrar ${item.kind === 'folder' ? 'carpeta' : 'archivo'}`} {onclose}>
  <form
    class="space-y-4"
    onsubmit={(event) => {
      event.preventDefault();
      submit();
    }}
  >
    <label class="block text-sm font-medium text-foreground" for="explorer-rename"
      >Nuevo nombre</label
    >
    <input
      id="explorer-rename"
      bind:this={nameInput}
      bind:value={name}
      maxlength="200"
      class="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
    />
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button variant="ghost" type="button" onclick={onclose}>Cancelar</Button>
      <Button type="submit" disabled={saving || !name.trim()}
        >{saving ? 'Guardando…' : 'Guardar'}</Button
      >
    </div>
  </form>
</Modal>
