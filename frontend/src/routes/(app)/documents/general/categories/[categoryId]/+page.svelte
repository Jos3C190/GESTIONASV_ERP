<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';

  $effect(() => {
    const categoryId = page.params.categoryId;
    if (categoryId) {
      void goto('/documents/general?category=' + encodeURIComponent(categoryId), {
        replaceState: true,
        noScroll: true
      });
    }
  });
</script>

<svelte:head><title>Documentos generales · GestionaSV</title></svelte:head>

<div class="flex min-h-72 items-center justify-center text-sm text-foreground-muted" role="status">
  Aplicando filtro de categoría…
</div>
