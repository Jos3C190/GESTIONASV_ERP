<script lang="ts">
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { timeAgo } from './tracking';
  import type { TransferSummary, TransferTrack } from './transfers';

  let {
    transfers,
    selectedId = null,
    loading = false,
    error = null,
    now,
    onselect
  }: {
    transfers: (TransferSummary | TransferTrack)[];
    selectedId?: string | null;
    loading?: boolean;
    error?: string | null;
    now: number;
    onselect: (id: string) => void;
  } = $props();

  const progressOf = (transfer: TransferSummary | TransferTrack) =>
    'progress' in transfer ? transfer.progress : null;
</script>

<div class="toolbar">
  <span>{transfers.length} en tránsito</span>
</div>
{#if error}<p class="error">{error}</p>{/if}
<ul class="list">
  {#each transfers as transfer (transfer.id)}
    {@const progress = progressOf(transfer)}
    <li>
      <button
        type="button"
        class="row"
        class:selected={transfer.id === selectedId}
        aria-pressed={transfer.id === selectedId}
        onclick={() => onselect(transfer.id)}
      >
        <span class="head">
          <strong>{transfer.code}</strong>
          <span class:incident={transfer.status === 'incident'}
            >{transfer.status === 'incident' ? 'Con incidencia' : 'En tránsito'}</span
          >
        </span>
        <span class="route">
          <span class="dot origin"></span>{transfer.origin.branch}
        </span>
        <span class="route">
          <span class="dot destination"></span>{transfer.destination.branch}
        </span>
        <span class="meta">
          <FleetIcon name="truck" size={13} />{transfer.vehicleCode ?? 'Sin vehículo'}
          {#if transfer.dispatchedAt}· salió {timeAgo(transfer.dispatchedAt, now)}{/if}
        </span>
        {#if progress !== null}
          <span class="bar" aria-hidden="true"
            ><span style:width="{Math.round(progress * 100)}%"></span></span
          >
        {/if}
      </button>
    </li>
  {:else}
    <li class="empty">
      {loading ? 'Buscando traslados…' : 'No hay traslados en tránsito en este momento.'}
    </li>
  {/each}
</ul>

<style>
  .toolbar {
    padding: 10px 12px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .list {
    flex: 1;
    overflow-y: auto;
    margin: 0;
    padding: 0 6px 6px;
    list-style: none;
  }
  .row {
    display: grid;
    gap: 5px;
    width: 100%;
    padding: 10px;
    border-radius: 9px;
    text-align: left;
  }
  .row:hover {
    background: rgb(var(--surface-hover));
  }
  .row.selected {
    background: rgb(var(--primary) / 0.1);
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .head strong {
    font:
      600 12px 'Geist Mono',
      monospace;
  }
  .head span {
    font-size: 11px;
    font-weight: 550;
    color: rgb(var(--primary));
  }
  .head span.incident {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .route {
    display: flex;
    align-items: center;
    gap: 7px;
    overflow: hidden;
    font-size: 12px;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .dot {
    flex-shrink: 0;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #0f172a;
  }
  .dot.destination {
    background: #16a34a;
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .bar {
    height: 4px;
    overflow: hidden;
    border-radius: 4px;
    background: rgb(var(--border));
  }
  .bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: rgb(var(--primary));
  }
  .empty {
    padding: 24px 12px;
    text-align: center;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .error {
    padding: 0 12px 8px;
    font-size: 12px;
    color: rgb(var(--danger));
  }
  button:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
</style>
