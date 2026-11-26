<script lang="ts">
  /**
   * Conteo de efectivo por denominación: billetes y monedas en dos columnas, con botones para
   * sumar y restar pensados para pantalla táctil y el total siempre a la vista.
   */
  import type { DenominationLine } from '#lib/types/pos.ts';
  import { DENOMINATIONS, centsToAmount, countTotalCents, formatMoney } from './format.ts';

  interface Props {
    lines: DenominationLine[];
    onchange: (lines: DenominationLine[]) => void;
    label?: string;
    disabled?: boolean;
  }

  let { lines, onchange, label = 'Conteo de efectivo', disabled = false }: Props = $props();

  const total = $derived(centsToAmount(countTotalCents(lines)));

  function quantity(form: string, denomination: string): number {
    return (
      lines.find((line) => line.form === form && line.denomination === denomination)?.quantity ?? 0
    );
  }

  function setQuantity(form: string, denomination: string, value: number) {
    const next = Math.max(0, Math.min(100000, Math.trunc(Number.isFinite(value) ? value : 0)));
    onchange(
      lines.map((line) =>
        line.form === form && line.denomination === denomination
          ? { ...line, quantity: next }
          : line
      )
    );
  }

  function subtotal(form: string, denomination: string): string {
    return formatMoney(
      centsToAmount(Math.round(Number(denomination) * 100) * quantity(form, denomination))
    );
  }

  const columns = [
    { form: 'bill', title: 'Billetes' },
    { form: 'coin', title: 'Monedas' }
  ] as const;
</script>

<fieldset class="space-y-3" {disabled}>
  <legend class="sr-only">{label}</legend>
  <div class="grid gap-3 sm:grid-cols-2">
    {#each columns as column (column.form)}
      <div class="rounded-xl border border-border bg-surface-muted/40 p-3">
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground-muted">
          {column.title}
        </p>
        <ul class="space-y-1.5">
          {#each DENOMINATIONS.filter((item) => item.form === column.form) as item (`${item.form}-${item.denomination}`)}
            {@const id = `count-${item.form}-${item.denomination}`}
            <li class="flex items-center gap-2">
              <label
                for={id}
                class="w-12 flex-none text-sm font-semibold tabular-nums text-foreground"
                >{item.label}</label
              >
              <button
                type="button"
                class="flex h-9 w-9 flex-none items-center justify-center rounded-lg border border-border bg-surface text-lg text-foreground-muted hover:bg-surface-hover disabled:opacity-40"
                aria-label={`Quitar un ${column.form === 'bill' ? 'billete' : 'moneda'} de ${item.label}`}
                disabled={disabled || quantity(item.form, item.denomination) === 0}
                onclick={() =>
                  setQuantity(
                    item.form,
                    item.denomination,
                    quantity(item.form, item.denomination) - 1
                  )}>−</button
              >
              <input
                {id}
                type="number"
                inputmode="numeric"
                min="0"
                max="100000"
                class="h-9 w-16 rounded-lg border border-border bg-surface px-2 text-center text-sm tabular-nums text-foreground focus:border-primary focus:outline-none"
                value={quantity(item.form, item.denomination)}
                onchange={(event) =>
                  setQuantity(
                    item.form,
                    item.denomination,
                    Number((event.currentTarget as HTMLInputElement).value)
                  )}
              />
              <button
                type="button"
                class="flex h-9 w-9 flex-none items-center justify-center rounded-lg border border-border bg-surface text-lg text-foreground-muted hover:bg-surface-hover disabled:opacity-40"
                aria-label={`Agregar un ${column.form === 'bill' ? 'billete' : 'moneda'} de ${item.label}`}
                {disabled}
                onclick={() =>
                  setQuantity(
                    item.form,
                    item.denomination,
                    quantity(item.form, item.denomination) + 1
                  )}>+</button
              >
              <span class="ml-auto text-right text-xs tabular-nums text-foreground-muted"
                >{subtotal(item.form, item.denomination)}</span
              >
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </div>
  <div
    class="flex items-center justify-between rounded-xl border border-primary/30 bg-primary/5 px-4 py-3"
    aria-live="polite"
  >
    <span class="text-sm font-medium text-foreground-muted">Total contado</span>
    <span class="text-2xl font-bold tabular-nums text-foreground" data-testid="count-total"
      >{formatMoney(total)}</span
    >
  </div>
</fieldset>
