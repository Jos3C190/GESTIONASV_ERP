<script lang="ts">
  import { onMount } from 'svelte';

  export interface ExplorerFilterOption {
    value: string;
    label: string;
  }

  interface Props {
    id: string;
    label: string;
    value: string;
    options: ExplorerFilterOption[];
    onselect: (value: string) => void;
  }

  let { id, label, value, options, onselect }: Props = $props();
  let open = $state(false);
  let activeIndex = $state(0);
  let root: HTMLDivElement;
  let trigger: HTMLButtonElement;

  let selected = $derived(options.find((option) => option.value === value) ?? options[0]);

  $effect(() => {
    const selectedIndex = options.findIndex((option) => option.value === value);
    activeIndex = selectedIndex >= 0 ? selectedIndex : 0;
  });

  function close() {
    open = false;
  }

  function choose(option: ExplorerFilterOption) {
    onselect(option.value);
    close();
    requestAnimationFrame(() => trigger?.focus());
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (open) {
        event.preventDefault();
        close();
      }
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) open = true;
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      activeIndex = (activeIndex + direction + options.length) % options.length;
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) {
        open = true;
        return;
      }
      const option = options[activeIndex];
      if (option) choose(option);
      return;
    }

    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      activeIndex = event.key === 'Home' ? 0 : Math.max(options.length - 1, 0);
    }
  }

  onMount(() => {
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (root && !root.contains(event.target as Node)) close();
    };
    document.addEventListener('pointerdown', closeOnOutsidePointer);
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer);
  });
</script>

<div bind:this={root} class="explorer-filter relative">
  <span class="explorer-filter-label" id={`${id}-label`}>{label}</span>
  <button
    bind:this={trigger}
    type="button"
    role="combobox"
    class="explorer-filter-trigger"
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls={`${id}-listbox`}
    aria-activedescendant={open ? `${id}-option-${activeIndex}` : undefined}
    aria-labelledby={`${id}-label ${id}-value`}
    onclick={() => (open = !open)}
    onkeydown={handleKeydown}
  >
    <span id={`${id}-value`} class="truncate">{selected?.label ?? 'Seleccionar'}</span>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
      <path d="m7 10 5 5 5-5" />
    </svg>
  </button>

  {#if open}
    <div
      id={`${id}-listbox`}
      class="explorer-filter-menu"
      role="listbox"
      aria-labelledby={`${id}-label`}
      tabindex="-1"
    >
      {#each options as option, index (option.value)}
        <button
          type="button"
          id={`${id}-option-${index}`}
          tabindex="-1"
          role="option"
          aria-selected={option.value === value}
          class:explorer-filter-option-active={index === activeIndex}
          class:explorer-filter-option-selected={option.value === value}
          onclick={() => choose(option)}
          onpointerenter={() => (activeIndex = index)}
        >
          <span>{option.label}</span>
          {#if option.value === value}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
              <path d="m5 12 4 4L19 6" />
            </svg>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .explorer-filter {
    display: inline-flex;
    min-width: 7.5rem;
    align-items: center;
    gap: var(--explorer-space-1);
    border: 1px solid rgb(var(--border));
    border-radius: var(--explorer-radius-md);
    background: rgb(var(--surface));
    padding: var(--explorer-space-0) var(--explorer-space-0) var(--explorer-space-0) var(--explorer-space-1);
    color: rgb(var(--foreground-muted));
    transition: border-color 140ms ease, background-color 140ms ease, box-shadow 140ms ease;
  }
  .explorer-filter:focus-within {
    border-color: rgb(var(--primary) / 0.7);
    box-shadow: 0 0 0 2px rgb(var(--surface)), 0 0 0 4px rgb(var(--primary));
  }
  .explorer-filter-label {
    flex: 0 0 auto;
    font-size: 0.6875rem;
    font-weight: 650;
    letter-spacing: 0.01em;
    color: rgb(var(--foreground-muted));
  }
  .explorer-filter-trigger {
    display: inline-flex;
    min-height: var(--explorer-control-height);
    min-width: 4.5rem;
    flex: 1;
    align-items: center;
    justify-content: space-between;
    gap: var(--explorer-space-1);
    border-radius: var(--explorer-radius-sm);
    padding: 0 var(--explorer-space-0);
    text-align: left;
    font-size: 0.8125rem;
    font-weight: 600;
    color: rgb(var(--foreground));
  }
  .explorer-filter-trigger:hover { background: rgb(var(--surface-hover)); }
  .explorer-filter-trigger:focus-visible { outline: none; box-shadow: 0 0 0 2px rgb(var(--surface)), 0 0 0 4px rgb(var(--primary)); }
  .explorer-filter-menu {
    position: absolute;
    z-index: 40;
    top: calc(100% + var(--explorer-space-0));
    right: 0;
    min-width: 100%;
    max-width: min(22rem, calc(100vw - 2rem));
    max-height: 18rem;
    overflow-y: auto;
    border: 1px solid rgb(var(--border-strong) / 0.75);
    border-radius: var(--explorer-radius-md);
    background: rgb(var(--surface-elevated));
    padding: var(--explorer-space-0);
    box-shadow: var(--shadow-xl);
  }
  .explorer-filter-menu button {
    display: flex;
    min-height: var(--explorer-control-height);
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: var(--explorer-space-2);
    border-radius: 0.5rem;
    padding: 0 var(--explorer-space-1);
    text-align: left;
    font-size: 0.8125rem;
    color: rgb(var(--foreground));
  }
  .explorer-filter-menu button:hover,
  .explorer-filter-option-active { background: rgb(var(--surface-hover)); }
  .explorer-filter-option-selected { color: rgb(var(--primary)); }
  @media (max-width: 760px) {
    .explorer-filter { flex: 1 1 9rem; }
  }
  @media (prefers-reduced-motion: reduce) { .explorer-filter { transition: none; } }
</style>
