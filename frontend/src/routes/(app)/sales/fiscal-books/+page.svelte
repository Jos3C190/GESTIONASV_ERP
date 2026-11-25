<script lang="ts">
  import FiscalBooksPage from '#lib/features/fiscal-books/FiscalBooksPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const canRead = $derived(permissions.hasPermission('fiscal_books:read'));
  const canManage = $derived(permissions.hasPermission('fiscal_books:manage'));
</script>

<svelte:head>
  <title>Libros de IVA | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar los libros de IVA.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Libros de IVA
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Libros de ventas a contribuyentes, a consumidores y de compras del mes, con los anexos de la
        declaración de IVA (F-07) listos para cargar en el portal de Hacienda. Salen de los
        documentos sellados y de las compras con su documento del proveedor.
      </p>
    </header>
    <FiscalBooksPage {canManage} />
  </div>
{/if}
