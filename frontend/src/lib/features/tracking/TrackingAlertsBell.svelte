<script lang="ts">
  import { goto } from '$app/navigation';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { ALERT_KIND_LABELS, trackingAlerts } from './alerts.svelte';

  const PREVIEW = 5;
  let open = $state(false);
  let root = $state<HTMLDivElement>();

  const visible = $derived(permissions.hasPermission('tracking:read') && !!company.id);
  const count = $derived(trackingAlerts.unacknowledged);
  const critical = $derived(
    trackingAlerts.items.some((item) => item.severity === 'critical' && !item.acknowledged_at)
  );

  $effect(() => {
    if (!visible) return;
    return trackingAlerts.subscribe();
  });

  $effect(() => {
    // Al cambiar de empresa se consultan sus alertas de inmediato.
    void company.id;
    if (visible) void trackingAlerts.refresh();
  });

  function openTracking(transferId?: string) {
    open = false;
    void goto(transferId ? `/tracking?transfer=${transferId}` : '/tracking?tab=alerts');
  }
</script>

<svelte:window
  onclick={(event) => {
    if (open && root && !root.contains(event.target as Node)) open = false;
  }}
  onkeydown={(event) => {
    if (event.key === 'Escape') open = false;
  }}
/>

{#if visible}
  <div class="bell" bind:this={root}>
    <button
      type="button"
      class="trigger"
      aria-haspopup="true"
      aria-expanded={open}
      aria-label={count ? `${count} alertas de traslados sin reconocer` : 'Alertas de traslados'}
      title="Alertas de traslados"
      onclick={() => (open = !open)}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        ><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path
          d="M10.3 21a1.94 1.94 0 0 0 3.4 0"
        /></svg
      >
      {#if count}<span class="badge" class:critical>{count > 9 ? '9+' : count}</span>{/if}
    </button>
    {#if open}
      <div class="menu" role="dialog" aria-label="Alertas de traslados">
        <header>
          <strong>Alertas de traslados</strong>
          <span>{trackingAlerts.items.length} abiertas</span>
        </header>
        {#if trackingAlerts.items.length}
          <ul>
            {#each trackingAlerts.items.slice(0, PREVIEW) as alert (alert.id)}
              <li class={alert.severity} class:seen={!!alert.acknowledged_at}>
                <button type="button" onclick={() => openTracking(alert.transfer_id)}>
                  <span class="kind"
                    >{ALERT_KIND_LABELS[alert.kind]} · {alert.transfer_code ?? 'Traslado'}</span
                  >
                  <span class="message">{alert.message}</span>
                </button>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="empty">Sin alertas abiertas.</p>
        {/if}
        <button type="button" class="all" onclick={() => openTracking()}
          >Ver todas en Seguimiento</button
        >
      </div>
    {/if}
  </div>
{/if}

<style>
  .bell {
    position: relative;
  }
  .trigger {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    color: rgb(var(--foreground-muted));
  }
  .trigger:hover {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .badge {
    position: absolute;
    top: 2px;
    right: 1px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 999px;
    background: rgb(var(--warning));
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    line-height: 16px;
    text-align: center;
  }
  .badge.critical {
    background: rgb(var(--danger));
  }
  .menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    z-index: 50;
    width: min(340px, calc(100vw - 24px));
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    box-shadow: 0 12px 32px rgb(0 0 0 / 0.18);
  }
  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    padding: 12px 14px 8px;
    font-size: 13px;
  }
  header span,
  .empty {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  ul {
    display: grid;
    gap: 4px;
    margin: 0;
    padding: 0 8px;
    list-style: none;
  }
  li {
    border-left: 3px solid rgb(var(--success));
    border-radius: 6px;
  }
  li.warning {
    border-left-color: rgb(var(--warning));
  }
  li.critical {
    border-left-color: rgb(var(--danger));
  }
  li.seen {
    opacity: 0.65;
  }
  li button {
    display: grid;
    gap: 2px;
    width: 100%;
    padding: 7px 8px;
    border-radius: 0 6px 6px 0;
    text-align: left;
  }
  li button:hover {
    background: rgb(var(--surface-hover));
  }
  .kind {
    font-size: 11px;
    font-weight: 600;
    color: rgb(var(--foreground-muted));
  }
  .message {
    font-size: 12px;
    line-height: 1.4;
  }
  .empty {
    margin: 0;
    padding: 4px 14px 8px;
  }
  .all {
    display: block;
    width: 100%;
    margin-top: 8px;
    padding: 10px 14px;
    border-top: 1px solid rgb(var(--border));
    font-size: 12px;
    font-weight: 600;
    color: rgb(var(--primary));
    text-align: left;
  }
</style>
