<script lang="ts">
  import type { FixedAmounts } from '../manual-costs';
  import { totalAmounts } from '../manual-costs';
  import type { RetaceoCalculationMode } from '$lib/types/retaceo';
  let {
    value,
    currency,
    disabled = false,
    errors = {},
    oninput,
    mode = 'manual',
    daiRate = '',
    vatRate = '',
    fob = '0',
    otherExpenses = '0',
    onmodechange,
    onrateinput
  }: {
    value: FixedAmounts;
    currency: string;
    disabled?: boolean;
    errors?: Partial<Record<keyof FixedAmounts, string>>;
    oninput: (key: keyof FixedAmounts, value: string) => void;
    mode?: RetaceoCalculationMode;
    daiRate?: string;
    vatRate?: string;
    fob?: string;
    otherExpenses?: string;
    onmodechange?: (mode: RetaceoCalculationMode) => void;
    onrateinput?: (key: 'dai' | 'vat', value: string) => void;
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

  function money(amount: string): string {
    if (!amount.trim() || !Number.isFinite(Number(amount))) return '—';
    return new Intl.NumberFormat('es-SV', { style: 'currency', currency }).format(Number(amount));
  }

  function sum(values: string[]): string {
    if (values.some((value) => !value.trim())) return '';
    try {
      return totalAmounts(values);
    } catch {
      return '';
    }
  }
</script>

<section
  class="rounded-xl border border-border bg-surface p-4"
  aria-labelledby="fixed-amounts-heading"
>
  <h2 id="fixed-amounts-heading" class="font-semibold text-foreground">Cálculo del retaceo</h2>
  {#if onmodechange}
    <fieldset class="mt-4">
      <legend class="mb-2 text-sm font-medium text-foreground">Modo de cálculo</legend>
      <div class="grid gap-3 sm:grid-cols-2">
        {#each [{ key: 'automatic', label: 'Automático', help: 'FOB desde la compra e impuestos por porcentaje.' }, { key: 'manual', label: 'Manual', help: 'Ingresa tu FOB y tus importes de DAI e IVA.' }] as option}
          <label
            class="flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm {mode ===
            option.key
              ? 'border-primary bg-primary/5'
              : 'border-border'}"
          >
            <input
              type="radio"
              name="retaceo-calculation-mode"
              value={option.key}
              checked={mode === option.key}
              {disabled}
              onchange={() => onmodechange?.(option.key as RetaceoCalculationMode)}
              class="mt-0.5 h-4 w-4 accent-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            />
            <span
              ><span class="block font-medium text-foreground">{option.label}</span><span
                class="mt-1 block text-xs leading-5 text-foreground-muted">{option.help}</span
              ></span
            >
          </label>
        {/each}
      </div>
    </fieldset>
  {/if}
  <p class="mt-1 max-w-prose text-sm leading-6 text-foreground-muted">
    {#if mode === 'automatic'}
      El flete incluye el seguro. DAI: (FOB + flete/seguro) × porcentaje. IVA: (base + DAI) ×
      porcentaje. Escribe 0 cuando no apliquen.
    {:else}
      Ingresa tus importes calculados de flete, DAI e IVA; escribe 0 cuando no apliquen. El IVA se
      registra separado del costo de adquisición.
    {/if}
  </p>
  <div class="mt-4 grid gap-4 md:grid-cols-3">
    {#each fields as field (field.key)}
      {#if mode === 'manual' || field.key === 'freight'}
        <label class="block text-sm text-foreground">
          <span class="mb-1.5 block font-medium"
            >{mode === 'automatic' ? 'Flete y seguro total' : field.label} ({currency})</span
          >
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
      {/if}
    {/each}
    {#if mode === 'automatic'}
      {#each [{ key: 'dai', label: 'DAI', value: daiRate }, { key: 'vat', label: 'IVA', value: vatRate }] as rate}
        <label class="block text-sm text-foreground">
          <span class="mb-1.5 block font-medium">{rate.label} (%)</span>
          <input
            id={`fixed-rate-${rate.key}`}
            aria-label={`${rate.label} (%)`}
            type="number"
            min="0"
            max="1000"
            step="0.000001"
            required
            value={rate.value}
            {disabled}
            oninput={(event) => onrateinput?.(rate.key as 'dai' | 'vat', event.currentTarget.value)}
            aria-invalid={Boolean(errors[rate.key as 'dai' | 'vat'])}
            aria-describedby={`fixed-rate-${rate.key}-help`}
            class="h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
          />
          <span
            id={`fixed-rate-${rate.key}-help`}
            class="mt-1.5 block text-xs leading-5 text-foreground-muted"
            >Porcentaje aplicable a esta importación.</span
          >
          {#if errors[rate.key as 'dai' | 'vat']}<span
              role="alert"
              class="mt-1 block text-xs text-danger">{errors[rate.key as 'dai' | 'vat']}</span
            >{/if}
        </label>
      {/each}
    {/if}
  </div>
  {#if onmodechange}
    <dl
      class="mt-5 grid gap-4 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-live="polite"
    >
      <div>
        <dt class="text-xs text-foreground-muted">
          FOB {mode === 'automatic' ? 'desde la compra' : 'ingresado'}
        </dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">{money(fob)}</dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">
          DAI {mode === 'automatic' ? 'calculado' : 'ingresado'}
        </dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">{money(value.dai)}</dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">
          IVA {mode === 'automatic' ? 'calculado' : 'ingresado'}
        </dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">{money(value.vat)}</dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Costo de adquisición · sin IVA</dt>
        <dd class="mt-1 font-semibold tabular-nums text-foreground">
          {money(sum([fob, value.freight, value.dai, otherExpenses]))}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Total con IVA</dt>
        <dd class="mt-1 font-medium tabular-nums text-foreground">
          {money(sum([fob, value.freight, value.dai, otherExpenses, value.vat]))}
        </dd>
      </div>
    </dl>
  {/if}
</section>
