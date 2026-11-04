<script lang="ts">
  import type { Snippet } from 'svelte';
  import FleetIcon from '../FleetIcon.svelte';

  let { warn = false, children }: { warn?: boolean; children: Snippet } = $props();
</script>

<div class="notice" class:warn>
  <FleetIcon name={warn ? 'alert' : 'info'} size={16} />
  <p>{@render children()}</p>
</div>

<style>
  .notice {
    display: flex;
    gap: 10px;
    padding: 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface-muted));
    font-size: 14px;
  }
  .warn {
    border-color: rgb(var(--warning) / 45%);
    background: rgb(var(--warning) / 10%);
  }
  .notice :global(svg) {
    flex: none;
    margin-top: 2px;
  }
  p {
    margin: 0;
  }
  p :global(a) {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
</style>
