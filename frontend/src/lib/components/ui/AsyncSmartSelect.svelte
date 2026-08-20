<script lang="ts">
  import { onMount } from 'svelte';

  export interface AsyncSmartOption {
    value: string;
    label: string;
    description?: string;
  }

  interface Props {
    id: string;
    label?: string;
    ariaLabel?: string;
    value?: string;
    selectedLabel?: string;
    placeholder?: string;
    disabled?: boolean;
    compact?: boolean;
    onselect?: (value: string, option?: AsyncSmartOption) => void;
    loadOptions: (query: string) => Promise<AsyncSmartOption[]>;
  }

  let {
    id,
    label = '',
    ariaLabel,
    value = $bindable(''),
    selectedLabel = '',
    placeholder = 'Buscar o seleccionar…',
    disabled = false,
    compact = false,
    onselect,
    loadOptions
  }: Props = $props();

  let open = $state(false);
  let query = $state('');
  let options = $state<AsyncSmartOption[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let active = $state(0);
  let root: HTMLDivElement;
  let requestId = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function withSelected(items: AsyncSmartOption[]) {
    if (!value || !selectedLabel || items.some((item) => item.value === value)) return items;
    return [{ value, label: selectedLabel }, ...items];
  }

  async function search(rawQuery: string) {
    const currentRequest = ++requestId;
    loading = true;
    error = null;
    try {
      const result = await loadOptions(rawQuery);
      if (currentRequest !== requestId) return;
      options = withSelected(result);
      active = 0;
    } catch (err: unknown) {
      if (currentRequest !== requestId) return;
      options = withSelected([]);
      error = err instanceof Error ? err.message : 'No se pudieron cargar las opciones.';
    } finally {
      if (currentRequest === requestId) loading = false;
    }
  }

  function openList() {
    if (disabled) return;
    open = true;
    query = '';
    void search('');
  }

  function choose(option: AsyncSmartOption) {
    value = option.value;
    query = '';
    open = false;
    onselect?.(option.value, option);
  }

  function clear() {
    value = '';
    query = '';
    open = false;
    onselect?.('');
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      open = false;
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!open) {
        openList();
        active = 0;
        return;
      }
      active = Math.min(active + 1, Math.max(options.length - 1, 0));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      active = Math.max(active - 1, 0);
    } else if (event.key === 'Enter' && open && options[active]) {
      event.preventDefault();
      choose(options[active]!);
    }
  }

  onMount(() => {
    const close = (event: PointerEvent) => {
      if (root && !root.contains(event.target as Node)) open = false;
    };
    document.addEventListener('pointerdown', close);
    return () => {
      document.removeEventListener('pointerdown', close);
      if (timer) clearTimeout(timer);
    };
  });
</script>

<div bind:this={root} class="relative">
  {#if label}<label for={id} class="mb-1 block text-sm font-medium text-foreground">{label}</label>{/if}
  <div class="relative">
    <input
      {id}
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={open}
      aria-controls={`${id}-listbox`}
      aria-activedescendant={open && options[active] ? `${id}-option-${active}` : undefined}
      aria-label={ariaLabel || label || undefined}
      {disabled}
      value={open ? query : selectedLabel}
      {placeholder}
      autocomplete="off"
      onfocus={openList}
      oninput={(event) => {
        query = (event.currentTarget as HTMLInputElement).value;
        open = true;
        active = 0;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => void search(query), 250);
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
        onclick={clear}>×</button
      >{/if}
    <button
      type="button"
      tabindex="-1"
      aria-label={`Abrir ${ariaLabel || label || 'selección'}`}
      {disabled}
      class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-foreground-subtle"
      onclick={() => (open ? (open = false) : openList())}>⌄</button
    >
  </div>
  {#if open}<div
      id={`${id}-listbox`}
      role="listbox"
      class="absolute z-[1200] mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-border bg-surface-elevated p-1.5 shadow-lifted"
    >
      {#if loading}<p class="px-3 py-5 text-center text-xs text-foreground-muted">Cargando…</p>
      {:else if error}<p class="px-3 py-5 text-center text-xs text-danger">{error}</p>
      {:else if options.length === 0}<p class="px-3 py-5 text-center text-xs text-foreground-muted">Sin resultados</p>
      {:else}{#each options as option, index (option.value)}<button
            id={`${id}-option-${index}`}
            type="button"
            role="option"
            aria-selected={option.value === value}
            class="flex w-full flex-col rounded-lg px-3 py-2 text-left transition-colors {index === active
              ? 'bg-surface-hover'
              : ''} {option.value === value ? 'text-primary' : 'text-foreground'}"
            onpointerenter={() => (active = index)}
            onclick={() => choose(option)}
            ><span class="text-sm font-medium">{option.label}</span>{#if option.description}<span
                class="text-xs text-foreground-muted">{option.description}</span
              >{/if}</button
          >{/each}{/if}
    </div>{/if}
</div>
