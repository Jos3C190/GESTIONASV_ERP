<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
</script>

<svelte:head><title>Productos — ERP System</title></svelte:head>

<div class="flex flex-col gap-6 p-6 animate-fade-scale">
  <!-- Page header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-foreground">Productos</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Gestión del catálogo de productos de la empresa.
      </p>
    </div>
  </div>

  <!-- Empty state -->
  <Card class="p-12">
    <div class="flex flex-col items-center text-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-5">
        <svg
          width="32"
          height="32"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="text-primary"
          aria-hidden="true"
        >
          <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
      </div>
      <h2 class="text-lg font-semibold text-foreground">Sin productos registrados</h2>
      <p class="mt-2 max-w-sm text-sm text-foreground-muted">
        Aún no se han agregado productos al sistema. Cuando el módulo esté completamente
        implementado, aquí podrás crear, editar y consultar el catálogo de productos.
      </p>
      <div class="mt-6">
        <Button variant="secondary" onclick={() => (window.location.href = '/dashboard')}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Volver al dashboard
        </Button>
      </div>
    </div>
  </Card>
</div>
