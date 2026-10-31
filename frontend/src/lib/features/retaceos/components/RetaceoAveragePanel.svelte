<script lang="ts">
  import { retaceosApi } from '$lib/api/retaceos';
  import type { RetaceoAverageComparison } from '$lib/types/retaceo';
  import Button from '$lib/components/ui/Button.svelte';

  let {
    retaceoId,
    contextKey,
    productLabels,
    unitLabels,
    revision = ''
  }: {
    retaceoId: string;
    contextKey: string;
    productLabels: Map<number, string>;
    unitLabels: Map<number, string>;
    revision?: string;
  } = $props();
  let data = $state<RetaceoAverageComparison | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let refresh = $state(0);
  function number(value: string, decimals = 6) {
    return Number(value).toLocaleString('es-SV', { maximumFractionDigits: decimals });
  }
  function money(value: string, decimals = 2) {
    return data
      ? `${data.currency} ${Number(value).toLocaleString('es-SV', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
      : '—';
  }
  $effect(() => {
    const id = retaceoId;
    void contextKey;
    void revision;
    void refresh;
    let active = true;
    data = null;
    loading = true;
    error = null;
    void retaceosApi
      .averageComparison(id)
      .then((result) => {
        if (active) data = result;
      })
      .catch((cause) => {
        if (active)
          error = cause instanceof Error ? cause.message : 'No se pudo comparar el costo promedio.';
      })
      .finally(() => {
        if (active) loading = false;
      });
    return () => {
      active = false;
    };
  });
</script>

<section
  class="overflow-hidden rounded-xl border border-border bg-surface"
  aria-labelledby="average-heading"
  aria-busy={loading}
>
  <div class="flex flex-wrap items-start justify-between gap-3 border-b border-border p-5">
    <div>
      <h2 id="average-heading" class="font-semibold text-foreground">Costo promedio ponderado</h2>
      <p class="mt-1 max-w-3xl text-sm leading-6 text-foreground-muted">
        {data?.value_only
          ? 'Regularización de una recepción ya registrada. Cambia su valor y el promedio de la empresa, sin agregar unidades. El registro original permanece en el Kardex.'
          : data?.mode === 'posted'
            ? 'Comparación histórica del registro de recepción. Los movimientos posteriores se consultan en el Kardex.'
            : 'Proyección para recibir todas las cantidades del retaceo. Usa el saldo actual de toda la empresa; puede cambiar antes de la recepción definitiva.'}
      </p>
    </div>
    <Button variant="secondary" size="sm" disabled={loading} onclick={() => (refresh += 1)}
      >Actualizar comparación</Button
    >
  </div>
  <p role="status" class="sr-only">
    {loading
      ? 'Consultando costo promedio…'
      : error
        ? 'Comparación no disponible.'
        : 'Comparación actualizada.'}
  </p>
  {#if loading}<div class="p-5"><div class="skeleton h-32 rounded-lg"></div></div>
  {:else if error}<div
      class="m-5 rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-foreground"
      role="status"
    >
      {error}
    </div>
  {:else if data}
    {#if !data.lines.length}<p class="p-5 text-sm text-foreground-muted">
        La recepción terminó sin cantidades aceptadas. No se incorporó valor al inventario.
      </p>{/if}
    {#each data.lines as line (line.inventory_item_id)}
      <article class="border-b border-border p-5 last:border-0">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h3 class="text-sm font-semibold text-foreground">
            {productLabels.get(line.product_id) ?? 'Producto de la compra'}
          </h3>
          <a
            href={`/inventory/kardex?inventory_item_id=${encodeURIComponent(line.inventory_item_id)}`}
            class="rounded text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >Comparar en Kardex</a
          >
        </div>
        <div class="mt-4 space-y-3 sm:hidden">
          {#each [{ label: 'Saldo anterior', quantity: line.previous_quantity, value: line.previous_value, average: line.previous_average }, { label: data.value_only ? 'Ajuste de valor' : 'Entrada del retaceo', quantity: line.incoming_quantity, value: line.incoming_value, average: null }, { label: data.mode === 'posted' ? 'Saldo registrado' : 'Saldo previsto', quantity: line.resulting_quantity, value: line.resulting_value, average: line.resulting_average }] as stage (stage.label)}
            <div class="rounded-lg border border-border p-3">
              <h4 class="text-sm font-medium text-foreground">{stage.label}</h4>
              <dl class="mt-2 space-y-2 text-sm">
                <div class="flex justify-between gap-3">
                  <dt class="text-foreground-muted">Cantidad</dt>
                  <dd class="tabular-nums text-foreground">
                    {number(stage.quantity)}
                    {unitLabels.get(line.base_unit_id) ?? 'unidad base'}
                  </dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-foreground-muted">Valor</dt>
                  <dd class="tabular-nums text-foreground">{money(stage.value)}</dd>
                </div>
                {#if stage.average !== null}<div class="flex justify-between gap-3">
                    <dt class="text-foreground-muted">Promedio</dt>
                    <dd class="font-medium tabular-nums text-foreground">
                      {money(stage.average, 6)}
                    </dd>
                  </div>{/if}
              </dl>
            </div>
          {/each}
        </div>
        <div class="mt-4 hidden overflow-x-auto sm:block">
          <table class="w-full min-w-[580px] text-left text-sm">
            <thead class="text-xs text-foreground-muted"
              ><tr
                ><th scope="col" class="pb-3 font-medium">Concepto</th><th
                  scope="col"
                  class="pb-3 text-right font-medium"
                  >Cantidad ({unitLabels.get(line.base_unit_id) ?? 'unidad base'})</th
                ><th scope="col" class="pb-3 text-right font-medium">Valor</th><th
                  scope="col"
                  class="pb-3 text-right font-medium">Costo promedio</th
                ></tr
              ></thead
            >
            <tbody class="divide-y divide-border text-foreground">
              <tr
                ><th scope="row" class="py-3 font-medium">Saldo anterior</th><td
                  class="text-right tabular-nums">{number(line.previous_quantity)}</td
                ><td class="text-right tabular-nums">{money(line.previous_value)}</td><td
                  class="text-right tabular-nums">{money(line.previous_average, 6)}</td
                ></tr
              >
              <tr
                ><th scope="row" class="py-3 font-medium"
                  >{data.value_only ? 'Ajuste de valor' : 'Entrada del retaceo'}</th
                ><td class="text-right tabular-nums">{number(line.incoming_quantity)}</td><td
                  class="text-right tabular-nums">{money(line.incoming_value)}</td
                ><td class="text-right text-foreground-muted">—</td></tr
              >
              <tr class="bg-primary/5"
                ><th scope="row" class="py-3 font-semibold"
                  >{data.mode === 'posted' ? 'Saldo registrado' : 'Saldo previsto'}</th
                ><td class="text-right font-semibold tabular-nums"
                  >{number(line.resulting_quantity)}</td
                ><td class="text-right font-semibold tabular-nums">{money(line.resulting_value)}</td
                ><td class="text-right font-semibold tabular-nums"
                  >{money(line.resulting_average, 6)}</td
                ></tr
              >
            </tbody>
          </table>
        </div>
      </article>
    {/each}
    <p class="px-5 pb-5 text-xs leading-5 text-foreground-muted">
      {data.value_only
        ? 'Se proyecta el costo corregido de la recepción y su efecto en salidas y devoluciones posteriores. El promedio resultante utiliza el valor y la existencia actuales; el Kardex conserva los movimientos originales.'
        : 'Promedio = (valor anterior + costo de entrada) ÷ (cantidad anterior + cantidad recibida), expresado en la unidad base. El cálculo definitivo se registra con la recepción y conserva su historia.'}
    </p>
  {/if}
</section>
