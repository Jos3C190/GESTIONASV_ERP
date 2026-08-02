<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
</script>

<svelte:head><title>Proveedores — ERP System</title></svelte:head>

<div class="flex flex-col gap-6 p-6 animate-fade-scale">
  <!-- Page header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-foreground">Proveedores</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Gestión de proveedores y contactos comerciales.
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
          <path d="M3 7l3-3h12l3 3M3 7l3 3h12l3-3M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7" />
        </svg>
      </div>
      <h2 class="text-lg font-semibold text-foreground">Sin proveedores registrados</h2>
      <p class="mt-2 max-w-sm text-sm text-foreground-muted">
        Aún no se han agregado proveedores al sistema. Cuando el módulo esté completamente
        implementado, aquí podrás crear, editar y consultar el directorio de proveedores.
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
