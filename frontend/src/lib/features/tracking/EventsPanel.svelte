<script lang="ts">
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { EVENT_GROUPS, type EventGroup, type TrackingEvent } from './events';
  import { timeAgo } from './tracking';

  let {
    events,
    now,
    focusedId = null,
    onfocus
  }: {
    events: TrackingEvent[];
    now: number;
    focusedId?: string | null;
    onfocus: (event: TrackingEvent) => void;
  } = $props();

  let group = $state<'all' | EventGroup>('all');

  const ICONS: Record<EventGroup, 'pin' | 'fuel' | 'power' | 'alert' | 'clock'> = {
    geofence: 'pin',
    speed: 'alert',
    engine: 'power',
    alarm: 'alert',
    stop: 'clock'
  };

  const visible = $derived(
    group === 'all'
      ? events
      : events.filter(
          (event) => event.group === group || (group === 'alarm' && event.group === 'stop')
        )
  );
</script>

<div class="filters" role="group" aria-label="Filtrar eventos">
  {#each EVENT_GROUPS as item (item.id)}
    <button
      type="button"
      class:active={group === item.id}
      aria-pressed={group === item.id}
      onclick={() => (group = item.id)}>{item.label}</button
    >
  {/each}
</div>
<ul class="list">
  {#each visible as event (event.id)}
    <li>
      <button
        type="button"
        class="row"
        class:focused={focusedId === event.id}
        disabled={event.latitude === null}
        onclick={() => onfocus(event)}
      >
        <span class="icon {event.tone}"><FleetIcon name={ICONS[event.group]} size={15} /></span>
        <span class="main">
          <strong>{event.title}</strong>
          <span>{event.vehicleName}{event.detail ? ` · ${event.detail}` : ''}</span>
        </span>
        <time datetime={event.time.toISOString()}>{timeAgo(event.time, now)}</time>
      </button>
    </li>
  {:else}
    <li class="empty">Sin eventos en las últimas 24 horas.</li>
  {/each}
</ul>

<style>
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 12px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .filters button {
    padding: 4px 8px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .filters button.active {
    border-color: rgb(var(--foreground));
    background: rgb(var(--foreground));
    color: rgb(var(--surface));
  }
  .list {
    flex: 1;
    overflow-y: auto;
    margin: 0;
    padding: 6px;
    list-style: none;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 8px;
    border-radius: 9px;
    text-align: left;
  }
  .row:hover:not(:disabled),
  .row.focused {
    background: rgb(var(--surface-hover));
  }
  .row:disabled {
    cursor: default;
  }
  .icon {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgb(var(--primary) / 0.12);
    color: rgb(var(--primary));
  }
  .icon.success {
    background: rgb(var(--success) / 0.12);
    color: rgb(var(--success));
  }
  .icon.warning {
    background: rgb(var(--warning) / 0.14);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .icon.danger {
    background: rgb(var(--danger) / 0.12);
    color: rgb(var(--danger));
  }
  .main {
    display: grid;
    flex: 1;
    gap: 2px;
    min-width: 0;
  }
  .main strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
    font-weight: 600;
  }
  .main span,
  time {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  time {
    flex-shrink: 0;
  }
  .empty {
    padding: 24px 12px;
    text-align: center;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  button:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
</style>
