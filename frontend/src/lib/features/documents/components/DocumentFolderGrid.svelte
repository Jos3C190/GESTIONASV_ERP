<script lang="ts">
  import type { DocumentFolderOut } from '$lib/api/client';
  import DocumentFolderCard from './DocumentFolderCard.svelte';

  interface Props {
    folders: DocumentFolderOut[];
    loading?: boolean;
    hrefFor: (folder: DocumentFolderOut) => string;
    emptyTitle?: string;
    emptyDescription?: string;
  }

  let {
    folders,
    loading = false,
    hrefFor,
    emptyTitle = 'No hay carpetas para mostrar',
    emptyDescription = 'Cuando existan elementos autorizados aparecerán aquí.'
  }: Props = $props();
</script>

{#if loading}
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
    {#each [1, 2, 3, 4, 5, 6] as item (item)}
      <div class="skeleton h-[148px] rounded-2xl border border-border" aria-hidden="true"></div>
    {/each}
  </div>
{:else if folders.length === 0}
  <div class="rounded-2xl border border-dashed border-border px-6 py-12 text-center">
    <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted" aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
        <path d="M3.5 9h17" />
      </svg>
    </div>
    <p class="mt-3 text-sm font-medium text-foreground">{emptyTitle}</p>
    <p class="mt-1 text-xs text-foreground-muted">{emptyDescription}</p>
  </div>
{:else}
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Carpetas">
    {#each folders as folder (folder.id)}
      <DocumentFolderCard {folder} href={hrefFor(folder)} />
    {/each}
  </div>
{/if}
