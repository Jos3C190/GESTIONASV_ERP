<script lang="ts">
  import Tabs from '#lib/components/ui/Tabs.svelte';
  import PrivacyIncidentsPanel from '#lib/features/privacy/components/PrivacyIncidentsPanel.svelte';
  import PrivacyNoticePanel from '#lib/features/privacy/components/PrivacyNoticePanel.svelte';
  import PrivacyRequestsPanel from '#lib/features/privacy/components/PrivacyRequestsPanel.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const TABS = [
    { id: 'aviso', label: 'Aviso de privacidad' },
    { id: 'solicitudes', label: 'Solicitudes' },
    { id: 'vulneraciones', label: 'Vulneraciones' }
  ];

  let active = $state('aviso');
  const canRead = $derived(permissions.hasPermission('privacy:read'));
  const canManage = $derived(permissions.hasPermission('privacy:manage'));
</script>

<svelte:head>
  <title>Datos personales | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar la protección de datos personales de la empresa.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Administración</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Datos personales
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Cumplimiento de la Ley para la Protección de Datos Personales: el aviso que se informa a los
        clientes, las solicitudes de sus titulares y las vulneraciones de seguridad.
      </p>
    </header>

    <Tabs items={TABS} bind:active />

    {#if active === 'aviso'}
      <PrivacyNoticePanel {canManage} />
    {:else if active === 'solicitudes'}
      <PrivacyRequestsPanel {canManage} />
    {:else}
      <PrivacyIncidentsPanel {canManage} />
    {/if}
  </div>
{/if}
