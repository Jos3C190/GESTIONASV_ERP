<script lang="ts">
  import type { FixedAmounts } from '../manual-costs';
  import { totalAmounts, validateImportAmount } from '../manual-costs';

  let {
    value,
    currency,
    disabled = false,
    errors = {},
    showErrors = false,
    oninput,
    fob = '0',
    otherExpenses = '0',
    creating = false
  }: {
    value: FixedAmounts;
    currency: string;
    disabled?: boolean;
    /** Messages coming from the parent (for example a server rejection). */
    errors?: Partial<Record<keyof FixedAmounts, string>>;
    /** Show the validation of empty fields too, once the user tried to save. */
    showErrors?: boolean;
    oninput: (key: keyof FixedAmounts, value: string) => void;
    fob?: string;
    otherExpenses?: string;
    /** On the creation form the additional expenses do not exist yet. */
    creating?: boolean;
  } = $props();

  const fields = [
    {
      key: 'freight',
      label: 'Flete y seguro',
      help: 'Escribe el importe de tu documento de transporte y seguro. Escribe 0 si no aplica.'
    },
    {
      key: 'dai',
      label: 'DAI',
      help: 'Escribe el Derecho Arancelario a la Importación de tu póliza o declaración. Escribe 0 si no aplica.'
    }
  ] as const;

  let touched = $state<Partial<Record<keyof FixedAmounts, boolean>>>({});

  function fieldError(key: keyof FixedAmounts): string | null {
    if (errors[key]) return errors[key] ?? null;
    if (!showErrors && !touched[key]) return null;
    return validateImportAmount(value[key]);
  }

  function money(amount: string): string {
    if (!amount.trim() || !Number.isFinite(Number(amount))) return '—';
    return new Intl.NumberFormat('es-SV', { style: 'currency', currency }).format(Number(amount));
  }

  function sum(values: string[]): string {
    if (values.some((entry) => !entry.trim())) return '';
    try {
      return totalAmounts(values);
    } catch {
      return '';
    }
  }

  const total = $derived(
    validateImportAmount(value.freight) || validateImportAmount(value.dai)
      ? ''
      : sum([fob, value.freight, value.dai, otherExpenses])
  );
</script>

<section
  class="rounded-xl border border-border bg-surface p-4"
  aria-labelledby="fixed-amounts-heading"
>
  <h2 id="fixed-amounts-heading" class="font-semibold text-foreground">Costos del retaceo</h2>
  <p class="mt-1 max-w-prose text-sm leading-6 text-foreground-muted">
    El costo total suma el FOB, el flete y seguro, el DAI y los gastos adicionales. Cada importe se
    reparte entre los productos según su FOB.
  </p>
  <div class="mt-4 grid gap-4 md:grid-cols-2">
    <div class="text-sm text-foreground">
      <dl>
        <dt class="mb-1.5 font-medium">FOB desde la factura (fijo)</dt>
        <dd
          id="fixed-fob-value"
          aria-describedby="fixed-fob-help"
          class="flex h-11 w-full items-center rounded-lg border border-border bg-surface-muted px-3 font-medium tabular-nums text-foreground"
        >
          {money(fob)}
        </dd>
      </dl>
      <p id="fixed-fob-help" class="mt-1.5 text-xs leading-5 text-foreground-muted">
        Valor neto de las líneas de la factura de compra (subtotal menos descuento) para las
        cantidades recibidas. No se edita aquí.
      </p>
    </div>

    {#each fields as field (field.key)}
      {@const message = fieldError(field.key)}
      <div class="text-sm text-foreground">
        <label for={`fixed-${field.key}`} class="mb-1.5 block font-medium"
          >{field.label} ({currency})</label
        >
        <input
          id={`fixed-${field.key}`}
          type="number"
          min="0"
          step="0.000001"
          inputmode="decimal"
          required
          value={value[field.key]}
          {disabled}
          oninput={(event) => oninput(field.key, event.currentTarget.value)}
          onblur={() => (touched[field.key] = true)}
          aria-invalid={message ? 'true' : undefined}
          aria-describedby={`fixed-${field.key}-help${message ? ` fixed-${field.key}-error` : ''}`}
          class="h-11 w-full rounded-lg border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60 {message
            ? 'border-danger'
            : 'border-border-control'}"
        />
        {#if message}<span
            id={`fixed-${field.key}-error`}
            role="alert"
            class="mt-1 block text-xs text-danger">{message}</span
          >{/if}
        <span
          id={`fixed-${field.key}-help`}
          class="mt-1.5 block text-xs leading-5 text-foreground-muted">{field.help}</span
        >
      </div>
    {/each}

    <div class="text-sm text-foreground">
      <dl>
        <dt class="mb-1.5 font-medium">Gastos adicionales</dt>
        <dd
          id="fixed-expenses-value"
          aria-describedby="fixed-expenses-help"
          class="flex h-11 w-full items-center rounded-lg border border-border bg-surface-muted px-3 font-medium tabular-nums text-foreground"
        >
          {money(otherExpenses)}
        </dd>
      </dl>
      <p id="fixed-expenses-help" class="mt-1.5 text-xs leading-5 text-foreground-muted">
        {creating
          ? 'Los registrarás después de crear el retaceo.'
          : 'Suma de los gastos con comprobante que registras abajo.'}
      </p>
    </div>
  </div>

  <dl class="mt-5 border-t border-border pt-4" aria-live="polite">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <dt class="text-sm text-foreground-muted">Costo total</dt>
      <dd class="text-lg font-semibold tabular-nums text-foreground">{money(total)}</dd>
    </div>
  </dl>
</section>
