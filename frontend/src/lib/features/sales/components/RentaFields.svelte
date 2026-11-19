<script lang="ts">
  import { RENTA_INCOME_LABELS, RENTA_OPERATION_LABELS } from '#lib/features/sales/renta-labels.ts';

  let {
    operation,
    income,
    disabled = false,
    onchange
  }: {
    operation: number | null;
    income: number | null;
    disabled?: boolean;
    onchange: (operation: number | null, income: number | null) => void;
  } = $props();

  const selectClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground disabled:opacity-60';

  function parse(value: string): number | null {
    return value === '' ? null : Number(value);
  }
</script>

<label class="flex min-w-0 flex-col gap-1 text-sm text-foreground-muted"
  >Tipo de operación (renta)
  <select
    class={selectClass}
    value={operation === null ? '' : String(operation)}
    onchange={(event) => onchange(parse(event.currentTarget.value), income)}
    {disabled}
  >
    <option value="">Elige el tipo de operación</option>
    {#each Object.entries(RENTA_OPERATION_LABELS) as [value, label] (value)}
      <option {value}>{value} · {label}</option>
    {/each}
  </select>
</label>
<label class="flex min-w-0 flex-col gap-1 text-sm text-foreground-muted"
  >Tipo de ingreso (renta)
  <select
    class={selectClass}
    value={income === null ? '' : String(income)}
    onchange={(event) => onchange(operation, parse(event.currentTarget.value))}
    {disabled}
  >
    <option value="">Elige el tipo de ingreso</option>
    {#each Object.entries(RENTA_INCOME_LABELS) as [value, label] (value)}
      <option {value}>{value} · {label}</option>
    {/each}
  </select>
</label>
