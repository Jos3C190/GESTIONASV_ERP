<script lang="ts">
  interface Props {
    label: string;
    id: string;
    type?: string;
    value: string | number;
    oninput?: (e: Event) => void;
    placeholder?: string;
    error?: string;
    required?: boolean;
    disabled?: boolean;
    options?: { value: string; label: string }[];
    min?: string;
    max?: string;
    step?: string;
    maxlength?: number;
  }

  let {
    label,
    id,
    type = 'text',
    value = $bindable(),
    oninput,
    placeholder,
    error,
    required = false,
    disabled = false,
    options,
    min,
    max,
    step,
    maxlength
  }: Props = $props();

  function handleInput(e: Event) {
    oninput?.(e);
  }
</script>

<div>
  <label for={id} class="mb-1 block text-sm font-medium text-foreground">
    {label}{#if required}<span class="text-danger"> *</span>{/if}
  </label>
  {#if options}
    <select
      {id}
      {disabled}
      {required}
      bind:value
      onchange={handleInput}
      class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
    >
      {#each options as opt (opt.value)}
        <option value={opt.value}>{opt.label}</option>
      {/each}
    </select>
  {:else}
    <input
      {id}
      {type}
      {disabled}
      {required}
      {placeholder}
      {min}
      {max}
      {step}
      {maxlength}
      bind:value
      oninput={handleInput}
      class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
      aria-invalid={error ? 'true' : undefined}
      aria-describedby={error ? `${id}-error` : undefined}
    />
  {/if}
  {#if error}
    <p id="{id}-error" class="mt-1 text-xs text-danger">{error}</p>
  {/if}
</div>
