<script lang="ts">
  import type { TrackingAlertOut } from '$lib/api/client';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { ALERT_KIND_LABELS } from './alerts.svelte';
  import { timeAgo } from './tracking';

  let {
    alerts,
    now,
    monitorActive = true,
    error = null,
    onopen,
    onacknowledge
  }: {
    alerts: TrackingAlertOut[];
    now: number;
    monitorActive?: boolean;
    error?: string | null;
    onopen: (alert: TrackingAlertOut) => void;
    onacknowledge: (alert: TrackingAlertOut) => void;
  } = $props();

  let busy = $state<string | null>(null);

  async function acknowledge(alert: TrackingAlertOut) {
    busy = alert.id;
    try {
      await onacknowledge(alert);
    } finally {
      busy = null;
    }
  }
</script>

<div class="content">
  {#if !monitorActive}
    <p class="note warn">
      <FleetIcon name="alert" size={13} />El servidor GPS no está configurado: no se generan
      alertas.
    </p>
  {/if}
  {#if error}<p class="note warn" role="alert">{error}</p>{/if}
  <ul class="alerts">
    {#each alerts as alert (alert.id)}
      <li class={alert.severity} class:acknowledged={!!alert.acknowledged_at}>
        <button type="button" class="body" onclick={() => onopen(alert)}>
          <span class="head">
            <span class="kind">{ALERT_KIND_LABELS[alert.kind]}</span>
            <span class="time">{timeAgo(new Date(alert.opened_at), now)}</span>
          </span>
          <strong>{alert.message}</strong>
          <span class="meta"
            >{alert.transfer_code ?? 'Traslado'}{alert.vehicle_code
              ? ` · ${alert.vehicle_code}`
              : ''}</span
          >
        </button>
        {#if alert.acknowledged_at}
          <span class="seen" title="Reconocida"><FleetIcon name="check" size={13} /></span>
        {:else}
          <button
            type="button"
            class="ack"
            disabled={busy === alert.id}
            onclick={() => acknowledge(alert)}>Reconocer</button
          >
        {/if}
      </li>
    {:else}
      <li class="empty">
        Sin alertas abiertas. Aquí aparecen llegadas, retrasos, paradas largas, desvíos y pérdida de
        señal de los traslados en ruta.
      </li>
    {/each}
  </ul>
</div>

<style>
  .content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 8px 6px;
  }
  .note {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 8px 8px;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 11px;
    line-height: 1.4;
  }
  .note.warn {
    background: rgb(var(--warning) / 0.08);
    color: rgb(var(--warning));
  }
  .alerts {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 10px 8px 10px 12px;
    border-left: 3px solid rgb(var(--primary));
    border-radius: 8px;
    background: rgb(var(--surface-hover) / 0.6);
  }
  li.critical {
    border-left-color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.06);
  }
  li.warning {
    border-left-color: rgb(var(--warning));
    background: rgb(var(--warning) / 0.07);
  }
  li.info {
    border-left-color: rgb(var(--success));
    background: rgb(var(--success) / 0.06);
  }
  li.acknowledged {
    opacity: 0.7;
  }
  .body {
    display: grid;
    flex: 1;
    gap: 3px;
    min-width: 0;
    text-align: left;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .kind {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  strong {
    font-size: 12px;
    font-weight: 500;
    line-height: 1.4;
  }
  .meta {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .ack {
    flex-shrink: 0;
    padding: 4px 8px;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    background: rgb(var(--surface));
    font-size: 11px;
    font-weight: 500;
  }
  .ack:disabled {
    opacity: 0.5;
  }
  .seen {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    color: rgb(var(--success));
  }
  .empty {
    display: block;
    padding: 24px 12px;
    border: 0;
    background: none;
    font-size: 12px;
    line-height: 1.5;
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
</style>
