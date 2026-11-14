<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { fleetApi, type CostCategory, type CostReport } from '$lib/features/fleet/api';
  import {
    COST_CATEGORY_LABELS,
    costPeriods,
    formatDate,
    formatMoney,
    formatNumber,
    formatRate,
    meterShort,
    plateLabel,
    type CostPeriodId
  } from '$lib/features/fleet/catalog';
  import CostKpis from '$lib/features/fleet/CostKpis.svelte';
  import PeriodSwitch from '$lib/features/fleet/PeriodSwitch.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  const periods = costPeriods(new Date());

  let from = $state(periods.month.from);
  let to = $state(periods.month.to);
  let report = $state<CostReport | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showIdle = $state(false);
  let attempt = $state(0);

  const canRead = $derived(permissions.hasPermission('fleet:read'));
  const incomplete = $derived(!from || !to);
  const backwards = $derived(Boolean(from && to && from > to));
  const hasCosts = $derived(Number(report?.totals.total ?? 0) > 0);
  const activePeriod = $derived(
    (Object.keys(periods) as CostPeriodId[]).find(
      (id) => periods[id].from === from && periods[id].to === to
    ) ?? null
  );
  const costly = $derived((report?.rows ?? []).filter((row) => Number(row.total) > 0));
  const idleCount = $derived((report?.rows.length ?? 0) - costly.length);
  const visibleRows = $derived(showIdle ? (report?.rows ?? []) : costly);
  const categories = $derived(
    (Object.entries(report?.other_by_category ?? {}) as [CostCategory, string][]).sort(
      (a, b) => Number(b[1]) - Number(a[1])
    )
  );

  async function load(dateFrom: string, dateTo: string, signal: AbortSignal) {
    loading = true;
    error = null;
    try {
      report = await fleetApi.costReport({ date_from: dateFrom, date_to: dateTo }, signal);
    } catch (err) {
      if (signal.aborted) return;
      report = null;
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el reporte.';
    } finally {
      if (!signal.aborted) loading = false;
    }
  }

  $effect(() => {
    void branch.id;
    void attempt;
    if (!canRead || incomplete || backwards) {
      loading = false;
      return;
    }
    const controller = new AbortController();
    void load(from, to, controller.signal);
    return () => controller.abort();
  });
</script>

<svelte:head>
  <title>Costos de flota | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para ver la flota.
  </div>
{:else}
  <div class="space-y-5">
    <a href="/fleet" class="back">← Flota</a>
    <header>
      <h1 class="text-2xl font-bold tracking-tight text-foreground">Costos de flota</h1>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Combustible, mantenimiento completado, otros costos e incidentes de cada vehículo. Es un
        reporte operativo: no genera asientos contables.
      </p>
    </header>

    <section class="filters" aria-label="Periodo del reporte">
      <PeriodSwitch
        value={activePeriod}
        onselect={(id) => {
          from = periods[id].from;
          to = periods[id].to;
        }}
      />
      <div class="dates">
        <label><span>Desde</span><input type="date" bind:value={from} /></label>
        <label><span>Hasta</span><input type="date" bind:value={to} /></label>
      </div>
    </section>

    {#if incomplete}
      <p class="notice">Indica las dos fechas para ver el reporte.</p>
    {:else if backwards}
      <p class="notice danger" role="alert">La fecha inicial no puede ser posterior a la final.</p>
    {:else if error}
      <div class="notice danger retry" role="alert">
        <p>{error}</p>
        <Button size="lg" variant="secondary" onclick={() => attempt++}>Reintentar</Button>
      </div>
    {:else if loading && !report}
      <p class="muted" role="status">Cargando reporte…</p>
    {:else if report}
      {#if !hasCosts}
        <p class="notice" class:busy={loading} aria-busy={loading}>
          No hay costos entre el {formatDate(report.date_from)} y el {formatDate(report.date_to)}.
          Se registran en la ficha de cada vehículo: <a href="/fleet">ir a Flota</a>.
        </p>
      {:else}
        <div class="results" class:busy={loading} aria-busy={loading}>
          <CostKpis totals={report.totals} />
          {#if categories.length}
            <ul class="categories" aria-label="Otros costos por categoría">
              {#each categories as [category, amount] (category)}
                <li class="pill">
                  {COST_CATEGORY_LABELS[category]} <strong>{formatMoney(amount)}</strong>
                </li>
              {/each}
            </ul>
          {/if}
          <!-- Como tarjetas en el teléfono, sin estos roles el lector de pantalla pierde la tabla. -->
          <!-- svelte-ignore a11y_no_redundant_roles -->
          <table role="table">
            <caption class="sr-only">Costo por vehículo en el periodo</caption>
            <!-- svelte-ignore a11y_no_redundant_roles -->
            <thead role="rowgroup">
              <!-- svelte-ignore a11y_no_redundant_roles -->
              <tr role="row">
                <th role="columnheader" scope="col">Vehículo</th>
                <th role="columnheader" scope="col" class="num">Combustible</th>
                <th role="columnheader" scope="col" class="num">Mantenimiento</th>
                <th role="columnheader" scope="col" class="num">Otros</th>
                <th role="columnheader" scope="col" class="num">Incidentes</th>
                <th role="columnheader" scope="col" class="num">Total</th>
                <th role="columnheader" scope="col" class="num">Recorrido</th>
                <th role="columnheader" scope="col" class="num">Costo por km u hora</th>
              </tr>
            </thead>
            <!-- svelte-ignore a11y_no_redundant_roles -->
            <tbody role="rowgroup">
              {#each visibleRows as row (row.vehicle_id)}
                {@const unit = meterShort(row.meter_unit)}
                <!-- svelte-ignore a11y_no_redundant_roles -->
                <tr role="row">
                  <td role="cell" class="vehicle-cell">
                    <div class="vehicle">
                      <a href={`/fleet/${row.vehicle_id}?tab=costs&from=${from}&to=${to}`}
                        >{row.code}</a
                      >
                      <strong class="card-total" aria-hidden="true">{formatMoney(row.total)}</strong
                      >
                      <small>{plateLabel(row.plate)} · {row.kind_name} · {row.branch_name}</small>
                    </div>
                  </td>
                  <td role="cell" class="num" data-label="Combustible">{formatMoney(row.fuel)}</td>
                  <td role="cell" class="num" data-label="Mantenimiento">
                    {formatMoney(row.maintenance)}
                  </td>
                  <td role="cell" class="num" data-label="Otros">{formatMoney(row.other)}</td>
                  <td role="cell" class="num" data-label="Incidentes">
                    {formatMoney(row.incidents)}
                  </td>
                  <td role="cell" class="num total-cell" data-label="Total">
                    {formatMoney(row.total)}
                  </td>
                  <td role="cell" class="num" data-label="Recorrido">
                    {formatNumber(row.distance)}
                    {unit}
                  </td>
                  <td role="cell" class="num" data-label={`Costo por ${unit}`}>
                    {row.cost_per_unit ? formatRate(row.cost_per_unit) : '—'}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
          {#if idleCount > 0}
            <button
              type="button"
              class="idle"
              aria-expanded={showIdle}
              onclick={() => (showIdle = !showIdle)}
            >
              {showIdle
                ? 'Ocultar vehículos sin costos'
                : `Mostrar ${idleCount} ${idleCount === 1 ? 'vehículo' : 'vehículos'} sin costos`}
            </button>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .back {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .back:hover {
    color: rgb(var(--foreground));
  }
  .filters {
    display: grid;
    gap: 12px;
  }
  .dates {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .idle {
    justify-self: start;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  label {
    display: grid;
    min-width: 0;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
    color: rgb(var(--foreground));
  }
  input {
    width: 100%;
    min-width: 0;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 16px;
  }
  .results {
    display: grid;
    gap: 16px;
    transition: opacity 150ms ease;
  }
  .busy {
    opacity: 0.55;
  }
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .categories {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    list-style: none;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .pill {
    padding: 6px 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
  }
  .pill strong {
    color: rgb(var(--foreground));
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .notice {
    padding: 14px 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .notice a {
    color: rgb(var(--foreground));
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .retry {
    display: grid;
    gap: 10px;
    justify-items: start;
  }
  .danger {
    border-color: rgb(var(--danger) / 0.3);
    color: rgb(var(--danger));
  }
  /* En el teléfono cada vehículo es una tarjeta: una tabla de 7 columnas obligaría a deslizar. */
  table,
  tbody,
  tr,
  td {
    display: block;
  }
  thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  tbody {
    display: grid;
    gap: 10px;
  }
  tr {
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  td {
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  td.num {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 3px 0;
    font-variant-numeric: tabular-nums;
  }
  td.num::before {
    content: attr(data-label);
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  /* El total ya encabeza la tarjeta; el aria-hidden de arriba deja esta celda para el lector. */
  td.total-cell {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  .vehicle {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 2px 12px;
    margin-bottom: 8px;
  }
  .vehicle a {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    min-height: 44px;
    color: rgb(var(--foreground));
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .card-total {
    font-size: 16px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .vehicle small {
    grid-column: 1 / -1;
  }
  @media (min-width: 768px) {
    .filters {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: space-between;
    }
    .dates {
      width: 340px;
    }
    input {
      min-height: 38px;
      font-size: 13px;
    }
    tbody {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  /* Con el menú lateral abierto, antes de este ancho la tabla no cabe. */
  @media (min-width: 1200px) {
    table {
      display: table;
      width: 100%;
      overflow: hidden;
      border: 1px solid rgb(var(--border));
      border-collapse: separate;
      border-spacing: 0;
      border-radius: 12px;
      background: rgb(var(--surface));
    }
    thead {
      position: static;
      display: table-header-group;
      width: auto;
      height: auto;
      clip-path: none;
    }
    tbody {
      display: table-row-group;
    }
    tr {
      display: table-row;
      padding: 0;
      border: 0;
      border-radius: 0;
    }
    th,
    td,
    td.num {
      display: table-cell;
      padding: 10px 14px;
      border-bottom: 1px solid rgb(var(--border));
      text-align: left;
      vertical-align: middle;
    }
    tbody tr:last-child td {
      border-bottom: 0;
    }
    th {
      color: rgb(var(--foreground-muted));
      font-size: 12px;
      font-weight: 600;
    }
    th.num,
    td.num {
      text-align: right;
      white-space: nowrap;
    }
    td.num::before {
      content: none;
    }
    td.total-cell {
      position: static;
      width: auto;
      height: auto;
      overflow: visible;
      clip-path: none;
      font-weight: 600;
    }
    .card-total {
      display: none;
    }
    .vehicle {
      display: block;
      margin-bottom: 0;
    }
    .vehicle small {
      display: block;
    }
  }
</style>
