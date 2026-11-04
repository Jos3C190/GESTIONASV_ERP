<script lang="ts">
  import type { CostPeriodId } from './catalog';

  const OPTIONS: { id: CostPeriodId; label: string }[] = [
    { id: 'month', label: 'Este mes' },
    { id: 'last_month', label: 'Mes pasado' },
    { id: 'year', label: 'Este año' }
  ];

  let {
    value,
    withAll = false,
    onselect,
    onall
  }: {
    value: CostPeriodId | 'all' | null;
    withAll?: boolean;
    onselect: (period: CostPeriodId) => void;
    onall?: () => void;
  } = $props();
</script>

<div class="switch" role="group" aria-label="Periodo">
  {#each OPTIONS as option (option.id)}
    <button
      type="button"
      class:active={value === option.id}
      aria-pressed={value === option.id}
      onclick={() => onselect(option.id)}>{option.label}</button
    >
  {/each}
  {#if withAll}
    <button
      type="button"
      class:active={value === 'all'}
      aria-pressed={value === 'all'}
      onclick={() => onall?.()}>Todo</button
    >
  {/if}
</div>

<style>
  .switch {
    display: flex;
    gap: 4px;
    width: fit-content;
    max-width: 100%;
    padding: 3px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    background: rgb(var(--surface));
  }
  button {
    min-height: 44px;
    padding: 0 10px;
    border-radius: 8px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    transition:
      background-color 150ms ease,
      color 150ms ease;
  }
  button:hover {
    color: rgb(var(--foreground));
  }
  .active {
    background: rgb(var(--surface-hover));
    box-shadow: inset 0 0 0 1px rgb(var(--control-border));
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  /* Su borde usa box-shadow y taparía el anillo de foco global. */
  .active:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
</style>
