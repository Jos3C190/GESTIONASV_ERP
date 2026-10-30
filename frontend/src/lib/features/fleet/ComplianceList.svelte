<script lang="ts">
  import type { Compliance } from './api';
  import FleetIcon from './FleetIcon.svelte';

  let { compliance }: { compliance: Compliance } = $props();
  const ordered = $derived(
    [...compliance.issues].sort((a, b) =>
      a.severity === b.severity ? 0 : a.severity === 'blocking' ? -1 : 1
    )
  );
</script>

{#if ordered.length === 0}
  <p class="ok">
    <FleetIcon name="shield" size={15} />Apto para operar: documentos y servicio al día.
  </p>
{:else}
  <ul class="issues">
    {#each ordered as issue, index (index)}
      <li class={issue.severity}>
        <FleetIcon name="alert" size={14} /><span>{issue.message}</span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .ok {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 9px 10px;
    border-radius: 8px;
    background: rgb(var(--success) / 0.08);
    color: rgb(var(--success));
    font-size: 12px;
    font-weight: 550;
  }
  .issues {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: flex;
    align-items: flex-start;
    gap: 7px;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 12px;
    line-height: 1.45;
  }
  li :global(svg) {
    flex-shrink: 0;
    margin-top: 2px;
  }
  .blocking {
    border-color: rgb(var(--danger) / 0.22);
    background: rgb(var(--danger) / 0.07);
    color: rgb(var(--danger));
  }
  .warning {
    border-color: rgb(var(--warning) / 0.25);
    background: rgb(var(--warning) / 0.08);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
</style>
