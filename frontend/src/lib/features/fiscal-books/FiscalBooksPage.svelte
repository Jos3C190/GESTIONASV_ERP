<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalBooksApi } from '#lib/api/fiscal-books.ts';
  import PurchaseFiscalForm from '#lib/features/fiscal-books/PurchaseFiscalForm.svelte';
  import {
    DOCUMENT_TYPES,
    MODE_LABELS,
    RENTA_FIELDS,
    previousPeriod,
    saveBlob
  } from '#lib/features/fiscal-books/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type {
    FiscalBookKind,
    FiscalBookMode,
    FiscalMonth,
    RentaPurchase
  } from '#lib/types/fiscal-books.ts';

  let { canManage }: { canManage: boolean } = $props();

  type Tab = FiscalBookKind | 'annexes' | 'pending';

  const inputClass =
    'h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';
  const cell = 'px-3 py-2 text-right tabular-nums';
  const head = 'px-3 py-2 text-left text-xs font-medium uppercase text-foreground-muted';

  let period = $state(previousPeriod());
  let mode = $state<FiscalBookMode | null>(null);
  let month = $state<FiscalMonth | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let tab = $state<Tab>('contributors');
  let firstFolio = $state(1);
  let downloading = $state<string | null>(null);
  let downloadError = $state<string | null>(null);
  let recording = $state<string | null>(null);

  let defaults = $state<RentaPurchase | null>(null);
  let defaultsOpen = $state(false);
  let defaultsBusy = $state(false);
  let defaultsMessage = $state<string | null>(null);

  const tabs = $derived<{ key: Tab; label: string; count: number }[]>(
    month
      ? [
          { key: 'contributors', label: 'Contribuyentes', count: month.contributor_book.length },
          { key: 'consumers', label: 'Consumidor final', count: month.consumer_book.length },
          { key: 'purchases', label: 'Compras', count: month.purchase_book.length },
          {
            key: 'annexes',
            label: 'Anexos F-07',
            count: month.annexes.filter((annex) => annex.rows.length).length
          },
          { key: 'pending', label: 'Compras pendientes', count: month.pending_purchases.length }
        ]
      : []
  );
  const simulated = $derived(month !== null && month.mode !== 'production');
  const suffix = $derived(
    month ? (month.mode === 'production' ? '' : `_${MODE_LABELS[month.mode].toUpperCase()}`) : ''
  );

  async function load() {
    loading = true;
    loadError = null;
    try {
      // El modo elegido vale para el mismo mes; en otro mes lo propone el servidor.
      const requested = month && month.period === period ? mode : null;
      month = await fiscalBooksApi.month(period, requested);
      mode = month.mode;
    } catch (cause) {
      month = null;
      loadError = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los libros.';
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    await load();
    try {
      defaults = await fiscalBooksApi.settings();
    } catch {
      defaults = null;
    }
  });

  async function download(kind: 'xlsx' | 'zip' | FiscalBookKind) {
    if (!month) return;
    downloading = kind;
    downloadError = null;
    try {
      if (kind === 'xlsx') {
        saveBlob(
          await fiscalBooksApi.workbook(month.period, month.mode),
          `F07_libros_${month.period}${suffix}.xlsx`
        );
      } else if (kind === 'zip') {
        saveBlob(
          await fiscalBooksApi.f07Zip(month.period, month.mode),
          `F07_${month.period}${suffix}.zip`
        );
      } else {
        const blob = await fiscalBooksApi.bookPdf(month.period, kind, firstFolio, month.mode);
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank', 'noopener');
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      }
    } catch (cause) {
      downloadError = cause instanceof HttpError ? cause.message : 'No se pudo generar el archivo.';
    } finally {
      downloading = null;
    }
  }

  async function saveDefaults(event: SubmitEvent) {
    event.preventDefault();
    if (!defaults) return;
    defaultsBusy = true;
    defaultsMessage = null;
    try {
      defaults = await fiscalBooksApi.saveSettings(defaults);
      defaultsMessage = 'Se guardó la renta de compras por defecto.';
    } catch (cause) {
      defaultsMessage =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar la renta por defecto.';
    } finally {
      defaultsBusy = false;
    }
  }
</script>

<div class="space-y-5">
  <form
    class="flex flex-wrap items-end gap-3"
    onsubmit={(event) => {
      event.preventDefault();
      void load();
    }}
  >
    <label class="space-y-1 text-sm text-foreground-muted"
      >Mes
      <input class={inputClass} type="month" bind:value={period} required />
    </label>
    {#if month && month.modes.length > 1}
      <label class="space-y-1 text-sm text-foreground-muted"
        >Modo
        <select class={inputClass} bind:value={mode}>
          {#each month.modes as item (item)}
            <option value={item}>{MODE_LABELS[item]}</option>
          {/each}
        </select>
      </label>
    {/if}
    <Button type="submit" variant="secondary" disabled={loading}>Consultar</Button>
  </form>

  {#if loading}
    <div class="grid gap-3 sm:grid-cols-4" aria-hidden="true">
      {#each [1, 2, 3, 4] as item (item)}
        <div class="skeleton h-20 rounded-xl"></div>
      {/each}
    </div>
    <div class="skeleton h-64 rounded-xl" aria-hidden="true"></div>
  {:else if loadError}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {loadError}
    </div>
  {:else if month}
    <section class="space-y-3" aria-label="Resumen del mes">
      <div class="flex flex-wrap items-center gap-2 text-sm text-foreground-muted">
        <span class="font-medium text-foreground"
          >{month.label.charAt(0).toUpperCase()}{month.label.slice(1)}</span
        >
        <span>·</span>
        <span>{month.issuer.name}</span>
        <span
          class="rounded-full px-2 py-0.5 text-xs font-medium {simulated
            ? 'bg-warning/10 text-warning'
            : 'bg-success/10 text-success'}">{MODE_LABELS[month.mode]}</span
        >
      </div>
      {#if simulated}
        <div
          class="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning"
          role="note"
        >
          Documentos en modo {MODE_LABELS[month.mode].toLowerCase()}, sin validez fiscal: sirven
          para revisar el formato, no para cargar al portal de Hacienda.
        </div>
      {/if}
      {#each month.warnings as warning (warning)}
        <div class="rounded-xl border border-border bg-surface-muted p-3 text-sm text-foreground">
          {warning}
        </div>
      {/each}
      <dl class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {#each [['Débito fiscal', month.summary.debit], ['Crédito fiscal', month.summary.credit], ['Percepción cobrada', month.summary.perception_collected], ['Impuesto del mes', month.summary.balance]] as [label, value] (label)}
          <div class="rounded-xl border border-border bg-surface p-4">
            <dt class="text-sm text-foreground-muted">{label}</dt>
            <dd class="mt-1 text-xl font-semibold tabular-nums text-foreground">
              {formatMoney(value)}
            </dd>
          </div>
        {/each}
      </dl>
      <p class="text-xs text-foreground-muted">
        El impuesto del mes es débito menos crédito más la percepción cobrada, antes de remanentes,
        retenciones que le hicieron a la empresa y anticipos, que el ERP no registra.
      </p>
    </section>

    <section
      class="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-surface p-4"
      aria-label="Descargas"
    >
      <Button variant="secondary" disabled={downloading !== null} onclick={() => download('xlsx')}>
        {downloading === 'xlsx' ? 'Generando…' : 'Excel del mes'}
      </Button>
      <Button variant="secondary" disabled={downloading !== null} onclick={() => download('zip')}>
        {downloading === 'zip' ? 'Generando…' : 'ZIP del F-07'}
      </Button>
      <label class="ml-auto space-y-1 text-sm text-foreground-muted"
        >Folio inicial
        <input class="{inputClass} w-24" type="number" min="1" bind:value={firstFolio} />
      </label>
      {#each [['contributors', 'PDF contribuyentes'], ['consumers', 'PDF consumidores'], ['purchases', 'PDF compras']] as [kind, label] (kind)}
        <Button
          variant="ghost"
          disabled={downloading !== null || firstFolio < 1}
          onclick={() => download(kind as FiscalBookKind)}
        >
          {downloading === kind ? 'Generando…' : label}
        </Button>
      {/each}
      {#if downloadError}
        <p class="w-full text-sm text-danger" role="alert">{downloadError}</p>
      {/if}
    </section>

    <div class="flex gap-1 overflow-x-auto border-b border-border" role="tablist">
      {#each tabs as item (item.key)}
        <button
          type="button"
          role="tab"
          aria-selected={tab === item.key}
          class="whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium {tab === item.key
            ? 'border-primary text-foreground'
            : 'border-transparent text-foreground-muted hover:text-foreground'}"
          onclick={() => (tab = item.key)}
          >{item.label} <span class="text-foreground-muted">({item.count})</span></button
        >
      {/each}
    </div>

    <div class="overflow-x-auto rounded-xl border border-border bg-surface" role="tabpanel">
      {#if tab === 'contributors'}
        {#if month.contributor_book.length === 0}
          <p class="p-6 text-center text-sm text-foreground-muted">
            Sin créditos fiscales ni notas en el mes.
          </p>
        {:else}
          <table class="min-w-full text-sm">
            <thead class="bg-surface-muted">
              <tr>
                <th class={head}>N°</th>
                <th class={head}>Fecha</th>
                <th class={head}>Documento</th>
                <th class={head}>Cliente</th>
                <th class={head}>NRC</th>
                <th class="{head} text-right">Exentas</th>
                <th class="{head} text-right">Gravadas</th>
                <th class="{head} text-right">Débito fiscal</th>
                <th class="{head} text-right">Total</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each month.contributor_book as line (line.number)}
                <tr>
                  <td class="px-3 py-2">{line.number}</td>
                  <td class="px-3 py-2 whitespace-nowrap">{formatDay(line.issued_on)}</td>
                  <td class="px-3 py-2"
                    >{DOCUMENT_TYPES[line.document_type]}
                    <span class="block text-xs text-foreground-muted">{line.control_number}</span
                    ></td
                  >
                  <td class="px-3 py-2">{line.customer}</td>
                  <td class="px-3 py-2">{line.registry}</td>
                  <td class={cell}>{formatMoney(line.exempt)}</td>
                  <td class={cell}>{formatMoney(line.taxed)}</td>
                  <td class={cell}>{formatMoney(line.vat)}</td>
                  <td class="{cell} font-medium">{formatMoney(line.total)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      {:else if tab === 'consumers'}
        {#if month.consumer_book.length === 0}
          <p class="p-6 text-center text-sm text-foreground-muted">Sin facturas en el mes.</p>
        {:else}
          <table class="min-w-full text-sm">
            <thead class="bg-surface-muted">
              <tr>
                <th class={head}>Día</th>
                <th class={head}>Del</th>
                <th class={head}>Al</th>
                <th class={head}>Caja</th>
                <th class="{head} text-right">Exentas</th>
                <th class="{head} text-right">No sujetas</th>
                <th class="{head} text-right">Gravadas (IVA incluido)</th>
                <th class="{head} text-right">Total</th>
                <th class={head}>Observación</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each month.consumer_book as line, index (index)}
                <tr class={line.note ? 'text-danger' : ''}>
                  <td class="px-3 py-2 whitespace-nowrap">{formatDay(line.day)}</td>
                  <td class="px-3 py-2 text-xs">{line.first_control}</td>
                  <td class="px-3 py-2 text-xs">{line.last_control}</td>
                  <td class="px-3 py-2">{line.point_of_sale}</td>
                  <td class={cell}>{formatMoney(line.exempt)}</td>
                  <td class={cell}>{formatMoney(line.not_subject)}</td>
                  <td class={cell}>{formatMoney(line.taxed)}</td>
                  <td class="{cell} font-medium">{formatMoney(line.total)}</td>
                  <td class="px-3 py-2 text-xs">{line.note}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      {:else if tab === 'purchases'}
        {#if month.purchase_book.length === 0}
          <p class="p-6 text-center text-sm text-foreground-muted">
            Sin compras con documento del proveedor en el mes.
          </p>
        {:else}
          <table class="min-w-full text-sm">
            <thead class="bg-surface-muted">
              <tr>
                <th class={head}>N°</th>
                <th class={head}>Fecha</th>
                <th class={head}>Documento</th>
                <th class={head}>Proveedor</th>
                <th class={head}>NRC</th>
                <th class="{head} text-right">Exentas</th>
                <th class="{head} text-right">Gravadas</th>
                <th class="{head} text-right">Crédito fiscal</th>
                <th class="{head} text-right">Total</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each month.purchase_book as line (line.number)}
                <tr>
                  <td class="px-3 py-2">{line.number}</td>
                  <td class="px-3 py-2 whitespace-nowrap">{formatDay(line.issued_on)}</td>
                  <td class="px-3 py-2"
                    >{DOCUMENT_TYPES[line.document_type]}
                    <span class="block break-all text-xs text-foreground-muted"
                      >{line.document_number}</span
                    ></td
                  >
                  <td class="px-3 py-2">{line.supplier}</td>
                  <td class="px-3 py-2">{line.registry}</td>
                  <td class={cell}>{formatMoney(line.internal_exempt)}</td>
                  <td class={cell}>{formatMoney(line.internal_taxed)}</td>
                  <td class={cell}>{formatMoney(line.vat)}</td>
                  <td class="{cell} font-medium">{formatMoney(line.total)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      {:else if tab === 'annexes'}
        <div class="divide-y divide-border">
          {#each month.annexes as annex (annex.key)}
            <details class="p-4">
              <summary class="cursor-pointer text-sm">
                <span class="font-medium text-foreground">{annex.title}</span>
                <span class="text-foreground-muted">
                  · {annex.file_name} · {annex.rows.length} fila(s)</span
                >
              </summary>
              {#if annex.rows.length}
                <pre
                  class="mt-3 overflow-x-auto rounded-md bg-surface-muted p-3 text-xs text-foreground">{annex.rows
                    .map((row) => row.join(';'))
                    .join('\n')}</pre>
              {:else}
                <p class="mt-2 text-sm text-foreground-muted">
                  Sin filas este mes; no se genera el archivo.
                </p>
              {/if}
            </details>
          {/each}
        </div>
      {:else if month.pending_purchases.length === 0}
        <p class="p-6 text-center text-sm text-foreground-muted">
          Todas las compras recibidas del mes tienen su documento registrado.
        </p>
      {:else}
        <ul class="divide-y divide-border">
          {#each month.pending_purchases as item (item.id)}
            <li class="space-y-3 p-4">
              <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
                <div>
                  <a class="font-medium text-primary hover:underline" href="/purchases/{item.id}"
                    >{item.code}</a
                  >
                  <span class="text-foreground-muted">
                    · {item.supplier} · {item.invoice_number ?? 'sin número'} ·
                    {formatDay(item.invoice_date)}</span
                  >
                </div>
                <div class="flex items-center gap-3">
                  <span class="tabular-nums text-foreground">{formatMoney(item.total)}</span>
                  {#if canManage && recording !== item.id}
                    <Button size="sm" variant="secondary" onclick={() => (recording = item.id)}>
                      Registrar documento
                    </Button>
                  {/if}
                </div>
              </div>
              {#if recording === item.id}
                <PurchaseFiscalForm
                  purchaseId={item.id}
                  {canManage}
                  onSaved={() => {
                    recording = null;
                    void load();
                  }}
                />
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    {#if canManage && defaults}
      <section class="rounded-xl border border-border bg-surface p-4" aria-label="Renta de compras">
        <button
          type="button"
          class="text-sm font-medium text-foreground"
          aria-expanded={defaultsOpen}
          onclick={() => (defaultsOpen = !defaultsOpen)}
        >
          Renta de compras por defecto {defaultsOpen ? '▴' : '▾'}
        </button>
        {#if defaultsOpen}
          <form class="mt-3 grid gap-3 sm:grid-cols-2" onsubmit={saveDefaults}>
            <p class="text-sm text-foreground-muted sm:col-span-2">
              Se propone al registrar el documento de una compra; en cada compra se puede cambiar.
            </p>
            {#each RENTA_FIELDS as field (field.key)}
              <label class="space-y-1 text-sm text-foreground-muted"
                >{field.label}
                <select
                  class="{inputClass} w-full"
                  value={String(defaults[field.key])}
                  onchange={(event) => {
                    if (defaults)
                      defaults = { ...defaults, [field.key]: Number(event.currentTarget.value) };
                  }}
                >
                  {#each Object.entries(field.options) as [value, label] (value)}
                    <option {value}>{value} · {label}</option>
                  {/each}
                </select>
              </label>
            {/each}
            <div class="flex items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={defaultsBusy}>Guardar renta por defecto</Button>
              {#if defaultsMessage}
                <span class="text-sm text-foreground-muted" role="status">{defaultsMessage}</span>
              {/if}
            </div>
          </form>
        {/if}
      </section>
    {/if}
  {/if}
</div>
