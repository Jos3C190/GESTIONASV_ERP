<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import {
    decimalMicros,
    displayDecimal,
    fromMicros,
    openingQuantities,
    valuationApi,
    type ValuationOverview
  } from '../valuation';

  let {
    data,
    onapproved,
    onrefresh
  }: {
    data: ValuationOverview;
    onapproved: () => Promise<void>;
    onrefresh: (data: ValuationOverview) => void;
  } = $props();
  const quantities = $derived(openingQuantities(data));
  const items = $derived(data.items.filter((item) => quantities.has(item.inventory_item_id)));
  let values = $state<Record<string, string>>({});
  let references = $state<Record<string, string>>({});
  let currency = $state('USD');
  let reference = $state('');
  let approved = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let page = $state(0);
  let refreshing = $state(false);
  let refreshNotice = $state('');
  const busy = $derived(saving || refreshing);
  const currencyError = $derived(
    /^[A-Z]{3}$/.test(currency.trim().toUpperCase())
      ? ''
      : 'Escribe las tres letras de una moneda activa, por ejemplo USD.'
  );
  const referenceError = $derived(
    reference.trim().length >= 3
      ? ''
      : 'Identifica el documento de corte con al menos tres caracteres.'
  );
  let active = true;
  onDestroy(() => {
    active = false;
  });
  const inputClass =
    'w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50';
  function costError(id: string): string {
    try {
      decimalMicros(values[id] ?? '');
      return '';
    } catch (cause) {
      return cause instanceof Error ? cause.message : 'Revisa el costo.';
    }
  }
  async function nextIncomplete() {
    const index = items.findIndex(
      (item) =>
        costError(item.inventory_item_id) ||
        (references[item.inventory_item_id] ?? '').trim().length < 3
    );
    if (index < 0) return;
    page = Math.floor(index / 20);
    await tick();
    const id = items[index]!.inventory_item_id;
    document.getElementById(`${costError(id) ? 'cost' : 'source'}-${id}`)?.focus();
  }
  async function refresh() {
    if (busy) return;
    refreshing = true;
    approved = false;
    error = null;
    try {
      const next = await valuationApi.overview();
      if (!active) return;
      const nextQuantities = openingQuantities(next);
      let changed = 0;
      for (const [id, quantity] of quantities) {
        if (nextQuantities.get(id) !== quantity) {
          delete values[id];
          delete references[id];
          changed++;
        }
      }
      page = 0;
      approved = false;
      onrefresh(next);
      refreshNotice = changed
        ? `Conteo actualizado. Revisa ${changed} productos con cantidades cambiadas; sus costos se dejaron pendientes. Los demás valores se conservaron.`
        : 'Conteo actualizado. Se conservaron los costos capturados; confirma nuevamente la revisión.';
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'No se pudo actualizar el conteo.';
    } finally {
      refreshing = false;
    }
  }
  const visible = $derived(items.slice(page * 20, (page + 1) * 20));
  const completed = $derived(
    items.filter((item) => {
      try {
        decimalMicros(values[item.inventory_item_id] ?? '');
        return (references[item.inventory_item_id] ?? '').trim().length >= 3;
      } catch {
        return false;
      }
    }).length
  );
  const total = $derived.by(() => {
    let amount = 0n;
    for (const item of items) {
      try {
        amount += decimalMicros(values[item.inventory_item_id] ?? '0');
      } catch {
        return null;
      }
    }
    return fromMicros(amount);
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    error = null;
    if (currencyError || referenceError) {
      error = currencyError || referenceError;
      return;
    }
    if (!approved || completed !== items.length) {
      error = 'Completa el costo y su respaldo en todos los productos y confirma la revisión.';
      return;
    }
    saving = true;
    try {
      await valuationApi.open({
        currency: currency.trim().toUpperCase(),
        reference: reference.trim(),
        approved: true,
        snapshot_fingerprint: data.snapshot_fingerprint,
        lines: items.map((item) => ({
          inventory_item_id: item.inventory_item_id,
          quantity_base: quantities.get(item.inventory_item_id)!,
          total_cost: fromMicros(decimalMicros(values[item.inventory_item_id] ?? '')),
          cost_reference: (references[item.inventory_item_id] ?? '').trim()
        }))
      });
      if (active) await onapproved();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'No se pudo aprobar el saldo inicial.';
    } finally {
      saving = false;
    }
  }
</script>

<form onsubmit={submit} class="space-y-6" aria-label="Aprobación del saldo inicial">
  <div class="max-w-3xl space-y-2">
    <h2 class="text-xl font-semibold text-foreground">Preparar saldo inicial</h2>
    <p class="text-sm leading-6 text-foreground-muted">
      Revisa las existencias de todos los almacenes, incluida cuarentena y tránsito. Registra el
      valor total documentado de cada producto en su unidad base.
    </p>
    <p class="text-sm leading-6 text-foreground-muted">
      Finaliza los retaceos anteriores al corte y concilia este valor con contabilidad. La
      aprobación activa el promedio para los movimientos siguientes y conserva el conteo actual.
    </p>
  </div>
  <div class="flex flex-wrap items-center gap-3">
    <Button variant="secondary" disabled={busy} onclick={() => void refresh()}
      >{refreshing ? 'Actualizando conteo…' : 'Actualizar conteo'}</Button
    >
    {#if completed < items.length}<Button
        variant="secondary"
        disabled={busy}
        onclick={() => void nextIncomplete()}>Ir a producto pendiente</Button
      >{/if}
  </div>
  {#if refreshNotice}<p role="status" class="text-sm text-foreground-muted">{refreshNotice}</p>{/if}
  <p id="valuation-input-help" class="max-w-3xl text-xs leading-5 text-foreground-muted">
    Costo total en {currency}: usa hasta seis decimales, sin separadores de miles (ejemplo:
    1250.500000). La fuente del costo debe tener al menos tres caracteres. Cero requiere su respaldo
    igual que los demás importes.
  </p>
  <fieldset disabled={busy} class="grid gap-4 sm:grid-cols-[10rem_1fr]">
    <FormField
      id="valuation-currency"
      label="Moneda"
      bind:value={currency}
      error={currencyError}
      required
      maxlength={3}
    />
    <FormField
      id="valuation-reference"
      label="Documento de corte y aprobación"
      bind:value={reference}
      error={reference ? referenceError : undefined}
      required
      maxlength={240}
      placeholder="Acta de conteo y conciliación"
    />
  </fieldset>
  <div class="overflow-hidden rounded-xl border border-border">
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3"
    >
      <p class="text-sm font-medium text-foreground">
        {completed} de {items.length} productos documentados
      </p>
      <p class="text-sm text-foreground-muted">
        Valor capturado <strong class="ml-2 font-mono text-foreground"
          >{total === null
            ? 'Revisa los importes inválidos'
            : `${currency} ${displayDecimal(total, 6)}`}</strong
        >
      </p>
    </div>
    {#if items.length === 0}
      <p class="p-6 text-sm text-foreground-muted">
        La empresa no tiene existencias. Puedes aprobar un saldo inicial de cero; las próximas
        recepciones incorporarán su costo.
      </p>
    {:else}
      <div class="overflow-x-auto">
        <table class="opening-table w-full text-left text-sm">
          <caption class="sr-only"
            >Existencias actuales y valor total documentado por producto</caption
          >
          <thead class="bg-surface text-xs text-foreground-muted"
            ><tr
              ><th class="p-4" scope="col">Producto</th><th class="p-4 text-right" scope="col"
                >Existencia base</th
              ><th class="p-4" scope="col">Costo total</th><th class="p-4" scope="col"
                >Fuente del costo</th
              ></tr
            ></thead
          >
          <tbody class="divide-y divide-border">
            {#each visible as item (item.inventory_item_id)}
              <tr>
                <th class="max-w-xs p-4 font-normal" scope="row"
                  ><span class="block font-medium">{item.product_name}</span><span
                    class="text-xs text-foreground-muted">{item.sku}</span
                  ></th
                >
                <td class="p-4 text-right font-mono tabular-nums"
                  ><span class="mb-1 block font-sans text-xs text-foreground-muted sm:hidden"
                    >Existencia base</span
                  >{displayDecimal(quantities.get(item.inventory_item_id)!)}
                  <span class="text-foreground-muted">{item.base_unit}</span></td
                >
                <td class="p-4"
                  ><label
                    class="mb-1 block text-xs text-foreground-muted sm:sr-only"
                    for={`cost-${item.inventory_item_id}`}
                    >Costo total<span class="sr-only"> de {item.product_name}</span></label
                  ><input
                    id={`cost-${item.inventory_item_id}`}
                    class={inputClass}
                    inputmode="decimal"
                    placeholder="0.000000"
                    maxlength="25"
                    bind:value={values[item.inventory_item_id]}
                    disabled={busy}
                    aria-describedby={`valuation-input-help cost-error-${item.inventory_item_id}`}
                    aria-invalid={!!values[item.inventory_item_id] &&
                      !!costError(item.inventory_item_id)}
                  />
                  <p
                    id={`cost-error-${item.inventory_item_id}`}
                    aria-live="polite"
                    class="mt-1 text-xs text-danger"
                  >
                    {values[item.inventory_item_id] ? costError(item.inventory_item_id) : ''}
                  </p></td
                >
                <td class="p-4"
                  ><label
                    class="mb-1 block text-xs text-foreground-muted sm:sr-only"
                    for={`source-${item.inventory_item_id}`}
                    >Fuente del costo<span class="sr-only"> de {item.product_name}</span></label
                  ><input
                    id={`source-${item.inventory_item_id}`}
                    class={inputClass}
                    maxlength="240"
                    placeholder="Factura, retaceo o acta"
                    bind:value={references[item.inventory_item_id]}
                    disabled={busy}
                    aria-describedby={`valuation-input-help source-error-${item.inventory_item_id}`}
                    aria-invalid={!!references[item.inventory_item_id] &&
                      (references[item.inventory_item_id] ?? '').trim().length < 3}
                  />
                  <p
                    id={`source-error-${item.inventory_item_id}`}
                    aria-live="polite"
                    class="mt-1 text-xs text-danger"
                  >
                    {references[item.inventory_item_id] &&
                    (references[item.inventory_item_id] ?? '').trim().length < 3
                      ? 'Escribe al menos tres caracteres.'
                      : ''}
                  </p></td
                >
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if items.length > 20}<div
          class="flex items-center justify-end gap-3 border-t border-border p-3"
        >
          <Button size="sm" variant="secondary" disabled={page === 0 || busy} onclick={() => page--}
            >Anterior</Button
          ><span class="text-sm">Página {page + 1} de {Math.ceil(items.length / 20)}</span><Button
            size="sm"
            variant="secondary"
            disabled={(page + 1) * 20 >= items.length || busy}
            onclick={() => page++}>Siguiente</Button
          >
        </div>{/if}
    {/if}
  </div>
  <label class="flex max-w-3xl items-start gap-3 text-sm leading-6 text-foreground"
    ><input
      class="mt-1 size-4 accent-primary"
      type="checkbox"
      bind:checked={approved}
      disabled={busy}
    />Confirmo que el conteo y los costos están documentados y conciliados. Autorizo este saldo
    inicial para la empresa; cualquier corrección posterior deberá conservar su historial.</label
  >
  {#if error}<p
      class="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </p>{/if}
  <Button
    type="submit"
    variant="success"
    disabled={busy ||
      !approved ||
      completed !== items.length ||
      !!referenceError ||
      !!currencyError}>{saving ? 'Aprobando saldo…' : 'Aprobar saldo inicial'}</Button
  >
</form>

<style>
  @media (max-width: 639px) {
    .opening-table thead {
      display: none;
    }
    .opening-table tbody,
    .opening-table tr {
      display: block;
    }
    .opening-table tr {
      padding: 0.75rem;
    }
    .opening-table th,
    .opening-table td {
      display: block;
      max-width: none;
      text-align: left;
      padding: 0.5rem;
    }
  }
</style>
