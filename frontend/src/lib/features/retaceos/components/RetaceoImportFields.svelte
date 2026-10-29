<script lang="ts">
  import type { RetaceoImportData } from '$lib/types/retaceo';
  let {
    value,
    oninput,
    disabled = false,
    invoiceLocked = false
  }: {
    value: RetaceoImportData;
    oninput: (value: RetaceoImportData) => void;
    disabled?: boolean;
    invoiceLocked?: boolean;
  } = $props();
  const fields = [
    { key: 'origin_country', label: 'País de origen', type: 'text', length: 120 },
    { key: 'import_invoice_number', label: 'Factura de importación', type: 'text', length: 80 },
    { key: 'import_invoice_date', label: 'Fecha de factura', type: 'date', length: undefined },
    { key: 'import_policy_number', label: 'Póliza de importación', type: 'text', length: 80 },
    { key: 'import_policy_date', label: 'Fecha de póliza', type: 'date', length: undefined }
  ] as const;
</script>

<section
  class="rounded-xl border border-border bg-surface p-4"
  aria-labelledby="import-fields-heading"
>
  <h2 id="import-fields-heading" class="font-semibold text-foreground">
    Documentación de importación
  </h2>
  <p class="mt-1 text-sm text-foreground-muted">
    Captura país y póliza cuando correspondan. {invoiceLocked
      ? 'Factura y fecha: desde la recepción confirmada, solo lectura.'
      : 'Deja vacíos los campos que no apliquen.'}
  </p>
  <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each fields as field (field.key)}
      <label class="block text-sm text-foreground"
        ><span class="mb-1.5 block font-medium">{field.label}</span>
        <input
          type={field.type}
          maxlength={field.length}
          value={value[field.key] ?? ''}
          {disabled}
          readonly={invoiceLocked &&
            (field.key === 'import_invoice_number' || field.key === 'import_invoice_date')}
          oninput={(event) => oninput({ ...value, [field.key]: event.currentTarget.value || null })}
          class="h-10 w-full rounded-lg border border-border-control bg-surface px-3 read-only:border-border read-only:bg-surface-muted read-only:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        />
      </label>
    {/each}
  </div>
</section>
