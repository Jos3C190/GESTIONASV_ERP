<script lang="ts">
  import { OPERATIONAL_META, type OperationalStatus } from './catalog';
  let { status }: { status: OperationalStatus } = $props();
  const meta = $derived(OPERATIONAL_META[status]);
</script>

<span class="vehicle-status {meta.tone}"><span class="dot"></span>{meta.label}</span>

<style>
  .vehicle-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 5px;
    padding: 4px 7px;
    font-size: 12px;
    line-height: 1.25;
    font-weight: 550;
    white-space: nowrap;
  }
  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
  }
  .route {
    color: rgb(var(--fleet-route-ink, var(--primary)));
    background: rgb(var(--primary) / 0.08);
  }
  .available {
    color: rgb(var(--success));
    background: rgb(var(--success) / 0.08);
  }
  .maintenance {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    background: rgb(var(--warning) / 0.09);
  }
  .muted {
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-hover));
  }
</style>
