<script lang="ts">
  import { page } from '$app/state';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  let moduleName = $derived(page.url.searchParams.get('module') ?? 'Módulo');
</script>

<svelte:head><title>{moduleName} — GestionaSV</title></svelte:head>

<div class="flex min-h-full items-center justify-center p-6">
  <div class="w-full max-w-lg animate-fade-scale">
    <Card class="p-8">
      <div class="flex flex-col items-center text-center">
        <div class="relative mb-6">
          <div class="flex h-20 w-20 items-center justify-center rounded-3xl bg-primary/10">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-primary" aria-hidden="true">
              <path d="M12 6v6l4 2" /><circle cx="12" cy="12" r="9" />
            </svg>
          </div>
        </div>
        <h2 class="text-xl font-bold text-foreground">{moduleName}</h2>
        <p class="mt-2 text-sm text-foreground-muted">
          Este módulo está en desarrollo. Estará disponible próximamente en GestionaSV.
        </p>
        <div class="mt-8">
          <Button onclick={() => (window.location.href = '/dashboard')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
            Volver al dashboard
          </Button>
        </div>
      </div>
    </Card>
  </div>
</div>
