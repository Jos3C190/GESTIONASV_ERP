<script lang="ts">
  import { page } from '$app/state';
  import DocumentFolderView from '$lib/features/documents/components/DocumentFolderView.svelte';

  let categoryId = $derived(page.params.categoryId);
</script>

<DocumentFolderView scope="category" {categoryId} categoryModule="general" />
