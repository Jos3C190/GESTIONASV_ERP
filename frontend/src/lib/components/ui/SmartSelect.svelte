<script lang="ts">
  import { onMount } from 'svelte';

  export interface SmartOption {
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
  }
  interface Props {
    id: string;
    label?: string;
    ariaLabel?: string;
    value: string;
    options: SmartOption[];
    placeholder?: string;
    required?: boolean;
    disabled?: boolean;
    error?: string;
    compact?: boolean;
    onselect?: (value: string) => void;
  }
  let {
    id,
    label = '',
    ariaLabel,
    value = $bindable(),
    options,
    placeholder = 'Buscar o seleccionar…',
    required = false,
    disabled = false,
    error,
    compact = false,
    onselect
  }: Props = $props();
  let open = $state(false);
  let query = $state('');
  let active = $state(0);
  let root: HTMLDivElement;
  let selected = $derived(options.find((option) => option.value === value));
  let filtered = $derived(
    options.filter((option) =>
      `${option.label} ${option.description ?? ''}`
        .toLocaleLowerCase('es')
        .includes(query.trim().toLocaleLowerCase('es'))
    )
  );
  function choose(option: SmartOption) {
    if (option.disabled) return;
    value = option.value;
    query = '';
    open = false;
    onselect?.(option.value);
  }
  function keydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      open = false;
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      open = true;
      active = Math.min(active + 1, Math.max(filtered.length - 1, 0));
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      active = Math.max(active - 1, 0);
    }
    if (event.key === 'Enter' && open && filtered[active]) {
      event.preventDefault();
      choose(filtered[active]!);
    }
  }
  onMount(() => {
    const close = (event: PointerEvent) => {
      if (root && !root.contains(event.target as Node)) open = false;
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  });
</script>

<div bind:this={root} class="relative">
  {#if label}<label for={id} class="mb-1 block text-sm font-medium text-foreground"
      >{label}{#if required}<span class="text-danger"> *</span>{/if}</label
    >{/if}
  <div class="relative">
    <input
      {id}
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={open}
      aria-controls={`${id}-listbox`}
      aria-activedescendant={open && filtered[active] ? `${id}-option-${active}` : undefined}
      aria-invalid={error ? 'true' : undefined}
      aria-describedby={error ? `${id}-error` : undefined}
      aria-label={ariaLabel || label || undefined}
      {disabled}
      value={open ? query : (selected?.label ?? '')}
      {placeholder}
      autocomplete="off"
      onfocus={() => {
        open = true;
        query = '';
        active = 0;
      }}
      oninput={(event) => {
        query = (event.currentTarget as HTMLInputElement).value;
        open = true;
        active = 0;
      }}
      onkeydown={keydown}
      class="w-full border border-border bg-surface text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50 {compact
        ? 'h-8 rounded-md px-2.5 pr-14 text-[13px]'
        : 'rounded-lg px-3 py-2.5 pr-16 text-sm'}"
    />
    {#if value && !disabled}<button
        type="button"
        aria-label={`Limpiar ${ariaLabel || label || 'selección'}`}
        class="absolute right-9 top-1/2 -translate-y-1/2 rounded p-1 text-foreground-subtle hover:bg-surface-hover hover:text-foreground"
        onclick={() => {
          value = '';
          onselect?.('');
        }}>×</button
      >{/if}
    <button
      type="button"
      tabindex="-1"
      aria-label={`Abrir ${ariaLabel || label || 'selección'}`}
      {disabled}
      class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-foreground-subtle"
      onclick={() => (open = !open)}>⌄</button
    >
  </div>
  {#if open}<div
      id={`${id}-listbox`}
      role="listbox"
      class="absolute z-[1200] mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-border bg-surface-elevated p-1.5 shadow-lifted"
    >
      {#if filtered.length === 0}<p class="px-3 py-6 text-center text-xs text-foreground-muted">
          Sin resultados
        </p>{/if}
      {#each filtered as option, index (option.value)}<button
          id={`${id}-option-${index}`}
          type="button"
          role="option"
          aria-selected={option.value === value}
          disabled={option.disabled}
          class="flex w-full flex-col rounded-lg px-3 py-2 text-left transition-colors {index ===
          active
            ? 'bg-surface-hover'
            : ''} {option.value === value ? 'text-primary' : 'text-foreground'} disabled:opacity-45"
          onpointerenter={() => (active = index)}
          onclick={() => choose(option)}
          ><span class="text-sm font-medium">{option.label}</span>{#if option.description}<span
              class="text-xs text-foreground-muted">{option.description}</span
            >{/if}</button
        >{/each}
    </div>{/if}
  {#if error}<p id={`${id}-error`} class="mt-1 text-xs text-danger">{error}</p>{/if}
</div>
