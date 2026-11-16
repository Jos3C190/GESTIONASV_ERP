<script lang="ts">
  import Tabs from '$lib/components/ui/Tabs.svelte';
  import FiscalActivitiesPanel from '$lib/features/fiscal/components/FiscalActivitiesPanel.svelte';
  import FiscalDocumentsPanel from '$lib/features/fiscal/components/FiscalDocumentsPanel.svelte';
  import FiscalEstablishmentsPanel from '$lib/features/fiscal/components/FiscalEstablishmentsPanel.svelte';
  import FiscalProfilePanel from '$lib/features/fiscal/components/FiscalProfilePanel.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  const TABS = [
    { id: 'emisor', label: 'Emisor' },
    { id: 'actividades', label: 'Actividades' },
    { id: 'establecimientos', label: 'Establecimientos y cajas' },
    { id: 'documentos', label: 'Documentos' }
  ];

  let active = $state('emisor');
  const canRead = $derived(permissions.hasPermission('fiscal_settings:read'));
  const canManage = $derived(permissions.hasPermission('fiscal_settings:manage'));
</script>

<svelte:head>
  <title>Configuración fiscal | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar la configuración fiscal de la empresa.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Configuración fiscal
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Datos con los que la empresa emite sus documentos tributarios electrónicos: perfil de
        emisor, actividades económicas, establecimientos con sus cajas y documentos habilitados.
      </p>
    </header>

    <Tabs items={TABS} bind:active />

    {#if active === 'emisor'}
      <FiscalProfilePanel {canManage} />
    {:else if active === 'actividades'}
      <FiscalActivitiesPanel {canManage} />
    {:else if active === 'establecimientos'}
      <FiscalEstablishmentsPanel {canManage} />
    {:else}
      <FiscalDocumentsPanel {canManage} />
    {/if}
  </div>
{/if}
