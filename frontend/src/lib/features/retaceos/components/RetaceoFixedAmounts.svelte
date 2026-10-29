<script lang="ts">
  import type { FixedAmounts } from '../manual-costs';
  let {
    value,
    currency,
    disabled = false,
    errors = {},
    oninput
  }: {
    value: FixedAmounts;
    currency: string;
    disabled?: boolean;
    errors?: Partial<Record<keyof FixedAmounts, string>>;
    oninput: (key: keyof FixedAmounts, value: string) => void;
  } = $props();
  const fields = [
    {
      key: 'freight',
      label: 'Flete total',
      help: 'Importe real del transporte de la importación.'
    },
    { key: 'dai', label: 'DAI total', help: 'Derecho Arancelario a la Importación documentado.' },
    {
      key: 'vat',
      label: 'IVA de importación',
      help: 'Se registra separado del costo de adquisición.'
    }
  ] as const;
</script>

<section
  class="rounded-xl border border-border bg-surface p-4"
  aria-labelledby="fixed-amounts-heading"
>
  <h2 id="fixed-amounts-heading" class="font-semibold text-foreground">Componentes del retaceo</h2>
  <p class="mt-1 max-w-prose text-sm leading-6 text-foreground-muted">
    Captura flete y DAI; escribe 0 cuando no apliquen. El IVA se registra aparte, también con 0
    explícito.
  </p>
  <div class="mt-4 grid gap-4 md:grid-cols-3">
    {#each fields as field (field.key)}
      <label class="block text-sm text-foreground">
        <span class="mb-1.5 block font-medium">{field.label} ({currency})</span>
        <input
          id={`fixed-${field.key}`}
          type="number"
          min="0"
          step="0.000001"
          required
          value={value[field.key]}
          {disabled}
          oninput={(event) => oninput(field.key, event.currentTarget.value)}
          aria-invalid={Boolean(errors[field.key])}
          aria-describedby={`fixed-${field.key}-help${errors[field.key] ? ` fixed-${field.key}-error` : ''}`}
          class="h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
        />
        {#if errors[field.key]}<span
            id={`fixed-${field.key}-error`}
            role="alert"
            class="mt-1 block text-xs text-danger">{errors[field.key]}</span
          >{/if}
        <span
          id={`fixed-${field.key}-help`}
          class="mt-1.5 block text-xs leading-5 text-foreground-muted">{field.help}</span
        >
      </label>
    {/each}
  </div>
</section>
