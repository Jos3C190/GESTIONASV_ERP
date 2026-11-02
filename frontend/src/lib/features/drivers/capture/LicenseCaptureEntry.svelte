<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { driversApi, type Driver } from '../api';
  import '../drivers-theme.css';
  import LicenseCaptureDialog from './LicenseCaptureDialog.svelte';

  let {
    driver,
    compact = false,
    onconfirmed
  }: { driver: Driver; compact?: boolean; onconfirmed: () => void } = $props();

  const allowed = $derived(permissions.hasPermission('drivers:documents'));
  const label = $derived(
    driver.license.document_id ? 'Actualizar con fotos' : 'Capturar con fotos'
  );
  let available = $state(false);
  let open = $state(false);

  $effect(() => {
    if (!allowed) return;
    driversApi
      .captureCapabilities()
      .then((result) => (available = result.enabled))
      .catch(() => (available = false));
  });
</script>

{#if allowed && available}
  {#if compact}
    <Button class="w-full" onclick={() => (open = true)}>
      <FleetIcon name="camera" size={16} />{label}
    </Button>
  {:else}
    <section class="entry">
      <div>
        <h3>Captura guiada</h3>
        <p>Fotografía el frente y el reverso; propondremos los datos para que los revises.</p>
      </div>
      <Button size="lg" onclick={() => (open = true)}>
        <FleetIcon name="camera" size={16} />{label}
      </Button>
    </section>
  {/if}
  <LicenseCaptureDialog bind:open {driver} onconfirmed={() => onconfirmed()} />
{/if}

<style>
  .entry {
    display: grid;
    gap: 12px;
    margin-bottom: 16px;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
  }
  h3 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 600;
  }
  p {
    margin: 4px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  @media (min-width: 640px) {
    .entry {
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
    }
  }
</style>
