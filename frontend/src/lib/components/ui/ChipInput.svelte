<script lang="ts">
  interface Props {
    id: string;
    label: string;
    values: string[];
    suggestions?: string[];
    placeholder?: string;
  }
  let {
    id,
    label,
    values = $bindable(),
    suggestions = [],
    placeholder = 'Escriba y presione Enter'
  }: Props = $props();
  let draft = $state('');
  function add(value = draft) {
    const normalized = value.trim();
    if (
      normalized &&
      !values.some((item) => item.toLocaleLowerCase('es') === normalized.toLocaleLowerCase('es'))
    )
      values = [...values, normalized];
    draft = '';
  }
</script>

<div>
  <label for={id} class="mb-1 block text-sm font-medium text-foreground">{label}</label>
  <div
    class="rounded-xl border border-border bg-surface p-2 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary"
  >
    <div class="mb-2 flex flex-wrap gap-1.5">
      {#each values as value (value)}<span
          class="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-1 text-xs text-foreground"
          >{value}<button
            type="button"
            aria-label={`Quitar ${value}`}
            class="text-foreground-subtle hover:text-danger"
            onclick={() => (values = values.filter((item) => item !== value))}>×</button
          ></span
        >{/each}
    </div>
    <input
      {id}
      bind:value={draft}
      list={`${id}-suggestions`}
      {placeholder}
      class="w-full border-0 bg-transparent px-1 py-1 text-sm text-foreground outline-none"
      onkeydown={(event) => {
        if (event.key === 'Enter' || event.key === ',') {
          event.preventDefault();
          add();
        }
        if (event.key === 'Backspace' && !draft && values.length) values = values.slice(0, -1);
      }}
      onblur={() => add()}
    /><datalist id={`${id}-suggestions`}
      >{#each suggestions as suggestion}<option value={suggestion}></option>{/each}</datalist
    >
  </div>
</div>
