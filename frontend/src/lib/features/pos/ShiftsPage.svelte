<script lang="ts">
  /** Turnos de caja de la sucursal: los que esperan revisión primero; filtros por estado y fecha. */
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { posApi } from '#lib/api/pos.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import type { PosShift, ShiftStatus } from '#lib/types/pos.ts';
  import ShiftReview from './ShiftReview.svelte';
  import { SHIFT_STATUS, formatDateTime, formatMoney, today } from './format.ts';

  const FILTERS: { key: string; label: string; statuses: ShiftStatus[] | undefined }[] = [
    { key: 'review', label: 'Por aprobar', statuses: ['counted'] },
    { key: 'active', label: 'En curso', statuses: ['open', 'recount'] },
    { key: 'closed', label: 'Cerrados', statuses: ['closed'] },
    { key: 'all', label: 'Todos', statuses: undefined }
  ];

  let filter = $state('review');
  let from = $state('');
  let to = $state(today());
  let items = $state<PosShift[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selected = $state<string | null>(null);
  let offset = $state(0);
  const LIMIT = 50;

  async function load() {
    loading = true;
    error = null;
    try {
      const page = await posApi.shifts({
        branchId: branch.id,
        statuses: FILTERS.find((item) => item.key === filter)?.statuses,
        from: from || null,
        to: to || null,
        limit: LIMIT,
        offset
      });
      items = page.items;
      total = page.total;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudieron cargar los turnos.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void filter;
    void from;
    void to;
    void offset;
    void branch.id;
    void load();
  });
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-end gap-3">
    <div
      class="flex flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-1"
      role="tablist"
    >
      {#each FILTERS as item (item.key)}
        <button
          type="button"
          role="tab"
          aria-selected={filter === item.key}
          class={`rounded-md px-3 py-1.5 text-sm font-medium ${filter === item.key ? 'bg-surface text-foreground shadow-sm' : 'text-foreground-muted hover:text-foreground'}`}
          onclick={() => {
            filter = item.key;
            offset = 0;
          }}>{item.label}</button
        >
      {/each}
    </div>
    <label class="text-xs font-medium text-foreground-muted">
      Desde
      <input
        type="date"
        class="mt-1 block h-9 rounded-lg border border-border bg-surface px-2 text-sm"
        value={from}
        onchange={(event) => {
          from = (event.currentTarget as HTMLInputElement).value;
          offset = 0;
        }}
      />
    </label>
    <label class="text-xs font-medium text-foreground-muted">
      Hasta
      <input
        type="date"
        class="mt-1 block h-9 rounded-lg border border-border bg-surface px-2 text-sm"
        value={to}
        onchange={(event) => {
          to = (event.currentTarget as HTMLInputElement).value;
          offset = 0;
        }}
      />
    </label>
  </div>

  {#if loading}
    <div class="space-y-2" aria-label="Cargando turnos">
      {#each [1, 2, 3, 4] as item (item)}<div class="h-14 rounded-lg skeleton"></div>{/each}
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <p>{error}</p>
      <div class="mt-3">
        <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
      </div>
    </div>
  {:else if items.length === 0}
    <div
      class="flex flex-col items-center rounded-xl border border-border bg-surface p-10 text-center"
    >
      <span
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-subtle"
        aria-hidden="true"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg
        >
      </span>
      <p class="mt-3 font-semibold text-foreground">
        {filter === 'review' ? 'Ningún turno espera revisión' : 'No hay turnos con estos filtros'}
      </p>
      <p class="mt-1 text-sm text-foreground-muted">
        Cambia el estado o las fechas para ver otros turnos.
      </p>
      {#if filter !== 'all'}
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={() => (filter = 'all')}>Ver todos</Button>
        </div>
      {/if}
    </div>
  {:else}
    <div class="overflow-x-auto rounded-xl border border-border bg-surface">
      <table class="w-full min-w-[720px] text-sm">
        <thead
          class="bg-surface-muted text-left text-xs uppercase tracking-wider text-foreground-muted"
        >
          <tr>
            <th class="px-4 py-2">Turno</th>
            <th class="px-4 py-2">Caja</th>
            <th class="px-4 py-2">Cajero</th>
            <th class="px-4 py-2">Apertura</th>
            <th class="px-4 py-2">Estado</th>
            <th class="px-4 py-2 text-right">Contado</th>
            <th class="px-4 py-2 text-right">Diferencia</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each items as item (item.id)}
            <tr class="cursor-pointer hover:bg-surface-hover" onclick={() => (selected = item.id)}>
              <td class="px-4 py-2 font-semibold"
                ><button
                  type="button"
                  class="text-left hover:underline"
                  onclick={() => (selected = item.id)}>{item.code}</button
                ></td
              >
              <td class="px-4 py-2"
                >{item.register_code}<span class="block text-xs text-foreground-muted"
                  >{item.branch_name}</span
                ></td
              >
              <td class="px-4 py-2">{item.cashier.name}</td>
              <td class="px-4 py-2 tabular-nums">{formatDateTime(item.opened_at)}</td>
              <td class="px-4 py-2"
                ><Badge variant={SHIFT_STATUS[item.status].variant}
                  >{SHIFT_STATUS[item.status].label}</Badge
                ></td
              >
              <td class="px-4 py-2 text-right tabular-nums">{formatMoney(item.counted_cash)}</td>
              <td
                class={`px-4 py-2 text-right tabular-nums ${item.cash_difference && Number(item.cash_difference) !== 0 ? 'font-semibold text-danger' : ''}`}
              >
                {item.cash_difference === null ? '—' : formatMoney(item.cash_difference)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if total > LIMIT}
      <div class="flex items-center justify-between text-sm text-foreground-muted">
        <span>{offset + 1}–{Math.min(offset + LIMIT, total)} de {total}</span>
        <div class="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={offset === 0}
            onclick={() => (offset = Math.max(0, offset - LIMIT))}>Anteriores</Button
          >
          <Button
            variant="secondary"
            size="sm"
            disabled={offset + LIMIT >= total}
            onclick={() => (offset += LIMIT)}>Siguientes</Button
          >
        </div>
      </div>
    {/if}
  {/if}
</div>

<ShiftReview shiftId={selected} onclose={() => (selected = null)} onchanged={() => void load()} />
